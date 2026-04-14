import streamlit as st
import pandas as pd
from database import run_query, execute_non_query, cargar_referencias, get_engine
from sqlalchemy import text
import time

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Inversiones", layout="wide")

st.title("📈 Gestión de Inversiones")
st.caption("Registro de compras y ventas de activos financieros.")

# ---------------------------------------------------------------------------
# 1. CARGA DE DATOS DE REFERENCIA
# ---------------------------------------------------------------------------
df_activos_todos, dict_tipos, dict_entidades, dict_estrategias = cargar_referencias()

TIPOS_INVERSION = ["Compra", "Venta"]

# Diccionario nombre → isin para todos los activos
dict_activos_nombre_isin = dict(zip(df_activos_todos["denominacion"], df_activos_todos["isin"]))
dict_activos_isin_nombre = dict(zip(df_activos_todos["isin"], df_activos_todos["denominacion"]))

# Categorías ordenadas con "Ninguna" por defecto
categorias_ord = sorted(dict_estrategias.keys())
idx_ninguna    = categorias_ord.index("Ninguna") if "Ninguna" in categorias_ord else 0


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def fmt_eur(n):
    try:
        return f"{float(n):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "—"


def calcular_inversion(tipo: str, unidades: float, precio: float,
                       com: float, can: float, imp: float) -> dict:
    """
    Devuelve un dict con todos los importes calculados.
    - importe_bruto  = unidades × precio unitario
    - gastos_totales = comisión + canon + impuestos
    - importe_total:
        Compra → bruto + gastos  (pagas el activo MÁS los costes)
        Venta  → bruto - gastos  (recibes el activo MENOS los costes)
    """
    bruto  = round(unidades * precio, 2)
    gastos = round(com + can + imp, 2)
    if tipo == "Compra":
        total = round(bruto + gastos, 2)
    else:
        total = round(bruto - gastos, 2)
    return {"bruto": bruto, "gastos": gastos, "total": total}


# ---------------------------------------------------------------------------
# 2. TABS PRINCIPALES
# ---------------------------------------------------------------------------
tab_nuevo, tab_historial, tab_editar = st.tabs(
    ["🆕 Nueva Operación", "📜 Historial", "✏️ Editar / Borrar"]
)


