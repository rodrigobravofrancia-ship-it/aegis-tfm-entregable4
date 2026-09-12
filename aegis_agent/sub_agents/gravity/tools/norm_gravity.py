import os
import json
import time
from pydantic import BaseModel, Field
from google import genai
from google.genai import types


class NormGravityItem(BaseModel):
    nombre_norma: str = Field(description="Nombre de la norma analizada.")
    gravedad: str = Field(description="Nivel de gravedad: 'Leve', 'Moderado', 'Grave' o 'No Aplica'.")
    justificacion_gravedad: str = Field(description="Justificacion clara de la clasificacion de gravedad asignada.")


CONTEXTO_NORMATIVO = """
Modifican anexos del Reglamento de Infracciones y Sanciones de la Superintendencia de Banca, Seguros y Administradoras Privadas de Fondos de Pensiones
RESOLUCION SBS N° 00013-2024

ANEXO 1 - INFRACCIONES COMUNES

I. INFRACCIONES LEVES
26) Incumplir con el plazo y/o suministrar informacion incorrecta declaracion jurada propietarios significativos...
64)

II. INFRACCIONES GRAVES
9) Incumplir obligaciones debida diligencia reforzada...
10) Banca corresponsal: no aplicar debida diligencia reforzada...
14) No contar con Manual prevencion LA/FT...
15) No implementar politicas gestion riesgos LA/FT...
16) No haber elaborado identificacion/evaluacion riesgos LA/FT...
23) Oficial de Cumplimiento: no informar designacion, no contar con Programa Anual...
48) No evaluar riesgos cambios ambiente negocio/nuevos productos...
53) No mantener base de datos personas vinculadas...
71) Oficial Conducta Mercado: no contar con oficial, no cumpla requisitos...
79) Servicios significativos/subcontratados: no seleccion proveedor, no incluir requerimientos minimos, no gestionar riesgos...
80) No contar con Manual Riesgo Operacional...
81) No presentar Informe Evaluacion idoneidad moral...
82) Aplicar/cobrar primas seguro desgravamen no conformes...
83) No informar trimestralmente cumplimiento plan adecuacion solvencia...
84) No contar con Codigo de Etica y Conducta...
85) Incumplir mandatos SBS con impacto material (situacion financiera <5% patrimonio)...

III. INFRACCIONES MUY GRAVES
22) No cumplir condiciones pactadas (impacto >= 100 UIT)...
23) Practicas negocio no ajustadas gestion conducta mercado (impacto >= 100 UIT)...
24) Cobrar primas seguro desgravamen no conformes (impacto >= 100 UIT)...
25) Incumplir normas libros/registros contables con impacto material (>5% patrimonio)...
26) Incumplir mandatos SBS con impacto material (>5% patrimonio)...
"""

ESCALA_MULTAS_SBS = """
ESCALA REFERENCIAL DE MULTAS (Reglamento de Infracciones y Sanciones SBS):
- LEVES: Amonestacion o Multa (Generalmente < 20 UIT).
- GRAVES: Multa de 20 UIT hasta 100 UIT. (Impacto economico significativo).
- MUY GRAVES: Multa > 100 UIT, o revocacion de licencia/intervencion. (Impacto economico muy alto o sistemico).
*Nota: UIT (Unidad Impositiva Tributaria) vigente debe considerarse segun el ano de infraccion.
"""


def classify_single_norm_gravity(norm: dict) -> dict:
    """Clasifica la gravedad de una norma individual basandose en la Resolucion SBS N 00013-2024."""

    nombre = norm.get("Nombre_norma", "")
    contenido = norm.get("Contenido", "")
    resumen = norm.get("resumen_norma", "")
    tipo_alerta = norm.get("tipo_alerta", "")
    consideraciones_1 = norm.get("principales_consideraciones_1", "")
    consideraciones_2 = norm.get("principales_consideraciones_2", "")
    consideraciones_3 = norm.get("principales_consideraciones_3", "")

    prompt = f"""Eres un agente experto en Riesgos, Cumplimiento y Sanciones de la SBS (Superintendencia de Banca y Seguros del Peru).

Tu tarea es clasificar la gravedad de infracciones potenciales para una empresa de seguros y salud (ej. Rimac), basandote EXCLUSIVAMENTE en:

1. La RESOLUCION SBS N° 00013-2024
2. La escala referencial de multas SBS
3. El impacto operativo real en la compania

--- CONTEXTO NORMATIVO ---
{CONTEXTO_NORMATIVO}
--- FIN CONTEXTO NORMATIVO ---

--- ESCALA DE MULTAS ---
{ESCALA_MULTAS_SBS}
--- FIN ESCALA DE MULTAS ---

--- NORMA A CLASIFICAR ---
Nombre: {nombre}
Resumen: {resumen}
Tipo de alerta: {tipo_alerta}
Principales consideraciones 1: {consideraciones_1}
Principales consideraciones 2: {consideraciones_2}
Principales consideraciones 3: {consideraciones_3}

Contenido completo:
{contenido}
--- FIN NORMA ---

REGLAS DE CLASIFICACION:

1. MATCH CON SBS (PRIORIDAD ALTA):
   Compara con el CONTEXTO NORMATIVO:
   - Infraccion LEVE -> gravedad "Leve"
   - Infraccion GRAVE (20-100 UIT) -> gravedad "Moderado"
   - Infraccion MUY GRAVE (>100 UIT) -> gravedad "Grave"

2. ANALISIS DE IMPACTO (SI NO HAY MATCH):
   - Leve: Impacto administrativo, ajustes documentarios, bajo riesgo (<10 UIT).
   - Moderado: Impacto operativo, riesgo de sancion (10-50 UIT), observaciones regulatorias.
   - Grave: Impacto critico, multas >50 UIT, riesgo reputacional o intervencion.

3. ANALISIS DE CONTEXTO (CRITICO):
   - NO usar solo palabras clave. Evaluar intencion real.
   - Ejemplo: "SOAT" como requisito -> Leve o No Aplica.
   - Solo asignar Moderado o Grave si: cambia obligaciones, introduce sanciones, o impacta negocio asegurador.

4. USO DE tipo_alerta (SENAL COMPLEMENTARIA, no criterio unico):
   - Implementacion -> mayor gravedad.
   - Informativa -> menor gravedad.
   - No Aplica -> "No Aplica".

JUSTIFICACION:
- Si hay referencia SBS: "Severidad [X] segun Anexo 1 - numeral [Y]"
- Si es por impacto: "Impacto [X] debido a [riesgo]"
- Aclarar si es cambio regulatorio o mencion administrativa.

Retorna: nombre_norma, gravedad ("Leve", "Moderado", "Grave" o "No Aplica"), justificacion_gravedad.
"""

    client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
    intentos_maximos = 3

    for intento in range(intentos_maximos):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=NormGravityItem,
                    max_output_tokens=8192,
                    temperature=0,
                ),
            )

            if response.parsed:
                return response.parsed.model_dump()
            else:
                return json.loads(response.text)

        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                if intento < intentos_maximos - 1:
                    time.sleep(30)
                    continue

            return {
                "nombre_norma": nombre,
                "gravedad": "ERROR",
                "justificacion_gravedad": f"ERROR: {str(e)}"
            }

    return {}
