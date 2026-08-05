import streamlit as st
from supabase import create_client
import os
import base64
import io
import urllib.parse
import re
import calendar
import pandas as pd
import altair as alt
from dotenv import load_dotenv
from fpdf import FPDF
from datetime import datetime, timezone, timedelta
import bcrypt

# =====================================================================
# 1. CONFIGURACIÓN INICIAL DE PÁGINA Y ESTILOS (MODO CLARO CON ACENTOS SUAVES)
# =====================================================================
# Zona horaria Colombia GMT-5
def now_co():
    """Retorna datetime actual en hora Colombia (GMT-5)."""
    return datetime.now(timezone(timedelta(hours=-5)))

st.set_page_config(page_title="Boomerang Visión", layout="wide", page_icon="👓", initial_sidebar_state="expanded")

# ============ CSS MEJORADO ============
st.markdown("""
    <style>
        /* ==========================================================
           BOOMERANG VISIÓN – ESTILOS GLOBALES (MODO CLARO)
           Paleta: negro #000, blanco #fff, rojo suave #e57373
           ========================================================== */

        /* --- 1. Estructura base --- */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        .stApp {
            background-color: #ffffff !important;
        }

        /* --- 2. Barra lateral --- */
        [data-testid="stSidebar"] {
            background-color: #f0f0f0 !important;
        }
        [data-testid="stSidebar"] * {
            color: #000000 !important;
        }

        /* --- 3. Tipografía general --- */
        h1, h2, h3, h4, h5, h6 {
            color: #000000 !important;
        }
        /* Etiqueta de riesgo: la regla "div, span" es demasiado amplia
           y puede pintarse encima de colores de alerta; limitamos al texto
           principal evitando sobreescribir componentes específicos. */
        p, label {
            color: #000000 !important;
        }

        /* --- 4. VARIABLES COMPARTIDAS DE CAMPO DE ENTRADA ---
           Todos los inputs (text, number, date, textarea, select)
           comparten un único bloque de reglas para garantizar
           uniformidad y evitar declaraciones duplicadas que
           creen bordes dobles o cortados.
        */

        /* 4a. Limpiar contenedores intermedios de Streamlit.
               Streamlit envuelve cada widget en 1-3 divs antes
               de llegar al elemento nativo; esos divs no deben
               tener borde propio ni fondo de color para no
               interferir con el borde del elemento interior. */
        .stTextInput > div,
        .stTextInput > div > div,
        .stNumberInput > div,
        .stNumberInput > div > div,
        .stTextArea > div,
        .stTextArea > div > div,
        .stDateInput > div,
        .stDateInput > div > div,
        .stSelectbox > div,
        .stSelectbox > div > div {
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
            outline: none !important;
        }

        /* 4b. Elemento nativo: input, textarea y el control
               interno de BaseWeb para selectbox.
               Usamos box-sizing: border-box para que el
               border-radius y el padding no rompan el ancho. */
        .stTextInput input,
        .stNumberInput input,
        .stTextArea textarea,
        .stDateInput input {
            background-color: #f2f2f2 !important;
            border: 1.5px solid #b0b0b0 !important;
            border-radius: 6px !important;
            color: #000000 !important;
            padding: 8px 12px !important;
            font-size: 15px !important;
            box-sizing: border-box !important;
            box-shadow: none !important;
            outline: none !important;
            width: 100% !important;
            transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
        }

        /* 4c. Selectbox — borde solo en el control, no en el label
               El div[data-testid="stSelectbox"] contiene tanto el label como el control.
               Si le ponemos borde al wrapper entero, el label queda dentro del recuadro
               (feo). La solución: wrapper sin borde, y usamos :last-child para apuntar
               solo al div del control de BaseWeb — selector estructural que React no pisa. */

        /* Wrapper externo: sin borde, solo posicionamiento */
        div[data-testid="stSelectbox"] {
            background-color: transparent !important;
            border: none !important;
            padding: 0 !important;
        }

        /* Label del selectbox: estilo limpio, fuera del recuadro */
        div[data-testid="stSelectbox"] > label {
            font-size: 14px !important;
            font-weight: 500 !important;
            color: #000000 !important;
            margin-bottom: 4px !important;
            display: block !important;
        }

        /* El control visible: el div que envuelve al BaseWeb select.
           Usamos > div:last-child que apunta al contenedor del control
           (después del label), estable estructuralmente ante re-renders. */
        div[data-testid="stSelectbox"] > div:last-child {
            background-color: #f2f2f2 !important;
            border: 1.5px solid #b0b0b0 !important;
            border-radius: 6px !important;
        }

        /* Todos los divs internos de BaseWeb: transparent */
        div[data-testid="stSelectbox"] [data-baseweb="select"],
        div[data-testid="stSelectbox"] [data-baseweb="select"] > div,
        div[data-testid="stSelectbox"] [data-baseweb="select"] > div > div,
        div[data-testid="stSelectbox"] div[role="combobox"] {
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
            outline: none !important;
        }

        /* Control BaseWeb primer div — altura y padding consistentes con inputs */
        div[data-testid="stSelectbox"] [data-baseweb="select"] > div:first-child {
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
            min-height: 38px !important;
            padding: 6px 10px !important;
        }

        /* Texto del valor seleccionado */
        div[data-testid="stSelectbox"] [data-baseweb="select"] span,
        div[data-testid="stSelectbox"] [data-baseweb="select"] p {
            color: #000000 !important;
            background-color: transparent !important;
            font-size: 15px !important;
        }

        /* Flecha chevron */
        div[data-testid="stSelectbox"] [data-baseweb="select"] svg {
            fill: #555555 !important;
        }

        /* Foco: borde rojo suave en el control */
        div[data-testid="stSelectbox"] > div:last-child:focus-within {
            border-color: #e57373 !important;
            box-shadow: 0 0 0 3px rgba(229,115,115,0.20) !important;
        }

        /* Menú desplegable (popover) */
        [data-baseweb="popover"] {
            border-radius: 8px !important;
            overflow: hidden !important;
        }
        [data-baseweb="popover"] [data-baseweb="menu"] {
            background-color: #f8f8f8 !important;
            border: 1.5px solid #b0b0b0 !important;
            border-radius: 8px !important;
            box-shadow: 0 4px 16px rgba(0,0,0,0.10) !important;
        }
        [data-baseweb="popover"] [role="option"] {
            background-color: #f8f8f8 !important;
            color: #000000 !important;
            padding: 9px 14px !important;
            font-size: 14px !important;
        }
        [data-baseweb="popover"] [role="option"]:hover {
            background-color: #fce4e4 !important;
            color: #000000 !important;
        }
        [data-baseweb="popover"] [aria-selected="true"] {
            background-color: #f5c2c2 !important;
            color: #000000 !important;
            font-weight: 600 !important;
        }

                /* 4d. Multiselect — misma estrategia: borde solo en el control, label afuera */
        div[data-testid="stMultiSelect"] {
            background-color: transparent !important;
            border: none !important;
            padding: 0 !important;
        }
        div[data-testid="stMultiSelect"] > div:last-child {
            background-color: #f2f2f2 !important;
            border: 1.5px solid #b0b0b0 !important;
            border-radius: 6px !important;
        }
        div[data-testid="stMultiSelect"] [data-baseweb="select"],
        div[data-testid="stMultiSelect"] [data-baseweb="select"] > div,
        div[data-testid="stMultiSelect"] [data-baseweb="select"] > div:first-child {
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
        }
        div[data-testid="stMultiSelect"] > div:last-child:focus-within {
            border-color: #e57373 !important;
            box-shadow: 0 0 0 3px rgba(229,115,115,0.20) !important;
        }
        div[data-testid="stMultiSelect"] [data-baseweb="tag"] {
            background-color: #f5c2c2 !important;
            border-radius: 4px !important;
            color: #000000 !important;
            border: 1px solid #d0a0a0 !important;
        }

                /* 4e. Foco: borde rojo suave + glow discreto.
               Para el selectbox se usa :focus-within porque
               el foco real cae en el <input> hijo oculto. */
        .stTextInput input:focus,
        .stNumberInput input:focus,
        .stTextArea textarea:focus,
        .stDateInput input:focus {
            border-color: #e57373 !important;
            box-shadow: 0 0 0 3px rgba(229, 115, 115, 0.25) !important;
            outline: none !important;
        }
        .stSelectbox [data-baseweb="select"] > div:first-child:focus-within,
        .stMultiSelect [data-baseweb="select"] > div:first-child:focus-within {
            border-color: #e57373 !important;
            box-shadow: 0 0 0 3px rgba(229, 115, 115, 0.25) !important;
        }

        /* --- 5. Botones --- */
        .stButton > button {
            background-color: #f5c2c2 !important;
            color: #000000 !important;
            border: 1px solid #d0a0a0 !important;
            border-radius: 6px !important;
            font-weight: 600 !important;
            padding: 6px 16px !important;
            transition: background-color 0.2s ease, box-shadow 0.2s ease !important;
        }
        .stButton > button:hover {
            background-color: #e8a8a8 !important;
            color: #000000 !important;
            box-shadow: 0 2px 6px rgba(0,0,0,0.12) !important;
        }
        .stButton > button:active {
            background-color: #d48c8c !important;
        }
        /* Botón primario explícito (type="primary") */
        .stButton > button[kind="primary"] {
            background-color: #e57373 !important;
            color: #ffffff !important;
            border-color: #c62828 !important;
        }
        .stButton > button[kind="primary"]:hover {
            background-color: #ef9a9a !important;
            color: #000000 !important;
        }

        /* --- 6. Tabs --- */
        .stTabs [data-baseweb="tab-list"] {
            background-color: #f0f0f0 !important;
            border-radius: 6px 6px 0 0 !important;
            gap: 2px !important;
        }
        .stTabs [data-baseweb="tab"] {
            color: #555555 !important;
            border-radius: 6px 6px 0 0 !important;
            font-weight: 500 !important;
        }
        .stTabs [aria-selected="true"] {
            background-color: #ffffff !important;
            color: #c62828 !important;
            border-bottom: 2px solid #e57373 !important;
            font-weight: 700 !important;
        }
        .stTabs [data-baseweb="tab"]:hover {
            background-color: #e8e8e8 !important;
            color: #000000 !important;
        }

        /* --- 7. Dataframes / tablas --- */
        .stDataFrame {
            background-color: #ffffff !important;
        }
        .stDataFrame thead th {
            background-color: #f0f0f0 !important;
            color: #000000 !important;
            border: 1px solid #d0d0d0 !important;
            font-weight: 700 !important;
        }
        .stDataFrame tbody td {
            color: #000000 !important;
            border: 1px solid #e0e0e0 !important;
        }

        /* --- 8. Alertas (success, info, warning, error) ---
               NO forzamos color negro en * porque los iconos SVG
               de Streamlit usan fill que se rompería. Solo
               actuamos sobre el texto. */
        .stAlert {
            background-color: #f9f9f9 !important;
            border-radius: 6px !important;
        }
        .stAlert p, .stAlert span {
            color: #000000 !important;
        }

        /* --- 9. Expander --- */
        details > summary {
            background-color: #f0f0f0 !important;
            color: #000000 !important;
            border-radius: 6px !important;
            padding: 8px 12px !important;
        }
        details[open] > summary {
            border-radius: 6px 6px 0 0 !important;
        }
        details > div {
            background-color: #ffffff !important;
            border: 1px solid #e0e0e0 !important;
            border-top: none !important;
            border-radius: 0 0 6px 6px !important;
            padding: 12px !important;
        }

        /* --- 10. Checkbox, radio, toggle --- */
        .stCheckbox label span,
        .stRadio label span {
            color: #000000 !important;
        }

        /* --- 11. Métricas (st.metric) --- */
        [data-testid="stMetricValue"] {
            color: #000000 !important;
        }
        [data-testid="stMetricLabel"] {
            color: #555555 !important;
        }

        /* --- 12. Contenedores con borde (st.container(border=True)) --- */
        /* Base: borde gris estándar para todos los containers */
        [data-testid="stVerticalBlockBorderWrapper"] {
            border: 1px solid #d0d0d0 !important;
            border-radius: 10px !important;
            overflow: hidden !important;
            padding-bottom: 6px !important;
        }

        /* --- 12b. Tarjetas de laboratorio coloreadas por estado ---
           El JS dentro de cada tarjeta escribe el atributo data-estado
           en su propio stVerticalBlockBorderWrapper. Estos selectores de
           atributo tienen mayor especificidad que la regla base de arriba
           y sobreescriben el border-left con el color del estado. */
        [data-testid="stVerticalBlockBorderWrapper"][data-estado="Pendiente de enviar"],
        [data-testid="stVerticalBlockBorderWrapper"][data-estado="Pendiente de enviar"] > div[data-testid="stVerticalBlock"] {
            border-left: 6px solid #E61B23 !important;
            background-color: #fff5f5 !important;
        }
        [data-testid="stVerticalBlockBorderWrapper"][data-estado="En Laboratorio"],
        [data-testid="stVerticalBlockBorderWrapper"][data-estado="En Laboratorio"] > div[data-testid="stVerticalBlock"] {
            border-left: 6px solid #ff9800 !important;
            background-color: #fffaf2 !important;
        }
        [data-testid="stVerticalBlockBorderWrapper"][data-estado="Recibido en Óptica"],
        [data-testid="stVerticalBlockBorderWrapper"][data-estado="Recibido en Óptica"] > div[data-testid="stVerticalBlock"] {
            border-left: 6px solid #2196F3 !important;
            background-color: #f3f8ff !important;
        }
        [data-testid="stVerticalBlockBorderWrapper"][data-estado="Entregado"],
        [data-testid="stVerticalBlockBorderWrapper"][data-estado="Entregado"] > div[data-testid="stVerticalBlock"] {
            border-left: 6px solid #4CAF50 !important;
            background-color: #f4fdf4 !important;
        }

        /* --- 13. Spinner / Progress --- */
        .stProgress > div > div {
            background-color: #e57373 !important;
        }

    </style>
""", unsafe_allow_html=True)

# =====================================================================
# 2. CONEXIÓN A SUPABASE
# =====================================================================
# Compatible con Streamlit Cloud (st.secrets) y desarrollo local (.env)
load_dotenv()
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
except Exception:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

@st.cache_resource
def init_connection():
    return create_client(url, key)

supabase = init_connection()

# Parche JS global: fuerza estilos de borde en selectbox después de cada re-render
# (Streamlit Cloud inyecta estilos inline que sobreescriben el CSS; este JS los pisa de vuelta)
st.markdown("""
    <script>
    (function() {
        function styleSelects() {
            // Apuntamos al ultimo div hijo de stSelectbox/stMultiSelect:
            // ese es el contenedor del control de BaseWeb, justo despues del label.
            // Asi el borde rodea solo el control, no el label → estetica limpia.
            [
                'div[data-testid="stSelectbox"]',
                'div[data-testid="stMultiSelect"]'
            ].forEach(function(sel) {
                document.querySelectorAll(sel).forEach(function(wrapper) {
                    // Outer wrapper: sin borde ni fondo
                    wrapper.style.setProperty('background-color', 'transparent', 'important');
                    wrapper.style.setProperty('border', 'none', 'important');
                    // Last child: el control visual
                    var ctrl = wrapper.lastElementChild;
                    if (ctrl) {
                        ctrl.style.setProperty('background-color', '#f2f2f2', 'important');
                        ctrl.style.setProperty('border', '1.5px solid #b0b0b0', 'important');
                        ctrl.style.setProperty('border-radius', '6px', 'important');
                    }
                });
            });
            // Todos los divs internos de BaseWeb: transparent
            document.querySelectorAll(
                'div[data-testid="stSelectbox"] [data-baseweb="select"], ' +
                'div[data-testid="stSelectbox"] [data-baseweb="select"] > div, ' +
                'div[data-testid="stMultiSelect"] [data-baseweb="select"], ' +
                'div[data-testid="stMultiSelect"] [data-baseweb="select"] > div'
            ).forEach(function(el) {
                el.style.setProperty('background-color', 'transparent', 'important');
                el.style.setProperty('border', 'none', 'important');
                el.style.setProperty('box-shadow', 'none', 'important');
            });
        }
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', styleSelects);
        } else {
            styleSelects();
        }
        var obs = new MutationObserver(function(muts) {
            if (muts.some(function(m) { return m.addedNodes.length > 0; })) {
                clearTimeout(window._sst);
                window._sst = setTimeout(styleSelects, 80);
            }
        });
        obs.observe(document.body, { childList: true, subtree: true });
    })();
    </script>
""", unsafe_allow_html=True)

@st.cache_data(ttl=60, show_spinner=False)
def query_cached(tabla, filtros=None):
    """Cache de 60 s para consultas de solo lectura frecuentes."""
    q = supabase.table(tabla).select("*")
    if filtros:
        for col, val in filtros.items():
            q = q.eq(col, val)
    return q.execute().data or []

