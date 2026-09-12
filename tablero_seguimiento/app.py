"""Tablero de seguimiento AEGIS (Entregable 4 - prototipo).

Interfaz Streamlit que lee/escribe sobre la misma base SQLite que alimenta el
paso final del pipeline ADK (SQLiteWriterAgent): permite revisar las normas
clasificadas y dar seguimiento a los planes de accion de las normas con
tipo_alerta == "Posible Impacto".

Uso:
    streamlit run tablero_seguimiento/app.py
"""
import os
import sqlite3
from datetime import datetime, timezone

import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

# Paleta categorica fija del proyecto (misma que EDA/estilo_graficos.py y
# MODELADO/estilo_modelado.py): azul = Informativa, naranja = Posible Impacto.
AZUL = "#2a78d6"
NARANJA = "#eb6834"
COLOR_TIPO_ALERTA = {"Informativa": AZUL, "Posible Impacto": NARANJA}
COLOR_ESTADO_PLAN = {"Pendiente": "#eb6834", "En progreso": "#e0b400", "Completado": "#1baf7a"}

AEGIS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEMINARIO_DIR = os.path.dirname(AEGIS_DIR)
DB_PATH = os.path.join(AEGIS_DIR, "tablero_seguimiento", "aegis.db")
FIGURAS_EDA = os.path.join(SEMINARIO_DIR, "EDA", "figuras")
FIGURAS_MODELADO = os.path.join(SEMINARIO_DIR, "MODELADO", "figuras")

ESTADOS_PLAN = ["Pendiente", "En progreso", "Completado"]


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _cargar_normas() -> pd.DataFrame:
    with _connect() as conn:
        return pd.read_sql_query("SELECT * FROM normas ORDER BY fecha_publicacion DESC", conn)


def _cargar_planes() -> pd.DataFrame:
    with _connect() as conn:
        return pd.read_sql_query(
            """
            SELECT p.*, n.glosa, n.entidad, n.tipo_norma, n.gravedad,
                   n.resumen_norma, n.justificacion_tipo_alerta
            FROM planes_accion p
            JOIN normas n ON n.codigo_norma = p.codigo_norma
            ORDER BY p.actualizado_en DESC
            """,
            conn,
        )


def _cargar_historial(plan_id: int) -> pd.DataFrame:
    with _connect() as conn:
        return pd.read_sql_query(
            "SELECT * FROM historial_estado WHERE plan_id = ? ORDER BY fecha DESC",
            conn,
            params=(plan_id,),
        )


def _guardar_plan(plan_id: int, codigo_norma: str, estado_anterior: str, estado_nuevo: str,
                   responsable: str, fecha_limite: str, comentarios: str) -> None:
    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute(
            """UPDATE planes_accion
               SET estado = ?, responsable = ?, fecha_limite = ?, comentarios = ?, actualizado_en = ?
               WHERE id = ?""",
            (estado_nuevo, responsable, fecha_limite, comentarios, ahora, plan_id),
        )
        if estado_anterior != estado_nuevo:
            conn.execute(
                """INSERT INTO historial_estado (plan_id, estado_anterior, estado_nuevo, fecha, comentario)
                   VALUES (?, ?, ?, ?, ?)""",
                (plan_id, estado_anterior, estado_nuevo, ahora, comentarios),
            )
        conn.commit()


st.set_page_config(page_title="AEGIS - Tablero de seguimiento", layout="wide")
st.title("AEGIS · Tablero de seguimiento normativo")

if not os.path.exists(DB_PATH):
    st.info(
        "Aun no hay datos. Corre primero el pipeline (`python main_consola.py` o "
        "`python run_scraping.py`) para generar `tablero_seguimiento/aegis.db`."
    )
    st.stop()

tab_normas, tab_planes, tab_metricas = st.tabs(["Normas", "Planes de accion", "Metricas"])

# ------------------------------------------------------------------ Normas --
with tab_normas:
    normas = _cargar_normas()
    if normas.empty:
        st.info("No hay normas cargadas todavia.")
    else:
        col1, col2, col3, col4 = st.columns(4)
        f_alerta = col1.multiselect("Tipo de alerta", sorted(normas["tipo_alerta"].dropna().unique()))
        f_gravedad = col2.multiselect("Gravedad", sorted(normas["gravedad"].dropna().unique()))
        f_entidad = col3.multiselect("Entidad", sorted(normas["entidad"].dropna().unique()))
        f_area = col4.multiselect("Area sugerida", sorted(normas["area_sugerida"].dropna().unique()))

        vista = normas.copy()
        if f_alerta:
            vista = vista[vista["tipo_alerta"].isin(f_alerta)]
        if f_gravedad:
            vista = vista[vista["gravedad"].isin(f_gravedad)]
        if f_entidad:
            vista = vista[vista["entidad"].isin(f_entidad)]
        if f_area:
            vista = vista[vista["area_sugerida"].isin(f_area)]

        st.caption(f"{len(vista)} de {len(normas)} normas")
        st.dataframe(
            vista[["codigo_norma", "fecha_publicacion", "entidad", "tipo_norma", "glosa",
                   "tipo_alerta", "gravedad", "area_sugerida"]],
            use_container_width=True,
            hide_index=True,
        )

        seleccion = st.selectbox("Ver detalle de una norma", ["(ninguna)"] + list(vista["codigo_norma"]))
        if seleccion != "(ninguna)":
            fila = vista[vista["codigo_norma"] == seleccion].iloc[0]
            st.markdown(f"### {fila['glosa']}")
            st.write(f"**Entidad:** {fila['entidad']} · **Tipo:** {fila['tipo_norma']} · "
                     f"**Fecha:** {fila['fecha_publicacion']}")
            st.write("**Resumen:**", fila["resumen_norma"])
            st.write(f"**Tipo de alerta:** {fila['tipo_alerta']} — {fila['justificacion_tipo_alerta']}")
            st.write(f"**Gravedad:** {fila['gravedad']} — {fila['justificacion_gravedad']}")
            st.write(f"**Area sugerida:** {fila['area_sugerida']} — {fila['justificacion_area']}")
            for i in (1, 2, 3):
                consideracion = fila.get(f"principales_consideraciones_{i}")
                if consideracion:
                    st.write(f"- {consideracion}")

