"""Sub-agente: análisis y enriquecimiento de cada norma (Gemini)."""
import os
import json
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai.types import Content, Part

from .tools.norm_analyzer import analyze_norm


class AnalysisAgent(BaseAgent):
    """PASO 3: Recorre state['norms'] y agrega los campos de resumen, articulos,
    consideraciones, tipo_alerta y justificacion_tipo_alerta usando analyze_norm."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        if state.get("pipeline_aborted"):
            return

        norms = state.get("norms", [])
        staging_dir = state.get("staging_dir")
        total = len(norms)

        print("\n" + "=" * 60)
        print("PASO 3: ANALISIS Y CLASIFICACION DE NORMAS")
        print("=" * 60)
        print(f"--- Iniciando análisis de {total} normas ---")

        for i, norm in enumerate(norms, 1):
            nombre = norm.get("Nombre_norma", "Sin nombre")
            print(f"[{i}/{total}] Analizando: {nombre} ...")

            if norm.get("Contenido") == "ERROR" or "ERROR" in norm.get("Entidad", ""):
                print("  --> [SKIP] Norma con error en extraccion.")
                norm["resumen_norma"] = "ERROR: Norma no extraida correctamente"
                norm["articulos"] = "ERROR"
                norm["principales_consideraciones_1"] = "ERROR"
                norm["principales_consideraciones_2"] = "ERROR"
                norm["principales_consideraciones_3"] = "ERROR"
                norm["tipo_alerta"] = "ERROR"
                norm["justificacion_tipo_alerta"] = "ERROR"
                continue

            analysis = analyze_norm(norm)
            norm["resumen_norma"] = analysis.get("resumen_norma", "")
            norm["articulos"] = analysis.get("articulos", "")
            norm["principales_consideraciones_1"] = analysis.get("principales_consideraciones_1", "")
            norm["principales_consideraciones_2"] = analysis.get("principales_consideraciones_2", "")
            norm["principales_consideraciones_3"] = analysis.get("principales_consideraciones_3", "")
            norm["tipo_alerta"] = analysis.get("tipo_alerta", "")
            norm["justificacion_tipo_alerta"] = analysis.get("justificacion_tipo_alerta", "")
            print(f"  --> [OK] tipo_alerta: {norm['tipo_alerta']}")

        print("--- Análisis finalizado ---\n")

        if staging_dir:
            out_path = os.path.join(staging_dir, "resultado_analisis.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump({"norms": norms}, f, ensure_ascii=False, indent=4)
            print(f"[Analisis] JSON intermedio: {out_path}")

        msg = f"[Analisis] {total} normas analizadas."
        yield Event(
            author=self.name,
            content=Content(parts=[Part(text=msg)]),
            actions=EventActions(state_delta={"norms": norms}),
        )
