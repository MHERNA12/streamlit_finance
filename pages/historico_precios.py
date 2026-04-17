import streamlit as st
import pandas as pd
import time
from database import run_query, execute_non_query, get_engine
from sqlalchemy import text

def mostrar_logo(nombre, width=70):
    """Muestra el logo de una entidad desde la carpeta iconos/."""
    import os
    ruta_base = f"iconos/{nombre}"
    for ext in [".png", ".jpg", ".jpeg", ".svg"]:
        if os.path.exists(ruta_base + ext):
            st.image(ruta_base + ext, width=width)
            return
    st.markdown("<div style='font-size:2rem;text-align:center'>🏦</div>", unsafe_allow_html=True)

st.set_page_config(page_title="Histórico de Precios", layout="wide")

st.title("💹 Registro de Precios")
st.caption("Actualización manual de precios de activos en cartera.")

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def fmt_eur(n):
    try:
        return f"{float(n):,.6f} €".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "—"

def fmt_eur2(n):
    try:
        return f"{float(n):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "—"

# ---------------------------------------------------------------------------
# CARGA DE DATOS DE REFERENCIA
# ---------------------------------------------------------------------------
@st.cache_data(ttl=60)
def cargar_activos_inversion():
    """Activos de tipo Inversión o Ahorro con posición abierta en v_estado_activos."""
    return run_query("""
        SELECT
            a.isin,
            a.denominacion,
            a.entidad_id,
            e.nombre AS entidad,
            v.unidades,
            v.coste_total
        FROM activos_descripcion a
        JOIN ref_entidad e ON a.entidad_id = e.id
        JOIN ref_tipo_producto tp ON a.tipo_producto_id = tp.id
        -- Solo activos con posición abierta en v_estado_activos
        JOIN v_estado_activos v ON v.activo = a.denominacion AND v.entidad = e.nombre
        WHERE tp.nombre IN ('Inversión', 'Ahorro')
        ORDER BY e.nombre, a.denominacion
    """)

df_activos = cargar_activos_inversion()

# ---------------------------------------------------------------------------
# TABS
# ---------------------------------------------------------------------------
tab_registrar, tab_historial, tab_editar = st.tabs(
    ["📝 Registrar Precios", "📜 Histórico", "✏️ Editar / Borrar"]
)