# ------------------------------------------------------------- Planes de accion --
with tab_planes:
    planes = _cargar_planes()
    if planes.empty:
        st.info("No hay normas de 'Posible Impacto' con plan de accion todavia.")
    else:
        resumen_estado = planes["estado"].value_counts()
        cols = st.columns(len(ESTADOS_PLAN))
        for col, estado in zip(cols, ESTADOS_PLAN):
            col.metric(estado, int(resumen_estado.get(estado, 0)))

        for _, plan in planes.iterrows():
            titulo = f"{plan['codigo_norma']} · {plan['glosa'][:80]} — [{plan['estado']}]"
            with st.expander(titulo):
                st.write(f"**Entidad:** {plan['entidad']} · **Gravedad:** {plan['gravedad']}")
                st.write("**Justificacion de la alerta:**", plan["justificacion_tipo_alerta"])

                with st.form(key=f"form_plan_{plan['id']}"):
                    c1, c2 = st.columns(2)
                    estado_nuevo = c1.selectbox(
                        "Estado", ESTADOS_PLAN,
                        index=ESTADOS_PLAN.index(plan["estado"]) if plan["estado"] in ESTADOS_PLAN else 0,
                        key=f"estado_{plan['id']}",
                    )
                    responsable = c2.text_input("Responsable", value=plan["responsable"] or "", key=f"resp_{plan['id']}")
                    fecha_limite = st.date_input(
                        "Fecha limite",
                        value=pd.to_datetime(plan["fecha_limite"]).date() if plan["fecha_limite"] else None,
                        key=f"fecha_{plan['id']}",
                    )
                    comentarios = st.text_area("Comentarios", value=plan["comentarios"] or "", key=f"com_{plan['id']}")
                    if st.form_submit_button("Guardar"):
                        _guardar_plan(
                            plan_id=int(plan["id"]),
                            codigo_norma=plan["codigo_norma"],
                            estado_anterior=plan["estado"],
                            estado_nuevo=estado_nuevo,
                            responsable=responsable,
                            fecha_limite=str(fecha_limite) if fecha_limite else "",
                            comentarios=comentarios,
                        )
                        st.success("Plan de accion actualizado.")
                        st.rerun()

                historial = _cargar_historial(int(plan["id"]))
                if not historial.empty:
                    st.caption("Historial de cambios de estado")
                    st.dataframe(
                        historial[["estado_anterior", "estado_nuevo", "fecha", "comentario"]],
                        hide_index=True, use_container_width=True,
                    )

# ------------------------------------------------------------------ Metricas --
with tab_metricas:
    normas = _cargar_normas()
    if normas.empty:
        st.info("No hay normas cargadas todavia.")
    else:
        st.subheader("Corrida actual")
        c1, c2 = st.columns(2)

        with c1:
            conteo = normas["tipo_alerta"].value_counts().reindex(
                ["Informativa", "Posible Impacto"]
            ).fillna(0)
            fig, ax = plt.subplots(figsize=(4, 3))
            ax.bar(conteo.index, conteo.values, color=[COLOR_TIPO_ALERTA.get(t, "#898781") for t in conteo.index])
            ax.set_title("Distribucion por tipo de alerta")
            ax.set_ylabel("N° de normas")
            ax.spines[["top", "right"]].set_visible(False)
            st.pyplot(fig, use_container_width=True)

        with c2:
            planes = _cargar_planes()
            if not planes.empty:
                conteo_estado = planes["estado"].value_counts().reindex(ESTADOS_PLAN).fillna(0)
                fig2, ax2 = plt.subplots(figsize=(4, 3))
                ax2.bar(conteo_estado.index, conteo_estado.values,
                        color=[COLOR_ESTADO_PLAN[e] for e in conteo_estado.index])
                ax2.set_title("Planes de accion por estado")
                ax2.set_ylabel("N° de planes")
                ax2.spines[["top", "right"]].set_visible(False)
                st.pyplot(fig2, use_container_width=True)
            else:
                st.caption("Sin planes de accion todavia.")

        st.subheader("Contexto: EDA y comparacion de tecnicas (Entregables 2-3)")
        st.caption("Figuras generadas previamente en el EDA y en la fase de modelado.")
        cfig1, cfig2 = st.columns(2)
        ruta_dist = os.path.join(FIGURAS_EDA, "01_distribucion_tipo_alerta.png")
        ruta_comp = os.path.join(FIGURAS_MODELADO, "09_comparacion_tecnicas.png")
        if os.path.exists(ruta_dist):
            cfig1.image(ruta_dist, caption="Distribucion tipo_alerta (historico 2024-2025)")
        if os.path.exists(ruta_comp):
            cfig2.image(ruta_comp, caption="Comparacion de las 3 tecnicas de clasificacion")
