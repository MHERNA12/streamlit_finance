import streamlit as st
import time
import pandas as pd
from database import run_query, execute_non_query

st.set_page_config(page_title="Editar Activo", layout="wide")

st.title("✏️ Editar Caracterización de Activo")

# 1. Buscamos los activos existentes
activos_df = run_query("SELECT isin, denominacion FROM activos_descripcion ORDER BY denominacion")
dict_activos = dict(zip(activos_df['denominacion'], activos_df['isin']))

seleccion = st.selectbox("Seleccione el activo que desea modificar:", 
                         options=[""] + list(dict_activos.keys()),
                         help="Busque por nombre del activo")

if seleccion:
    isin_seleccionado = dict_activos[seleccion]
    
    # 2. Cargamos TODOS los datos actuales (Asegúrate de que la columna sea entidad_id)
    datos_actuales = run_query(f"SELECT * FROM activos_descripcion WHERE isin = '{isin_seleccionado}'").iloc[0]

    # 3. Cargamos opciones para los desplegables
    def get_options(table_name):
        df = run_query(f"SELECT id, nombre FROM {table_name} ORDER BY nombre")
        return dict(zip(df['nombre'], df['id']))
    
    dict_tipos_prod = get_options("ref_tipo_producto")
    dict_clases_base = get_options("ref_clase_activo")
    dict_activos_fin = get_options("ref_activo_financiero")
    dict_entidades = get_options("ref_entidad")

    def get_key_by_value(d, value):
        for k, v in d.items():
            if v == value: return k
        return None

    # --- INICIO DEL FORMULARIO ---
    with st.form("form_edicion"):
        col_id1, col_id2, col_id3, col_id4 = st.columns([2, 3, 1, 2])
        
        with col_id1:
            st.text_input("ISIN (No editable)", value=datos_actuales['isin'], disabled=True)
        with col_id2:
            denominacion = st.text_input("Denominación", value=datos_actuales['denominacion'])
        with col_id3:
            riesgo = st.number_input("Riesgo (1-7)", 1, 7, int(datos_actuales['riesgo']))
        with col_id4:
            # Precargamos la entidad que acabas de añadir con el ALTER TABLE
            nombre_entidad_actual = get_key_by_value(dict_entidades, datos_actuales['entidad_id'])
            ent_sel = st.selectbox("Entidad / Banco", options=list(dict_entidades.keys()),
                                  index=list(dict_entidades.keys()).index(nombre_entidad_actual) if nombre_entidad_actual in dict_entidades else 0)

        c1, c2, c3 = st.columns(3)
        tp = c1.selectbox("Tipo Producto", options=list(dict_tipos_prod.keys()), 
                          index=list(dict_tipos_prod.keys()).index(get_key_by_value(dict_tipos_prod, datos_actuales['tipo_producto_id'])))
        ca = c2.selectbox("Clase Activo", options=list(dict_clases_base.keys()),
                          index=list(dict_clases_base.keys()).index(get_key_by_value(dict_clases_base, datos_actuales['clase_activo_id'])))
        af = c3.selectbox("Activo Financiero", options=list(dict_activos_fin.keys()),
                          index=list(dict_activos_fin.keys()).index(get_key_by_value(dict_activos_fin, datos_actuales['tipo_activo_financiero_id'])))

        st.divider()
        col_l, col_r, col_s = st.columns([1,1,2])
        
        with col_l:
            st.subheader("📊 Clases (%)")
            rf = st.number_input("Renta Fija", 0.0, 100.0, float(datos_actuales['pct_renta_fija']))
            rv = st.number_input("Renta Variable", 0.0, 100.0, float(datos_actuales['pct_renta_variable']))
            ef = st.number_input("Efectivo", 0.0, 100.0, float(datos_actuales['pct_efectivo']))
            al = st.number_input("Alternativos", 0.0, 100.0, float(datos_actuales['pct_alternativos']))

        with col_r:
            st.subheader("🌍 Regiones (%)")
            na = st.number_input("Norteamérica", 0.0, 100.0, float(datos_actuales['pct_norteamerica']))
            eu = st.number_input("Europa Des.", 0.0, 100.0, float(datos_actuales['pct_europa_desarrollada']))
            as_ = st.number_input("Asia Des.", 0.0, 100.0, float(datos_actuales['pct_asia_desarrollada']))
            me = st.number_input("Emergentes", 0.0, 100.0, float(datos_actuales['pct_mercados_emergentes']))

        with col_s:
            st.subheader("🏗️ Sectores (%)")
            cs1, cs2, cs3 = st.columns(3)
            p_mat = cs1.number_input("Mat. Básicos", 0.0, 100.0, float(datos_actuales['pct_materiales_basicos']))
            p_con_c = cs1.number_input("Cons. Cíclico", 0.0, 100.0, float(datos_actuales['pct_consumo_ciclico']))
            p_fin = cs1.number_input("Financiero", 0.0, 100.0, float(datos_actuales['pct_servicios_financieros']))
            p_inm = cs1.number_input("Inmobiliario", 0.0, 100.0, float(datos_actuales['pct_inmobiliario']))
            
            p_com = cs2.number_input("Comunicación", 0.0, 100.0, float(datos_actuales['pct_comunicacion']))
            p_ene = cs2.number_input("Energía", 0.0, 100.0, float(datos_actuales['pct_energia']))
            p_ind = cs2.number_input("Industriales", 0.0, 100.0, float(datos_actuales['pct_industriales']))
            p_tec = cs2.number_input("Tecnología", 0.0, 100.0, float(datos_actuales['pct_tecnologia']))
            
            p_con_d = cs3.number_input("Cons. Defensivo", 0.0, 100.0, float(datos_actuales['pct_consumo_defensivo']))
            p_sal = cs3.number_input("Salud", 0.0, 100.0, float(datos_actuales['pct_salud']))
            p_uti = cs3.number_input("Utilities", 0.0, 100.0, float(datos_actuales['pct_utilities']))
            p_mon = cs3.number_input("F. Monetarios", 0.0, 100.0, float(datos_actuales['pct_fondos_monetarios']))

        obs = st.text_area("Observaciones", value=datos_actuales['observaciones'] or "")

        # BOTÓN DE ENVÍO DENTRO DEL WITH FORM
        update_btn = st.form_submit_button("📝 Actualizar Activo")

    # --- LÓGICA TRAS PULSAR EL BOTÓN ---
    if update_btn:
        s_clase = round(rf + rv + ef + al, 2)
        s_region = round(na + eu + as_ + me, 2)
        s_sector = round(p_mat + p_con_c + p_fin + p_inm + p_com + p_ene + p_ind + p_tec + p_con_d + p_sal + p_uti + p_mon, 2)

        if s_clase != 100.0 or s_region != 100.0 or s_sector != 100.0:
            st.error(f"⚠️ Error: Clases ({s_clase}%), Regiones ({s_region}%), Sectores ({s_sector}%). Deben sumar 100%.")
        else:
            # Query corregida con entidad_id
            query_update = """
                UPDATE activos_descripcion SET 
                    denominacion = :denom, riesgo = :riesgo, entidad_id = :eid, observaciones = :obs,
                    tipo_producto_id = :tp, clase_activo_id = :ca, tipo_activo_financiero_id = :af,
                    pct_renta_fija = :rf, pct_renta_variable = :rv, pct_efectivo = :ef, pct_alternativos = :al,
                    pct_norteamerica = :na, pct_europa_desarrollada = :eu, pct_asia_desarrollada = :as, pct_mercados_emergentes = :me,
                    pct_materiales_basicos = :p1, pct_consumo_ciclico = :p2, pct_servicios_financieros = :p3, 
                    pct_inmobiliario = :p4, pct_comunicacion = :p5, pct_energia = :p6, pct_industriales = :p7,
                    pct_tecnologia = :p8, pct_consumo_defensivo = :p9, pct_salud = :p10,
                    pct_utilities = :p11, pct_fondos_monetarios = :p12
                WHERE isin = :isin
            """
            params = {
                "isin": isin_seleccionado, "denom": denominacion, "riesgo": riesgo, "eid": dict_entidades[ent_sel], "obs": obs,
                "tp": dict_tipos_prod[tp], "ca": dict_clases_base[ca], "af": dict_activos_fin[af],
                "rf": rf, "rv": rv, "ef": ef, "al": al, "na": na, "eu": eu, "as": as_, "me": me,
                "p1": p_mat, "p2": p_con_c, "p3": p_fin, "p4": p_inm, "p5": p_com, "p6": p_ene, 
                "p7": p_ind, "p8": p_tec, "p9": p_con_d, "p10": p_sal, "p11": p_uti, "p12": p_mon
            }
            try:
                execute_non_query(query_update, params)
                st.success(f"✅ Activo {isin_seleccionado} actualizado correctamente.")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al actualizar: {e}")

    # --- ZONA DE BORRADO (FUERA DEL FORMULARIO) ---
    st.divider()
    with st.expander("⚠️ Zona Peligrosa: Borrar registro"):
        st.warning(f"Se eliminará permanentemente: {seleccion}")
        check_borrar = st.checkbox("Confirmo la eliminación")
        if st.button("🗑️ Eliminar Activo", type="primary", disabled=not check_borrar):
            try:
                execute_non_query("DELETE FROM activos_descripcion WHERE isin = :isin", {"isin": isin_seleccionado})
                st.success("Activo eliminado.")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"No se puede borrar: existen transacciones vinculadas a este ISIN.")