# ===========================================================================
# TAB 1 — REGISTRAR PRECIOS
# ===========================================================================
with tab_registrar:

    if df_activos.empty:
        st.info("ℹ️ No hay activos de inversión con posición abierta.")
        st.stop()

    st.markdown("Introduce el precio actual de cada activo. Pulsa **Guardar todos** cuando hayas terminado.")

    st.divider()

    # Fecha FUERA del form para detectar cambios y precargar precios
    fecha_registro = st.date_input(
        "📅 Fecha de los precios",
        value=pd.Timestamp.today(),
        format="DD/MM/YYYY",
        key="hp_fecha"
    )

    # Fechas con datos registrados (informativo bajo el date_input)
    df_fechas = run_query("SELECT DISTINCT fecha FROM historico_precios ORDER BY fecha DESC LIMIT 10")
    if not df_fechas.empty:
        fechas_str = "  |  ".join(pd.to_datetime(f).strftime("%d/%m/%Y") for f in df_fechas["fecha"])
        st.caption(f"📅 Fechas con precios registrados: **{fechas_str}**")

    # Cuando cambia la fecha, precargamos en session_state el precio de esa fecha
    # (o el último disponible si no hay datos para esa fecha)
    if st.session_state.get("hp_fecha_prev") != str(fecha_registro):
        st.session_state["hp_fecha_prev"] = str(fecha_registro)

        for _, row in df_activos.iterrows():
            k = f"precio_{row['isin']}_{row['entidad_id']}"

            # 1. Precio exacto para la fecha seleccionada
            df_precio_fecha = run_query("""
                SELECT precio FROM historico_precios
                WHERE isin = :isin AND entidad_id = :eid AND fecha = :fecha
                ORDER BY id DESC LIMIT 1
            """, {"isin": row["isin"], "eid": int(row["entidad_id"]), "fecha": fecha_registro})

            if not df_precio_fecha.empty:
                st.session_state[k] = float(df_precio_fecha.iloc[0]["precio"])
            else:
                # 2. Último precio disponible (cualquier fecha anterior)
                df_ultimo = run_query("""
                    SELECT precio, fecha FROM historico_precios
                    WHERE isin = :isin AND entidad_id = :eid
                    ORDER BY fecha DESC, id DESC LIMIT 1
                """, {"isin": row["isin"], "eid": int(row["entidad_id"])})

                st.session_state[k] = float(df_ultimo.iloc[0]["precio"]) if not df_ultimo.empty else 0.0

    st.divider()

    # Metadatos por activo para el preview y el guardado (sin depender del form)
    meta_activos = []
    for _, row in df_activos.iterrows():
        k = f"precio_{row['isin']}_{row['entidad_id']}"
        # Buscamos último precio y fecha para mostrar referencia
        df_ref = run_query("""
            SELECT precio, fecha FROM historico_precios
            WHERE isin = :isin AND entidad_id = :eid
            ORDER BY fecha DESC, id DESC LIMIT 1
        """, {"isin": row["isin"], "eid": int(row["entidad_id"])})
        ultimo_precio = float(df_ref.iloc[0]["precio"]) if not df_ref.empty else None
        ultima_fecha  = df_ref.iloc[0]["fecha"] if not df_ref.empty else None

        meta_activos.append({
            "isin":         row["isin"],
            "entidad_id":   int(row["entidad_id"]),
            "entidad":      row["entidad"],
            "denominacion": row["denominacion"],
            "unidades":     float(row["unidades"]),
            "coste_total":  float(row["coste_total"]),
            "ultimo_precio": ultimo_precio,
            "ultima_fecha":  ultima_fecha,
            "key_precio":   k,
            "key_obs":      f"obs_{row['isin']}_{row['entidad_id']}",
        })

    # Formulario — solo contiene widgets, no lógica de negocio
    with st.form("form_precios"):

        hdr = st.columns([3, 1.5, 1.5, 1.5, 3])
        hdr[0].markdown("**Activo**")
        hdr[1].markdown("**Unidades**")
        hdr[2].markdown("**Coste medio ud.**")
        hdr[3].markdown("**Precio actual**")
        hdr[4].markdown("**Observaciones**")

        entidad_actual = None
        for m in meta_activos:
            if m["entidad"] != entidad_actual:
                entidad_actual = m["entidad"]
                st.divider()
                logo_col, nombre_col = st.columns([0.5, 6])
                with logo_col:
                    mostrar_logo(entidad_actual, width=40)
                with nombre_col:
                    st.markdown(f"#### {entidad_actual}")

            coste_medio = m["coste_total"] / m["unidades"] if m["unidades"] > 0 else 0
            cols = st.columns([3, 1.5, 1.5, 1.5, 3])

            with cols[0]:
                st.markdown(f"**{m['denominacion']}**")
                st.caption(f"`{m['isin']}`")
                if m["ultima_fecha"] is not None:
                    st.caption(f"Último: {fmt_eur(m['ultimo_precio'])} ({pd.to_datetime(m['ultima_fecha']).strftime('%d/%m/%Y')})")

            cols[1].markdown(f"{m['unidades']:.4f}")
            cols[2].markdown(fmt_eur(coste_medio))

            cols[3].number_input(
                label=m["key_precio"],
                label_visibility="collapsed",
                min_value=0.0,
                step=0.01,
                format="%.6f",
                key=m["key_precio"]
            )

            cols[4].text_input(
                label=m["key_obs"],
                label_visibility="collapsed",
                placeholder="Opcional...",
                key=m["key_obs"]
            )

        st.divider()
        guardar_btn = st.form_submit_button("💾 Guardar todos los precios", type="primary", width='stretch')

    # --- Preview de valoración — siempre desde session_state ---
    st.subheader("📊 Vista previa de valoración")
    df_ultima_fecha = run_query("SELECT MAX(fecha) AS ultima_fecha FROM historico_precios")
    ultima_fecha_precio = df_ultima_fecha.iloc[0]["ultima_fecha"]
    if ultima_fecha_precio:
        st.caption(f"📅 Valoración calculada con precios de: **{pd.to_datetime(ultima_fecha_precio).strftime('%d/%m/%Y')}**")
    else:
        st.caption("📅 No hay precios registrados aún en el histórico.")
    filas_preview = []
    for m in meta_activos:
        precio_actual = float(st.session_state.get(m["key_precio"], 0.0))
        valor_actual  = precio_actual * m["unidades"]
        plusvalia     = valor_actual - m["coste_total"]
        pct           = (plusvalia / m["coste_total"] * 100) if m["coste_total"] > 0 else 0
        filas_preview.append({
            "Entidad":       m["entidad"],
            "Activo":        m["denominacion"],
            "Unidades":      m["unidades"],
            "Coste total":   m["coste_total"],
            "Precio actual": precio_actual,
            "Valor actual":  valor_actual,
            "Plusvalía €":   plusvalia,
            "Plusvalía %":   pct,
        })

    df_preview = pd.DataFrame(filas_preview)

    total_coste = df_preview["Coste total"].sum()
    total_valor = df_preview["Valor actual"].sum()
    total_plus  = total_valor - total_coste
    total_pct   = (total_plus / total_coste * 100) if total_coste > 0 else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("💰 Coste total invertido", fmt_eur2(total_coste))
    m2.metric("📈 Valor actual cartera",  fmt_eur2(total_valor))
    m3.metric("✨ Plusvalía latente", fmt_eur2(total_plus), delta=f"{total_pct:+.2f}%")
    m4.metric("📋 Activos en cartera", len(df_preview))

    st.divider()

    # --- Expanders por entidad ---
    for entidad_nombre in df_preview["Entidad"].unique():
        df_ent = df_preview[df_preview["Entidad"] == entidad_nombre].copy()

        tc_ent = df_ent["Coste total"].sum()
        tv_ent = df_ent["Valor actual"].sum()
        tp_ent = tv_ent - tc_ent
        pct_ent = (tp_ent / tc_ent * 100) if tc_ent > 0 else 0

        with st.expander(f"🏦 {entidad_nombre}  —  Coste: {fmt_eur2(tc_ent)}  |  Valor: {fmt_eur2(tv_ent)}  |  Plusvalía: {fmt_eur2(tp_ent)} ({pct_ent:+.2f}%)", 
                         expanded=False):
            e1, e2, e3, e4 = st.columns(4)
            e1.metric("💰 Coste invertido",  fmt_eur2(tc_ent))
            e2.metric("📈 Valor actual",     fmt_eur2(tv_ent))
            e3.metric("✨ Plusvalía latente", fmt_eur2(tp_ent), delta=f"{pct_ent:+.2f}%")
            e4.metric("📋 Activos",          len(df_ent))

            st.dataframe(
                df_ent.drop(columns=["Entidad"]),
                hide_index=True,
                width='stretch',
                column_config={
                    "Unidades":      st.column_config.NumberColumn(format="%.4f"),
                    "Coste total":   st.column_config.NumberColumn("Coste (€)",     format="%.2f €"),
                    "Precio actual": st.column_config.NumberColumn("Precio (€)",    format="%.6f €"),
                    "Valor actual":  st.column_config.NumberColumn("Valor (€)",     format="%.2f €"),
                    "Plusvalía €":   st.column_config.NumberColumn("Plusvalía (€)", format="%.2f €"),
                    "Plusvalía %":   st.column_config.NumberColumn("Plusvalía (%)", format="%.2f%%"),
                }
            )

    # --- Guardado ---
    if guardar_btn:
        errores  = []
        guardados = 0

        with get_engine().begin() as conn:
            for m in meta_activos:
                precio_guardar = float(st.session_state.get(m["key_precio"], 0.0))
                obs_guardar    = st.session_state.get(m["key_obs"], None) or None

                if precio_guardar <= 0:
                    errores.append(f"⚠️ {m['denominacion']}: precio 0, omitido.")
                    continue
                try:
                    conn.execute(text("""
                        INSERT INTO historico_precios (fecha, isin, entidad_id, precio, observaciones)
                        VALUES (:fecha, :isin, :eid, :precio, :obs)
                        ON CONFLICT ON CONSTRAINT uq_precio_fecha_isin_entidad
                        DO UPDATE SET precio = EXCLUDED.precio,
                                      observaciones = EXCLUDED.observaciones
                    """), {
                        "fecha":  fecha_registro,
                        "isin":   m["isin"],
                        "eid":    m["entidad_id"],
                        "precio": precio_guardar,
                        "obs":    obs_guardar,
                    })
                    guardados += 1
                except Exception as e:
                    errores.append(f"❌ {m['denominacion']}: {e}")

        if guardados:
            st.success(f"✅ {guardados} precio{'s' if guardados != 1 else ''} guardado{'s' if guardados != 1 else ''} correctamente.")
            cargar_activos_inversion.clear()
            time.sleep(1)
            st.rerun()
        for err in errores:
            st.warning(err)