# =====================================================================
# 3. SISTEMA DE AUTENTICACIÓN Y ROLES LOCALES (PERSISTENCIA DIARIA)
# =====================================================================
# ── Usuarios del sistema ──────────────────────────────────────────────
# Para agregar o cambiar contraseñas usa el script tools/hash_password.py
# NUNCA escribas contraseñas en texto plano en este archivo.
USUARIOS_PERMITIDOS = {
    "1022396649": {"hash": "$2b$12$gFAaYBKx9MbY6LmB5jzlyua138yntPOt70A4vMek48tf7ar//iAVW", "nombre": "Dr. Mateo F.", "rol": "admin", "id": "1022396649"},
    "1024585129": {"hash": "$2b$12$B/6vCxYqn3UIhacSuTd/C.9AtZwQeHjVdLqpA8hLpc1RwhFx/A7zy", "nombre": "Dr. Juan Pablo", "rol": "admin", "id": "1024585129"},
    "39667008": {"hash": "$2b$12$d20TxP8RA0VcZUIRDYS0OeZb1aj7ZJjFbFYxWYf5fq1tqDsC.t.ZG", "nombre": "Rosa (Asesora)", "rol": "admin", "id": "39667008"},
    "79203712": {"hash": "$2b$12$utxfnI7yKTFK3bu/RckDiOeHLgk2wu6iGp5KUR30QYUlbuSdj2qWO", "nombre": "Nelson (Asesor)", "rol": "admin", "id": "79203712"},
    "asesor":     {"hash": "$2b$12$.qveRTit/Shp7AytkdWGveb6kl6fHPvJ9iMecNzFRII1kB19uMSl2", "nombre": "Asesor Invitado", "rol": "asesor_limitado", "id": "asesor"},
    "doctor":     {"hash": "$2b$12$v0DR0MvszR5DM2FCMotUqeHqCyc9bPqnZzs6v4.V06ibN9g2/oAvK", "nombre": "Doctor Invitado", "rol": "doctor_limitado", "id": "doctor"}
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
        if token_date == now_co().strftime("%Y-%m-%d") and token_user_id in USUARIOS_PERMITIDOS:
            st.session_state.user_info = USUARIOS_PERMITIDOS[token_user_id]
    except Exception: pass

if not st.session_state.user_info:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col_l1, col_l2, col_l3 = st.columns([1, 1.2, 1])
    with col_l2:
        with st.container(border=True):
            # Solo usamos logo.png (modo claro)
            b64_logo = get_image_base64("logo.png")
            if b64_logo:
                st.markdown(f'<div style="text-align: center;"><img src="data:image/png;base64,{b64_logo}" width="80%"></div><br>', unsafe_allow_html=True)
            else:
                st.markdown("<h2 style='text-align: center; color:#000000;'>👓 Boomerang Visión</h2>", unsafe_allow_html=True)
            
            st.markdown("<p style='text-align: center; color: #555;'>Ingreso al Sistema Central</p>", unsafe_allow_html=True)
            user_input = st.text_input("Usuario (Documento)")
            pass_input = st.text_input("Contraseña", type="password")
            
            if st.button("🔐 Iniciar Sesión", type="primary", use_container_width=True):
                user_clean = user_input.strip().lower()
                if user_clean in USUARIOS_PERMITIDOS and bcrypt.checkpw(pass_input.strip().encode(), USUARIOS_PERMITIDOS[user_clean]["hash"].encode()):
                    st.session_state.user_info = USUARIOS_PERMITIDOS[user_clean]
                    nuevo_token = base64.b64encode(f"{user_clean}||{now_co().strftime('%Y-%m-%d')}".encode("utf-8")).decode("utf-8")
                    st.query_params["auth_token"] = nuevo_token
                    st.rerun()
                else:
                    st.error("⚠️ Usuario o contraseña incorrectos.")
    st.stop()

# =====================================================================
# 4. FUNCIONES DE FORMATEO Y PDF (sin cambios)
# =====================================================================
def clean_numeric_string(val_str):
    val = str(val_str).strip()
    if not val: return ""
    return "".join(c for c in val if c.isdigit())

def valor_numerico_factura(numero_factura):
    """
    Extrae el valor numérico de un numero_factura para ORDENAR, sin
    importar si es real ('5422'), legado ('LEG-2385', 'LEG-TR00001')
    o una venta menor ('MEN-20260805114523123456'). Como TRABAJOS.xlsx
    y REGISTRO_DIARIO.xlsx comparten la misma numeración secuencial del
    negocio, ordenar por este valor da un orden cronológico confiable
    -- más confiable que fecha_venta como texto, que puede tener
    inconsistencias de formato entre orígenes. Las ventas menores usan
    un timestamp como número, que naturalmente las ordena de últimas
    (son siempre las más recientes al momento de crearse).
    """
    nf = str(numero_factura or "")
    if nf.startswith("LEG-"):
        resto = nf[4:]
        if resto.startswith("TR"):
            resto = resto[2:]
        resto = resto.split("-", 1)[0]  # quita sufijo de desambiguación (-B, -C...)
    elif nf.startswith("MEN-"):
        resto = nf[4:]
    else:
        resto = nf
    try:
        return int(resto)
    except ValueError:
        return -1  # no interpretable: al final


def formatear_numero_factura_display(numero_factura):
    """
    Solo para VISUALIZACIÓN: convierte 'LEG-TR02385' -> '2385' y
    'LEG-2670' -> '2670'. Preserva sufijos de desambiguación
    ('LEG-2347-B' -> '2347-B'). Las ventas menores ('MEN-...') se
    muestran como 'Venta menor'. Las facturas reales (sin prefijo
    especial) se muestran tal cual. El valor original completo se
    sigue usando internamente para keys de widgets y operaciones en BD.
    """
    nf = str(numero_factura or "")
    if nf.startswith("MEN-"):
        return "Venta menor"
    if not nf.startswith("LEG-"):
        return nf
    resto = nf[4:]
    if resto.startswith("TR"):
        resto = resto[2:]
    partes = resto.split("-", 1)
    numero = partes[0].lstrip("0") or "0"
    sufijo = f"-{partes[1]}" if len(partes) > 1 else ""
    return f"{numero}{sufijo}"


def filtro_busqueda_factura(termino):
    """
    Construye la parte 'numero_factura.eq...' de un filtro .or_() que
    encuentra una factura sin importar si el usuario escribió el
    número corto ('2385') o el formato completo. Cubre las dos
    variantes de prefijo legado que existen en la BD:
      - 'LEG-{numero_trabajo}'      (cuando el Excel sí traía número)
      - 'LEG-TR{contador:05d}'      (cuando no traía número)
    Devuelve una lista de condiciones para unir con coma en .or_().
    """
    t = str(termino or "").strip().upper()
    if not t:
        return []
    condiciones = [f"numero_factura.eq.{t}"]
    if t.isdigit():
        condiciones.append(f"numero_factura.eq.LEG-{t}")
        condiciones.append(f"numero_factura.eq.LEG-TR{t.zfill(5)}")
    return condiciones


def _fecha_gasto_seguro(fecha_str):
    """
    Parsea fecha_gasto (formato ISO8601, mezcla de precisiones entre
    gastos nuevos y migrados) a 'YYYY-MM'. Nunca lanza excepción:
    devuelve None ante un valor vacío o corrupto en vez de tumbar
    la página completa de Analítica.
    """
    if not fecha_str:
        return None
    try:
        return datetime.fromisoformat(str(fecha_str).replace("Z", "+00:00")).strftime('%Y-%m')
    except (ValueError, TypeError):
        return None


def traer_todas_las_filas(tabla, filtros_fn=None, orden_col=None, orden_desc=True, columnas="*"):
    """
    Trae TODAS las filas de una tabla, sin importar el límite de 1000
    filas por request que aplica por defecto la API de Supabase.
    Pagina en bloques de 1000 usando .range() hasta agotar los datos.

    filtros_fn: función opcional que recibe la query y le aplica
    filtros (.eq(), .neq(), etc.) antes de paginar.
    columnas: string de columnas para .select(), por defecto todas.
    """
    BLOQUE = 1000
    todas = []
    inicio = 0
    while True:
        q = supabase.table(tabla).select(columnas)
        if filtros_fn:
            q = filtros_fn(q)
        if orden_col:
            q = q.order(orden_col, desc=orden_desc)
        bloque = q.range(inicio, inicio + BLOQUE - 1).execute().data or []
        todas.extend(bloque)
        if len(bloque) < BLOQUE:
            break
        inicio += BLOQUE
    return todas


def normalizar_texto_busqueda(v):
    """Mayúsculas, sin tildes, espacios colapsados -- para agrupar identidades."""
    if not v:
        return ""
    s = str(v).strip().upper()
    reemplazos = {"Á":"A","É":"E","Í":"I","Ó":"O","Ú":"U","Ñ":"N","Ü":"U"}
    for a, b in reemplazos.items():
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


def _buscar_candidatos_historial(query_texto):
    """
    Busca por documento, nombre, celular o N° de factura/trabajo en las
    tablas YA UNIFICADAS: pacientes, historias_clinicas (incluye legado
    vía nombre_legado/celular_legado) y ventas_facturacion (incluye
    legado vía titular_nombre/titular_doc/titular_tel, con numero_factura
    prefijado "LEG-" para los históricos).
    Devuelve un dict {clave_identidad: {documento, nombre, celular,
    activo, n_legado}}.
    """
    q_upper = normalizar_texto_busqueda(query_texto)
    q_digits = "".join(c for c in query_texto if c.isdigit())

    pac_matches, hc_matches, vf_matches = [], [], []
    error_busqueda = None
    try:
        filtros_pac = []
        if q_digits:
            filtros_pac += [f"documento.eq.{q_digits}", f"celular.eq.{q_digits}"]
        if q_upper:
            filtros_pac.append(f"nombre_completo.ilike.%{q_upper}%")
        if filtros_pac:
            pac_matches = supabase.table("pacientes").select("*") \
                .or_(",".join(filtros_pac)).limit(20).execute().data

        filtros_hc = []
        if q_digits:
            filtros_hc += [f"paciente_documento.eq.{q_digits}",
                            f"celular_legado.eq.{q_digits}"]
        if q_upper:
            filtros_hc.append(f"nombre_legado.ilike.%{q_upper}%")
        if filtros_hc:
            hc_matches = supabase.table("historias_clinicas").select("*") \
                .or_(",".join(filtros_hc)).limit(50).execute().data

        filtros_vf = []
        if q_digits:
            filtros_vf += [f"paciente_documento.eq.{q_digits}",
                            f"titular_doc.eq.{q_digits}",
                            f"titular_tel.eq.{q_digits}"]
            filtros_vf += filtro_busqueda_factura(q_digits)
        if q_upper:
            filtros_vf.append(f"titular_nombre.ilike.%{q_upper}%")
        if filtros_vf:
            vf_matches = supabase.table("ventas_facturacion").select("*") \
                .or_(",".join(filtros_vf)).limit(50).execute().data
    except Exception as e:
        error_busqueda = str(e)

    identidades = {}

    def _clave(doc, nombre):
        doc_limpio = "".join(c for c in str(doc or "") if c.isdigit())
        if doc_limpio:
            return f"DOC:{doc_limpio}"
        return f"NOM:{normalizar_texto_busqueda(nombre)}"

    for p in pac_matches:
        k = _clave(p.get("documento"), p.get("nombre_completo"))
        identidades.setdefault(k, {"documento": p.get("documento"),
                                    "nombre": p.get("nombre_completo"),
                                    "celular": p.get("celular"),
                                    "activo": False, "n_legado": 0})
        identidades[k]["activo"] = True
        identidades[k]["documento"] = p.get("documento") or identidades[k]["documento"]
        identidades[k]["nombre"] = p.get("nombre_completo") or identidades[k]["nombre"]

    for h in hc_matches:
        nombre_h = h.get("nombre_legado") or ""
        k = _clave(h.get("paciente_documento"), nombre_h)
        identidades.setdefault(k, {"documento": h.get("paciente_documento"),
                                    "nombre": nombre_h,
                                    "celular": h.get("celular_legado"),
                                    "activo": False, "n_legado": 0})
        if h.get("origen") == "LEGADO":
            identidades[k]["n_legado"] += 1

    for v in vf_matches:
        nombre_v = v.get("titular_nombre") or ""
        k = _clave(v.get("paciente_documento") or v.get("titular_doc"), nombre_v)
        identidades.setdefault(k, {"documento": v.get("paciente_documento") or v.get("titular_doc"),
                                    "nombre": nombre_v,
                                    "celular": v.get("titular_tel"),
                                    "activo": False, "n_legado": 0})
        if v.get("origen") == "LEGADO":
            identidades[k]["n_legado"] += 1

    return identidades, error_busqueda


def _cargar_detalle_historial(doc_sel, nombre_sel):
    """
    Carga el historial completo (ficha activa + historias + ventas) para
    una identidad ya resuelta, filtrando por documento si existe, o por
    nombre exacto cuando la identidad no tiene documento vinculado.
    """
    if doc_sel:
        pac_hist = supabase.table("pacientes").select("*").eq("documento", doc_sel).execute().data
        hist_data = supabase.table("historias_clinicas").select("*").eq("paciente_documento", doc_sel).order("fecha", desc=True).execute().data
        ventas_data = supabase.table("ventas_facturacion").select("*").eq("paciente_documento", doc_sel).execute().data
    else:
        pac_hist = []
        hist_data = supabase.table("historias_clinicas").select("*").eq("nombre_legado", nombre_sel).order("fecha", desc=True).execute().data
        ventas_data = supabase.table("ventas_facturacion").select("*").eq("titular_nombre", nombre_sel).execute().data
    # Orden por número de factura real, no por fecha_venta como texto
    # (mismo criterio que Control de Trabajos, ver valor_numerico_factura).
    if ventas_data:
        ventas_data = sorted(ventas_data, key=lambda v: valor_numerico_factura(v.get("numero_factura")), reverse=True)
    return pac_hist, hist_data, ventas_data


def mostrar_buscador_historial(key_prefix):
    """
    Renderiza el buscador de historial completo (búsqueda multi-criterio
    + selector de candidatos + detalle). Reutilizable desde cualquier
    módulo -- key_prefix evita colisiones de session_state entre usos.
    """
    st.caption("Busca por cédula, nombre, celular o N° de factura/trabajo. Incluye "
               "historias e información de venta activas, y también registros de "
               "años anteriores migrados desde archivos antiguos, aunque no sean "
               "una historia clínica o factura completa.")
    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        query_hist = st.text_input(
            "Cédula, nombre, celular o N° de factura:", key=f"{key_prefix}_query"
        ).strip()
    with col_h2:
        st.write(""); st.write("")
        buscar_hist = st.button("Buscar", key=f"{key_prefix}_btn", use_container_width=True)

    if buscar_hist and query_hist:
        with st.spinner("Buscando..."):
            identidades, error_busqueda = _buscar_candidatos_historial(query_hist)
        if error_busqueda:
            st.caption(f"⚠️ Ocurrió un problema al buscar ({error_busqueda}).")
        st.session_state[f"{key_prefix}_candidatos"] = identidades
        st.session_state[f"{key_prefix}_query_hecha"] = query_hist
        st.session_state[f"{key_prefix}_sel"] = None

    candidatos = st.session_state.get(f"{key_prefix}_candidatos")
    if candidatos is None:
        return

    if len(candidatos) == 0:
        st.error(f"No se encontró ningún registro para "
                 f"“{st.session_state.get(f'{key_prefix}_query_hecha','')}”.")
        return

    sel_info = None
    if len(candidatos) == 1:
        sel_info = list(candidatos.values())[0]
    else:
        sel_key = st.session_state.get(f"{key_prefix}_sel")
        if sel_key and sel_key in candidatos:
            # Ya hay una selección: se oculta la lista larga para que el
            # detalle aparezca inmediatamente, sin tener que hacer scroll
            # a través de todos los demás candidatos.
            sel_info = candidatos[sel_key]
            if st.button("🔙 Ver los demás resultados", key=f"{key_prefix}_volver"):
                st.session_state[f"{key_prefix}_sel"] = None
                st.rerun()
            st.caption(f"Mostrando: **{sel_info['nombre'] or '—'}** "
                       f"(de {len(candidatos)} coincidencias para "
                       f"“{st.session_state.get(f'{key_prefix}_query_hecha','')}”)")
        else:
            st.markdown(f"##### Se encontraron **{len(candidatos)}** coincidencias — selecciona una:")
            for k, info in candidatos.items():
                with st.container(border=True):
                    cc1, cc2, cc3 = st.columns([3, 2, 1])
                    etiqueta_activo = " · ✅ Paciente activo" if info["activo"] else ""
                    cc1.markdown(f"**{info['nombre'] or '—'}**{etiqueta_activo}")
                    cc2.markdown(f"Doc: `{info['documento'] or '—'}` · "
                                 f"Tel: `{info['celular'] or '—'}` · "
                                 f"{info['n_legado']} registro(s) legado")
                    if cc3.button("Ver", key=f"{key_prefix}_ver_{k}", use_container_width=True):
                        st.session_state[f"{key_prefix}_sel"] = k
                        st.rerun()

    if not sel_info:
        return

    doc_sel = sel_info.get("documento")
    nombre_sel = sel_info.get("nombre")

    with st.spinner("Cargando historial completo..."):
        pac_hist, hist_data, ventas_data = _cargar_detalle_historial(doc_sel, nombre_sel)

    st.divider()

    if pac_hist:
        p = pac_hist[0]
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"**👤 {str(p.get('nombre_completo','')).upper()}**")
            c2.markdown(f"**📱** {p.get('celular','N/A')}")
            c3.markdown(f"**🎂** {p.get('fecha_nacimiento','N/A')}")
    else:
        aviso = "no está registrado como paciente activo" if not doc_sel else \
                "este documento no está registrado como paciente activo"
        st.warning(f"⚠️ {nombre_sel or 'Este contacto'} {aviso}, "
                   f"pero se encontraron registros históricos abajo.")

    # --- Historias clínicas (actuales y legado, ya unificadas) ---
    if hist_data:
        st.markdown(f"##### 📋 {len(hist_data)} historia(s) clínica(s)")
        for h in hist_data:
            fecha_fmt = (h.get("fecha") or "")[:10]
            try:
                fecha_fmt = datetime.strptime(fecha_fmt, "%Y-%m-%d").strftime("%d/%m/%Y")
            except Exception:
                pass
            es_legado = h.get("origen") == "LEGADO"
            titulo_extra = " · 📜 LEGADO" if es_legado else ""
            if h.get("pendiente_revisar") in (True, "true", "True"):
                titulo_extra += " · ⚠️ PENDIENTE POR REVISAR"
            with st.container(border=True):
                hc1, hc2 = st.columns([1, 3])
                hc1.markdown(f"**📅 {fecha_fmt}**{titulo_extra}")
                hc2.markdown(f"**Motivo:** {h.get('motivo_consulta','—') or '—'}")
                rx_od = h.get("rx_final_od", "")
                rx_oi = h.get("rx_final_oi", "")
                dp = h.get("dp", "")
                add = h.get("adicion", "")
                obs = h.get("observaciones", "")
                if rx_od or rx_oi:
                    st.markdown(f"**Rx OD:** `{rx_od}`  |  **Rx OI:** `{rx_oi}`" + (f"  |  **D.P.:** `{dp}`" if dp else "") + (f"  |  **Adición:** `{add}`" if add else ""))
                if obs:
                    st.caption(f"📝 {obs}")

    # --- Ventas / trabajos (actuales y legado, ya unificadas) ---
    if ventas_data:
        st.markdown(f"##### 🛍️ {len(ventas_data)} venta(s) / trabajo(s)")
        for v in ventas_data:
            fecha_fmt = (v.get("fecha_venta") or "")[:10]
            try:
                fecha_fmt = datetime.strptime(fecha_fmt, "%Y-%m-%d").strftime("%d/%m/%Y")
            except Exception:
                pass
            es_legado = v.get("origen") == "LEGADO"
            etiqueta = f"🛠️ Fac. {formatear_numero_factura_display(v.get('numero_factura','—'))} — {fecha_fmt}"
            if es_legado:
                etiqueta += " · 📜 LEGADO"
            with st.expander(etiqueta):
                st.markdown(f"**Detalle:** {v.get('descripcion','—')}")
                info_extra = []
                if v.get("total"):
                    try:
                        info_extra.append(f"**Total:** ${format_currency_co(int(float(v['total'])))}")
                    except Exception:
                        pass
                if v.get("estado_lab"):
                    info_extra.append(f"**Estado:** {v['estado_lab']}")
                if v.get("laboratorio"):
                    info_extra.append(f"**Laboratorio:** {v['laboratorio']}")
                if info_extra:
                    st.markdown(" · ".join(info_extra))
                if es_legado:
                    st.caption("⚠️ Registro histórico migrado: se asume saldado (sin desglose "
                               "de abonos originales). No participa del cuadre de caja actual.")

    if not hist_data and not ventas_data and not pac_hist:
        st.info("No hay historias ni ventas asociadas a este contacto todavía.")


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

def styled_header(text, icon="", badge_html=""):
    st.markdown(f"""
        <div style="display:flex; align-items:center; justify-content:space-between;
                    border-bottom: 2px solid #f5c2c2; padding-bottom:10px; margin-bottom:20px;">
            <h3 style='font-weight:700; margin:0; color:#000000;'>{icon} {text}</h3>
            {badge_html}
        </div>
    """, unsafe_allow_html=True)

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
    if len(parts) < 3:
        # Texto que contiene 'X' pero no sigue el formato "esf cil Xeje"
        # (puede pasar con Fórmula Externa, que es texto libre). Se
        # muestra tal cual en vez de intentar forzarlo a la cuadrícula.
        return rx_str.upper(), "", ""
    esf = "NEUTRO" if parts[0] in ['N', 'NEUTRO'] else parts[0].upper()
    cil = parts[1]; eje = parts[2].upper()
    return esf, cil, eje


def rx_string_a_numeros(rx_str):
    """
    Inverso de build_rx_string(): convierte '+1.75 -0.75 x 0°' de vuelta
    a (esfera, cilindro, eje) como floats/int, para prellenar los
    number_input al editar una fórmula ya guardada. Nunca lanza
    excepción -- ante cualquier formato no reconocido, devuelve ceros.
    """
    if not rx_str or str(rx_str).upper() in ("N/A", "NEUTRO", ""):
        return 0.0, 0.0, 0
    try:
        s = str(rx_str).upper().replace('X', ' ').replace('°', '')
        parts = s.split()
        if len(parts) == 1:
            return float(parts[0]), 0.0, 0
        if len(parts) >= 3:
            return float(parts[0]), float(parts[1]), int(float(parts[2]))
    except (ValueError, IndexError):
        pass
    return 0.0, 0.0, 0

# =====================================================================
# 5. FUNCIONES DE DIBUJO DE PDF (se mantienen igual, solo usan logo.png)
# =====================================================================
def dibujar_media_carta(pdf, paciente, historia, venta, tipo_documento, logo_path="logo.png", fecha_impresion=None):
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
    pdf.cell(65, 6, (fecha_impresion or now_co()).strftime("%d/%m/%Y %H:%M"), border=1)
    
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

def dibujar_orden_laboratorio(pdf, paciente, historia, venta, tipo_orden="", logo_path="logo.png", fecha_impresion=None):
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
    pdf.set_font("helvetica", "", 9); pdf.cell(55, 6, (fecha_impresion or now_co()).strftime("%d/%m/%Y %H:%M"), border="T,B", ln=1)
    
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

