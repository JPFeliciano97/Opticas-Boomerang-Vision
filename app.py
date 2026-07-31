import streamlit as st
from supabase import create_client
import os
import base64
import io
import urllib.parse
import pandas as pd
from dotenv import load_dotenv
from fpdf import FPDF
from datetime import datetime

# =====================================================================
# 1. CONFIGURACIÓN INICIAL DE PÁGINA Y BD
# =====================================================================
st.set_page_config(page_title="Boomerang Visión ERP", layout="wide", page_icon="👓", initial_sidebar_state="expanded")

load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

@st.cache_resource
def init_connection():
    return create_client(url, key)

supabase = init_connection()

# =====================================================================
# 2. SISTEMA DE AUTENTICACIÓN Y ROLES LOCALES (CON PERSISTENCIA DIARIA)
# =====================================================================
USUARIOS_PERMITIDOS = {
    "1022396649": {"pass": "mateo", "nombre": "Dr. Mateo F.", "rol": "admin", "id": "1022396649"},
    "1024585129": {"pass": "juan", "nombre": "Dr. Juan Pablo", "rol": "admin", "id": "1024585129"},
    "39667008": {"pass": "rosa", "nombre": "Rosa (Asesora)", "rol": "admin", "id": "39667008"},
    "79203712": {"pass": "nelson", "nombre": "Nelson (Asesor)", "rol": "admin", "id": "79203712"},
    "asesor": {"pass": "1234", "nombre": "Asesor Invitado", "rol": "asesor_limitado", "id": "asesor"},
    "doctor": {"pass": "1234", "nombre": "Doctor Invitado", "rol": "doctor_limitado", "id": "doctor"}
}

if "user_info" not in st.session_state:
    st.session_state.user_info = None

# Verificación de sesión persistente (Token de URL válido solo por el día de hoy)
if st.session_state.user_info is None and "auth_token" in st.query_params:
    try:
        token = st.query_params["auth_token"]
        decoded_token = base64.b64decode(token).decode("utf-8")
        token_user_id, token_date = decoded_token.split("||")
        if token_date == datetime.now().strftime("%Y-%m-%d") and token_user_id in USUARIOS_PERMITIDOS:
            st.session_state.user_info = USUARIOS_PERMITIDOS[token_user_id]
    except Exception:
        pass

if not st.session_state.user_info:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col_l1, col_l2, col_l3 = st.columns([1, 1.5, 1])
    with col_l2:
        with st.container(border=True):
            st.markdown("<h2 style='text-align: center; color: #00bcd4;'>👓 Boomerang Visión</h2>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: #888;'>Inicia sesión con tu Documento o Usuario</p>", unsafe_allow_html=True)
            
            user_input = st.text_input("Usuario (Documento)")
            pass_input = st.text_input("Contraseña", type="password")
            
            if st.button("🔐 Ingresar al Sistema", type="primary", use_container_width=True):
                user_clean = user_input.strip().lower()
                if user_clean in USUARIOS_PERMITIDOS and USUARIOS_PERMITIDOS[user_clean]["pass"] == pass_input.strip():
                    st.session_state.user_info = USUARIOS_PERMITIDOS[user_clean]
                    # Generar token persistente para el día actual
                    nuevo_token = base64.b64encode(f"{user_clean}||{datetime.now().strftime('%Y-%m-%d')}".encode("utf-8")).decode("utf-8")
                    st.query_params["auth_token"] = nuevo_token
                    st.success(f"¡Bienvenido, {st.session_state.user_info['nombre']}!")
                    st.rerun()
                else:
                    st.error("⚠️ Usuario o contraseña incorrectos.")
    st.stop()

# =====================================================================
# 3. FUNCIONES DE FORMATEO DINÁMICO Y UTILIDADES
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
    rev = digits[::-1]
    res = ""
    for i, char in enumerate(rev):
        if i > 0 and i % 3 == 0:
            res += "'" if i % 6 == 0 else "."
        res += char
    return res[::-1]

def get_whatsapp_link(celular, mensaje):
    digits = clean_numeric_string(celular)
    if not digits: return "#"
    if not digits.startswith("57") and len(digits) == 10:
        digits = "57" + digits
    encoded_msg = urllib.parse.quote(mensaje)
    return f"https://wa.me/{digits}?text={encoded_msg}"

def convert_df_to_excel(df, sheet_name="Reporte"):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()

def styled_header(text, icon=""):
    st.markdown(f"<h3 style='color: #00bcd4; font-weight: 600;'>{icon} {text}</h3>", unsafe_allow_html=True)

# =====================================================================
# 4. LÓGICA CLÍNICA - CONSTRUCTOR DE RX Y CÁLCULOS
# =====================================================================
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
    if tipo_gafas == "Lejos":
        h['adicion'] = ""
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
    cil = parts[1]
    eje = parts[2].upper()
    return esf, cil, eje

# =====================================================================
# 5. CALLBACKS DE INTERFAZ Y ESTADO
# =====================================================================
def force_negative_cyl_od():
    if st.session_state.cil_od > 0: st.session_state.cil_od = -abs(st.session_state.cil_od)

def force_negative_cyl_oi():
    if st.session_state.cil_oi > 0: st.session_state.cil_oi = -abs(st.session_state.cil_oi)

def on_subtotal_change(): st.session_state.subtotal_input = format_currency_co(st.session_state.subtotal_input)
def on_abono_change(): st.session_state.abono_input = format_currency_co(st.session_state.abono_input)
def on_monto_rec_change(): st.session_state.monto_rec_input = format_currency_co(st.session_state.monto_rec_input)
def on_monto_gasto_change(): st.session_state.monto_gasto_input = format_currency_co(st.session_state.monto_gasto_input)
def on_p_compra_change(): st.session_state.p_compra_input = format_currency_co(st.session_state.p_compra_input)
def on_p_venta_change(): st.session_state.p_venta_input = format_currency_co(st.session_state.p_venta_input)

def on_descuento_change():
    raw = st.session_state.descuento_input
    tipo = st.session_state.tipo_descuento_widget
    digits = clean_numeric_string(raw)
    if not digits: st.session_state.descuento_input = ""; return
    st.session_state.descuento_input = f"{digits}%" if tipo == "Porcentaje (%)" else format_currency_co(digits)

def on_tipo_descuento_change():
    raw = st.session_state.descuento_input
    digits = clean_numeric_string(raw)
    if not digits: st.session_state.descuento_input = ""; return
    st.session_state.descuento_input = f"{digits}%" if st.session_state.tipo_descuento_widget == "Porcentaje (%)" else format_currency_co(digits)

def on_altura_focal_change():
    digits = "".join(c for c in st.session_state.altura_focal_input if c.isdigit())
    st.session_state.altura_focal_input = f"{digits} mm" if digits else ""

for k in ["subtotal_input", "abono_input", "descuento_input", "altura_focal_input", "monto_rec_input", "monto_gasto_input", "p_compra_input", "p_venta_input"]:
    if k not in st.session_state: st.session_state[k] = ""
if "last_fac_search" not in st.session_state: st.session_state.last_fac_search = ""

# Vaciado Seguro
if "trigger_clear_doc" in st.session_state and st.session_state.trigger_clear_doc:
    for k in ["doc_input", "nom_input", "cel_input", "dir_input", "ocu_input", "edad_input", "mot_input", "ctrl_input", "dp_od_input", "dp_oi_input", "obs_input"]:
        st.session_state[k] = ""
    for k in ["esf_od", "cil_od", "eje_od", "esf_oi", "cil_oi", "eje_oi", "add_input"]:
        st.session_state[k] = 0.0 if "eje" not in k else 0
    st.session_state.trigger_clear_doc = False

if "trigger_clear_factura" in st.session_state and st.session_state.trigger_clear_factura:
    for k in ["subtotal_input", "abono_input", "descuento_input", "altura_focal_input"]:
        st.session_state[k] = ""
    st.session_state.trigger_clear_factura = False

if "trigger_clear_recaudo" in st.session_state and st.session_state.trigger_clear_recaudo:
    st.session_state.monto_rec_input = ""
    st.session_state.last_fac_search = ""
    st.session_state.trigger_clear_recaudo = False

