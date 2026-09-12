"""Definición del agente raíz AEGIS como SequentialAgent (ADK).

Cada paso del pipeline original está envuelto en un sub-agente independiente
que comparte estado a través de session.state:

    fecha_desde/fecha_hasta -> [Scraper] -> zip_path (o passthrough si
              zip_path ya viene de un ZIP manual, ver main_consola.py)
              -> [DataLoader] -> documents
              -> [Extraction] -> norms (con metadata extraída)
              -> [Analysis]   -> norms enriquecidas (resumen, tipo_alerta, ...)
              -> [Gravity]    -> norms con gravedad
              -> [Area]       -> norms con area_sugerida
              -> [Excel]      -> reporte_path
              -> [SQLiteWriter] -> db_path (normas + planes_accion para el
                 tablero de seguimiento)

Las prompts y schemas Pydantic se conservan dentro de aegis_agent/tools/.
"""
from google.adk.agents import SequentialAgent

from .sub_agents import (
    ScraperAgent,
    DataLoaderAgent,
    ExtractionAgent,
    AnalysisAgent,
    GravityAgent,
    AreaAgent,
    ExcelReportAgent,
    SQLiteWriterAgent,
)


root_agent = SequentialAgent(
    name="AegisNormPipeline",
    description=(
        "Pipeline secuencial AEGIS: descarga (scraping) o recibe un ZIP de "
        "normas de El Peruano, las extrae con Gemini, las analiza, clasifica "
        "gravedad y área responsable, produce un reporte Excel corporativo y "
        "persiste los resultados y planes de acción en SQLite para el tablero "
        "de seguimiento."
    ),
    sub_agents=[
        ScraperAgent(name="ScraperAgent"),
        DataLoaderAgent(name="DataLoaderAgent"),
        ExtractionAgent(name="ExtractionAgent"),
        AnalysisAgent(name="AnalysisAgent"),
        GravityAgent(name="GravityAgent"),
        AreaAgent(name="AreaAgent"),
        ExcelReportAgent(name="ExcelReportAgent"),
        SQLiteWriterAgent(name="SQLiteWriterAgent"),
    ],
)
