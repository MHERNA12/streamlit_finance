import streamlit as st
import pandas as pd
import os
from database import run_query
from styles import MONEDA_CONFIG


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def fmt(n):
    """Formato moneda española: 1.234,56 €"""
    try:
        return f"{float(n):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "— €"

def mostrar_logo(nombre, width=70):
    """Muestra el logo de una entidad desde la carpeta iconos/."""
    ruta_base = f"iconos/{nombre}"
    for ext in [".png", ".jpg", ".jpeg", ".svg"]:
        if os.path.exists(ruta_base + ext):
            st.image(ruta_base + ext, width=width)
            return
    # Fallback emoji si no existe el archivo
    st.markdown(f"<div style='font-size:2.5rem;text-align:center'>🏦</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 1. CABECERA
# ---------------------------------------------------------------------------
st.title("🏦 Estado Global del Patrimonio")
st.caption(f"Última actualización: {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')}")

# ---------------------------------------------------------------------------
# 2. CARGA DE DATOS
# ---------------------------------------------------------------------------
# Saldo por entidad desglosado en tesorería e inversión
# Tesorería: movimientos operativa='TESORERIA' (Ingreso suma, Gasto resta)
# Inversión:  movimientos operativa='INVERSION'  (Compra resta, Venta suma)
df_resumen = run_query("""
    SELECT
        e.nombre                                                AS entidad,

        -- TESORERÍA: saldo neto de ingresos y gastos
        SUM(CASE
            WHEN t.operativa = 'TESORERIA' AND rt.nombre = 'Ingreso' THEN  t.importe_total
            WHEN t.operativa = 'TESORERIA' AND rt.nombre = 'Gasto'   THEN -t.importe_total
            ELSE 0
        END)                                                    AS saldo_tesoreria,

        -- INVERSIÓN: capital neto (coste de compras menos ingresos de ventas)
        SUM(CASE
            WHEN t.operativa = 'INVERSION' AND rt.nombre = 'Compra' THEN  t.importe_total
            WHEN t.operativa = 'INVERSION' AND rt.nombre = 'Venta'  THEN -t.importe_total
            ELSE 0
        END)                                                    AS capital_invertido

    FROM transacciones t
    JOIN ref_entidad          e  ON t.entidad_id          = e.id
    JOIN ref_tipo_transaccion rt ON t.tipo_transaccion_id = rt.id
    GROUP BY e.nombre
    ORDER BY (SUM(CASE
            WHEN t.operativa = 'TESORERIA' AND rt.nombre = 'Ingreso' THEN  t.importe_total
            WHEN t.operativa = 'TESORERIA' AND rt.nombre = 'Gasto'   THEN -t.importe_total
            WHEN t.operativa = 'INVERSION' AND rt.nombre = 'Compra' THEN  t.importe_total
            WHEN t.operativa = 'INVERSION' AND rt.nombre = 'Venta'  THEN -t.importe_total
            ELSE 0
        END)) DESC
""")

# ---------------------------------------------------------------------------
# 3. TARJETAS POR ENTIDAD + TOTAL GLOBAL
# ---------------------------------------------------------------------------
if df_resumen.empty:
    st.warning("No hay datos suficientes. Registra transacciones en Tesorería o Inversiones.")
    st.stop()

df_resumen["saldo_total"] = df_resumen["saldo_tesoreria"] + df_resumen["capital_invertido"]

total_tesoreria  = df_resumen["saldo_tesoreria"].sum()
total_inversion  = df_resumen["capital_invertido"].sum()
total_global     = df_resumen["saldo_total"].sum()

# Número de columnas = entidades + 1 (total global)
n_cols = len(df_resumen) + 1
cols   = st.columns(n_cols)

# -- Tarjetas por entidad --
for i, row in df_resumen.iterrows():
    with cols[i]:
        # Logo centrado
        mostrar_logo(row["entidad"], width=70)

        # Nombre y saldo total como métrica principal
        st.metric(
            label=row["entidad"],
            value=fmt(row["saldo_total"]),
        )

        # Desglose tesorería / inversión
        color_teso = "normal" if row["saldo_tesoreria"] >= 0 else "inverse"
        color_inv  = "normal" if row["capital_invertido"] >= 0 else "inverse"

        st.caption("💰 **Tesorería**")
        st.metric(
            label="",
            value=fmt(row["saldo_tesoreria"]),
            label_visibility="collapsed",
        )
        st.caption("📈 **Inversión** *(coste)*")
        st.metric(
            label="",
            value=fmt(row["capital_invertido"]),
            label_visibility="collapsed",
        )

# -- Tarjeta TOTAL GLOBAL --
with cols[-1]:
    # Logo total (si existe iconos/TOTAL_GLOBAL.png) o emoji
    ruta_total = "iconos/TOTAL_GLOBAL.png"
    if os.path.exists(ruta_total):
        st.image(ruta_total, width=70)
    else:
        st.markdown("<div style='font-size:2.5rem;text-align:center'>💼</div>", unsafe_allow_html=True)

    st.metric(label="PATRIMONIO TOTAL", value=fmt(total_global))

    st.caption("💰 **Total Tesorería**")
    st.metric(label="", value=fmt(total_tesoreria), label_visibility="collapsed")

    st.caption("📈 **Total Inversión** *(coste)*")
    st.metric(label="", value=fmt(total_inversion), label_visibility="collapsed")

st.divider()

# ---------------------------------------------------------------------------
# 4. DESGLOSE DETALLADO DE ACTIVOS
# ---------------------------------------------------------------------------
st.subheader("📊 Distribución por Activos")

df_activos = run_query("""
    SELECT
        e.nombre                                                AS "Entidad",
        a.denominacion                                          AS "Activo",
        t.operativa                                             AS "Tipo",

        -- Unidades netas (solo inversión)
        SUM(CASE
            WHEN rt.nombre = 'Compra' THEN  t.unidades
            WHEN rt.nombre = 'Venta'  THEN -t.unidades
            ELSE 0
        END)                                                    AS "Unidades",

        -- Saldo neto en euros
        SUM(CASE
            WHEN rt.nombre IN ('Ingreso', 'Compra') THEN  t.importe_total
            WHEN rt.nombre IN ('Gasto',  'Venta')   THEN -t.importe_total
            ELSE 0
        END)                                                    AS "Saldo (€)"

    FROM transacciones t
    JOIN ref_entidad          e  ON t.entidad_id          = e.id
    JOIN activos_descripcion  a  ON t.isin                = a.isin
    JOIN ref_tipo_transaccion rt ON t.tipo_transaccion_id = rt.id
    GROUP BY e.nombre, a.denominacion, t.operativa
    HAVING SUM(CASE
            WHEN rt.nombre IN ('Ingreso', 'Compra') THEN  t.importe_total
            WHEN rt.nombre IN ('Gasto',  'Venta')   THEN -t.importe_total
            ELSE 0
        END) != 0
    ORDER BY e.nombre, t.operativa, "Saldo (€)" DESC
""")

if not df_activos.empty:
    # Etiqueta legible para el tipo
    df_activos["Tipo"] = df_activos["Tipo"].map(
        {"TESORERIA": "💰 Tesorería", "INVERSION": "📈 Inversión"}
    )

    st.dataframe(
        df_activos,
        width='stretch',
        hide_index=True,
        column_config={
            "Entidad":   st.column_config.TextColumn("🏦 Entidad"),
            "Activo":    st.column_config.TextColumn("Activo / Instrumento"),
            "Tipo":      st.column_config.TextColumn("Tipo"),
            "Unidades":  st.column_config.NumberColumn("Unidades", format="%.4f"),
            "Saldo (€)": st.column_config.NumberColumn("Saldo / Coste (€)", format="%.2f €"),
        },
    )

st.divider()

# ---------------------------------------------------------------------------
# 5. ANALÍTICA RÁPIDA
# ---------------------------------------------------------------------------
c1, c2, c3 = st.columns(3)

with c1:
    n_entidades = len(df_resumen)
    st.info(f"Tienes activos en **{n_entidades}** entidad{'es' if n_entidades != 1 else ''}.")

with c2:
    pct_teso = (total_tesoreria / total_global * 100) if total_global else 0
    st.info(f"Tu liquidez (Tesorería) es el **{pct_teso:.1f}%** del patrimonio total.")

with c3:
    pct_inv = (total_inversion / total_global * 100) if total_global else 0
    st.info(f"Tu capital invertido representa el **{pct_inv:.1f}%** del patrimonio total.")