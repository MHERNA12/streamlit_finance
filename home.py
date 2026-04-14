import streamlit as st

st.set_page_config(page_title="Finanzas Personales", layout="wide")

# DESPUÉS
pg = st.navigation({
    "": [st.Page("pages/dashboard.py",  title="🏦 Patrimonio", default=True)],
    "Movimientos": [
        st.Page("pages/tesoreria.py",  title="💰 Tesorería"),
        st.Page("pages/inversiones.py", title="📈 Inversiones"),
    ],
    "Cartera": [
        st.Page("pages/ver_descrip_activos.py", title="📋 Ver Activos"),
        st.Page("pages/crear_activo.py",        title="🛡️ Crear Activo"),
        st.Page("pages/editar_activo.py",       title="✏️ Editar Activo"),
    ],
    "Configuración": [
        st.Page("pages/ref_tablas.py", title="⚙️ Tablas de Referencia"),
    ],
})
pg.run()