# ===========================================================================
# TAB 2 — HISTÓRICO
# ===========================================================================
with tab_historial:

    with st.expander("🔍 Filtros", expanded=False):
        hf1, hf2, hf3, hf4 = st.columns(4)

        # Activos disponibles en histórico
        activos_hist = run_query("""
            SELECT DISTINCT a.denominacion, hp.isin
            FROM historico_precios hp
            JOIN activos_descripcion a ON hp.isin = a.isin
            ORDER BY a.denominacion
        """)
        opciones_activos = ["Todos"] + activos_hist["denominacion"].tolist() if not activos_hist.empty else ["Todos"]
        filtro_activo = hf1.selectbox("Activo", opciones_activos)

        entidades_hist = run_query("SELECT id, nombre FROM ref_entidad ORDER BY nombre")
        opciones_ent   = ["Todas"] + entidades_hist["nombre"].tolist()
        filtro_ent     = hf2.selectbox("Entidad", opciones_ent)

        f_desde = hf3.date_input("Desde", value=pd.Timestamp.today() - pd.DateOffset(months=3))
        f_hasta = hf4.date_input("Hasta", value=pd.Timestamp.today())

    df_hist = run_query("""
        SELECT
            hp.id,
            hp.fecha                AS "Fecha",
            e.nombre                AS "Entidad",
            a.denominacion          AS "Activo",
            hp.isin                 AS "ISIN",
            hp.precio               AS "Precio (€)",
            hp.observaciones        AS "Observaciones",
            hp.created_at           AS "Registrado"
        FROM historico_precios hp
        JOIN activos_descripcion a ON hp.isin       = a.isin
        JOIN ref_entidad          e ON hp.entidad_id = e.id
        ORDER BY hp.fecha DESC, a.denominacion
    """)

    if df_hist.empty:
        st.info("ℹ️ Aún no hay precios registrados.")
    else:
        df_hist["Fecha"] = pd.to_datetime(df_hist["Fecha"])

        # Aplicar filtros
        mask = (
            (df_hist["Fecha"].dt.date >= f_desde) &
            (df_hist["Fecha"].dt.date <= f_hasta)
        )
        if filtro_activo != "Todos":
            mask &= df_hist["Activo"] == filtro_activo
        if filtro_ent != "Todas":
            mask &= df_hist["Entidad"] == filtro_ent
        df_mostrar = df_hist[mask]

        st.metric("📋 Registros encontrados", len(df_mostrar))
        st.divider()

        st.dataframe(
            df_mostrar.drop(columns=["id", "Registrado"]),
            hide_index=True,
            width='stretch',
            column_config={
                "Fecha":      st.column_config.DateColumn("📅 Fecha", format="DD/MM/YYYY"),
                "Precio (€)": st.column_config.NumberColumn("Precio (€)", format="%.6f €"),
            }
        )

        csv = df_mostrar.drop(columns=["id", "Registrado"]).to_csv(index=False, sep=";", decimal=",").encode("utf-8")
        st.download_button(
            "⬇️ Exportar CSV",
            data=csv,
            file_name=f"historico_precios_{f_desde}_{f_hasta}.csv",
            mime="text/csv",
        )


