import streamlit as st
import pandas as pd
from database import run_query, execute_non_query, cargar_referencias
import time

# --- CONFIGURACIÓN DE LA PÁGINA (Debe ser lo primero) ---
st.set_page_config(page_title="Tesorería", layout="wide")

st.title("💰 Gestión de Tesorería")
st.caption("Registro de Ingresos y Gastos (Nóminas, recibos, intereses, etc.)")

# --- 1. CARGA DE DATOS ---
# Importante: cargar_referencias debe devolver (df_activos, dict_tipos, dict_entidades, dict_estrategias)
df_activos_todos, dict_tipos, dict_entidades, dict_estrategias = cargar_referencias()

# Filtrar solo tipos de transacciones de tesorería
tipos_tesoreria = ["Ingreso", "Gasto"]

# Diccionario para búsqueda rápida de ISIN por nombre
dict_activos = dict(zip(df_activos_todos['denominacion'], df_activos_todos['isin']))

tab1, tab2 = st.tabs(["🆕 Nuevo Movimiento", "📜 Historial Tesorería"])

# --- TAB 1: NUEVO MOVIMIENTO ---
with tab1:
    if "tick_teso" not in st.session_state:
        st.session_state.tick_teso = 0
    
    # El formulario ahora vive en el flujo principal del archivo
    with st.form(f"form_tesoreria_{st.session_state.tick_teso}"):
        c1, c2, c3 = st.columns(3)
        f = c1.date_input("Fecha", value=pd.to_datetime("today"))
        ent_nombre = c2.selectbox("Entidad", list(dict_entidades.keys()))
        
        ent_id_sel = dict_entidades[ent_nombre]
        activos_entidad = df_activos_todos[df_activos_todos['entidad_id'] == ent_id_sel]['denominacion'].tolist()
        cuenta_nombre = c3.selectbox("Cuenta de Destino/Origen", activos_entidad)

        c4, c5, c6 = st.columns(3)
        t_mov = c4.selectbox("Tipo", tipos_tesoreria)
        importe_neto = c5.number_input("Importe Neto (€)", min_value=0.0, step=10.0, format="%.2f")
        estrategia = c6.selectbox("Categoría/Estrategia", list(dict_estrategias.keys()))

        c7, c8, c9 = st.columns(3)
        com = c7.number_input("Comisión (€)", min_value=0.0, step=0.5, format="%.2f")
        can = c8.number_input("Canon/Otros (€)", min_value=0.0, step=0.5, format="%.2f")
        imp = c9.number_input("Impuestos/Retención (€)", min_value=0.0, step=0.5, format="%.2f")

        obs = st.text_input("Observaciones (Ej: Nómina Marzo, Recibo Luz...)")

        gastos_totales = com + can + imp
        if t_mov == "Ingreso":
            bruto_f = importe_neto - gastos_totales
        else:
            bruto_f = importe_neto + gastos_totales

        st.markdown(f"### Total Real en Cuenta: **{bruto_f:,.2f} €**")
        
        btn_guardar = st.form_submit_button("Grabar Movimiento", type="primary")

        if btn_guardar:
            if importe_neto <= 0:
                st.error("El importe debe ser mayor a 0")
            else:
                query = """
                    INSERT INTO transacciones 
                    (fecha_operacion, entidad_id, isin, tipo_transaccion_id, unidades, precio_unitario, 
                     importe_neto, comision, canon, impuestos, importe_total, observaciones, 
                     estrategia_id, operativa)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                params = (
                    f, ent_id_sel, dict_activos[cuenta_nombre], dict_tipos[t_mov],
                    0, 0, importe_neto, com, can, imp, bruto_f, obs,
                    dict_estrategias[estrategia], 'TESORERIA'
                )
                
                try:
                    execute_non_query(query, params)
                    st.success("✅ Movimiento registrado")
                    st.session_state.tick_teso += 1
                    time.sleep(1.2)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

# --- TAB 2: HISTORIAL TESORERÍA ---
with tab2:
    st.subheader("Últimos movimientos de caja")
    historial = run_query("""
        SELECT t.fecha_operacion, e.nombre as entidad, a.denominacion as cuenta, 
               rt.nombre as tipo, t.importe_total, t.observaciones
        FROM transacciones t
        JOIN ref_entidad e ON t.entidad_id = e.id
        JOIN activos_descripcion a ON t.isin = a.isin
        JOIN ref_tipo_transaccion rt ON t.tipo_transaccion_id = rt.id
        WHERE t.operativa = 'TESORERIA'
        ORDER BY t.fecha_operacion DESC, t.id DESC
        LIMIT 50
    """)
    
    if not historial.empty:
        historial['importe_total'] = historial['importe_total'].apply(lambda x: f"{x:,.2f} €")
        st.dataframe(historial, use_container_width=True, hide_index=True)
    else:
        st.info("No hay movimientos de tesorería registrados.")