"""Sub-agente: clasificación de área responsable por norma (Gemini + Base_Areas.xlsx)."""
import os
import json
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai.types import Content, Part

from .tools.norm_area_classifier import classify_single_norm_area, load_areas_from_excel


class AreaAgent(BaseAgent):
    """PASO 5: Carga la base de áreas desde state['areas_excel_path'] y clasifica
    el área responsable de cada norma agregando 'area_sugerida' al estado."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        if state.get("pipeline_aborted"):
            return

        norms = state.get("norms", [])
        staging_dir = state.get("staging_dir")
        areas_excel_path = state.get("areas_excel_path")
        total = len(norms)

        if not areas_excel_path or not os.path.exists(areas_excel_path):
            msg = f"[Areas][ERROR] No se encontró Base_Areas.xlsx en: {areas_excel_path}"
            print(msg)
            yield Event(
                author=self.name,
                content=Content(parts=[Part(text=msg)]),
                actions=EventActions(
                    state_delta={"pipeline_aborted": True, "pipeline_error": msg}
                ),
            )
            return

        print("\n" + "=" * 60)
        print("PASO 5: CLASIFICACION DE AREAS")
        print("=" * 60)
        print(f"Cargando base de áreas desde: {areas_excel_path}")
        areas_context_str = load_areas_from_excel(areas_excel_path)

        print(f"--- Iniciando clasificación de áreas de {total} normas ---")
        for i, norm in enumerate(norms, 1):
            nombre = norm.get("Nombre_norma", "Sin nombre")
            print(f"[{i}/{total}] Clasificando área: {nombre} ...")

            if norm.get("Contenido") == "ERROR" or "ERROR" in norm.get("resumen_norma", ""):
                print("  --> [SKIP] Norma con error en pasos previos.")
                norm["area_sugerida"] = "ERROR"
                norm["justificacion_area"] = "ERROR"
                continue

            result = classify_single_norm_area(norm, areas_context_str)
            norm["area_sugerida"] = result.get("area_sugerida", "ND")
            norm["justificacion_area"] = result.get("justificacion_area", "ND")
            print(f"  --> [OK] área: {norm['area_sugerida']}")

        print("--- Clasificación de áreas finalizada ---\n")

        if staging_dir:
            out_path = os.path.join(staging_dir, "resultado_areas.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump({"norms": norms}, f, ensure_ascii=False, indent=4)
            print(f"[Areas] JSON intermedio: {out_path}")

        msg = f"[Areas] {total} normas con área asignada."
        yield Event(
            author=self.name,
            content=Content(parts=[Part(text=msg)]),
            actions=EventActions(state_delta={"norms": norms}),
        )