def dibujar_prescripcion_clinica(pdf, paciente, historia, detalles_rx, logo_path="logo.png", fecha_impresion=None):
    pdf.set_font("helvetica", "B", 10)
    if os.path.exists(logo_path): pdf.image(logo_path, x=10, y=10, w=45)
    pdf.set_xy(60, 10); pdf.set_font("helvetica", "", 9)
    pdf.cell(80, 5, "Boomerang Vision MF", ln=1)
    pdf.set_x(60); pdf.cell(80, 5, "C.C. UNISUR Local 1114 Soacha", ln=1)
    pdf.set_x(60); pdf.cell(80, 5, "Teléfono 6019045922", ln=1)
    
    pdf.set_xy(120, 15); pdf.set_font("helvetica", "B", 16)
    pdf.cell(85, 8, "PRESCRIPCION OPTICA", align="C", ln=1)
    if str(historia.get('observaciones', '')).upper() == "FÓRMULA EXTERNA":
        pdf.set_xy(120, 23); pdf.set_font("helvetica", "BI", 9); pdf.set_text_color(180, 0, 0)
        pdf.cell(85, 5, "*** FÓRMULA EXTERNA ***", align="C", ln=1); pdf.set_text_color(0, 0, 0)
    
    pdf.ln(5); y_start = 28
    pdf.set_xy(10, y_start); pdf.set_font("helvetica", "I", 8)
    pdf.cell(110, 4, "Nombre del paciente:", border="L,T,R"); pdf.cell(25, 4, "Fecha", border=1, align="C")
    pdf.set_font("helvetica", "", 9); pdf.cell(60, 4, (fecha_impresion or now_co()).strftime("%d/%m/%Y %I:%M %p"), border=1, align="C", ln=1)

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
    # av_od/av_oi (por ojo) tienen prioridad; av_lejos (compartido) queda
    # como respaldo para llamadas antiguas que no separan por ojo.
    av_od = detalles_rx.get('av_od') or detalles_rx.get('av_lejos', '')
    av_oi = detalles_rx.get('av_oi') or detalles_rx.get('av_lejos', '')
    pdf.cell(30, 6, dp_od, border=1, align="C"); pdf.cell(40, 6, av_od.upper(), border=1, align="C", ln=1)
    
    pdf.set_xy(30, y4+6); pdf.cell(25, 6, "IZQUIERDO", border=1, align="C")
    esf_oi, cil_oi, eje_oi = parse_for_grid(historia.get('rx_final_oi'))
    pdf.cell(30, 6, esf_oi, border=1, align="C"); pdf.cell(30, 6, cil_oi, border=1, align="C"); pdf.cell(20, 6, eje_oi, border=1, align="C")
    pdf.cell(30, 6, dp_oi, border=1, align="C"); pdf.cell(40, 6, av_oi.upper(), border=1, align="C", ln=1)
    
    y5 = pdf.get_y(); pdf.set_x(10)
    pdf.cell(20, 12, "CERCA", border=1, align="C")
    
    pdf.set_xy(30, y5); pdf.cell(25, 6, "DERECHO", border=1, align="C")
    add_str = format_add(historia.get('adicion'))
    cerca_esf = f"{add_str} ADD" if add_str else ""
    av_cerca_od = detalles_rx.get('av_cerca_od') or detalles_rx.get('av_cerca', '')
    av_cerca_oi = detalles_rx.get('av_cerca_oi') or detalles_rx.get('av_cerca', '')
    pdf.cell(30, 6, cerca_esf, border=1, align="C"); pdf.cell(30, 6, "", border=1, align="C")
    pdf.cell(20, 6, "", border=1, align="C"); pdf.cell(30, 6, "", border=1, align="C")
    pdf.cell(40, 6, av_cerca_od.upper() if add_str else "", border=1, align="C", ln=1)
    
    pdf.set_xy(30, y5+6); pdf.cell(25, 6, "IZQUIERDO", border=1, align="C")
    pdf.cell(30, 6, cerca_esf, border=1, align="C"); pdf.cell(30, 6, "", border=1, align="C")
    pdf.cell(20, 6, "", border=1, align="C"); pdf.cell(30, 6, "", border=1, align="C")
    pdf.cell(40, 6, av_cerca_oi.upper() if add_str else "", border=1, align="C", ln=1)
    
    y6 = pdf.get_y(); pdf.set_x(10)
    pdf.cell(35, 6, "CONTROL:", border=1); pdf.cell(60, 6, detalles_rx.get('prox_control', '').upper(), border=1)
    pdf.cell(25, 6, "VIGENCIA:", border=1); pdf.cell(75, 6, "30 DIAS", border=1, ln=1)
    
    pdf.set_x(10); pdf.cell(35, 6, "TIPO LENTE:", border=1); pdf.cell(60, 6, detalles_rx.get('tipo_lente', '').upper(), border=1)
    pdf.cell(25, 6, "USO:", border=1); pdf.cell(75, 6, detalles_rx.get('uso', '').upper(), border=1, ln=1)
    
    pdf.set_x(10); pdf.cell(35, 6, "FILTRO:", border=1); pdf.cell(60, 6, detalles_rx.get('filtro', '').upper(), border=1)
    pdf.cell(50, 6, "TRATAMIENTO:", border=1); pdf.cell(50, 6, "UN AÑO", border=1, ln=1)
    
    pdf.set_x(10); pdf.set_font("helvetica", "B", 9); pdf.cell(195, 6, "OBSERVACIONES:", border="L,T,R", ln=1)
    pdf.set_font("helvetica", "", 9); pdf.set_x(10)
    pdf.multi_cell(195, 5, historia.get('observaciones', '').upper(), border="L,R")
    
    y_firma = pdf.get_y(); pdf.set_xy(120, max(y_firma, y6+35))
    pdf.set_font("helvetica", "", 8); pdf.set_text_color(100, 100, 100)
    pdf.cell(75, 4, "Mateo F. Feliciano L.", align="C", ln=1); pdf.set_x(120)
    pdf.cell(75, 4, "Optómetra U.L.S.", align="C", ln=1); pdf.set_x(120)
    pdf.cell(75, 4, "T.P. 1022396649", align="C", ln=1); pdf.set_text_color(0, 0, 0)
    
    pdf.set_x(10); pdf.cell(195, 1, "", border="T", ln=1)
    pdf.set_font("helvetica", "B", 8); pdf.cell(195, 6, "Nota: NO SE DA GARANTIA POR TRABAJOS EN OTRA OPTICA", ln=1)

def get_sidebar_logo_html():
    # Solo usamos logo.png
    b64_logo = get_image_base64("logo.png")
    if b64_logo:
        return f'<div style="text-align: center;"><img src="data:image/png;base64,{b64_logo}" width="85%" style="margin-bottom: 20px;"></div>'
    else:
        return "<h3 style='text-align: center;'>Boomerang Visión</h3>"

# =====================================================================
# 6. CALLBACKS DE INTERFAZ
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
def on_p_compra_m_change(): st.session_state.p_compra_m = format_currency_co(st.session_state.p_compra_m)
def on_p_venta_m_change(): st.session_state.p_venta_m = format_currency_co(st.session_state.p_venta_m)

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

for k in ["subtotal_input", "abono_input", "descuento_input", "altura_focal_input", "monto_rec_input", "monto_gasto_input", "p_compra_input", "p_venta_input", "p_compra_m", "p_venta_m", "desc_gasto_input"]:
    if k not in st.session_state: st.session_state[k] = ""
if "last_fac_search" not in st.session_state: st.session_state.last_fac_search = ""

if "trigger_clear_doc" in st.session_state and st.session_state.trigger_clear_doc:
    for k in ["doc_input", "nom_input", "cel_input", "dir_input", "ocu_input", "edad_input", "mot_input", "ctrl_input", "dp_od_input", "dp_oi_input", "obs_input"]: st.session_state[k] = ""
    for k in ["esf_od", "cil_od", "eje_od", "esf_oi", "cil_oi", "eje_oi", "add_input"]: st.session_state[k] = 0.0 if "eje" not in k else 0
    st.session_state.fecha_nac_input = datetime(1995, 1, 1)
    # Por seguridad: el habeas data NUNCA debe quedar "encendido" para el
    # siguiente paciente sin su confirmación verbal real.
    st.session_state.habeas_check = False
    st.session_state.trigger_clear_doc = False

if "trigger_clear_factura" in st.session_state and st.session_state.trigger_clear_factura:
    for k in ["subtotal_input", "abono_input", "descuento_input", "altura_focal_input"]: st.session_state[k] = ""
    for k in ["esf_od_ext", "cil_od_ext", "esf_oi_ext", "cil_oi_ext", "add_ext"]: st.session_state[k] = 0.0
    for k in ["eje_od_ext", "eje_oi_ext"]: st.session_state[k] = 0
    for k in ["av_od_ext", "dp_od_ext", "av_oi_ext", "dp_oi_ext", "av_cerca_od_input", "av_cerca_oi_input"]: st.session_state[k] = ""
    st.session_state.trigger_clear_factura = False

if "trigger_clear_recaudo" in st.session_state and st.session_state.trigger_clear_recaudo:
    st.session_state.monto_rec_input = ""
    st.session_state.last_fac_search = ""
    st.session_state.fac_search_input = ""
    st.session_state.trigger_clear_recaudo = False

if "trigger_clear_gastos" in st.session_state and st.session_state.trigger_clear_gastos:
    st.session_state.desc_gasto_input = ""
    st.session_state.monto_gasto_input = ""
    st.session_state.metodo_gasto_input = "EFECTIVO"
    st.session_state.trigger_clear_gastos = False

if "trigger_clear_venta_busqueda" in st.session_state and st.session_state.trigger_clear_venta_busqueda:
    st.session_state.search_opt = ""
    st.session_state.trigger_clear_venta_busqueda = False

if "trigger_clear_anular" in st.session_state and st.session_state.trigger_clear_anular:
    st.session_state.input_anular = ""
    st.session_state.trigger_clear_anular = False

if "trigger_clear_ajuste" in st.session_state and st.session_state.trigger_clear_ajuste:
    st.session_state.codigo_ajuste_input = ""
    st.session_state.ajuste_cantidad = 1
    st.session_state.trigger_clear_ajuste = False

if "trigger_clear_laboratorio" in st.session_state and st.session_state.trigger_clear_laboratorio:
    st.session_state.nuevo_lab_input = ""
    st.session_state.trigger_clear_laboratorio = False

if "trigger_clear_montura" in st.session_state and st.session_state.trigger_clear_montura:
    for k in ["m_marca", "m_prov", "p_compra_m", "p_venta_m", "m_ref_unico", "m_color_unico", "m_base_ref"]:
        if k in st.session_state: st.session_state[k] = ""
    for i in range(st.session_state.get("ultima_cant_monturas", 1)):
        for k in [f"ref_{i}", f"col_{i}"]:
            if k in st.session_state: st.session_state[k] = ""
    st.session_state.m_cant = 1
    st.session_state.trigger_clear_montura = False

if "trigger_clear_producto" in st.session_state and st.session_state.trigger_clear_producto:
    for k in ["inv_codigo", "inv_marca", "inv_desc", "inv_prov", "p_compra_input", "p_venta_input"]:
        st.session_state[k] = ""
    st.session_state.trigger_clear_producto = False

if "trigger_clear_paciente_rapido" in st.session_state and st.session_state.trigger_clear_paciente_rapido:
    for k in ["q_nom_nuevo", "q_cel_nuevo", "q_dir_nuevo"]:
        if k in st.session_state: st.session_state[k] = ""
    st.session_state.trigger_clear_paciente_rapido = False

if "trigger_clear_editar" in st.session_state and st.session_state.trigger_clear_editar:
    st.session_state.edit_search_input = ""
    st.session_state.trigger_clear_editar = False

if "global_toast" in st.session_state:
    st.toast(st.session_state.global_toast, icon=st.session_state.get("global_toast_icon", "✅"))
    del st.session_state.global_toast
    if "global_toast_icon" in st.session_state: del st.session_state.global_toast_icon

# =====================================================================
# 7. BARRA LATERAL (SECCIONADA Y CONDICIONAL)
# =====================================================================
user_rol = st.session_state.user_info["rol"]
user_id = st.session_state.user_info["id"]

clinica_mods = ["👨‍⚕️ Consultorio"] if (user_rol == "admin" and user_id in ["1022396649", "1024585129"]) or user_rol == "doctor_limitado" else []
comercial_mods = ["🛍️ Óptica y Facturación", "📊 Cuadre de Caja Físico"] if user_rol in ["admin", "asesor_limitado"] else []
operaciones_mods = ["📦 Inventario", "🔬 Control de Trabajos"] if user_rol in ["admin", "asesor_limitado"] else []
admin_mods = ["📅 CRM y Fidelización", "📈 Analítica y Estadísticas"] if user_rol == "admin" else []

all_mods = clinica_mods + comercial_mods + operaciones_mods + admin_mods
if "current_module" not in st.session_state or st.session_state.current_module not in all_mods:
    st.session_state.current_module = all_mods[0] if all_mods else ""


def _limpiar_busquedas_historial():
    """
    Limpia el estado de las búsquedas de 'Historial de un Paciente'
    (Consultorio y Facturación) al cambiar de módulo. Sin esto, la
    búsqueda anterior (texto + resultados) quedaba "pegada" la próxima
    vez que se entraba a esas pantallas, incluso después de haber
    trabajado en otra parte completamente distinta del sistema.
    """
    prefijos = ("hist_consultorio_", "hist_facturacion_")
    for key in list(st.session_state.keys()):
        if key.startswith(prefijos):
            del st.session_state[key]


def _cambiar_modulo(nuevo_modulo):
    if nuevo_modulo != st.session_state.current_module:
        _limpiar_busquedas_historial()
    st.session_state.current_module = nuevo_modulo
    st.rerun()


with st.sidebar:
    st.markdown(get_sidebar_logo_html(), unsafe_allow_html=True)
    st.caption(f"👤 Sesión activa: **{st.session_state.user_info['nombre']}**")
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.user_info = None
        if "auth_token" in st.query_params: del st.query_params["auth_token"]
        st.rerun()
        
    st.markdown("---")
    
    if clinica_mods:
        st.markdown("### 🏥 Área Clínica")
        for m in clinica_mods:
            if st.button(m, use_container_width=True, type="primary" if st.session_state.current_module == m else "secondary"):
                _cambiar_modulo(m)
                
    if comercial_mods:
        st.markdown("### 🏬 Área Comercial")
        for m in comercial_mods:
            if st.button(m, use_container_width=True, type="primary" if st.session_state.current_module == m else "secondary"):
                _cambiar_modulo(m)
                
    if operaciones_mods:
        st.markdown("### ⚙️ Operaciones")
        for m in operaciones_mods:
            if st.button(m, use_container_width=True, type="primary" if st.session_state.current_module == m else "secondary"):
                _cambiar_modulo(m)
                
    if admin_mods:
        st.markdown("### 📈 Administración")
        for m in admin_mods:
            if st.button(m, use_container_width=True, type="primary" if st.session_state.current_module == m else "secondary"):
                _cambiar_modulo(m)
                
    st.markdown("---")
    # Alerta de stock crítico (productos en 0)
    if user_rol in ["admin", "asesor_limitado"]:
        try:
            inv_sidebar = supabase.table("inventario").select("codigo,marca,cantidad,categoria").execute().data or []
            # Excluir Monturas del alerta de stock (rotan constantemente)
            inv_no_montura = [p for p in inv_sidebar if str(p.get("categoria", "")).lower() != "montura"]
            sin_stock  = [p for p in inv_no_montura if int(p.get("cantidad", 0)) == 0]
            bajo_stock = [p for p in inv_no_montura if 0 < int(p.get("cantidad", 0)) <= 2]
            if sin_stock:
                st.error(f"🚨 **{len(sin_stock)} producto(s) sin stock**")
                with st.expander("Ver productos sin stock"):
                    for p in sin_stock:
                        st.caption(f"• {p.get('marca','').upper()} — Ref. {p.get('codigo','')}")
            if bajo_stock:
                st.warning(f"⚠️ **{len(bajo_stock)} producto(s) con stock bajo (≤2)**")
                with st.expander("Ver stock bajo"):
                    for p in bajo_stock:
                        cant = int(p.get("cantidad", 0))
                        st.caption(f"• {p.get('marca','').upper()} — Ref. {p.get('codigo','')} ({cant} ud.)")
        except Exception:
            pass
    st.caption("🚀 Boomerang Visión - V1.0")

modulo = st.session_state.current_module

# =====================================================================
# 8. MÓDULOS DE LA APLICACIÓN (solo se modifica la parte de Refracción)
# =====================================================================

