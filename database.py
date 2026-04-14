# database.py
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

@st.cache_resource
def get_engine():
    """Crea el motor de conexión utilizando los secretos de Streamlit."""
    pg = st.secrets["postgres"]
    url = f"postgresql://{pg['user']}:{pg['password']}@{pg['host']}:{pg['port']}/{pg['database']}"
    return create_engine(url)

def run_query(query, params=None):
    """Ejecuta una consulta de lectura y devuelve un DataFrame."""
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(query), conn, params=params)

def execute_non_query(query, params=None):
    """Ejecuta comandos que no devuelven datos (INSERT, UPDATE, DELETE)."""
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(query), params)

def cargar_referencias():
    """Carga todas las tablas de referencia necesarias para los selectboxes"""
    # 1. Activos (incluye entidad_id para la cascada)
    df_activos = run_query("SELECT isin, denominacion, entidad_id FROM activos_descripcion ORDER BY denominacion")
    
    # 2. Tipos de Transacción
    df_tipos = run_query("SELECT id, nombre FROM ref_tipo_transaccion")
    dict_tipos = dict(zip(df_tipos['nombre'], df_tipos['id']))
    
    # 3. Entidades
    df_entidades = run_query("SELECT id, nombre FROM ref_entidad ORDER BY nombre")
    dict_entidades = dict(zip(df_entidades['nombre'], df_entidades['id']))
    
    # 4. Estrategias / Categorías
    df_estrategias = run_query("SELECT id, nombre FROM ref_estrategia ORDER BY nombre")
    dict_estrategias = dict(zip(df_estrategias['nombre'], df_estrategias['id']))
    
    return df_activos, dict_tipos, dict_entidades, dict_estrategias