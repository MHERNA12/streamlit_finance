import streamlit as st
import pandas as pd
from database import run_query, execute_non_query, cargar_referencias
import time

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Tesorería", layout="wide")

st.title("💰 Gestión de Tesorería")
st.caption("Registro de ingresos y gastos en cuentas corrientes (nóminas, recibos, intereses, transferencias...)")

# ---------------------------------------------------------------------------
# 1. CARGA DE DATOS DE REFERENCIA
# ---------------------------------------------------------------------------
df_activos_todos, dict_tipos, dict_entidades, dict_estrategias = cargar_referencias()

# Solo tipos relevantes para tesorería
TIPOS_TESORERIA = ["Ingreso", "Gasto"]

# Filtramos solo activos de tipo cuenta corriente/ahorro (tipo_producto_id)
# Usamos todos los activos y dejamos al usuario elegir — ya filtramos por entidad
dict_activos_nombre_isin = dict(zip(df_activos_todos["denominacion"], df_activos_todos["isin"]))


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def fmt_eur(n):
    """Formatea un número como moneda española."""
    try:
        return f"{float(n):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "—"


def calcular_importe_total(tipo: str, importe_neto: float, com: float, can: float, imp: float) -> float:
    """
    Calcula el impacto real en cuenta:
    - Ingreso: lo que realmente entra  = neto - retenciones/gastos
    - Gasto:   lo que realmente sale   = neto + comisiones/gastos extra
    """
    gastos = com + can + imp
    if tipo == "Ingreso":
        return importe_neto - gastos
    else:  # Gasto
        return importe_neto + gastos


# ---------------------------------------------------------------------------
# 2. TABS PRINCIPALES
# ---------------------------------------------------------------------------
tab_nuevo, tab_historial, tab_editar = st.tabs(
    ["🆕 Nuevo Movimiento", "📜 Historial", "✏️ Editar / Borrar"]
)


