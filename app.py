import streamlit as st
from supabase import create_client
import os
import base64
import io
import urllib.parse
import pandas as pd
import altair as alt
from dotenv import load_dotenv
from fpdf import FPDF
from datetime import datetime
import streamlit.components.v1 as components

# =====================================================================
# 1. CONFIGURACIÓN INICIAL DE PÁGINA Y BD
# =====================================================================
st.set_page_config(page_title="Boomerang Visión", layout="wide", page_icon="👓", initial_sidebar_state="expanded")

# Inyección de JS agresiva para intentar forzar el calendario a Español
components.html("""
    <script>
        const doc = window.parent.document;
        doc.documentElement.lang = 'es-CO';
        Object.defineProperty(window.parent.navigator, 'language', {value: 'es-CO', configurable: true});
        Object.defineProperty(window.parent.navigator, 'languages', {value: ['es-CO', 'es'], configurable: true});
    </script>
""", height=0, width=0)

st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        .block-container {padding-top: 2rem; padding-bottom: 2rem;}
        
        /* =========================================================
           ESTILOS PULIDOS: BORDES FINOS Y SIN ARTEFACTOS
           ========================================================= */

        /* 1. CONTENEDOR EXTERNO - Borde delgado (1px) y fondo gris claro */
        div[data-testid="stTextInput"] > div:last-child,
        div[data-testid="stNumberInput"] > div:last-child,
        div[data-testid="stDateInput"] > div:last-child,
        div[data-testid="stSelectbox"] > div:last-child,
        div[data-testid="stTextArea"] > div:last-child {
            background-color: #f1f5f9 !important; 
            border: 1px solid #cbd5e1 !important; 
            border-radius: 6px !important;
            overflow: hidden !important; 
        }

        /* 2. EFECTO FOCO/SELECCIÓN (ROJO) - Mismo grosor exacto */
        div[data-testid="stTextInput"] > div:last-child:focus-within,
        div[data-testid="stNumberInput"] > div:last-child:focus-within,
        div[data-testid="stDateInput"] > div:last-child:focus-within,
        div[data-testid="stSelectbox"] > div:last-child:focus-within,
        div[data-testid="stTextArea"] > div:last-child:focus-within {
            background-color: #ffebee !important; 
            border: 1px solid #E61B23 !important; 
            box-shadow: inset 0 0 0 1px #E61B23 !important; /* Inset shadow elimina puntos externos */
        }

        /* 3. LIMPIEZA DE ARTEFACTOS INTERNOS (Líneas grises inferiores y puntos) */
        div[data-baseweb="input"],
        div[data-baseweb="base-input"],
        div[data-baseweb="select"] > div {
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
        }

        /* Ocultar agresivamente pseudo-elementos (elimina la barra gris abajo de los números) */
        div[data-baseweb="base-input"]::after,
        div[data-baseweb="base-input"]::before,
        div[data-baseweb="input"]::after,
        div[data-baseweb="input"]::before {
            display: none !important;
            content: none !important;
            border: none !important;
            background: transparent !important;
        }

        /* Asegurar que las esquinas internas sean transparentes (elimina el punto) */
        div[data-testid="stTextInput"] div[data-baseweb="base-input"] > div,
        div[data-testid="stNumberInput"] div[data-baseweb="base-input"] > div {
            border: none !important;
            box-shadow: none !important;
            outline: none !important;
            background: transparent !important;
        }

        /* 4. TEXTO OSCURO PARA CONTRASTE */
        div[data-testid="stTextInput"] input, 
        div[data-testid="stNumberInput"] input, 
        div[data-testid="stDateInput"] input,
        div[data-testid="stTextArea"] textarea {
            background-color: transparent !important;
            color: #0f172a !important; 
            border: none !important;
            box-shadow: none !important;
            padding-left: 12px !important;
            outline: none !important;
        }

        div[data-testid="stSelectbox"] div[data-baseweb="select"] {
            color: #0f172a !important;
        }

        /* BOTONES DEL NUMBER INPUT (+ / -) */
        div[data-baseweb="spinbutton"] {
            background-color: transparent !important;
            border: none !important;
        }
        
        /* ESTILO PARA ST.PILLS */
        div[data-testid="stPills"] button {
            background-color: #f1f5f9 !important;
            border: 1px solid #cbd5e1 !important;
            color: #475569 !important;
            border-radius: 6px !important;
            font-weight: 500 !important;
        }
        div[data-testid="stPills"] button[aria-selected="true"] {
            background-color: #ffebee !important;
            border: 1px solid #E61B23 !important;
            color: #E61B23 !important;
        }
    </style>
