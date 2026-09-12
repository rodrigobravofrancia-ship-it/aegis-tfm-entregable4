"""Sub-agente: persiste las normas enriquecidas en SQLite y crea planes de
accion para las clasificadas como Posible Impacto (PASO final, alimenta el
tablero de seguimiento de Entregable 4)."""
import os
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai.types import Content, Part

from .tools.sqlite_writer import write_norms_to_sqlite


class SQLiteWriterAgent(BaseAgent):
    """PASO 7: guarda state['norms'] en tablero_seguimiento/aegis.db."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        if state.get("pipeline_aborted"):
            return

        norms = state.get("norms", [])

        print("\n" + "=" * 60)
        print("PASO 7: PERSISTENCIA EN SQLITE (tablero de seguimiento)")
        print("=" * 60)

        project_root = os.path.dirname(
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
        )
        db_path = state.get("db_path") or os.path.join(
            project_root, "tablero_seguimiento", "aegis.db"
        )

        try:
            summary = write_norms_to_sqlite(norms, db_path)
        except Exception as e:
            err_msg = f"[SQLiteWriter][ERROR] {e}"
            print(err_msg)
            yield Event(
                author=self.name,
                content=Content(parts=[Part(text=err_msg)]),
            )
            return

        msg = (
            f"[SQLiteWriter] {summary['normas_guardadas']} normas guardadas en "
            f"{db_path} ({summary['planes_creados']} planes de accion nuevos)."
        )
        print(msg)

        yield Event(
            author=self.name,
            content=Content(parts=[Part(text=msg)]),
            actions=EventActions(state_delta={"db_path": db_path}),
        )