# =====================================================================
# 6. FUNCIONES PDF (DIBUJO)
# =====================================================================
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
    
    pdf.set_font("helvetica", "", 9)
    pdf.set_xy(10, 39)
    pdf.cell(20, 6, "FECHA", border=1)
    pdf.set_font("helvetica", "B", 9)
    pdf.cell(65, 6, datetime.now().strftime("%d/%m/%Y %H:%M"), border=1)
    
    pdf.set_font("helvetica", "", 9)
    pdf.cell(55, 6, "FACTURA", border=1, align="R")
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(55, 6, f"No. {venta['numero_factura']}", border=1, ln=1, align="C")
    
    pdf.set_font("helvetica", "", 8.5)
    pdf.set_xy(10, 46)
    pdf.cell(20, 6, "NOMBRE:", border=1)
    pdf.set_font("helvetica", "B", 8.5)
    pdf.cell(85, 6, venta['titular_nombre'], border=1)
    
    pdf.set_font("helvetica", "", 8.5)
    pdf.cell(15, 6, "TEL:", border=1)
    pdf.cell(75, 6, str(venta['titular_tel']), border=1, ln=1)
    
    pdf.set_xy(10, 52)
    pdf.cell(20, 6, "DIRECCION:", border=1)
    pdf.cell(85, 6, str(paciente.get('direccion', '') or ''), border=1)
    pdf.cell(15, 6, "D.I:", border=1)
    pdf.cell(75, 6, str(venta['titular_doc']), border=1, ln=1)
    
    pdf.set_font("helvetica", "B", 8.5)
    pdf.set_xy(10, 60)
    pdf.cell(15, 6, "COD.", border=1, align="C")
    pdf.cell(110, 6, "DESCRIPCION", border=1, align="C")
    pdf.cell(15, 6, "CANT.", border=1, align="C")
    pdf.cell(27, 6, "V.UNIT.", border=1, align="C")
    pdf.cell(28, 6, "TOTAL", border=1, ln=1, align="C")
    
    pdf.set_font("helvetica", "", 8.5)
    pdf.set_xy(10, 66)
    pdf.cell(15, 8, "1", border=1, align="C")
    pdf.cell(110, 8, venta['descripcion'], border=1)
    pdf.cell(15, 8, "1", border=1, align="C")
    pdf.cell(27, 8, f"$ {format_currency_co(venta['subtotal'])}", border=1, align="R")
    pdf.cell(28, 8, f"$ {format_currency_co(venta['subtotal'])}", border=1, ln=1, align="R")
    
    pdf.set_xy(10, 74)
    pdf.cell(15, 6, "", border=1); pdf.cell(110, 6, "", border=1); pdf.cell(15, 6, "", border=1)
    pdf.cell(27, 6, "", border=1); pdf.cell(28, 6, "", border=1, ln=1)

    pdf.set_font("helvetica", "B", 8.5)
    pdf.set_xy(10, 81)
    pdf.cell(110, 5, f"ENTREGA: {venta['fecha_entrega']}", border=1, ln=1)
    
    pdf.set_font("helvetica", "", 8)
    pdf.set_xy(10, 86)
    pdf.cell(70, 5, f"RX FINAL: {paciente['nombre_completo']}", border="L,T,B")
    pdf.set_font("helvetica", "B", 8)
    pdf.cell(40, 5, "AV", border="T,B", ln=1, align="C")
    
    pdf.set_font("helvetica", "", 8)
    pdf.set_xy(10, 91)
    pdf.cell(70, 5, f"OD: {format_rx_ui(historia.get('rx_final_od', 'N/A'))}", border="L,B")
    pdf.cell(40, 5, "20/20", border="B", ln=1, align="C")
    
    pdf.set_xy(10, 96)
    pdf.cell(70, 5, f"OI: {format_rx_ui(historia.get('rx_final_oi', 'N/A'))}", border="L,B")
    pdf.cell(40, 5, "20/20", border="B", ln=1, align="C")
    
    add_text = f" ADD: {historia.get('adicion')}" if historia.get('adicion') else ""
    alt_text = f" | ALTURA: {venta['altura_focal']}" if venta.get('altura_focal') else ""
    pdf.set_xy(10, 101)
    pdf.cell(110, 5, f"DP: {historia.get('dp', '')}{add_text}{alt_text}", border="L,B,R", ln=1)
    
    totales = [("SUBTOTAL", venta['subtotal']), ("DESCUENTO", venta['descuento']), ("TOTAL", venta['total']), ("ABONO", venta['abono']), ("SALDO", venta['saldo'])]
    for i, (concepto, valor) in enumerate(totales):
        pdf.set_xy(120, 81 + (i * 5))
        pdf.set_font("helvetica", "", 8)
        pdf.cell(50, 5, concepto, border=1, align="C")
        pdf.set_font("helvetica", "B" if concepto in ["TOTAL", "SALDO"] else "", 8)
        pdf.cell(35, 5, f"$ {format_currency_co(valor)}", border=1, ln=1, align="R")

    pdf.set_font("helvetica", "", 7.5)
    pdf.set_xy(120, 106)
    obs_texto = f"OBS: {historia.get('observaciones', '') or ''}"
    pdf.cell(85, 5, (obs_texto[:95] + '...') if len(obs_texto) > 95 else obs_texto, border=1)

    pdf.set_font("helvetica", "B", 8)
    pdf.set_xy(10, 112)
    pdf.cell(195, 4.5, "DESPUES DE 30 DIAS NO RESPONDEMOS POR TRABAJOS", border=1, ln=1, align="C")
    
    pdf.set_xy(10, 117)
    pdf.set_font("helvetica", "B", 7.5)
    pdf.cell(25, 10, "GARANTIA:", border=1, align="C")
    pdf.set_xy(35, 117)
    pdf.set_font("helvetica", "", 6.5)
    pdf.multi_cell(170, 3.3, "* Lentes oftálmicos aplica por defectos de fabricación por un mes.\n** No hay garantía por manipulación indebida o limpieza con productos abrasivos.\n*** No se da garantía por fórmulas de otro sitio.", border=1)
    
    pdf.set_font("helvetica", "I", 7)
    pdf.set_xy(10, 128)
    pdf.cell(195, 4, f"BOOMERANG VISION  --  {tipo_documento}", align="C", ln=1)

def dibujar_orden_laboratorio(pdf, paciente, historia, venta, tipo_orden="", logo_path="logo.png"):
    pdf.rect(10, 10, 80, 18)
    pdf.set_font("helvetica", "B", 34)
    pdf.set_xy(10, 10)
    pdf.cell(80, 18, f"{venta['numero_factura']}", border=0, align="C")
    
    if os.path.exists(logo_path): pdf.image(logo_path, x=95, y=10, w=52)
        
    pdf.set_font("helvetica", "B", 10)
    pdf.set_xy(150, 10)
    pdf.cell(55, 4, "Boomerang Vision", ln=1, align="R")
    pdf.set_font("helvetica", "", 8)
    pdf.set_xy(150, 14); pdf.cell(55, 4, "C.C. UNISUR Local 1114", ln=1, align="R")
    pdf.set_xy(150, 18); pdf.cell(55, 4, "TEL. 601-9045922", ln=1, align="R")
    
    pdf.set_xy(10, 30)
    pdf.set_font("helvetica", "", 8.5)
    pdf.cell(15, 6, "FECHA", border="T,B")
    pdf.set_font("helvetica", "", 9)
    pdf.cell(180, 6, datetime.now().strftime("%d/%m/%Y %H:%M"), border="T,B", ln=1)
    
    pdf.set_xy(10, 38)
    pdf.set_font("helvetica", "", 8.5); pdf.cell(20, 6, "NOMBRE:  ", border="B")
    pdf.set_font("helvetica", "B", 9); pdf.cell(100, 6, venta['titular_nombre'].upper(), border="B")
    pdf.set_font("helvetica", "", 8.5); pdf.cell(15, 6, "TEL:      ", border="B")
    pdf.set_font("helvetica", "", 9); pdf.cell(60, 6, str(venta['titular_tel']), border="B", ln=1)
    
    pdf.set_xy(10, 46)
    pdf.set_font("helvetica", "B", 8); pdf.cell(195, 5, "DETALLE", border="B", ln=1, align="C")
    
    pdf.set_xy(10, 52)
    pdf.set_font("helvetica", "", 9)
    pdf.cell(150, 7, venta['descripcion'].upper(), border="B")
    pdf.cell(45, 7, f"$  {format_currency_co(venta['total'])}", border="B", ln=1, align="R")
    
    pdf.set_xy(10, 59)
    pdf.cell(150, 6, "", border="B"); pdf.cell(45, 6, "$             -", border="B", ln=1, align="R")
    
    pdf.set_xy(10, 67)
    pdf.set_font("helvetica", "B", 8.5)
    pdf.cell(195, 5, f"RX FINAL: {paciente['nombre_completo'].upper()}", border=1, ln=1, align="C")
    
    add_val = f" {historia.get('adicion')}" if historia.get('adicion') else ""
    alt_val = f" {venta['altura_focal']}" if venta.get('altura_focal') else ""
    
    pdf.set_xy(10, 72)
    pdf.set_font("helvetica", "B", 9)
    pdf.cell(85, 6, f"OD:    {format_rx_ui(historia.get('rx_final_od', 'N/A'))}", border=1)
    pdf.cell(75, 6, f"ADD:{add_val}", border=1)
    pdf.cell(35, 6, f"ALTURA: {alt_val}", border=1, ln=1, align="C")
    
    pdf.set_xy(10, 78)
    pdf.cell(85, 6, f"OI:     {format_rx_ui(historia.get('rx_final_oi', 'N/A'))}", border=1)
    pdf.cell(75, 6, f"DP: {historia.get('dp', '')}", border=1)
    pdf.cell(35, 6, f"ALTURA: {alt_val}", border=1, ln=1, align="C")
    
    pdf.set_xy(10, 87)
    pdf.set_font("helvetica", "B", 18)
    pdf.multi_cell(110, 8, f"{venta['fecha_entrega'].upper()}", border=0)
    
    totales_orden = [("TOTAL", venta['total']), ("ABONO", venta['abono']), ("SALDO", venta['saldo'])]
    for i, (concepto, valor) in enumerate(totales_orden):
        pdf.set_xy(125, 87 + (i * 5))
        pdf.set_font("helvetica", "", 8); pdf.cell(35, 5, concepto, border="B")
        pdf.set_font("helvetica", "B", 9); pdf.cell(35, 5, f"$  {format_currency_co(valor)}", border="B", ln=1, align="R")
        
    pdf.set_font("helvetica", "I", 7)
    pdf.set_xy(10, 128)
    tipo_str = f" - {tipo_orden}" if tipo_orden else ""
    pdf.cell(195, 4, f"BOOMERANG VISION -- ORDEN DE LABORATORIO / IMPRESIÓN EXCEL{tipo_str}", align="C", ln=1)