# ===========================================================================
# TAB 1 — NUEVA OPERACIÓN
# ===========================================================================
with tab_nuevo:

    # --- Session state ---
    if "inv_tick"    not in st.session_state: st.session_state.inv_tick    = 0
    if "inv_preview" not in st.session_state: st.session_state.inv_preview = None

    # ── Entidad y Activo FUERA del form ────────────────────────────────────────
    # Al estar fuera, al cambiar entidad se recarga la lista de activos
    # inmediatamente sin esperar al submit del form.
    pre1, pre2, pre3 = st.columns([2, 3, 2])
    ent_nombre = pre1.selectbox("🏦 Entidad", sorted(dict_entidades.keys()),
                                key="inv_ent")
    ent_id_sel      = dict_entidades[ent_nombre]
    activos_entidad = df_activos_todos[
        df_activos_todos["entidad_id"].astype(int) == int(ent_id_sel)
    ]["denominacion"].tolist()
    if not activos_entidad:
        st.warning("⚠️ No hay activos registrados para esta entidad.")
        activos_entidad = ["— sin activos —"]
    activo_nombre = pre2.selectbox(
        "📦 Activo (ISIN / Nombre)", activos_entidad,
        help="Activo que se compra o vende", key="inv_activo"
    )
    tipo_mov = pre3.selectbox("↕️ Tipo de operación", TIPOS_INVERSION,
                              key="inv_tipo")

    # ── Cuenta de efectivo FUERA del form — filtrada por la misma entidad ─────
    label_cuenta_od = (
        "💳 Cuenta de la que sale el dinero"
        if st.session_state.get("inv_tipo", TIPOS_INVERSION[0]) == "Compra"
        else "💳 Cuenta donde ingresa el dinero"
    )
    activos_entidad_od = ["— No registrar movimiento de efectivo —"] + df_activos_todos[
        df_activos_todos["entidad_id"].astype(int) == int(ent_id_sel)
    ]["denominacion"].tolist()
    # Excluimos el propio activo que se compra/vende de la lista
    activo_sel = st.session_state.get("inv_activo", "")
    activos_entidad_od = [a for a in activos_entidad_od if a != activo_sel]

    cuenta_od_nombre = st.selectbox(
        label_cuenta_od,
        activos_entidad_od,
        key="inv_cuenta_od",
        help="Cuenta de la misma entidad desde/hacia donde fluye el efectivo"
    )

    with st.form(f"form_inversion_{st.session_state.inv_tick}", clear_on_submit=False):

        # ── Fila 1: Fecha · Estrategia ──────────────────────────────────────
        c1, c2 = st.columns([2, 3])
        fecha      = c1.date_input("📅 Fecha operación", value=pd.Timestamp.today(), format="DD/MM/YYYY")
        estrategia = c2.selectbox(
            "🏷️ Estrategia",
            categorias_ord,
            index=idx_ninguna,
            help="Estrategia que motiva la operación"
        )

        st.divider()

        # ── Fila 3: Unidades · Precio unitario ──────────────────────────────
        c6, c7 = st.columns([2, 2])
        unidades = c6.number_input(
            "🔢 Unidades / Participaciones",
            min_value=0.0001, step=1.0, format="%.4f",
            help="Número de acciones, participaciones o unidades"
        )
        precio_unitario = c7.number_input(
            "💵 Precio unitario (€)",
            min_value=0.000001, step=0.01, format="%.6f",
            help="Precio por unidad en el momento de la operación"
        )

        # ── Fila 4: Costes ───────────────────────────────────────────────────
        c8, c9, c10 = st.columns(3)
        com = c8.number_input("Comisión broker (€)", min_value=0.0, step=0.5, format="%.2f")
        can = c9.number_input("Canon bolsa (€)",     min_value=0.0, step=0.5, format="%.2f")
        imp = c10.number_input(
            "Impuestos / Retención (€)",
            min_value=0.0, step=0.5, format="%.2f",
            help="Retención fiscal, tasa Tobin, etc."
        )

        # ── Observaciones ────────────────────────────────────────────────────
        obs = st.text_input(
            "📝 Observaciones",
            placeholder="Ej: Aportación mensual indexado, Stop-loss Telefónica..."
        )

        st.divider()

        # ── Botones ──────────────────────────────────────────────────────────
        btn_col1, btn_col2 = st.columns([1, 1])
        btn_calcular = btn_col1.form_submit_button(
            "🔄 Calcular operación",
            use_container_width=True,
        )
        btn_guardar = btn_col2.form_submit_button(
            "💾 Grabar Operación",
            type="primary",
            use_container_width=True,
            disabled=(st.session_state.inv_preview is None),
        )

    # ── Lógica post-submit ───────────────────────────────────────────────────

    if btn_calcular:
        resultado = calcular_inversion(tipo_mov, unidades, precio_unitario, com, can, imp)
        st.session_state.inv_preview = {
            # importes
            **resultado,
            # campos de operación
            "tipo":             tipo_mov,
            "fecha":            fecha,
            "ent_id":           ent_id_sel,
            "activo_nombre":    activo_nombre,
            "estrategia":       estrategia,
            "unidades":         unidades,
            "precio_unitario":  precio_unitario,
            "com":              com,
            "can":              can,
            "imp":              imp,
            "cuenta_od_nombre": cuenta_od_nombre,
            "obs":              obs,
        }
        st.rerun()

    if st.session_state.inv_preview is not None:
        p = st.session_state.inv_preview
        signo = "−" if p["tipo"] == "Compra" else "+"
        color  = "red" if p["tipo"] == "Compra" else "green"

        col_prev1, col_prev2, col_prev3, col_prev4 = st.columns(4)
        col_prev1.metric("📊 Importe bruto",   fmt_eur(p["bruto"]))
        col_prev2.metric("💸 Gastos totales",  fmt_eur(p["gastos"]))
        col_prev3.metric(
            "💶 Capital " + ("invertido" if p["tipo"] == "Compra" else "recibido"),
            fmt_eur(p["total"])
        )
        col_prev4.metric(
            "Precio medio unitario",
            fmt_eur(p["total"] / p["unidades"]) if p["unidades"] else "—"
        )

        st.info(
            f"**Impacto en efectivo:** :{color}[{signo} {fmt_eur(p['total'])}]  \n"
            f"{p['unidades']:.4f} uds × {fmt_eur(p['precio_unitario'])} | "
            f"Comisión **{fmt_eur(p['com'])}** | "
            f"Canon **{fmt_eur(p['can'])}** | "
            f"Impuestos **{fmt_eur(p['imp'])}**"
            + (f"\n\n**Cuenta efectivo:** {p['cuenta_od_nombre']}" if p["cuenta_od_nombre"] != "— No registrar movimiento de efectivo —" else "")
        )
        st.caption("✅ Revisa la operación. Si es correcta pulsa **Grabar Operación**. Si cambias algún campo, vuelve a calcular.")

    if btn_guardar and st.session_state.inv_preview is not None:
        p = st.session_state.inv_preview

        if p["activo_nombre"] == "— sin activos —":
            st.error("❌ Selecciona un activo válido.")
        else:
            isin_activo  = dict_activos_nombre_isin.get(p["activo_nombre"])
            isin_cuenta  = (
                dict_activos_nombre_isin.get(p["cuenta_od_nombre"])
                if p["cuenta_od_nombre"] != "— No registrar movimiento de efectivo —"
                else None
            )

            try:
                sql_inversion = text("""
                    INSERT INTO transacciones (
                        fecha_operacion, entidad_id, isin,
                        tipo_transaccion_id, operativa,
                        unidades, precio_unitario,
                        importe_neto, comision, canon, impuestos, importe_total,
                        isin_origen_destino, estrategia_id, observaciones
                    ) VALUES (
                        :fecha, :eid, :isin,
                        :tipo_id, 'INVERSION',
                        :unidades, :precio,
                        :bruto, :com, :can, :imp, :total,
                        :isin_od, :estrategia_id, :obs
                    )
                """)

                params_inversion = {
                    "fecha":        p["fecha"],
                    "eid":          p["ent_id"],
                    "isin":         isin_activo,
                    "tipo_id":      dict_tipos[p["tipo"]],
                    "unidades":     p["unidades"],
                    "precio":       p["precio_unitario"],
                    "bruto":        p["bruto"],
                    "com":          p["com"],
                    "can":          p["can"],
                    "imp":          p["imp"],
                    "total":        p["total"],
                    "isin_od":      isin_cuenta,
                    "estrategia_id": dict_estrategias[p["estrategia"]],
                    "obs":          p["obs"] or None,
                }

                # Preparar contramovimiento de tesorería si hay cuenta asociada
                if isin_cuenta:
                    tipo_contra = "Gasto" if p["tipo"] == "Compra" else "Ingreso"
                    cuenta_row  = df_activos_todos[df_activos_todos["isin"] == isin_cuenta]
                    eid_cuenta  = int(cuenta_row["entidad_id"].iloc[0]) if not cuenta_row.empty else p["ent_id"]

                    sql_tesoreria = text("""
                        INSERT INTO transacciones (
                            fecha_operacion, entidad_id, isin,
                            tipo_transaccion_id, operativa,
                            unidades, precio_unitario,
                            importe_neto, comision, canon, impuestos, importe_total,
                            isin_origen_destino, estrategia_id, observaciones
                        ) VALUES (
                            :fecha, :eid, :isin,
                            :tipo_id, 'TESORERIA',
                            0, 0,
                            :total, 0, 0, 0, :total,
                            :isin_activo, :estrategia_id, :obs
                        )
                    """)
                    params_tesoreria = {
                        "fecha":        p["fecha"],
                        "eid":          eid_cuenta,
                        "isin":         isin_cuenta,
                        "tipo_id":      dict_tipos[tipo_contra],
                        "total":        p["total"],
                        "isin_activo":  isin_activo,
                        "estrategia_id": dict_estrategias[p["estrategia"]],
                        "obs":          f"[AUTO] {p['tipo']} {p['activo_nombre']} — {p['obs'] or ''}".strip("— "),
                    }

                # Ejecutar ambos INSERTs en una única transacción atómica:
                # si el segundo falla, el primero también se revierte (rollback automático)
                with get_engine().begin() as conn:
                    conn.execute(sql_inversion, params_inversion)
                    if isin_cuenta:
                        conn.execute(sql_tesoreria, params_tesoreria)

                signo = "−" if p["tipo"] == "Compra" else "+"
                st.success(
                    f"✅ {p['tipo']} registrada: **{p['unidades']:.4f} uds** de **{p['activo_nombre']}** "
                    f"por {signo} {fmt_eur(p['total'])}"
                    + (f"  \nContramovimiento de efectivo registrado en **{p['cuenta_od_nombre']}**." if isin_cuenta else "")
                )
                st.session_state.inv_tick    += 1
                st.session_state.inv_preview  = None
                time.sleep(1.5)
                st.rerun()

            except Exception as e:
                st.error(f"❌ Error al guardar: {e}")


