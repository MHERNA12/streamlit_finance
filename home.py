import streamlit as st
import pandas as pd
from database import run_query
import os
from styles import MONEDA_CONFIG, mostrar_logo_entidad, mostrar_logo_total

st.set_page_config(page_title="Dashboard Patrimonio", layout="wide")

# --- 1. CABECERA ---
st.title("🏦 Estado Global del Patrimonio")
st.write(f"Última actualización: {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')}")

# --- 2. RESUMEN POR ENTIDAD (Métricas con Desglose) ---
# Traemos el total, el efectivo y la inversión por cada entidad
df_resumen = run_query("""
    SELECT 
        entidad, 
        SUM(coste_total) as total,
        -- Consideramos Efectivo todo lo que tenga 0 unidades (cuentas corrientes)
        SUM(CASE WHEN unidades = 0 THEN coste_total ELSE 0 END) as efectivo,
        -- Consideramos Inversión lo que sí tiene unidades (acciones, participaciones, etc.)
        SUM(CASE WHEN unidades <> 0 THEN coste_total ELSE 0 END) as inversion
    FROM v_estado_activos 
    GROUP BY entidad 
    ORDER BY total DESC
""")

if not df_resumen.empty:
    suma_total = df_resumen['total'].sum()
    efectivo_global = df_resumen['efectivo'].sum()
    inversion_global = df_resumen['inversion'].sum()
    
    # Formateador rápido (puedes moverlo a styles.py si prefieres)
    def fmt(n): return f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    cols = st.columns(len(df_resumen) + 1)
    
    # 3. Bucle para entidades
    for i, row in df_resumen.iterrows():
        with cols[i]:
            mostrar_logo_entidad(row['entidad'], width=60)
            st.metric(label=row['entidad'], value=f"{fmt(row['total'])} €")
            
            # Desglose pequeño debajo de la métrica
            st.caption(f"🏦 **Efectivo:** {fmt(row['efectivo'])} €")
            st.caption(f"📈 **Inversión:** {fmt(row['inversion'])} €")

    # 4. Columna del TOTAL GLOBAL
    with cols[-1]:
        mostrar_logo_total(width=60)
        st.metric(label="PATRIMONIO TOTAL", value=f"{fmt(suma_total)} €")
        
        # Desglose del total global
        st.caption(f"💰 **Total Cash:** {fmt(efectivo_global)} €")
        st.caption(f"🚀 **Total Inv.:** {fmt(inversion_global)} €")

    st.divider()
    # ... resto del código (Tabla de activos y analítica)

    # --- 3. DESGLOSE DETALLADO DE ACTIVOS ---
    st.subheader("📊 Distribución por Activos")
    
    df_activos = run_query("""
        SELECT entidad, activo, unidades, coste_total 
        FROM v_estado_activos 
        ORDER BY entidad ASC, coste_total DESC
    """)

    # Formateamos el DataFrame para que sea legible
    st.dataframe(
        df_activos,
        use_container_width=True,
        hide_index=True,
        column_config={
            "entidad": st.column_config.TextColumn("Entidad"),
            "activo": st.column_config.TextColumn("Activo / Instrumento"),
            "unidades": st.column_config.NumberColumn("Unidades", format="%.4f"),
            "coste_total": st.column_config.NumberColumn("Valor Coste (€)", format="%.2f €")
        }
    )

    # --- 4. ANALÍTICA RÁPIDA (Opcional) ---
    c1, c2 = st.columns(2)
    with c1:
        st.info(f"Tienes activos distribuidos en **{len(df_resumen)}** entidades diferentes.")
    with c2:
        # Calcular peso del efectivo vs inversión
        efectivo_total = df_activos[df_activos['activo'] == 'Efectivo']['coste_total'].sum()
        pct_cash = (efectivo_total / suma_total) * 100 if suma_total > 0 else 0
        st.info(f"Tu nivel de liquidez (Efectivo) es del **{pct_cash:.2f}%**.")

else:
    st.warning("No hay datos suficientes para generar el dashboard. Registra transacciones en la sección correspondiente.")

