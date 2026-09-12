import os
import json
import time
import openpyxl
from pydantic import BaseModel, Field
from google import genai
from google.genai import types


class NormAreaItem(BaseModel):
    nombre_norma: str = Field(description="Nombre de la norma analizada.")
    area_sugerida: str = Field(description="Nombre exacto del area responsable, tomado de la lista de areas disponibles. 'ND' si no hay suficiente informacion.")
    justificacion_area: str = Field(description="Explicacion concisa (maximo 250 palabras) del porque se asigno esa area o areas, citando los temas o materias de la norma que motivaron la decision. 'ND' si no hay suficiente informacion.")


def load_areas_from_excel(excel_path: str) -> str:
    """Lee Base_Areas.xlsx y genera un string con las areas disponibles para el prompt."""
    wb = openpyxl.load_workbook(excel_path)
    ws = wb.active

    areas_text = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        grupo = row[0] or ""
        subgrupo = row[1] or ""
        temas = row[2] or ""
        # Limpiar saltos de linea en temas
        temas_clean = temas.replace("\n", ", ").strip().strip(",").strip()
        areas_text.append(f"- Grupo: {grupo} | Area: {subgrupo} | Temas: {temas_clean}")

    wb.close()
    return "\n".join(areas_text)


def classify_single_norm_area(norm: dict, areas_context_str: str) -> dict:
    """Clasifica el area responsable de una norma individual."""

    nombre = norm.get("Nombre_norma", "")
    contenido = norm.get("Contenido", "")
    resumen = norm.get("resumen_norma", "")
    entidad = norm.get("Entidad", "")

    prompt = f"""Eres un experto en Organizacion Empresarial y Procesos en una compania de Seguros.

Tu tarea es identificar que AREA o GERENCIA es responsable de atender una norma legal, usando la base de areas definida.

--- LISTA DE AREAS DISPONIBLES ---
{areas_context_str}
--- FIN LISTA DE AREAS ---

--- NORMA A CLASIFICAR ---
Nombre: {nombre}
Entidad emisora: {entidad}
Resumen: {resumen}

Contenido completo:
{contenido}
--- FIN NORMA ---

REGLAS DE CLASIFICACION:

1. Identifica la coincidencia mas fuerte con la LISTA DE AREAS DISPONIBLES.

2. Asignacion por especialidad:
   - Seguros -> area tecnica de seguros correspondiente
   - Inversiones -> area de inversiones
   - Riesgos -> gestion de riesgos
   - Contabilidad -> finanzas/contabilidad
   (usar siempre nombres EXACTOS de la lista, campo "Area")

3. Si la norma es general o transversal:
   -> "Cumplimiento" (del grupo Riesgos)

4. Si no hay suficiente informacion:
   -> "ND"

IMPORTANTE:
- No inventar areas. Usar UNICAMENTE las areas de la lista.
- Priorizar precision sobre inferencias debiles.
- El valor de area_sugerida debe coincidir EXACTAMENTE con un valor del campo "Area" de la lista.

JUSTIFICACION (campo justificacion_area):
- Redacta una explicacion CONCISA, en espanol, de POR QUE se asigno esa area (o areas).
- Apoyate en los temas, materias o entidad de la norma que motivaron la decision.
- LIMITE ESTRICTO: maximo 250 palabras. Preferible 100-150.
- No repitas el contenido completo de la norma; solo el razonamiento.
- Si no hay suficiente informacion para clasificar, devuelve "ND" tambien en justificacion_area.

Retorna: nombre_norma, area_sugerida, justificacion_area.
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
                    response_schema=NormAreaItem,
                    max_output_tokens=8192,
                    temperature=0,
                ),
            )

            if response.parsed:
                return response.parsed.model_dump()
            elif response.text:
                return json.loads(response.text)
            else:
                finish_reason = "UNKNOWN"
                try:
                    if response.candidates:
                        finish_reason = str(getattr(response.candidates[0], "finish_reason", "UNKNOWN"))
                except Exception:
                    pass
                raise ValueError(
                    f"Respuesta de Gemini sin contenido (finish_reason={finish_reason})"
                )

        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                if intento < intentos_maximos - 1:
                    time.sleep(30)
                    continue

            return {
                "nombre_norma": nombre,
                "area_sugerida": f"ERROR: {str(e)}",
                "justificacion_area": f"ERROR: {str(e)}"
            }

    return {}
