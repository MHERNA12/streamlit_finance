import streamlit as st
from database import get_engine, run_query # Importación limpia
from sqlalchemy import text

# Configuración de la página
st.set_page_config(page_title="Tablas de Referencia", layout="wide")
st.title("⚙️ Configuración de Tablas de Referencia")


# Listado de tablas de referencia según el documento
tablas = {
    "Entidades": "ref_entidad",
    "Tipos de Producto": "ref_tipo_producto",
    "Posiciones": "ref_posicion",
    "Clases de Activo": "ref_clase_activo",
    "Activo Financiero": "ref_activo_financiero",
    "Tipos de Transacción": "ref_tipo_transaccion",
    "Estrategias": "ref_estrategia",
    "Sectores Detallados": "ref_sector",
    "Sectores económicos": "ref_macro_sector",
    "Regiones": "ref_region",
    "Origen Ingreso-Gasto":"ref_origen_transaccion"
}

# Selector en la interfaz
tabla_seleccionada = st.selectbox("Selecciona la tabla que deseas visualizar:", list(tablas.keys()))

if tabla_seleccionada:
    nombre_tabla = tablas[tabla_seleccionada]
    
    try:
        # Usamos SQLAlchemy para leer
        df = run_query(f"SELECT * FROM {nombre_tabla}")
        
        st.subheader(f"Datos en: {nombre_tabla}")
        st.dataframe(df, width='content', hide_index=True)
        
    except Exception as e:
        st.error(f"Error al conectar con la base de datos: {e}")

# Sección para insertar (Uso de transacciones con SQLAlchemy)
with st.expander(f"Añadir nuevo registro a {tabla_seleccionada}"):
    nuevo_nombre = st.text_input("Nombre del nuevo elemento:")
    
    # Campo extra solo para ref_origen_transaccion
    nuevo_tipo = None
    if tablas[tabla_seleccionada] == "ref_origen_transaccion":
        nuevo_tipo = st.selectbox("Tipo", ["INGRESO", "GASTO"])
    
    if st.button("Guardar"):
        if nuevo_nombre:
            try:
                engine = get_engine()
                with engine.begin() as conn:
                    if tablas[tabla_seleccionada] == "ref_origen_transaccion":
                        query = text("INSERT INTO ref_origen_transaccion (nombre, tipo) VALUES (:val, :tipo)")
                        conn.execute(query, {"val": nuevo_nombre, "tipo": nuevo_tipo})
                    else:
                        query = text(f"INSERT INTO {tablas[tabla_seleccionada]} (nombre) VALUES (:val)")
                        conn.execute(query, {"val": nuevo_nombre})
                st.success(f"'{nuevo_nombre}' añadido correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")