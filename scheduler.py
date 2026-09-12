"""Programa la ejecucion diaria del scraping de El Peruano.

Sustituto local de Cloud Scheduler para el prototipo de Entregable 4: en vez
de desplegar el flujo en GCP (ver arquitectura conceptual de Entregable 3,
Fig. 3), este script deja el pipeline corriendo automaticamente todos los
dias mientras la maquina esta encendida.

Uso:
    python scheduler.py            # corre todos los dias a las 08:00
    python scheduler.py 20:30      # corre todos los dias a esa hora

Alternativa sin dejar un proceso corriendo: crear una tarea en el
Programador de Tareas de Windows que ejecute
    python run_scraping.py
a la hora deseada (Accion: iniciar programa `python`, argumentos
`run_scraping.py`, "Iniciar en" la carpeta de este proyecto).
"""
import sys
import subprocess
import time
from datetime import datetime

import schedule


def ejecutar_scraping_de_hoy() -> None:
    hoy = datetime.now().strftime("%d/%m/%Y")
    print(f"\n[Scheduler] Disparando scraping para {hoy} ...")
    subprocess.run([sys.executable, "run_scraping.py", hoy, hoy], check=False)


if __name__ == "__main__":
    hora = sys.argv[1] if len(sys.argv) > 1 else "08:00"
    schedule.every().day.at(hora).do(ejecutar_scraping_de_hoy)

    print(f"[Scheduler] Programado para correr todos los dias a las {hora}.")
    print("Ctrl+C para salir.\n")

    while True:
        schedule.run_pending()
        time.sleep(30)
