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
df_resumen = run_query("SELECT * FROM v_resumen_patrimonio")

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
 
# --- Carga de datos ---
df_inversion = run_query("""
    SELECT
        entidad     AS "Entidad",
        activo      AS "Activo",
        unidades    AS "Unidades",
        coste_total AS "Coste (€)"
    FROM v_estado_activos
    ORDER BY entidad, "Coste (€)" DESC
""")
 
df_tesoreria = run_query("""
    SELECT
        entidad AS "Entidad",
        activo  AS "Activo",
        saldo   AS "Saldo (€)"
    FROM v_saldo_tesoreria
    ORDER BY entidad, "Saldo (€)" DESC
""")
 
# --- Filtro por entidad (sobre la unión de ambas tablas) ---
entidades_disponibles = sorted(set(
    list(df_inversion["Entidad"].unique() if not df_inversion.empty else []) +
    list(df_tesoreria["Entidad"].unique() if not df_tesoreria.empty else [])
))
entidad_sel = st.multiselect(
    "🏦 Filtrar por entidad",
    options=entidades_disponibles,
    default=entidades_disponibles,
)
 
# Aplicar filtro
if entidad_sel:
    df_inv_f  = df_inversion[df_inversion["Entidad"].isin(entidad_sel)] if not df_inversion.empty else df_inversion
    df_teso_f = df_tesoreria[df_tesoreria["Entidad"].isin(entidad_sel)] if not df_tesoreria.empty else df_tesoreria
else:
    df_inv_f, df_teso_f = df_inversion, df_tesoreria
 
# --- Dos columnas ---
col_inv, col_teso = st.columns(2)
 
with col_inv:
    st.markdown("#### 📈 Inversión")
    if df_inv_f.empty:
        st.info("No hay posiciones abiertas de inversión.")
    else:
        st.dataframe(
            df_inv_f,
            width='stretch',
            hide_index=True,
            column_config={
                "Entidad":   st.column_config.TextColumn("🏦 Entidad"),
                "Activo":    st.column_config.TextColumn("Activo"),
                "Unidades":  st.column_config.NumberColumn("Unidades", format="%.4f"),
                "Coste (€)": st.column_config.NumberColumn("Coste (€)", format="%.2f €"),
            },
        )
        total_inv_f = df_inv_f["Coste (€)"].sum()
        st.caption(f"**Total coste:** {fmt(total_inv_f)}")
 
with col_teso:
    st.markdown("#### 💰 Tesorería")
    if df_teso_f.empty:
        st.info("No hay saldos de tesorería.")
    else:
        st.dataframe(
            df_teso_f,
            width='stretch',
            hide_index=True,
            column_config={
                "Entidad":   st.column_config.TextColumn("🏦 Entidad"),
                "Activo":    st.column_config.TextColumn("Cuenta"),
                "Saldo (€)": st.column_config.NumberColumn("Saldo (€)", format="%.2f €"),
            },
        )
        total_teso_f = df_teso_f["Saldo (€)"].sum()
        st.caption(f"**Total saldo:** {fmt(total_teso_f)}")
 
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