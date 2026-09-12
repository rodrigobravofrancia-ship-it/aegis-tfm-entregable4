import os
import json
import time
from pydantic import BaseModel, Field
from typing import List
from google import genai
from google.genai import types


class NormAnalysisData(BaseModel):
    resumen_norma: str = Field(description="Resumen de la norma en maximo 40 palabras, basado en el campo Contenido. Debe capturar la idea principal y mas relevante.")
    articulos: str = Field(description="TODOS los articulos mencionados en el Contenido, extraidos de forma TEXTUAL sin resumir ni modificar.")
    principales_consideraciones_1: str = Field(description="Punto mas relevante extraido del contenido de la norma, en orden de importancia (1ro).")
    principales_consideraciones_2: str = Field(description="Segundo punto mas relevante extraido del contenido de la norma.")
    principales_consideraciones_3: str = Field(description="Tercer punto mas relevante extraido del contenido de la norma.")
    tipo_alerta: str = Field(description="Clasificacion de la norma: 'Implementacion', 'Informativa' o 'No Aplica'.")
    justificacion_tipo_alerta: str = Field(description="Explicacion breve y clara del porque de la clasificacion tipo_alerta asignada.")


def analyze_norm(norm: dict) -> dict:
    """Analiza una norma individual y retorna los campos de enriquecimiento."""

    contenido = norm.get("Contenido", "")
    nombre = norm.get("Nombre_norma", "")
    tipo = norm.get("Tipo_norma", "")
    entidad = norm.get("Entidad", "")
    glosa = norm.get("Glosa", "")

    prompt = f"""Eres un agente experto en cumplimiento normativo del sector seguros y salud en Peru.

Analiza la siguiente norma legal publicada en El Peruano y genera los campos solicitados.

--- DATOS DE LA NORMA ---
Nombre: {nombre}
Tipo: {tipo}
Entidad: {entidad}
Glosa: {glosa}
Contenido:
{contenido}
--- FIN DATOS ---

CAMPOS A GENERAR:

1. resumen_norma: Maximo 40 palabras. Basado en el Contenido. Captura la idea principal y mas relevante.

2. articulos: Extrae TODOS los articulos mencionados en el Contenido. Deben ser TEXTUALES, sin resumir ni modificar. Si no hay articulos, indica "No contiene articulos". No incluyan tablas, solo texto
3. principales_consideraciones_1, principales_consideraciones_2, principales_consideraciones_3: Los 3 puntos mas relevantes del contenido, en orden de importancia.

4. tipo_alerta: Clasifica la norma en una de estas categorias:

  📌 Reglas de Clasificación (Reference)

🔴 Implementación (Normativa):
Implica adecuación, obligación, cambios operativos o legales clave.
- Palabras clave: seguros, EPS, IAFAS, póliza, prima, cobertura, siniestro, reservas técnicas, tarifas actuariales, suscripción, seguros de vida, SCTR, SOAT, microseguros, vida ley, fianzas, cauciones.
- Temas: protección de datos, libre competencia, antisoborno, anticorrupción, gestión de riesgos, inversiones, reclamos, atención al usuario, IA.
- ⚠️ IMPORTANTE: Si la norma NO tiene obligaciones directas para el sector seguros, NO debe ser "Implementación" sino "Informativa".

🟡 Informativa:
Propósito de difusión, consulta pública o disposiciones generales sin impacto operativo directo inmediato.
- Difusión/Consulta: prepublicación, proyecto, reglamento, directivas, comentarios.
- Disposiciones: emergencias, designaciones, renuncias generales, campañas sanitarias.
- Entidades Salud: farmacias, dispositivos médicos, droguerías, laboratorios, registro sanitario.
- Emisores: MINSA, Ministerio de Salud, SUNAT, Municipalidades de Lima, San Isidro, San Borja.
- 💡 NUEVAS REGLAS:
  - Normas que se publican **TRIMESTRALMENTE** o periódicamente de forma rutinaria.
  - Normas emitidas por la **SBS** que modifiquen **MONTOS DE CAPITAL** de aseguradoras (si no afectan directamente a Rimac).
  - Normas que generen **OBLIGACIONES INDIRECTAS** al sector seguros.
  - Normas relacionadas al **"Impuesto Vehicular"** o Impuesto al Patrimonio Vehicular (son siempre Informativas).
  - Normas que deleguen facultades para la **suscripción de contratos** de prestación de servicios de seguridad social en salud o representación ante **EsSalud** (Informativa por impacto en procesos/auditoría).
  - La **"Norma Técnica de Salud para el Manejo de la Cadena de Frío en Inmunizaciones"** (Se considera Informativa porque Rímac realiza campañas de vacunación en coordinación con clínicas y el ámbito de aplicación incluye empresas privadas).
  - Normas sobre **"innovación pública"** que mencionen "salud" como área de aplicación (Se considera Informativa por relevancia indirecta al sector).
  - ⚠️ **SINO ES EL DISTRITO DE ALGUNA REGION DE LIMA O AREQUIPA O TRUJILLO NO CUENTA**.
  - 🚫 **ATALAYA NI NINGUN DISTRITO EXTERNO NO CONOCIDO NO CUENTA**.
  - 🛑 **SI ESTABLECE INFRACCION PARA RIMAC NO PUEDE SER INFORMATIVA** (Debe ser Implementación).
  - 📍 **JULIACA PUNO NO AFECTA A LIMA ES NO APLICA**.
  - 💰 Normas que modifiquen el **sistema de pago de obligaciones tributarias (detracciones)** son siempre **Informativas**.
  - 📱 La norma que habilita la **billetera digital** para el pago de haberes y otras obligaciones laborales (**Ley N° 32413**) se considera **Informativa** (es una opción de pago aunque la empresa use transferencias).
  - 🛂 Las normas relacionadas a la **Ley de Migraciones** son siempre **Informativas**.
  - 📝 Si una norma de la **SUNAT** trata sobre **sanciones tributarias** es una norma **Informativa**.
  - 🚢 Si la norma aprueba los montos de las **cartas fianzas o pólizas de caución** y los formatos **OPS 11 (A y B)** para agencias marítimas, fluviales, lacustres y empresas/cooperativas de estiba y desestiba, no genera obligaciones directas para Rimac ni para el sector asegurador. Su alcance es específico al ámbito portuario y financiero de dichas agencias, por lo que se clasifica como **Informativa**, con impacto indirecto y relevancia únicamente como conocimiento general del marco regulatorio portuario.

⚫ No Aplica:
Normas que no generan impacto operativo ni informativo relevante para el área de cumplimiento.
- Autorizaciones de viaje.
- Funcionarios (renuncias/designaciones) EXCEPTO SBS/SUSALUD de alto rango.
- Gerencia municipal, decretos alcaldía, ordenanzas (EXCEPTO Lima, Arequipa, Trujillo).
- Instituciones educativas, JNE, JEF, DEVIDA.
- Otras municipalidades, CAP-P.
- 🚫 REGLAS ESTRICTAS DE NEGOCIO:
  a) Clasifica como "No Aplica" si afecta a sectores NO RELEVANTES para Seguros/Salud (Pesca, Agro, etc.).
  b) Clasifica como "No Aplica" si son CAMBIOS ADMINISTRATIVOS u organizativos de cualquier MINISTERIO.
  c) Clasifica como "No Aplica" si son RENUNCIAS o NOMBRAMIENTOS de funcionarios (asesores, directores) incluso en Salud/SBS, a menos que sea el Ministro/Superintendente.
  d) Clasifica como "No Aplica" si son CONDICIONES ESTÁNDAR u OBVIAS ya existentes (ej. "soat para", "licencia para", "soat vigente para" como requisito previo).
  e) Si NO es una INFRACCIÓN DIRECTA ante la SBS u organismo estatal, es siempre "No Aplica" (ej. "si no es una infracción...").
  f) Las de tipo "RESOLUCION DE PRESIDENCIA DEL CONSEJO DIRECTIVO", "RESOLUCION GERENCIAL", **"RESOLUCION JEFATURAL"**, **"RESOLUCION SUPREMA"**, **"RESOLUCION DE SECRETARÍA GENERAL"**, **"RESOLUCION DIRECTORAL"** o **"DECRETO MUNICIPAL"** son siempre "No Aplica".
  g) Clasifica como "No Aplica" si impacta **SOLO al SIS** (Sistema Integrado de Salud) y no a privados.
  h) Clasifica como "No Aplica" si la norma **NO IMPACTA al SECTOR ASEGURADOR** (Rimac).
  i) Clasifica como "No Aplica" cualquier norma de distritos que NO pertenezcan a las regiones de **LIMA, AREQUIPA o TRUJILLO**. ATALAYA y distritos externos no conocidos son siempre **No Aplica**.
  j) Clasifica como "No Aplica" si NO es una norma emitida por la SBS ni establece infracciones para entidades reguladas por la SBS.
  k) Clasifica como "No Aplica" si es una norma para las AFP (Administradoras de Fondos de Pensiones) que no aplique al sector seguros.
  l) Clasifica como **"No Aplica"** si es una norma emitida por un **Ministerio** y tras el análisis determinas que no genera obligaciones directas ni impacto relevante para el sector seguros o salud privada.
  m) Clasifica como **"No Aplica"** cualquier **RENUNCIA o NOMBRAMIENTO de funcionarios en SUSALUD**, sin importar el rango.
  n) Si la norma NO menciona expresamente términos relacionados a **SEGUROS, ASEGURADORAS, EPS, PÓLIZA, COBERTURA** o **SALUD PRIVADA**, es siempre **"No Aplica"**.
  o) Clasifica como **"No Aplica"** si trata sobre temas médicos/clínicos/sanitarios específicos que no impactan al negocio asegurador (ej. **"Banco de Leche Humana"**, **"Lactancia Materna"**, **"Día de la Salud [X]"**).
  p) Clasifica como **"No Aplica"** si trata sobre **SECTOR TRANSPORTE** (Revisiones Técnicas, licencias de conducir, profesionalización de conductores, autorizaciones de rutas) o **INFRAESTRUCTURA** (Drenaje Pluvial, saneamiento, electricidad) sin impacto directo en la regulación de seguros.
  q) Clasifica como **"No Aplica"** si el título de la norma indica expresamente que es para entidades **"distintas a las empresas del sistema financiero, empresas de seguros"**.
  r) Las normas de tipo **"RESOLUCION VICE MINISTERIAL"** son siempre **"No Aplica"**, a menos que su análisis de contexto determine un impacto directo e indudable en las compañías de seguros.
  s) Clasifica como **"No Aplica"** el padrón nominal de la población menor de seis años como instrumento del Organismo de Focalización e Información Social (**OFIS**) (No tiene relación con seguros).
  t) Clasifica como **"No Aplica"** normas que supervisan o fiscalizan los servicios de **defensa pública** o promueven mecanismos alternativos de solución de conflictos (No tiene relación con seguros).
  u) Clasifica como **"No Aplica"** si se modifican **facultades internas del MINSA** o se realizan **modificaciones de cargos/cuadros de personal** que no tengan relación directa con el negocio de seguros.
  v) Clasifica como **"No Aplica"** las **autorizaciones de viaje de funcionarios de la SBS**.
  w) Clasifica como **"No Aplica"** las normas sobre **"innovación pública"** y "salud" si tras el análisis determinas que el contexto **NO afecta al sector seguros**.
  x) Clasifica como **"No Aplica"** si la norma es una **delegación de facultades** en diversos funcionarios de **SENCICO** (No afecta al sector seguros).
  y) Clasifica como **"No Aplica"** si la norma trata sobre el **ingreso de una empresa bancaria al Estado**.
  z) Clasifica como **"No Aplica"** si la norma declara la **intervención de una cooperativa de ahorro y crédito**.
  aa) Clasifica como **"No Aplica"** si la norma es una **disposición administrativa general del Poder Judicial** sobre su organización y productividad.
  ab) Clasifica como **"No Aplica"** si la norma trata sobre la **delegación de facultades administrativas internas del IIAP** para su representación.
  ac) Clasifica como **"No Aplica"** cualquier norma referente a **JULIACA o PUNO**, ya que no afectan a Lima ni a las zonas de interés principal.
  ad) Clasifica como **"No Aplica"** normas sobre devolución del **ISC para transportistas**.
  ae) Clasifica como **"No Aplica"** normas sobre límites máximos para la incorporación de mayores ingresos públicos para **gasto corriente**.
  af) Clasifica como **"No Aplica"** la administración de **recursos públicos** sin vinculación a Rimac.
  ag) Clasifica como **"No Aplica"** la **transferencia de funciones** sectoriales de transporte a la Municipalidad de Lima.
  ah) Clasifica como **"No Aplica"** si la norma trata sobre el **"Impuesto a las Embarcaciones de Recreo"**.
  ai) Clasifica como **"No Aplica"** si la norma tiene relación con la **"utilización de los fondos climáticos"**.
  aj) Clasifica como **"No Aplica"** si la norma regula el uso de **teléfonos celulares** en Educación Básica.
  ak) Clasifica como **"No Aplica"** la Ley de titulación de terrenos (**posesiones informales**).
  al) Clasifica como **"No Aplica"** el Reglamento de Desarrollo del **Turismo Comunitario**.
  al) **Considerar "No Aplica"** las normas sobre el proceso especial de **colaboración eficaz** (Modificación del Reglamento del Decreto Legislativo N° 1301), por ser estrictamente de ámbito penal/procesal y no afectar al sector asegurador.
  am) Clasifica como **"No Aplica"** las **transferencias financieras** destinadas a Gobiernos Regionales distintos a Lima, Arequipa o Trujillo (ej. **Gobierno Regional de Pasco**), por ser irrelevantes para la operación.
  an) Si la norma u ordenanza tiene un **alcance limitado** a una zona específica (un solo distrito o municipalidad) y no es de carácter nacional o metropolitano, es **No Aplica**.
  ao) Las **Directivas Administrativas del MINSA** son siempre **No Aplica**.
  ap) Clasifica como **"No Aplica"** las normas de carácter **penal, urbanístico, electoral, educativo, etc.**, que aunque sean nacionales, no tienen impacto material en seguros ni en el cumplimiento normativo del sector.
  ap) Si el documento es una resolución, ordenanza o decisión que aplica **únicamente a un caso específico**, persona determinada o jurisdicción local puntual, es **No Aplica**.
  aq) Normas que regulan aspectos de un **sector muy limitado** (ej. servicios aeroportuarios, una sola municipalidad, un caso puntual) son **No Aplica**.
  ar) Normas que regulen **planes urbanos, ordenanzas metropolitanas o disposiciones territoriales específicas** (ej. "Lima Balnearios del Sur") son **No Aplica** por su alcance geográfico limitado.
  ba) Las normas u ordenanzas que tengan que ver con **OSIPTEL** son **No Aplica**, ya que no tienen relación directa con el sector seguros.
  bb) Las **ordenanzas municipales**, incluso de distritos críticos como **Santiago de Surco**, deben clasificarse como **No Aplica** por su alcance limitado a una jurisdicción local específica.
  bc) Normas de **INDECOPI** que declaren barreras burocráticas ilegales en municipalidades (ej. San Isidro sobre preescolares), son **No Aplica**. Se consideran de gravedad **Leve** por baja relevancia e impacto nulo en el negocio.
  bd) Normas sobre **juegos de lotería** son **No Aplica**, no tienen relación con seguros.
  be) La aprobación o actualización de formularios virtuales como el **PDT ISC (Formulario Virtual N° 615)** es **No Aplica**, por ser actualizaciones de normas rutinarias.
  bf) Las **"Fe de erratas"** de Decretos Legislativos que corrijan aspectos técnicos sobre el **control del valor en aduanas** son **No Aplica**.

   ANALISIS DE CONTEXTO (CRITICO): NO te bases solo en keywords. Evalua la intencion real de la norma.
   Ejemplo: Si menciona "SOAT" como requisito -> NO es implementacion. Puede ser Informativa o No Aplica.

5. justificacion_tipo_alerta: Explicacion breve y clara del porque de la clasificacion tipo_alerta asignada. Evalua, valida o corrige la clasificacion. Justifica tu decision.
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
                    response_schema=NormAnalysisData,
                    max_output_tokens=60192,
                    temperature=0.15,
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
                "resumen_norma": f"ERROR: {str(e)}",
                "articulos": "ERROR",
                "principales_consideraciones_1": "ERROR",
                "principales_consideraciones_2": "ERROR",
                "principales_consideraciones_3": "ERROR",
                "tipo_alerta": "ERROR",
                "justificacion_tipo_alerta": "ERROR",
            }

    return {}
