import os
import json
import tempfile
import shutil
import uuid
from pydantic import BaseModel, Field
from typing import List
from google import genai
from google.genai import types

class SourceDocumentInfo(BaseModel):
    pdf_path: str
    norm_reference_name: str

class MetadataInfo(BaseModel):
    source: str = Field(description="Fuente de donde proviene el documento (ej. El Peruano)")
    processing_type: str = "norm_extraction"
    language: str = "es-PE"

class NormData(BaseModel):
    Nombre_norma: str = Field(description="Nombre del archivo PDF de la norma, sin la extensión .pdf")
    Tipo_norma: str = Field(description="Tipo de norma extraído del nombre del archivo PDF. Suele encontrarse al inicio del nombre, antes del código de la norma. Sin espacios al inicio ni al final.")
    Codigo_norma: str = Field(description="Código de la norma: parte numérica y siglas del nombre del archivo PDF, ubicada después de 'N°'. Sin espacios al inicio ni al final, sin la extensión .pdf.")
    Entidad: str = Field(description="Institución o Entidad emisora de la norma (ej. Ministerio, Municipalidad, Consejo). Colocarlo siempre en mayúsculas")
    Glosa: str = Field(description="Texto ubicado inmediatamente encima del título de la norma.")
    Fecha_publicacion: str = Field(description="Fecha ubicada en la parte superior del PDF, cerca del logo y texto: El Peruano. Formato: YYYY-MM-DD")
    Contenido: str = Field(description="Texto completo y literal del cuerpo de la norma de referencia.")
    source_document: SourceDocumentInfo

class NormExtractionOutput(BaseModel):
    metadata: MetadataInfo
    norms: List[NormData]

import time

