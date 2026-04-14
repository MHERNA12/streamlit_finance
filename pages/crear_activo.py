import streamlit as st
import time
from database import run_query, execute_non_query 

st.set_page_config(page_title="Configurar Activo", layout="wide")

st.title("🛡️ Caracterización Detallada de Activo")

def get_options(table_name):
    df = run_query(f"SELECT id, nombre FROM {table_name}")
    return dict(zip(df['nombre'], df['id']))

dict_tipos_prod = get_options("ref_tipo_producto")
dict_clases_base = get_options("ref_clase_activo")
dict_activos_fin = get_options("ref_activo_financiero")
dict_entidades = get_options("ref_entidad")

# Iniciamos el formulario
with st.form("form_caracterizacion", clear_on_submit=False):
    # --- DATOS BÁSICOS ---
    col_id1, col_id2, col_id3, col_id4 = st.columns([2, 3, 1,1])
    isin = col_id1.text_input("ISIN (PK)", max_chars=12).upper()
    denominacion = col_id2.text_input("Denominación del Activo")
    riesgo = col_id3.number_input("Riesgo (1-7)", 1, 7, 1)
    entidad = col_id4.selectbox("Entidad", options=sorted(dict_entidades.keys()))

    c1, c2, c3 = st.columns(3)
    tp = c1.selectbox("Tipo de Producto", options=sorted(dict_tipos_prod.keys()))
    ca = c2.selectbox("Clase de Activo Base", options=sorted(dict_clases_base.keys()))
    af = c3.selectbox("Activo Financiero", options=sorted(dict_activos_fin.keys()))

    st.divider()

    # --- CLASES Y REGIONES ---
    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("📊 Composición Clases (%)")
        sub_c1, sub_c2 = st.columns(2)
        rf = sub_c1.number_input("Renta Fija", 0.0, 100.0, 0.0, step=0.01)
        rv = sub_c2.number_input("Renta Variable", 0.0, 100.0, 0.0, step=0.01)
        ef = sub_c1.number_input("Efectivo", 0.0, 100.0, 0.0, step=0.01)
        al = sub_c2.number_input("Alternativos", 0.0, 100.0, 0.0, step=0.01)

    with col_right:
        st.subheader("🌍 Distribución Regiones (%)")
        sub_r1, sub_r2 = st.columns(2)
        na = sub_r1.number_input("Norteamérica", 0.0, 100.0, 0.0, step=0.01)
        eu = sub_r2.number_input("Europa Des.", 0.0, 100.0, 0.0, step=0.01)
        as_ = sub_r1.number_input("Asia Des.", 0.0, 100.0, 0.0, step=0.01)
        me = sub_r2.number_input("Emergentes", 0.0, 100.0, 0.0, step=0.01)

    st.divider()

    # --- SECTORES ---
    st.subheader("🏗️ Desglose por Sectores Específicos (%)")
    s1, s2, s3, s4 = st.columns(4)
    p_mat = s1.number_input("Mat. Básicos", 0.0, 100.0, 0.0, step=0.01)
    p_con_c = s1.number_input("Cons. Cíclico", 0.0, 100.0, 0.0, step=0.01)
    p_fin = s1.number_input("S. Financieros", 0.0, 100.0, 0.0, step=0.01)
    
    p_inm = s2.number_input("Inmobiliario", 0.0, 100.0, 0.0, step=0.01)
    p_com = s2.number_input("Comunicación", 0.0, 100.0, 0.0, step=0.01)
    p_ene = s2.number_input("Energía", 0.0, 100.0, 0.0, step=0.01)
    
    p_ind = s3.number_input("Industriales", 0.0, 100.0, 0.0, step=0.01)
    p_tec = s3.number_input("Tecnología", 0.0, 100.0, 0.0, step=0.01)
    p_con_d = s3.number_input("Cons. Defensivo", 0.0, 100.0, 0.0, step=0.01)
    
    p_sal = s4.number_input("Salud", 0.0, 100.0, 0.0, step=0.01)
    p_uti = s4.number_input("Utilities", 0.0, 100.0, 0.0, step=0.01)
    p_mon = s4.number_input("F. Monetarios", 0.0, 100.0, 0.0, step=0.01)

    obs = st.text_area("Observaciones")

    # BOTÓN DE GUARDADO
    submit = st.form_submit_button("💾 Guardar Caracterización")

# LÓGICA TRAS PULSAR GUARDAR (Fuera del contenedor visual del form para mostrar errores arriba o abajo)
if submit:
    # 1. Calculamos sumas
    s_clase = round(rf + rv + ef + al, 2)
    s_region = round(na + eu + as_ + me, 2)
    s_sector = round(p_mat + p_con_c + p_fin + p_inm + p_com + p_ene + p_ind + p_tec + p_con_d + p_sal + p_uti + p_mon, 2)

    # 2. Verificamos errores
    errores = []
    if s_clase != 100.0: errores.append(f"Clases suma {s_clase}%")
    if s_region != 100.0: errores.append(f"Regiones suma {s_region}%")
    if s_sector != 100.0: errores.append(f"Sectores suma {s_sector}%")
    if not isin or not denominacion: errores.append("Falta ISIN o Denominación")

    if errores:
        st.error(f"⚠️ **No se pudo guardar:** {', '.join(errores)}. Todos los grupos deben sumar exactamente 100.00%.")
    else:
        try:
            query = """
                INSERT INTO activos_descripcion (
                    isin, denominacion, riesgo, entidad_id, observaciones, tipo_producto_id, clase_activo_id, tipo_activo_financiero_id,
                    pct_renta_fija, pct_renta_variable, pct_efectivo, pct_alternativos,
                    pct_norteamerica, pct_europa_desarrollada, pct_asia_desarrollada, pct_mercados_emergentes,
                    pct_materiales_basicos, pct_consumo_ciclico, pct_servicios_financieros, pct_inmobiliario,
                    pct_comunicacion, pct_energia, pct_industriales, pct_tecnologia,
                    pct_consumo_defensivo, pct_salud, pct_utilities, pct_fondos_monetarios
                ) VALUES (
                    :isin, :denom, :riesgo, :entidad, :obs, :tp, :ca, :af, :rf, :rv, :ef, :al, :na, :eu, :as, :me,
                    :p1, :p2, :p3, :p4, :p5, :p6, :p7, :p8, :p9, :p10, :p11, :p12
                )
            """
            params = {
                "isin": isin, "denom": denominacion, "riesgo": riesgo, "entidad":dict_entidades[entidad], "obs": obs,
                "tp": dict_tipos_prod[tp], "ca": dict_clases_base[ca], "af": dict_activos_fin[af],
                "rf": rf, "rv": rv, "ef": ef, "al": al, "na": na, "eu": eu, "as": as_, "me": me,
                "p1": p_mat, "p2": p_con_c, "p3": p_fin, "p4": p_inm, "p5": p_com, "p6": p_ene,
                "p7": p_ind, "p8": p_tec, "p9": p_con_d, "p10": p_sal, "p11": p_uti, "p12": p_mon
            }
            execute_non_query(query, params)
            st.success("✅ Activo guardado con éxito.")
            time.sleep(2)
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error de base de datos: {e}")