""", unsafe_allow_html=True)

load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

@st.cache_resource
def init_connection():
    return create_client(url, key)

supabase = init_connection()

# =====================================================================
# 2. SISTEMA DE AUTENTICACIÓN Y ROLES LOCALES
# =====================================================================
USUARIOS_PERMITIDOS = {
    "1022396649": {"pass": "mateo", "nombre": "Dr. Mateo F.", "rol": "admin", "id": "1022396649"},
    "1024585129": {"pass": "juan", "nombre": "Dr. Juan Pablo", "rol": "admin", "id": "1024585129"},
    "39667008": {"pass": "rosa", "nombre": "Rosa (Asesora)", "rol": "admin", "id": "39667008"},
    "79203712": {"pass": "nelson", "nombre": "Nelson (Asesor)", "rol": "admin", "id": "79203712"},
    "asesor": {"pass": "1234", "nombre": "Asesor Invitado", "rol": "asesor_limitado", "id": "asesor"},
    "doctor": {"pass": "1234", "nombre": "Doctor Invitado", "rol": "doctor_limitado", "id": "doctor"}
}

def get_image_base64(path):
    if os.path.exists(path):
        with open(path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    return None

if "user_info" not in st.session_state: st.session_state.user_info = None

if st.session_state.user_info is None and "auth_token" in st.query_params:
    try:
        token = st.query_params["auth_token"]
        decoded_token = base64.b64decode(token).decode("utf-8")
        token_user_id, token_date = decoded_token.split("||")
        if token_date == datetime.now().strftime("%Y-%m-%d") and token_user_id in USUARIOS_PERMITIDOS:
            st.session_state.user_info = USUARIOS_PERMITIDOS[token_user_id]
    except Exception: pass

if not st.session_state.user_info:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col_l1, col_l2, col_l3 = st.columns([1, 1.2, 1])
    with col_l2:
        with st.container(border=True):
            b64_logo = get_image_base64("logo.png")
            if b64_logo:
                st.markdown(f'<div style="text-align: center;"><img src="data:image/png;base64,{b64_logo}" width="80%"></div><br>', unsafe_allow_html=True)
            else:
                st.markdown("<h2 style='text-align: center;'>👓 Boomerang Visión</h2>", unsafe_allow_html=True)
            
            st.markdown("<p style='text-align: center; color: #888;'>Ingreso al Sistema Central</p>", unsafe_allow_html=True)
            user_input = st.text_input("Usuario (Documento)")
            pass_input = st.text_input("Contraseña", type="password")
            
            if st.button("🔐 Iniciar Sesión", type="primary", use_container_width=True):
                user_clean = user_input.strip().lower()
                if user_clean in USUARIOS_PERMITIDOS and USUARIOS_PERMITIDOS[user_clean]["pass"] == pass_input.strip():
                    st.session_state.user_info = USUARIOS_PERMITIDOS[user_clean]
                    nuevo_token = base64.b64encode(f"{user_clean}||{datetime.now().strftime('%Y-%m-%d')}".encode("utf-8")).decode("utf-8")
                    st.query_params["auth_token"] = nuevo_token
                    st.rerun()
                else:
                    st.error("⚠️ Usuario o contraseña incorrectos.")
    st.stop()

# =====================================================================
# 3. FUNCIONES DE FORMATEO Y PDF
# =====================================================================
def clean_numeric_string(val_str):
    val = str(val_str).strip()
    if not val: return ""
    return "".join(c for c in val if c.isdigit())

def format_currency_co(val):
    if val is None or val == "": return ""
    if isinstance(val, (int, float)): val = int(val)
    val_str = str(val).strip()
    if val_str.endswith(".0"): val_str = val_str[:-2]
    digits = clean_numeric_string(val_str)
    if not digits: return ""
    rev = digits[::-1]; res = ""
    for i, char in enumerate(rev):
        if i > 0 and i % 3 == 0: res += "'" if i % 6 == 0 else "."
        res += char
    return res[::-1]

def format_add(add_val):
    if not add_val: return ""
    val_str = str(add_val).strip().upper()
    if val_str in ["0", "0.0", "0.00", "+0.00", "-0.00", "N/A", "NEUTRO"]: 
        return ""
    return val_str

def has_valid_addition(add_val):
    if not add_val: return False
    try:
        val_str = str(add_val).strip().upper()
        if val_str in ["0", "0.0", "0.00", "+0.00", "-0.00", "N/A", "NEUTRO"]:
            return False
        clean_f = float(val_str.replace('+', '').strip())
        return clean_f > 0.0
    except:
        return False

def get_whatsapp_link(celular, mensaje):
    digits = clean_numeric_string(celular)
    if not digits: return "#"
    if not digits.startswith("57") and len(digits) == 10: digits = "57" + digits
    encoded_msg = urllib.parse.quote(mensaje)
    return f"https://wa.me/{digits}?text={encoded_msg}"

def convert_df_to_excel(df, sheet_name="Reporte"):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer: df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()

def styled_header(text, icon=""):
    st.markdown(f"<h3 style='font-weight: 700; margin-bottom: 20px;'>{icon} {text}</h3>", unsafe_allow_html=True)

def build_rx_string(sph, cyl, axis):
    sph_str = "NEUTRO" if sph == 0.0 else f"{sph:+.2f}"
    if cyl == 0.0: return sph_str
    cyl_neg = -abs(cyl)
    return f"{sph_str} {cyl_neg:.2f} x {int(axis)}°"

def format_rx_ui(rx_str):
    if not rx_str or rx_str == "N/A": return "N/A"
    rx_str = str(rx_str).strip().upper()
    if "0.00 X 0" in rx_str or "0.0 X 0" in rx_str:
        clean = rx_str.split("0.0")[0].strip()
        if clean: return clean
    return rx_str

def parse_dp_individual(dp_str):
    if not dp_str or dp_str == "N/A": return "N/A", "N/A"
    dp_str = str(dp_str).upper()
    if "/" in dp_str:
        parts = dp_str.split("/")
        return parts[0].strip(), parts[1].strip()
    return dp_str, "N/A"

def get_cerca_rx(rx_str, adicion_val):
    if not rx_str or rx_str == "N/A": return "N/A"
    try:
        add_f = float(str(adicion_val).replace('+', '').strip()) if adicion_val else 0.0
        if "X" not in rx_str.upper():
            esfera = 0.0 if "NEUTRO" in rx_str.upper() else float(rx_str)
            esf_cerca = esfera + add_f
            return "NEUTRO" if esf_cerca == 0.0 else f"{esf_cerca:+.2f}"
        parts = rx_str.upper().replace('X', ' ').split()
        if len(parts) >= 3:
            esfera = 0.0 if parts[0] in ['N', 'NEUTRO'] else float(parts[0])
            cilindro = float(parts[1])
            eje = int(float(parts[2].replace('°', '')))
            esf_cerca = esfera + add_f
            sph_cerca_str = "NEUTRO" if esf_cerca == 0.0 else f"{esf_cerca:+.2f}"
            if cilindro == 0.0: return sph_cerca_str
            return f"{sph_cerca_str} {cilindro:.2f} x {eje}°"
    except Exception: pass
    return rx_str

def procesar_historia_factura(historia, tipo_gafas):
    h = historia.copy()
    if tipo_gafas == "Lejos": h['adicion'] = ""
    elif tipo_gafas == "Cerca":
        h['rx_final_od'] = get_cerca_rx(h.get('rx_final_od'), h.get('adicion'))
        h['rx_final_oi'] = get_cerca_rx(h.get('rx_final_oi'), h.get('adicion'))
        h['adicion'] = ""
    return h

def parse_for_grid(rx_str):
    if not rx_str or rx_str == "N/A": return "NEUTRO", "", ""
    if "X" not in rx_str.upper(): return rx_str.upper(), "", ""
    parts = rx_str.upper().replace('X', ' ').split()
    esf = "NEUTRO" if parts[0] in ['N', 'NEUTRO'] else parts[0].upper()
    cil = parts[1]; eje = parts[2].upper()
    return esf, cil, eje

def dibujar_media_carta(pdf, paciente, historia, venta, tipo_documento, logo_path="logo.png"):
    pdf.set_font("helvetica", "B", 10)
    pdf.text(10, 15, "Boomerang Vision MF")
    pdf.set_font("helvetica", "", 8.5)
    pdf.text(10, 19, "No Responsable de IVA")
    pdf.text(10, 23, "NIT. 1022396649-1")
    pdf.text(10, 27, "C.C. UNISUR Local 1114")
    pdf.text(10, 31, "TEL. 601-9045922")
    pdf.text(10, 35, "CEL: 3118831369")
    if os.path.exists(logo_path): pdf.image(logo_path, x=145, y=10, w=55)
    
    pdf.set_font("helvetica", "", 9); pdf.set_xy(10, 39)
    pdf.cell(20, 6, "FECHA", border=1)
    pdf.set_font("helvetica", "B", 9)
    pdf.cell(65, 6, datetime.now().strftime("%d/%m/%Y %H:%M"), border=1)
    
    pdf.set_font("helvetica", "", 9)
    pdf.cell(55, 6, "FACTURA", border=1, align="R")
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(55, 6, f"No. {venta['numero_factura']}", border=1, ln=1, align="C")
    
    pdf.set_font("helvetica", "", 8.5); pdf.set_xy(10, 46)
    pdf.cell(20, 6, "NOMBRE:", border=1); pdf.set_font("helvetica", "B", 8.5)
    pdf.cell(85, 6, venta['titular_nombre'], border=1); pdf.set_font("helvetica", "", 8.5)
    pdf.cell(15, 6, "TEL:", border=1); pdf.cell(75, 6, str(venta['titular_tel']), border=1, ln=1)
    
    pdf.set_xy(10, 52)
    pdf.cell(20, 6, "DIRECCION:", border=1); pdf.cell(85, 6, str(paciente.get('direccion', '') or ''), border=1)
    pdf.cell(15, 6, "D.I:", border=1); pdf.cell(75, 6, str(venta['titular_doc']), border=1, ln=1)
    
    pdf.set_font("helvetica", "B", 8.5); pdf.set_xy(10, 60)
    pdf.cell(15, 6, "COD.", border=1, align="C"); pdf.cell(110, 6, "DESCRIPCION", border=1, align="C")
    pdf.cell(15, 6, "CANT.", border=1, align="C"); pdf.cell(27, 6, "V.UNIT.", border=1, align="C"); pdf.cell(28, 6, "TOTAL", border=1, ln=1, align="C")
    
    pdf.set_font("helvetica", "", 8.5); pdf.set_xy(10, 66)
    pdf.cell(15, 8, "1", border=1, align="C"); pdf.cell(110, 8, venta['descripcion'], border=1)
    pdf.cell(15, 8, "1", border=1, align="C"); pdf.cell(27, 8, f"$ {format_currency_co(venta['subtotal'])}", border=1, align="R")
    pdf.cell(28, 8, f"$ {format_currency_co(venta['subtotal'])}", border=1, ln=1, align="R")
    
    pdf.set_xy(10, 74)
    pdf.cell(15, 6, "", border=1); pdf.cell(110, 6, "", border=1); pdf.cell(15, 6, "", border=1); pdf.cell(27, 6, "", border=1); pdf.cell(28, 6, "", border=1, ln=1)

    pdf.set_font("helvetica", "B", 8.5); pdf.set_xy(10, 81)
    pdf.cell(110, 5, f"ENTREGA: {venta['fecha_entrega']}", border=1, ln=1)
    
    pdf.set_font("helvetica", "", 8); pdf.set_xy(10, 86)
    pdf.cell(70, 5, f"RX FINAL: {paciente['nombre_completo']}", border="L,T,B")
    pdf.set_font("helvetica", "B", 8); pdf.cell(40, 5, "AV", border="T,B", ln=1, align="C")
    
    pdf.set_font("helvetica", "", 8); pdf.set_xy(10, 91)
    pdf.cell(70, 5, f"OD: {format_rx_ui(historia.get('rx_final_od', 'N/A'))}", border="L,B"); pdf.cell(40, 5, "20/20", border="B", ln=1, align="C")
    
    pdf.set_xy(10, 96); pdf.cell(70, 5, f"OI: {format_rx_ui(historia.get('rx_final_oi', 'N/A'))}", border="L,B"); pdf.cell(40, 5, "20/20", border="B", ln=1, align="C")
    
    add_str = format_add(historia.get('adicion'))
    add_text = f" ADD: {add_str}" if add_str else ""
    alt_text = f" | ALTURA: {venta['altura_focal']}" if venta.get('altura_focal') else ""
    pdf.set_xy(10, 101)
    pdf.cell(110, 5, f"DP: {historia.get('dp', '')}{add_text}{alt_text}", border="L,B,R", ln=1)
    
    totales = [("SUBTOTAL", venta['subtotal']), ("DESCUENTO", venta['descuento']), ("TOTAL", venta['total']), ("ABONO", venta['abono']), ("SALDO", venta['saldo'])]
    for i, (concepto, valor) in enumerate(totales):
        pdf.set_xy(120, 81 + (i * 5))
        pdf.set_font("helvetica", "", 8); pdf.cell(50, 5, concepto, border=1, align="C")
        pdf.set_font("helvetica", "B" if concepto in ["TOTAL", "SALDO"] else "", 8)
        pdf.cell(35, 5, f"$ {format_currency_co(valor)}", border=1, ln=1, align="R")

    pdf.set_font("helvetica", "", 7.5); pdf.set_xy(120, 106)
    obs_texto = f"OBS: {historia.get('observaciones', '') or ''}"
    pdf.cell(85, 5, (obs_texto[:95] + '...') if len(obs_texto) > 95 else obs_texto, border=1)

    pdf.set_font("helvetica", "B", 8); pdf.set_xy(10, 112)
    pdf.cell(195, 4.5, "DESPUES DE 30 DIAS NO RESPONDEMOS POR TRABAJOS", border=1, ln=1, align="C")
    
    pdf.set_xy(10, 117); pdf.set_font("helvetica", "B", 7.5); pdf.cell(25, 10, "GARANTIA:", border=1, align="C")
    pdf.set_xy(35, 117); pdf.set_font("helvetica", "", 6.5)
    pdf.multi_cell(170, 3.3, "* Lentes oftálmicos aplica por defectos de fabricación por un mes.\n** No hay garantía por manipulación indebida o limpieza con productos abrasivos.\n*** No se da garantía por fórmulas de otro sitio.", border=1)
    
    pdf.set_font("helvetica", "I", 7); pdf.set_xy(10, 128)
    pdf.cell(195, 4, f"BOOMERANG VISION  --  {tipo_documento}", align="C", ln=1)

def dibujar_orden_laboratorio(pdf, paciente, historia, venta, tipo_orden="", logo_path="logo.png"):
    pdf.rect(10, 10, 80, 18); pdf.set_font("helvetica", "B", 34); pdf.set_xy(10, 10)
    pdf.cell(80, 18, f"{venta['numero_factura']}", border=0, align="C")
    
    if os.path.exists(logo_path): pdf.image(logo_path, x=95, y=10, w=52)
        
    pdf.set_font("helvetica", "B", 10); pdf.set_xy(150, 10); pdf.cell(55, 4, "Boomerang Vision", ln=1, align="R")
    pdf.set_font("helvetica", "", 8); pdf.set_xy(150, 14); pdf.cell(55, 4, "C.C. UNISUR Local 1114", ln=1, align="R")
    pdf.set_xy(150, 18); pdf.cell(55, 4, "TEL. 601-9045922", ln=1, align="R")
    
    pdf.set_xy(10, 30); pdf.set_font("helvetica", "B", 12)
    pdf.cell(125, 6, "ORDEN DE LABORATORIO", border="T,B")
    
    pdf.set_font("helvetica", "", 8.5)
    pdf.cell(15, 6, "FECHA", border="T,B")
    pdf.set_font("helvetica", "", 9); pdf.cell(55, 6, datetime.now().strftime("%d/%m/%Y %H:%M"), border="T,B", ln=1)
    
    pdf.set_xy(10, 38); pdf.set_font("helvetica", "", 8.5); pdf.cell(20, 6, "NOMBRE:  ", border="B")
    pdf.set_font("helvetica", "B", 9); pdf.cell(100, 6, venta['titular_nombre'].upper(), border="B")
    pdf.set_font("helvetica", "", 8.5); pdf.cell(15, 6, "TEL:      ", border="B")
    pdf.set_font("helvetica", "", 9); pdf.cell(60, 6, str(venta['titular_tel']), border="B", ln=1)
    
    pdf.set_xy(10, 46); pdf.set_font("helvetica", "B", 8); pdf.cell(195, 5, "DETALLE", border="B", ln=1, align="C")
    
    pdf.set_xy(10, 52); pdf.set_font("helvetica", "", 9)
    pdf.cell(150, 7, venta['descripcion'].upper(), border="B")
    pdf.cell(45, 7, f"$  {format_currency_co(venta['total'])}", border="B", ln=1, align="R")
    
    pdf.set_xy(10, 59)
    if tipo_orden:
        pdf.set_font("helvetica", "B", 10)
        pdf.cell(150, 6, f"*** RX {tipo_orden.upper()} ***", border="B")
    else:
        pdf.cell(150, 6, "", border="B")
    pdf.set_font("helvetica", "", 9)
    pdf.cell(45, 6, "$             -", border="B", ln=1, align="R")
    
    pdf.set_xy(10, 67); pdf.set_font("helvetica", "B", 8.5); pdf.cell(195, 5, f"RX FINAL: {paciente['nombre_completo'].upper()}", border=1, ln=1, align="C")
    
    add_str = format_add(historia.get('adicion'))
    texto_add = f"ADD: {add_str}" if add_str else ""
    alt_val = f" {venta['altura_focal']}" if venta.get('altura_focal') else ""
    
    pdf.set_xy(10, 72); pdf.set_font("helvetica", "B", 9)
    pdf.cell(85, 6, f"OD:    {format_rx_ui(historia.get('rx_final_od', 'N/A'))}", border=1)
    pdf.cell(75, 6, texto_add, border=1); pdf.cell(35, 6, f"ALTURA: {alt_val}", border=1, ln=1, align="C")
    
    pdf.set_xy(10, 78); pdf.cell(85, 6, f"OI:     {format_rx_ui(historia.get('rx_final_oi', 'N/A'))}", border=1)
    pdf.cell(75, 6, f"DP: {historia.get('dp', '')}", border=1); pdf.cell(35, 6, f"ALTURA: {alt_val}", border=1, ln=1, align="C")
    
    pdf.set_xy(10, 87); pdf.set_font("helvetica", "B", 18); pdf.multi_cell(110, 8, f"{venta['fecha_entrega'].upper()}", border=0)
    
    totales_orden = [("TOTAL", venta['total']), ("ABONO", venta['abono']), ("SALDO", venta['saldo'])]
    for i, (concepto, valor) in enumerate(totales_orden):
        pdf.set_xy(125, 87 + (i * 5))
        pdf.set_font("helvetica", "", 8); pdf.cell(35, 5, concepto, border="B")
        pdf.set_font("helvetica", "B", 9); pdf.cell(35, 5, f"$  {format_currency_co(valor)}", border="B", ln=1, align="R")
        
    pdf.set_font("helvetica", "I", 7); pdf.set_xy(10, 128)
    pdf.cell(195, 4, f"BOOMERANG VISION -- ORDEN DE LAB / EXCEL", align="C", ln=1)

def dibujar_prescripcion_clinica(pdf, paciente, historia, detalles_rx, logo_path="logo.png"):
    pdf.set_font("helvetica", "B", 10)
    if os.path.exists(logo_path): pdf.image(logo_path, x=10, y=10, w=45)
    pdf.set_xy(60, 10); pdf.set_font("helvetica", "", 9)
    pdf.cell(80, 5, "Boomerang Vision MF", ln=1)
    pdf.set_x(60); pdf.cell(80, 5, "C.C. UNISUR Local 1114 Soacha", ln=1)
    pdf.set_x(60); pdf.cell(80, 5, "Teléfono 6019045922", ln=1)
    
    pdf.set_xy(120, 15); pdf.set_font("helvetica", "B", 16)
    pdf.cell(85, 8, "PRESCRIPCION OPTICA", align="C", ln=1)
    
    pdf.ln(5); y_start = 28
    pdf.set_xy(10, y_start); pdf.set_font("helvetica", "I", 8)
    pdf.cell(110, 4, "Nombre del paciente:", border="L,T,R"); pdf.cell(25, 4, "Fecha", border=1, align="C")
    pdf.set_font("helvetica", "", 9); pdf.cell(60, 4, datetime.now().strftime("%d/%m/%Y %I:%M %p"), border=1, align="C", ln=1)

    pdf.set_x(10); pdf.set_font("helvetica", "", 10)
    pdf.cell(110, 6, paciente['nombre_completo'].upper(), border="L,B,R")
    pdf.set_font("helvetica", "I", 8); pdf.cell(45, 3, "Identificación", border="L,R", align="C"); pdf.cell(40, 3, "Tipo", border="L,R", align="C", ln=1)

    pdf.set_x(10); pdf.cell(110, 4, "", border=0)
    pdf.set_font("helvetica", "", 9); pdf.cell(10, 4, "CC", border="L,B", align="C")
    pdf.cell(35, 4, str(paciente['documento']), border="B,R", align="C"); pdf.cell(40, 4, "PARTICULAR", border="L,B,R", align="C", ln=1)

    pdf.set_x(10); pdf.set_font("helvetica", "I", 8)
    pdf.cell(110, 4, "Profesional:", border="L,T,R"); pdf.cell(85, 4, "Identificación", border="L,T,R", align="C", ln=1)

    pdf.set_x(10); pdf.set_font("helvetica", "", 10)
    pdf.cell(110, 6, "MATEO FELIPE FELICIANO", border="L,B,R")
    pdf.set_font("helvetica", "", 9); pdf.cell(15, 6, "CC", border="L,B", align="C")
    pdf.cell(70, 6, "1022396649", border="B,R", align="C", ln=1)

    pdf.set_x(10); pdf.set_font("helvetica", "", 9)
    pdf.cell(20, 6, "", border="L,T"); pdf.cell(25, 6, "OJO", border=1, align="C")
    pdf.cell(30, 6, "ESFERA", border=1, align="C"); pdf.cell(30, 6, "CILINDRO", border=1, align="C")
    pdf.cell(20, 6, "EJE", border=1, align="C"); pdf.cell(30, 6, "DNP", border=1, align="C"); pdf.cell(40, 6, "AV", border=1, align="C", ln=1)
    
    y4 = pdf.get_y(); pdf.set_x(10)
    pdf.cell(20, 12, "LEJOS", border=1, align="C")
    
    pdf.set_xy(30, y4); pdf.cell(25, 6, "DERECHO", border=1, align="C")
    esf_od, cil_od, eje_od = parse_for_grid(historia.get('rx_final_od'))
    pdf.cell(30, 6, esf_od, border=1, align="C"); pdf.cell(30, 6, cil_od, border=1, align="C"); pdf.cell(20, 6, eje_od, border=1, align="C")
    dp_od, dp_oi = parse_dp_individual(historia.get('dp'))
    pdf.cell(30, 6, dp_od, border=1, align="C"); pdf.cell(40, 6, detalles_rx.get('av_lejos', '').upper(), border=1, align="C", ln=1)
    
    pdf.set_xy(30, y4+6); pdf.cell(25, 6, "IZQUIERDO", border=1, align="C")
    esf_oi, cil_oi, eje_oi = parse_for_grid(historia.get('rx_final_oi'))
    pdf.cell(30, 6, esf_oi, border=1, align="C"); pdf.cell(30, 6, cil_oi, border=1, align="C"); pdf.cell(20, 6, eje_oi, border=1, align="C")
    pdf.cell(30, 6, dp_oi, border=1, align="C"); pdf.cell(40, 6, detalles_rx.get('av_lejos', '').upper(), border=1, align="C", ln=1)
    
    y5 = pdf.get_y(); pdf.set_x(10)
    pdf.cell(20, 12, "CERCA", border=1, align="C")
    
    pdf.set_xy(30, y5); pdf.cell(25, 6, "DERECHO", border=1, align="C")
    add_str = format_add(historia.get('adicion'))
    cerca_esf = f"{add_str} ADD" if add_str else ""
    pdf.cell(30, 6, cerca_esf, border=1, align="C"); pdf.cell(30, 6, "", border=1, align="C")
    pdf.cell(20, 6, "", border=1, align="C"); pdf.cell(30, 6, "", border=1, align="C")
    pdf.cell(40, 6, detalles_rx.get('av_cerca', '').upper() if add_str else "", border=1, align="C", ln=1)
    
    pdf.set_xy(30, y5+6); pdf.cell(25, 6, "IZQUIERDO", border=1, align="C")
    pdf.cell(30, 6, cerca_esf, border=1, align="C"); pdf.cell(30, 6, "", border=1, align="C")
    pdf.cell(20, 6, "", border=1, align="C"); pdf.cell(30, 6, "", border=1, align="C")
    pdf.cell(40, 6, detalles_rx.get('av_cerca', '').upper() if add_str else "", border=1, align="C", ln=1)
    
    y6 = pdf.get_y(); pdf.set_x(10)
    pdf.cell(35, 6, "CONTROL:", border=1); pdf.cell(60, 6, detalles_rx.get('prox_control', '').upper(), border=1)
    pdf.cell(25, 6, "VIGENCIA:", border=1); pdf.cell(75, 6, "30 DIAS", border=1, ln=1)
    
    pdf.set_x(10); pdf.cell(35, 6, "TIPO LENTE:", border=1); pdf.cell(60, 6, detalles_rx.get('tipo_lente', '').upper(), border=1)
    pdf.cell(25, 6, "USO:", border=1); pdf.cell(75, 6, detalles_rx.get('uso', '').upper(), border=1, ln=1)
    
    pdf.set_x(10); pdf.cell(35, 6, "FILTRO:", border=1); pdf.cell(60, 6, detalles_rx.get('filtro', '').upper(), border=1)
    pdf.cell(50, 6, "TREntiendo perfectamente la frustración. Ese mensaje de "Brave bloqueó esta página" que vemos en el archivo {5849E0C0-A7C9-487A-B468-1BC1F793EB97}.png es un clásico dolor de cabeza cuando intentamos renderizar documentos o manejar descargas web.

El problema central radica en los **Brave Shields (Escudos de Brave)**. Este navegador tiene políticas de privacidad y bloqueo de rastreadores extremadamente agresivas. Si el botón "Descargar Facturación" está intentando cargar el documento dentro de un `iframe`, o está haciendo una petición de origen cruzado (cross-origin) a un servidor externo para obtener el archivo, Brave lo clasifica inmediatamente como un riesgo de rastreo o contenido inseguro y corta la conexión de raíz.

Aquí tienes la hoja de ruta para solucionarlo, desde la prueba rápida hasta la solución definitiva a nivel de código.

### 1. La Solución Rápida (Para validar localmente)
Antes de tocar el código, asegúrate de que este es exactamente el origen del problema:
*   Ve a la barra de direcciones de Brave.
*   Haz clic en el **ícono del león** (Brave Shields).
*   Desactiva los escudos para esta URL (especialmente si estás trabajando en `localhost`).
*   Recarga la página. Si el documento carga o se descarga correctamente, confirmamos que el problema es la forma en que el código maneja el archivo frente a las políticas del navegador.

### 2. La Solución Definitiva (A nivel de arquitectura)
Depender de un `iframe` para mostrar previsualizaciones o manejar descargas te va a generar este mismo problema repetidamente en navegadores estrictos o si los usuarios tienen bloqueadores de anuncios (AdBlock, uBlock). 

Para evitarlo y hacer que funcione de manera nativa sin importar el navegador, la mejor ruta al trabajar con componentes en React o Next.js es manejar la descarga a través de un **Blob (Binary Large Object)** directamente en la memoria del cliente, o forzar la descarga nativa mediante un enlace.

**Opción A: Descarga manejada por Blob (Ideal para APIs)**
En lugar de incrustar la respuesta, intercepta el archivo, conviértelo en un objeto temporal y fuerza la descarga limpia:

```javascript
const descargarFactura = async () => {
  try {
    // Aquí haces la llamada a tu API o base de datos
    const respuesta = await fetch('RUTA_A_TU_ENDPOINT_DE_FACTURACION');
    
    // Convertimos la respuesta a un Blob (archivo binario)
    const blob = await respuesta.blob();
    
    // Creamos una URL temporal en la memoria del navegador
    const url = window.URL.createObjectURL(blob);
    
    // Forzamos la descarga creando un elemento ancla <a> invisible
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'factura_paciente.pdf'); // Nombre del archivo
    document.body.appendChild(link);
    
    link.click(); // Ejecuta la descarga
    
    // Limpieza de memoria
    link.remove();
    window.URL.revokeObjectURL(url);
    
  } catch (error) {
    console.error("Error procesando la descarga de la factura:", error);
  }
};
