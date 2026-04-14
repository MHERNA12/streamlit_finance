import streamlit as st
from database import run_query
from styles import COLOR_CLASES, COLOR_REGIONES, COLOR_SECTORES, PLOTLY_TEMPLATE, CONFIG_BARRA_PCT
import plotly.express as px
import pandas as pd

st.set_page_config(page_title="Listado de Activos", layout="wide")

st.title("📋 Descripción de Activos")

# 1. Consulta extendida incluyendo la nueva relación con ref_entidad
query = """
    SELECT 
        a.isin AS "ISIN", 
        a.denominacion AS "Nombre",
        e.nombre AS "Entidad",
        tp.nombre AS "Tipo Producto", 
        ca.nombre AS "Clase Activo", 
        af.nombre AS "Activo Financiero",
        a.riesgo AS "Riesgo",
        a.pct_renta_fija AS "RF", a.pct_renta_variable AS "RV", a.pct_efectivo AS "Cash", a.pct_alternativos AS "Alt",
        a.pct_norteamerica AS "NA", a.pct_europa_desarrollada AS "EU", a.pct_asia_desarrollada AS "AS", a.pct_mercados_emergentes AS "EM",
        a.pct_materiales_basicos, a.pct_consumo_ciclico, a.pct_servicios_financieros, a.pct_inmobiliario,
        a.pct_comunicacion, a.pct_energia, a.pct_industriales, a.pct_tecnologia,
        a.pct_consumo_defensivo, a.pct_salud, a.pct_utilities, a.pct_fondos_monetarios,
        a.observaciones AS "Observaciones"
    FROM activos_descripcion a
    LEFT JOIN ref_entidad e ON a.entidad_id = e.id
    LEFT JOIN ref_tipo_producto tp ON a.tipo_producto_id = tp.id
    LEFT JOIN ref_clase_activo ca ON a.clase_activo_id = ca.id
    LEFT JOIN ref_activo_financiero af ON a.tipo_activo_financiero_id = af.id
    ORDER BY a.denominacion ASC
"""

