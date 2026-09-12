"""Sub-agente: scraping de normas legales de El Peruano (PASO 0, opcional).

Si state['zip_path'] ya viene definido (modo manual, ver main_consola.py),
este agente actua como passthrough y no hace nada. Si en cambio el estado
trae 'fecha_desde'/'fecha_hasta' (modo scraping, ver run_scraping.py),
descarga las normas publicadas en ese rango desde diariooficial.elperuano.pe
y arma un ZIP con la misma estructura que los ZIPs manuales, dejando
state['zip_path'] listo para que DataLoaderAgent continue sin cambios.
"""
import os
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai.types import Content, Part

from .tools.elperuano_scraper import run_scraper


class ScraperAgent(BaseAgent):
    """PASO 0 (opcional): scraping en vivo de El Peruano, o passthrough si ya
    hay un ZIP manual en el estado."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state

        if state.get("zip_path"):
            print("[Scraper] 'zip_path' ya presente en el estado (modo manual) -> se omite el scraping.")
            return

        fecha_desde = state.get("fecha_desde")
        fecha_hasta = state.get("fecha_hasta")
        if not fecha_desde or not fecha_hasta:
            msg = (
                "[Scraper][ERROR] No hay 'zip_path' ni 'fecha_desde'/'fecha_hasta' "
                "en el estado. Indica un ZIP manual o un rango de fechas para el scraping."
            )
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
        print("PASO 0: SCRAPING DE NORMAS (El Peruano)")
        print("=" * 60)
        print(f"Rango de fechas: {fecha_desde} - {fecha_hasta}")

        project_root = os.path.dirname(
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
        )
        scraped_dir = state.get("scraped_dir") or os.path.join(project_root, "data_scraped")
        os.makedirs(scraped_dir, exist_ok=True)

        try:
            result = run_scraper(fecha_desde, fecha_hasta, scraped_dir)
        except Exception as e:
            err_msg = f"[Scraper][ERROR] {e}"
            print(err_msg)
            yield Event(
                author=self.name,
                content=Content(parts=[Part(text=err_msg)]),
                actions=EventActions(
                    state_delta={"pipeline_aborted": True, "pipeline_error": str(e)}
                ),
            )
            return

        areas_excel_path = state.get("areas_excel_path") or os.path.join(
            project_root, "data", "Base_Areas.xlsx"
        )

        msg = f"[Scraper] {result['count']} normas descargadas -> {result['zip_path']}"
        print(msg)

        yield Event(
            author=self.name,
            content=Content(parts=[Part(text=msg)]),
            actions=EventActions(
                state_delta={
                    "zip_path": result["zip_path"],
                    "areas_excel_path": areas_excel_path,
                }
            ),
        )