def extract_norm_from_pdf(pdf_path: str, norm_ref_name: str, pdf_basename: str) -> dict:
    prompt = f"""
    Eres un asistente legal experto en extraer normas del diario 'El Peruano'.
    OJO: Un PDF de El Peruano puede contener una ÚNICA norma (que abarca todo el documento) o puede agrupar múltiples normas distintas separadas por grandes espacios, líneas divisorias 'y/o' cuadros, lo podrás reconocer cuando veas que aparece otra norma en un espacio central o protagónico (no dentro de texto extenso).
    Tu MISIÓN es enfocar tu atención ÚNICAMENTE en el "bloque o sección" correspondiente a la norma cuyo título coincide exactamente con: "{norm_ref_name}" (a esto le llamaremos tu 'Ancla').
    Si el documento tiene varias normas, ignora por completo el resto. Si solo tiene una, tu 'Ancla' dominará todo el documento.

    Dentro de la sección que le pertenece a tu 'Ancla', extrae la información basándote en esta estructura visual:

    1. Título de referencia (Ancla): "{norm_ref_name}". Todo lo que busques girará en torno a este título, sin saltar a otra norma, usualmente separada por líneas, grandes espacios o bloques de texto.
    2. Glosa: Es el título descriptivo (generalmente en negrita) que resume tu norma. Lo encontrarás un poco MÁS ARRIBA de tu 'Ancla', pero siempre perteneciendo a la misma norma.
    3. Entidad: Es la institución emisora de tu norma. Su ubicación varía:
       - Puede estar ARRIBA de la Glosa (ej. en un banner o cuadro como "MUNICIPALIDAD DE...").
       - Puede estar ABAJO de la Glosa y ARRIBA del 'Ancla' (ej. "COMISIÓN DE DUMPING...").
       - Ubícala revisando los escasos renglones inmediatamente superiores a tu 'Ancla', dentro de tu mismo bloque.
    4. Contenido: Es TODO el texto de la norma que empieza INMEDIATAMENTE DEBAJO de tu 'Ancla' (Título). Empieza con el lugar/fecha (ej. "Lima, 9 de marzo..."), seguido de VISTO, CONSIDERANDO, SE RESUELVE, etc. Extrae todo este texto literal de forma completa.
       - OJO CON LOS SALTOS DE PÁGINA/COLUMNA: Si la norma no ha terminado al final de la página o columna, CONTINÚA extrayendo el resto del texto en la siguiente, ignorando cualquier encabezado del periódico (ej. "El Peruano / Miércoles... NORMAS LEGALES").
       - FINAL DE LA NORMA: Asegúrate de incluir los párrafos finales como "Regístrese, comuníquese y publíquese" y el texto hasta el final real. Tu norma TERMINA y dejas de extraer cuando encuentres: una línea divisoria grande o gruesa que tiene posteriormente glosa de otra norma, un nuevo título de norma, o un recuadro separador (ej. "PROVINCIAS").
    5. Fecha_publicacion: Siempre está en la cabecera general de la página (al costado del logotipo "El Peruano"). Extrae la fecha de publicación del diario (ej. "Martes 24 de marzo de 2026") y devuélvela estrictamente como YYYY-MM-DD.
    6. Nombre_norma: Será estrictamente el valor "{pdf_basename}" pero SIN la extensión ".pdf" al final.
    7. Tipo_norma: Se extrae del nombre del archivo "{pdf_basename}". Corresponde al tipo de norma, el cual SUELE ubicarse al inicio del nombre del archivo, antes del código de la norma. Elimina cualquier espacio al inicio o al final y devuélvelo en MAYÚSCULAS (upper). Ejemplos:
       - "RESOLUCION MINISTERIAL N° 00334-2026-DE.pdf" -> "RESOLUCION MINISTERIAL"
       - "Decretos de Alcaldía N° 02-2026-MDS.pdf" -> "DECRETOS DE ALCALDÍA"
       - "RESOLUCION N° 046-2026_CDB-INDECOPI.pdf" -> "RESOLUCION"
    8. Codigo_norma: Se extrae del nombre del archivo "{pdf_basename}". Corresponde a la parte numérica y las siglas del nombre de la norma, la cual SUELE ubicarse después de "N°" (pero no siempre; si no aparece "N°", identifícala igualmente dentro del nombre del archivo). Excluye la extensión .pdf, elimina cualquier espacio al inicio o al final y devuélvela en MAYÚSCULAS (upper). Ejemplos:
       - "RESOLUCION MINISTERIAL N° 00334-2026-DE.pdf" -> "00334-2026-DE"
       - "Decretos de Alcaldía N° 02-2026-MDS.pdf" -> "02-2026-MDS"
       - "RESOLUCION N° 046-2026_CDB-INDECOPI.pdf" -> "046-2026_CDB-INDECOPI"

    SI NO ENCUENTRAS EL TITULO DE LA NORMA DENTRO DEL PDF:
    Retorna el JSON pero rellena Entidad, Glosa, Fecha_publicacion y Contenido con el valor "ERROR: Norma no encontrada".
    """

    # ADK automatically configures GENAI credentials (GOOGLE_API_KEY) in env
    client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
    intentos_maximos = 3
    for intento in range(intentos_maximos):
        safe_pdf_path = None
        uploaded_file = None
        try:
            # Para prevenir errores de UnicodeDecodeError (ASCII) en el SDK al leer "í" o "°",
            # creamos una copia temporal segura sin caracteres especiales en la ruta.
            temp_dir = tempfile.gettempdir()
            safe_pdf_path = os.path.join(temp_dir, f"norma_segura_{uuid.uuid4().hex}.pdf")
            shutil.copy2(pdf_path, safe_pdf_path)

            uploaded_file = client.files.upload(
                file=safe_pdf_path,
                config={'display_name': 'document.pdf', 'mime_type': 'application/pdf'}
            )

            # Generar contenido estructurado
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[uploaded_file, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=NormExtractionOutput,
                ),
            )

            # Obtenemos JSON asegurado por Pydantic Schema.
            # Usar response.parsed.model_dump() previene el warning de parts no-texto (function_call).
            if response.parsed:
                json_output = response.parsed.model_dump()
            elif response.text:
                json_output = json.loads(response.text)
            else:
                # Ni parsed ni text: respuesta vacía. Suele pasar por SAFETY,
                # RECITATION (común con textos legales), MAX_TOKENS o function_call edge case.
                finish_reason = "UNKNOWN"
                try:
                    if response.candidates:
                        finish_reason = str(getattr(response.candidates[0], "finish_reason", "UNKNOWN"))
                except Exception:
                    pass
                raise ValueError(
                    f"Respuesta de Gemini sin contenido (finish_reason={finish_reason})"
                )

            # Forzar data local
            for norm in json_output.get("norms", []):
                if "source_document" in norm:
                    norm["source_document"]["pdf_path"] = pdf_path
                    norm["source_document"]["norm_reference_name"] = norm_ref_name

            return json_output

        except Exception as e:
            # Si el error es por límite de tokens gratuitos (Resource Exhausted), esperamos
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                if intento < intentos_maximos - 1:
                    time.sleep(30) # Pausa de 30 segundos
                    continue

            # Captura cualquier otro error de subida o si se acabaron los reintentos
            return {
                "metadata": {
                    "source": "El Peruano",
                    "processing_type": "norm_extraction",
                    "language": "es-PE"
                },
                "norms": [
                    {
                        "Nombre_norma": pdf_basename,
                        "Tipo_norma": "ERROR",
                        "Codigo_norma": "ERROR",
                        "Entidad": f"ERROR: {str(e)}",
                        "Glosa": "ERROR",
                        "Fecha_publicacion": "ERROR",
                        "Contenido": "ERROR",
                        "source_document": {
                            "pdf_path": pdf_path,
                            "norm_reference_name": norm_ref_name
                        }
                    }
                ]
            }
        finally:
            # Limpieza garantizada: temp local + archivo remoto en Gemini Files API
            if safe_pdf_path and os.path.exists(safe_pdf_path):
                try:
                    os.remove(safe_pdf_path)
                except OSError:
                    pass
            if uploaded_file is not None:
                try:
                    client.files.delete(name=uploaded_file.name)
                except Exception:
                    pass

    # Por seguridad en el tipado de retorno
    return {}
