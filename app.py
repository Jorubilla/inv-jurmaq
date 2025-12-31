import streamlit as st
import pandas as pd
from datetime import datetime
import re
from streamlit_qrcode_scanner import qrcode_scanner
from io import BytesIO

# Configuración de la página
st.set_page_config(
    page_title="Inventario JURMAQ",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS minimalista
st.markdown("""
<style>
    /* Fuentes y colores minimalistas */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .main-title {
        font-size: 1.8rem;
        font-weight: 300;
        color: #1a1a1a;
        letter-spacing: -0.02em;
        margin-bottom: 0.5rem;
    }
    
    .section-divider {
        border-top: 1px solid #e0e0e0;
        margin: 2rem 0 1.5rem 0;
    }
    
    /* Inputs minimalistas */
    .stTextInput > div > div > input,
    .stSelectbox > div > div > select {
        border-radius: 0;
        border: none;
        border-bottom: 1px solid #d0d0d0;
        padding: 0.5rem 0;
        background: transparent;
    }
    
    .stTextInput > div > div > input:focus,
    .stSelectbox > div > div > select:focus {
        border-bottom: 2px solid #1a1a1a;
        box-shadow: none;
    }
    
    /* Botones minimalistas */
    .stButton > button {
        border-radius: 0;
        border: 1px solid #1a1a1a;
        background: white;
        color: #1a1a1a;
        padding: 0.6rem 2rem;
        font-weight: 400;
        letter-spacing: 0.05em;
        transition: all 0.2s;
    }
    
    .stButton > button:hover {
        background: #1a1a1a;
        color: white;
    }
    
    .stButton > button[kind="primary"] {
        background: #1a1a1a;
        color: white;
    }
    
    .stButton > button[kind="primary"]:hover {
        background: #000;
    }
    
    /* Tablas minimalistas */
    .dataframe {
        border: none !important;
    }
    
    .dataframe thead tr th {
        background: white !important;
        border-bottom: 1px solid #1a1a1a !important;
        color: #1a1a1a !important;
        font-weight: 600 !important;
        padding: 1rem 0.5rem !important;
        text-transform: uppercase;
        font-size: 0.75rem;
        letter-spacing: 0.1em;
    }
    
    .dataframe tbody tr td {
        border-bottom: 1px solid #f0f0f0 !important;
        padding: 0.8rem 0.5rem !important;
    }
    
    /* Tabs minimalistas */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
        border-bottom: 1px solid #e0e0e0;
    }
    
    .stTabs [data-baseweb="tab"] {
        padding: 0.8rem 0;
        background: transparent;
        border: none;
        color: #999;
        font-weight: 400;
    }
    
    .stTabs [aria-selected="true"] {
        color: #1a1a1a;
        border-bottom: 2px solid #1a1a1a;
    }
    
    /* Sidebar minimalista */
    section[data-testid="stSidebar"] {
        background: #fafafa;
        border-right: 1px solid #e0e0e0;
    }
    
    /* Mensajes minimalistas */
    .success-msg {
        padding: 1rem;
        background: #f5f5f5;
        border-left: 3px solid #1a1a1a;
        color: #1a1a1a;
        font-size: 0.9rem;
    }
    
    .error-msg {
        padding: 1rem;
        background: #fff5f5;
        border-left: 3px solid #dc3545;
        color: #dc3545;
        font-size: 0.9rem;
    }
    
    /* Métricas minimalistas */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 300;
        color: #1a1a1a;
    }
    
    [data-testid="stMetricLabel"] {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #666;
    }
</style>
""", unsafe_allow_html=True)

# Funciones auxiliares
def extract_run_from_qr(qr_text):
    if not qr_text:
        return None
    match = re.search(r'[&?]run=(\d+[-\d]*)', qr_text.lower())
    if match:
        return match.group(1)
    match = re.search(r'\b(\d{1,2}\.\d{3}\.\d{3}[-][0-9kK]|\d{7,8}[-][0-9kK])\b', qr_text)
    if match:
        return match.group(1)
    return None

def validate_rut(rut):
    if not rut:
        return False
    pattern = r'^\d{1,2}\.?\d{3}\.?\d{3}[-][0-9kK]$'
    return bool(re.match(pattern, str(rut)))

@st.cache_resource
def get_gsheets_connection():
    try:
        conn = st.connection("gsheets", type="gsheets")
        return conn
    except Exception as e:
        st.error(f"Error de conexión: {str(e)}")
        return None

@st.cache_data(ttl=60)
def load_inventory_data(_conn):
    try:
        df = _conn.read(worksheet="Inventario", ttl=0)
        return df
    except Exception as e:
        st.error(f"Error al cargar inventario: {str(e)}")
        return pd.DataFrame()

@st.cache_data(ttl=60)
def load_log_data(_conn):
    try:
        df = _conn.read(worksheet="Log_Movimientos", ttl=0)
        return df
    except Exception as e:
        return pd.DataFrame(columns=['Fecha', 'Hora', 'Codigo_Herramienta', 'Tipo_Movimiento', 
                                     'Ubicacion_Origen', 'Ubicacion_Destino', 'RUT_Responsable', 
                                     'Nombre_Responsable', 'Observaciones'])

def register_movement(conn, codigo, tipo_mov, ubicacion_origen, ubicacion_destino, 
                      rut_responsable, nombre_responsable, observaciones=""):
    try:
        log_df = load_log_data(conn)
        new_row = pd.DataFrame([{
            'Fecha': datetime.now().strftime('%Y-%m-%d'),
            'Hora': datetime.now().strftime('%H:%M:%S'),
            'Codigo_Herramienta': codigo,
            'Tipo_Movimiento': tipo_mov,
            'Ubicacion_Origen': ubicacion_origen,
            'Ubicacion_Destino': ubicacion_destino,
            'RUT_Responsable': rut_responsable,
            'Nombre_Responsable': nombre_responsable,
            'Observaciones': observaciones
        }])
        updated_log = pd.concat([log_df, new_row], ignore_index=True)
        conn.update(worksheet="Log_Movimientos", data=updated_log)
        return True
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return False

def update_inventory(conn, codigo, nueva_ubicacion, rut_responsable, nombre_responsable):
    try:
        inv_df = load_inventory_data(conn)
        mask = inv_df['Codigo'] == codigo
        if not mask.any():
            st.error(f"Código {codigo} no encontrado")
            return False
        inv_df.loc[mask, 'Ubicacion_Actual'] = nueva_ubicacion
        inv_df.loc[mask, 'RUT_Responsable'] = rut_responsable
        inv_df.loc[mask, 'Nombre_Responsable'] = nombre_responsable
        inv_df.loc[mask, 'Ultima_Actualizacion'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.update(worksheet="Inventario", data=inv_df)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return False

def export_to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte')
    output.seek(0)
    return output

# INTERFAZ DE USUARIO
def show_user_interface(conn):
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["Salida a Obra", "Devolución", "Traslado"])
    
    with tab1:
        st.markdown("#### Salida desde Bodega")
        st.write("")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.caption("CÓDIGO DE HERRAMIENTA")
            scan_tool = st.checkbox("Escanear QR", key="scan_tool_salida")
            if scan_tool:
                qr_tool = qrcode_scanner(key="qr_tool_salida")
                codigo_herramienta = qr_tool if qr_tool else ""
            else:
                codigo_herramienta = st.text_input("", key="manual_tool_salida", label_visibility="collapsed", placeholder="Ingrese código")
        
        with col2:
            st.caption("RUT RESPONSABLE")
            scan_rut = st.checkbox("Escanear Carnet", key="scan_rut_salida")
            if scan_rut:
                qr_rut = qrcode_scanner(key="qr_rut_salida")
                if qr_rut:
                    extracted_rut = extract_run_from_qr(qr_rut)
                    rut_responsable = extracted_rut if extracted_rut else qr_rut
                else:
                    rut_responsable = ""
            else:
                rut_responsable = st.text_input("", key="manual_rut_salida", label_visibility="collapsed", placeholder="12.345.678-9")
        
        st.write("")
        nombre_responsable = st.text_input("Nombre", key="nombre_salida", placeholder="Nombre completo")
        obra_destino = st.selectbox("Obra destino", ["Nestle Purina", "Teno", "Central"], key="obra_salida")
        observaciones_salida = st.text_area("Observaciones", key="obs_salida", height=100, placeholder="Opcional")
        
        st.write("")
        if st.button("Registrar Salida", type="primary", key="btn_salida"):
            if not codigo_herramienta:
                st.markdown('<div class="error-msg">Debe ingresar código de herramienta</div>', unsafe_allow_html=True)
            elif not rut_responsable or not validate_rut(rut_responsable):
                st.markdown('<div class="error-msg">Debe ingresar un RUT válido</div>', unsafe_allow_html=True)
            elif not nombre_responsable:
                st.markdown('<div class="error-msg">Debe ingresar nombre del responsable</div>', unsafe_allow_html=True)
            else:
                if register_movement(conn, codigo_herramienta, "Salida a Obra", "Bodega Central", 
                                    obra_destino, rut_responsable, nombre_responsable, observaciones_salida):
                    if update_inventory(conn, codigo_herramienta, obra_destino, rut_responsable, nombre_responsable):
                        st.markdown('<div class="success-msg">✓ Salida registrada correctamente</div>', unsafe_allow_html=True)
    
    with tab2:
        st.markdown("#### Devolución a Bodega")
        st.write("")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.caption("CÓDIGO DE HERRAMIENTA")
            scan_tool_dev = st.checkbox("Escanear QR", key="scan_tool_dev")
            if scan_tool_dev:
                qr_tool_dev = qrcode_scanner(key="qr_tool_dev")
                codigo_dev = qr_tool_dev if qr_tool_dev else ""
            else:
                codigo_dev = st.text_input("", key="manual_tool_dev", label_visibility="collapsed", placeholder="Ingrese código")
        
        with col2:
            st.caption("RUT RESPONSABLE")
            scan_rut_dev = st.checkbox("Escanear Carnet", key="scan_rut_dev")
            if scan_rut_dev:
                qr_rut_dev = qrcode_scanner(key="qr_rut_dev")
                if qr_rut_dev:
                    extracted_rut_dev = extract_run_from_qr(qr_rut_dev)
                    rut_dev = extracted_rut_dev if extracted_rut_dev else qr_rut_dev
                else:
                    rut_dev = ""
            else:
                rut_dev = st.text_input("", key="manual_rut_dev", label_visibility="collapsed", placeholder="12.345.678-9")
        
        st.write("")
        nombre_dev = st.text_input("Nombre", key="nombre_dev", placeholder="Nombre completo")
        obra_origen_dev = st.selectbox("Obra origen", ["Nestle Purina", "Teno", "Central"], key="obra_dev")
        observaciones_dev = st.text_area("Observaciones", key="obs_dev", height=100, placeholder="Opcional")
        
        st.write("")
        if st.button("Registrar Devolución", type="primary", key="btn_dev"):
            if not codigo_dev:
                st.markdown('<div class="error-msg">Debe ingresar código de herramienta</div>', unsafe_allow_html=True)
            elif not rut_dev or not validate_rut(rut_dev):
                st.markdown('<div class="error-msg">Debe ingresar un RUT válido</div>', unsafe_allow_html=True)
            elif not nombre_dev:
                st.markdown('<div class="error-msg">Debe ingresar nombre del responsable</div>', unsafe_allow_html=True)
            else:
                if register_movement(conn, codigo_dev, "Devolución a Bodega", obra_origen_dev,
                                    "Bodega Central", rut_dev, nombre_dev, observaciones_dev):
                    if update_inventory(conn, codigo_dev, "Bodega Central", "", ""):
                        st.markdown('<div class="success-msg">✓ Devolución registrada correctamente</div>', unsafe_allow_html=True)
    
    with tab3:
        st.markdown("#### Traslado entre Obras")
        st.write("")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.caption("CÓDIGO DE HERRAMIENTA")
            scan_tool_tras = st.checkbox("Escanear QR", key="scan_tool_tras")
            if scan_tool_tras:
                qr_tool_tras = qrcode_scanner(key="qr_tool_tras")
                codigo_tras = qr_tool_tras if qr_tool_tras else ""
            else:
                codigo_tras = st.text_input("", key="manual_tool_tras", label_visibility="collapsed", placeholder="Ingrese código")
        
        with col2:
            st.caption("RUT RESPONSABLE")
            scan_rut_tras = st.checkbox("Escanear Carnet", key="scan_rut_tras")
            if scan_rut_tras:
                qr_rut_tras = qrcode_scanner(key="qr_rut_tras")
                if qr_rut_tras:
                    extracted_rut_tras = extract_run_from_qr(qr_rut_tras)
                    rut_tras = extracted_rut_tras if extracted_rut_tras else qr_rut_tras
                else:
                    rut_tras = ""
            else:
                rut_tras = st.text_input("", key="manual_rut_tras", label_visibility="collapsed", placeholder="12.345.678-9")
        
        st.write("")
        nombre_tras = st.text_input("Nombre", key="nombre_tras", placeholder="Nombre completo")
        
        col_orig, col_dest = st.columns(2)
        with col_orig:
            obra_origen_tras = st.selectbox("Obra origen", ["Nestle Purina", "Teno", "Central"], key="obra_orig_tras")
        with col_dest:
            obra_destino_tras = st.selectbox("Obra destino", ["Nestle Purina", "Teno", "Central"], key="obra_dest_tras")
        
        observaciones_tras = st.text_area("Observaciones", key="obs_tras", height=100, placeholder="Opcional")
        
        st.write("")
        if st.button("Registrar Traslado", type="primary", key="btn_tras"):
            if not codigo_tras:
                st.markdown('<div class="error-msg">Debe ingresar código de herramienta</div>', unsafe_allow_html=True)
            elif not rut_tras or not validate_rut(rut_tras):
                st.markdown('<div class="error-msg">Debe ingresar un RUT válido</div>', unsafe_allow_html=True)
            elif not nombre_tras:
                st.markdown('<div class="error-msg">Debe ingresar nombre del responsable</div>', unsafe_allow_html=True)
            elif obra_origen_tras == obra_destino_tras:
                st.markdown('<div class="error-msg">Origen y destino deben ser diferentes</div>', unsafe_allow_html=True)
            else:
                if register_movement(conn, codigo_tras, "Traslado", obra_origen_tras,
                                    obra_destino_tras, rut_tras, nombre_tras, observaciones_tras):
                    if update_inventory(conn, codigo_tras, obra_destino_tras, rut_tras, nombre_tras):
                        st.markdown('<div class="success-msg">✓ Traslado registrado correctamente</div>', unsafe_allow_html=True)

# PANEL ADMINISTRADOR
def show_admin_interface(conn):
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    
    admin_tab1, admin_tab2, admin_tab3 = st.tabs(["Panel de Control", "Historial", "Exportar"])
    
    with admin_tab1:
        st.markdown("#### Panel de Control")
        st.write("")
        
        inv_df = load_inventory_data(conn)
        
        if not inv_df.empty:
            # Métricas
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Herramientas", len(inv_df))
            with col2:
                st.metric("En Bodega", len(inv_df[inv_df['Ubicacion_Actual'] == 'Bodega Central']))
            with col3:
                st.metric("En Obras", len(inv_df[inv_df['Ubicacion_Actual'] != 'Bodega Central']))
            with col4:
                st.metric("Nestlé Purina", len(inv_df[inv_df['Ubicacion_Actual'] == 'Nestle Purina']))
            
            st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
            
            # Filtros
            st.caption("FILTRAR POR UBICACIÓN")
            filtro_obra = st.selectbox("", ["Todas", "Bodega Central", "Nestle Purina", "Teno", "Central"], 
                                      key="filtro_obra", label_visibility="collapsed")
            
            if filtro_obra != "Todas":
                df_filtrado = inv_df[inv_df['Ubicacion_Actual'] == filtro_obra]
            else:
                df_filtrado = inv_df
            
            st.write("")
            st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
        else:
            st.info("No hay datos en el inventario")
    
    with admin_tab2:
        st.markdown("#### Historial de Movimientos")
        st.write("")
        
        log_df = load_log_data(conn)
        
        if not log_df.empty:
            st.caption("BUSCAR POR HERRAMIENTA")
            buscar_codigo = st.text_input("", key="buscar_codigo", label_visibility="collapsed", 
                                         placeholder="Ingrese código")
            
            if buscar_codigo:
                historial = log_df[log_df['Codigo_Herramienta'] == buscar_codigo].sort_values('Fecha', ascending=False)
                if not historial.empty:
                    st.write("")
                    st.markdown(f"**Hoja de vida: {buscar_codigo}**")
                    st.dataframe(historial, use_container_width=True, hide_index=True)
                else:
                    st.info("No se encontraron movimientos para este código")
            else:
                st.write("")
                st.dataframe(log_df.sort_values('Fecha', ascending=False).head(50), 
                           use_container_width=True, hide_index=True)
        else:
            st.info("No hay movimientos registrados")
    
    with admin_tab3:
        st.markdown("#### Exportar Datos")
        st.write("")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.caption("INVENTARIO ACTUAL")
            inv_df = load_inventory_data(conn)
            if not inv_df.empty:
                excel_inv = export_to_excel(inv_df)
                st.download_button(
                    label="Descargar Inventario",
                    data=excel_inv,
                    file_name=f"inventario_jurmaq_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        
        with col2:
            st.caption("HISTORIAL DE MOVIMIENTOS")
            log_df = load_log_data(conn)
            if not log_df.empty:
                excel_log = export_to_excel(log_df)
                st.download_button(
                    label="Descargar Historial",
                    data=excel_log,
                    file_name=f"historial_jurmaq_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

# MAIN
def main():
    conn = get_gsheets_connection()
    
    if conn is None:
        st.stop()
    
    # Header minimalista
    st.markdown('<div class="main-title">JURMAQ — Inventario</div>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.write("")
        st.write("")
        st.markdown("### Configuración")
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        
        admin_mode = st.checkbox("Modo Administrador")
        
        if admin_mode:
            password = st.text_input("Contraseña", type="password")
            
            if password == st.secrets.get("admin_password", "admin123"):
                st.markdown('<div class="success-msg">Acceso concedido</div>', unsafe_allow_html=True)
                show_admin_panel = True
            elif password:
                st.markdown('<div class="error-msg">Contraseña incorrecta</div>', unsafe_allow_html=True)
                show_admin_panel = False
            else:
                show_admin_panel = False
        else:
            show_admin_panel = False
        
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.caption(f"Fecha: {datetime.now().strftime('%d/%m/%Y')}")
    
    # Contenido
    if show_admin_panel:
        show_admin_interface(conn)
    else:
        show_user_interface(conn)

if __name__ == "__main__":
    main()
