# styles.py
import os
import streamlit as st

# --- COLORES PARA CLASES DE ACTIVOS ---
COLOR_CLASES = {
    "Renta Variable": "#FF4B4B", # Rojo
    "Renta Fija": "#00CC96",    # Verde
    "Efectivo": "#636EFA",      # Azul
    "Alternativos": "#FECB52"   # Dorado
}

# --- COLORES PARA REGIONES ---
COLOR_REGIONES = {
    "Norteamérica": "#1F77B4",
    "Europa": "#9467BD",
    "Asia": "#FF7F0E",
    "Emergentes": "#8C564B"
}

# --- COLORES PARA SUPERSECTORES (SUNBURST) ---
COLOR_SECTORES = {
    "Ciclico":  "#FECB52",
    "Sensible": "#FF4B4B",
    "Defensivo": "#00CC96"
}
# --- FORMATOS DE TEXTO ---
FORMATO_PCT = "%{text:.1f}%"  # Un decimal y símbolo %
FORMATO_MONEDA = "%{text:.2f}€" # Para cuando hagamos gráficos de dinero

# --- CONFIGURACIÓN DE COLUMNAS PARA DATAFRAMES ---
# Definimos el formato con separador de miles y símbolo de euro
MONEDA_CONFIG = {
    "format": "%.2f €", 
    "help": "Importe en euros "
}

FORMATO_EURO = "%.2f €" # Para usar en st.metric o textos
# --- CONFIGURACIÓN ESTÁNDAR DE TRACES ---
# Esto centraliza la posición del texto
CONFIG_BARRA_PCT = {
    "texttemplate": FORMATO_PCT,
    "textposition": "outside"
}
# --- CONFIGURACIÓN DE GRÁFICOS ---
# Puedes guardar aquí configuraciones comunes de Plotly para que todos los
# gráficos tengan el mismo aspecto (fuentes, márgenes, etc.)
PLOTLY_TEMPLATE = "plotly_white"

def mostrar_logo_entidad(nombre_entidad, width=80):
    """
    Busca el logo de una entidad en la carpeta iconos y lo renderiza.
    Si no existe, muestra un emoji genérico.
    """
    # Intentamos varias extensiones por si acaso
    ruta_base = f"iconos/{nombre_entidad}"
    img_path = None
    
    for ext in [".png", ".jpg", ".jpeg"]:
        if os.path.exists(ruta_base + ext):
            img_path = ruta_base + ext
            break
            
    if img_path:
        return st.image(img_path, width=width)
    else:
        return st.write("🏦")

def mostrar_logo_total(width=80):
    """Renderiza el logo del Total Global"""
    ruta = "iconos/TOTAL_GLOBAL.png"
    if os.path.exists(ruta):
        st.image(ruta, width=width)
    else:
        st.write("💰")