try:
    df_original = run_query(query)

    if not df_original.empty:
        # --- FILTROS ---
        with st.expander("🔍 Herramientas de filtrado"):
            col_f1, col_f2, col_f3 = st.columns(3)
            busqueda = col_f1.text_input("Buscar por Nombre, ISIN o Entidad").upper()
            
            # Filtro por Entidad
            entidades_disp = sorted(df_original["Entidad"].dropna().unique().tolist())
            entidades_sel = col_f2.multiselect("Filtrar por Entidad", options=entidades_disp, default=entidades_disp)
            
            riesgo_sel = col_f3.slider("Rango de Riesgo", 1, 7, (1, 7))

        # Aplicar filtros
        df_filtrado = df_original[
            (df_original["Entidad"].isin(entidades_sel)) &
            (df_original["Riesgo"].between(riesgo_sel[0], riesgo_sel[1]))
        ]
        
        if busqueda:
            # Buscamos en Nombre, ISIN y ahora también en Entidad
            mask = (
                df_filtrado["Nombre"].str.upper().str.contains(busqueda) | 
                df_filtrado["ISIN"].str.upper().str.contains(busqueda) |
                df_filtrado["Entidad"].str.upper().str.contains(busqueda)
            )
            df_filtrado = df_filtrado[mask]

        # --- TABLA CON SELECCIÓN ---
        st.subheader("Selecciona un activo para ver su desglose:")
        selection = st.dataframe(
            df_filtrado, 
            hide_index=True, 
            width='stretch',
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "Entidad": st.column_config.TextColumn("🏦 Entidad"),
                "Riesgo": st.column_config.NumberColumn(format="%d ⚠️"),
                "RF": st.column_config.NumberColumn(format="%.1f%%"),
                "RV": st.column_config.NumberColumn(format="%.1f%%"),
                "Cash": st.column_config.NumberColumn(format="%.1f%%"),
                "Alt": st.column_config.NumberColumn(format="%.1f%%"),
                # Ocultamos columnas técnicas de sectores/regiones
                "NA": None, "EU": None, "AS": None, "EM": None,
                "pct_materiales_basicos": None, "pct_consumo_ciclico": None, "pct_servicios_financieros": None,
                "pct_inmobiliario": None, "pct_comunicacion": None, "pct_energia": None,
                "pct_industriales": None, "pct_tecnologia": None, "pct_consumo_defensivo": None,
                "pct_salud": None, "pct_utilities": None, "pct_fondos_monetarios": None
            }
        )

        # --- LÓGICA DE GRÁFICOS (Se mantiene igual, extrayendo de 'row') ---
        if len(selection.selection.rows) > 0:
            idx = selection.selection.rows[0]
            row = df_filtrado.iloc[idx]
            
            st.divider()
            st.markdown(f"### 📈 Análisis de: **{row['Nombre']}**")
            st.info(f"🏦 **Entidad:** {row['Entidad']} | 🆔 **ISIN:** {row['ISIN']} | 🛡️ **Riesgo:** {row['Riesgo']}")
            
            g1, g2, g3 = st.columns(3)

            # Gráfico 1: Clases
            with g1:
                data_clase = pd.DataFrame({
                    "Clase": ["Renta Fija", "Renta Variable", "Efectivo", "Alternativos"],
                    "Valor": [row["RF"], row["RV"], row["Cash"], row["Alt"]]
                })
                fig_clase = px.pie(data_clase, values="Valor", names="Clase", hole=0.4,
                                   title="Composición", color="Clase",
                                   color_discrete_map=COLOR_CLASES, template=PLOTLY_TEMPLATE)
                st.plotly_chart(fig_clase, width='stretch')

            # Gráfico 2: Regiones
            with g2:
                data_reg = pd.DataFrame({
                    "Región": ["Norteamérica", "Europa", "Asia", "Emergentes"],
                    "Valor": [row["NA"], row["EU"], row["AS"], row["EM"]]
                })
                fig_reg = px.bar(data_reg, x="Región", y="Valor", title="Distribución Geográfica", 
                                 color="Región", text="Valor",
                                 color_discrete_map=COLOR_REGIONES, template=PLOTLY_TEMPLATE)
                fig_reg.update_traces(**CONFIG_BARRA_PCT)
                st.plotly_chart(fig_reg, width='stretch')

            # Gráfico 3: Sectores (Sunburst)
            with g3:
                sectores_map = {
                    "Ciclico": [("Materiales Básicos", row["pct_materiales_basicos"]), ("Consumo Cíclico", row["pct_consumo_ciclico"]), 
                                ("Financiero", row["pct_servicios_financieros"]), ("Inmobiliario", row["pct_inmobiliario"])],
                    "Sensible": [("Comunicación", row["pct_comunicacion"]), ("Energía", row["pct_energia"]), 
                                 ("Industriales", row["pct_industriales"]), ("Tecnología", row["pct_tecnologia"])],
                    "Defensivo": [("Consumo Defensivo", row["pct_consumo_defensivo"]), ("Salud", row["pct_salud"]), 
                                  ("Utilities", row["pct_utilities"]), ("Fondos Monetarios", row["pct_fondos_monetarios"])]
                }
                sun_data = [[sup, sec, val] for sup, lista in sectores_map.items() for sec, val in lista if val > 0]
                df_sun = pd.DataFrame(sun_data, columns=["Supersector", "Sector", "Valor"])
                
                if not df_sun.empty:
                    fig_sun = px.sunburst(df_sun, path=["Supersector", "Sector"], values="Valor",
                                         title="Desglose Sectorial", color="Supersector",
                                         color_discrete_map=COLOR_SECTORES, template=PLOTLY_TEMPLATE)
                    fig_sun.update_traces(textinfo="label+percent entry", texttemplate="%{label}<br>%{value:.1f}%")
                    st.plotly_chart(fig_sun, width='stretch')
                else:
                    st.warning("Sin datos sectoriales")

except Exception as e:
    st.error(f"Error crítico en la visualización: {e}")