def dibujar_prescripcion_clinica(pdf, paciente, historia, detalles_rx, logo_path="logo.png"):
    pdf.set_font("helvetica", "B", 10)
    if os.path.exists(logo_path): pdf.image(logo_path, x=10, y=10, w=45)
    pdf.set_xy(60, 10)
    pdf.set_font("helvetica", "", 9)
    pdf.cell(80, 5, "Boomerang Vision MF", ln=1)
    pdf.set_x(60); pdf.cell(80, 5, "C.C. UNISUR Local 1114 Soacha", ln=1)
    pdf.set_x(60); pdf.cell(80, 5, "Teléfono 6019045922", ln=1)
    
    pdf.set_xy(120, 15)
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(85, 8, "PRESCRIPCION OPTICA", align="C", ln=1)
    
    pdf.ln(5)
    y_start = 28

    pdf.set_xy(10, y_start)
    pdf.set_font("helvetica", "I", 8)
    pdf.cell(110, 4, "Nombre del paciente:", border="L,T,R")
    pdf.cell(25, 4, "Fecha", border=1, align="C")
    pdf.set_font("helvetica", "", 9)
    pdf.cell(60, 4, datetime.now().strftime("%d/%m/%Y %I:%M %p"), border=1, align="C", ln=1)

    pdf.set_x(10)
    pdf.set_font("helvetica", "", 10)
    pdf.cell(110, 6, paciente['nombre_completo'].upper(), border="L,B,R")
    pdf.set_font("helvetica", "I", 8)
    pdf.cell(45, 3, "Identificación del paciente", border="L,R", align="C")
    pdf.cell(40, 3, "Tipo de usuario", border="L,R", align="C", ln=1)

    pdf.set_x(10)
    pdf.cell(110, 4, "", border=0)
    pdf.set_font("helvetica", "", 9)
    pdf.cell(10, 4, "CC", border="L,B", align="C")
    pdf.cell(35, 4, str(paciente['documento']), border="B,R", align="C")
    pdf.cell(40, 4, "PARTICULAR", border="L,B,R", align="C", ln=1)

    pdf.set_x(10)
    pdf.set_font("helvetica", "I", 8)
    pdf.cell(110, 4, "Nombre del profesional:", border="L,T,R")
    pdf.cell(85, 4, "Identificación del profesional", border="L,T,R", align="C", ln=1)

    pdf.set_x(10)
    pdf.set_font("helvetica", "", 10)
    pdf.cell(110, 6, "MATEO FELIPE FELICIANO", border="L,B,R")
    pdf.set_font("helvetica", "", 9)
    pdf.cell(15, 6, "CC", border="L,B", align="C")
    pdf.cell(70, 6, "1022396649", border="B,R", align="C", ln=1)

    pdf.set_x(10)
    pdf.set_font("helvetica", "", 9)
    pdf.cell(20, 6, "", border="L,T")
    pdf.cell(25, 6, "OJO", border=1, align="C")
    pdf.cell(30, 6, "ESFERA", border=1, align="C"); pdf.cell(30, 6, "CILINDRO", border=1, align="C")
    pdf.cell(20, 6, "EJE", border=1, align="C"); pdf.cell(30, 6, "DNP", border=1, align="C")
    pdf.cell(40, 6, "AV", border=1, align="C", ln=1)
    
    y4 = pdf.get_y()
    pdf.set_x(10)
    pdf.cell(20, 12, "LEJOS", border=1, align="C")
    
    pdf.set_xy(30, y4)
    pdf.cell(25, 6, "DERECHO", border=1, align="C")
    esf_od, cil_od, eje_od = parse_for_grid(historia.get('rx_final_od'))
    pdf.cell(30, 6, esf_od, border=1, align="C"); pdf.cell(30, 6, cil_od, border=1, align="C"); pdf.cell(20, 6, eje_od, border=1, align="C")
    dp_od, dp_oi = parse_dp_individual(historia.get('dp'))
    pdf.cell(30, 6, dp_od, border=1, align="C"); pdf.cell(40, 6, detalles_rx.get('av_lejos', '').upper(), border=1, align="C", ln=1)
    
    pdf.set_xy(30, y4+6)
    pdf.cell(25, 6, "IZQUIERDO", border=1, align="C")
    esf_oi, cil_oi, eje_oi = parse_for_grid(historia.get('rx_final_oi'))
    pdf.cell(30, 6, esf_oi, border=1, align="C"); pdf.cell(30, 6, cil_oi, border=1, align="C"); pdf.cell(20, 6, eje_oi, border=1, align="C")
    pdf.cell(30, 6, dp_oi, border=1, align="C"); pdf.cell(40, 6, detalles_rx.get('av_lejos', '').upper(), border=1, align="C", ln=1)
    
    y5 = pdf.get_y()
    pdf.set_x(10)
    pdf.cell(20, 12, "CERCA", border=1, align="C")
    
    pdf.set_xy(30, y5)
    pdf.cell(25, 6, "DERECHO", border=1, align="C")
    add_val = historia.get('adicion')
    cerca_esf = f"{add_val} ADD" if add_val else ""
    pdf.cell(30, 6, cerca_esf, border=1, align="C"); pdf.cell(30, 6, "", border=1, align="C")
    pdf.cell(20, 6, "", border=1, align="C"); pdf.cell(30, 6, "", border=1, align="C")
    pdf.cell(40, 6, detalles_rx.get('av_cerca', '').upper() if add_val else "", border=1, align="C", ln=1)
    
    pdf.set_xy(30, y5+6)
    pdf.cell(25, 6, "IZQUIERDO", border=1, align="C")
    pdf.cell(30, 6, cerca_esf, border=1, align="C"); pdf.cell(30, 6, "", border=1, align="C")
    pdf.cell(20, 6, "", border=1, align="C"); pdf.cell(30, 6, "", border=1, align="C")
    pdf.cell(40, 6, detalles_rx.get('av_cerca', '').upper() if add_val else "", border=1, align="C", ln=1)
    
    y6 = pdf.get_y()
    pdf.set_x(10)
    pdf.cell(35, 6, "PRÓXIMO CONTROL:", border=1); pdf.cell(60, 6, detalles_rx.get('prox_control', '').upper(), border=1)
    pdf.cell(25, 6, "VIGENCIA:", border=1); pdf.cell(75, 6, "30 DIAS", border=1, ln=1)
    
    pdf.set_x(10)
    pdf.cell(35, 6, "TIPO DE LENTE:", border=1); pdf.cell(60, 6, detalles_rx.get('tipo_lente', '').upper(), border=1)
    pdf.cell(25, 6, "USO:", border=1); pdf.cell(75, 6, detalles_rx.get('uso', '').upper(), border=1, ln=1)
    
    pdf.set_x(10)
    pdf.cell(35, 6, "CLASE DE FILTRO:", border=1); pdf.cell(60, 6, detalles_rx.get('filtro', '').upper(), border=1)
    pdf.cell(50, 6, "PERÍODO DE TRATAMIENTO:", border=1); pdf.cell(50, 6, "UN AÑO", border=1, ln=1)
    
    pdf.set_x(10)
    pdf.set_font("helvetica", "B", 9); pdf.cell(195, 6, "OBSERVACIONES:", border="L,T,R", ln=1)
    pdf.set_font("helvetica", "", 9); pdf.set_x(10)
    pdf.multi_cell(195, 5, historia.get('observaciones', '').upper(), border="L,R")
    
    y_firma = pdf.get_y()
    pdf.set_xy(120, max(y_firma, y6+35))
    pdf.set_font("helvetica", "", 8); pdf.set_text_color(100, 100, 100)
    pdf.cell(75, 4, "Mateo F. Feliciano L.", align="C", ln=1); pdf.set_x(120)
    pdf.cell(75, 4, "Optómetra U.L.S.", align="C", ln=1); pdf.set_x(120)
    pdf.cell(75, 4, "T.P. 1022396649", align="C", ln=1); pdf.set_text_color(0, 0, 0)
    
    pdf.set_x(10)
    pdf.cell(195, 1, "", border="T", ln=1)
    pdf.set_font("helvetica", "B", 8)
    pdf.cell(195, 6, "Nota: NO SE DA GARANTIA POR TRABAJOS REALIZADOS EN OTRA OPTICA", ln=1)

