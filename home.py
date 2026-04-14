import streamlit as st
import pandas as pd
from database import run_query
import os
from styles import MONEDA_CONFIG, mostrar_logo_entidad, mostrar_logo_total

st.set_page_config(page_title="Dashboard Patrimonio", layout="wide")

# --- 1. CABECERA ---
st.title("🏦 Estado Global del Patrimonio")
st.write(f"Última actualización: {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')}")