# ------------------------------------------
# MÓDULO 1: CONSULTORIO (Pestañas Limpias)
# ------------------------------------------
if modulo == "👨‍⚕️ Consultorio":
    try:
        pendientes_revisar = supabase.table("historias_clinicas").select(
            "paciente_documento,nombre_legado,celular_legado,fecha,motivo_consulta"
        ).eq("pendiente_revisar", True).order("fecha", desc=True).execute().data
    except Exception:
        pendientes_revisar = []

    n_pendientes = len(pendientes_revisar)
    badge = ""
    if n_pendientes > 0:
        badge = (f'<span style="background:#fff3e0; color:#ef6c00; padding:5px 14px; '
                 f'border-radius:20px; font-weight:700; font-size:0.85em;">'
                 f'⚠️ {n_pendientes} pendiente(s) por revisar</span>')
    styled_header("Recepción y Clínica", "👨‍⚕️", badge)

    if n_pendientes > 0:
        with st.expander(f"⚠️ {n_pendientes} historia(s) clínica(s) pendiente(s) por revisar", expanded=False):
            st.caption("Visitas recientes migradas del histórico que no traían fórmula registrada. "
                       "Se resuelven solas cuando el paciente vuelve y se le crea una historia nueva "
                       "con fórmula, o puedes marcarlas como revisadas manualmente.")
            for i, pend in enumerate(pendientes_revisar):
                with st.container(border=True):
                    pc1, pc2 = st.columns([4, 1])
                    nombre_p = pend.get("nombre_legado") or "(sin nombre)"
                    doc_p = pend.get("paciente_documento") or "sin documento"
                    fecha_p = (pend.get("fecha") or "")[:10]
                    pc1.markdown(f"**{nombre_p}** · Doc: `{doc_p}` · {fecha_p}")
                    pc1.caption(pend.get("motivo_consulta") or "Sin motivo registrado")
                    if pc2.button("Marcar revisada", key=f"marcar_rev_{i}", use_container_width=True):
                        try:
                            q = supabase.table("historias_clinicas").update({"pendiente_revisar": False})
                            if pend.get("paciente_documento"):
                                q = q.eq("paciente_documento", pend["paciente_documento"]).eq("fecha", pend["fecha"])
                            else:
                                q = q.eq("nombre_legado", pend.get("nombre_legado")).eq("fecha", pend["fecha"])
                            q.execute()
                            st.toast("Marcada como revisada.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"No se pudo actualizar: {e}")
    
    tab_adm, tab_ref, tab_cierre, tab_hist = st.tabs(["📋 1. Admisión Paciente", "👁️ 2. Refracción (Rx)", "📝 3. Diagnóstico y Cierre", "📂 4. Historial"])
    
    with tab_adm:
        col_doc_search, col_doc_btn = st.columns([3, 1])
        with col_doc_search: doc_autofill = st.text_input("🔍 Cargar paciente existente (Cédula):").upper()
        with col_doc_btn:
            st.write(""); st.write("")
            if st.button("Buscar", use_container_width=True) and doc_autofill:
                res_exist = supabase.table("pacientes").select("*").eq("documento", doc_autofill).execute()
                if res_exist.data:
                    p = res_exist.data[0]
                    st.session_state.doc_input = p.get("documento", ""); st.session_state.nom_input = p.get("nombre_completo", "")
                    st.session_state.cel_input = p.get("celular", ""); st.session_state.dir_input = p.get("direccion", "")
                    st.session_state.ocu_input = p.get("ocupacion", ""); st.session_state.edad_input = p.get("edad", "")
                    st.toast("✅ Paciente cargado.")
                    st.session_state.doc_autofill_preview = None
                else:
                    # No está como paciente activo: buscamos en historial
                    # unificado (historias_clinicas y ventas_facturacion,
                    # que ya incluyen los registros migrados del histórico)
                    # por si hay algo que valga la pena mostrar antes de
                    # asumir que es un paciente totalmente nuevo.
                    try:
                        hc_prev = supabase.table("historias_clinicas").select("*") \
                            .eq("paciente_documento", doc_autofill).order("fecha", desc=True).execute().data
                        vf_prev = supabase.table("ventas_facturacion").select("*") \
                            .eq("paciente_documento", doc_autofill).order("fecha_venta", desc=True).execute().data
                    except Exception:
                        hc_prev, vf_prev = [], []

                    if hc_prev or vf_prev:
                        nombre_prev = ""
                        cel_prev = ""
                        if hc_prev and hc_prev[0].get("nombre_legado"):
                            nombre_prev = hc_prev[0]["nombre_legado"]
                            cel_prev = hc_prev[0].get("celular_legado", "")
                        elif vf_prev and vf_prev[0].get("titular_nombre"):
                            nombre_prev = vf_prev[0]["titular_nombre"]
                            cel_prev = vf_prev[0].get("titular_tel", "")
                        if nombre_prev:
                            st.session_state.nom_input = nombre_prev
                        if cel_prev:
                            st.session_state.cel_input = cel_prev
                        st.session_state.doc_input = doc_autofill
                        st.session_state.doc_autofill_preview = {
                            "n_historias": len(hc_prev), "n_ventas": len(vf_prev),
                        }
                        st.info(f"📜 No está registrado como paciente activo, pero encontramos "
                                f"{len(hc_prev)} historia(s) y {len(vf_prev)} venta(s) en el histórico. "
                                f"Nombre y celular sugeridos abajo — verifícalos y completa el registro.")
                    else:
                        st.session_state.doc_autofill_preview = None
                        st.warning("No encontrado, ni activo ni en el histórico.")

        with st.container(border=True):
            col1, col2, col3 = st.columns(3)
            documento = col1.text_input("Documento *", key="doc_input")
            nombre = col2.text_input("Nombre Completo *", key="nom_input")
            celular = col3.text_input("Celular *", key="cel_input")
            direccion = col1.text_input("Dirección", key="dir_input")
            ocupacion = col2.text_input("Ocupación", key="ocu_input")
            fecha_nacimiento = col3.date_input("Fecha Nacimiento", value=datetime(1995, 1, 1), min_value=datetime(1900, 1, 1), max_value=now_co().replace(tzinfo=None), format="DD/MM/YYYY", key="fecha_nac_input")
            edad = col1.text_input("Edad", key="edad_input")
            
        col_mot, col_ctrl = st.columns([2, 1])
        motivo = col_mot.text_input("Motivo de Consulta", key="mot_input")
        ultimo_control = col_ctrl.text_input("Último Control", key="ctrl_input")

    with tab_ref:
        with st.container(border=True):
            st.markdown("**Ojo Derecho (OD)**")
            c1, c2, c3, sp, c4 = st.columns([2, 2, 2, 0.5, 2])
            esfera_od = c1.number_input("Esfera OD", step=0.25, format="%.2f", key="esf_od")
            cilindro_od = c2.number_input("Cilindro OD", step=0.25, format="%.2f", key="cil_od", on_change=force_negative_cyl_od)
            # Eje OD: paso 5, rango 0-175
            eje_od = c3.number_input("Eje OD", min_value=0, max_value=175, step=5, key="eje_od")
            dp_od = c4.text_input("D.P. OD (mm)", key="dp_od_input")

            st.markdown("**Ojo Izquierdo (OI)**")
            c5, c6, c7, sp2, c8 = st.columns([2, 2, 2, 0.5, 2])
            esfera_oi = c5.number_input("Esfera OI", step=0.25, format="%.2f", key="esf_oi")
            cilindro_oi = c6.number_input("Cilindro OI", step=0.25, format="%.2f", key="cil_oi", on_change=force_negative_cyl_oi)
            # Eje OI: paso 5, rango 0-175
            eje_oi = c7.number_input("Eje OI", min_value=0, max_value=175, step=5, key="eje_oi")
            dp_oi = c8.text_input("D.P. OI (mm)", key="dp_oi_input")
            
            # Adición en columna más estrecha
            col_add1, col_add2 = st.columns([1, 3])
            with col_add1:
                adicion = st.number_input("Adición", min_value=0.00, step=0.25, format="%.2f", key="add_input")
            with col_add2:
                st.write("")  # espacio vacío

    with tab_cierre:
        obs = st.text_area("Observaciones Clínicas", height=100, key="obs_input")
        
        st.markdown("<br>", unsafe_allow_html=True)
        habeas_data_autorizado = st.toggle("✅ El paciente autoriza el tratamiento de sus datos personales (Habeas Data)", key="habeas_check")
        st.caption("Activa el interruptor una vez el paciente confirme verbalmente.")
        
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("💾 Guardar Historia Clínica", type="primary", use_container_width=True):
            if not documento or not nombre or not celular: st.error("⚠️ Documento, Nombre y Celular obligatorios.")
            elif not habeas_data_autorizado: st.error("⚠️ Debes confirmar el Habeas Data.")
            else:
                rx_od_final = build_rx_string(esfera_od, cilindro_od, eje_od); rx_oi_final = build_rx_string(esfera_oi, cilindro_oi, eje_oi)
                dp_combined = f"{dp_od}/{dp_oi}" if dp_od and dp_oi else (dp_od or dp_oi or "")
                doc_up = str(documento).upper(); nom_up = str(nombre).upper()
                # Normalizar celular: solo dígitos, sin prefijo 57, exactamente 10 dígitos
                cel_digits = "".join(filter(str.isdigit, str(celular)))
                if cel_digits.startswith("57") and len(cel_digits) == 12:
                    cel_digits = cel_digits[2:]
                cel_up = cel_digits if cel_digits else str(celular).upper()
                
                try: supabase.table("pacientes").upsert({"documento": doc_up, "nombre_completo": nom_up, "celular": cel_up, "ocupacion": str(ocupacion).upper(), "direccion": str(direccion).upper(), "edad": str(edad).upper(), "fecha_nacimiento": fecha_nacimiento.strftime("%Y-%m-%d"), "habeas_data": True, "habeas_data_fecha": now_co().isoformat()}).execute()
                except Exception: supabase.table("pacientes").upsert({"documento": doc_up, "nombre_completo": nom_up, "celular": cel_up, "ocupacion": str(ocupacion).upper(), "direccion": str(direccion).upper(), "fecha_nacimiento": fecha_nacimiento.strftime("%Y-%m-%d"), "habeas_data": True, "habeas_data_fecha": now_co().isoformat()}).execute()

                supabase.table("historias_clinicas").insert({"paciente_documento": doc_up, "motivo_consulta": str(motivo).upper(), "rx_final_od": rx_od_final, "rx_final_oi": rx_oi_final, "dp": dp_combined, "ultimo_control": str(ultimo_control).upper(), "observaciones": str(obs).upper(), "adicion": f"{adicion:+.2f}" if adicion > 0.0 else "", "fecha": now_co().isoformat()}).execute()

                # El paciente acaba de ser reatendido con una historia real:
                # se resuelven sus pendientes de revisión anteriores, si tenía.
                try:
                    supabase.table("historias_clinicas").update({"pendiente_revisar": False}) \
                        .eq("paciente_documento", doc_up).eq("pendiente_revisar", True).execute()
                except Exception:
                    pass

                st.session_state.global_toast = f"Historia de {nom_up} guardada."
                st.session_state.trigger_clear_doc = True
                st.rerun()

    with tab_hist:
        st.markdown("#### 🔍 Buscar Historial de un Paciente")
        mostrar_buscador_historial("hist_consultorio")

# ------------------------------------------
# MÓDULO 2: FACTURACIÓN Y WIZARD REESTRUCTURADO
# ------------------------------------------
elif modulo == "🛍️ Óptica y Facturación":
    styled_header("Facturación y Ventas", "🛍️")
    tab_venta, tab_menor, tab_recaudo, tab_anular, tab_editar, tab_reimprimir, tab_hist_fact = st.tabs(
        ["🛒 Nueva Venta", "🧦 Venta Menor", "💵 Recaudar Saldo", "🚫 Anular", "✏️ Editar Reciente", "🖨️ Reimprimir", "📜 Historial"]
    )
    
    with tab_venta:
        # Confirmación de la última venta guardada: se muestra ARRIBA del
        # formulario (ya vacío) en vez de dejar el PDF embebido bloqueando
        # la pantalla indefinidamente. Los bytes viven en session_state
        # porque tras el rerun que limpia el formulario, ya no hay forma
        # de regenerarlos a partir de campos que quedaron en blanco.
        ultima = st.session_state.get("ultima_venta_pdfs")
        if ultima:
            with st.container(border=True):
                uc1, uc2 = st.columns([5, 1])
                uc1.success(f"✅ Venta registrada — Factura #{ultima['numero_factura']}")
                if uc2.button("✕", key="cerrar_ultima_venta", help="Ocultar este aviso"):
                    del st.session_state["ultima_venta_pdfs"]
                    st.rerun()
                st.download_button(
                    "📥 Descargar Facturación (incluye orden de laboratorio)",
                    data=ultima["pdf_bytes"],
                    file_name=f"Facturacion_{ultima['numero_factura']}.pdf",
                    mime="application/pdf", use_container_width=True,
                    key="dl_ultima_factura")
            st.divider()

        search_doc = st.text_input("🔍 Buscar Cédula del Paciente:", key="search_opt").upper()
        if search_doc:
            res_paciente = supabase.table("pacientes").select("*").eq("documento", search_doc).execute()
            
            if len(res_paciente.data) == 0:
                st.warning("⚠️ Paciente no registrado en la base de datos (Fórmula Externa o Nuevo).")

                # Buscar coincidencia en el historial (ya unificado en las
                # tablas operativas: ventas_facturacion e historias_clinicas)
                # por documento, para sugerir nombre/celular y que el
                # asesor no tenga que volver a preguntarlos si ya existían
                # en archivos antiguos.
                nombre_sugerido, cel_sugerido = "", ""
                try:
                    leg_trab = supabase.table("ventas_facturacion").select(
                        "titular_nombre,titular_tel,fecha_venta"
                    ).eq("paciente_documento", search_doc).order("fecha_venta", desc=True).limit(1).execute().data
                    leg_hc = supabase.table("historias_clinicas").select(
                        "nombre_legado,celular_legado,fecha"
                    ).eq("paciente_documento", search_doc).order("fecha", desc=True).limit(1).execute().data
                    candidatos = []
                    for t in (leg_trab or []):
                        candidatos.append({"nombre": t.get("titular_nombre"),
                                            "celular": t.get("titular_tel"),
                                            "fecha": t.get("fecha_venta")})
                    for h in (leg_hc or []):
                        candidatos.append({"nombre": h.get("nombre_legado"),
                                            "celular": h.get("celular_legado"),
                                            "fecha": h.get("fecha")})
                    if candidatos:
                        candidatos.sort(key=lambda x: x.get("fecha") or "", reverse=True)
                        mejor = candidatos[0]
                        nombre_sugerido = mejor.get("nombre") or ""
                        cel_sugerido = mejor.get("celular") or ""
                        if nombre_sugerido:
                            st.info(f"📜 Encontramos este documento en el historial antiguo: "
                                    f"**{nombre_sugerido}** · Tel: `{cel_sugerido or '—'}`. "
                                    f"Verifica los datos y confírmalos abajo.")
                except Exception as e:
                    st.caption(f"⚠️ No se pudo consultar el historial legado ({e}).")

                with st.expander("➕ Registrar Paciente para Alimentar la Base de Datos", expanded=True):
                    q_nom = st.text_input("Nombre Completo *", value=nombre_sugerido, key="q_nom_nuevo").upper()
                    q_cel = st.text_input("Celular *", value=cel_sugerido, key="q_cel_nuevo").upper()
                    q_dir = st.text_input("Dirección (Opcional)", key="q_dir_nuevo").upper()
                    if st.button("Guardar y Alimentar Base de Datos") and q_nom and q_cel:
                        supabase.table("pacientes").insert({
                            "documento": search_doc, "nombre_completo": q_nom, "celular": q_cel, 
                            "direccion": q_dir, "habeas_data": True, "habeas_data_fecha": now_co().isoformat()
                        }).execute()
                        st.success("¡Paciente guardado exitosamente!")
                        st.session_state.trigger_clear_paciente_rapido = True
                        st.rerun()
            else:
                paciente = res_paciente.data[0]
                
                st.success(f"✅ Paciente Encontrado: **{paciente['nombre_completo']}** | Cédula: `{paciente['documento']}` | Tel: `{paciente.get('celular', 'N/A')}`")
                
                res_historias = supabase.table("historias_clinicas").select("*").eq("paciente_documento", search_doc).order("id_consulta", desc=True).execute()
                historias_data = res_historias.data or []
                
                if historias_data:
                    with st.expander("👁️ Ver Fórmulas Registradas en el Sistema para este Paciente", expanded=False):
                        for h in historias_data:
                            st.markdown(f"**Consulta ID #{h.get('id_consulta')} — Fecha:** {str(h.get('fecha', ''))[:10]}")
                            add_val = format_add(h.get('adicion'))
                            add_display = f" | **ADD:** {add_val}" if add_val else ""
                            st.markdown(f"- **OD:** {format_rx_ui(h.get('rx_final_od', 'N/A'))} | **OI:** {format_rx_ui(h.get('rx_final_oi', 'N/A'))}{add_display} | **DP:** {h.get('dp', 'N/A')}")
                            if h.get('observaciones'):
                                st.markdown(f"- *Observaciones:* {h.get('observaciones')}")
                            st.divider()
                else:
                    st.info("ℹ️ Este paciente no tiene exámenes o historias clínicas guardadas en el sistema (puede usar opción de Fórmula Externa).")

                st.divider()

                es_titular_mismo = st.checkbox("¿La factura queda a nombre del paciente registrado?", value=True)
                if es_titular_mismo:
                    titular_nombre = paciente['nombre_completo']
                    titular_doc = paciente['documento']
                    titular_tel = paciente.get('celular', 'N/A')
                else:
                    st.markdown("##### 👤 Datos del Pagador / Titular de la Factura")
                    col_t1, col_t2, col_t3 = st.columns(3)
                    titular_nombre = col_t1.text_input("Nombre Completo Titular *").upper()
                    titular_doc = col_t2.text_input("Cédula / NIT Titular *").upper()
                    titular_tel = col_t3.text_input("Celular Titular *").upper()

                st.divider()

                try:
                    # numero_factura es texto y las 5.097 facturas legado usan
                    # prefijo "LEG-", así que ordenar por texto no sirve para
                    # encontrar el máximo real (alfabéticamente "LEG-..." queda
                    # por encima de cualquier número). Se filtran las legado y
                    # se calcula el máximo numérico en Python.
                    candidatos_num = supabase.table("ventas_facturacion").select("numero_factura") \
                        .not_.like("numero_factura", "LEG-%").execute().data or []
                    numeros_reales = [int(c["numero_factura"]) for c in candidatos_num
                                      if str(c.get("numero_factura", "")).strip().isdigit()]
                    BASE_FACTURACION = 5422  # última factura del sistema anterior a esta migración
                    sugerido = max(numeros_reales, default=BASE_FACTURACION)
                    sugerido = max(sugerido, BASE_FACTURACION) + 1
                except Exception:
                    sugerido = 5423
                
                num_factura = st.text_input("N° de Factura", value=str(sugerido))
                
                factura_existe = False
                if num_factura:
                    try:
                        if len(supabase.table("ventas_facturacion").select("numero_factura").eq("numero_factura", num_factura).execute().data) > 0:
                            st.error(f"⚠️ El número de factura **{num_factura}** ya existe.")
                            factura_existe = True
                    except: pass

                st.markdown("##### Origen de los Lentes")
                opc_rx = ["Fórmula del Sistema"] if historias_data else []
                opc_rx.extend(["Fórmula Externa", "No aplica"])
                origen_rx = st.pills("Selecciona la fuente de la Rx:", opc_rx, default=opc_rx[0])
                
                historia = {}
                if origen_rx == "Fórmula del Sistema" and historias_data:
                    historia = historias_data[0]
                elif origen_rx == "Fórmula Externa":
                    st.caption("Ingresa cada valor por separado -- se guardan estructurados "
                               "(no como texto libre), para que la receta y las órdenes de "
                               "laboratorio los lean correctamente.")
                    st.markdown("**Ojo Derecho (OD)**")
                    ext1, ext2, ext3, ext4, ext5 = st.columns(5)
                    esf_od_ext = ext1.number_input("Esfera OD", step=0.25, format="%.2f", key="esf_od_ext")
                    cil_od_ext = ext2.number_input("Cilindro OD", step=0.25, format="%.2f", key="cil_od_ext")
                    eje_od_ext = ext3.number_input("Eje OD", min_value=0, max_value=175, step=5, key="eje_od_ext")
                    av_od_ext = ext4.text_input("AV OD", key="av_od_ext").upper()
                    dp_od_ext = ext5.text_input("DP OD (mm)", key="dp_od_ext").upper()

                    st.markdown("**Ojo Izquierdo (OI)**")
                    ext6, ext7, ext8, ext9, ext10 = st.columns(5)
                    esf_oi_ext = ext6.number_input("Esfera OI", step=0.25, format="%.2f", key="esf_oi_ext")
                    cil_oi_ext = ext7.number_input("Cilindro OI", step=0.25, format="%.2f", key="cil_oi_ext")
                    eje_oi_ext = ext8.number_input("Eje OI", min_value=0, max_value=175, step=5, key="eje_oi_ext")
                    av_oi_ext = ext9.text_input("AV OI", key="av_oi_ext").upper()
                    dp_oi_ext = ext10.text_input("DP OI (mm)", key="dp_oi_ext").upper()

                    add_ext = st.number_input("Adición (ADD)", min_value=0.00, step=0.25, format="%.2f", key="add_ext")

                    rx_od_final_ext = build_rx_string(esf_od_ext, cil_od_ext, eje_od_ext)
                    rx_oi_final_ext = build_rx_string(esf_oi_ext, cil_oi_ext, eje_oi_ext)
                    dp_ext_combined = f"{dp_od_ext or 'N/A'}/{dp_oi_ext or 'N/A'}"
                    historia = {
                        "rx_final_od": rx_od_final_ext, "rx_final_oi": rx_oi_final_ext,
                        "adicion": f"{add_ext:+.2f}" if add_ext > 0.0 else "",
                        "dp": dp_ext_combined, "observaciones": "FÓRMULA EXTERNA",
                        "av_od": av_od_ext, "av_oi": av_oi_ext,
                    }
                else:
                    historia = {"rx_final_od": "N/A", "rx_final_oi": "N/A", "adicion": "", "dp": "", "observaciones": "NO APLICA RX"}

                tipo_gafas = st.selectbox("Formato de Impresión:", ["Lejos", "Cerca", "Adición (Bifocal/Progresivo)", "Dos Pares"])
                
                st.markdown("##### Montura y Descripción")
                origen_montura = st.pills("Selecciona la montura:", ["Montura de Vitrina", "Montura del Paciente", "No aplica"], default="Montura de Vitrina")
                
                desc_sug = "LENTES EN MONTURA DEL PACIENTE"
                selected_frame_code = None
                
                if origen_montura == "Montura de Vitrina":
                    col_vit1, col_vit2 = st.columns([1, 2])
                    ref_busqueda = col_vit1.text_input("🔍 N° Referencia Montura:").upper()
                    
                    if ref_busqueda:
                        res_montura = supabase.table("inventario").select("*").eq("codigo", ref_busqueda).ilike("categoria", "Montura").execute().data
                        if res_montura:
                            m_encontrada = res_montura[0]
                            if int(m_encontrada.get("cantidad", 0)) > 0:
                                col_vit2.success(f"✅ {m_encontrada['marca']} | ${format_currency_co(m_encontrada['precio_venta'])}")
                                selected_frame_code = m_encontrada['codigo']
                                desc_sug = f"LENTES + MONTURA {m_encontrada['marca']} REF. {selected_frame_code}"
                            else:
                                col_vit2.error("⚠️ SIN STOCK (Cant: 0)")
                                desc_sug = f"LENTES + MONTURA {m_encontrada['marca']} REF. {ref_busqueda} (SIN STOCK)"
                        else:
                            col_vit2.warning("⚠️ No encontrada en el inventario.")
                            desc_sug = f"LENTES + MONTURA REF. {ref_busqueda}"
                    else:
                        desc_sug = "LENTES + MONTURA REF. "
                        
                elif origen_montura == "No aplica":
                    desc_sug = "SERVICIO / OTRO (TRASPASO / SOLDADURA / PROVEEDOR)"
                
                desc_producto = st.text_input("Descripción final:", value=desc_sug).upper()
                
                c1, c2, c3 = st.columns(3)
                c1.text_input("Valor Subtotal ($)", key="subtotal_input", on_change=on_subtotal_change)
                c2.selectbox("Tipo Dcto", ["Sin Descuento", "Porcentaje (%)", "Valor Fijo ($)"], key="tipo_descuento_widget", on_change=on_tipo_descuento_change)
                c3.text_input("Dcto Aplicado", key="descuento_input", on_change=on_descuento_change)
                
                sub_val = int(clean_numeric_string(st.session_state.subtotal_input) or 0)
                abono_val = int(clean_numeric_string(st.session_state.abono_input) or 0)
                desc_val = int(clean_numeric_string(st.session_state.descuento_input) or 0)
                desc_calc = int((desc_val/100.0)*sub_val) if st.session_state.get("tipo_descuento_widget") == "Porcentaje (%)" else desc_val
                tot_neto = sub_val - desc_calc
                sal_pend = tot_neto - abono_val

                c4, c5, c6 = st.columns(3)
                c4.text_input("Abono Inicial ($)", key="abono_input", on_change=on_abono_change)
                metodo_pago = c5.selectbox("Método de Pago", ["EFECTIVO", "BOLD", "LLAVE", "NEQUI", "DAVIPLATA"])
                
                with c6:
                    st.markdown(f"""
                        <div style="background-color: #f0f0f0; border: 1px solid #b0b0b0; padding: 9px; border-radius: 6px; text-align: center; margin-top: 24px;">
                            <span style="font-size: 0.8em; color: #000000; font-weight: 600;">SALDO PENDIENTE</span><br>
                            <span style="font-size: 1.3em; font-weight: bold; color: #e57373;">${format_currency_co(sal_pend)}</span>
                        </div>
                    """, unsafe_allow_html=True)

                col_ent1, col_ent2 = st.columns(2)
                fecha_entrega = col_ent1.text_input("Fecha/Hora Entrega", placeholder="Ej: 3 días / Mañana / 15-ago").upper()
                altura_focal = col_ent2.text_input("Alt. Focal (Opcional)", key="altura_focal_input", on_change=on_altura_focal_change).upper()

                with st.expander("Opcional: Detalles para Receta Clínica"):
                    col_rx1, col_rx2 = st.columns(2)
                    tipo_lente = col_rx1.selectbox("Tipo Lente", ["MONOFOCAL", "PROGRESIVO", "BIFOCAL INVISIBLE", "BIFOCAL FLAT TOP", "OCUPACIONAL", "DOS PARES"])
                    filtro = col_rx1.selectbox("Filtro", ["SIN FILTRO", "ANTIRREFLEJO", "FOTOSENSIBLE", "ANTIRREFLEJO + FOTOSENSIBLE"])
                    uso = col_rx2.selectbox("Uso", ["PERMANENTE", "PROLONGADO", "ESFUERZO VISUAL", "PROTECCIÓN"])
                    prox_control = col_rx2.text_input("Próximo Control").upper()
                    av_od = col_rx1.text_input("AV Lejos OD", value=historia.get("av_od", "")).upper()
                    av_oi = col_rx2.text_input("AV Lejos OI", value=historia.get("av_oi", "")).upper()
                    av_cerca_od = col_rx1.text_input("AV Cerca OD", key="av_cerca_od_input").upper()
                    av_cerca_oi = col_rx2.text_input("AV Cerca OI", key="av_cerca_oi_input").upper()
                    detalles_rx = {"tipo_lente": tipo_lente, "filtro": filtro, "uso": uso, "prox_control": prox_control,
                                    "av_od": av_od, "av_oi": av_oi, "av_cerca_od": av_cerca_od, "av_cerca_oi": av_cerca_oi}
                
                st.divider()
                col_btn1, col_btn2 = st.columns([1, 1])
                btn_generar_paquete = col_btn1.button("📄 Generar Factura y Órdenes", type="primary", use_container_width=True, disabled=factura_existe)
                btn_generar_rx = col_btn2.button("👁️ Generar Receta Clínica", use_container_width=True)
                
                if btn_generar_paquete:
                    if not desc_producto or sub_val == 0 or not titular_nombre or not titular_doc:
                        st.warning("⚠️ Debes rellenar la descripción, el subtotal y los datos del titular válidos.")
                    else:
                        venta_data = {
                            "numero_factura": num_factura, "titular_nombre": titular_nombre, "titular_doc": titular_doc, "titular_tel": titular_tel,
                            "descripcion": desc_producto, "subtotal": sub_val, "descuento": desc_calc, "total": tot_neto, 
                            "abono": abono_val, "saldo": sal_pend, "fecha_entrega": fecha_entrega, "altura_focal": altura_focal,
                            "metodo_pago": metodo_pago
                        }
                        # Se calcula antes del insert para poder persistir la
                        # fórmula usada en la venta (ya no vive solo en el PDF).
                        hist_factura = procesar_historia_factura(historia, tipo_gafas)
                        try:
                            supabase.table("ventas_facturacion").insert({
                                "numero_factura": num_factura, "paciente_documento": paciente['documento'], "titular_nombre": titular_nombre,
                                "titular_doc": titular_doc, "titular_tel": titular_tel, "descripcion": desc_producto, "subtotal": sub_val,
                                "descuento": desc_calc, "total": tot_neto, "abono": abono_val, "saldo": sal_pend,
                                "fecha_entrega": fecha_entrega, "altura_focal": altura_focal, "metodo_pago": metodo_pago,
                                "estado": "ACTIVA", "estado_lab": "Pendiente de enviar", "fecha_venta": now_co().isoformat(),
                                "rx_final_od": hist_factura.get("rx_final_od", ""), "rx_final_oi": hist_factura.get("rx_final_oi", ""),
                                "adicion": hist_factura.get("adicion", ""), "dp": hist_factura.get("dp", ""),
                                "av_od": detalles_rx.get("av_od", ""), "av_oi": detalles_rx.get("av_oi", ""),
                                "av_cerca_od": detalles_rx.get("av_cerca_od", ""), "av_cerca_oi": detalles_rx.get("av_cerca_oi", ""),
                                "origen_rx": origen_rx,
                            }).execute()
                            
                            if origen_montura == "Montura de Vitrina" and selected_frame_code:
                                frame_data = supabase.table("inventario").select("cantidad").eq("codigo", selected_frame_code).execute().data
                                if frame_data: supabase.table("inventario").update({"cantidad": frame_data[0]["cantidad"] - 1}).eq("codigo", selected_frame_code).execute()
                                case_data = supabase.table("inventario").select("cantidad").eq("codigo", "ESTUCHE-GENERICO").execute().data
                                if case_data: supabase.table("inventario").update({"cantidad": case_data[0]["cantidad"] - 1}).eq("codigo", "ESTUCHE-GENERICO").execute()
                        except Exception as e: st.error(f"Error técnico BD: {e}")

                        pdf = FPDF(orientation="P", unit="mm", format="Letter")
                        pdf.set_compression(True)
                        pdf.add_page(); dibujar_media_carta(pdf, paciente, hist_factura, venta_data, "COPIA CLIENTE")
                        pdf.add_page(); dibujar_media_carta(pdf, paciente, hist_factura, venta_data, "COPIA ÓPTICA / CAJA")
                        
                        if tipo_gafas == "Dos Pares":
                            h_lejos = historia.copy(); h_lejos['adicion'] = ""
                            pdf.add_page(); dibujar_orden_laboratorio(pdf, paciente, h_lejos, venta_data, "DOS PARES - LEJOS")
                            h_cerca = historia.copy()
                            h_cerca['rx_final_od'] = get_cerca_rx(historia.get('rx_final_od'), historia.get('adicion'))
                            h_cerca['rx_final_oi'] = get_cerca_rx(historia.get('rx_final_oi'), historia.get('adicion')); h_cerca['adicion'] = ""
                            pdf.add_page(); dibujar_orden_laboratorio(pdf, paciente, h_cerca, venta_data, "DOS PARES - CERCA")
                        else:
                            pdf.add_page(); dibujar_orden_laboratorio(pdf, paciente, hist_factura, venta_data, tipo_gafas.upper())
                        
                        pdf_bytes = bytes(pdf.output())
                        st.session_state.global_toast = f"Venta registrada. Factura #{num_factura}"
                        # Se guarda el PDF y se limpia TODO el formulario (volviendo
                        # a la pantalla inicial de Nueva Venta) en vez de dejarlo
                        # embebido en pantalla indefinidamente. La búsqueda de
                        # cédula es la que controla si se muestra el resto del
                        # formulario -- limpiarla oculta todo lo demás de una vez.
                        st.session_state.ultima_venta_pdfs = {
                            "numero_factura": num_factura, "pdf_bytes": pdf_bytes,
                        }
                        st.session_state.trigger_clear_venta_busqueda = True
                        st.session_state.trigger_clear_factura = True
                        st.rerun()

                if btn_generar_rx:
                    pdf_rx = FPDF(orientation="P", unit="mm", format="Letter")
                    pdf_rx.set_compression(True); pdf_rx.add_page()
                    dibujar_prescripcion_clinica(pdf_rx, paciente, historia, detalles_rx)
                    pdf_bytes_rx = bytes(pdf_rx.output())
                    st.toast("🎉 ¡Receta Clínica Generada!")
                    st.download_button(
                        label="📥 Descargar Receta Clínica",
                        data=pdf_bytes_rx,
                        file_name=f"Receta_{paciente['documento']}.pdf",
                        mime="application/pdf"
                    )
                    b64_rx = base64.b64encode(pdf_bytes_rx).decode("utf-8")
                    st.markdown(
                        f"""
                        <iframe src="data:application/pdf;base64,{b64_rx}" 
                                width="100%" height="600px" 
                                style="border: none;"
                                sandbox="allow-scripts allow-same-origin allow-modals">
                            <p style="color:#000000;">Tu navegador no puede mostrar el PDF. 
                            <a href="data:application/pdf;base64,{b64_rx}" download="Receta_{paciente['documento']}.pdf">Descárgalo aquí</a>.</p>
                        </iframe>
                        """,
                        unsafe_allow_html=True
                    )

    with tab_menor:
        st.markdown("<h4 style='color: #000000;'>🧦 Registrar Venta Menor</h4>", unsafe_allow_html=True)
        st.caption("Para artículos sueltos que no requieren una factura completa: "
                   "cordones, líquidos de limpieza, tornillos, plaquetas, etc. "
                   "Se registra como pagada de inmediato y entra al cuadre de caja del día.")

        with st.form("form_venta_menor", clear_on_submit=True):
            fm1, fm2, fm3 = st.columns([3, 1, 1])
            with fm1:
                desc_menor = st.text_input("Descripción del artículo", placeholder="Ej: Cordón, Líquido limpiador").upper()
            with fm2:
                cantidad_menor = st.number_input("Cantidad", min_value=1, value=1, step=1)
            with fm3:
                valor_unit_menor = st.number_input("Valor unitario ($)", min_value=0, step=1000, value=0)
            metodo_menor = st.selectbox("Método de Pago", ["EFECTIVO", "BOLD", "LLAVE", "NEQUI", "DAVIPLATA"])
            guardar_menor = st.form_submit_button("💾 Registrar Venta", type="primary", use_container_width=True)

        if guardar_menor:
            if not desc_menor or valor_unit_menor <= 0:
                st.warning("⚠️ Ingresa una descripción y un valor válidos.")
            else:
                total_menor = int(valor_unit_menor) * int(cantidad_menor)
                # Prefijo "MEN-" + timestamp con microsegundos: identificador
                # único sin necesitar consultar la BD primero. No es una
                # factura formal, así que no ocupa la numeración real.
                num_menor = f"MEN-{now_co().strftime('%Y%m%d%H%M%S%f')}"
                desc_final = desc_menor if cantidad_menor == 1 else f"{desc_menor} x{int(cantidad_menor)}"
                supabase.table("ventas_facturacion").insert({
                    "numero_factura": num_menor,
                    "paciente_documento": "",
                    "titular_nombre": "VENTA MENOR",
                    "titular_doc": "", "titular_tel": "",
                    "descripcion": desc_final,
                    "subtotal": total_menor, "descuento": 0, "total": total_menor,
                    "abono": total_menor, "saldo": 0,
                    "fecha_entrega": "", "altura_focal": "",
                    "metodo_pago": metodo_menor, "estado": "ACTIVA",
                    "estado_lab": "Entregado",
                    "fecha_venta": now_co().isoformat(),
                    "laboratorio": "", "origen": "ACTUAL",
                }).execute()
                st.session_state.global_toast = f"Venta menor registrada: {desc_final} — ${format_currency_co(total_menor)}"
                st.rerun()

        st.divider()
        st.markdown("#### 🧾 Ventas menores de hoy")
        hoy_str = now_co().strftime("%Y-%m-%d")
        ventas_menores_hoy = supabase.table("ventas_facturacion").select("*") \
            .like("numero_factura", "MEN-%") \
            .gte("fecha_venta", f"{hoy_str}T00:00:00").lte("fecha_venta", f"{hoy_str}T23:59:59") \
            .order("fecha_venta", desc=True).execute().data or []

        if ventas_menores_hoy:
            total_dia_menor = sum(v.get("total", 0) for v in ventas_menores_hoy)
            st.caption(f"**{len(ventas_menores_hoy)}** venta(s) menor(es) hoy · Total: **${format_currency_co(total_dia_menor)}**")
            for vm in ventas_menores_hoy:
                hora = (vm.get("fecha_venta") or "")[11:16]
                with st.container(border=True):
                    vc1, vc2, vc3 = st.columns([1, 3, 1])
                    vc1.markdown(f"**🕐 {hora}**")
                    vc2.markdown(vm.get("descripcion", ""))
                    vc3.markdown(f"**${format_currency_co(vm.get('total', 0))}** · {vm.get('metodo_pago','')}")
        else:
            st.info("Todavía no hay ventas menores registradas hoy.")

    with tab_recaudo:
        st.markdown("<h4 style='color: #000000;'>💵 Recaudar Saldo y Cambiar Estado a Entregado</h4>", unsafe_allow_html=True)
        fac_search = st.text_input("Ingrese el N° de Factura o Cédula a buscar:", key="fac_search_input").upper()
        if fac_search:
            # Cubre tanto factura corta ("2385") como formato legado completo
            cond_factura = filtro_busqueda_factura(fac_search)
            filtro_or = ",".join(cond_factura + [f"paciente_documento.eq.{fac_search}"])
            # Primero buscamos la factura SIN filtrar por saldo, para detectar si ya está pagada
            res_cualquier = supabase.table("ventas_facturacion").select("*").or_(filtro_or).neq("estado", "ANULADA").order("fecha_venta", desc=True).limit(1).execute()
            res_saldo = supabase.table("ventas_facturacion").select("*").or_(filtro_or).gt("saldo", 0).neq("estado", "ANULADA").execute()

            if res_cualquier.data and not res_saldo.data:
                # Factura encontrada pero saldo = 0 → ya está pagada
                fac_pagada = res_cualquier.data[0]
                st.success(f"✅ La Factura N° **{formatear_numero_factura_display(fac_pagada['numero_factura'])}** de **{fac_pagada['titular_nombre']}** ya se encuentra **cancelada en su totalidad** (Total: ${format_currency_co(int(fac_pagada.get('total', 0)))}). No tiene saldo pendiente.")
            elif res_saldo.data:
                fac_pen = res_saldo.data[0]
                saldo_actual_int = int(fac_pen['saldo'])
                st.info(f"📌 Factura N° **{formatear_numero_factura_display(fac_pen['numero_factura'])}** | Paciente: **{fac_pen['titular_nombre']}** | Estado Actual: `{fac_pen.get('estado_lab', 'Pendiente')}`")
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
                            "fecha_pago": now_co().isoformat()
                        }).execute()
                        
                        st.session_state.global_toast = f"Pago registrado. Nuevo saldo: ${format_currency_co(nuevo_saldo)} | Estado: {nuevo_est_recaudo}"
                        st.session_state.trigger_clear_recaudo = True
                        st.rerun()
            else:
                st.warning("⚠️ No se encontraron facturas para ese número de factura o cédula.")

    with tab_anular:
        st.markdown("<h4 style='color: #000000;'>🚫 Anulación de Facturas</h4>", unsafe_allow_html=True)
        num_anular = st.text_input("Ingrese el N° de Factura a Anular:", key="input_anular").upper()
        if num_anular:
            cond_anular = filtro_busqueda_factura(num_anular)
            res_anular = supabase.table("ventas_facturacion").select("*").or_(",".join(cond_anular)).limit(1).execute()
            if res_anular.data:
                fac_a = res_anular.data[0]
                if fac_a.get("estado") == "ANULADA": st.error("⚠️ Esta factura ya se encuentra ANULADA.")
                else:
                    st.warning(f"⚠️ ¿Confirmas la anulación de la Factura N° **{formatear_numero_factura_display(fac_a['numero_factura'])}** de **{fac_a['titular_nombre']}** por valor de **${format_currency_co(fac_a['total'])}**?")
                    confirmar_anulacion = st.checkbox(
                        "Entiendo que esta acción es **irreversible** y deseo anular la factura.",
                        key=f"chk_anular_{fac_a['numero_factura']}"
                    )
                    if confirmar_anulacion:
                        if st.button("🚨 CONFIRMAR ANULACIÓN DE FACTURA", type="primary"):
                            supabase.table("ventas_facturacion").update({"estado": "ANULADA"}).eq("numero_factura", fac_a["numero_factura"]).execute()
                            st.session_state.global_toast = "Factura ANULADA exitosamente."
                            st.session_state.global_toast_icon = "🚨"
                            st.session_state.trigger_clear_anular = True
                            st.rerun()
                    else:
                        st.info("Marca la casilla de confirmación para habilitar el botón de anulación.")
            else:
                st.error("No existe ninguna factura con ese número.")

    with tab_editar:
        st.markdown("<h4 style='color: #000000;'>✏️ Editar Factura Reciente</h4>", unsafe_allow_html=True)
        st.caption("Solo se pueden editar facturas creadas en las **últimas 24 horas** -- "
                   "pasado ese plazo, usa Anular y crea una nueva si hace falta corregir algo, "
                   "para no alterar el historial financiero ya cerrado.")

        edit_search = st.text_input("N° de Factura a editar:", key="edit_search_input").strip().upper()
        if edit_search:
            cond_edit = filtro_busqueda_factura(edit_search)
            res_edit = supabase.table("ventas_facturacion").select("*").or_(",".join(cond_edit)).limit(1).execute()

            if not res_edit.data:
                st.error("No se encontró ninguna factura con ese número.")
            else:
                venta_e = res_edit.data[0]
                if venta_e.get("estado") == "ANULADA":
                    st.error("⚠️ Esta factura está ANULADA y no se puede editar.")
                elif venta_e.get("origen") == "LEGADO":
                    st.error("⚠️ Esta es una factura histórica migrada, no una venta reciente -- no se puede editar.")
                else:
                    fv_raw = venta_e.get("fecha_venta", "")
                    try:
                        fv_dt = datetime.fromisoformat(fv_raw.replace("Z", "+00:00")).astimezone(timezone(timedelta(hours=-5))).replace(tzinfo=None)
                    except Exception:
                        fv_dt = None

                    horas_transcurridas = (now_co().replace(tzinfo=None) - fv_dt).total_seconds() / 3600 if fv_dt else None

                    if horas_transcurridas is None or horas_transcurridas > 24:
                        st.error(f"⚠️ Esta factura tiene más de 24 horas "
                                 f"({horas_transcurridas:.1f} h) y ya no se puede editar."
                                 if horas_transcurridas is not None else
                                 "⚠️ No se pudo determinar la antigüedad de esta factura.")
                    else:
                        st.success(f"✏️ Editando Factura N° **{formatear_numero_factura_display(venta_e['numero_factura'])}** "
                                   f"-- creada hace {horas_transcurridas:.1f} h, dentro del plazo permitido.")

                        with st.form("form_editar_factura"):
                            st.markdown("##### Datos generales")
                            fe1, fe2 = st.columns(2)
                            e_desc = fe1.text_input("Descripción", value=venta_e.get("descripcion", "")).upper()
                            e_metodo = fe2.selectbox("Método de Pago", ["EFECTIVO", "BOLD", "LLAVE", "NEQUI", "DAVIPLATA"],
                                                      index=["EFECTIVO", "BOLD", "LLAVE", "NEQUI", "DAVIPLATA"].index(venta_e.get("metodo_pago", "EFECTIVO")) if venta_e.get("metodo_pago") in ["EFECTIVO", "BOLD", "LLAVE", "NEQUI", "DAVIPLATA"] else 0)

                            fe3, fe4, fe5 = st.columns(3)
                            e_total = fe3.number_input("Total ($)", min_value=0, step=1000, value=int(venta_e.get("total", 0)))
                            e_abono = fe4.number_input("Abono ($)", min_value=0, step=1000, value=int(venta_e.get("abono", 0)))
                            e_saldo_calc = max(0, e_total - e_abono)
                            fe5.metric("Saldo (calculado)", f"${format_currency_co(e_saldo_calc)}")

                            e_entrega = st.text_input("Fecha/Hora Entrega", value=venta_e.get("fecha_entrega", "")).upper()

                            st.markdown("##### Fórmula (Rx)")
                            esf_od_prev, cil_od_prev, eje_od_prev = rx_string_a_numeros(venta_e.get("rx_final_od"))
                            esf_oi_prev, cil_oi_prev, eje_oi_prev = rx_string_a_numeros(venta_e.get("rx_final_oi"))
                            dp_prev = str(venta_e.get("dp", "") or "")
                            dp_od_prev, dp_oi_prev = (dp_prev.split("/") + [""])[:2] if "/" in dp_prev else (dp_prev, dp_prev)

                            st.markdown("**OD**")
                            eo1, eo2, eo3, eo4, eo5 = st.columns(5)
                            e_esf_od = eo1.number_input("Esfera OD", step=0.25, format="%.2f", value=esf_od_prev, key=f"e_esf_od_{venta_e['numero_factura']}")
                            e_cil_od = eo2.number_input("Cilindro OD", step=0.25, format="%.2f", value=cil_od_prev, key=f"e_cil_od_{venta_e['numero_factura']}")
                            e_eje_od = eo3.number_input("Eje OD", min_value=0, max_value=175, step=5, value=eje_od_prev, key=f"e_eje_od_{venta_e['numero_factura']}")
                            e_av_od = eo4.text_input("AV OD", value=venta_e.get("av_od", "")).upper()
                            e_dp_od = eo5.text_input("DP OD", value=dp_od_prev.strip()).upper()

                            st.markdown("**OI**")
                            ei1, ei2, ei3, ei4, ei5 = st.columns(5)
                            e_esf_oi = ei1.number_input("Esfera OI", step=0.25, format="%.2f", value=esf_oi_prev, key=f"e_esf_oi_{venta_e['numero_factura']}")
                            e_cil_oi = ei2.number_input("Cilindro OI", step=0.25, format="%.2f", value=cil_oi_prev, key=f"e_cil_oi_{venta_e['numero_factura']}")
                            e_eje_oi = ei3.number_input("Eje OI", min_value=0, max_value=175, step=5, value=eje_oi_prev, key=f"e_eje_oi_{venta_e['numero_factura']}")
                            e_av_oi = ei4.text_input("AV OI", value=venta_e.get("av_oi", "")).upper()
                            e_dp_oi = ei5.text_input("DP OI", value=dp_oi_prev.strip()).upper()

                            add_prev = 0.0
                            try:
                                add_prev = abs(float(str(venta_e.get("adicion", "") or "0").replace("+", "")))
                            except ValueError:
                                pass
                            e_add = st.number_input("Adición (ADD)", min_value=0.00, step=0.25, format="%.2f", value=add_prev)

                            guardar_edicion = st.form_submit_button("💾 Guardar Cambios", type="primary", use_container_width=True)

                        if guardar_edicion:
                            supabase.table("ventas_facturacion").update({
                                "descripcion": e_desc, "metodo_pago": e_metodo,
                                "total": int(e_total), "subtotal": int(e_total),
                                "abono": int(e_abono), "saldo": int(e_saldo_calc),
                                "fecha_entrega": e_entrega,
                                "rx_final_od": build_rx_string(e_esf_od, e_cil_od, e_eje_od),
                                "rx_final_oi": build_rx_string(e_esf_oi, e_cil_oi, e_eje_oi),
                                "adicion": f"{e_add:+.2f}" if e_add > 0.0 else "",
                                "dp": f"{e_dp_od}/{e_dp_oi}",
                                "av_od": e_av_od, "av_oi": e_av_oi,
                            }).eq("numero_factura", venta_e["numero_factura"]).execute()
                            st.session_state.global_toast = f"Factura #{formatear_numero_factura_display(venta_e['numero_factura'])} actualizada."
                            st.session_state.trigger_clear_editar = True
                            st.rerun()

    with tab_reimprimir:
        st.markdown("<h4 style='color:#000000;'>🖨️ Reimprimir Documentos de una Factura</h4>", unsafe_allow_html=True)
        st.caption("Busca una factura anterior y descarga sus documentos con la fecha original de emisión.")

        reimp_search = st.text_input("N° de Factura o Cédula del paciente:", key="reimp_search").strip().upper()

        if reimp_search:
            with st.spinner("Buscando factura..."):
                cond_reimp = filtro_busqueda_factura(reimp_search)
                filtro_or_reimp = ",".join(cond_reimp + [f"paciente_documento.eq.{reimp_search}"])
                res_reimp = supabase.table("ventas_facturacion").select("*").or_(
                    filtro_or_reimp
                ).neq("estado", "ANULADA").order("fecha_venta", desc=True).limit(1).execute()

            if not res_reimp.data:
                st.error("No se encontró ninguna factura activa para ese criterio.")
            else:
                venta_r = res_reimp.data[0]

                # Parsear fecha_venta original (incluye hora y timezone Colombia)
                fv_raw = venta_r.get("fecha_venta", "")
                try:
                    if "T" in fv_raw:
                        fecha_original = datetime.fromisoformat(fv_raw.replace("Z", "+00:00"))
                        # Convertir a hora Colombia si viene en UTC
                        fecha_original = fecha_original.astimezone(timezone(timedelta(hours=-5)))
                        # Quitar timezone para strftime (naive datetime)
                        fecha_original = fecha_original.replace(tzinfo=None)
                    else:
                        fecha_original = datetime.strptime(fv_raw[:10], "%Y-%m-%d")
                except Exception:
                    fecha_original = None

                fecha_display = fecha_original.strftime("%d/%m/%Y %H:%M") if fecha_original else "—"

                # Resumen de la factura encontrada
                with st.container(border=True):
                    rc1, rc2, rc3 = st.columns(3)
                    rc1.markdown(f"**Fac N°:** {formatear_numero_factura_display(venta_r['numero_factura'])}")
                    rc2.markdown(f"**Fecha original:** {fecha_display}")
                    rc3.markdown(f"**Estado:** `{venta_r.get('estado_lab', '—')}`")
                    rc1.markdown(f"**Titular:** {venta_r['titular_nombre']}")
                    rc2.markdown(f"**Total:** ${format_currency_co(int(venta_r.get('total', 0)))}")
                    rc3.markdown(f"**Saldo:** ${format_currency_co(int(venta_r.get('saldo', 0)))}")
                    st.markdown(f"**Detalle:** {venta_r.get('descripcion', '—')}")

                # Cargar datos del paciente
                pac_doc = venta_r.get("paciente_documento", "")
                pac_data_r = supabase.table("pacientes").select("*").eq("documento", pac_doc).execute().data
                paciente_r = pac_data_r[0] if pac_data_r else {
                    "nombre_completo": venta_r.get("titular_nombre", ""),
                    "documento": pac_doc, "direccion": "", "celular": ""
                }

                # La fórmula usada en ESTA venta específica ya se guarda
                # directamente en ventas_facturacion desde que se creó (no
                # depende de adivinar qué historia clínica corresponde por
                # fecha). Solo para ventas anteriores a este cambio, que no
                # tienen estos campos, se cae al comportamiento anterior:
                # buscar la historia clínica más cercana (anterior o igual)
                # a la fecha de venta.
                if venta_r.get("rx_final_od") or venta_r.get("rx_final_oi"):
                    hist_r = {
                        "rx_final_od": venta_r.get("rx_final_od", ""),
                        "rx_final_oi": venta_r.get("rx_final_oi", ""),
                        "adicion": venta_r.get("adicion", ""),
                        "dp": venta_r.get("dp", ""),
                        "observaciones": f"ORIGEN: {venta_r.get('origen_rx', '')}".strip(": "),
                    }
                    detalles_rx_venta = {
                        "av_od": venta_r.get("av_od", ""), "av_oi": venta_r.get("av_oi", ""),
                        "av_cerca_od": venta_r.get("av_cerca_od", ""), "av_cerca_oi": venta_r.get("av_cerca_oi", ""),
                    }
                else:
                    historias_r = supabase.table("historias_clinicas").select("*").eq(
                        "paciente_documento", pac_doc
                    ).order("fecha", desc=True).execute().data or []

                    hist_r = None
                    if historias_r and fecha_original:
                        # La más reciente que sea anterior o igual a la fecha de la venta
                        for h in historias_r:
                            h_raw = h.get("fecha", "")
                            try:
                                if "T" in h_raw:
                                    h_dt = datetime.fromisoformat(h_raw.replace("Z", "+00:00")).replace(tzinfo=None)
                                else:
                                    h_dt = datetime.strptime(h_raw[:10], "%Y-%m-%d")
                                if h_dt <= fecha_original:
                                    hist_r = h
                                    break
                            except Exception:
                                continue
                    if not hist_r and historias_r:
                        hist_r = historias_r[-1]  # Fallback: la más antigua disponible
                    if not hist_r:
                        hist_r = {"rx_final_od": "", "rx_final_oi": "", "dp": "", "adicion": "", "observaciones": ""}
                    detalles_rx_venta = {}

                st.markdown("---")
                st.markdown("**Selecciona los documentos a descargar:**")
                d1, d2, d3 = st.columns(3)

                # ── Documento 1: Factura (2 copias) ──────────────────────────────
                with d1:
                    with st.container(border=True):
                        st.markdown("**📄 Factura**")
                        st.caption("2 copias: cliente + óptica/caja")
                        try:
                            pdf_f = FPDF(orientation="P", unit="mm", format="Letter")
                            pdf_f.set_compression(True)
                            pdf_f.add_page()
                            dibujar_media_carta(pdf_f, paciente_r, hist_r, venta_r, "COPIA CLIENTE", fecha_impresion=fecha_original)
                            pdf_f.add_page()
                            dibujar_media_carta(pdf_f, paciente_r, hist_r, venta_r, "COPIA ÓPTICA / CAJA", fecha_impresion=fecha_original)
                            pdf_bytes_f = bytes(pdf_f.output())
                            st.download_button(
                                "⬇️ Descargar Factura",
                                data=pdf_bytes_f,
                                file_name=f"Factura_{venta_r['numero_factura']}.pdf",
                                mime="application/pdf",
                                use_container_width=True,
                                key=f"dl_fac_{venta_r['numero_factura']}"
                            )
                        except Exception as e:
                            st.error(f"Error generando factura: {e}")

                # ── Documento 2: Orden de laboratorio ────────────────────────────
                with d2:
                    with st.container(border=True):
                        st.markdown("**🔬 Orden de Laboratorio**")
                        st.caption("Con Rx y datos del trabajo")
                        try:
                            pdf_o = FPDF(orientation="P", unit="mm", format="Letter")
                            pdf_o.set_compression(True)
                            pdf_o.add_page()
                            dibujar_orden_laboratorio(pdf_o, paciente_r, hist_r, venta_r, fecha_impresion=fecha_original)
                            pdf_bytes_o = bytes(pdf_o.output())
                            st.download_button(
                                "⬇️ Descargar Orden de Lab",
                                data=pdf_bytes_o,
                                file_name=f"OrdenLab_{venta_r['numero_factura']}.pdf",
                                mime="application/pdf",
                                use_container_width=True,
                                key=f"dl_ord_{venta_r['numero_factura']}"
                            )
                        except Exception as e:
                            st.error(f"Error generando orden: {e}")

                # ── Documento 3: Prescripción clínica ────────────────────────────
                with d3:
                    with st.container(border=True):
                        st.markdown("**📋 Prescripción Clínica**")
                        st.caption("Receta del optómetra")
                        if str(hist_r.get('observaciones', '')).upper() == "FÓRMULA EXTERNA":
                            st.info("📄 Esta venta usó una **fórmula externa** (traída por el paciente). "
                                    "La prescripción lo indica claramente en observaciones.")
                        try:
                            # Reconstruir detalles_rx desde la historia clínica
                            rx_od_r = hist_r.get("rx_final_od", "") or ""
                            rx_oi_r = hist_r.get("rx_final_oi", "") or ""
                            def _parse_rx(rx_str):
                                parts = str(rx_str).replace("(", "").replace(")", "").split()
                                sph = parts[0] if len(parts) > 0 else ""
                                cyl = parts[1] if len(parts) > 1 else ""
                                axis = parts[2] if len(parts) > 2 else ""
                                return sph, cyl, axis
                            esf_od_r, cil_od_r, eje_od_r = _parse_rx(rx_od_r)
                            esf_oi_r, cil_oi_r, eje_oi_r = _parse_rx(rx_oi_r)
                            dp_r = hist_r.get("dp", "") or ""
                            dp_parts = str(dp_r).split("/")
                            dp_od_r = dp_parts[0].strip() if dp_parts else ""
                            dp_oi_r = dp_parts[1].strip() if len(dp_parts) > 1 else dp_od_r
                            add_r = hist_r.get("adicion", "") or ""
                            # Si la venta trae AV real guardado, se usa; si no
                            # (ventas anteriores a este cambio), se asume 20/20
                            # como valor razonable por defecto.
                            detalles_rx_r = {
                                "esf_od": esf_od_r, "cil_od": cil_od_r, "eje_od": eje_od_r,
                                "esf_oi": esf_oi_r, "cil_oi": cil_oi_r, "eje_oi": eje_oi_r,
                                "dp_od": dp_od_r, "dp_oi": dp_oi_r,
                                "adicion": add_r,
                                "av_od": detalles_rx_venta.get("av_od") or "20/20",
                                "av_oi": detalles_rx_venta.get("av_oi") or "20/20",
                                "av_cerca_od": detalles_rx_venta.get("av_cerca_od", ""),
                                "av_cerca_oi": detalles_rx_venta.get("av_cerca_oi", ""),
                                "tipo_lente": "", "uso": "", "filtro": "", "prox_control": ""
                            }
                            pdf_p = FPDF(orientation="P", unit="mm", format="Letter")
                            pdf_p.set_compression(True)
                            pdf_p.add_page()
                            dibujar_prescripcion_clinica(pdf_p, paciente_r, hist_r, detalles_rx_r, fecha_impresion=fecha_original)
                            pdf_bytes_p = bytes(pdf_p.output())
                            st.download_button(
                                "⬇️ Descargar Prescripción",
                                data=pdf_bytes_p,
                                file_name=f"Prescripcion_{venta_r['numero_factura']}.pdf",
                                mime="application/pdf",
                                use_container_width=True,
                                key=f"dl_presc_{venta_r['numero_factura']}"
                            )
                        except Exception as e:
                            st.error(f"Error generando prescripción: {e}")

                if not hist_r.get("rx_final_od") and not hist_r.get("rx_final_oi"):
                    st.warning("⚠️ No se encontró historia clínica con Rx para este paciente. La orden de laboratorio y prescripción irán sin datos de fórmula.")

    with tab_hist_fact:
        st.markdown("#### 🔍 Buscar Historial de un Paciente")
        mostrar_buscador_historial("hist_facturacion")