# ===========================================================================
# TAB 1 — NUEVO MOVIMIENTO
# ===========================================================================
with tab_nuevo:

    # --- Session state ---
    if "tick_teso" not in st.session_state:
        st.session_state.tick_teso = 0
    if "teso_preview" not in st.session_state:
        st.session_state.teso_preview = None

    # ── Entidad y Cuenta FUERA del form ─────────────────────────────────────
    # Deben estar fuera para que al cambiar la entidad se recargue
    # inmediatamente la lista de activos sin esperar al submit del form.
    pre1, pre2 = st.columns([2, 4])
    ent_nombre = pre1.selectbox("🏦 Entidad", sorted(dict_entidades.keys()),
                                key="teso_ent")

    ent_id_sel      = dict_entidades[ent_nombre]
    activos_entidad = df_activos_todos[
        df_activos_todos["entidad_id"].astype(int) == int(ent_id_sel)
    ]["denominacion"].tolist()

    if not activos_entidad:
        st.warning("⚠️ No hay activos registrados para esta entidad. Crea primero un activo de tipo Cuenta Corriente.")
        activos_entidad = ["— sin activos —"]

    cuenta_nombre = pre2.selectbox("💳 Cuenta de Cargo/Abono", activos_entidad,
                                   key="teso_cuenta")

    # ── Resto del formulario ─────────────────────────────────────────────────
    with st.form(f"form_tesoreria_{st.session_state.tick_teso}", clear_on_submit=False):

        # Fila 1: Fecha, Tipo, Categoría
        categorias_ordenadas = sorted(dict_estrategias.keys())
        idx_ninguna = categorias_ordenadas.index("Ninguna") if "Ninguna" in categorias_ordenadas else 0

        c1, c2, c3 = st.columns([2, 2, 3])
        fecha    = c1.date_input("📅 Fecha", value=pd.Timestamp.today(), format="DD/MM/YYYY")
        tipo_mov = c2.selectbox("↕️ Tipo de Movimiento", TIPOS_TESORERIA)
        estrategia = c3.selectbox(
            "🏷️ Categoría / Estrategia",
            categorias_ordenadas,
            index=idx_ninguna,
            help="Usa esta categoría para clasificar el movimiento (Nómina, Suministros, Ocio...)"
        )

        st.divider()

        # Fila 2: Importes
        c6, c7, c8, c9 = st.columns(4)
        importe_neto = c6.number_input(
            "💶 Importe Neto (€)",
            min_value=0.01, step=10.0, format="%.2f",
            help="Importe base antes de gastos adicionales o retenciones"
        )
        com = c7.number_input("Comisión (€)",           min_value=0.0, step=0.5, format="%.2f")
        can = c8.number_input("Canon / Otros (€)",      min_value=0.0, step=0.5, format="%.2f")
        imp = c9.number_input(
            "Impuestos / Retención (€)",
            min_value=0.0, step=0.5, format="%.2f",
            help="Retención IRPF, withholding tax, etc."
        )

        obs = st.text_input(
            "📝 Observaciones",
            placeholder="Ej: Nómina marzo, Recibo luz, Intereses cuenta naranja..."
        )

        st.divider()

        btn_col1, btn_col2 = st.columns([1, 1])
        btn_calcular = btn_col1.form_submit_button(
            "🔄 Calcular impacto",
            use_container_width=True,
        )
        btn_guardar = btn_col2.form_submit_button(
            "💾 Grabar Movimiento",
            type="primary",
            use_container_width=True,
            disabled=(st.session_state.teso_preview is None),
        )

    # ---------------------------------------------------------------------------
    # LÓGICA POST-SUBMIT
    # ---------------------------------------------------------------------------

    # — Botón CALCULAR: solo actualiza el preview en session_state
    if btn_calcular:
        valor = calcular_importe_total(tipo_mov, importe_neto, com, can, imp)
        st.session_state.teso_preview = {
            "valor":       valor,
            "tipo":        tipo_mov,
            "importe_neto": importe_neto,
            "com": com, "can": can, "imp": imp,
            # guardamos también el resto de campos para usarlos al grabar
            "fecha": fecha,
            "ent_id": ent_id_sel,
            "cuenta_nombre": cuenta_nombre,
            "estrategia": estrategia,
            "obs": obs,
        }
        st.rerun()   # forzamos repintado para mostrar el preview y activar el botón

    # — Mostrar preview si existe
    if st.session_state.teso_preview is not None:
        p = st.session_state.teso_preview
        signo = "+" if p["tipo"] == "Ingreso" else "-"
        color  = "green" if p["tipo"] == "Ingreso" else "red"
        st.info(
            f"**Impacto real en cuenta:** :{color}[{signo} {fmt_eur(abs(p['valor']))}]  \n"
            f"Neto **{fmt_eur(p['importe_neto'])}** | "
            f"Comisión **{fmt_eur(p['com'])}** | "
            f"Canon **{fmt_eur(p['can'])}** | "
            f"Impuestos **{fmt_eur(p['imp'])}**  \n"
            f"Cuenta cargo/ abono: **{cuenta_nombre}**"
        )
        st.caption("✅ Revisa el cálculo. Si es correcto pulsa **Grabar Movimiento**. Si cambias algún importe, vuelve a calcular.")

    # — Botón GRABAR: usa los valores del preview guardado
    if btn_guardar and st.session_state.teso_preview is not None:
        p = st.session_state.teso_preview
        if p["cuenta_nombre"] == "— sin activos —":
            st.error("❌ Selecciona una cuenta válida.")
        else:
            isin_cuenta = dict_activos_nombre_isin.get(p["cuenta_nombre"])
            signo = "+" if p["tipo"] == "Ingreso" else "-"
            query = """
                INSERT INTO transacciones (
                    fecha_operacion, entidad_id, isin,
                    tipo_transaccion_id, operativa,
                    unidades, precio_unitario,
                    importe_neto, comision, canon, impuestos, importe_total,
                    estrategia_id, observaciones
                ) VALUES (
                    :fecha, :eid, :isin,
                    :tipo_id, 'TESORERIA',
                    0, 0,
                    :importe_neto, :com, :can, :imp, :importe_total,
                    :estrategia_id, :obs
                )
            """
            params = {
                "fecha":        p["fecha"],
                "eid":          p["ent_id"],
                "isin":         isin_cuenta,
                "tipo_id":      dict_tipos[p["tipo"]],
                "importe_neto": p["importe_neto"],
                "com":          p["com"],
                "can":          p["can"],
                "imp":          p["imp"],
                "importe_total": p["valor"],
                "estrategia_id": dict_estrategias[p["estrategia"]],
                "obs":          p["obs"] or None,
            }
            try:
                execute_non_query(query, params)
                st.success(f"✅ Movimiento registrado: {signo} {fmt_eur(abs(p['valor']))}")
                # Reset completo para el siguiente movimiento
                st.session_state.tick_teso += 1
                st.session_state.teso_preview = None
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al guardar: {e}")