def get_image_base64(path):
    if os.path.exists(path):
        with open(path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    return None

def get_sidebar_logo_html():
    b64_logo1 = get_image_base64("logo.png")
    b64_logo2 = get_image_base64("logo2.png")
    
    if not b64_logo1 and not b64_logo2:
        return """
        <div style="text-align: center; margin-bottom: 20px;">
            <h1 style="color: #00bcd4; margin-bottom: 0px;">👓</h1>
            <h3 style="color: #ffffff; font-weight: 300;">Boomerang Visión</h3>
        </div>
        """
    
    img_light = f'<img src="data:image/png;base64,{b64_logo1}" class="logo-light">' if b64_logo1 else ""
    img_dark = f'<img src="data:image/png;base64,{b64_logo2}" class="logo-dark">' if b64_logo2 else img_light.replace('logo-light', 'logo-dark')
    
    return f"""
    <style>
        .logo-light {{ display: block; max-width: 80%; margin: auto; margin-bottom: 20px; }}
        .logo-dark {{ display: none; max-width: 80%; margin: auto; margin-bottom: 20px; }}
        @media (prefers-color-scheme: dark) {{
            .logo-light {{ display: none; }}
            .logo-dark {{ display: block; }}
        }}
    </style>
    <div style="text-align: center;">
        {img_light}
        {img_dark}
    </div>
    """

# ==========================================
# 7. SISTEMA GLOBAL DE NOTIFICACIONES FLOTANTES (TOASTS)
# ==========================================
if "global_toast" in st.session_state:
    st.toast(st.session_state.global_toast, icon=st.session_state.get("global_toast_icon", "✅"))
    del st.session_state.global_toast
    if "global_toast_icon" in st.session_state:
        del st.session_state.global_toast_icon

# ==========================================
# 8. INTERFAZ DE USUARIO (MENÚ LATERAL Y ROLES)
# ==========================================
user_rol = st.session_state.user_info["rol"]
user_id = st.session_state.user_info["id"]

todos_los_modulos = [
    "👨‍⚕️ Consultorio (Doctor)", 
    "🛍️ Óptica y Facturación",
    "📊 Cuadre de Caja Físico",
    "📦 Inventario (Bodega)",
    "🔬 Control de Laboratorios",
    "📅 CRM y Fidelización",
    "📈 Analítica y Estadísticas"
]

modulos_permitidos = []

if user_rol == "admin":
    modulos_permitidos = todos_los_modulos.copy()
    # Restricción explícita: Solo Dr. Mateo y Dr. Juan ven Consultorio
    if user_id not in ["1022396649", "1024585129"]:
        modulos_permitidos.remove("👨‍⚕️ Consultorio (Doctor)")
elif user_rol == "asesor_limitado":
    modulos_permitidos = [
        "🛍️ Óptica y Facturación",
        "📊 Cuadre de Caja Físico",
        "🔬 Control de Laboratorios"
    ]
elif user_rol == "doctor_limitado":
    modulos_permitidos = [
        "👨‍⚕️ Consultorio (Doctor)"
    ]

with st.sidebar:
    st.markdown(get_sidebar_logo_html(), unsafe_allow_html=True)
    st.caption(f"👤 Sesión: {st.session_state.user_info['nombre']}")
    
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.user_info = None
        if "auth_token" in st.query_params:
            del st.query_params["auth_token"]
        st.rerun()
        
    st.markdown("---")
    modulo = st.sidebar.radio("Módulo de Trabajo:", modulos_permitidos)
    st.markdown("---")
    st.caption("🚀 Boomerang Visión ERP - V1.0")

# ------------------------------------------
# MÓDULO 1: CONSULTORIO (DOCTOR)
# ------------------------------------------
if modulo == "👨‍⚕️ Consultorio (Doctor)":
    styled_header("Recepción de Pacientes y Clínica", "👨‍⚕️")
    
    with st.container(border=True):
        col_doc_search, col_doc_btn = st.columns([3, 1])
        with col_doc_search:
            doc_autofill = st.text_input("🔍 Buscar Paciente Registrado (Cédula):", key="doc_autofill_input").upper()
        with col_doc_btn:
            st.write(""); st.write("")
            if st.button("Cargar Datos Paciente", use_container_width=True):
                if doc_autofill:
                    res_exist = supabase.table("pacientes").select("*").eq("documento", doc_autofill).execute()
                    if res_exist.data:
                        p_data = res_exist.data[0]
                        st.session_state.doc_input = p_data.get("documento", "")
                        st.session_state.nom_input = p_data.get("nombre_completo", "")
                        st.session_state.cel_input = p_data.get("celular", "")
                        st.session_state.dir_input = p_data.get("direccion", "")
                        st.session_state.ocu_input = p_data.get("ocupacion", "")
                        st.session_state.edad_input = p_data.get("edad", "")
                        st.toast("✅ Datos cargados correctamente.", icon="👤")
                    else:
                        st.warning("No se encontró ningún paciente con esa cédula.")

    st.markdown("<h4 style='color: #4CAF50;'>👤 Información General</h4>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        documento = st.text_input("Documento (Cédula/TI) *", key="doc_input")
        direccion = st.text_input("Dirección de Residencia", key="dir_input")
    with col2:
        nombre = st.text_input("Nombre Completo *", key="nom_input")
        ocupacion = st.text_input("Ocupación", key="ocu_input")
    with col3:
        celular = st.text_input("Número de Celular *", key="cel_input")
        edad = st.text_input("Edad", key="edad_input") 
        fecha_nacimiento = st.date_input("Fecha de Nacimiento", value=datetime(1995, 1, 1), min_value=datetime(1900, 1, 1), max_value=datetime.now(), format="DD/MM/YYYY", key="fnac_input")
        
    st.divider()
    st.markdown("<h4 style='color: #2196F3;'>👁️ Evaluación Óptica</h4>", unsafe_allow_html=True)
    col_mot, col_ctrl = st.columns([2, 1])
    with col_mot: motivo = st.text_input("Motivo de Consulta", key="mot_input")
    with col_ctrl: ultimo_control = st.text_input("Último Control (Ej: 1 año)", key="ctrl_input")

    st.markdown("##### 📝 Fórmula Óptica (Rx)")
    with st.container(border=True):
        st.markdown("**Ojo Derecho (OD)**")
        col_od1, col_od2, col_od3, col_od_space, col_od_dp = st.columns([2, 2, 2, 0.5, 2])
        with col_od1: esfera_od = st.number_input("Esfera OD", value=0.00, step=0.25, format="%.2f", key="esf_od")
        with col_od2: cilindro_od = st.number_input("Cilindro OD", value=0.00, step=0.25, format="%.2f", key="cil_od", on_change=force_negative_cyl_od)
        with col_od3: eje_od = st.number_input("Eje OD", value=0, min_value=0, max_value=180, step=1, key="eje_od")
        with col_od_dp: dp_od = st.text_input("D. Pupilar OD (mm)", placeholder="Ej: 32", key="dp_od_input")

        st.markdown("**Ojo Izquierdo (OI)**")
        col_oi1, col_oi2, col_oi3, col_oi_space, col_oi_dp = st.columns([2, 2, 2, 0.5, 2])
        with col_oi1: esfera_oi = st.number_input("Esfera OI", value=0.00, step=0.25, format="%.2f", key="esf_oi")
        with col_oi2: cilindro_oi = st.number_input("Cilindro OI", value=0.00, step=0.25, format="%.2f", key="cil_oi", on_change=force_negative_cyl_oi)
        with col_oi3: eje_oi = st.number_input("Eje OI", value=0, min_value=0, max_value=180, step=1, key="eje_oi")
        with col_oi_dp: dp_oi = st.text_input("D. Pupilar OI (mm)", placeholder="Ej: 30", key="dp_oi_input")
        
        st.write("") 
        col_ad, col_empty_ad = st.columns([2, 6])
        with col_ad: adicion = st.number_input("Adición", value=0.00, min_value=0.00, step=0.25, format="%.2f", key="add_input")
           
    obs = st.text_area("Observaciones Clínicas (Opcional)", height=100, key="obs_input")
    
    with st.container(border=True):
        st.markdown("<h5 style='color: #FF9800;'>🔒 Autorización de Datos (Habeas Data)</h5>", unsafe_allow_html=True)
        habeas_data_autorizado = st.checkbox("El paciente autoriza el tratamiento de sus datos personales y clínicos (Habeas Data) *", key="habeas_check")
        st.caption("💡 Marca esta casilla una vez el paciente confirme su autorización de forma verbal o mediante formato físico.")

    st.write("")
    submit = st.button("💾 Guardar Historia Clínica", use_container_width=True, type="primary")

    if submit:
        if not documento or not nombre or not celular:
            st.error("⚠️ Por favor, completa los campos obligatorios: Documento, Nombre y Celular.")
        elif not habeas_data_autorizado:
            st.error("⚠️ Debes confirmar la autorización de Habeas Data del paciente antes de guardar.")
        else:
            rx_od_final = build_rx_string(esfera_od, cilindro_od, eje_od)
            rx_oi_final = build_rx_string(esfera_oi, cilindro_oi, eje_oi)
            dp_combined = f"{dp_od}/{dp_oi}" if dp_od and dp_oi else (dp_od or dp_oi or "")
            adicion_final = f"{adicion:+.2f}" if adicion > 0.0 else ""

            doc_up = str(documento).upper(); nom_up = str(nombre).upper(); cel_up = str(celular).upper()
            ocu_up = str(ocupacion).upper(); dir_up = str(direccion).upper(); eda_up = str(edad).upper()
            mot_up = str(motivo).upper(); ctrl_up = str(ultimo_control).upper(); obs_up = str(obs).upper()
            fnac_str = fecha_nacimiento.strftime("%Y-%m-%d") if fecha_nacimiento else None
            habeas_fecha_str = datetime.now().isoformat()

            try:
                supabase.table("pacientes").upsert({
                    "documento": doc_up, "nombre_completo": nom_up, "celular": cel_up, "ocupacion": ocu_up, 
                    "direccion": dir_up, "edad": eda_up, "fecha_nacimiento": fnac_str,
                    "habeas_data": habeas_data_autorizado, "habeas_data_fecha": habeas_fecha_str
                }).execute()
            except Exception:
                supabase.table("pacientes").upsert({
                    "documento": doc_up, "nombre_completo": nom_up, "celular": cel_up, "ocupacion": ocu_up, 
                    "direccion": dir_up, "fecha_nacimiento": fnac_str,
                    "habeas_data": habeas_data_autorizado, "habeas_data_fecha": habeas_fecha_str
                }).execute()

            supabase.table("historias_clinicas").insert({
                "paciente_documento": doc_up, "motivo_consulta": mot_up, "rx_final_od": rx_od_final, 
                "rx_final_oi": rx_oi_final, "dp": dp_combined, "ultimo_control": ctrl_up, 
                "observaciones": obs_up, "adicion": adicion_final, "fecha": datetime.now().isoformat()
            }).execute()
            
            st.session_state.global_toast = f"Historia clínica de {nom_up} guardada correctamente."
            st.session_state.trigger_clear_doc = True
            st.rerun()

# ------------------------------------------
# MÓDULO 2: ÓPTICA Y FACTURACIÓN (UNIFICADO)
# ------------------------------------------
elif modulo == "🛍️ Óptica y Facturación":
    styled_header("Óptica y Facturación Central", "🛍️")
    
    tab_venta, tab_recaudo, tab_anular = st.tabs(["🛒 Nueva Venta y Factura", "💵 Recaudar Saldo Pendiente", "🚫 Anular Factura"])
    
    with tab_venta:
        with st.container(border=True):
            col_search, col_empty = st.columns([1, 1])
            with col_search:
                search_doc = st.text_input("🔍 Buscar por Cédula del Paciente:", placeholder="Ej: 1024585129", key="search_opt").upper()
        
        if search_doc:
            res_paciente = supabase.table("pacientes").select("*").eq("documento", search_doc).execute()
            
            if len(res_paciente.data) == 0:
                st.warning("⚠️ No se encontró ningún paciente con esa cédula en la base de datos.")
                with st.expander("➕ Registro Rápido de Paciente (Para Venta Directa)", expanded=True):
                    with st.form("form_quick_register"):
                        st.info("💡 Registra los datos básicos para facturarle a un paciente con fórmula externa.")
                        q_nom = st.text_input("Nombre Completo *").upper()
                        q_cel = st.text_input("Número de Celular *").upper()
                        q_dir = st.text_input("Dirección de Residencia").upper()
                        btn_quick = st.form_submit_button("Guardar y Continuar")
                        if btn_quick:
                            if q_nom and q_cel:
                                supabase.table("pacientes").insert({
                                    "documento": search_doc, "nombre_completo": q_nom, 
                                    "celular": q_cel, "direccion": q_dir, "habeas_data": True,
                                    "habeas_data_fecha": datetime.now().isoformat()
                                }).execute()
                                st.session_state.global_toast = "Paciente registrado rápidamente con éxito."
                                st.rerun()
                            else:
                                st.error("Nombre y Celular son obligatorios.")
            else:
                paciente = res_paciente.data[0]
                res_historias = supabase.table("historias_clinicas").select("*").eq("paciente_documento", search_doc).order("id_consulta", desc=True).execute()
                historias_data = res_historias.data or []
                
                with st.expander(f"👤 Datos Generales de: {paciente['nombre_completo']}", expanded=True):
                    st.info(f"**Documento:** {paciente['documento']} | **Celular:** {paciente['celular']} | **Dirección:** {paciente.get('direccion', 'No registrada')}")
                    if historias_data:
                        st.markdown("#### 📋 Historial Clínico Interno")
                        datos_tabla = []
                        for h in historias_data:
                            f_original = h.get("fecha") or h.get("created_at") or "Sin Fecha"
                            try: f_formateada = datetime.fromisoformat(f_original.replace("Z", "+00:00")).strftime("%d/%m/%Y - %I:%M %p") if "T" in f_original else f_original[:10]
                            except: f_formateada = f_original
                            datos_tabla.append({"Fecha Consulta": f_formateada, "OD": format_rx_ui(h.get("rx_final_od", "N/A")), "OI": format_rx_ui(h.get("rx_final_oi", "N/A")), "ADD": h.get("adicion") or "N/A", "DP": h.get("dp", "N/A")})
                        st.table(datos_tabla)
                    else:
                        st.warning("El paciente no tiene fórmulas clínicas internas guardadas.")
                
                st.divider()
                st.markdown("<h4 style='color: #4CAF50;'>🧾 Creador de Factura y Orden</h4>", unsafe_allow_html=True)
                
                try:
                    res_max = supabase.table("ventas_facturacion").select("numero_factura").order("numero_factura", desc=True).limit(1).execute()
                    sugerido = int(res_max.data[0]["numero_factura"]) + 1 if res_max.data and res_max.data[0]["numero_factura"] else 5342
                except: sugerido = 5342
                
                num_factura = st.text_input("Número de Factura", value=str(sugerido))
                factura_existe = False
                if num_factura:
                    try:
                        if len(supabase.table("ventas_facturacion").select("numero_factura").eq("numero_factura", num_factura).execute().data) > 0:
                            st.error(f"⚠️ El número de factura **{num_factura}** ya existe.")
                            factura_existe = True
                    except: pass

                st.markdown("##### 1. Titular (Pago)")
                col_t1, col_t2, col_t3 = st.columns(3)
                with col_t1: t_nombre = st.text_input("Nombre", value=paciente['nombre_completo']).upper()
                with col_t2: t_doc = st.text_input("Documento", value=paciente['documento']).upper()
                with col_t3: t_tel = st.text_input("Teléfono", value=paciente['celular']).upper()
                
                st.markdown("##### 2. Origen de la Fórmula Óptica (RX)")
                opciones_rx = ["Fórmula del Sistema (Última Visita)"] if historias_data else []
                opciones_rx.append("Fórmula Externa (Traída por el paciente)")
                origen_rx = st.radio("Selecciona qué fórmula usar:", opciones_rx, horizontal=True)
                
                historia = {}
                if origen_rx == "Fórmula del Sistema (Última Visita)":
                    historia = historias_data[0]
                    st.success("✅ Se usará la fórmula generada en el consultorio.")
                else:
                    st.info("✍️ Ingresa los datos de la fórmula externa exactamente como deseas que se impriman.")
                    col_od_ex, col_oi_ex, col_add_ex, col_dp_ex = st.columns(4)
                    rx_od_ext = col_od_ex.text_input("RX Ojo Derecho (OD)", placeholder="Ej: -1.00 -0.50 x 90°").upper()
                    rx_oi_ext = col_oi_ex.text_input("RX Ojo Izquierdo (OI)", placeholder="Ej: -1.25 -0.75 x 180°").upper()
                    add_ext = col_add_ex.text_input("Adición (ADD)", placeholder="Ej: +2.00").upper()
                    dp_ext = col_dp_ex.text_input("D. Pupilar (DP)", placeholder="Ej: 62").upper()
                    historia = {"rx_final_od": rx_od_ext if rx_od_ext else "N/A", "rx_final_oi": rx_oi_ext if rx_oi_ext else "N/A", "adicion": add_ext if add_ext else "", "dp": dp_ext if dp_ext else "N/A", "observaciones": "FÓRMULA EXTERNA"}

                st.markdown("##### 3. Prescripción y Diseño")
                tipo_gafas = st.selectbox("Impresión de Fórmula:", ["Lejos", "Cerca", "Adición (Bifocal/Progresivo)", "Dos Pares"])
                
                with st.container(border=True):
                    st.markdown("##### 4. Detalles de Venta y Finanzas")
                    origen_montura = st.radio("Montura:", ["Montura Nueva (Vitrina)", "Montura del Paciente (Solo Lentes)"], horizontal=True)
                    
                    selected_frame_code = None
                    desc_sugerida = ""
                    if origen_montura == "Montura Nueva (Vitrina)":
                        monturas = supabase.table("inventario").select("*").ilike("categoria", "Montura").gt("cantidad", 0).execute().data or []
                        if monturas:
                            opciones_monturas = [f"{m['codigo']} | {m['marca']} - {m['descripcion']} | ${format_currency_co(m['precio_venta'])}" for m in monturas]
                            montura_elegida = st.selectbox("Seleccione la Montura:", opciones_monturas)
                            selected_frame_code = montura_elegida.split(" | ")[0]
                            desc_sugerida = f"LENTES + MONTURA {montura_elegida.split(' | ')[1]}"
                        else:
                            st.warning("No hay monturas disponibles.")
                            desc_sugerida = "LENTES + MONTURA"
                    else:
                        desc_sugerida = "LENTES EN MONTURA DEL PACIENTE"

                    desc_producto = st.text_input("Descripción final:", value=desc_sugerida).upper()
                    
                    col_calc1, col_calc2, col_calc3 = st.columns(3)
                    with col_calc1: subtotal_str = st.text_input("Valor Subtotal ($)", key="subtotal_input", on_change=on_subtotal_change)
                    with col_calc2: tipo_descuento = st.selectbox("Tipo Descuento", ["Sin Descuento", "Porcentaje (%)", "Valor Fijo ($)"], key="tipo_descuento_widget", on_change=on_tipo_descuento_change)
                    with col_calc3: descuento_str = st.text_input("Descuento Aplicado", key="descuento_input", on_change=on_descuento_change)
                    
                    subtotal_val = int(clean_numeric_string(st.session_state.subtotal_input) or 0)
                    abono_val = int(clean_numeric_string(st.session_state.abono_input) or 0)
                    descuento_digits = int(clean_numeric_string(st.session_state.descuento_input) or 0)
                    
                    descuento_calculado = 0
                    if tipo_descuento == "Porcentaje (%)": descuento_calculado = int((descuento_digits / 100.0) * subtotal_val)
                    elif tipo_descuento == "Valor Fijo ($)": descuento_calculado = descuento_digits
                    
                    total_neto = int(subtotal_val - descuento_calculado)
                    saldo_pendiente = int(total_neto - abono_val)
                    
                    col_p1, col_p2, col_p3 = st.columns([1.5, 1.5, 2])
                    with col_p1: abono_str = st.text_input("Abono Inicial ($)", key="abono_input", on_change=on_abono_change)
                    with col_p2: st.metric(label="Saldo Neto Pendiente", value=f"${format_currency_co(saldo_pendiente)}")
                    with col_p3: metodo_pago = st.selectbox("Método de Pago", ["EFECTIVO", "BOLD", "LLAVE", "NEQUI", "DAVIPLATA"])

                    col_f1, col_f2 = st.columns([2, 1])
                    with col_f1: fecha_entrega = st.text_input("Fecha/Hora de Entrega", placeholder="Ej: LUNES 30 JUNIO 5:30 P.M.").upper()
                    with col_f2: alt_focal_str = st.text_input("Alt. Focal (Opc)", key="altura_focal_input", on_change=on_altura_focal_change).upper()

                with st.expander("Opcional: Detalles para Receta Clínica"):
                    col_rx1, col_rx2 = st.columns(2)
                    tipo_lente = col_rx1.selectbox("Tipo Lente", ["MONOFOCAL", "PROGRESIVO", "BIFOCAL INVISIBLE", "BIFOCAL FLAT TOP", "OCUPACIONAL", "DOS PARES"])
                    filtro = col_rx1.selectbox("Filtro", ["SIN FILTRO", "ANTIRREFLEJO", "FOTOSENSIBLE", "ANTIRREFLEJO + FOTOSENSIBLE"])
                    uso = col_rx2.selectbox("Uso", ["PERMANENTE", "PROLONGADO", "ESFUERZO VISUAL", "PROTECCIÓN"])
                    prox_control = col_rx2.text_input("Próximo Control").upper()
                    av_lejos = col_rx1.text_input("AV Lejos").upper()
                    av_cerca = col_rx2.text_input("AV Cerca").upper()
                    detalles_rx = {"tipo_lente": tipo_lente, "filtro": filtro, "uso": uso, "prox_control": prox_control, "av_lejos": av_lejos, "av_cerca": av_cerca}
                
                st.divider()
                col_btn1, col_btn2 = st.columns([1, 1])
                btn_generar_paquete = col_btn1.button("📄 Generar Factura y Órdenes", type="primary", use_container_width=True, disabled=factura_existe)
                btn_generar_rx = col_btn2.button("👁️ Generar Receta Clínica", use_container_width=True)
                
                if btn_generar_paquete:
                    if not desc_producto or subtotal_val == 0:
                        st.warning("⚠️ Debes rellenar la descripción y un subtotal válido.")
                    else:
                        venta_data = {
                            "numero_factura": num_factura, "titular_nombre": t_nombre, "titular_doc": t_doc, "titular_tel": t_tel,
                            "descripcion": desc_producto, "subtotal": subtotal_val, "descuento": descuento_calculado, "total": total_neto, 
                            "abono": abono_val, "saldo": saldo_pendiente, "fecha_entrega": fecha_entrega, "altura_focal": st.session_state.altura_focal_input,
                            "metodo_pago": metodo_pago
                        }
                        try:
                            supabase.table("ventas_facturacion").insert({
                                "numero_factura": num_factura, "paciente_documento": paciente['documento'], "titular_nombre": t_nombre,
                                "titular_doc": t_doc, "titular_tel": t_tel, "descripcion": desc_producto, "subtotal": subtotal_val,
                                "descuento": descuento_calculado, "total": total_neto, "abono": abono_val, "saldo": saldo_pendiente,
                                "fecha_entrega": fecha_entrega, "altura_focal": st.session_state.altura_focal_input, "metodo_pago": metodo_pago,
                                "estado": "ACTIVA", "estado_lab": "Pendiente de enviar", "fecha_venta": datetime.now().isoformat()
                            }).execute()
                            
                            if origen_montura == "Montura Nueva (Vitrina)" and selected_frame_code:
                                frame_data = supabase.table("inventario").select("cantidad").eq("codigo", selected_frame_code).execute().data
                                if frame_data: supabase.table("inventario").update({"cantidad": frame_data[0]["cantidad"] - 1}).eq("codigo", selected_frame_code).execute()
                                case_data = supabase.table("inventario").select("cantidad").eq("codigo", "ESTUCHE-GENERICO").execute().data
                                if case_data: supabase.table("inventario").update({"cantidad": case_data[0]["cantidad"] - 1}).eq("codigo", "ESTUCHE-GENERICO").execute()
                        except Exception as e: st.error(f"Error técnico BD: {e}")

                        pdf = FPDF(orientation="P", unit="mm", format="Letter")
                        pdf.set_compression(True)
                        hist_factura = procesar_historia_factura(historia, tipo_gafas)
                        pdf.add_page(); dibujar_media_carta(pdf, paciente, hist_factura, venta_data, "COPIA CLIENTE")
                        pdf.add_page(); dibujar_media_carta(pdf, paciente, hist_factura, venta_data, "COPIA ÓPTICA / CAJA")
                        
                        if tipo_gafas == "Dos Pares":
                            h_lejos = historia.copy(); h_lejos['adicion'] = ""
                            pdf.add_page(); dibujar_orden_laboratorio(pdf, paciente, h_lejos, venta_data, "LEJOS")
                            h_cerca = historia.copy()
                            h_cerca['rx_final_od'] = get_cerca_rx(historia.get('rx_final_od'), historia.get('adicion'))
                            h_cerca['rx_final_oi'] = get_cerca_rx(historia.get('rx_final_oi'), historia.get('adicion')); h_cerca['adicion'] = ""
                            pdf.add_page(); dibujar_orden_laboratorio(pdf, paciente, h_cerca, venta_data, "CERCA")
                        else:
                            pdf.add_page(); dibujar_orden_laboratorio(pdf, paciente, hist_factura, venta_data, "" if tipo_gafas == "Adición (Bifocal/Progresivo)" else tipo_gafas.upper())
                        
                        pdf_bytes = bytes(pdf.output())
                        st.session_state.global_toast = f"Venta registrada. Factura #{num_factura}"
                        st.download_button(label="📥 Descargar Facturación", data=pdf_bytes, file_name=f"Facturacion_{num_factura}.pdf", mime="application/pdf")
                        st.markdown(f'<iframe src="data:application/pdf;base64,{base64.b64encode(pdf_bytes).decode("utf-8")}" width="100%" height="600" type="application/pdf"></iframe>', unsafe_allow_html=True)
                        st.session_state.trigger_clear_factura = True

                if btn_generar_rx:
                    pdf_rx = FPDF(orientation="P", unit="mm", format="Letter")
                    pdf_rx.set_compression(True); pdf_rx.add_page()
                    dibujar_prescripcion_clinica(pdf_rx, paciente, historia, detalles_rx)
                    pdf_bytes_rx = bytes(pdf_rx.output())
                    st.toast("🎉 ¡Receta Clínica Generada!")
                    st.download_button(label="📥 Descargar Receta Clínica", data=pdf_bytes_rx, file_name=f"Receta_{paciente['documento']}.pdf", mime="application/pdf")
                    st.markdown(f'<iframe src="data:application/pdf;base64,{base64.b64encode(pdf_bytes_rx).decode("utf-8")}" width="100%" height="600" type="application/pdf"></iframe>', unsafe_allow_html=True)

    with tab_recaudo:
        st.markdown("<h4 style='color: #4CAF50;'>💵 Recaudar Saldo y Cambiar Estado a Entregado</h4>", unsafe_allow_html=True)
        fac_search = st.text_input("Ingrese el N° de Factura o Cédula a buscar:").upper()
        if fac_search:
            res_saldo = supabase.table("ventas_facturacion").select("*").or_(f"numero_factura.eq.{fac_search},paciente_documento.eq.{fac_search}").gt("saldo", 0).neq("estado", "ANULADA").execute()
            if res_saldo.data:
                fac_pen = res_saldo.data[0]
                saldo_actual_int = int(fac_pen['saldo']) 
                st.info(f"📌 Factura N° **{fac_pen['numero_factura']}** | Paciente: **{fac_pen['titular_nombre']}** | Estado Actual: `{fac_pen.get('estado_lab', 'Pendiente')}`")
                st.warning(f"**Saldo Pendiente Actual:** ${format_currency_co(saldo_actual_int)}")
                
                if st.session_state.last_fac_search != fac_pen['numero_factura']:
                    st.session_state.monto_rec_input = format_currency_co(saldo_actual_int)
                    st.session_state.last_fac_search = fac_pen['numero_factura']

                col_rec1, col_rec2, col_rec3 = st.columns(3)
                with col_rec1:
                    monto_rec = int(clean_numeric_string(st.text_input("Monto a Abonar/Liquidar ($)", key="monto_rec_input", on_change=on_monto_rec_change)) or 0)
                with col_rec2:
                    metodo_rec = st.selectbox("Método del Cobro", ["EFECTIVO", "BOLD", "LLAVE", "NEQUI", "DAVIPLATA"], key="met_rec")
                with col_rec3:
                    estados_posibles = ["Pendiente de enviar", "En Laboratorio", "Recibido en Óptica", "Entregado"]
                    nuevo_est_recaudo = st.selectbox("Nuevo Estado de la Factura", estados_posibles, index=3)

                st.write("")
                if st.button("✅ Registrar Pago y Actualizar Estado", type="primary", use_container_width=True):
                    if monto_rec <= 0: st.error("⚠️ Debes digitar un monto mayor a cero.")
                    elif monto_rec > saldo_actual_int: st.error(f"⚠️ El monto supera el saldo pendiente de ${format_currency_co(saldo_actual_int)}.")
                    else:
                        nuevo_saldo = saldo_actual_int - monto_rec
                        nuevo_abono = int(fac_pen['abono']) + monto_rec
                        supabase.table("ventas_facturacion").update({
                            "saldo": nuevo_saldo, 
                            "abono": nuevo_abono, 
                            "estado_lab": nuevo_est_recaudo
                        }).eq("numero_factura", fac_pen["numero_factura"]).execute()
                        
                        supabase.table("pagos_saldos").insert({
                            "numero_factura": fac_pen['numero_factura'], 
                            "paciente_documento": fac_pen['paciente_documento'], 
                            "monto_pagado": monto_rec, 
                            "metodo_pago": metodo_rec, 
                            "fecha_pago": datetime.now().isoformat()
                        }).execute()
                        
                        st.session_state.global_toast = f"Pago registrado. Nuevo saldo: ${format_currency_co(nuevo_saldo)} | Estado: {nuevo_est_recaudo}"
                        st.session_state.trigger_clear_recaudo = True
                        st.rerun()
            else:
                st.info("No se encontraron facturas activas con saldo pendiente para ese criterio.")

    with tab_anular:
        st.markdown("<h4 style='color: #F44336;'>🚫 Anulación de Facturas</h4>", unsafe_allow_html=True)
        num_anular = st.text_input("Ingrese el N° de Factura a Anular:", key="input_anular").upper()
        if num_anular:
            res_anular = supabase.table("ventas_facturacion").select("*").eq("numero_factura", num_anular).execute()
            if res_anular.data:
                fac_a = res_anular.data[0]
                if fac_a.get("estado") == "ANULADA": st.error("⚠️ Esta factura ya se encuentra ANULADA.")
                else:
                    st.warning(f"⚠️ ¿Confirmas la anulación de la Factura N° **{fac_a['numero_factura']}** de **{fac_a['titular_nombre']}** por valor de **${format_currency_co(fac_a['total'])}**?")
                    if st.button("🚨 CONFIRMAR ANULACIÓN DE FACTURA", type="primary"):
                        supabase.table("ventas_facturacion").update({"estado": "ANULADA"}).eq("numero_factura", fac_a["numero_factura"]).execute()
                        st.session_state.global_toast = "Factura ANULADA exitosamente."
                        st.session_state.global_toast_icon = "🚨"
                        st.rerun()
            else:
                st.error("No existe ninguna factura con ese número.")

# ------------------------------------------
# MÓDULO 3: CUADRE DE CAJA (FINANZAS CON BASE INICIAL)
# ------------------------------------------
elif modulo == "📊 Cuadre de Caja Físico":
    styled_header("Cuadre de Caja Físico e Historial Diario", "📊")
    
    col_fc1, col_fc2 = st.columns([2, 1])
    with col_fc1:
        fecha_consulta = st.date_input("Selecciona la fecha a consultar:", datetime.now().date())
    with col_fc2:
        base_caja_inicial = st.number_input("Base Inicial en Gaveta ($)", min_value=0, value=50000, step=10000)

    fecha_str = fecha_consulta.strftime("%Y-%m-%d")
    
    tab_resumen, tab_gastos = st.tabs(["💰 Resumen y Movimientos", "💸 Registrar Gasto de Caja"])

    ventas = supabase.table("ventas_facturacion").select("*").gte("fecha_venta", f"{fecha_str}T00:00:00").lte("fecha_venta", f"{fecha_str}T23:59:59").neq("estado", "ANULADA").execute().data or []
    recaudos = supabase.table("pagos_saldos").select("*").gte("fecha_pago", f"{fecha_str}T00:00:00").lte("fecha_pago", f"{fecha_str}T23:59:59").execute().data or []
    gastos = supabase.table("gastos_caja").select("*").gte("fecha_gasto", f"{fecha_str}T00:00:00").lte("fecha_gasto", f"{fecha_str}T23:59:59").execute().data or []

    with tab_resumen:
        abono_efectivo = sum(v.get('abono', 0) for v in ventas if str(v.get('metodo_pago') or '').upper() == 'EFECTIVO')
        abono_bancos = sum(v.get('abono', 0) for v in ventas if str(v.get('metodo_pago') or '').upper() != 'EFECTIVO')
        
        recaudo_efectivo = sum(r.get('monto_pagado', 0) for r in recaudos if str(r.get('metodo_pago') or '').upper() == 'EFECTIVO')
        recaudo_bancos = sum(r.get('monto_pagado', 0) for r in recaudos if str(r.get('metodo_pago') or '').upper() != 'EFECTIVO')
        
        gastos_efectivo = sum(g.get('monto', 0) for g in gastos if str(g.get('metodo_pago') or '').upper() == 'EFECTIVO')

        efectivo_caja = base_caja_inicial + (abono_efectivo + recaudo_efectivo) - gastos_efectivo
        total_bancos = abono_bancos + recaudo_bancos

        st.markdown("<h4 style='color: #4CAF50;'>💵 Arqueo de Caja</h4>", unsafe_allow_html=True)
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("💵 Efectivo Físico (En Gaveta)", f"${format_currency_co(efectivo_caja)}")
        col_m2.metric("🏦 Total Bancos (Digital)", f"${format_currency_co(total_bancos)}")
        col_m3.metric("✅ Flujo Total Diario", f"${format_currency_co(efectivo_caja + total_bancos + gastos_efectivo - base_caja_inicial)}")

        st.divider()
        st.markdown(f"#### 📜 Movimientos de Caja del Día ({fecha_str})")
        
        movimientos = [{"Hora": "08:00", "Tipo": "BASE", "Detalle": "Apertura de Caja Inicial", "Monto": base_caja_inicial, "Método": "EFECTIVO"}]
        for v in ventas:
            if v.get('abono', 0) > 0: movimientos.append({"Hora": v['fecha_venta'][11:16], "Tipo": "VENTA", "Detalle": f"Fac #{v['numero_factura']} - {v['titular_nombre']}", "Monto": v['abono'], "Método": v['metodo_pago']})
        for r in recaudos:
            movimientos.append({"Hora": r['fecha_pago'][11:16], "Tipo": "RECAUDO", "Detalle": f"Saldo Fac #{r['numero_factura']}", "Monto": r['monto_pagado'], "Método": r['metodo_pago']})
        for g in gastos:
            movimientos.append({"Hora": g['fecha_gasto'][11:16], "Tipo": "GASTO", "Detalle": str(g['descripcion']).upper(), "Monto": -g['monto'], "Método": g['metodo_pago']})
        
        if movimientos:
            df_mov = pd.DataFrame(movimientos).sort_values(by="Hora", ascending=False)
            
            def color_mov(val):
                if isinstance(val, (int, float)): return f"color: {'#ff4b4b' if val < 0 else '#00c04b'}; font-weight: bold;"
                return ""
                
            st.dataframe(df_mov.style.map(color_mov, subset=['Monto']).format({"Monto": lambda x: f"${format_currency_co(abs(x))}"}), use_container_width=True)
            st.download_button(label="📊 Descargar Historial a Excel (.xlsx)", data=convert_df_to_excel(df_mov, "Caja"), file_name=f"Movimientos_{fecha_str}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.info("No hay movimientos financieros en la fecha seleccionada.")

    with tab_gastos:
        st.markdown("<h4 style='color: #F44336;'>💸 Registrar Salida de Dinero (Gasto)</h4>", unsafe_allow_html=True)
        col_g1, col_g2, col_g3 = st.columns([2, 1, 1])
        with col_g1: desc_gasto = st.text_input("Concepto / Descripción del Gasto", placeholder="Ej: Pago mensajería laboratorio").upper()
        with col_g2: monto_gasto = int(clean_numeric_string(st.text_input("Valor ($)", key="monto_gasto_input", on_change=on_monto_gasto_change)) or 0)
        with col_g3: metodo_gasto = st.selectbox("Forma de Salida", ["EFECTIVO", "BOLD", "NEQUI", "DAVIPLATA"])
        
        if st.button("💾 Guardar Gasto de Caja", type="primary"):
            if not desc_gasto or monto_gasto <= 0: st.warning("⚠️ Ingresa una descripción y valor válidos.")
            else:
                supabase.table("gastos_caja").insert({"descripcion": desc_gasto, "monto": monto_gasto, "metodo_pago": metodo_gasto, "fecha_gasto": datetime.now().isoformat()}).execute()
                st.session_state.global_toast = "Gasto registrado correctamente."
                st.session_state.trigger_clear_gastos = True
                st.rerun()

# ------------------------------------------
# MÓDULO 4: INVENTARIO BODEGA
# ------------------------------------------
elif modulo == "📦 Inventario (Bodega)":
    styled_header("Gestión de Bodega y Vitrinas", "📦")
    tab_catalogo, tab_ingreso, tab_ajuste = st.tabs(["📋 Catálogo y Stock", "➕ Registrar Producto", "🔄 Ajuste Rápido"])
    
    with tab_catalogo:
        inventario = supabase.table("inventario").select("*").order("marca").execute().data or []
        if inventario:
            tabla_inv = []
            inv_total = 0
            potencial = 0
            for p in inventario:
                cant = int(p.get("cantidad", 0))
                compra = int(p.get("precio_compra", 0))
                venta = int(p.get("precio_venta", 0))
                inv_total += (cant * compra)
                potencial += (cant * venta)
                tabla_inv.append({"Código": str(p.get("codigo", "")), "Categoría": str(p.get("categoria", "")), "Marca": str(p.get("marca", "")).upper(), "Descripción": str(p.get("descripcion", "")).upper(), "Cant.": cant, "Costo": compra, "P. Venta": venta})
            
            df_inv = pd.DataFrame(tabla_inv)
            st.dataframe(df_inv.style.format({"Costo": lambda x: f"${format_currency_co(x)}", "P. Venta": lambda x: f"${format_currency_co(x)}"}), use_container_width=True)
            st.download_button(label="📊 Exportar Inventario", data=convert_df_to_excel(df_inv, "Bodega"), file_name="Inventario.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            
            st.divider()
            c1, c2, c3 = st.columns(3)
            c1.info(f"**Stock Total:** {sum(i['Cant.'] for i in tabla_inv)} unds")
            c2.warning(f"**Inversión:** ${format_currency_co(inv_total)}")
            c3.success(f"**Ganancia Proyectada:** ${format_currency_co(potencial - inv_total)}")
        else:
            st.info("La bodega está vacía.")

    with tab_ingreso:
        st.caption("💡 Sugerencia: Crea 'ESTUCHE-GENERICO' para que se descuente automáticamente al vender monturas.")
        with st.container(border=True):
            col_i1, col_i2 = st.columns(2)
            with col_i1:
                inv_codigo = st.text_input("Código *", key="inv_codigo").upper()
                inv_categoria = st.selectbox("Categoría", ["Montura", "Lente de Contacto", "Accesorio", "Estuche", "Líquido", "Otro"])
                inv_marca = st.text_input("Marca *", key="inv_marca").upper()
            with col_i2:
                inv_desc = st.text_input("Descripción *", key="inv_desc").upper()
                inv_prov = st.text_input("Proveedor", key="inv_prov").upper()
                inv_cant = st.number_input("Cantidad Inicial", min_value=0, step=1, value=1)
            
            c1, c2 = st.columns(2)
            with c1: val_compra = int(clean_numeric_string(st.text_input("Precio Compra $", key="p_compra_input", on_change=on_p_compra_change)) or 0)
            with c2: val_venta = int(clean_numeric_string(st.text_input("Precio Venta $", key="p_venta_input", on_change=on_p_venta_change)) or 0)
                
            if st.button("💾 Guardar Producto", type="primary", use_container_width=True):
                if not inv_codigo or not inv_marca or not inv_desc: st.error("⚠️ Código, Marca y Descripción son obligatorios.")
                else:
                    try:
                        supabase.table("inventario").insert({"codigo": inv_codigo, "categoria": inv_categoria, "marca": inv_marca, "descripcion": inv_desc, "proveedor": inv_prov, "cantidad": inv_cant, "precio_compra": val_compra, "precio_venta": val_venta, "fecha_ingreso": datetime.now().isoformat()}).execute()
                        st.session_state.global_toast = f"Producto '{inv_codigo}' registrado."
                        st.session_state.trigger_clear_inv = True
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")

    with tab_ajuste:
        codigo_ajuste = st.text_input("Buscar por Código:").upper()
        if codigo_ajuste:
            res_prod = supabase.table("inventario").select("*").eq("codigo", codigo_ajuste).execute()
            if res_prod.data:
                prod = res_prod.data[0]
                stock = int(prod["cantidad"])
                st.info(f"**{prod['marca']}** - {prod['descripcion']} | Stock: **{stock}**")
                c1, c2, c3 = st.columns([1, 1, 2])
                with c1: accion = st.radio("Acción:", ["Sumar (+)", "Restar (-)"])
                with c2: cant_ajustar = st.number_input("Cantidad", min_value=1, step=1, value=1)
                with c3:
                    st.write(""); st.write("")
                    if st.button("Actualizar Stock", type="primary", use_container_width=True):
                        nuevo_stock = stock + cant_ajustar if accion == "Sumar (+)" else stock - cant_ajustar
                        if nuevo_stock < 0: st.error("⚠️ Stock negativo.")
                        else:
                            supabase.table("inventario").update({"cantidad": nuevo_stock}).eq("codigo", codigo_ajuste).execute()
                            st.session_state.global_toast = f"Stock actualizado a {nuevo_stock}."
                            st.rerun()

# ------------------------------------------
# MÓDULO 5: CONTROL DE LABORATORIO
# ------------------------------------------
elif modulo == "🔬 Control de Laboratorios":
    styled_header("Trazabilidad y Laboratorios", "🔬")
    
    tab_trabajos, tab_labs = st.tabs(["📋 Control de Trabajos", "⚙️ Gestionar Laboratorios"])
    
    with tab_labs:
        st.markdown("#### Configuración de Laboratorios Externos")
        nuevo_lab = st.text_input("Agregar Nuevo Laboratorio:", placeholder="Ej: OPTILAB BOGOTÁ").upper()
        if st.button("➕ Añadir Laboratorio", type="primary"):
            if nuevo_lab:
                try:
                    supabase.table("laboratorios").insert({"nombre": nuevo_lab}).execute()
                    st.session_state.global_toast = "Laboratorio añadido correctamente."
                    st.rerun()
                except Exception as e:
                    st.error("⚠️ Es posible que este laboratorio ya exista o falte crear la tabla en Supabase.")
        
        st.divider()
        labs_db = supabase.table("laboratorios").select("*").execute().data or []
        if labs_db:
            st.markdown("**Laboratorios Registrados:**")
            for l in labs_db:
                st.markdown(f"🏭 `{l['nombre']}`")
        else:
            st.info("Aún no has registrado laboratorios externos.")

    with tab_trabajos:
        col_b1, col_b2 = st.columns(2)
        search_fac_lab = col_b1.text_input("🔍 Buscar por N° Factura:").upper()
        filtro_estado = col_b2.selectbox("Filtrar trabajos por estado:", ["Todos los Activos", "Pendiente de enviar", "En Laboratorio", "Recibido en Óptica", "Entregado"])
        
        query_lab = supabase.table("ventas_facturacion").select("*").neq("estado", "ANULADA")
        if filtro_estado != "Todos los Activos": query_lab = query_lab.eq("estado_lab", filtro_estado)
        if search_fac_lab: query_lab = query_lab.eq("numero_factura", search_fac_lab)
            
        trabajos = query_lab.order("fecha_venta", desc=True).execute().data or []
        opciones_labs = ["NO ASIGNADO"] + [l['nombre'] for l in (supabase.table("laboratorios").select("nombre").execute().data or [])]
        
        if trabajos:
            for t in trabajos:
                est_act = t.get("estado_lab", "Pendiente de enviar")
                
                if est_act == "Pendiente de enviar": 
                    border_color = "#f44336"; badge_bg = "#ffebee"; badge_fg = "#c62828"
                elif est_act == "En Laboratorio": 
                    border_color = "#ff9800"; badge_bg = "#fff3e0"; badge_fg = "#ef6c00"
                elif est_act == "Recibido en Óptica": 
                    border_color = "#2196F3"; badge_bg = "#e3f2fd"; badge_fg = "#1565c0"
                else: 
                    border_color = "#4CAF50"; badge_bg = "#e8f5e9"; badge_fg = "#2e7d32"
                
                with st.container(border=True):
                    st.markdown(f"""
                        <div style="border-left: 5px solid {border_color}; padding-left: 10px; margin-bottom: 8px;">
                            <span style="background-color: {badge_bg}; color: {badge_fg}; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 0.85em;">{est_act.upper()}</span>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    c1, c2, c3 = st.columns([2, 2, 2])
                    with c1:
                        st.markdown(f"**Fac N°:** `{t['numero_factura']}`")
                        st.markdown(f"**Titular:** {t['titular_nombre']}")
                        st.markdown(f"**Detalle:** {t['descripcion']}")
                    with c2:
                        st.markdown(f"**Entrega:** `{t['fecha_entrega']}`")
                        if int(t.get('saldo', 0)) > 0: st.markdown(f"**Saldo:** ${format_currency_co(int(t['saldo']))}")
                        else: st.markdown("**Pagado 100%** ✅")
                    with c3:
                        posibles = ["Pendiente de enviar", "En Laboratorio", "Recibido en Óptica", "Entregado"]
                        idx_est = posibles.index(est_act) if est_act in posibles else 0
                        nuevo_est = st.selectbox(f"Estado de la Factura", posibles, index=idx_est, key=f"est_{t['numero_factura']}")
                        
                        lab_act = t.get("laboratorio") or "NO ASIGNADO"
                        idx_lab = opciones_labs.index(lab_act) if lab_act in opciones_labs else 0
                        nuevo_lab_sel = st.selectbox(f"Laboratorio Externo:", opciones_labs, index=idx_lab, key=f"lab_{t['numero_factura']}")
                        
                        if nuevo_est != est_act or nuevo_lab_sel != lab_act:
                            if st.button(f"💾 Guardar #{t['numero_factura']}", key=f"btn_est_{t['numero_factura']}", type="primary"):
                                supabase.table("ventas_facturacion").update({"estado_lab": nuevo_est, "laboratorio": nuevo_lab_sel if nuevo_lab_sel != "NO ASIGNADO" else None}).eq("numero_factura", t['numero_factura']).execute()
                                st.session_state.global_toast = f"Trabajo actualizado a: {nuevo_est}"
                                st.rerun()
        else:
            st.info("No hay trabajos registrados con esos filtros.")

# ------------------------------------------
# MÓDULO 6: CRM Y FIDELIZACIÓN
# ------------------------------------------
elif modulo == "📅 CRM y Fidelización":
    styled_header("CRM y Retención de Pacientes", "📅")
    
    hoy = datetime.now()
    if hoy.day == 1:
        st.success(f"🔔 **¡Hoy inicia un nuevo mes!** Es el momento perfecto para revisar la lista de cumpleaños y enviar recordatorios de control anual a tus pacientes.")
    
    tab_anual, tab_cumple, tab_directorio, tab_plantillas = st.tabs(["🔄 Control Anual", "🎂 Cumpleaños", "📞 Directorio", "⚙️ Plantillas WhatsApp"])
    
    if "tpl_anual" not in st.session_state:
        st.session_state.tpl_anual = "¡Hola [NOMBRE]! Te saludamos de Boomerang Visión 👓. Ha pasado un año desde tu último examen visual y queremos invitarte a tu control anual para cuidar de tu salud visual. ¿Te gustaría agendar una cita?"
    if "tpl_cumple" not in st.session_state:
        st.session_state.tpl_cumple = "¡Feliz cumpleaños, [NOMBRE]! 🥳 Te deseamos un día maravilloso de parte de todo el equipo de Boomerang Visión. Queremos regalarte un descuento especial del 20% en tu próximo par de lentes o montura en este mes. ¡Te esperamos!"

    with tab_anual:
        historias_todas = supabase.table("historias_clinicas").select("*").execute().data or []
        pacientes_para_llamar = []
        for h in historias_todas:
            f_str = h.get("fecha")
            if f_str:
                try:
                    f_dt = datetime.fromisoformat(f_str.replace("Z", "+00:00")).date() if "T" in f_str else datetime.strptime(f_str[:10], "%Y-%m-%d").date()
                    if 330 <= (hoy.date() - f_dt).days <= 400:
                        p_info = supabase.table("pacientes").select("*").eq("documento", h.get("paciente_documento")).execute().data
                        if p_info:
                            pacientes_para_llamar.append({"Documento": p_info[0].get("documento"), "Nombre": p_info[0].get("nombre_completo"), "Celular": p_info[0].get("celular"), "Ultima_Consulta": f_dt.strftime("%d/%m/%Y")})
                except: pass
        if pacientes_para_llamar:
            st.info(f"Se encontraron **{len(pacientes_para_llamar)}** pacientes para control anual.")
            for item in pacientes_para_llamar:
                nombre_corto = item['Nombre'].split()[0]
                msg_final = st.session_state.tpl_anual.replace("[NOMBRE]", nombre_corto)
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 2])
                    c1.markdown(f"**👤 {str(item['Nombre']).upper()}**\n\nCédula: {item['Documento']} | Última visita: {item['Ultima_Consulta']}")
                    c2.markdown(f"📱 Cel: `{item['Celular']}`")
                    c3.link_button("💬 Enviar WhatsApp", get_whatsapp_link(item['Celular'], msg_final), use_container_width=True)
        else: st.info("No hay pacientes cumpliendo un año de su última consulta.")

    with tab_cumple:
        todos_pacientes = supabase.table("pacientes").select("*").execute().data or []
        cumpleañeros = []
        for p in todos_pacientes:
            fnac = p.get("fecha_nacimiento")
            if fnac:
                try:
                    fnac_dt = datetime.fromisoformat(fnac.replace("Z", "+00:00")).date() if isinstance(fnac, str) else fnac
                    if fnac_dt.month == hoy.month:
                        edad = hoy.year - fnac_dt.year - ((hoy.month, hoy.day) < (fnac_dt.month, fnac_dt.day))
                        cumpleañeros.append({"Documento": p.get("documento"), "Nombre": str(p.get("nombre_completo", "")).upper(), "Celular": p.get("celular", "N/A"), "Nacimiento": fnac_dt.strftime("%d/%m/%Y"), "Edad": edad})
                except: pass
        if cumpleañeros:
            st.info(f"¡Hay **{len(cumpleañeros)}** pacientes de cumpleaños este mes!")
            for c in cumpleañeros:
                nombre_corto = c['Nombre'].split()[0]
                msg_cumple = st.session_state.tpl_cumple.replace("[NOMBRE]", nombre_corto)
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 2])
                    c1.markdown(f"🎂 **{c['Nombre']}** (Cumple {c['Edad']} años)\n\nCédula: {c['Documento']}")
                    c2.markdown(f"📱 Cel: `{c['Celular']}`")
                    c3.link_button("🎁 Enviar Felicitación", get_whatsapp_link(c['Celular'], msg_cumple), use_container_width=True)
        else: st.info("No hay pacientes registrados con fecha de nacimiento en el mes actual.")

    with tab_directorio:
        busqueda_dir = st.text_input("🔍 Filtrar por nombre o cédula:").upper()
        tabla_dir = [{"Documento": str(p.get("documento", "")), "Nombre": str(p.get("nombre_completo", "")).upper(), "Celular": p.get("celular", "N/A"), "F. Nacimiento": p.get("fecha_nacimiento", "N/A"), "Habeas Data": "Sí" if p.get("habeas_data") else "No"} for p in todos_pacientes if not busqueda_dir or busqueda_dir in str(p.get("nombre_completo", "")).upper() or busqueda_dir in str(p.get("documento", ""))]
        if tabla_dir:
            df_dir = pd.DataFrame(tabla_dir)
            st.dataframe(df_dir, use_container_width=True)
            st.download_button("📊 Descargar Directorio (.xlsx)", convert_df_to_excel(df_dir, "Pacientes"), "Directorio.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else: st.info("No hay registros que coincidan.")

    with tab_plantillas:
        st.markdown("#### Personaliza tus Mensajes de WhatsApp")
        st.caption("Usa la etiqueta [NOMBRE] para insertar automáticamente el nombre del paciente.")
        st.session_state.tpl_anual = st.text_area("Plantilla Control Anual", value=st.session_state.tpl_anual, height=100)
        st.session_state.tpl_cumple = st.text_area("Plantilla Cumpleaños", value=st.session_state.tpl_cumple, height=100)
        if st.button("💾 Guardar Plantillas", type="primary"):
            st.success("¡Plantillas actualizadas correctamente para esta sesión!")

# ------------------------------------------
# MÓDULO 7: ANALÍTICA, ESTADÍSTICAS Y RESPALDO MAESTRO
# ------------------------------------------
elif modulo == "📈 Analítica y Estadísticas":
    styled_header("Dashboard Analítico y Respaldo General", "📈")
    
    ventas_db = supabase.table("ventas_facturacion").select("*").neq("estado", "ANULADA").execute().data or []
    gastos_db = supabase.table("gastos_caja").select("*").execute().data or []
    
    if ventas_db:
        df_dash = pd.DataFrame(ventas_db)
        df_dash['fecha_venta'] = pd.to_datetime(df_dash['fecha_venta'])
        df_dash['mes_anio'] = df_dash['fecha_venta'].dt.strftime('%Y-%m')
        
        total_cartera_pendiente = df_dash['saldo'].sum()
        
        modo_analitica = st.radio("Modo de Visualización:", ["Resumen Global", "Filtrar por Mes Específico", "Comparativa Multimes"], horizontal=True)
        meses_disponibles = sorted(df_dash['mes_anio'].unique(), reverse=True)
        
        if modo_analitica == "Filtrar por Mes Específico":
            mes_sel = st.selectbox("Selecciona el mes a analizar:", meses_disponibles)
            df_filtered = df_dash[df_dash['mes_anio'] == mes_sel]
            gastos_filtered = [g for g in gastos_db if datetime.fromisoformat(g['fecha_gasto'].replace("Z", "+00:00")).strftime('%Y-%m') == mes_sel] if gastos_db else []
            
            total_recaudado = df_filtered['total'].sum()
            total_facturas = len(df_filtered)
            promedio = total_recaudado / total_facturas if total_facturas > 0 else 0
            total_gastos = sum(g.get("monto", 0) for g in gastos_filtered)
            
            st.markdown(f"#### 🎯 Resumen Financiero - {mes_sel}")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("💰 Ventas del Mes", f"${format_currency_co(total_recaudado)}")
            m2.metric("💸 Gastos Operativos", f"${format_currency_co(total_gastos)}", delta="- Salidas", delta_color="inverse")
            m3.metric("📈 Ganancia Neta Mes", f"${format_currency_co(total_recaudado - total_gastos)}")
            m4.metric("📊 Ticket Promedio", f"${format_currency_co(promedio)}")
            
            st.info(f"📌 **Dinero de saldos por cobrar:** ${format_currency_co(total_cartera_pendiente)}")
            
        elif modo_analitica == "Comparativa Multimes":
            meses_sel = st.multiselect("Selecciona los meses a comparar:", meses_disponibles, default=meses_disponibles[:min(2, len(meses_disponibles))])
            if meses_sel:
                df_comp = df_dash[df_dash['mes_anio'].isin(meses_sel)]
                st.markdown("#### 📊 Comparativa Financiera por Mes")
                
                tabla_comp = []
                for m in sorted(meses_sel):
                    df_m = df_comp[df_comp['mes_anio'] == m]
                    ventas_m = df_m['total'].sum()
                    fact_m = len(df_m)
                    gastos_m = sum(g.get("monto", 0) for g in gastos_db if datetime.fromisoformat(g['fecha_gasto'].replace("Z", "+00:00")).strftime('%Y-%m') == m)
                    tabla_comp.append({"Mes": m, "Ventas Brutas": ventas_m, "Gastos": gastos_m, "Ganancia Neta": ventas_m - gastos_m, "N° Facturas": fact_m})
                
                df_tabla_comp = pd.DataFrame(tabla_comp)
                st.dataframe(df_tabla_comp.style.format({"Ventas Brutas": lambda x: f"${format_currency_co(x)}", "Gastos": lambda x: f"${format_currency_co(x)}", "Ganancia Neta": lambda x: f"${format_currency_co(x)}"}), use_container_width=True)
                st.bar_chart(df_tabla_comp.set_index('Mes')[['Ventas Brutas', 'Ganancia Neta']])
            else:
                st.warning("Selecciona al menos un mes para la comparativa.")
        else:
            total_recaudado = df_dash['total'].sum()
            total_facturas = len(df_dash)
            promedio = total_recaudado / total_facturas if total_facturas > 0 else 0
            total_gastos = sum(g.get("monto", 0) for g in gastos_db)
            
            st.markdown("#### 🎯 Resumen Financiero Histórico Global")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("💰 Ventas Brutas", f"${format_currency_co(total_recaudado)}")
            m2.metric("💸 Gastos Operativos", f"${format_currency_co(total_gastos)}", delta="- Salidas", delta_color="inverse")
            m3.metric("📈 Ganancia Neta", f"${format_currency_co(total_recaudado - total_gastos)}")
            m4.metric("📊 Ticket Promedio", f"${format_currency_co(promedio)}")
            
            st.info(f"📌 **Dinero de saldos por cobrar:** ${format_currency_co(total_cartera_pendiente)}")
            
            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**📅 Tendencia de Ventas (Mensual)**")
                st.bar_chart(df_dash.groupby('mes_anio')['total'].sum().reset_index().set_index('mes_anio'), color="#4CAF50")
                
                st.markdown("**💳 Uso de Métodos de Pago**")
                if 'metodo_pago' in df_dash.columns:
                    st.bar_chart(df_dash['metodo_pago'].value_counts().reset_index().set_index('metodo_pago'), color="#2196F3")
                    
            with c2:
                st.markdown("**🏭 Ranking de Laboratorios (Asignaciones)**")
                if 'laboratorio' in df_dash.columns:
                    labs_count = df_dash['laboratorio'].fillna('NO ASIGNADO').value_counts().reset_index()
                    st.bar_chart(labs_count.set_index('laboratorio'), color="#FF9800")
                else:
                    st.info("Aún no has asignado facturas a laboratorios externos.")
                    
                st.markdown("**🔥 Top 5 de Ventas Más Altas**")
                top_ventas = df_dash[['numero_factura', 'titular_nombre', 'total', 'fecha_venta']].sort_values(by='total', ascending=False).head(5)
                top_ventas['fecha_venta'] = top_ventas['fecha_venta'].dt.strftime('%d/%m/%Y')
                st.dataframe(top_ventas.style.format({"total": lambda x: f"${format_currency_co(x)}"}), use_container_width=True)

        st.divider()
        st.markdown("#### 💾 Respaldo Total de Base de Datos (Master Backup)")
        st.caption("Descarga un archivo Excel con todas las tablas críticas del sistema para tu respaldo local.")
        if st.button("📥 Generar Respaldo Completo en Excel", type="primary"):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                p_data = supabase.table("pacientes").select("*").execute().data
                if p_data: pd.DataFrame(p_data).to_excel(writer, index=False, sheet_name="Pacientes")
                
                h_data = supabase.table("historias_clinicas").select("*").execute().data
                if h_data: pd.DataFrame(h_data).to_excel(writer, index=False, sheet_name="HistoriasClinicas")
                
                v_data = supabase.table("ventas_facturacion").select("*").execute().data
                if v_data: pd.DataFrame(v_data).to_excel(writer, index=False, sheet_name="VentasFacturacion")
                
                i_data = supabase.table("inventario").select("*").execute().data
                if i_data: pd.DataFrame(i_data).to_excel(writer, index=False, sheet_name="Inventario")
                
                g_data = supabase.table("gastos_caja").select("*").execute().data
                if g_data: pd.DataFrame(g_data).to_excel(writer, index=False, sheet_name="GastosCaja")
            
            excel_bytes = output.getvalue()
            st.download_button(
                label="📥 Descargar Master Backup (.xlsx)",
                data=excel_bytes,
                file_name=f"MasterBackup_BoomerangVision_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.info("No hay suficientes registros en la base de datos.")