# ------------------------------------------
# MÓDULO 3: CUADRE DE CAJA (DD/MM/YYYY)
# ------------------------------------------
elif modulo == "📊 Cuadre de Caja Físico":
    styled_header("Cuadre de Caja Físico e Historial Diario", "📊")
    
    col_fc1, col_fc2 = st.columns([2, 1])
    with col_fc1:
        fecha_consulta = st.date_input("Selecciona la fecha a consultar:", now_co().date(), format="DD/MM/YYYY")
    with col_fc2:
        base_caja_inicial = st.number_input("Base Inicial en Gaveta ($)", min_value=0, value=50000, step=10000)

    fecha_str = fecha_consulta.strftime("%Y-%m-%d")
    
    tab_resumen, tab_gastos, tab_gastos_mensuales = st.tabs(
        ["💰 Resumen y Movimientos", "💸 Registrar Gasto de Caja", "📅 Gastos Mensuales"]
    )

    ventas = supabase.table("ventas_facturacion").select("*").gte("fecha_venta", f"{fecha_str}T00:00:00").lte("fecha_venta", f"{fecha_str}T23:59:59").neq("estado", "ANULADA").execute().data or []
    recaudos = supabase.table("pagos_saldos").select("*").gte("fecha_pago", f"{fecha_str}T00:00:00").lte("fecha_pago", f"{fecha_str}T23:59:59").execute().data or []
    gastos_todos_dia = supabase.table("gastos_caja").select("*").gte("fecha_gasto", f"{fecha_str}T00:00:00").lte("fecha_gasto", f"{fecha_str}T23:59:59").execute().data or []
    # El cuadre diario solo se cierra con gastos DIARIOS (operativos).
    # Los MENSUALES (nómina, arriendo, facturas de proveedores) no
    # distorsionan el cierre de caja del día -- se reflejan aparte, en
    # el balance mensual.
    gastos = [g for g in gastos_todos_dia if str(g.get('tipo_gasto') or 'DIARIO').upper() == 'DIARIO']
    gastos_mensuales_dia = [g for g in gastos_todos_dia if str(g.get('tipo_gasto') or 'DIARIO').upper() == 'MENSUAL']

    with tab_resumen:
        if gastos_mensuales_dia:
            total_men_dia = sum(g.get('monto', 0) for g in gastos_mensuales_dia)
            st.caption(f"📅 Hoy también se registraron **{len(gastos_mensuales_dia)}** gasto(s) mensual(es) "
                       f"por ${format_currency_co(total_men_dia)} -- no incluidos en este cuadre diario, "
                       f"ver pestaña 'Gastos Mensuales'.")

        abono_efectivo = sum(v.get('abono', 0) for v in ventas if str(v.get('metodo_pago') or '').upper() == 'EFECTIVO')
        abono_bancos = sum(v.get('abono', 0) for v in ventas if str(v.get('metodo_pago') or '').upper() != 'EFECTIVO')
        
        recaudo_efectivo = sum(r.get('monto_pagado', 0) for r in recaudos if str(r.get('metodo_pago') or '').upper() == 'EFECTIVO')
        recaudo_bancos = sum(r.get('monto_pagado', 0) for r in recaudos if str(r.get('metodo_pago') or '').upper() != 'EFECTIVO')
        
        gastos_efectivo = sum(g.get('monto', 0) for g in gastos if str(g.get('metodo_pago') or '').upper() == 'EFECTIVO')

        efectivo_caja = base_caja_inicial + (abono_efectivo + recaudo_efectivo) - gastos_efectivo
        total_bancos = abono_bancos + recaudo_bancos

        st.markdown("### 💵 Resumen de Caja")
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("💵 Efectivo Físico (En Gaveta)", f"${format_currency_co(efectivo_caja)}")
        col_m2.metric("🏦 Total Bancos (Digital)", f"${format_currency_co(total_bancos)}")
        col_m3.metric("✅ Flujo Total Diario", f"${format_currency_co(efectivo_caja + total_bancos + gastos_efectivo - base_caja_inicial)}")

        st.divider()
        st.markdown(f"#### 📜 Movimientos de Caja del Día ({fecha_consulta.strftime('%d/%m/%Y')})")
        
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
                if isinstance(val, (int, float)): return f"color: {'#E61B23' if val < 0 else '#00A650'}; font-weight: bold;"
                return ""
                
            st.dataframe(df_mov.style.map(color_mov, subset=['Monto']).format({"Monto": lambda x: f"${format_currency_co(abs(x))}"}), use_container_width=True)
            st.download_button(label="📊 Descargar Historial a Excel (.xlsx)", data=convert_df_to_excel(df_mov, "Caja"), file_name=f"Movimientos_{fecha_str}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.info("No hay movimientos financieros en la fecha seleccionada.")

    with tab_gastos:
        st.markdown("### 💸 Registrar Salida de Dinero (Gasto)")
        tipo_gasto_sel = st.radio(
            "Tipo de gasto:",
            ["🗓️ Diario (operativo)", "📅 Mensual (nómina, arriendo, facturas de proveedores...)"],
            key="tipo_gasto_radio", horizontal=True,
        )
        es_mensual = tipo_gasto_sel.startswith("📅")
        if es_mensual:
            st.caption("Este gasto no se restará del cuadre de caja de hoy -- se reflejará en el "
                       "balance del mes, en la pestaña 'Gastos Mensuales'.")
        col_g1, col_g2, col_g3 = st.columns([2, 1, 1])
        with col_g1: desc_gasto = st.text_input("Concepto / Descripción del Gasto", placeholder="Ej: Pago mensajería laboratorio", key="desc_gasto_input").upper()
        with col_g2: monto_gasto = int(clean_numeric_string(st.text_input("Valor ($)", key="monto_gasto_input", on_change=on_monto_gasto_change)) or 0)
        with col_g3: metodo_gasto = st.selectbox("Forma de Salida", ["EFECTIVO", "BOLD", "NEQUI", "DAVIPLATA"], key="metodo_gasto_input")
        
        if st.button("💾 Guardar Gasto de Caja", type="primary"):
            if not desc_gasto or monto_gasto <= 0: st.warning("⚠️ Ingresa una descripción y valor válidos.")
            else:
                supabase.table("gastos_caja").insert({
                    "descripcion": desc_gasto, "monto": monto_gasto, "metodo_pago": metodo_gasto,
                    "fecha_gasto": now_co().isoformat(),
                    "tipo_gasto": "MENSUAL" if es_mensual else "DIARIO",
                }).execute()
                st.session_state.global_toast = "Gasto registrado correctamente."
                st.session_state.trigger_clear_gastos = True
                st.rerun()

    with tab_gastos_mensuales:
        st.markdown("### 📅 Balance de Gastos Mensuales")
        st.caption("Gastos grandes recurrentes (nómina, arriendo, pagos a proveedores) que no forman "
                   "parte del cuadre de caja del día a día, comparados contra el ingreso del mes.")

        hoy_gm = now_co()
        meses_atras = st.slider("Meses hacia atrás a mostrar:", 1, 12, 6, key="meses_gastos_mensuales")
        mes_opciones = [(hoy_gm - pd.DateOffset(months=i)).strftime("%Y-%m") for i in range(meses_atras)]
        mes_sel_gm = st.selectbox("Mes a consultar:", mes_opciones, key="mes_gastos_mensuales")

        inicio_mes = f"{mes_sel_gm}-01T00:00:00"
        anio_gm, mes_num_gm = int(mes_sel_gm[:4]), int(mes_sel_gm[5:7])
        ultimo_dia = calendar.monthrange(anio_gm, mes_num_gm)[1]
        fin_mes = f"{mes_sel_gm}-{ultimo_dia:02d}T23:59:59"

        gastos_mes = supabase.table("gastos_caja").select("*") \
            .eq("tipo_gasto", "MENSUAL") \
            .gte("fecha_gasto", inicio_mes).lte("fecha_gasto", fin_mes).execute().data or []
        ventas_mes_gm = traer_todas_las_filas(
            "ventas_facturacion",
            filtros_fn=lambda q: q.neq("estado", "ANULADA").gte("fecha_venta", inicio_mes).lte("fecha_venta", fin_mes)
        )
        gastos_diarios_mes = supabase.table("gastos_caja").select("monto") \
            .eq("tipo_gasto", "DIARIO") \
            .gte("fecha_gasto", inicio_mes).lte("fecha_gasto", fin_mes).execute().data or []

        total_ingresos_mes = sum(v.get("total", 0) for v in ventas_mes_gm)
        total_gastos_mensuales = sum(g.get("monto", 0) for g in gastos_mes)
        total_gastos_diarios_mes = sum(g.get("monto", 0) for g in gastos_diarios_mes)
        balance_neto = total_ingresos_mes - total_gastos_mensuales - total_gastos_diarios_mes

        bm1, bm2, bm3, bm4 = st.columns(4)
        bm1.metric("💰 Ingresos del Mes", f"${format_currency_co(total_ingresos_mes)}")
        bm2.metric("📅 Gastos Mensuales", f"${format_currency_co(total_gastos_mensuales)}")
        bm3.metric("🗓️ Gastos Diarios (suma del mes)", f"${format_currency_co(total_gastos_diarios_mes)}")
        bm4.metric("✅ Balance Neto del Mes", f"${format_currency_co(balance_neto)}")

        st.divider()
        if gastos_mes:
            df_gm = pd.DataFrame(gastos_mes)[["fecha_gasto", "descripcion", "monto", "metodo_pago"]]
            df_gm["fecha_gasto"] = df_gm["fecha_gasto"].str[:10]
            df_gm = df_gm.sort_values("fecha_gasto", ascending=False)
            st.dataframe(
                df_gm.style.format({"monto": lambda x: f"${format_currency_co(x)}"}),
                use_container_width=True, hide_index=True,
                column_config={"fecha_gasto": "Fecha", "descripcion": "Concepto",
                               "monto": "Valor", "metodo_pago": "Método"}
            )
        else:
            st.info(f"No hay gastos mensuales registrados en {mes_sel_gm}.")

# ------------------------------------------
# MÓDULO 4: INVENTARIO BODEGA
# ------------------------------------------
elif modulo == "📦 Inventario":
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
                fi_raw = p.get("fecha_ingreso", "")
                fi_fmt = ""
                if fi_raw:
                    try: fi_fmt = datetime.strptime(str(fi_raw)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
                    except: fi_fmt = str(fi_raw)[:10]
                tabla_inv.append({"Código": str(p.get("codigo", "")), "Categoría": str(p.get("categoria", "")), "Marca": str(p.get("marca", "")).upper(), "Descripción": str(p.get("descripcion", "")).upper(), "Cant.": cant, "Costo": compra, "P. Venta": venta, "Ingreso": fi_fmt})
            
            df_inv = pd.DataFrame(tabla_inv)
            
            def color_stock(val):
                return "color: #E61B23; font-weight: bold;" if val == 0 else ""
                
            st.dataframe(df_inv.style.format({"Costo": lambda x: f"${format_currency_co(x)}", "P. Venta": lambda x: f"${format_currency_co(x)}"}).map(color_stock, subset=['Cant.']), use_container_width=True)
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
            inv_categoria = st.selectbox("Categoría", ["Montura", "Lente de Contacto", "Accesorio", "Estuche", "Líquido", "Otro"])
            
            if inv_categoria == "Montura":
                col_m1, col_m2 = st.columns(2)
                inv_marca = col_m1.text_input("Marca *", key="m_marca").upper()
                inv_prov = col_m2.text_input("Proveedor", key="m_prov").upper()
                
                col_m3, col_m4 = st.columns(2)
                inv_mat = col_m3.selectbox("Material", ["METALICA", "TITANIO", "ALUMINIO", "ACERO", "PLASTICO", "ACETATO", "TR 90"], key="m_mat")
                inv_cant = col_m4.number_input("Cantidad a Ingresar", min_value=1, step=1, value=1, key="m_cant")
                
                c_pc, c_pv = st.columns(2)
                val_compra = int(clean_numeric_string(c_pc.text_input("Precio Compra Unitario $", key="p_compra_m", on_change=on_p_compra_m_change)) or 0)
                val_venta = int(clean_numeric_string(c_pv.text_input("Precio Venta Unitario $", key="p_venta_m", on_change=on_p_venta_m_change)) or 0)
                
                st.markdown("---")
                st.markdown("**Detalle de Referencias y Colores**")
                monturas_data = []
                
                if inv_cant == 1:
                    cm1, cm2 = st.columns(2)
                    m_ref = cm1.text_input("N° Referencia (Código) *", key="m_ref_unico").upper()
                    m_color = cm2.text_input("Color *", key="m_color_unico").upper()
                    monturas_data.append((m_ref, m_color))
                else:
                    base_ref = st.text_input("Referencia Base (Para autocompletar)", help="Ej: Si digitas '123', se autocompletará 123-1, 123-2, etc.", key="m_base_ref").upper()
                    st.caption("Modifica manualmente los colores y el número de referencia final si es necesario:")
                    for i in range(int(inv_cant)):
                        cm1, cm2 = st.columns(2)
                        m_ref = cm1.text_input(f"Ref. Montura {i+1} *", value=f"{base_ref}-{i+1}" if base_ref else "", key=f"ref_{i}").upper()
                        m_color = cm2.text_input(f"Color Montura {i+1} *", key=f"col_{i}").upper()
                        monturas_data.append((m_ref, m_color))
                
                if st.button("💾 Guardar Montura(s)", type="primary", use_container_width=True):
                    if not inv_marca or any(not r or not c for r, c in monturas_data):
                        st.error("⚠️ Marca, Referencia y Color son obligatorios para todas las monturas listadas.")
                    else:
                        try:
                            for r, c in monturas_data:
                                desc_final = f"MONTURA {inv_mat} - COLOR {c}"
                                supabase.table("inventario").insert({
                                    "codigo": r, "categoria": "Montura", "marca": inv_marca, 
                                    "descripcion": desc_final, "proveedor": inv_prov, 
                                    "cantidad": 1, "precio_compra": val_compra, "precio_venta": val_venta, 
                                    "fecha_ingreso": now_co().isoformat()
                                }).execute()
                            st.session_state.global_toast = f"{inv_cant} montura(s) registrada(s) correctamente."
                            st.session_state.ultima_cant_monturas = int(inv_cant)
                            st.session_state.trigger_clear_montura = True
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar en base de datos: {e}")
            else:
                col_i1, col_i2 = st.columns(2)
                with col_i1:
                    inv_codigo = st.text_input("Código *", key="inv_codigo").upper()
                    inv_marca = st.text_input("Marca *", key="inv_marca").upper()
                with col_i2:
                    inv_desc = st.text_input("Descripción *", key="inv_desc").upper()
                    inv_prov = st.text_input("Proveedor", key="inv_prov").upper()
                    
                c1, c2, c3 = st.columns(3)
                inv_cant = c1.number_input("Cantidad Inicial", min_value=0, step=1, value=1)
                val_compra = int(clean_numeric_string(c2.text_input("Precio Compra $", key="p_compra_input", on_change=on_p_compra_change)) or 0)
                val_venta = int(clean_numeric_string(c3.text_input("Precio Venta $", key="p_venta_input", on_change=on_p_venta_change)) or 0)
                    
                if st.button("💾 Guardar Producto", type="primary", use_container_width=True):
                    if not inv_codigo or not inv_marca or not inv_desc: 
                        st.error("⚠️ Código, Marca y Descripción son obligatorios.")
                    else:
                        try:
                            supabase.table("inventario").insert({
                                "codigo": inv_codigo, "categoria": inv_categoria, "marca": inv_marca, 
                                "descripcion": inv_desc, "proveedor": inv_prov, "cantidad": inv_cant, 
                                "precio_compra": val_compra, "precio_venta": val_venta, 
                                "fecha_ingreso": now_co().isoformat()
                            }).execute()
                            st.session_state.global_toast = f"Producto '{inv_codigo}' registrado."
                            st.session_state.trigger_clear_producto = True
                            st.rerun()
                        except Exception as e: 
                            st.error(f"Error: {e}")

    with tab_ajuste:
        codigo_ajuste = st.text_input("Buscar por Código:", key="codigo_ajuste_input").upper()
        if codigo_ajuste:
            res_prod = supabase.table("inventario").select("*").eq("codigo", codigo_ajuste).execute()
            if res_prod.data:
                prod = res_prod.data[0]
                stock = int(prod["cantidad"])
                st.info(f"**{prod['marca']}** - {prod['descripcion']} | Stock: **{stock}**")
                c1, c2, c3 = st.columns([1, 1, 2])
                with c1: accion = st.radio("Acción:", ["Sumar (+)", "Restar (-)"], key="ajuste_accion")
                with c2: cant_ajustar = st.number_input("Cantidad", min_value=1, step=1, value=1, key="ajuste_cantidad")
                with c3:
                    st.write(""); st.write("")
                    if st.button("Actualizar Stock", type="primary", use_container_width=True):
                        nuevo_stock = stock + cant_ajustar if accion == "Sumar (+)" else stock - cant_ajustar
                        if nuevo_stock < 0: st.error("⚠️ Stock negativo.")
                        else:
                            supabase.table("inventario").update({"cantidad": nuevo_stock}).eq("codigo", codigo_ajuste).execute()
                            st.session_state.global_toast = f"Stock actualizado a {nuevo_stock}."
                            st.session_state.trigger_clear_ajuste = True
                            st.rerun()

# ------------------------------------------
# MÓDULO 5: CONTROL DE TRABAJOS
# ------------------------------------------
elif modulo == "🔬 Control de Trabajos":
    styled_header("Control de Trabajos", "🔬")
    
    tab_trabajos, tab_labs = st.tabs(["📋 Control de Trabajos", "⚙️ Gestionar Laboratorios"])
    
    with tab_labs:
        st.markdown("### Configuración de Laboratorios Externos")
        nuevo_lab = st.text_input("Agregar Nuevo Laboratorio:", placeholder="Ej: OPTILAB BOGOTÁ", key="nuevo_lab_input").upper()
        if st.button("➕ Añadir Laboratorio", type="primary"):
            if nuevo_lab:
                try:
                    supabase.table("laboratorios").insert({"nombre": nuevo_lab}).execute()
                    st.session_state.global_toast = "Laboratorio añadido correctamente."
                    st.session_state.trigger_clear_laboratorio = True
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
        
        def _filtros_trabajos(q):
            q = q.neq("estado", "ANULADA")
            # Las ventas menores (cordones, líquidos, etc.) no tienen
            # seguimiento de laboratorio -- no pertenecen a esta vista.
            q = q.not_.like("numero_factura", "MEN-%")
            if filtro_estado != "Todos los Activos":
                q = q.eq("estado_lab", filtro_estado)
            if search_fac_lab:
                q = q.eq("numero_factura", search_fac_lab)
            return q

        trabajos_todos = traer_todas_las_filas(
            "ventas_facturacion", filtros_fn=_filtros_trabajos)
        # Se ordena en Python por el valor numérico real de la factura
        # (no por fecha_venta como texto, que puede tener inconsistencias
        # de formato entre facturas nuevas y migradas). Como TRABAJOS.xlsx
        # y REGISTRO_DIARIO.xlsx comparten la misma numeración secuencial
        # del negocio, esto da un orden cronológico confiable.
        trabajos_todos.sort(key=lambda t: valor_numerico_factura(t.get("numero_factura")), reverse=True)
        opciones_labs = ["NO ASIGNADO"] + [l['nombre'] for l in (supabase.table("laboratorios").select("nombre").execute().data or [])]

        # Paginación: 15 por página para no colapsar la carga con miles
        # de trabajos históricos migrados.
        POR_PAGINA_TRAB = 15
        total_trab = len(trabajos_todos)
        total_pags_trab = max(1, (total_trab + POR_PAGINA_TRAB - 1) // POR_PAGINA_TRAB)
        st.session_state.setdefault("trab_pagina", 1)
        if search_fac_lab or filtro_estado:
            # Si cambian los filtros de búsqueda, reiniciar a la página 1
            filtros_actuales = (search_fac_lab, filtro_estado)
            if st.session_state.get("trab_filtros_prev") != filtros_actuales:
                st.session_state.trab_pagina = 1
                st.session_state.trab_filtros_prev = filtros_actuales
        pag_trab = min(st.session_state.trab_pagina, total_pags_trab)
        inicio_trab = (pag_trab - 1) * POR_PAGINA_TRAB
        trabajos = trabajos_todos[inicio_trab:inicio_trab + POR_PAGINA_TRAB]

        if trabajos_todos:
            st.caption(f"**{total_trab}** trabajo(s) · Página **{pag_trab}** de **{total_pags_trab}**")

        if trabajos:
            for t in trabajos:
                est_act = t.get("estado_lab", "Pendiente de enviar")
                fac_id = t['numero_factura']
                fac_id_display = formatear_numero_factura_display(fac_id)

                if est_act == "Pendiente de enviar":
                    border_color = "#E61B23"; card_bg = "#fff8f8"; badge_bg = "#ffebee"; badge_fg = "#c62828"
                elif est_act == "En Laboratorio":
                    border_color = "#ff9800"; card_bg = "#fffbf4"; badge_bg = "#fff3e0"; badge_fg = "#ef6c00"
                elif est_act == "Recibido en Óptica":
                    border_color = "#2196F3"; card_bg = "#f5f9ff"; badge_bg = "#e3f2fd"; badge_fg = "#1565c0"
                else:
                    border_color = "#4CAF50"; card_bg = "#f6fdf6"; badge_bg = "#e8f5e9"; badge_fg = "#2e7d32"

                with st.container(border=True):
                    # Estrategia definitiva: el script se ejecuta DESDE DENTRO del container.
                    # Sube por el DOM buscando su propio stVerticalBlockBorderWrapper y le
                    # añade un atributo data-estado. El CSS global (abajo, sección 12b) usa
                    # ese atributo con alta especificidad para pintar el borde lateral.
                    # Usar setAttribute en lugar de style.setProperty evita la guerra !important.
                    st.markdown(f"""
                        <script>
                        (function() {{
                            function tag(el) {{
                                var node = el ? el.parentElement : null;
                                var attempts = 0;
                                var interval = setInterval(function() {{
                                    var cur = node;
                                    while (cur && cur !== document.body) {{
                                        if (cur.getAttribute && cur.getAttribute('data-testid') === 'stVerticalBlockBorderWrapper') {{
                                            cur.setAttribute('data-estado', '{est_act}');
                                            // Propaga color al stVerticalBlock interior
                                            var inner = cur.querySelector('[data-testid="stVerticalBlock"]');
                                            if (inner) {{ inner.style.setProperty('background-color', '{card_bg}', 'important'); }}
                                            clearInterval(interval);
                                            return;
                                        }}
                                        cur = cur.parentElement;
                                    }}
                                    if (++attempts > 20) clearInterval(interval);
                                }}, 50);
                            }}
                            var sc = document.currentScript;
                            if (document.readyState === 'loading') {{
                                document.addEventListener('DOMContentLoaded', function() {{ tag(sc); }});
                            }} else {{
                                tag(sc);
                            }}
                        }})();
                        </script>
                        <style>
                        /* Estilo de selectbox en tarjetas de lab — apunta al wrapper externo
                           de Streamlit que React no toca, garantizando persistencia. */
                        [data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stSelectbox"] {{
                            background-color: transparent !important;
                            border: none !important;
                        }}
                        [data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stSelectbox"] > div:last-child {{
                            background-color: #f2f2f2 !important;
                            border: 1.5px solid #b0b0b0 !important;
                            border-radius: 6px !important;
                        }}
                        [data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stSelectbox"] [data-baseweb="select"],
                        [data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stSelectbox"] [data-baseweb="select"] > div {{
                            background-color: transparent !important;
                            border: none !important;
                            box-shadow: none !important;
                        }}
                        </style>
                        <div style="margin-bottom:10px; padding-top:2px;">
                            <span style="background-color:{badge_bg}; color:{badge_fg}; padding:4px 12px;
                                border-radius:20px; font-weight:700; font-size:0.8em; letter-spacing:0.6px;">
                                {est_act.upper()}
                            </span>
                        </div>
                    """, unsafe_allow_html=True)

                    c1, c2, c3 = st.columns([2, 2, 2])
                    with c1:
                        st.markdown(f"<span style='font-size:1.3em; font-weight:900; color:#000;'>Fac N° {fac_id_display}</span>", unsafe_allow_html=True)
                        st.markdown(f"**Titular:** {t['titular_nombre']}")
                        st.markdown(f"**Detalle:** {t['descripcion']}")
                    with c2:
                        entrega_val = t.get('fecha_entrega', '') or ''
                        entrega_txt = entrega_val.strip() if entrega_val.strip() else "—"
                        st.markdown(f"**Entrega:** {entrega_txt}")
                        if int(t.get('saldo', 0)) > 0:
                            st.markdown(f"**Saldo:** ${format_currency_co(int(t['saldo']))}")
                        else:
                            st.markdown("**Pagado 100%** ✅")
                    with c3:
                        posibles = ["Pendiente de enviar", "En Laboratorio", "Recibido en Óptica", "Entregado"]
                        idx_est = posibles.index(est_act) if est_act in posibles else 0
                        nuevo_est = st.selectbox("Estado de la Factura", posibles, index=idx_est, key=f"est_{fac_id}")

                        lab_act = t.get("laboratorio") or "NO ASIGNADO"
                        idx_lab = opciones_labs.index(lab_act) if lab_act in opciones_labs else 0
                        nuevo_lab_sel = st.selectbox("Laboratorio Externo:", opciones_labs, index=idx_lab, key=f"lab_{fac_id}")

                        if nuevo_est != est_act or nuevo_lab_sel != lab_act:
                            if st.button(f"💾 Guardar #{fac_id_display}", key=f"btn_est_{fac_id}", type="primary"):
                                supabase.table("ventas_facturacion").update({"estado_lab": nuevo_est, "laboratorio": nuevo_lab_sel if nuevo_lab_sel != "NO ASIGNADO" else None}).eq("numero_factura", fac_id).execute()
                                st.session_state.global_toast = f"Trabajo actualizado a: {nuevo_est}"
                                st.rerun()

                        # Botón WhatsApp — aparece solo cuando el estado es "Recibido en Óptica"
                        if est_act == "Recibido en Óptica":
                            nombre_pac = str(t.get("titular_nombre", "")).split()[0].capitalize()
                            celular_pac = str(t.get("titular_tel", t.get("celular", ""))).strip()
                            if not celular_pac or celular_pac in ("None", ""):
                                pac_data = supabase.table("pacientes").select("celular").eq("documento", str(t.get("paciente_documento",""))).execute().data
                                celular_pac = str(pac_data[0].get("celular", "")) if pac_data else ""
                            cel_digits = "".join(filter(str.isdigit, celular_pac))
                            if cel_digits.startswith("57") and len(cel_digits) == 12:
                                cel_wa = cel_digits
                            elif len(cel_digits) == 10:
                                cel_wa = "57" + cel_digits
                            else:
                                cel_wa = cel_digits
                            # Mensaje sin emojis para evitar problemas de codificación
                            msg_wa = (
                                f"Hola {nombre_pac}, te saludamos de Boomerang Vision. "
                                f"Te informamos que tus gafas ya se encuentran listas para retirar "
                                f"en nuestra optica. Te esperamos!"
                            )
                            import urllib.parse as _up
                            sin_cel = not cel_wa or len(cel_wa) < 10
                            wa_url  = f"https://wa.me/{cel_wa}?text={_up.quote(msg_wa)}" if not sin_cel else "#"
                            btn_opacity = "opacity:0.5;cursor:not-allowed;pointer-events:none;" if sin_cel else ""
                            aviso_p = (
                                "<p style='margin:6px 0 0 0;font-size:0.78em;"
                                "color:#b45309;text-align:center;'>"
                                "Sin numero de celular registrado para este paciente.</p>"
                            ) if sin_cel else ""
                            # SVG fuera del f-string para evitar que las llaves de los path
                            # sean interpretadas como variables de Python
                            svg_icon = (
                                '<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" '
                                'viewBox="0 0 24 24" fill="white" style="flex-shrink:0;">'
                                '<path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967'
                                '-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164'
                                '-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475'
                                '-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606'
                                '.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497'
                                '.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207'
                                '-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01'
                                '-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479'
                                ' 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487'
                                '.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118'
                                '.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289'
                                '.173-1.413-.074-.124-.272-.198-.57-.347z"/>'
                                '<path d="M12 0C5.373 0 0 5.373 0 12c0 2.123.554 4.116'
                                ' 1.524 5.845L0 24l6.318-1.508A11.95 11.95 0 0012 24'
                                'c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.818'
                                'a9.808 9.808 0 01-5.032-1.388l-.36-.214-3.733.891'
                                '.939-3.618-.236-.374A9.808 9.808 0 012.182 12'
                                'C2.182 6.575 6.575 2.182 12 2.182S21.818 6.575'
                                ' 21.818 12 17.425 21.818 12 21.818z"/>'
                                '</svg>'
                            )
                            wa_html = (
                                '<div style="margin-top:12px;margin-bottom:16px;width:100%;box-sizing:border-box;">'
                                f'<a href="{wa_url}" target="_blank" style="'
                                'display:flex;align-items:center;justify-content:center;'
                                'gap:8px;width:100%;box-sizing:border-box;'
                                'background-color:#25D366;color:#ffffff;'
                                'padding:9px 12px;border-radius:6px;'
                                'font-weight:700;font-size:0.85em;'
                                'text-decoration:none;letter-spacing:0.2px;'
                                f'box-shadow:0 2px 6px rgba(37,211,102,0.30);{btn_opacity}">'
                                + svg_icon +
                                'Avisar al paciente por WhatsApp'
                                '</a>'
                                + aviso_p +
                                '</div>'
                            )
                            st.markdown(wa_html, unsafe_allow_html=True)

            if total_pags_trab > 1:
                nt1, nt2, nt3, nt4, nt5 = st.columns([1, 1, 2, 1, 1])
                if nt1.button("⏮ Primera", key="trab_first", disabled=(pag_trab == 1), use_container_width=True):
                    st.session_state.trab_pagina = 1; st.rerun()
                if nt2.button("◀ Anterior", key="trab_prev", disabled=(pag_trab == 1), use_container_width=True):
                    st.session_state.trab_pagina = pag_trab - 1; st.rerun()
                nt3.markdown(f"<div style='text-align:center;padding-top:8px;'>{pag_trab} / {total_pags_trab}</div>", unsafe_allow_html=True)
                if nt4.button("Siguiente ▶", key="trab_next", disabled=(pag_trab == total_pags_trab), use_container_width=True):
                    st.session_state.trab_pagina = pag_trab + 1; st.rerun()
                if nt5.button("Última ⏭", key="trab_last", disabled=(pag_trab == total_pags_trab), use_container_width=True):
                    st.session_state.trab_pagina = total_pags_trab; st.rerun()
        else:
            st.info("No hay trabajos registrados con esos filtros.")

# ------------------------------------------
# MÓDULO 6: CRM Y FIDELIZACIÓN (DD/MM/YYYY)
# ------------------------------------------
elif modulo == "📅 CRM y Fidelización":
    styled_header("CRM y Retención de Pacientes", "📅")
    
    hoy = now_co()
    if hoy.day == 1:
        st.success(f"🔔 **¡Hoy inicia un nuevo mes!** Es el momento perfecto para revisar la lista de cumpleaños y enviar recordatorios de control anual a tus pacientes.")
    
    tab_anual, tab_cumple, tab_directorio, tab_plantillas = st.tabs(["🔄 Control Anual", "🎂 Cumpleaños", "📞 Directorio", "⚙️ Plantillas WhatsApp"])
    
    if "tpl_anual" not in st.session_state:
        try:
            tpl_db = supabase.table("configuracion").select("clave,valor").in_("clave", ["tpl_anual","tpl_cumple"]).execute().data or []
            tpl_map = {r["clave"]: r["valor"] for r in tpl_db}
        except Exception:
            tpl_map = {}
        st.session_state.tpl_anual = tpl_map.get("tpl_anual", "¡Hola [NOMBRE]! Te saludamos de Boomerang Visión 👓. Ha pasado un año desde tu último examen visual y queremos invitarte a tu control anual para cuidar de tu salud visual. ¿Te gustaría agendar una cita?")
        st.session_state.tpl_cumple = tpl_map.get("tpl_cumple", "¡Feliz cumpleaños, [NOMBRE]! 🥳 Te deseamos un día maravilloso de parte de todo el equipo de Boomerang Visión. Queremos regalarte un descuento especial del 20% en tu próximo par de lentes o montura en este mes. ¡Te esperamos!")

    with tab_anual:
        with st.spinner("Cargando historial de pacientes..."):
            historias_todas = traer_todas_las_filas(
                "historias_clinicas",
                columnas="paciente_documento,nombre_legado,celular_legado,fecha")
            # Se trae UNA sola vez, como índice, en vez de consultar pacientes
            # individualmente por cada historia (evita el patrón N+1: con
            # miles de historias migradas, eso podía disparar cientos de
            # consultas innecesarias y, además, siempre fallaba mientras
            # pacientes esté vacía).
            pacientes_idx = {
                p["documento"]: p
                for p in traer_todas_las_filas("pacientes", columnas="documento,nombre_completo,celular")
            }

        # Última visita por documento (una historia puede repetirse por paciente)
        ultima_visita = {}
        for h in historias_todas:
            doc = h.get("paciente_documento")
            if not doc:
                continue
            f_str = h.get("fecha")
            if not f_str:
                continue
            try:
                f_dt = datetime.fromisoformat(f_str.replace("Z", "+00:00")).date() if "T" in f_str else datetime.strptime(f_str[:10], "%Y-%m-%d").date()
            except Exception:
                continue
            actual = ultima_visita.get(doc)
            if not actual or f_dt > actual["fecha"]:
                ultima_visita[doc] = {
                    "fecha": f_dt,
                    "nombre_legado": h.get("nombre_legado"),
                    "celular_legado": h.get("celular_legado"),
                }

        pacientes_para_llamar = []
        for doc, info in ultima_visita.items():
            if not (330 <= (hoy.date() - info["fecha"]).days <= 400):
                continue
            p_activo = pacientes_idx.get(doc)
            # Se prioriza el dato del paciente activo (más probable que esté
            # actualizado); si no existe, se usa el nombre/celular legado
            # de la propia historia migrada.
            nombre = (p_activo or {}).get("nombre_completo") or info.get("nombre_legado") or ""
            celular = (p_activo or {}).get("celular") or info.get("celular_legado") or ""
            if not nombre:
                continue
            pacientes_para_llamar.append({
                "Documento": doc, "Nombre": nombre, "Celular": celular,
                "Ultima_Consulta": info["fecha"].strftime("%d/%m/%Y"),
                "Activo": p_activo is not None,
            })
        pacientes_para_llamar.sort(key=lambda x: x["Ultima_Consulta"])

        if pacientes_para_llamar:
            st.info(f"Se encontraron **{len(pacientes_para_llamar)}** pacientes para control anual.")
            for item in pacientes_para_llamar:
                nombre_corto = item['Nombre'].split()[0]
                msg_final = st.session_state.tpl_anual.replace("[NOMBRE]", nombre_corto)
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 2])
                    etiqueta_legado = "" if item["Activo"] else "  ·  📜 solo en histórico"
                    c1.markdown(f"**👤 {str(item['Nombre']).upper()}**{etiqueta_legado}\n\nCédula: {item['Documento']} | Última visita: {item['Ultima_Consulta']}")
                    c2.markdown(f"📱 Cel: `{item['Celular'] or '—'}`")
                    if normalizar_texto_busqueda(item['Celular']) and item['Celular']:
                        c3.link_button("💬 Enviar WhatsApp", get_whatsapp_link(item['Celular'], msg_final), use_container_width=True)
                    else:
                        c3.button("💬 Enviar WhatsApp", disabled=True, use_container_width=True,
                                  key=f"wa_off_anual_{item['Documento']}", help="Sin celular registrado")
        else: st.info("No hay pacientes cumpliendo un año de su última consulta.")

    with tab_cumple:
        with st.spinner("Cargando directorio..."):
            todos_pacientes = traer_todas_las_filas("pacientes")
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
        POR_PAGINA = 50
        d_col1, d_col2 = st.columns([3, 1])
        busqueda_dir = d_col1.text_input("🔍 Filtrar por nombre o cédula:").upper()

        # Construir lista filtrada
        tabla_dir = []
        for p in todos_pacientes:
            fnac_raw = p.get("fecha_nacimiento", "N/A")
            fnac_fmt = "N/A"
            if fnac_raw and fnac_raw != "N/A":
                try: fnac_fmt = datetime.strptime(str(fnac_raw)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
                except: pass
            if not busqueda_dir or busqueda_dir in str(p.get("nombre_completo", "")).upper() or busqueda_dir in str(p.get("documento", "")):
                tabla_dir.append({"Documento": str(p.get("documento", "")), "Nombre": str(p.get("nombre_completo", "")).upper(), "Celular": p.get("celular", "N/A"), "F. Nacimiento": fnac_fmt, "Habeas Data": "Sí" if p.get("habeas_data") else "No"})

        total = len(tabla_dir)
        total_pags = max(1, (total + POR_PAGINA - 1) // POR_PAGINA)
        if "dir_pagina" not in st.session_state: st.session_state.dir_pagina = 1
        if busqueda_dir: st.session_state.dir_pagina = 1  # reset al buscar

        pag = st.session_state.dir_pagina
        inicio = (pag - 1) * POR_PAGINA
        fin    = inicio + POR_PAGINA
        pagina_actual = tabla_dir[inicio:fin]

        if tabla_dir:
            st.caption(f"**{total}** pacientes registrados  •  Página **{pag}** de **{total_pags}**")
            df_dir = pd.DataFrame(pagina_actual)
            st.dataframe(df_dir, use_container_width=True)

            # Controles de paginación
            if total_pags > 1:
                nav1, nav2, nav3, nav4, nav5 = st.columns([1, 1, 2, 1, 1])
                if nav1.button("⏮ Primera", key="dir_first", disabled=(pag==1)):
                    st.session_state.dir_pagina = 1; st.rerun()
                if nav2.button("◀ Anterior", key="dir_prev", disabled=(pag==1)):
                    st.session_state.dir_pagina = pag - 1; st.rerun()
                nav3.markdown(f"<div style='text-align:center; padding-top:8px;'>{pag} / {total_pags}</div>", unsafe_allow_html=True)
                if nav4.button("Siguiente ▶", key="dir_next", disabled=(pag==total_pags)):
                    st.session_state.dir_pagina = pag + 1; st.rerun()
                if nav5.button("Última ⏭", key="dir_last", disabled=(pag==total_pags)):
                    st.session_state.dir_pagina = total_pags; st.rerun()

            df_full = pd.DataFrame(tabla_dir)
            st.download_button("📊 Descargar Directorio completo (.xlsx)", convert_df_to_excel(df_full, "Pacientes"), "Directorio.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.info("No hay registros que coincidan.")
    with tab_plantillas:
        st.markdown("### Personaliza tus Mensajes de WhatsApp")
        st.caption("Usa la etiqueta [NOMBRE] para insertar automáticamente el nombre del paciente.")
        st.session_state.tpl_anual = st.text_area("Plantilla Control Anual", value=st.session_state.tpl_anual, height=100)
        st.session_state.tpl_cumple = st.text_area("Plantilla Cumpleaños", value=st.session_state.tpl_cumple, height=100)
        if st.button("💾 Guardar Plantillas", type="primary"):
            try:
                supabase.table("configuracion").upsert({"clave": "tpl_anual", "valor": st.session_state.tpl_anual}).execute()
                supabase.table("configuracion").upsert({"clave": "tpl_cumple", "valor": st.session_state.tpl_cumple}).execute()
                st.success("¡Plantillas guardadas permanentemente en la base de datos!")
            except Exception:
                st.success("¡Plantillas actualizadas para esta sesión! (Para persistencia crea la tabla 'configuracion' con columnas clave/valor en Supabase)")

# ------------------------------------------
# MÓDULO 7: ANALÍTICA Y GRÁFICO AGRUPADO
# ------------------------------------------
elif modulo == "📈 Analítica y Estadísticas":
    styled_header("Dashboard Analítico y Respaldo General", "📈")
    
    ventas_db = traer_todas_las_filas(
        "ventas_facturacion",
        filtros_fn=lambda q: q.neq("estado", "ANULADA"),
        orden_col="fecha_venta", orden_desc=True)
    hoy_an = now_co()
    mes_actual = hoy_an.strftime("%Y-%m")
    ventas_mes = [v for v in ventas_db if str(v.get("fecha_venta","")).startswith(mes_actual)]
    total_mes = sum(int(v.get("total",0)) for v in ventas_mes)
    recaudado_mes = sum(int(v.get("abono",0)) for v in ventas_mes)
    pendiente_mes = total_mes - recaudado_mes
    
    km1, km2, km3, km4 = st.columns(4)
    km1.metric("🛍️ Ventas del mes",    f"{len(ventas_mes)}")
    km2.metric("💰 Facturado",          f"${format_currency_co(total_mes)}")
    km3.metric("✅ Recaudado",          f"${format_currency_co(recaudado_mes)}")
    km4.metric("⏳ Por recaudar",       f"${format_currency_co(pendiente_mes)}")
    st.markdown("---")
    gastos_db = supabase.table("gastos_caja").select("*").execute().data or []
    
    if ventas_db:
        df_dash = pd.DataFrame(ventas_db)
        # format='ISO8601' + errors='coerce': la tabla mezcla fechas de
        # facturas nuevas (con microsegundos, ej. "...T10:23:45.123456-05:00")
        # con fechas migradas del histórico (sin microsegundos, ej.
        # "...T00:00:00-05:00"). Sin 'ISO8601', pandas infiere un formato
        # fijo del primer valor y revienta al toparse con el otro formato,
        # aunque ambos sean ISO8601 perfectamente válidos. 'coerce' además
        # evita que una fecha vacía/corrupta tumbe todo el módulo.
        df_dash['fecha_venta'] = pd.to_datetime(
            df_dash['fecha_venta'], format='ISO8601', errors='coerce')
        filas_antes = len(df_dash)
        df_dash = df_dash.dropna(subset=['fecha_venta'])
        if len(df_dash) < filas_antes:
            st.caption(f"⚠️ Se omitieron {filas_antes - len(df_dash)} registro(s) "
                       f"con fecha inválida en el análisis.")
        df_dash['mes_anio'] = df_dash['fecha_venta'].dt.strftime('%Y-%m')
        
        total_cartera_pendiente = df_dash['saldo'].sum()
        
        modo_analitica = st.radio("Modo de Visualización:", ["Resumen Global", "Filtrar por Mes Específico", "Comparativa Multimes"], horizontal=True)
        # Salvaguarda: excluir meses futuros del selector. La causa real
        # de fechas futuras que aparecían aquí (año 2027 por error de
        # tecleo en el Excel original) ya se corrigió en el dato migrado,
        # pero este filtro protege contra cualquier otra fecha corrupta
        # que se cuele -- una venta jamás puede ser de un mes que no ha
        # llegado todavía.
        mes_actual_str = hoy_an.strftime("%Y-%m")
        meses_disponibles = sorted(
            (m for m in df_dash['mes_anio'].unique() if m <= mes_actual_str),
            reverse=True)
        
        if modo_analitica == "Filtrar por Mes Específico":
            mes_sel = st.selectbox("Selecciona el mes a analizar:", meses_disponibles)
            df_filtered = df_dash[df_dash['mes_anio'] == mes_sel]
            gastos_filtered = [g for g in gastos_db if _fecha_gasto_seguro(g.get('fecha_gasto')) == mes_sel] if gastos_db else []
            
            total_recaudado = df_filtered['total'].sum()
            total_facturas = len(df_filtered)
            promedio = total_recaudado / total_facturas if total_facturas > 0 else 0
            total_gastos = sum(g.get("monto", 0) for g in gastos_filtered)
            
            st.markdown(f"### 🎯 Resumen Financiero - {mes_sel}")
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
                st.markdown("### 📊 Comparativa Financiera por Mes")
                
                tabla_comp = []
                for m in sorted(meses_sel):
                    df_m = df_comp[df_comp['mes_anio'] == m]
                    ventas_m = df_m['total'].sum()
                    fact_m = len(df_m)
                    gastos_m = sum(g.get("monto", 0) for g in gastos_db if _fecha_gasto_seguro(g.get('fecha_gasto')) == m)
                    ganancia_m = ventas_m - gastos_m
                    tabla_comp.append({"Mes": m, "Ventas Brutas": ventas_m, "Gastos": gastos_m, "Ganancia Neta": ganancia_m, "N° Facturas": fact_m})
                
                df_tabla_comp = pd.DataFrame(tabla_comp)
                st.dataframe(df_tabla_comp.style.format({"Ventas Brutas": lambda x: f"${format_currency_co(x)}", "Gastos": lambda x: f"${format_currency_co(x)}", "Ganancia Neta": lambda x: f"${format_currency_co(x)}"}), use_container_width=True)
                
                df_melted = df_tabla_comp.melt(id_vars=['Mes'], value_vars=['Ventas Brutas', 'Gastos', 'Ganancia Neta'], var_name='Concepto', value_name='Valor')
                chart = alt.Chart(df_melted).mark_bar(width=20).encode(
                    x=alt.X('Mes:N', title='Mes', axis=alt.Axis(labelAngle=0)),
                    y=alt.Y('Valor:Q', title='Valor ($)'),
                    color=alt.Color('Concepto:N', scale=alt.Scale(domain=['Ventas Brutas', 'Gastos', 'Ganancia Neta'], range=['#2196F3', '#ff9800', '#00A650']), title='Concepto'),
                    xOffset='Concepto:N'
                ).properties(height=320)
                
                st.altair_chart(chart, use_container_width=True)
            else:
                st.warning("Selecciona al menos un mes para la comparativa.")
        else:
            total_recaudado = df_dash['total'].sum()
            total_facturas = len(df_dash)
            promedio = total_recaudado / total_facturas if total_facturas > 0 else 0
            total_gastos = sum(g.get("monto", 0) for g in gastos_db)
            
            st.markdown("### 🎯 Resumen Financiero Histórico Global")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("💰 Ventas Brutas", f"${format_currency_co(total_recaudado)}")
            m2.metric("💸 Gastos Operativos", f"${format_currency_co(total_gastos)}", delta="- Salidas", delta_color="inverse")
            m3.metric("📈 Ganancia Neta", f"${format_currency_co(total_recaudado - total_gastos)}")
            m4.metric("📊 Ticket Promedio", f"${format_currency_co(promedio)}")
            
            st.info(f"📌 **Dinero de saldos por cobrar:** ${format_currency_co(total_cartera_pendiente)}")
            
            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**📅 Tendencia de Ventas (Últimos 12 meses)**")
                # Se usa la fecha REAL de hoy como referencia, no el máximo
                # de fecha_venta -- si algún dato tuviera una fecha corrupta
                # a futuro, .max() desplazaría todo el gráfico hacia
                # adelante (esto causó exactamente el bug reportado).
                fecha_limite_tendencia = hoy_an - pd.DateOffset(months=11)
                df_tendencia = df_dash[
                    (df_dash['fecha_venta'] >= fecha_limite_tendencia) &
                    (df_dash['fecha_venta'] <= hoy_an)
                ]
                chart_tendencia = alt.Chart(df_tendencia.groupby('mes_anio')['total'].sum().reset_index()).mark_bar(width=25).encode(
                    x=alt.X('mes_anio:N', title='Mes', sort=None),
                    y=alt.Y('total:Q', title='Total ($)')
                ).properties(height=280)
                st.altair_chart(chart_tendencia, use_container_width=True)
                
                st.markdown("**💳 Uso de Métodos de Pago**")
                if 'metodo_pago' in df_dash.columns:
                    chart_pagos = alt.Chart(df_dash['metodo_pago'].value_counts().reset_index()).mark_bar(width=25).encode(
                        x=alt.X('metodo_pago:N', title='Método'),
                        y=alt.Y('count:Q', title='Cantidad')
                    ).properties(height=280)
                    st.altair_chart(chart_pagos, use_container_width=True)
                    
            with c2:
                st.markdown("**🏭 Ranking de Laboratorios (Asignaciones)**")
                if 'laboratorio' in df_dash.columns:
                    labs_count = df_dash['laboratorio'].fillna('NO ASIGNADO').value_counts().reset_index()
                    chart_labs = alt.Chart(labs_count).mark_bar(width=25).encode(
                        x=alt.X('laboratorio:N', title='Laboratorio'),
                        y=alt.Y('count:Q', title='Trabajos')
                    ).properties(height=280)
                    st.altair_chart(chart_labs, use_container_width=True)
                else:
                    st.info("Aún no has asignado facturas a laboratorios externos.")
                    
                st.markdown("**🔥 Top 5 de Ventas Más Altas**")
                top_ventas = df_dash[['numero_factura', 'titular_nombre', 'total', 'fecha_venta']].sort_values(by='total', ascending=False).head(5)
                top_ventas['fecha_venta'] = top_ventas['fecha_venta'].dt.strftime('%d/%m/%Y')
                st.dataframe(top_ventas.style.format({"total": lambda x: f"${format_currency_co(x)}"}), use_container_width=True)

        st.divider()
        st.markdown("### 💾 Respaldo Total de Base de Datos (Master Backup)")
        st.caption("Descarga un archivo Excel con todas las tablas críticas del sistema para tu respaldo local.")
        if st.button("📥 Generar Respaldo Completo en Excel", type="primary"):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                p_data = traer_todas_las_filas("pacientes")
                if p_data: pd.DataFrame(p_data).to_excel(writer, index=False, sheet_name="Pacientes")
                
                h_data = traer_todas_las_filas("historias_clinicas")
                if h_data: pd.DataFrame(h_data).to_excel(writer, index=False, sheet_name="HistoriasClinicas")
                
                v_data = traer_todas_las_filas("ventas_facturacion")
                if v_data: pd.DataFrame(v_data).to_excel(writer, index=False, sheet_name="VentasFacturacion")
                
                i_data = traer_todas_las_filas("inventario")
                if i_data: pd.DataFrame(i_data).to_excel(writer, index=False, sheet_name="Inventario")
                
                g_data = traer_todas_las_filas("gastos_caja")
                if g_data: pd.DataFrame(g_data).to_excel(writer, index=False, sheet_name="GastosCaja")
            
            excel_bytes = output.getvalue()
            st.download_button(
                label="📥 Descargar Master Backup (.xlsx)",
                data=excel_bytes,
                file_name=f"MasterBackup_BoomerangVision_{now_co().strftime('%d-%m-%Y')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.info("No hay suficientes registros en la base de datos.")
