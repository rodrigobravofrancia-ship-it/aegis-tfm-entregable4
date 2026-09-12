"""Paquete aegis_agent.

Expone el `root_agent` (SequentialAgent de ADK) que orquesta el pipeline
de extracción, análisis, gravedad y áreas de normas legales.
"""
from .agent import root_agent

__all__ = ["root_agent"]