# ===========================================================================
# TAB 2 — HISTORIAL
# ===========================================================================
with tab_historial:

    # --- Filtros rápidos ---
    with st.expander("🔍 Filtros", expanded=False):
        fc1, fc2, fc3, fc4 = st.columns(4)
        entidad_filtro = fc1.multiselect(
            "Entidad",
            options=sorted(dict_entidades.keys()),
            default=sorted(dict_entidades.keys())
        )
        tipo_filtro = fc2.multiselect("Tipo", TIPOS_TESORERIA, default=TIPOS_TESORERIA)
        fecha_desde = fc3.date_input("Desde", value=pd.Timestamp.today() - pd.DateOffset(months=3))
        fecha_hasta = fc4.date_input("Hasta", value=pd.Timestamp.today())

    historial = run_query("""
        SELECT
            t.id,
            t.fecha_operacion                       AS "Fecha",
            e.nombre                                AS "Entidad",
            a.denominacion                          AS "Cuenta",
            rt.nombre                               AS "Tipo",
            es.nombre                               AS "Categoría",
            t.importe_neto                          AS "Importe Neto",
            t.comision                              AS "Comisión",
            t.canon                                 AS "Canon",
            t.impuestos                             AS "Impuestos",
            t.importe_total                         AS "Total Real",
            t.observaciones                         AS "Observaciones"
        FROM transacciones t
        JOIN ref_entidad          e  ON t.entidad_id          = e.id
        JOIN activos_descripcion  a  ON t.isin                = a.isin
        JOIN ref_tipo_transaccion rt ON t.tipo_transaccion_id = rt.id
        LEFT JOIN ref_estrategia  es ON t.estrategia_id       = es.id
        WHERE t.operativa = 'TESORERIA'
        ORDER BY t.fecha_operacion DESC, t.id DESC
    """)

    if historial.empty:
        st.info("ℹ️ No hay movimientos de tesorería registrados todavía.")
    else:
        # Aplicar filtros en Python
        df_hist = historial.copy()
        df_hist["Fecha"] = pd.to_datetime(df_hist["Fecha"])

        if entidad_filtro:
            df_hist = df_hist[df_hist["Entidad"].isin(entidad_filtro)]
        if tipo_filtro:
            df_hist = df_hist[df_hist["Tipo"].isin(tipo_filtro)]
        df_hist = df_hist[
            (df_hist["Fecha"].dt.date >= fecha_desde) &
            (df_hist["Fecha"].dt.date <= fecha_hasta)
        ]

        # Métricas resumen del período filtrado
        total_ingresos = df_hist.loc[df_hist["Tipo"] == "Ingreso", "Total Real"].sum()
        total_gastos   = df_hist.loc[df_hist["Tipo"] == "Gasto",   "Total Real"].sum()
        saldo_neto     = total_ingresos - total_gastos

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📥 Ingresos", fmt_eur(total_ingresos))
        m2.metric("📤 Gastos",   fmt_eur(total_gastos))
        m3.metric(
            "⚖️ Saldo Neto",
            fmt_eur(saldo_neto),
            delta=None,
        )
        m4.metric("📋 Movimientos", len(df_hist))

        st.divider()

        # Tabla con columnas formateadas
        st.dataframe(
            df_hist.drop(columns=["id"]),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Fecha": st.column_config.DateColumn("📅 Fecha", format="DD/MM/YYYY"),
                "Importe Neto": st.column_config.NumberColumn("Neto (€)", format="%.2f €"),
                "Comisión":     st.column_config.NumberColumn("Comisión (€)", format="%.2f €"),
                "Canon":        st.column_config.NumberColumn("Canon (€)", format="%.2f €"),
                "Impuestos":    st.column_config.NumberColumn("Impuestos (€)", format="%.2f €"),
                "Total Real":   st.column_config.NumberColumn("💶 Total Real (€)", format="%.2f €"),
            },
        )

        # Exportar CSV
        csv = df_hist.drop(columns=["id"]).to_csv(index=False, sep=";", decimal=",").encode("utf-8")
        st.download_button(
            "⬇️ Exportar CSV",
            data=csv,
            file_name=f"tesoreria_{fecha_desde}_{fecha_hasta}.csv",
            mime="text/csv",
        )


