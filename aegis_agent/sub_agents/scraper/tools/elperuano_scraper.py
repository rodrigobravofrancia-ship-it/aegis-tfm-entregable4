"""Scraping de normas legales publicadas en diariooficial.elperuano.pe.

Confirmado por inspeccion directa (Playwright) de ambos sitios involucrados:

- `diariooficial.elperuano.pe/Normas` es una SPA que arma su listado via un
  formulario AJAX (inputs #cddesde/#cdhasta, boton #btnBuscar). Cada norma
  listada trae un link "Descarga individual" hacia
  `busquedas.elperuano.pe/dispositivo/NL/<id>/pdf`.
- Ese link NO es un PDF estatico: es otra SPA (busquedas.elperuano.pe) que al
  cargar genera un token firmado y hace un fetch interno al PDF real en
  `busquedas.elperuano.pe/api/archivo/file/<token>/*/<id>.PDF`. Un
  `requests.get` normal solo devuelve el shell HTML de esa SPA.

Por eso la descarga de cada PDF tambien se hace con el navegador: se abre la
pagina de "Descarga individual" y se intercepta la respuesta de red cuyo
Content-Type es application/pdf, capturando sus bytes directamente
(`response.body()`) sin depender de replicar el token firmado.
"""
import os
import re
import zipfile

from playwright.sync_api import sync_playwright

BASE_URL = "https://diariooficial.elperuano.pe/Normas"
_INVALID_FILENAME_CHARS = re.compile(r'[<>:"\\|?*]')


def _sanitize_filename(titulo: str) -> str:
    """Replica la convencion de nombres de los ZIPs manuales existentes:
    el titulo de la norma tal cual, con '/' reemplazado por '_' (data_loader
    hace el reemplazo inverso al leer el ZIP)."""
    titulo = re.sub(r"\s+", " ", titulo).strip()
    titulo = titulo.replace("/", "_")
    titulo = _INVALID_FILENAME_CHARS.sub("", titulo)
    return titulo


def _fetch_normas_index(page) -> list[dict]:
    """Lee el listado ya renderizado en `page` y devuelve
    [{entidad, titulo, pdf_view_url}, ...] para cada norma encontrada."""
    normas = []
    articles = page.locator("article.edicionesoficiales_articulos").all()
    for art in articles:
        try:
            entidad = art.locator("h4").inner_text().strip()
            titulo = art.locator("h5 a").first.inner_text().strip()
            pdf_view_url = art.locator("a:has-text('Descarga individual')").first.get_attribute("href")
        except Exception:
            continue
        if not pdf_view_url or not titulo:
            continue
        normas.append({"entidad": entidad, "titulo": titulo, "pdf_view_url": pdf_view_url})
    return normas


def _descargar_pdf_bytes(context, pdf_view_url: str) -> bytes | None:
    """Abre `pdf_view_url` (la pagina 'Descarga individual') en una pestaña
    nueva y captura los bytes de la respuesta application/pdf que esa pagina
    dispara internamente."""
    page = context.new_page()
    capturado: dict[str, bytes] = {}

    def _on_response(response):
        if "data" in capturado:
            return
        content_type = response.headers.get("content-type", "")
        if response.status == 200 and "pdf" in content_type.lower():
            try:
                capturado["data"] = response.body()
            except Exception:
                pass

    page.on("response", _on_response)
    try:
        page.goto(pdf_view_url, wait_until="networkidle", timeout=30000)
    except Exception:
        pass
    page.wait_for_timeout(500)
    page.close()
    return capturado.get("data")


def run_scraper(fecha_desde: str, fecha_hasta: str, output_dir: str) -> dict:
    """Descarga las normas publicadas entre fecha_desde y fecha_hasta
    (formato DD/MM/AAAA) y las empaqueta en un ZIP con la misma estructura de
    carpeta que los ZIPs manuales ya usados por el pipeline (una carpeta con
    el rango como nombre, un PDF por norma dentro).

    Retorna {"zip_path": ..., "count": <int>} para que ScraperAgent deje
    'zip_path' listo y DataLoaderAgent continue el pipeline sin cambios.
    """
    etiqueta = f"{fecha_desde.replace('/', '.')}_{fecha_hasta.replace('/', '.')}"
    extract_dir = os.path.join(output_dir, etiqueta)
    os.makedirs(extract_dir, exist_ok=True)

    pdf_filenames = []
    fallos = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto(BASE_URL, wait_until="networkidle", timeout=60000)

        page.fill("#cddesde", fecha_desde)
        page.fill("#cdhasta", fecha_hasta)
        page.click("#btnBuscar")
        page.wait_for_load_state("networkidle", timeout=60000)
        page.wait_for_timeout(1500)

        normas = _fetch_normas_index(page)
        page.close()

        if not normas:
            browser.close()
            raise RuntimeError(
                f"No se encontraron normas publicadas entre {fecha_desde} y {fecha_hasta}."
            )

        for norma in normas:
            filename = _sanitize_filename(norma["titulo"]) + ".pdf"
            pdf_path = os.path.join(extract_dir, filename)
            if os.path.exists(pdf_path):
                pdf_filenames.append(filename)
                continue

            pdf_bytes = _descargar_pdf_bytes(context, norma["pdf_view_url"])
            if not pdf_bytes:
                fallos.append(norma["titulo"])
                continue

            with open(pdf_path, "wb") as f:
                f.write(pdf_bytes)
            pdf_filenames.append(filename)

        browser.close()

    if not pdf_filenames:
        raise RuntimeError(
            f"Se encontraron {len(normas)} normas pero ninguna pudo descargarse "
            f"(revisar cambios en el sitio de El Peruano)."
        )
    if fallos:
        print(f"[Scraper][WARN] {len(fallos)} normas no se pudieron descargar: {fallos[:5]}...")

    zip_path = os.path.join(output_dir, f"{etiqueta}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename in pdf_filenames:
            zf.write(os.path.join(extract_dir, filename), arcname=os.path.join(etiqueta, filename))

    return {"zip_path": zip_path, "count": len(pdf_filenames)}
