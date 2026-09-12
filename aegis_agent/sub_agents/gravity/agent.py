"""Sub-agente: clasificación de gravedad por norma (Gemini, escala SBS)."""
import os
import json
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai.types import Content, Part

from .tools.norm_gravity import classify_single_norm_gravity


class GravityAgent(BaseAgent):
    """PASO 4: Para cada norma en state['norms'] aplica classify_single_norm_gravity
    y agrega los campos 'gravedad' y 'justificacion_gravedad'."""

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
        print("PASO 4: CLASIFICACION DE GRAVEDAD")
        print("=" * 60)
        print(f"--- Iniciando clasificación de gravedad de {total} normas ---")

        for i, norm in enumerate(norms, 1):
            nombre = norm.get("Nombre_norma", "Sin nombre")
            print(f"[{i}/{total}] Clasificando gravedad: {nombre} ...")

            if norm.get("Contenido") == "ERROR" or "ERROR" in norm.get("resumen_norma", ""):
                print("  --> [SKIP] Norma con error en pasos previos.")
                norm["gravedad"] = "ERROR"
                norm["justificacion_gravedad"] = "ERROR: Norma no procesada correctamente en pasos previos"
                continue

            result = classify_single_norm_gravity(norm)
            norm["gravedad"] = result.get("gravedad", "ERROR: Sin clasificacion")
            norm["justificacion_gravedad"] = result.get("justificacion_gravedad", "ERROR: Sin justificacion")
            print(f"  --> [OK] gravedad: {norm['gravedad']}")

        print("--- Clasificación de gravedad finalizada ---\n")

        if staging_dir:
            out_path = os.path.join(staging_dir, "resultado_gravedad.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump({"norms": norms}, f, ensure_ascii=False, indent=4)
            print(f"[Gravedad] JSON intermedio: {out_path}")

        msg = f"[Gravedad] {total} normas clasificadas."
        yield Event(
            author=self.name,
            content=Content(parts=[Part(text=msg)]),
            actions=EventActions(state_delta={"norms": norms}),
        )