# ===========================================================================
# TAB 3 — EDITAR / BORRAR
# ===========================================================================
with tab_editar:
    st.subheader("Selecciona un registro para editarlo o borrarlo")

    if "hp_edit_id"      not in st.session_state: st.session_state.hp_edit_id      = None
    if "hp_edit_preview" not in st.session_state: st.session_state.hp_edit_preview = None

    df_edit_src = run_query("""
        SELECT
            hp.id,
            hp.fecha                AS "Fecha",
            e.nombre                AS "Entidad",
            a.denominacion          AS "Activo",
            hp.precio               AS "Precio (€)",
            hp.observaciones        AS "Observaciones"
        FROM historico_precios hp
        JOIN activos_descripcion a ON hp.isin       = a.isin
        JOIN ref_entidad          e ON hp.entidad_id = e.id
        ORDER BY hp.fecha DESC, a.denominacion
        LIMIT 300
    """)

    if df_edit_src.empty:
        st.info("ℹ️ No hay registros que editar.")
    else:
        selection = st.dataframe(
            df_edit_src.drop(columns=["id"]),
            hide_index=True,
            width='stretch',
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "Fecha":      st.column_config.DateColumn("📅 Fecha", format="DD/MM/YYYY"),
                "Precio (€)": st.column_config.NumberColumn("Precio (€)", format="%.6f €"),
            }
        )

        if len(selection.selection.rows) > 0:
            idx    = selection.selection.rows[0]
            fila   = df_edit_src.iloc[idx]
            reg_id = int(fila["id"])

            if st.session_state.hp_edit_id != reg_id:
                st.session_state.hp_edit_id      = reg_id
                st.session_state.hp_edit_preview = None

            datos = run_query(
                "SELECT * FROM historico_precios WHERE id = :id", {"id": reg_id}
            ).iloc[0]

            st.divider()
            st.markdown(f"#### ✏️ Editando registro ID **{reg_id}** — {fila['Activo']} ({fila['Entidad']})")

            with st.form(f"form_edit_precio_{reg_id}"):
                ec1, ec2, ec3 = st.columns([2, 2, 3])

                fecha_e  = ec1.date_input(
                    "📅 Fecha",
                    value=pd.to_datetime(datos["fecha"]).date(),
                    format="DD/MM/YYYY"
                )
                precio_e = ec2.number_input(
                    "💶 Precio (€)",
                    min_value=0.000001,
                    step=0.01,
                    format="%.6f",
                    value=float(datos["precio"])
                )
                obs_e = ec3.text_input(
                    "📝 Observaciones",
                    value=datos["observaciones"] or ""
                )

                btn_col1, btn_col2 = st.columns([1, 1])
                btn_actualizar = btn_col1.form_submit_button(
                    "📝 Actualizar registro",
                    type="primary",
                    width='stretch'
                )
                # Placeholder para mantener layout
                btn_col2.empty()

            if btn_actualizar:
                try:
                    execute_non_query("""
                        UPDATE historico_precios SET
                            fecha         = :fecha,
                            precio        = :precio,
                            observaciones = :obs
                        WHERE id = :id
                    """, {
                        "id":     reg_id,
                        "fecha":  fecha_e,
                        "precio": precio_e,
                        "obs":    obs_e or None,
                    })
                    st.success("✅ Registro actualizado correctamente.")
                    st.session_state.hp_edit_id      = None
                    st.session_state.hp_edit_preview = None
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al actualizar: {e}")

            # --- Zona de borrado ---
            st.divider()
            with st.expander("⚠️ Zona peligrosa: eliminar registro"):
                st.warning(
                    f"Se eliminará permanentemente el precio de **{fila['Activo']}** "
                    f"del **{pd.to_datetime(datos['fecha']).strftime('%d/%m/%Y')}** "
                    f"— **{fmt_eur(datos['precio'])}**"
                )
                confirmar = st.checkbox("Confirmo que quiero eliminar este registro")
                if st.button("🗑️ Eliminar", type="primary", disabled=not confirmar):
                    try:
                        execute_non_query(
                            "DELETE FROM historico_precios WHERE id = :id", {"id": reg_id}
                        )
                        st.success("Registro eliminado.")
                        st.session_state.hp_edit_id      = None
                        st.session_state.hp_edit_preview = None
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al eliminar: {e}")