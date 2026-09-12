"""Sub-agente: generación del reporte Excel final."""
import os
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai.types import Blob, Content, Part

from .tools.excel_report import generate_excel_report


XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class ExcelReportAgent(BaseAgent):
    """PASO 6: Toma state['norms'] enriquecida y genera el archivo Excel final.
    Publica la ruta resultante en state['reporte_path']."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        if state.get("pipeline_aborted"):
            err = state.get("pipeline_error", "Pipeline abortado en pasos previos.")
            yield Event(
                author=self.name,
                content=Content(parts=[Part(text=f"Pipeline no completado: {err}")]),
            )
            return

        norms = state.get("norms", [])
        zip_name = state.get("zip_name", "reporte")
        output_dir = state.get("output_dir")

        print("\n" + "=" * 60)
        print("PASO 6: GENERACION DE REPORTE EXCEL")
        print("=" * 60)

        try:
            out_path = generate_excel_report(norms, zip_name, output_dir)
        except Exception as e:
            err_msg = f"[Excel][ERROR] {e}"
            print(err_msg)
            yield Event(
                author=self.name,
                content=Content(parts=[Part(text=err_msg)]),
                actions=EventActions(
                    state_delta={"pipeline_aborted": True, "pipeline_error": str(e)}
                ),
            )
            return

        msg = f"Pipeline AEGIS completado. Reporte Excel generado en: {out_path}"
        print(msg)

        # Adjuntar el archivo a la respuesta para que la UI ofrezca descarga.
        # El archivo en disco (out_path) se mantiene como respaldo histórico.
        parts = [Part(text=msg)]
        try:
            with open(out_path, "rb") as f:
                excel_bytes = f.read()
            parts.append(
                Part(
                    inline_data=Blob(
                        mime_type=XLSX_MIME,
                        data=excel_bytes,
                        display_name=os.path.basename(out_path),
                    )
                )
            )
        except Exception as e:
            print(f"[Excel][WARN] No se pudo adjuntar el archivo a la respuesta del chat: {e}")

        yield Event(
            author=self.name,
            content=Content(parts=parts),
            actions=EventActions(state_delta={"reporte_path": out_path}),
        )