# ===========================================================================
# TAB 3 — EDITAR / BORRAR
# ===========================================================================
with tab_editar:
    st.subheader("Selecciona un movimiento para editarlo o borrarlo")

    # Session state para el preview de edición
    # La clave incluye el mov_id para que se resetee al cambiar de fila
    if "edit_preview" not in st.session_state:
        st.session_state.edit_preview = None   # None = aún no calculado
    if "edit_preview_for_id" not in st.session_state:
        st.session_state.edit_preview_for_id = None

    # Cargamos los últimos 200 movimientos para seleccionar
    df_edit_source = run_query("""
        SELECT
            t.id,
            t.fecha_operacion                       AS "Fecha",
            e.nombre                                AS "Entidad",
            a.denominacion                          AS "Cuenta",
            rt.nombre                               AS "Tipo",
            t.importe_total                         AS "Total Real",
            t.observaciones                         AS "Observaciones"
        FROM transacciones t
        JOIN ref_entidad          e  ON t.entidad_id          = e.id
        JOIN activos_descripcion  a  ON t.isin                = a.isin
        JOIN ref_tipo_transaccion rt ON t.tipo_transaccion_id = rt.id
        WHERE t.operativa = 'TESORERIA'
        ORDER BY t.fecha_operacion DESC, t.id DESC
        LIMIT 200
    """)

    if df_edit_source.empty:
        st.info("ℹ️ No hay movimientos que editar.")
    else:
        selection = st.dataframe(
            df_edit_source.drop(columns=["id"]),
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "Fecha":      st.column_config.DateColumn("📅 Fecha", format="DD/MM/YYYY"),
                "Total Real": st.column_config.NumberColumn("💶 Total (€)", format="%.2f €"),
            },
        )

        if len(selection.selection.rows) > 0:
            idx    = selection.selection.rows[0]
            fila   = df_edit_source.iloc[idx]
            mov_id = int(fila["id"])

            # Si el usuario cambia de fila, reseteamos el preview
            if st.session_state.edit_preview_for_id != mov_id:
                st.session_state.edit_preview = None
                st.session_state.edit_preview_for_id = mov_id

            # Cargamos el registro completo desde la BD
            datos = run_query(
                "SELECT * FROM transacciones WHERE id = :id", {"id": mov_id}
            ).iloc[0]

            # Resolvemos los nombres actuales para los selectboxes
            tipo_actual = run_query(
                "SELECT nombre FROM ref_tipo_transaccion WHERE id = :id",
                {"id": int(datos["tipo_transaccion_id"])}
            ).iloc[0]["nombre"]
            ent_actual = run_query(
                "SELECT nombre FROM ref_entidad WHERE id = :id",
                {"id": int(datos["entidad_id"])}
            ).iloc[0]["nombre"]
            estrategia_actual = (
                run_query(
                    "SELECT nombre FROM ref_estrategia WHERE id = :id",
                    {"id": int(datos["estrategia_id"])}
                ).iloc[0]["nombre"]
                if datos["estrategia_id"]
                else (categorias_ordenadas[idx_ninguna] if "categorias_ordenadas" in dir() else sorted(dict_estrategias.keys())[0])
            )
            isin_actual_nombre_vals = df_activos_todos[
                df_activos_todos["isin"] == datos["isin"]
            ]["denominacion"].values
            isin_actual_nombre = isin_actual_nombre_vals[0] if len(isin_actual_nombre_vals) > 0 else ""

            st.divider()
            st.markdown(f"#### ✏️ Editando movimiento ID **{mov_id}**")

            # ------------------------------------------------------------------
            # FORMULARIO DE EDICIÓN con dos botones: Calcular | Actualizar
            # Entidad y Cuenta FUERA del form para reactividad inmediata
            # ------------------------------------------------------------------
            ed_pre1, ed_pre2 = st.columns([2, 4])
            ent_e = ed_pre1.selectbox(
                "🏦 Entidad",
                sorted(dict_entidades.keys()),
                index=sorted(dict_entidades.keys()).index(ent_actual) if ent_actual in dict_entidades else 0,
                key=f"edit_ent_{mov_id}"
            )
            ent_id_e  = dict_entidades[ent_e]
            activos_e = df_activos_todos[
                df_activos_todos["entidad_id"].astype(int) == int(ent_id_e)
            ]["denominacion"].tolist()
            if not activos_e:
                activos_e = ["— sin activos —"]
            cuenta_e = ed_pre2.selectbox(
                "💳 Cuenta",
                activos_e,
                index=activos_e.index(isin_actual_nombre) if isin_actual_nombre in activos_e else 0,
                key=f"edit_cuenta_{mov_id}"
            )

            with st.form(f"form_edicion_teso_{mov_id}"):
                ec1, ec2 = st.columns([2, 2])
                fecha_e  = ec1.date_input(
                    "📅 Fecha",
                    value=pd.to_datetime(datos["fecha_operacion"]).date(),
                    format="DD/MM/YYYY"
                )
                tipo_e = ec2.selectbox(
                    "↕️ Tipo",
                    TIPOS_TESORERIA,
                    index=TIPOS_TESORERIA.index(tipo_actual) if tipo_actual in TIPOS_TESORERIA else 0
                )

                cats_ord = sorted(dict_estrategias.keys())
                estr_e = st.selectbox(
                    "🏷️ Categoría",
                    cats_ord,
                    index=cats_ord.index(estrategia_actual) if estrategia_actual in cats_ord else 0
                )

                imp_e1, imp_e2, imp_e3, imp_e4 = st.columns(4)
                importe_neto_e = imp_e1.number_input(
                    "💶 Importe Neto (€)", min_value=0.01, step=10.0, format="%.2f",
                    value=float(datos["importe_neto"])
                )
                com_e    = imp_e2.number_input("Comisión (€)",    min_value=0.0, step=0.5, format="%.2f", value=float(datos["comision"]))
                can_e    = imp_e3.number_input("Canon (€)",       min_value=0.0, step=0.5, format="%.2f", value=float(datos["canon"]))
                imp_imp_e = imp_e4.number_input("Impuestos (€)", min_value=0.0, step=0.5, format="%.2f", value=float(datos["impuestos"]))

                obs_e = st.text_input("📝 Observaciones", value=datos["observaciones"] or "")

                st.divider()

                btn_col1, btn_col2 = st.columns([1, 1])
                btn_calcular_e = btn_col1.form_submit_button(
                    "🔄 Calcular impacto",
                    use_container_width=True,
                )
                btn_actualizar = btn_col2.form_submit_button(
                    "📝 Actualizar Movimiento",
                    type="primary",
                    use_container_width=True,
                    disabled=(st.session_state.edit_preview is None),
                )

            # ------------------------------------------------------------------
            # LÓGICA POST-SUBMIT del formulario de edición
            # ------------------------------------------------------------------

            # — Botón CALCULAR
            if btn_calcular_e:
                valor_e = calcular_importe_total(tipo_e, importe_neto_e, com_e, can_e, imp_imp_e)
                st.session_state.edit_preview = {
                    "valor":        valor_e,
                    "tipo":         tipo_e,
                    "importe_neto": importe_neto_e,
                    "com": com_e, "can": can_e, "imp": imp_imp_e,
                    # campos de contexto necesarios al guardar
                    "fecha":        fecha_e,
                    "ent_id":       ent_id_e,
                    "cuenta_nombre": cuenta_e,
                    "estrategia":   estr_e,
                    "obs":          obs_e,
                }
                st.rerun()

            # — Mostrar preview si existe
            if st.session_state.edit_preview is not None:
                p = st.session_state.edit_preview
                signo_e = "+" if p["tipo"] == "Ingreso" else "-"
                color_e  = "green" if p["tipo"] == "Ingreso" else "red"
                st.info(
                    f"**Impacto real en cuenta:** :{color_e}[{signo_e} {fmt_eur(abs(p['valor']))}]  \n"
                    f"Neto **{fmt_eur(p['importe_neto'])}** | "
                    f"Comisión **{fmt_eur(p['com'])}** | "
                    f"Canon **{fmt_eur(p['can'])}** | "
                    f"Impuestos **{fmt_eur(p['imp'])}**"
                )
                st.caption("✅ Revisa el cálculo. Si es correcto pulsa **Actualizar Movimiento**. Si cambias algún importe, vuelve a calcular.")

            # — Botón ACTUALIZAR: usa los valores del preview guardado
            if btn_actualizar and st.session_state.edit_preview is not None:
                p = st.session_state.edit_preview
                try:
                    execute_non_query("""
                        UPDATE transacciones SET
                            fecha_operacion     = :fecha,
                            entidad_id          = :eid,
                            isin                = :isin,
                            tipo_transaccion_id = :tipo_id,
                            importe_neto        = :importe_neto,
                            comision            = :com,
                            canon               = :can,
                            impuestos           = :imp,
                            importe_total       = :importe_total,
                            estrategia_id       = :estrategia_id,
                            observaciones       = :obs
                        WHERE id = :id
                    """, {
                        "id":           mov_id,
                        "fecha":        p["fecha"],
                        "eid":          p["ent_id"],
                        "isin":         dict_activos_nombre_isin.get(p["cuenta_nombre"]),
                        "tipo_id":      dict_tipos[p["tipo"]],
                        "importe_neto": p["importe_neto"],
                        "com":          p["com"],
                        "can":          p["can"],
                        "imp":          p["imp"],
                        "importe_total": p["valor"],
                        "estrategia_id": dict_estrategias[p["estrategia"]],
                        "obs":          p["obs"] or None,
                    })
                    st.success("✅ Movimiento actualizado correctamente.")
                    # Reset del preview para esta fila
                    st.session_state.edit_preview = None
                    st.session_state.edit_preview_for_id = None
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al actualizar: {e}")

            # ------------------------------------------------------------------
            # ZONA DE BORRADO
            # ------------------------------------------------------------------
            st.divider()
            with st.expander("⚠️ Zona peligrosa: eliminar movimiento"):
                st.warning(
                    f"Se eliminará permanentemente el movimiento del "
                    f"**{pd.to_datetime(datos['fecha_operacion']).strftime('%d/%m/%Y')}** "
                    f"por **{fmt_eur(datos['importe_total'])}**."
                )
                confirmar = st.checkbox("Confirmo que quiero eliminar este movimiento")
                if st.button("🗑️ Eliminar", type="primary", disabled=not confirmar):
                    try:
                        execute_non_query(
                            "DELETE FROM transacciones WHERE id = :id", {"id": mov_id}
                        )
                        st.success("Movimiento eliminado.")
                        st.session_state.edit_preview = None
                        st.session_state.edit_preview_for_id = None
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al eliminar: {e}")