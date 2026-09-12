"""Sub-agente: extracción paralela de normas desde los PDFs (Gemini)."""
import os
import json
import asyncio
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai.types import Content, Part

from .tools.norm_extractor import extract_norm_from_pdf


MAX_CONCURRENT_EXTRACTIONS = 5


class ExtractionAgent(BaseAgent):
    """PASO 2: Para cada documento en state['documents'], llama al extractor Gemini
    (extract_norm_from_pdf) en paralelo y acumula los registros en state['norms']."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        if state.get("pipeline_aborted"):
            return

        documents = state.get("documents", [])
        staging_dir = state.get("staging_dir")
        total_docs = len(documents)

        print("\n" + "=" * 60)
        print("PASO 2: EXTRACCION DE NORMAS")
        print("=" * 60)

        if total_docs == 0:
            msg = "[Extraccion][ERROR] No hay PDFs para procesar (state['documents'] vacío)."
            print(msg)
            yield Event(
                author=self.name,
                content=Content(parts=[Part(text=msg)]),
                actions=EventActions(
                    state_delta={"pipeline_aborted": True, "pipeline_error": msg}
                ),
            )
            return

        print(f"--- Iniciando extracción de {total_docs} documentos (concurrencia: {MAX_CONCURRENT_EXTRACTIONS}) ---")

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_EXTRACTIONS)

        async def _process_one(idx: int, doc: dict) -> tuple[int, dict, dict]:
            async with semaphore:
                partial = await asyncio.to_thread(
                    extract_norm_from_pdf,
                    doc["pdf_path"],
                    doc["norm_reference_name"],
                    doc["nombre_archivo_pdf"],
                )
                return idx, doc, partial

        tasks = [
            asyncio.create_task(_process_one(i, doc))
            for i, doc in enumerate(documents)
        ]

        results: list[dict | None] = [None] * total_docs
        completed = 0

        for finished in asyncio.as_completed(tasks):
            idx, doc, partial = await finished
            results[idx] = partial
            completed += 1
            basename = doc["nombre_archivo_pdf"]

            if "norms" in partial and len(partial["norms"]) > 0:
                entidad = partial["norms"][0].get("Entidad", "")
                if "ERROR" in entidad:
                    status_line = f"[{completed}/{total_docs}] [X] {basename}: {entidad[:60]}"
                else:
                    status_line = f"[{completed}/{total_docs}] [OK] {basename} ({entidad[:30]})"
            else:
                status_line = f"[{completed}/{total_docs}] [?] {basename}: sin normas extraídas"

            print(status_line)

            # Emitir progreso a la UI sin tocar state aún
            yield Event(
                author=self.name,
                content=Content(parts=[Part(text=status_line)]),
                actions=EventActions(),
            )

        # Consolidar manteniendo el orden original de documents
        norms: list[dict] = []
        for r in results:
            if r and "norms" in r:
                norms.extend(r["norms"])

        print("--- Extracción finalizada ---\n")

        # Persistencia local del JSON intermedio (compatibilidad con flujo previo)
        if staging_dir:
            os.makedirs(staging_dir, exist_ok=True)
            out_path = os.path.join(staging_dir, "resultado_normas.json")
            payload = {
                "metadata": {
                    "source": "El Peruano",
                    "processing_type": "norm_extraction",
                    "language": "es-PE",
                },
                "norms": norms,
            }
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=4)
            print(f"[Extraccion] JSON intermedio: {out_path}")

        msg = f"[Extraccion] {len(norms)} normas extraídas de {total_docs} documentos."
        yield Event(
            author=self.name,
            content=Content(parts=[Part(text=msg)]),
            actions=EventActions(state_delta={"norms": norms}),
        )
