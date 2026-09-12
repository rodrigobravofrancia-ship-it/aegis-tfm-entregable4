"""Entrada por consola para ejecutar el agente AEGIS en modo scraping
(sin ZIP manual): descarga las normas publicadas por El Peruano en un rango
de fechas y corre el mismo pipeline de clasificacion que main_consola.py.

Uso:
    python run_scraping.py                       # normas de hoy
    python run_scraping.py 10/09/2026 12/09/2026  # rango explicito (DD/MM/AAAA)
"""
import os
import sys
import asyncio
from datetime import datetime
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, "aegis_agent", ".env")
load_dotenv(env_path)

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

from aegis_agent import root_agent


APP_NAME = "aegis_app"
USER_ID = "scraper_user"


async def run_pipeline(fecha_desde: str, fecha_hasta: str) -> str | None:
    """Ejecuta el SequentialAgent AEGIS en modo scraping para el rango de
    fechas dado (DD/MM/AAAA) y retorna la ruta del Excel generado."""
    session_service = InMemorySessionService()

    initial_state = {
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
    }

    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        state=initial_state,
    )

    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    trigger = Content(parts=[Part(text=f"Procesar normas del {fecha_desde} al {fecha_hasta}")])

    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session.id,
        new_message=trigger,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    print(f"[{event.author}] {part.text}")

    final_session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session.id
    )
    return final_session.state.get("reporte_path")


if __name__ == "__main__":
    print("=======================================")
    print("  AEGIS - SCRAPING EL PERUANO (ADK)")
    print("=======================================")

    if len(sys.argv) == 3:
        fecha_desde, fecha_hasta = sys.argv[1], sys.argv[2]
    else:
        hoy = datetime.now().strftime("%d/%m/%Y")
        fecha_desde = fecha_hasta = hoy
        print(f"Sin argumentos: se usa la fecha de hoy ({hoy}).")
        print("Uso: python run_scraping.py DD/MM/AAAA DD/MM/AAAA\n")

    resultado = asyncio.run(run_pipeline(fecha_desde, fecha_hasta))

    if resultado:
        print(f"\nEXITO. Reporte Excel: {resultado}")
    else:
        print("\nHubo un error procesando las normas.")
