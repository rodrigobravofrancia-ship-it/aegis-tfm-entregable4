"""Entrada por consola para ejecutar el agente AEGIS (ADK SequentialAgent)."""
import os
import asyncio
from dotenv import load_dotenv

# 1. Cargamos las credenciales (GOOGLE_API_KEY) desde aegis_agent/.env
current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, "aegis_agent", ".env")
load_dotenv(env_path)

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

from aegis_agent import root_agent


APP_NAME = "aegis_app"
USER_ID = "console_user"


async def run_pipeline(zip_path: str) -> str | None:
    """Ejecuta el SequentialAgent AEGIS sobre un ZIP y retorna la ruta del Excel."""
    session_service = InMemorySessionService()

    initial_state = {
        "zip_path": os.path.abspath(zip_path),
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

    trigger = Content(parts=[Part(text=f"Procesar ZIP: {zip_path}")])

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
    print("  INICIANDO AEGIS EN CONSOLA (ADK)")
    print("=======================================")

    zip_de_prueba = "data/28.03.zip"

    if not os.path.exists(zip_de_prueba):
        print(f"\n[!] Error: No se encontró el archivo de prueba: {zip_de_prueba}")
        print("Edita 'main_consola.py' y coloca la ruta correcta al .zip")
    else:
        print(f"-> Archivo detectado: {zip_de_prueba}\n")
        resultado = asyncio.run(run_pipeline(zip_de_prueba))

        if resultado:
            print(f"\nEXITO. Reporte Excel: {resultado}")
        else:
            print("\nHubo un error procesando las normas.")