# ===========================================================================
# TAB 2 — HISTORIAL
# ===========================================================================
with tab_historial:

    with st.expander("🔍 Filtros", expanded=False):
        hf1, hf2, hf3, hf4 = st.columns(4)
        ent_filtro  = hf1.multiselect("Entidad", sorted(dict_entidades.keys()), default=sorted(dict_entidades.keys()))
        tipo_filtro = hf2.multiselect("Tipo", TIPOS_INVERSION, default=TIPOS_INVERSION)
        f_desde     = hf3.date_input("Desde", value=pd.Timestamp.today() - pd.DateOffset(years=1))
        f_hasta     = hf4.date_input("Hasta", value=pd.Timestamp.today())

    historial = run_query("""
        SELECT
            t.id,
            t.fecha_operacion                       AS "Fecha",
            e.nombre                                AS "Entidad",
            rt.nombre                               AS "Tipo",
            a.isin                                  AS "ISIN",
            a.denominacion                          AS "Activo",
            t.unidades                              AS "Unidades",
            t.precio_unitario                       AS "Precio ud.",
            t.importe_neto                          AS "Importe bruto",
            t.comision                              AS "Comisión",
            t.canon                                 AS "Canon",
            t.impuestos                             AS "Impuestos",
            t.importe_total                         AS "Total",
            aod.denominacion                        AS "Cuenta efectivo",
            es.nombre                               AS "Estrategia",
            t.observaciones                         AS "Observaciones"
        FROM transacciones t
        JOIN ref_entidad          e   ON t.entidad_id          = e.id
        JOIN activos_descripcion  a   ON t.isin                = a.isin
        JOIN ref_tipo_transaccion rt  ON t.tipo_transaccion_id = rt.id
        LEFT JOIN ref_estrategia  es  ON t.estrategia_id       = es.id
        LEFT JOIN activos_descripcion aod ON t.isin_origen_destino = aod.isin
        WHERE t.operativa = 'INVERSION'
        ORDER BY t.fecha_operacion DESC, t.id DESC
    """)

    if historial.empty:
        st.info("ℹ️ No hay operaciones de inversión registradas todavía.")
    else:
        df_hist = historial.copy()
        df_hist["Fecha"] = pd.to_datetime(df_hist["Fecha"])

        if ent_filtro:
            df_hist = df_hist[df_hist["Entidad"].isin(ent_filtro)]
        if tipo_filtro:
            df_hist = df_hist[df_hist["Tipo"].isin(tipo_filtro)]
        df_hist = df_hist[
            (df_hist["Fecha"].dt.date >= f_desde) &
            (df_hist["Fecha"].dt.date <= f_hasta)
        ]

        # Métricas resumen
        total_compras = df_hist.loc[df_hist["Tipo"] == "Compra", "Total"].sum()
        total_ventas  = df_hist.loc[df_hist["Tipo"] == "Venta",  "Total"].sum()
        saldo_neto    = total_ventas - total_compras

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📥 Capital comprado",  fmt_eur(total_compras))
        m2.metric("📤 Capital vendido",   fmt_eur(total_ventas))
        m3.metric("⚖️ Flujo neto",        fmt_eur(saldo_neto))
        m4.metric("📋 Operaciones",        len(df_hist))

        st.divider()

        st.dataframe(
            df_hist.drop(columns=["id"]),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Fecha":         st.column_config.DateColumn("📅 Fecha", format="DD/MM/YYYY"),
                "Unidades":      st.column_config.NumberColumn("Unidades", format="%.4f"),
                "Precio ud.":    st.column_config.NumberColumn("Precio ud. (€)", format="%.6f €"),
                "Importe bruto": st.column_config.NumberColumn("Bruto (€)", format="%.2f €"),
                "Comisión":      st.column_config.NumberColumn("Comisión (€)", format="%.2f €"),
                "Canon":         st.column_config.NumberColumn("Canon (€)", format="%.2f €"),
                "Impuestos":     st.column_config.NumberColumn("Impuestos (€)", format="%.2f €"),
                "Total":         st.column_config.NumberColumn("💶 Total (€)", format="%.2f €"),
            },
        )

        csv = df_hist.drop(columns=["id"]).to_csv(index=False, sep=";", decimal=",").encode("utf-8")
        st.download_button(
            "⬇️ Exportar CSV",
            data=csv,
            file_name=f"inversiones_{f_desde}_{f_hasta}.csv",
            mime="text/csv",
        )


