import streamlit as st
import pandas as pd
from datetime import datetime
import barcode
from barcode.writer import ImageWriter
from io import BytesIO
from PIL import Image
import re
from streamlit_gsheets import GSheetsConnection
import numpy as np

st.set_page_config(
    page_title="Inventario JURMAQ",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
.main-header {
    font-size: 2.5rem;
    font-weight: bold;
    color: #1f4788;
    text-align: center;
    padding: 1rem;
    background: linear-gradient(90deg, #1f4788 0%, #2563eb 100%);
    color: white;
    border-radius: 10px;
    margin-bottom: 2rem;
}
.stButton > button {
    width: 100%;
    background-color: #1f4788;
    color: white;
    font-weight: bold;
    border-radius: 8px;
    padding: 0.75rem;
    font-size: 1.1rem;
}
.stButton > button:hover {
    background-color: #2563eb;
    border-color: #2563eb;
}
.success-box {
    padding: 1rem;
    background-color: #d4edda;
    border: 1px solid #c3e6cb;
    border-radius: 8px;
    color: #155724;
    margin: 1rem 0;
}
.info-box {
    padding: 1rem;
    background-color: #d1ecf1;
    border: 1px solid #bee5eb;
    border-radius: 8px;
    color: #0c5460;
    margin: 1rem 0;
}
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_sheets_connection():
    return st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=60)
def load_data():
    try:
        conn = get_sheets_connection()
        df = conn.read(worksheet="Inventario", usecols=list(range(8)))
        return df.dropna(how="all")
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        return pd.DataFrame(columns=["Codigo", "Nombre", "Categoria", "Ubicacion", "Estado", "Responsable", "FechaUltimoMovimiento", "RUTResponsable"])

def save_to_sheets(df, worksheet="Inventario"):
    try:
        conn = get_sheets_connection()
        conn.update(worksheet=worksheet, data=df)
        return True
    except Exception as e:
        st.error(f"Error al guardar: {e}")
        return False

def log_movement(codigo, accion, ubicacion, responsable, rut):
    try:
        conn = get_sheets_connection()
        try:
            historial = conn.read(worksheet="Historial", usecols=list(range(6)), ttl=5)
        except:
            historial = pd.DataFrame(columns=["Fecha", "Codigo", "Accion", "Ubicacion", "Responsable", "RUT"])
        
        nuevo_registro = pd.DataFrame([{
            "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Codigo": codigo,
            "Accion": accion,
            "Ubicacion": ubicacion,
            "Responsable": responsable,
            "RUT": rut
        }])
        historial = pd.concat([historial, nuevo_registro], ignore_index=True)
        conn.update(worksheet="Historial", data=historial)
        return True
    except Exception as e:
        st.error(f"Error al registrar movimiento: {e}")
        return False
        
def generar_codigo_barra_imagen(valor):
    buffer = BytesIO()
    barcode_obj = barcode.get_code128(valor, writer=ImageWriter())
    barcode_obj.write(buffer, options={"module_width": 0.3, "module_height": 15.0, "font_size": 12, "text_distance": 5, "quiet_zone": 6.5})
    buffer.seek(0)
    return buffer.getvalue()

def generar_codigo_unico(df_inv):
    if df_inv.empty:
        return "JUR-000001"
    existentes = df_inv["Codigo"].tolist()
    nums = []
    for c in existentes:
        try:
            nums.append(int(c.split("-")[-1]))
        except:
            continue
    nxt = max(nums) + 1 if nums else 1
    return f"JUR-{nxt:06d}"

def extraer_rut_desde_qr(qrtext):
    if "&run=" in qrtext:
        parte = qrtext.split("&run=")[1]
        rut = parte.split("&")[0]
        return rut.strip()
    return None

def formatar_rut(rut):
    rut = re.sub(r"[^0-9Kk]", "", str(rut))
    if len(rut) < 2:
        return rut
    return f"{rut[:-1]}-{rut[-1]}"

st.markdown('<div class="main-header">🔨 SISTEMA INVENTARIO JURMAQ</div>', unsafe_allow_html=True)

st.sidebar.title("Menu de navegacion")
modulo = st.sidebar.radio(
    "Seleccione módulo",
    ["Registrar Herramienta", "Operaciones de Terreno", "Modo Administrador"],
    label_visibility="collapsed"
)

if modulo == "Registrar Herramienta":
    st.header("Registrar Nueva Herramienta")
    
    col1, col2 = st.columns(2)
    with col1:
        nombre = st.text_input("Nombre de la Herramienta", placeholder="Ej. Taladro Bosch")
        categoria = st.selectbox(
            "Categoría",
            ["Herramientas Eléctricas", "Herramientas Manuales", "Equipos de Medicin", "Maquinaria Pesada", "EPP", "Otro"]
        )
    with col2:
        ubicacion = st.selectbox(
            "Ubicación Inicial",
            ["Bodega Central", "Obra Nestle", "Obra Teno", "Obra Central", "Otro"]
        )
        if ubicacion == "Otro":
            ubicacion = st.text_input("Especifique ubicación")
    
    if st.button("Registrar y Generar Código de Barras", use_container_width=True):
        if nombre:
            df = load_data()
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            codigo = generar_codigo_unico(df)
            barcode_img = generar_codigo_barra_imagen(codigo)
            
            if barcode_img:
                st.success("¡Herramienta registrada exitosamente!")
                st.markdown(f'<div class="success-box"><b>Código generado: {codigo}</b></div>', unsafe_allow_html=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    image = Image.open(BytesIO(barcode_img))
                    st.image(image, caption=f"Código de Barras: {codigo}", use_container_width=True)
                with col2:
                    st.download_button(
                        label="Descargar PNG",
                        data=barcode_img,
                        file_name=f"{codigo}.png",
                        mime="image/png",
                        use_container_width=True
                    )
                
                nuevo_registro = pd.DataFrame([{
                    "Codigo": codigo,
                    "Nombre": nombre,
                    "Categoria": categoria,
                    "Ubicacion": ubicacion,
                    "Estado": "Disponible",
                    "Responsable": "NA",
                    "FechaUltimoMovimiento": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "RUTResponsable": "NA"
                }])
                
                if df.empty:
                    df = nuevo_registro
                else:
                    df = pd.concat([df, nuevo_registro], ignore_index=True)
                
                if save_to_sheets(df):
                    log_movement(codigo, "Registro Inicial", ubicacion, "Sistema", "NA")
                    st.balloons()
                else:
                    st.error("Error al guardar la herramienta")
        else:
            st.error("Por favor ingrese el nombre de la herramienta")
            
elif modulo == "Operaciones de Terreno":
    st.header("Operaciones de Terreno")
    
    tab1, tab2 = st.tabs(["Buscar por Codigo", "Escanear QR Carnet"])
    
    with tab1:
        st.subheader("Identificar Herramienta")
        codigo_buscar = st.text_input("Ingrese o escanee codigo de barras", placeholder="JUR20250101120000")
        
        if codigo_buscar:
            df = load_data()
            herramienta = df[df["Codigo"] == codigo_buscar]
            
            if not herramienta.empty:
                st.markdown('<div class="info-box">', unsafe_allow_html=True)
                st.markdown(f"**Herramienta:** {herramienta.iloc[0]['Nombre']}")
                st.markdown(f"**Categoria:** {herramienta.iloc[0]['Categoria']}")
                st.markdown(f"**Ubicacion Actual:** {herramienta.iloc[0]['Ubicacion']}")
                st.markdown(f"**Estado:** {herramienta.iloc[0]['Estado']}")
                st.markdown(f"**Responsable:** {herramienta.iloc[0]['Responsable']}")
                st.markdown('</div>', unsafe_allow_html=True)
                
                st.divider()
                st.subheader("Identificar Persona Responsable")
                col1, col2 = st.columns(2)
                with col1:
                    rut_manual = st.text_input("Ingrese RUT", placeholder="12345678-9")
                with col2:
                    nombre_responsable = st.text_input("Nombre Completo", placeholder="Juan Perez")
                
                st.divider()
                st.subheader("Registrar Movimiento")
                
                col1, col2, col3 = st.columns(3)
                nueva_ubicacion = st.selectbox(
                    "Nueva Ubicacion (Obra)",
                    ["Bodega Central", "Obra Nestle", "Obra Teno", "Obra Central", "Otro"],
                    key=f"destino_{codigo_buscar}"
                )
                if nueva_ubicacion == "Otro":
                    nueva_ubicacion = st.text_input("Especifique ubicacion")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("Salida a Obra", use_container_width=True):
                        if rut_manual and nombre_responsable:
                            df.loc[df["Codigo"] == codigo_buscar, "Estado"] = "En Uso"
                            df.loc[df["Codigo"] == codigo_buscar, "Ubicacion"] = nueva_ubicacion
                            df.loc[df["Codigo"] == codigo_buscar, "Responsable"] = nombre_responsable
                            df.loc[df["Codigo"] == codigo_buscar, "RUTResponsable"] = formatar_rut(rut_manual)
                            df.loc[df["Codigo"] == codigo_buscar, "FechaUltimoMovimiento"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            
                            if save_to_sheets(df):
                                log_movement(codigo_buscar, "Salida a Obra", nueva_ubicacion, nombre_responsable, formatar_rut(rut_manual))
                                st.success(f"Herramienta enviada a {nueva_ubicacion}")
                                st.rerun()
                        else:
                            st.error("Complete RUT y Nombre")
                
                with col2:
                    if st.button("Devolucion", use_container_width=True):
                        df.loc[df["Codigo"] == codigo_buscar, "Estado"] = "Disponible"
                        df.loc[df["Codigo"] == codigo_buscar, "Ubicacion"] = "Bodega Central"
                        df.loc[df["Codigo"] == codigo_buscar, "Responsable"] = "NA"
                        df.loc[df["Codigo"] == codigo_buscar, "RUTResponsable"] = "NA"
                        df.loc[df["Codigo"] == codigo_buscar, "FechaUltimoMovimiento"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        if save_to_sheets(df):
                            log_movement(codigo_buscar, "Devolucion", "Bodega Central", nombre_responsable if nombre_responsable else "NA", formatar_rut(rut_manual) if rut_manual else "NA")
                            st.success("Herramienta devuelta a bodega")
                            st.rerun()
                
                with col3:
                    if st.button("Traslado", use_container_width=True):
                        if rut_manual and nombre_responsable:
                            df.loc[df["Codigo"] == codigo_buscar, "Ubicacion"] = nueva_ubicacion
                            df.loc[df["Codigo"] == codigo_buscar, "Responsable"] = nombre_responsable
                            df.loc[df["Codigo"] == codigo_buscar, "RUTResponsable"] = formatar_rut(rut_manual)
                            df.loc[df["Codigo"] == codigo_buscar, "FechaUltimoMovimiento"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            
                            if save_to_sheets(df):
                                log_movement(codigo_buscar, "Traslado", nueva_ubicacion, nombre_responsable, formatar_rut(rut_manual))
                                st.success(f"Herramienta trasladada a {nueva_ubicacion}")
                                st.rerun()
                        else:
                            st.error("Complete RUT y Nombre")
            else:
                st.error("Codigo no encontrado en el inventario")
    
    with tab2:
        st.subheader("Escanear QR del Carnet")
        st.info("Escanee el codigo QR del reverso del carnet de identidad chileno")
        qrtext = st.text_area("Pegue el texto del QR escaneado", placeholder="Ejemplo ...&run=12345678...", height=100)
        
        if st.button("Extraer RUT"):
            if qrtext:
                rut = extraer_rut_desde_qr(qrtext)
                if rut:
                    st.success(f"RUT extraido: {formatar_rut(rut)}")
                    st.code(formatar_rut(rut), language=None)
                else:
                    st.error("No se pudo extraer el RUT. Verifique el formato del QR")
            else:
                st.warning("Por favor pegue el texto del QR")

elif modulo == "Modo Administrador":
    st.header("Modo Administrador")
    
    if "admin_logged" not in st.session_state:
        st.session_state.admin_logged = False
    
    if not st.session_state.admin_logged:
        password = st.text_input("Contrasena de Administrador", type="password")
        if st.button("Ingresar"):
            admin_pass = st.secrets.get("admin_password", "admin123")
            if password == admin_pass:
                st.session_state.admin_logged = True
                st.rerun()
            else:
                st.error("Contrasena incorrecta")
    else:
        tab1, tab2, tab3 = st.tabs(["Stock por Obra", "Historial Maestro", "Dashboard"])
        
        with tab1:
            st.subheader("Stock por Obra")
            df = load_data()
            if not df.empty:
                obra_filtro = st.selectbox(
                    "Filtrar por ubicacion",
                    ["Todas"] + sorted(df["Ubicacion"].unique().tolist())
                )
                if obra_filtro != "Todas":
                    df_filtrado = df[df["Ubicacion"] == obra_filtro]
                else:
                    df_filtrado = df
                
                st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Herramientas", len(df_filtrado))
                with col2:
                    disponibles = len(df_filtrado[df_filtrado["Estado"] == "Disponible"])
                    st.metric("Disponibles", disponibles)
                with col3:
                    enuso = len(df_filtrado[df_filtrado["Estado"] != "Disponible"])
                    st.metric("En Uso", enuso)
            else:
                st.info("No hay datos de inventario")
        
        with tab2:
            st.subheader("Historial de Trazabilidad")
            codigo_buscar = st.text_input("Buscar por codigo", placeholder="JUR20250101120000")
            
            if codigo_buscar:
                try:
                    conn = get_sheets_connection()
                    historial = conn.read(worksheet="Historial", usecols=list(range(6)), ttl=5)
                    historial_filtrado = historial[historial["Codigo"] == codigo_buscar]
                    
                    if not historial_filtrado.empty:
                        st.dataframe(
                            historial_filtrado.sort_values("Fecha", ascending=False),
                            use_container_width=True,
                            hide_index=True
                        )
                    else:
                        st.warning("No se encontro historial para este codigo")
                except Exception as e:
                    st.error(f"Error al cargar historial: {e}")
        
        with tab3:
            st.subheader("Dashboard General")
            df = load_data()
            if not df.empty:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Distribucion por Ubicacion**")
                    ubicacion_counts = df["Ubicacion"].value_counts()
                    st.bar_chart(ubicacion_counts)
                with col2:
                    st.markdown("**Distribucion por Categoria**")
                    categoria_counts = df["Categoria"].value_counts()
                    st.bar_chart(categoria_counts)
                
                st.markdown("**Estado del Inventario**")
                estado_counts = df["Estado"].value_counts()
                st.bar_chart(estado_counts)
            else:
                st.info("No hay datos para mostrar")
        
        if st.sidebar.button("Cerrar Sesion"):
            st.session_state.admin_logged = False
            st.rerun()

st.sidebar.divider()
st.sidebar.markdown("**Constructora JURMAQ**")
st.sidebar.caption("2025 - Sistema de Inventario v1.0")
