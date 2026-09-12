"""Persistencia de las normas clasificadas en SQLite, con el modelo de datos
que soporta el tablero de seguimiento de planes de accion (Entregable 4)."""
import os
import sqlite3
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS normas (
    codigo_norma TEXT PRIMARY KEY,
    fecha_publicacion TEXT,
    entidad TEXT,
    tipo_norma TEXT,
    glosa TEXT,
    resumen_norma TEXT,
    articulos TEXT,
    tipo_alerta TEXT,
    justificacion_tipo_alerta TEXT,
    gravedad TEXT,
    justificacion_gravedad TEXT,
    area_sugerida TEXT,
    justificacion_area TEXT,
    principales_consideraciones_1 TEXT,
    principales_consideraciones_2 TEXT,
    principales_consideraciones_3 TEXT,
    fecha_procesamiento TEXT
);

CREATE TABLE IF NOT EXISTS planes_accion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_norma TEXT NOT NULL UNIQUE REFERENCES normas(codigo_norma),
    estado TEXT NOT NULL DEFAULT 'Pendiente',
    responsable TEXT,
    fecha_limite TEXT,
    comentarios TEXT,
    actualizado_en TEXT
);

CREATE TABLE IF NOT EXISTS historial_estado (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL REFERENCES planes_accion(id),
    estado_anterior TEXT,
    estado_nuevo TEXT,
    fecha TEXT,
    comentario TEXT
);
"""

# Mapeo campo de `norms` (state del pipeline) -> columna SQLite. Coincide con
# excel_report/tools/excel_report.py::COLUMNS y con las 16 columnas de CONTEXT.md.
COLUMNS = [
    ("Codigo_norma", "codigo_norma"),
    ("Fecha_publicacion", "fecha_publicacion"),
    ("Entidad", "entidad"),
    ("Tipo_norma", "tipo_norma"),
    ("Glosa", "glosa"),
    ("resumen_norma", "resumen_norma"),
    ("articulos", "articulos"),
    ("tipo_alerta", "tipo_alerta"),
    ("justificacion_tipo_alerta", "justificacion_tipo_alerta"),
    ("gravedad", "gravedad"),
    ("justificacion_gravedad", "justificacion_gravedad"),
    ("area_sugerida", "area_sugerida"),
    ("justificacion_area", "justificacion_area"),
    ("principales_consideraciones_1", "principales_consideraciones_1"),
    ("principales_consideraciones_2", "principales_consideraciones_2"),
    ("principales_consideraciones_3", "principales_consideraciones_3"),
]


def _connect(db_path: str) -> sqlite3.Connection:
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    return conn


def write_norms_to_sqlite(norms: list[dict], db_path: str) -> dict:
    """Hace upsert de `norms` en la tabla `normas` y crea un plan de accion
    'Pendiente' para cada norma nueva con tipo_alerta == 'Posible Impacto'.

    Retorna {"normas_guardadas": int, "planes_creados": int}.
    """
    conn = _connect(db_path)
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    normas_guardadas = 0
    planes_creados = 0

    columnas_sql = ", ".join([col for _, col in COLUMNS] + ["fecha_procesamiento"])
    placeholders = ", ".join(["?"] * (len(COLUMNS) + 1))
    actualizacion_sql = ", ".join(
        [f"{col}=excluded.{col}" for _, col in COLUMNS] + ["fecha_procesamiento=excluded.fecha_procesamiento"]
    )

    for norm in norms:
        codigo = str(norm.get("Codigo_norma") or "").strip()
        if not codigo or codigo == "ERROR":
            continue

        valores = [norm.get(json_key, "") for json_key, _ in COLUMNS] + [now]
        cur.execute(
            f"""INSERT INTO normas ({columnas_sql})
                VALUES ({placeholders})
                ON CONFLICT(codigo_norma) DO UPDATE SET {actualizacion_sql}""",
            valores,
        )
        normas_guardadas += 1

        if norm.get("tipo_alerta") == "Posible Impacto":
            cur.execute("SELECT id FROM planes_accion WHERE codigo_norma = ?", (codigo,))
            if cur.fetchone() is None:
                cur.execute(
                    """INSERT INTO planes_accion (codigo_norma, estado, actualizado_en)
                       VALUES (?, 'Pendiente', ?)""",
                    (codigo, now),
                )
                planes_creados += 1

    conn.commit()
    conn.close()
    return {"normas_guardadas": normas_guardadas, "planes_creados": planes_creados}
