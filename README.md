# AEGIS — Prototipo (Entregable 4)

Clasificación automática de normativa legal aplicable al sector seguros
(Perú), como agente secuencial en Google ADK. Este README documenta el
prototipo construido para el Entregable 4 (TFM, Máster en Análisis y
Visualización de Datos Masivos, UNIR): scraping en vivo de El Peruano +
clasificación + tablero de seguimiento de planes de acción.

## Arquitectura del pipeline

`aegis_agent/agent.py` define `root_agent`, un `SequentialAgent` de ADK donde
cada paso comparte estado vía `session.state`:

```
fecha_desde/fecha_hasta  ─┐
                          ├─▶ [ScraperAgent]  ──▶ zip_path
zip_path (ZIP manual)    ─┘        (passthrough si zip_path ya viene dado)
                                        │
                                        ▼
                                [DataLoaderAgent]  ──▶ documents
                                        │
                                        ▼
                                [ExtractionAgent]  ──▶ norms (extraídas con Gemini)
                                        │
                                        ▼
                                [AnalysisAgent]    ──▶ + resumen, tipo_alerta
                                        │
                                        ▼
                                [GravityAgent]     ──▶ + gravedad
                                        │
                                        ▼
                                [AreaAgent]        ──▶ + area_sugerida
                                        │
                                        ▼
                                [ExcelReportAgent] ──▶ reporte_path (.xlsx)
                                        │
                                        ▼
                                [SQLiteWriterAgent] ──▶ db_path (normas + planes_accion)
```

Dos modos de entrada, mismo pipeline:

- **Manual** (`main_consola.py`): usa un ZIP de PDFs ya descargado a mano,
  igual que en entregas anteriores. `ScraperAgent` detecta `zip_path` en el
  estado y se comporta como passthrough.
- **Scraping** (`run_scraping.py`): dado un rango de fechas, `ScraperAgent`
  descarga las normas publicadas en `diariooficial.elperuano.pe` para ese
  rango y arma un ZIP con la misma estructura que los manuales, antes de
  seguir con el resto del pipeline sin cambios.

## Scraping de El Peruano — notas técnicas

`diariooficial.elperuano.pe/Normas` es una SPA (el listado se arma vía un
formulario AJAX: inputs `#cddesde`/`#cdhasta`, botón `#btnBuscar`). Cada
norma listada trae un link "Descarga individual" hacia
`busquedas.elperuano.pe/dispositivo/NL/<id>/pdf` — que a su vez **no es un
PDF estático**: es otra SPA que genera un token firmado y hace un fetch
interno al binario real (`.../api/archivo/file/<token>/*/<id>.PDF`).

Por eso `aegis_agent/sub_agents/scraper/tools/elperuano_scraper.py` usa
Playwright (Chromium headless) tanto para leer el listado como para
descargar cada PDF: abre la página de "Descarga individual" e intercepta la
respuesta de red `application/pdf`, capturando sus bytes directamente
(`response.body()`), sin necesidad de replicar el token firmado.

## Scraping programado

`scheduler.py` dispara `run_scraping.py` una vez al día (hora configurable)
usando la librería `schedule` — sustituto local de Cloud Scheduler para este
prototipo (la arquitectura real en GCP quedó diseñada conceptualmente en
Entregable 3, §"Arquitectura del flujo de trabajo en GCP"). Alternativa sin
dejar un proceso corriendo: una tarea del Programador de Tareas de Windows
que ejecute `python run_scraping.py`.

## Modelo de datos y tablero de seguimiento

`SQLiteWriterAgent` persiste cada corrida en `tablero_seguimiento/aegis.db`:

- `normas`: una fila por norma clasificada (mismas 16 columnas que
  `excel_report`/`CONTEXT.md`).
- `planes_accion`: se crea automáticamente un plan `Pendiente` por cada
  norma con `tipo_alerta = 'Posible Impacto'` — el componente **prescriptivo**
  del proyecto (las 3 técnicas de Entregable 2 son el componente predictivo,
  el EDA de Entregable 2 el descriptivo).
- `historial_estado`: trazabilidad de cada cambio de estado de un plan.

`tablero_seguimiento/app.py` (Streamlit) lee/escribe esa base:

```
streamlit run tablero_seguimiento/app.py
```

- **Normas**: tabla filtrable + detalle por norma.
- **Planes de acción**: asignar responsable/fecha límite/estado a cada norma
  de "Posible Impacto", con historial de cambios.
- **Métricas**: distribución de la corrida actual + figuras ya generadas en
  `../EDA/figuras/` y `../MODELADO/figuras/` (Entregables 2-3).

## Ejecución

```bash
pip install -r requirements.txt
playwright install chromium

# Modo manual (ZIP ya descargado)
python main_consola.py

# Modo scraping (hoy, o un rango de fechas DD/MM/AAAA)
python run_scraping.py
python run_scraping.py 10/09/2026 12/09/2026

# Scraping programado
python scheduler.py 08:00

# Tablero de seguimiento
streamlit run tablero_seguimiento/app.py
```

Requiere `aegis_agent/.env` con `GOOGLE_API_KEY` (no versionado, ver
`.gitignore`).

## Estructura de carpetas (resumen)

```
aegis_agent/
  agent.py                  # SequentialAgent root_agent
  sub_agents/
    scraper/                # NUEVO: scraping El Peruano (o passthrough)
    data_loader/
    extraction/
    analysis/
    gravity/
    area/
    excel_report/
    sqlite_writer/          # NUEVO: persistencia + planes de accion
main_consola.py              # entrypoint modo manual
run_scraping.py               # NUEVO: entrypoint modo scraping
scheduler.py                  # NUEVO: scraping programado diario
tablero_seguimiento/
  app.py                      # NUEVO: tablero Streamlit
  aegis.db                    # generado al correr el pipeline (no versionado)
```