# ===========================================================================
# TAB 3 — EDITAR / BORRAR
# ===========================================================================
with tab_editar:
    st.subheader("Selecciona una operación para editarla o borrarla")
    st.caption("⚠️ Si la operación tiene un contramovimiento de efectivo asociado, deberás corregirlo manualmente en Tesorería.")

    # Session state para el preview de edición
    if "inv_edit_preview"     not in st.session_state: st.session_state.inv_edit_preview     = None
    if "inv_edit_preview_for" not in st.session_state: st.session_state.inv_edit_preview_for = None

    df_edit_source = run_query("""
        SELECT
            t.id,
            t.fecha_operacion                       AS "Fecha",
            e.nombre                                AS "Entidad",
            rt.nombre                               AS "Tipo",
            a.denominacion                          AS "Activo",
            t.unidades                              AS "Unidades",
            t.importe_total                         AS "Total",
            t.observaciones                         AS "Observaciones"
        FROM transacciones t
        JOIN ref_entidad          e  ON t.entidad_id          = e.id
        JOIN activos_descripcion  a  ON t.isin                = a.isin
        JOIN ref_tipo_transaccion rt ON t.tipo_transaccion_id = rt.id
        WHERE t.operativa = 'INVERSION'
        ORDER BY t.fecha_operacion DESC, t.id DESC
        LIMIT 200
    """)

    if df_edit_source.empty:
        st.info("ℹ️ No hay operaciones que editar.")
    else:
        selection = st.dataframe(
            df_edit_source.drop(columns=["id"]),
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "Fecha":    st.column_config.DateColumn("📅 Fecha", format="DD/MM/YYYY"),
                "Unidades": st.column_config.NumberColumn("Unidades", format="%.4f"),
                "Total":    st.column_config.NumberColumn("💶 Total (€)", format="%.2f €"),
            },
        )

        if len(selection.selection.rows) > 0:
            idx    = selection.selection.rows[0]
            fila   = df_edit_source.iloc[idx]
            mov_id = int(fila["id"])

            # Resetear preview si cambia la fila seleccionada
            if st.session_state.inv_edit_preview_for != mov_id:
                st.session_state.inv_edit_preview     = None
                st.session_state.inv_edit_preview_for = mov_id

            # Cargar registro completo
            datos = run_query(
                "SELECT * FROM transacciones WHERE id = :id", {"id": mov_id}
            ).iloc[0]

            # Resolver nombres actuales
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
                if datos["estrategia_id"] else categorias_ord[idx_ninguna]
            )

            activo_actual_nombre = dict_activos_isin_nombre.get(datos["isin"], "")
            cuenta_od_actual = (
                dict_activos_isin_nombre.get(datos["isin_origen_destino"], "— No registrar movimiento de efectivo —")
                if datos["isin_origen_destino"] else "— No registrar movimiento de efectivo —"
            )

            st.divider()
            st.markdown(f"#### ✏️ Editando operación ID **{mov_id}**")

            # ── Entidad y Activo FUERA del form de edición ──────────────────
            ed1, ed2, ed3 = st.columns([2, 3, 2])
            ent_e = ed1.selectbox(
                "🏦 Entidad",
                sorted(dict_entidades.keys()),
                index=sorted(dict_entidades.keys()).index(ent_actual) if ent_actual in dict_entidades else 0,
                key=f"edit_inv_ent_{mov_id}"
            )
            ent_id_e      = dict_entidades[ent_e]
            activos_ent_e = df_activos_todos[
                df_activos_todos["entidad_id"].astype(int) == int(ent_id_e)
            ]["denominacion"].tolist()
            if not activos_ent_e:
                activos_ent_e = ["— sin activos —"]
            activo_e = ed2.selectbox(
                "📦 Activo",
                activos_ent_e,
                index=activos_ent_e.index(activo_actual_nombre) if activo_actual_nombre in activos_ent_e else 0,
                key=f"edit_inv_activo_{mov_id}"
            )
            tipo_e = ed3.selectbox(
                "↕️ Tipo",
                TIPOS_INVERSION,
                index=TIPOS_INVERSION.index(tipo_actual) if tipo_actual in TIPOS_INVERSION else 0,
                key=f"edit_inv_tipo_{mov_id}"
            )

            # ── Cuenta efectivo FUERA del form de edición — filtrada por entidad ─
            activos_od_e = ["— No registrar movimiento de efectivo —"] + df_activos_todos[
                df_activos_todos["entidad_id"].astype(int) == int(ent_id_e)
            ]["denominacion"].tolist()
            # Excluir el propio activo editado de la lista
            activos_od_e = [a for a in activos_od_e if a != activo_e]
            cuenta_od_e = st.selectbox(
                "💳 Cuenta efectivo (origen/destino)",
                activos_od_e,
                index=activos_od_e.index(cuenta_od_actual) if cuenta_od_actual in activos_od_e else 0,
                key=f"edit_inv_cuenta_od_{mov_id}",
                help="Cuenta de la misma entidad desde/hacia donde fluye el efectivo"
            )

            with st.form(f"form_edicion_inv_{mov_id}"):

                ec1, ec2 = st.columns([2, 3])
                fecha_e = ec1.date_input("📅 Fecha", value=pd.to_datetime(datos["fecha_operacion"]).date(), format="DD/MM/YYYY")
                estr_e = ec2.selectbox(
                    "🏷️ Estrategia",
                    categorias_ord,
                    index=categorias_ord.index(estrategia_actual) if estrategia_actual in categorias_ord else idx_ninguna
                )

                cu1, cu2 = st.columns([2, 2])
                unidades_e = cu1.number_input(
                    "🔢 Unidades", min_value=0.0001, step=1.0, format="%.4f",
                    value=float(datos["unidades"])
                )
                precio_e = cu2.number_input(
                    "💵 Precio unitario (€)", min_value=0.000001, step=0.01, format="%.6f",
                    value=float(datos["precio_unitario"])
                )

                gc1, gc2, gc3 = st.columns(3)
                com_e    = gc1.number_input("Comisión broker (€)", min_value=0.0, step=0.5, format="%.2f", value=float(datos["comision"]))
                can_e    = gc2.number_input("Canon bolsa (€)",     min_value=0.0, step=0.5, format="%.2f", value=float(datos["canon"]))
                imp_e    = gc3.number_input("Impuestos (€)",       min_value=0.0, step=0.5, format="%.2f", value=float(datos["impuestos"]))

                obs_e = st.text_input("📝 Observaciones", value=datos["observaciones"] or "")

                st.divider()

                btn_col1, btn_col2 = st.columns([1, 1])
                btn_calcular_e = btn_col1.form_submit_button(
                    "🔄 Calcular operación",
                    use_container_width=True,
                )
                btn_actualizar = btn_col2.form_submit_button(
                    "📝 Actualizar Operación",
                    type="primary",
                    use_container_width=True,
                    disabled=(st.session_state.inv_edit_preview is None),
                )

            # ── Lógica post-submit del form de edición ───────────────────────

            if btn_calcular_e:
                resultado_e = calcular_inversion(tipo_e, unidades_e, precio_e, com_e, can_e, imp_e)
                st.session_state.inv_edit_preview = {
                    **resultado_e,
                    "tipo":             tipo_e,
                    "fecha":            fecha_e,
                    "ent_id":           ent_id_e,
                    "activo_nombre":    activo_e,
                    "estrategia":       estr_e,
                    "unidades":         unidades_e,
                    "precio_unitario":  precio_e,
                    "com":              com_e,
                    "can":              can_e,
                    "imp":              imp_e,
                    "cuenta_od_nombre": cuenta_od_e,
                    "obs":              obs_e,
                }
                st.rerun()

            if st.session_state.inv_edit_preview is not None:
                p = st.session_state.inv_edit_preview
                signo_e = "−" if p["tipo"] == "Compra" else "+"
                color_e  = "red" if p["tipo"] == "Compra" else "green"

                col_p1, col_p2, col_p3, col_p4 = st.columns(4)
                col_p1.metric("📊 Importe bruto",  fmt_eur(p["bruto"]))
                col_p2.metric("💸 Gastos totales", fmt_eur(p["gastos"]))
                col_p3.metric(
                    "💶 Capital " + ("invertido" if p["tipo"] == "Compra" else "recibido"),
                    fmt_eur(p["total"])
                )
                col_p4.metric(
                    "Precio medio unitario",
                    fmt_eur(p["total"] / p["unidades"]) if p["unidades"] else "—"
                )

                _no_cuenta = "— No registrar movimiento de efectivo —"
                _label_cuenta = (
                    "💳 **Cargo en:** " if p["tipo"] == "Compra" else "💳 **Abono en:** "
                )
                _cuenta_info = (
                    f"  \n{_label_cuenta}**{p['cuenta_od_nombre']}**"
                    if p["cuenta_od_nombre"] != _no_cuenta
                    else "  \n💳 Sin movimiento de efectivo asociado"
                )
                st.info(
                    f"**Impacto en efectivo:** :{color_e}[{signo_e} {fmt_eur(p['total'])}]  \n"
                    f"{p['unidades']:.4f} uds × {fmt_eur(p['precio_unitario'])} | "
                    f"Comisión **{fmt_eur(p['com'])}** | Canon **{fmt_eur(p['can'])}** | Impuestos **{fmt_eur(p['imp'])}**"
                    + _cuenta_info
                )
                st.caption("✅ Revisa la operación. Si es correcta pulsa **Actualizar Operación**. Si cambias algún campo, vuelve a calcular.")

            if btn_actualizar and st.session_state.inv_edit_preview is not None:
                p        = st.session_state.inv_edit_preview
                isin_act = dict_activos_nombre_isin.get(p["activo_nombre"])
                isin_od  = (
                    dict_activos_nombre_isin.get(p["cuenta_od_nombre"])
                    if p["cuenta_od_nombre"] != "— No registrar movimiento de efectivo —"
                    else None
                )
                try:
                    execute_non_query("""
                        UPDATE transacciones SET
                            fecha_operacion     = :fecha,
                            entidad_id          = :eid,
                            isin                = :isin,
                            tipo_transaccion_id = :tipo_id,
                            unidades            = :unidades,
                            precio_unitario     = :precio,
                            importe_neto        = :bruto,
                            comision            = :com,
                            canon               = :can,
                            impuestos           = :imp,
                            importe_total       = :total,
                            isin_origen_destino = :isin_od,
                            estrategia_id       = :estrategia_id,
                            observaciones       = :obs
                        WHERE id = :id
                    """, {
                        "id":           mov_id,
                        "fecha":        p["fecha"],
                        "eid":          p["ent_id"],
                        "isin":         isin_act,
                        "tipo_id":      dict_tipos[p["tipo"]],
                        "unidades":     p["unidades"],
                        "precio":       p["precio_unitario"],
                        "bruto":        p["bruto"],
                        "com":          p["com"],
                        "can":          p["can"],
                        "imp":          p["imp"],
                        "total":        p["total"],
                        "isin_od":      isin_od,
                        "estrategia_id": dict_estrategias[p["estrategia"]],
                        "obs":          p["obs"] or None,
                    })
                    st.success("✅ Operación actualizada correctamente.")
                    st.session_state.inv_edit_preview     = None
                    st.session_state.inv_edit_preview_for = None
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al actualizar: {e}")

            # ── Zona de borrado ───────────────────────────────────────────────
            st.divider()
            with st.expander("⚠️ Zona peligrosa: eliminar operación"):

                # Buscar si existe un contramovimiento [AUTO] de tesorería asociado
                df_contra = run_query("""
                    SELECT id FROM transacciones
                    WHERE operativa            = 'TESORERIA'
                      AND isin_origen_destino  = :isin_activo
                      AND fecha_operacion      = :fecha
                      AND observaciones        LIKE '[AUTO]%'
                    ORDER BY id DESC
                    LIMIT 1
                """, {
                    "isin_activo": datos["isin"],
                    "fecha":       datos["fecha_operacion"],
                })
                tiene_contra = not df_contra.empty
                id_contra    = int(df_contra.iloc[0]["id"]) if tiene_contra else None

                msg_warning = (
                    f"Se eliminarán permanentemente **2 registros**:  \n"
                    f"• La operación de inversión del "
                    f"**{pd.to_datetime(datos['fecha_operacion']).strftime('%d/%m/%Y')}** "
                    f"— {tipo_actual} de **{activo_actual_nombre}** "
                    f"por **{fmt_eur(datos['importe_total'])}**  \n"
                    f"• Su contramovimiento de tesorería [AUTO] asociado"
                    if tiene_contra else
                    f"Se eliminará permanentemente la operación del "
                    f"**{pd.to_datetime(datos['fecha_operacion']).strftime('%d/%m/%Y')}** "
                    f"— {tipo_actual} de **{activo_actual_nombre}** "
                    f"por **{fmt_eur(datos['importe_total'])}**.  \n"
                    f"⚠️ No se encontró contramovimiento de tesorería asociado."
                )
                st.warning(msg_warning)

                confirmar = st.checkbox("Confirmo que quiero eliminar esta operación")
                if st.button("🗑️ Eliminar", type="primary", disabled=not confirmar):
                    try:
                        with get_engine().begin() as conn:
                            # Borrar primero el contramovimiento de tesorería (si existe)
                            if id_contra:
                                conn.execute(
                                    text("DELETE FROM transacciones WHERE id = :id"),
                                    {"id": id_contra}
                                )
                            # Borrar la operación de inversión
                            conn.execute(
                                text("DELETE FROM transacciones WHERE id = :id"),
                                {"id": mov_id}
                            )

                        msg_ok = "Operación e inversión eliminadas."
                        if tiene_contra:
                            msg_ok = "Operación de inversión y contramovimiento de tesorería eliminados."
                        st.success(msg_ok)
                        st.session_state.inv_edit_preview     = None
                        st.session_state.inv_edit_preview_for = None
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al eliminar: {e}")