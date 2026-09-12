"""Sub-agentes secuenciales del pipeline AEGIS.

Cada sub-agente es un paquete autocontenido con su `agent.py` y su carpeta
`tools/`, siguiendo la convención del framework ADK.
"""

from .scraper import ScraperAgent
from .data_loader import DataLoaderAgent
from .extraction import ExtractionAgent
from .analysis import AnalysisAgent
from .gravity import GravityAgent
from .area import AreaAgent
from .excel_report import ExcelReportAgent
from .sqlite_writer import SQLiteWriterAgent

__all__ = [
    "ScraperAgent",
    "DataLoaderAgent",
    "ExtractionAgent",
    "AnalysisAgent",
    "GravityAgent",
    "AreaAgent",
    "ExcelReportAgent",
    "SQLiteWriterAgent",
]
