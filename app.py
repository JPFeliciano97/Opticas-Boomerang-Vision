import streamlit as st
import streamlit.components.v1 as components
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


def hora_co(fecha_iso_str, formato="%H:%M"):
    """
    Extrae la hora de un timestamp ISO guardado en la BD, garantizando
    que se muestre en hora Colombia sin importar en qué zona horaria
    la haya devuelto Postgres/PostgREST. Postgres normaliza las
    columnas timestamptz a UTC al leerlas de vuelta -- tomar el string
    crudo con [11:16] asumiendo que sigue en hora Colombia mostraba la
    hora equivocada (esto causó el reporte de gastos "guardados 4
    horas tarde"). Nunca lanza excepción: ante formato irreconocible
    devuelve "--:--".
    """
    if not fecha_iso_str:
        return "--:--"
    try:
        dt = datetime.fromisoformat(str(fecha_iso_str).replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone(timedelta(hours=-5)))
        return dt.strftime(formato)
    except (ValueError, TypeError):
        return "--:--"

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
        /* El selector universal apagaba también el texto de las alertas de
           stock (sin stock / stock bajo), que es justo lo que debe saltar a
           la vista. Se excluyen las alertas para que conserven su color. */
        [data-testid="stSidebar"] *:not([data-testid="stAlertContainer"]):not([data-testid="stAlertContainer"] *) {
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
            background-color: #d35f5f !important;
            color: #ffffff !important;
        }
        /* La etiqueta visible del botón es un <p> hijo, y la regla global
           "p, label {color:#000}" le gana por apuntar directo al elemento.
           Sin estos dos selectores el texto blanco del botón primario nunca
           llega a verse: se renderiza negro sobre rojo. */
        .stButton > button[kind="primary"] p,
        .stButton > button[kind="primary"] div,
        .stButton > button[kind="primary"] label,
        /* En el sidebar hace falta repetir el selector con el prefijo del
           propio sidebar: la regla que pinta todo de negro allí lleva dos
           :not() y por eso gana en especificidad a la versión corta. */
        [data-testid="stSidebar"] .stButton > button[kind="primary"] p,
        [data-testid="stSidebar"] .stButton > button[kind="primary"] div,
        [data-testid="stSidebar"] .stButton > button[kind="primary"] label {
            color: #ffffff !important;
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
           El recuadro visible NO es .stAlert (ese es un envoltorio exterior)
           sino [data-testid="stAlertContainer"], al que Streamlit ya aplica
           el tinte semántico. Pintar .stAlert de gris solo ensuciaba el fondo
           por detrás de un tinte translúcido, y forzar el texto a negro
           borraba la señal de color. Aquí se conserva el tinte y se refuerza
           con un borde lateral, para que el tipo de mensaje se lea de reojo. */
        [data-testid="stAlertContainer"] {
            border-radius: 6px !important;
        }
        [data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) {
            border-left: 4px solid #22c55e !important;
        }
        [data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]),
        [data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) p,
        [data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) span {
            color: #166534 !important;
        }
        [data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {
            border-left: 4px solid #ef4444 !important;
        }
        [data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]),
        [data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) p,
        [data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) span {
            color: #991b1b !important;
        }
        [data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {
            border-left: 4px solid #eab308 !important;
        }
        [data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]),
        [data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) p,
        [data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) span {
            color: #854d0e !important;
        }
        [data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) {
            border-left: 4px solid #0ea5e9 !important;
        }
        [data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]),
        [data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) p,
        [data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) span {
            color: #075985 !important;
        }
        /* El código en línea (`texto`) dentro de una alerta hereda el color
           semántico y quedaría ilegible sobre su propio fondo: lo fijamos. */
        [data-testid="stAlertContainer"] code {
            color: #111111 !important;
            background-color: rgba(255,255,255,0.72) !important;
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

        /* --- 12. Contenedores con borde (st.container(border=True)) ---
           OJO con el nombre del testid: hasta ~1.4x el contenedor con borde
           era [data-testid="stVerticalBlockBorderWrapper"]; en Streamlit
           reciente (verificado en 1.61) ese testid ya no existe y el borde
           lo dibuja el stVerticalBlock que cuelga de un stLayoutWrapper.
           Se cubren ambos para no depender de la versión que instale el
           servidor -- requirements.txt solo fija "streamlit>=1.40".
           El hijo directo se usa a propósito: el wrapper de st.columns
           contiene un stHorizontalBlock, así que las columnas no coinciden
           con este selector y no se les pinta borde por error. */
        [data-testid="stVerticalBlockBorderWrapper"],
        [data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"] {
            border: 1px solid #d0d0d0 !important;
            border-radius: 10px !important;
            padding-bottom: 6px !important;
        }

        /* --- 12b. Selectbox dentro de tarjetas ---
           Antes existía aquí un bloque que coloreaba las tarjetas de
           laboratorio según [data-estado]. Ese atributo lo escribía un
           <script> incrustado con st.markdown, y Streamlit inyecta ese HTML
           vía innerHTML: por especificación, los <script> insertados así
           NO se ejecutan, así que el atributo nunca existía y el bloque
           entero era código muerto. Ahora el color del estado se dibuja
           como una franja HTML dentro de la tarjeta (módulo 5), que sí se
           renderiza siempre.
           Estas reglas de selectbox estaban duplicadas una vez por cada
           trabajo listado; aquí se declaran una sola vez. */
        [data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stSelectbox"],
        [data-testid="stLayoutWrapper"] div[data-testid="stSelectbox"] {
            background-color: transparent !important;
            border: none !important;
        }
        [data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stSelectbox"] > div:last-child,
        [data-testid="stLayoutWrapper"] div[data-testid="stSelectbox"] > div:last-child {
            background-color: #f2f2f2 !important;
            border: 1.5px solid #b0b0b0 !important;
            border-radius: 6px !important;
        }
        [data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stSelectbox"] [data-baseweb="select"],
        [data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stSelectbox"] [data-baseweb="select"] > div,
        [data-testid="stLayoutWrapper"] div[data-testid="stSelectbox"] [data-baseweb="select"],
        [data-testid="stLayoutWrapper"] div[data-testid="stSelectbox"] [data-baseweb="select"] > div {
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
        }

        /* --- 13. Spinner / Progress --- */
        .stProgress > div > div {
            background-color: #e57373 !important;
        }

        /* --- 14. Foco visible por teclado ---
           Varias reglas de arriba ponen outline:none para limpiar el borde
           de los inputs; sin esto, navegar con Tab no deja rastro visible. */
        button:focus-visible,
        [role="tab"]:focus-visible,
        summary:focus-visible,
        a:focus-visible {
            outline: 2px solid #c62828 !important;
            outline-offset: 2px !important;
        }

        /* --- 15. Hover de tarjetas: indica que la fila es manipulable --- */
        [data-testid="stVerticalBlockBorderWrapper"],
        [data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"] {
            transition: box-shadow 0.18s ease, border-color 0.18s ease !important;
        }
        [data-testid="stVerticalBlockBorderWrapper"]:hover,
        [data-testid="stLayoutWrapper"] > [data-testid="stVerticalBlock"]:hover {
            box-shadow: 0 2px 10px rgba(0,0,0,0.08) !important;
            border-color: #b8b8b8 !important;
        }

        /* --- 16. Métricas: cifras largas de moneda en 4 columnas --- */
        [data-testid="stMetricValue"] {
            font-size: 1.55rem !important;
            font-variant-numeric: tabular-nums !important;
        }

        /* --- 17. Accesibilidad: respetar reduced-motion --- */
        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after {
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
            }
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

# NOTA: aquí vivía un "parche JS global" (styleSelects + MutationObserver)
# que pretendía reforzar el borde de los selectbox tras cada re-render.
# Nunca se ejecutó: Streamlit inyecta el HTML de unsafe_allow_html mediante
# innerHTML, y por especificación del estándar HTML los <script> insertados
# de esa forma NO corren. El HTML y el <style> hermanos sí se renderizan,
# lo que hacía que el fallo pasara desapercibido al leer el código.
# El CSS equivalente (sección 4c/4d del bloque de estilos) sí funciona y es
# quien realmente da el borde a los selectbox.

@st.cache_data(ttl=300, show_spinner=False)
def columna_existe(tabla, columna):
    """¿La tabla tiene esa columna? Permite que el código funcione tanto
    antes como después de correr la migración, sin romperse si todavía
    no se ha añadido la columna en Supabase."""
    try:
        supabase.table(tabla).select(columna).limit(1).execute()
        return True
    except Exception:
        return False


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
# Métodos de pago que un cliente puede usar para pagar (venta o recaudo de
# saldo). ADDI y CODENSA son plataformas de crédito/compra-ahora-paga-después;
# junto con BOLD (pasarela de tarjeta), son los que cobran una comisión al
# negocio -- por eso son los que activan el campo de "% de recargo".
METODOS_PAGO_VENTA = ["EFECTIVO", "BOLD", "ADDI", "CODENSA", "LLAVE", "NEQUI", "DAVIPLATA"]
METODOS_PAGO_CON_RECARGO = {"BOLD", "ADDI", "CODENSA"}
# Métodos de pago para gastos del negocio (no aplican ADDI/CODENSA, que son
# líneas de crédito para clientes, no formas en que el negocio paga lo suyo).
METODOS_PAGO_GASTO = ["EFECTIVO", "BOLD", "NEQUI", "DAVIPLATA"]

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
    """Deja solo los dígitos. Sirve para teléfonos y documentos.
    NO usar para dinero: descarta el separador decimal, de modo que
    "5.500,00" se convierte en 550000. Para importes usar parse_money_co."""
    val = str(val_str).strip()
    if not val: return ""
    return "".join(c for c in val if c.isdigit())


def parse_money_co(val_str):
    """
    Interpreta un importe en pesos tal y como lo escribe una persona.

    El problema que resuelve: antes los montos se leían con
    clean_numeric_string, que borra TODO lo que no sea dígito. Así,
    escribir "5.500,00" guardaba 550.000 y "2.100.000,00" guardaba
    210 millones -- el importe quedaba multiplicado por 10 elevado al
    número de decimales, en silencio y sin ningún aviso.

    Regla: si tras el último separador quedan 1 o 2 dígitos, ese
    separador es el decimal y esa parte se descarta (el peso colombiano
    no maneja centavos en caja). Cualquier otro punto o coma es
    separador de miles. Acepta símbolos y texto alrededor.
    """
    if val_str is None:
        return 0
    if isinstance(val_str, (int, float)):
        return int(val_str)
    txt = str(val_str).strip()
    if not txt:
        return 0
    negativo = txt.startswith("-")
    limpio = re.sub(r"[^0-9.,]", "", txt)
    if not limpio:
        return 0
    ultimo = max(limpio.rfind("."), limpio.rfind(","))
    if ultimo != -1 and len(limpio) - ultimo - 1 in (1, 2):
        limpio = limpio[:ultimo]          # descarta la parte decimal
    digitos = re.sub(r"[^0-9]", "", limpio)
    if not digitos:
        return 0
    valor = int(digitos)
    return -valor if negativo else valor


def formatear_campo_money(val_str):
    """Normaliza lo que hay en un campo de dinero: interpreta y reescribe.
    Al salir del campo, "5.500,00" se muestra ya como "5.500", de modo
    que la persona ve el importe que realmente se va a guardar."""
    return format_currency_co(parse_money_co(val_str))

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
    gastos nuevos y migrados) a 'YYYY-MM' EN HORA COLOMBIA. Postgres
    normaliza timestamptz a UTC al devolverlo -- sin esta conversión,
    un gasto registrado de noche cerca de fin de mes podía agruparse
    en el mes siguiente por error. Nunca lanza excepción: devuelve
    None ante un valor vacío o corrupto en vez de tumbar Analítica.
    """
    if not fecha_str:
        return None
    try:
        dt = datetime.fromisoformat(str(fecha_str).replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone(timedelta(hours=-5)))
        return dt.strftime('%Y-%m')
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


def _sanitizar_para_filtro_postgrest(texto):
    """
    Quita caracteres que PostgREST interpreta como separadores especiales
    dentro del mini-lenguaje de .or_() (coma, paréntesis) antes de
    interpolar texto de búsqueda del usuario en un filtro. Sin esto, un
    nombre con coma o paréntesis podía romper el parseo del filtro
    completo (la búsqueda fallaba silenciosamente, capturada solo por
    el try/except general).
    """
    return re.sub(r"[,()]", " ", str(texto or "")).strip()


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
    q_upper = _sanitizar_para_filtro_postgrest(normalizar_texto_busqueda(query_texto))
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


# Paleta semántica de la app. Antes estos valores estaban escritos a mano
# en cada punto de uso, lo que ya había producido tres verdes distintos
# (#4CAF50, #00A650, #2E7D32) y tres ámbares para el mismo significado.
COLOR_MARCA  = "#e57373"   # rojo suave de marca
COLOR_EXITO  = "#4CAF50"   # verde "correcto / entregado"
COLOR_ALERTA = "#ff9800"   # ámbar "en proceso / atención"
COLOR_INFO   = "#2196F3"   # azul "informativo / recibido"
COLOR_URGENTE = "#E61B23"  # rojo "pendiente / urgente"

# Categorías de gasto. Salieron de agrupar los conceptos realmente
# escritos en los tres primeros meses de uso: laboratorio, nómina y
# arriendo concentran el 95% del dinero, así que ocho etiquetas bastan.
# 'tipo_gasto' (DIARIO/MENSUAL) responde a CUÁNDO golpea la caja y es
# un eje distinto: un pago a Falcon puede ser diario o mensual sin
# dejar de ser laboratorio.
CATEGORIAS_GASTO = [
    "LABORATORIO Y PROVEEDORES",
    "NOMINA",
    "ARRIENDO Y ADMINISTRACION",
    "SERVICIOS PUBLICOS",
    "HONORARIOS POR CONSULTA",
    "HONORARIOS POR TURNO",
    "TRANSPORTE",
    "ALIMENTACION",
    "ASEO E INSUMOS",
    "DEVOLUCIONES A CLIENTES",
    "OTROS",
]
CATEGORIA_POR_DEFECTO = "SIN CLASIFICAR"

# Por encima de este monto se pide confirmación explícita. El gasto
# legítimo más alto registrado es el arriendo ($2.100.000), así que el
# umbral deja pasar la operación normal y solo frena lo excepcional --
# que es justo donde aparecían importes como un sándwich de $5.500.000.
UMBRAL_GASTO_ALTO = 2_500_000


def format_currency_co(val):
    """
    Formatea un número como moneda colombiana: separador de miles con
    punto, consistente en cualquier magnitud (nunca apóstrofe -- el
    código anterior alternaba entre punto y apóstrofe cada 6 dígitos,
    dando resultados como "1'234.567" o "1.234'567.890" para cifras
    sobre el millón, que no es el formato colombiano estándar y podía
    confundirse con notación de otros países). También preserva el
    signo negativo: antes, un valor negativo (ej. una "Ganancia Neta"
    en pérdida) se mostraba idéntico al positivo, sin ningún indicador
    de que en realidad era una pérdida.
    """
    if val is None or val == "": return ""
    if isinstance(val, (int, float)): val = int(val)
    val_str = str(val).strip()
    if val_str.endswith(".0"): val_str = val_str[:-2]
    es_negativo = val_str.strip().startswith("-")
    digits = clean_numeric_string(val_str)
    if not digits: return ""
    rev = digits[::-1]; res = ""
    for i, char in enumerate(rev):
        if i > 0 and i % 3 == 0: res += "."
        res += char
    resultado = res[::-1]
    return f"-{resultado}" if es_negativo else resultado

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


def calcular_dp_combinada(dp_od, dp_oi):
    """
    Calcula la DP total de lejos (suma de DP OD + DP OI) y la DP de
    cerca (la de lejos menos 2mm, por la convergencia natural de los
    ojos al enfocar de cerca). Devuelve 'cerca/lejos' (ej: '60/62'
    para DP OD=31, DP OI=31), o '' si los valores no son numéricos.
    """
    try:
        od = float(str(dp_od).strip())
        oi = float(str(dp_oi).strip())
        lejos = od + oi
        cerca = lejos - 2
        fmt = lambda v: f"{v:.0f}" if v == int(v) else f"{v:.1f}"
        return f"{fmt(cerca)}/{fmt(lejos)}"
    except (ValueError, TypeError):
        return ""

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
        # "NEUTRO" como primer token es el placeholder de esfera=0 (lo usa
        # build_rx_string cuando la esfera es cero pero SÍ hay cilindro/eje,
        # ej: "NEUTRO -3.75 x 160°"). Antes, intentar convertir "NEUTRO" a
        # float lanzaba una excepción que descartaba TODO el resultado
        # (incluyendo cilindro y eje, que sí eran válidos) y devolvía ceros
        # -- por eso al reabrir para editar, esos dos campos aparecían en
        # blanco aunque sí estaban guardados correctamente en la BD.
        if parts and parts[0] == "NEUTRO":
            parts[0] = "0"
        if len(parts) == 1:
            return float(parts[0]), 0.0, 0
        if len(parts) >= 3:
            return float(parts[0]), float(parts[1]), int(float(parts[2]))
    except (ValueError, IndexError):
        pass
    return 0.0, 0.0, 0


def documento_parece_valido(doc):
    """
    Un documento de identificación (cédula, TI, CE, pasaporte, NIT)
    SIEMPRE tiene al menos un dígito -- ningún tipo de documento válido
    es puro texto. Esto detecta el caso real que se encontró: un campo
    de "Documento" con un nombre completo tecleado por error
    ("JUAN DIEGO VILLAMIL"), que el sistema guardaba sin avisar.
    No exige que sea NUMÉRICO PURO porque cédulas de extranjería y
    pasaportes pueden ser alfanuméricos.
    """
    doc = str(doc or "").strip()
    return bool(doc) and any(c.isdigit() for c in doc)


def es_documento_numerico(doc):
    """
    Validación ESTRICTA (solo dígitos) para los campos de "Documento"
    en Facturación, donde casi siempre se trata de una cédula
    colombiana. Más estricta que documento_parece_valido (que permite
    alfanumérico para CE/pasaporte) -- aquí, si alguien escribe una
    letra, es casi siempre un error de captura, no un tipo de
    documento legítimo distinto.
    """
    doc = str(doc or "").strip()
    return bool(doc) and doc.isdigit()


def sello_auditoria():
    """
    Devuelve {"modificado_por": ..., "modificado_fecha": ...} con el
    usuario actualmente logueado y la hora Colombia -- para dejar
    rastro de quién hizo cada cambio sensible (anular, editar una
    venta, corregir un documento), importante en un negocio con
    varios empleados usando el mismo sistema.
    """
    usuario_actual = st.session_state.get("user_info", {}).get("nombre", "Desconocido")
    return {"modificado_por": usuario_actual, "modificado_fecha": now_co().isoformat()}


def corregir_documento_paciente(doc_viejo, doc_nuevo):
    """
    Corrige el documento de un paciente en CASCADA: actualiza la fila
    en pacientes, y todas las historias_clinicas y ventas_facturacion
    que tuvieran ese documento (no solo la factura que se esté
    editando -- si el mismo error de captura se repitió en varias
    visitas, todas quedan vinculadas al documento correcto).
    Antes de tocar nada, valida que doc_nuevo no pertenezca YA a otro
    paciente distinto (evita fusionar accidentalmente dos personas).
    Devuelve (ok: bool, mensaje: str, es_colision: bool) -- es_colision
    le indica al llamador si el fallo fue específicamente porque el
    documento nuevo ya pertenece a alguien más, para poder ofrecer la
    opción de fusionar en vez de solo mostrar el error.
    """
    doc_viejo, doc_nuevo = str(doc_viejo).strip(), str(doc_nuevo).strip()
    if doc_viejo == doc_nuevo:
        return True, "", False
    if not documento_parece_valido(doc_nuevo):
        return False, "El nuevo documento no parece válido (debe contener al menos un número).", False
    ya_existe = supabase.table("pacientes").select("documento").eq("documento", doc_nuevo).execute().data
    if ya_existe:
        return False, (f"Ya existe un paciente registrado con el documento '{doc_nuevo}'. "
                        f"Si es la misma persona duplicada, puedes fusionar los registros."), True
    try:
        sello_aud = sello_auditoria()
        supabase.table("pacientes").update({"documento": doc_nuevo, **sello_aud}).eq("documento", doc_viejo).execute()
        supabase.table("historias_clinicas").update({"paciente_documento": doc_nuevo}).eq("paciente_documento", doc_viejo).execute()
        supabase.table("ventas_facturacion").update({"paciente_documento": doc_nuevo, "titular_doc": doc_nuevo, **sello_aud}).eq("paciente_documento", doc_viejo).execute()
        return True, f"Documento corregido de '{doc_viejo}' a '{doc_nuevo}' en todos los registros vinculados.", False
    except Exception as e:
        return False, f"Error al corregir el documento: {e}", False


def fusionar_pacientes(doc_a_eliminar, doc_a_conservar):
    """
    Fusiona dos fichas de paciente que resultaron ser la MISMA persona
    duplicada (ej: una vez registrada correctamente, y otra vez con el
    bug de nombre-en-el-campo-documento). Traslada todo el historial
    clínico y todas las ventas del documento que se va a eliminar hacia
    el documento que se conserva, y borra la ficha duplicada. Esto es
    una acción explícita del operador (nunca automática) porque fusionar
    a dos personas DISTINTAS por error sería mucho peor que el problema
    que resuelve -- por eso solo se ofrece cuando el operador ya
    confirmó visualmente que el nombre/celular coinciden.
    """
    doc_a_eliminar, doc_a_conservar = str(doc_a_eliminar).strip(), str(doc_a_conservar).strip()
    try:
        sello_aud = sello_auditoria()
        supabase.table("historias_clinicas").update({"paciente_documento": doc_a_conservar}).eq("paciente_documento", doc_a_eliminar).execute()
        supabase.table("ventas_facturacion").update({"paciente_documento": doc_a_conservar, "titular_doc": doc_a_conservar, **sello_aud}).eq("paciente_documento", doc_a_eliminar).execute()
        supabase.table("pacientes").delete().eq("documento", doc_a_eliminar).execute()
        return True, f"Registros fusionados en el documento '{doc_a_conservar}'. La ficha duplicada se eliminó."
    except Exception as e:
        return False, f"Error al fusionar: {e}"

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
    pdf.cell(55, 6, f"No. {formatear_numero_factura_display(venta['numero_factura'])}", border=1, ln=1, align="C")
    
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
    dp_od_fc, dp_oi_fc = parse_dp_individual(historia.get('dp'))
    dp_calculada_fc = calcular_dp_combinada(dp_od_fc, dp_oi_fc)
    dp_texto_fc = f"DP: {dp_calculada_fc}" if dp_calculada_fc else f"DP: {historia.get('dp') or ''}"
    pdf.set_xy(10, 101)
    pdf.cell(110, 5, f"{dp_texto_fc}{add_text}{alt_text}", border="L,B,R", ln=1)
    
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
    pdf.cell(80, 18, f"{formatear_numero_factura_display(venta['numero_factura'])}", border=0, align="C")
    
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
    dp_od_ol, dp_oi_ol = parse_dp_individual(historia.get('dp'))
    dp_calculada_ol = calcular_dp_combinada(dp_od_ol, dp_oi_ol)
    dp_texto_ol = dp_calculada_ol if dp_calculada_ol else (historia.get('dp') or '')
    pdf.cell(75, 6, f"DP: {dp_texto_ol}", border=1); pdf.cell(35, 6, f"ALTURA: {alt_val}", border=1, ln=1, align="C")
    
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

    # DP total calculada (suma OD+OI para lejos, menos 2mm para cerca),
    # además de los valores individuales por ojo de la cuadrícula arriba
    # (que el laboratorio sigue necesitando para centrar cada lente).
    dp_calculada_rx = calcular_dp_combinada(dp_od, dp_oi)
    if dp_calculada_rx:
        pdf.set_x(10); pdf.set_font("helvetica", "B", 9)
        pdf.cell(175, 6, f"DP TOTAL (Cerca/Lejos): {dp_calculada_rx}", border=1, align="C", ln=1)
        pdf.set_font("helvetica", "", 9)

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
def force_negative_cyl(key):
    """
    El cilindro en optometría siempre se expresa en notación negativa
    -- si el operador digita un valor positivo por error de tecleo (o
    porque está acostumbrado a la notación positiva de otro sistema),
    se corrige automáticamente al signo negativo. Genérica por key para
    poder usarse en los distintos campos de cilindro del sistema
    (Consultorio, Nueva Venta, Editar Historia, Editar Factura), que
    tienen nombres de key distintos y a veces dinámicos.
    """
    if st.session_state.get(key, 0) > 0:
        st.session_state[key] = -abs(st.session_state[key])


def wrap_eje(key):
    """
    El eje del cilindro es un ángulo circular: 0° y 180° son el mismo
    eje físico, así que el rango útil real es 0-175° en pasos de 5°.
    Streamlit deshabilita el botón "-" nativo cuando el valor está en
    min_value -- para que ese botón permita "dar la vuelta" de 0 a 175
    (en vez de quedar inutilizable en el extremo), el widget se
    configura con un margen de un paso fuera del rango real
    (min=-5, max=180) y este callback corrige el valor "envolviéndolo"
    al otro extremo apenas se sale del rango 0-175.
    """
    v = st.session_state.get(key, 0)
    if v < 0:
        st.session_state[key] = 175
    elif v > 175:
        st.session_state[key] = 0


def normalizar_cil_eje(cilindro, eje):
    """
    Misma corrección que force_negative_cyl/wrap_eje, pero como función
    pura (sin session_state) para usar DESPUÉS de un st.form_submit_button
    -- Streamlit no permite on_change en widgets dentro de un st.form(),
    así que en "Editar Historia" y "Editar Reciente" (que sí usan forms)
    la corrección se aplica aquí, sobre el valor ya enviado, en vez de
    en vivo mientras se digita.
    """
    if cilindro > 0:
        cilindro = -abs(cilindro)
    if eje < 0:
        eje = 175
    elif eje > 175:
        eje = 0
    return cilindro, eje

def on_subtotal_change(): st.session_state.subtotal_input = formatear_campo_money(st.session_state.subtotal_input)
def on_abono_change(): st.session_state.abono_input = formatear_campo_money(st.session_state.abono_input)
def on_monto_rec_change(): st.session_state.monto_rec_input = formatear_campo_money(st.session_state.monto_rec_input)
def on_monto_gasto_change(): st.session_state.monto_gasto_input = formatear_campo_money(st.session_state.monto_gasto_input)
def on_p_compra_change(): st.session_state.p_compra_input = formatear_campo_money(st.session_state.p_compra_input)
def on_p_venta_change(): st.session_state.p_venta_input = formatear_campo_money(st.session_state.p_venta_input)
def on_p_compra_m_change(): st.session_state.p_compra_m = formatear_campo_money(st.session_state.p_compra_m)
def on_p_venta_m_change(): st.session_state.p_venta_m = formatear_campo_money(st.session_state.p_venta_m)

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
    # Sin esto la confirmación quedaría marcada para el gasto siguiente,
    # que es justo lo que la haría inútil.
    st.session_state.confirmar_gasto_alto = False
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
    st.session_state.trigger_clear_editar = False

if "trigger_clear_venta_menor" in st.session_state and st.session_state.trigger_clear_venta_menor:
    st.session_state.metodo_menor_sel = "EFECTIVO"
    st.session_state.recargo_pct_menor_input = 0.0
    st.session_state.trigger_clear_venta_menor = False

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
    # Si se estaba revisando una pendiente y se sale sin guardar, se
    # descarta ese estado -- si no, el aviso "Datos de X cargados"
    # quedaría pegado en la próxima visita a Consultorio.
    st.session_state.revisando_pendiente = None
    # Mismo problema con las selecciones de "editar algo": si quedaban
    # pegadas tras salir sin guardar, el aviso de "cambios sin guardar"
    # se disparaba de nuevo en la SIGUIENTE visita, aunque todo estuviera
    # vacío -- porque hay_cambios_sin_guardar() las detecta como
    # "hay algo en curso" sin distinguir si es una sesión nueva.
    st.session_state.editar_factura_sel = None
    st.session_state.editar_historia_sel = None
    st.session_state.expander_pendientes_abierto = False


def hay_cambios_sin_guardar():
    """
    Heurística de "¿hay algo escrito sin guardar en el módulo actual?"
    para el aviso de confirmación al salir. Revisa los campos MÁS
    representativos de cada módulo (no cada campo posible) -- suficiente
    para detectar el caso real que importa: alguien escribió información
    de un paciente/producto/venta y todavía no le dio clic a Guardar.
    """
    m = st.session_state.get("current_module", "")
    ss = st.session_state

    def _txt(k):
        return bool(str(ss.get(k) or "").strip())

    if m == "👨‍⚕️ Consultorio":
        campos_texto = ["doc_input", "nom_input", "cel_input", "dir_input",
                         "ocu_input", "mot_input", "obs_input"]
        campos_rx = ["esf_od", "cil_od", "esf_oi", "cil_oi", "add_input"]
        if any(_txt(k) for k in campos_texto):
            return True
        if any(float(ss.get(k) or 0) != 0.0 for k in campos_rx):
            return True
        # Hay una historia clínica seleccionada para editar (formulario abierto)
        if ss.get("editar_historia_sel") is not None:
            return True
        # Hay una pendiente de revisión en curso (datos ya cargados en Admisión)
        if ss.get("revisando_pendiente"):
            return True
        return False

    if m == "🛍️ Óptica y Facturación":
        # El grupo de "Nueva Venta" solo cuenta si la búsqueda de
        # paciente sigue activa (el asistente realmente está visible en
        # pantalla) -- si search_opt está vacío, cualquier valor que
        # quedara en subtotal_input/abono_input es de una búsqueda
        # anterior ya cerrada, no un cambio real pendiente ahora mismo.
        # desc_producto_input se excluye del chequeo por completo: ese
        # campo siempre trae un texto sugerido por defecto en cuanto se
        # encuentra un paciente, así que su sola presencia no dice nada
        # sobre si la persona escribió algo intencionalmente.
        if _txt("search_opt") and (_txt("subtotal_input") or _txt("abono_input")):
            return True
        if _txt("desc_menor_input"):
            return True
        # Mismo problema que desc_producto_input: monto_rec_input se
        # auto-rellena con el saldo pendiente en cuanto se busca una
        # factura en Recaudar Saldo. Si luego se borra la búsqueda sin
        # guardar, el valor autorellenado queda pegado en session_state
        # aunque el campo visible (fac_search_input) ya esté vacío.
        if _txt("fac_search_input") and _txt("monto_rec_input"):
            return True
        # Hay una factura/venta menor seleccionada para editar
        if ss.get("editar_factura_sel") is not None:
            return True
        return False

    if m == "📦 Inventario":
        campos = ["inv_codigo", "inv_marca", "inv_desc", "m_marca", "m_ref_unico"]
        if any(_txt(k) for k in campos):
            return True
        # Hay un producto cargado en Ajuste Rápido o Editar Producto
        if _txt("codigo_ajuste_input") or _txt("codigo_editar_prod_input"):
            return True
        return False

    return False


def _limpiar_campos_modulo_actual():
    """
    Limpia los campos "sucios" del módulo que se está abandonando al
    confirmar "Salir sin guardar" -- sin esto, un valor a medio escribir
    quedaba pegado en session_state, y la próxima vez que se visitara
    ese módulo, el aviso de "cambios sin guardar" saltaba de nuevo con
    la pantalla visualmente en blanco (el valor viejo seguía ahí, solo
    invisible porque el campo que lo mostraba ya no estaba en pantalla).
    """
    m = st.session_state.get("current_module", "")
    ss = st.session_state
    if m == "👨‍⚕️ Consultorio":
        for k in ["doc_input", "nom_input", "cel_input", "dir_input", "ocu_input", "mot_input", "obs_input"]:
            ss[k] = ""
        for k in ["esf_od", "cil_od", "esf_oi", "cil_oi", "add_input"]:
            ss[k] = 0.0
        ss["editar_historia_sel"] = None
    elif m == "🛍️ Óptica y Facturación":
        for k in ["subtotal_input", "abono_input", "desc_menor_input", "monto_rec_input"]:
            ss[k] = ""
        ss["editar_factura_sel"] = None
    elif m == "📦 Inventario":
        for k in ["inv_codigo", "inv_marca", "inv_desc", "m_marca", "codigo_ajuste_input", "codigo_editar_prod_input"]:
            ss[k] = ""


@st.dialog("⚠️ Cambios sin guardar")
def _confirmar_salida_sin_guardar():
    # El destino se lee de session_state (no como parámetro de función):
    # el ciclo de vida interno de st.dialog no garantiza que un closure
    # de Python se preserve de forma confiable entre los reruns que
    # ocurren mientras el modal permanece abierto.
    st.warning("Hay información escrita en esta pantalla que todavía no se ha guardado. "
               "Si sales ahora, se perderá.")
    c1, c2 = st.columns(2)
    if c1.button("🚪 Salir sin guardar", use_container_width=True):
        destino = st.session_state.get("modulo_destino_pendiente")
        _limpiar_campos_modulo_actual()
        _limpiar_busquedas_historial()
        st.session_state.current_module = destino
        st.session_state.modulo_destino_pendiente = None
        st.rerun()
    if c2.button("✏️ Seguir editando", type="primary", use_container_width=True):
        st.session_state.modulo_destino_pendiente = None
        st.rerun()


def _cambiar_modulo(nuevo_modulo):
    if nuevo_modulo != st.session_state.current_module:
        if hay_cambios_sin_guardar():
            st.session_state.modulo_destino_pendiente = nuevo_modulo
            _confirmar_salida_sin_guardar()
            return
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
        with st.expander(f"⚠️ {n_pendientes} historia(s) clínica(s) pendiente(s) por revisar",
                          expanded=st.session_state.get("expander_pendientes_abierto", False)):
            st.caption("Visitas recientes migradas del histórico que no traían fórmula registrada. "
                       "Al hacer clic en 'Revisar' se cargan los datos conocidos del paciente en la "
                       "pestaña de Admisión -- solo falta completar la fórmula y guardar; la pendiente "
                       "se marca como resuelta automáticamente.")
            for i, pend in enumerate(pendientes_revisar):
                with st.container(border=True):
                    pc1, pc2 = st.columns([4, 1])
                    nombre_p = pend.get("nombre_legado") or "(sin nombre)"
                    doc_p = pend.get("paciente_documento") or "sin documento"
                    fecha_p = (pend.get("fecha") or "")[:10]
                    pc1.markdown(f"**{nombre_p}** · Doc: `{doc_p}` · {fecha_p}")
                    pc1.caption(pend.get("motivo_consulta") or "Sin motivo registrado")
                    if pc2.button("📋 Revisar", key=f"revisar_pend_{i}", use_container_width=True):
                        # Se guarda la identidad de la pendiente ORIGINAL (no
                        # solo el documento) porque muchas de estas no traen
                        # documento vinculado -- sin esto, no habría forma de
                        # encontrar y cerrar la fila correcta después de
                        # guardar la historia nueva con un documento recién
                        # asignado.
                        st.session_state.revisando_pendiente = {
                            "documento": pend.get("paciente_documento") or "",
                            "nombre_legado": pend.get("nombre_legado") or "",
                            "fecha": pend.get("fecha"),
                        }
                        st.session_state.doc_input = pend.get("paciente_documento") or ""
                        st.session_state.nom_input = pend.get("nombre_legado") or ""
                        st.session_state.cel_input = pend.get("celular_legado") or ""
                        # Se contrae el desplegable automáticamente: sin esto,
                        # había que bajar manualmente con scroll hasta el
                        # formulario de Admisión, pasando por toda la lista
                        # de pendientes que ya no hace falta seguir viendo.
                        st.session_state.expander_pendientes_abierto = False
                        st.rerun()

        if st.session_state.get("revisando_pendiente"):
            rp = st.session_state.revisando_pendiente
            st.info(f"📋 Datos de **{rp.get('nombre_legado') or rp.get('documento')}** cargados -- "
                    f"ve a la pestaña **'📋 1. Admisión Paciente'** para completar y guardar la "
                    f"fórmula. Se marcará como revisada automáticamente al guardar.")

    tab_adm, tab_ref, tab_cierre, tab_hist, tab_editar_hist = st.tabs(["📋 1. Admisión Paciente", "👁️ 2. Refracción (Rx)", "📝 3. Diagnóstico y Cierre", "📂 4. Historial", "✏️ Editar Historia"])
    
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
            cilindro_od = c2.number_input("Cilindro OD", step=0.25, format="%.2f", key="cil_od", on_change=force_negative_cyl, args=("cil_od",))
            # Eje OD: paso 5, rango 0-175
            eje_od = c3.number_input("Eje OD", min_value=-5, max_value=180, step=5, key="eje_od", on_change=wrap_eje, args=("eje_od",))
            dp_od = c4.text_input("D.P. OD (mm)", key="dp_od_input")

            st.markdown("**Ojo Izquierdo (OI)**")
            c5, c6, c7, sp2, c8 = st.columns([2, 2, 2, 0.5, 2])
            esfera_oi = c5.number_input("Esfera OI", step=0.25, format="%.2f", key="esf_oi")
            cilindro_oi = c6.number_input("Cilindro OI", step=0.25, format="%.2f", key="cil_oi", on_change=force_negative_cyl, args=("cil_oi",))
            # Eje OI: paso 5, rango 0-175
            eje_oi = c7.number_input("Eje OI", min_value=-5, max_value=180, step=5, key="eje_oi", on_change=wrap_eje, args=("eje_oi",))
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
            elif not documento_parece_valido(documento):
                st.error(f"⚠️ '{documento}' no parece un número de documento válido (debe contener al menos un "
                         f"número). Si escribiste un nombre por error en el campo Documento, corrígelo antes de guardar.")
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

                # La fecha del Habeas Data debe ser la del consentimiento
                # ORIGINAL, no la de la visita más reciente -- si el
                # paciente ya lo había autorizado antes, se preserva esa
                # fecha real en vez de sobrescribirla cada vez que vuelve
                # (perder esa fecha sería un problema real de cumplimiento:
                # el sistema debe poder demostrar CUÁNDO se dio el
                # consentimiento, no solo que existe).
                fecha_habeas_final = now_co().isoformat()
                try:
                    pac_existente = supabase.table("pacientes").select("habeas_data,habeas_data_fecha").eq("documento", doc_up).execute().data
                    if pac_existente and pac_existente[0].get("habeas_data") and pac_existente[0].get("habeas_data_fecha"):
                        fecha_habeas_final = pac_existente[0]["habeas_data_fecha"]
                except Exception:
                    pass

                try: supabase.table("pacientes").upsert({"documento": doc_up, "nombre_completo": nom_up, "celular": cel_up, "ocupacion": str(ocupacion).upper(), "direccion": str(direccion).upper(), "edad": str(edad).upper(), "fecha_nacimiento": fecha_nacimiento.strftime("%Y-%m-%d"), "habeas_data": True, "habeas_data_fecha": fecha_habeas_final}).execute()
                except Exception: supabase.table("pacientes").upsert({"documento": doc_up, "nombre_completo": nom_up, "celular": cel_up, "ocupacion": str(ocupacion).upper(), "direccion": str(direccion).upper(), "fecha_nacimiento": fecha_nacimiento.strftime("%Y-%m-%d"), "habeas_data": True, "habeas_data_fecha": fecha_habeas_final}).execute()

                supabase.table("historias_clinicas").insert({"paciente_documento": doc_up, "motivo_consulta": str(motivo).upper(), "rx_final_od": rx_od_final, "rx_final_oi": rx_oi_final, "dp": dp_combined, "ultimo_control": str(ultimo_control).upper(), "observaciones": str(obs).upper(), "adicion": f"{adicion:+.2f}" if adicion > 0.0 else "", "fecha": now_co().isoformat()}).execute()

                # El paciente acaba de ser reatendido con una historia real:
                # se resuelven sus pendientes de revisión anteriores, si tenía.
                try:
                    supabase.table("historias_clinicas").update({"pendiente_revisar": False}) \
                        .eq("paciente_documento", doc_up).eq("pendiente_revisar", True).execute()
                except Exception:
                    pass

                # Si se llegó aquí desde el botón "Revisar" de una pendiente
                # específica, se cierra ESA fila puntual por fecha original --
                # muchas pendientes no traían documento vinculado, así que el
                # UPDATE genérico de arriba (que busca por documento) no las
                # encontraría si el documento se acaba de asignar recién ahora.
                rp_activa = st.session_state.get("revisando_pendiente")
                if rp_activa:
                    try:
                        q_cerrar = supabase.table("historias_clinicas").update({"pendiente_revisar": False})
                        if rp_activa.get("documento"):
                            q_cerrar = q_cerrar.eq("paciente_documento", rp_activa["documento"])
                        else:
                            q_cerrar = q_cerrar.eq("nombre_legado", rp_activa.get("nombre_legado", ""))
                        q_cerrar.eq("fecha", rp_activa["fecha"]).execute()
                    except Exception:
                        pass
                    st.session_state.revisando_pendiente = None
                    st.session_state.expander_pendientes_abierto = False

                st.session_state.global_toast = f"Historia de {nom_up} guardada."
                st.session_state.trigger_clear_doc = True
                st.rerun()

    with tab_hist:
        st.markdown("#### 🔍 Buscar Historial de un Paciente")
        mostrar_buscador_historial("hist_consultorio")

    with tab_editar_hist:
        st.markdown("#### ✏️ Editar Historia Clínica")
        st.caption("Sin límite de antigüedad -- busca por documento y elige cuál historia corregir.")
        doc_buscar_hist = st.text_input("Documento del paciente:", key="doc_buscar_editar_hist").strip()

        if doc_buscar_hist and not es_documento_numerico(doc_buscar_hist):
            st.error("⚠️ El documento solo debe contener números.")
        elif doc_buscar_hist:
            historias_pac = supabase.table("historias_clinicas").select("*") \
                .eq("paciente_documento", doc_buscar_hist).order("fecha", desc=True).execute().data or []

            # Se identifica por posición en la lista (ya ordenada de forma
            # determinística) en vez de una columna "id" -- no se puede
            # confirmar con certeza que esa columna exista en todas las
            # instalaciones, así que es más seguro no depender de ella.
            sel_hist_idx = st.session_state.get("editar_historia_sel")
            hist_e = historias_pac[sel_hist_idx] if sel_hist_idx is not None and sel_hist_idx < len(historias_pac) else None

            if not hist_e:
                if not historias_pac:
                    st.info("Este documento no tiene historias clínicas registradas.")
                else:
                    st.markdown(f"##### {len(historias_pac)} historia(s) encontrada(s):")
                    for idx, h in enumerate(historias_pac):
                        with st.container(border=True):
                            hc1, hc2 = st.columns([4, 1])
                            hc1.markdown(f"**{h.get('fecha','')[:10]}** -- {h.get('motivo_consulta','') or '(sin motivo registrado)'}")
                            if h.get("modificado_por"):
                                hc1.caption(f"✏️ Última edición: {h['modificado_por']} · "
                                            f"{hora_co(h.get('modificado_fecha'), '%d/%m/%Y %H:%M')}")
                            if hc2.button("✏️ Editar", key=f"sel_edit_hist_{idx}", use_container_width=True):
                                st.session_state.editar_historia_sel = idx
                                st.rerun()
            else:
                if st.button("🔙 Ver todas las historias de este paciente"):
                    st.session_state.editar_historia_sel = None
                    st.rerun()

                st.info(f"✏️ Editando historia del {hist_e.get('fecha','')[:10]}")

                with st.form("form_editar_historia"):
                    eh_motivo = st.text_input("Motivo de Consulta", value=(hist_e.get("motivo_consulta") or "")).upper()

                    heh_esf_od, heh_cil_od, heh_eje_od = rx_string_a_numeros(hist_e.get("rx_final_od"))
                    heh_esf_oi, heh_cil_oi, heh_eje_oi = rx_string_a_numeros(hist_e.get("rx_final_oi"))
                    dp_prev_h = str(hist_e.get("dp", "") or "")
                    dp_od_prev_h, dp_oi_prev_h = (dp_prev_h.split("/") + [""])[:2] if "/" in dp_prev_h else (dp_prev_h, dp_prev_h)

                    st.markdown("**OD**")
                    hh1, hh2, hh3, hh4 = st.columns(4)
                    eh_esf_od = hh1.number_input("Esfera OD", step=0.25, format="%.2f", value=heh_esf_od, key=f"eh_esf_od_{hist_e.get('id')}")
                    eh_cil_od = hh2.number_input("Cilindro OD", step=0.25, format="%.2f", value=heh_cil_od, key=f"eh_cil_od_{hist_e.get('id')}")
                    eh_eje_od = hh3.number_input("Eje OD", min_value=-5, max_value=180, step=5, value=heh_eje_od, key=f"eh_eje_od_{hist_e.get('id')}")
                    eh_dp_od = hh4.text_input("DP OD", value=dp_od_prev_h.strip()).upper()

                    st.markdown("**OI**")
                    hh5, hh6, hh7, hh8 = st.columns(4)
                    eh_esf_oi = hh5.number_input("Esfera OI", step=0.25, format="%.2f", value=heh_esf_oi, key=f"eh_esf_oi_{hist_e.get('id')}")
                    eh_cil_oi = hh6.number_input("Cilindro OI", step=0.25, format="%.2f", value=heh_cil_oi, key=f"eh_cil_oi_{hist_e.get('id')}")
                    eh_eje_oi = hh7.number_input("Eje OI", min_value=-5, max_value=180, step=5, value=heh_eje_oi, key=f"eh_eje_oi_{hist_e.get('id')}")
                    eh_dp_oi = hh8.text_input("DP OI", value=dp_oi_prev_h.strip()).upper()

                    eh_add_prev = 0.0
                    try:
                        eh_add_prev = abs(float(str(hist_e.get("adicion", "") or "0").replace("+", "")))
                    except ValueError:
                        pass
                    eh_add = st.number_input("Adición (ADD)", min_value=0.00, step=0.25, format="%.2f", value=eh_add_prev)

                    eh_ultimo_control = st.text_input("Último Control", value=(hist_e.get("ultimo_control") or "")).upper()
                    eh_obs = st.text_area("Observaciones", value=(hist_e.get("observaciones") or "")).upper()

                    guardar_hist_edit = st.form_submit_button("💾 Guardar Cambios", type="primary", use_container_width=True)

                if guardar_hist_edit:
                    eh_cil_od, eh_eje_od = normalizar_cil_eje(eh_cil_od, eh_eje_od)
                    eh_cil_oi, eh_eje_oi = normalizar_cil_eje(eh_cil_oi, eh_eje_oi)
                    supabase.table("historias_clinicas").update({
                        "motivo_consulta": eh_motivo,
                        "rx_final_od": build_rx_string(eh_esf_od, eh_cil_od, eh_eje_od),
                        "rx_final_oi": build_rx_string(eh_esf_oi, eh_cil_oi, eh_eje_oi),
                        "dp": f"{eh_dp_od}/{eh_dp_oi}",
                        "adicion": f"{eh_add:+.2f}" if eh_add > 0.0 else "",
                        "ultimo_control": eh_ultimo_control,
                        "observaciones": eh_obs,
                        **sello_auditoria(),
                    }).eq("paciente_documento", doc_buscar_hist).eq("fecha", hist_e["fecha"]).execute()
                    st.session_state.global_toast = "Historia clínica actualizada."
                    st.session_state.editar_historia_sel = None
                    st.rerun()

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
                uc1.success(f"✅ Venta registrada — Factura #{formatear_numero_factura_display(ultima['numero_factura'])}")
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
        if search_doc and not es_documento_numerico(search_doc):
            st.error("⚠️ El documento solo debe contener números. Ingresa un número de documento válido.")
        elif search_doc:
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
                        if not documento_parece_valido(search_doc):
                            st.error(f"⚠️ '{search_doc}' no parece un documento válido -- revisa lo que "
                                     f"buscaste arriba antes de continuar.")
                        else:
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
                            st.markdown(f"- **OD:** {format_rx_ui(h.get('rx_final_od', 'N/A'))} | **OI:** {format_rx_ui(h.get('rx_final_oi', 'N/A'))}{add_display} | **DP:** {h.get('dp') or 'N/A'}")
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
                    # se calcula el máximo numérico en Python. Se pagina
                    # completo (no solo los primeros 1000) para que el número
                    # sugerido siga siendo correcto cuando el negocio acumule
                    # más de 1000 facturas reales.
                    candidatos_num = traer_todas_las_filas(
                        "ventas_facturacion",
                        filtros_fn=lambda q: q.not_.like("numero_factura", "LEG-%"),
                        columnas="numero_factura",
                    )
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
                    cil_od_ext = ext2.number_input("Cilindro OD", step=0.25, format="%.2f", key="cil_od_ext", on_change=force_negative_cyl, args=("cil_od_ext",))
                    eje_od_ext = ext3.number_input("Eje OD", min_value=-5, max_value=180, step=5, key="eje_od_ext", on_change=wrap_eje, args=("eje_od_ext",))
                    av_od_ext = ext4.text_input("AV OD", key="av_od_ext").upper()
                    dp_od_ext = ext5.text_input("DP OD (mm)", key="dp_od_ext").upper()

                    st.markdown("**Ojo Izquierdo (OI)**")
                    ext6, ext7, ext8, ext9, ext10 = st.columns(5)
                    esf_oi_ext = ext6.number_input("Esfera OI", step=0.25, format="%.2f", key="esf_oi_ext")
                    cil_oi_ext = ext7.number_input("Cilindro OI", step=0.25, format="%.2f", key="cil_oi_ext", on_change=force_negative_cyl, args=("cil_oi_ext",))
                    eje_oi_ext = ext8.number_input("Eje OI", min_value=-5, max_value=180, step=5, key="eje_oi_ext", on_change=wrap_eje, args=("eje_oi_ext",))
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
                
                desc_producto = st.text_input("Descripción final:", value=desc_sug, key="desc_producto_input").upper()
                
                c1, c2, c3 = st.columns(3)
                c1.text_input("Valor Subtotal ($)", key="subtotal_input", on_change=on_subtotal_change)
                c2.selectbox("Tipo Dcto", ["Sin Descuento", "Porcentaje (%)", "Valor Fijo ($)"], key="tipo_descuento_widget", on_change=on_tipo_descuento_change)
                c3.text_input("Dcto Aplicado", key="descuento_input", on_change=on_descuento_change)
                
                sub_val = parse_money_co(st.session_state.subtotal_input)
                abono_val = parse_money_co(st.session_state.abono_input)
                desc_val = parse_money_co(st.session_state.descuento_input)
                desc_calc = int((desc_val/100.0)*sub_val) if st.session_state.get("tipo_descuento_widget") == "Porcentaje (%)" else desc_val
                tot_neto = sub_val - desc_calc
                sal_pend = tot_neto - abono_val

                c4, c5, c6 = st.columns(3)
                c4.text_input("Abono Inicial ($)", key="abono_input", on_change=on_abono_change)
                metodo_pago = c5.selectbox("Método de Pago", METODOS_PAGO_VENTA)

                recargo_pct = 0.0
                recargo_valor = 0
                if metodo_pago in METODOS_PAGO_CON_RECARGO:
                    recargo_pct = c6.number_input(
                        f"% Recargo ({metodo_pago})", min_value=0.0, max_value=100.0,
                        step=0.5, format="%.2f", key="recargo_pct_input",
                        help="Comisión que cobra la plataforma por pagos a crédito/tarjeta. "
                             "Se calcula sobre el abono de hoy, no sobre el total de la factura."
                    )
                    recargo_valor = int(round(abono_val * (recargo_pct / 100.0)))
                    if recargo_valor > 0:
                        c6.caption(f"Comisión: ${format_currency_co(recargo_valor)} · "
                                   f"neto: ${format_currency_co(abono_val - recargo_valor)}")

                st.markdown(f"""
                    <div style="background-color: #f0f0f0; border: 1px solid #b0b0b0; padding: 9px; border-radius: 6px; text-align: center; margin-top: 10px;">
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
                    elif desc_calc > sub_val:
                        st.warning("⚠️ El descuento no puede ser mayor que el subtotal.")
                    elif abono_val > tot_neto:
                        st.warning(f"⚠️ El abono (${format_currency_co(abono_val)}) no puede ser mayor que el total "
                                   f"a pagar (${format_currency_co(tot_neto)}). Revisa los valores.")
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
                                "montura_codigo": selected_frame_code if (origen_montura == "Montura de Vitrina" and selected_frame_code) else None,
                                "recargo_pct": recargo_pct if recargo_pct > 0 else None,
                                "recargo_valor": recargo_valor,
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
                desc_menor = st.text_input("Descripción del artículo", placeholder="Ej: Cordón, Líquido limpiador", key="desc_menor_input").upper()
            with fm2:
                cantidad_menor = st.number_input("Cantidad", min_value=1, value=1, step=1)
            with fm3:
                valor_unit_menor = st.number_input("Valor unitario ($)", min_value=0, step=1000, value=0)
            guardar_menor = st.form_submit_button("💾 Registrar Venta", type="primary", use_container_width=True)

        # El método de pago vive FUERA del form: dentro de un st.form, los
        # widgets no reaccionan hasta el submit, así que el campo de %
        # recargo no podría aparecer/desaparecer según lo que se elija aquí.
        metodo_menor = st.selectbox("Método de Pago", METODOS_PAGO_VENTA, key="metodo_menor_sel")
        recargo_pct_menor = 0.0
        if metodo_menor in METODOS_PAGO_CON_RECARGO:
            recargo_pct_menor = st.number_input(
                f"% Recargo ({metodo_menor})", min_value=0.0, max_value=100.0,
                step=0.5, format="%.2f", key="recargo_pct_menor_input"
            )

        if guardar_menor:
            if not desc_menor or valor_unit_menor <= 0:
                st.warning("⚠️ Ingresa una descripción y un valor válidos.")
            else:
                total_menor = int(valor_unit_menor) * int(cantidad_menor)
                recargo_valor_menor = int(round(total_menor * (recargo_pct_menor / 100.0)))
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
                    "recargo_pct": recargo_pct_menor if recargo_pct_menor > 0 else None,
                    "recargo_valor": recargo_valor_menor,
                }).execute()
                st.session_state.global_toast = f"Venta menor registrada: {desc_final} — ${format_currency_co(total_menor)}"
                st.session_state.trigger_clear_venta_menor = True
                st.rerun()

        st.divider()
        st.markdown("#### 🧾 Ventas menores de hoy")
        hoy_str = now_co().strftime("%Y-%m-%d")
        ventas_menores_hoy = supabase.table("ventas_facturacion").select("*") \
            .like("numero_factura", "MEN-%") \
            .gte("fecha_venta", f"{hoy_str}T00:00:00-05:00").lte("fecha_venta", f"{hoy_str}T23:59:59-05:00") \
            .order("fecha_venta", desc=True).execute().data or []

        if ventas_menores_hoy:
            total_dia_menor = sum(v.get("total", 0) for v in ventas_menores_hoy)
            st.caption(f"**{len(ventas_menores_hoy)}** venta(s) menor(es) hoy · Total: **${format_currency_co(total_dia_menor)}**")
            for vm in ventas_menores_hoy:
                hora = hora_co(vm.get("fecha_venta"))
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
                    monto_rec = parse_money_co(st.text_input("Monto a Abonar/Liquidar ($)", key="monto_rec_input", on_change=on_monto_rec_change))
                with col_rec2:
                    metodo_rec = st.selectbox("Método del Cobro", METODOS_PAGO_VENTA, key="met_rec")
                with col_rec3:
                    estados_posibles = ["Pendiente de enviar", "En Laboratorio", "Recibido en Óptica", "Entregado"]
                    nuevo_est_recaudo = st.selectbox("Nuevo Estado de la Factura", estados_posibles, index=3)

                recargo_pct_rec = 0.0
                recargo_valor_rec = 0
                if metodo_rec in METODOS_PAGO_CON_RECARGO:
                    col_rg1, col_rg2 = st.columns(2)
                    recargo_pct_rec = col_rg1.number_input(
                        f"% Recargo ({metodo_rec})", min_value=0.0, max_value=100.0,
                        step=0.5, format="%.2f", key="recargo_pct_rec_input"
                    )
                    recargo_valor_rec = int(round(monto_rec * (recargo_pct_rec / 100.0)))
                    if recargo_valor_rec > 0:
                        col_rg2.caption(f"Comisión: ${format_currency_co(recargo_valor_rec)} · "
                                        f"neto: ${format_currency_co(monto_rec - recargo_valor_rec)}")

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
                            "estado_lab": nuevo_est_recaudo,
                            **sello_auditoria(),
                        }).eq("numero_factura", fac_pen["numero_factura"]).execute()
                        
                        supabase.table("pagos_saldos").insert({
                            "numero_factura": fac_pen['numero_factura'], 
                            "paciente_documento": fac_pen['paciente_documento'], 
                            "monto_pagado": monto_rec, 
                            "metodo_pago": metodo_rec, 
                            "recargo_pct": recargo_pct_rec if recargo_pct_rec > 0 else None,
                            "recargo_valor": recargo_valor_rec,
                            "fecha_pago": now_co().isoformat(),
                            "recibido_por": st.session_state.get("user_info", {}).get("nombre", "Desconocido"),
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
                            # saldo=0 al anular (por robustez: una factura anulada
                            # nunca debe poder aparecer como "pendiente de cobro"
                            # en ningún reporte, incluso si alguno olvidara filtrar
                            # por estado). abono se preserva como registro
                            # histórico de lo que sí se alcanzó a pagar.
                            supabase.table("ventas_facturacion").update({"estado": "ANULADA", "saldo": 0, **sello_auditoria()}).eq("numero_factura", fac_a["numero_factura"]).execute()
                            # Si la factura tenía una montura de vitrina, se
                            # restaura el stock descontado en la venta -- si no,
                            # el inventario del sistema queda desincronizado de
                            # la realidad física (la montura nunca salió de la
                            # tienda, pero el sistema la seguía contando como
                            # vendida).
                            montura_venta = fac_a.get("montura_codigo")
                            if montura_venta:
                                try:
                                    frame_data = supabase.table("inventario").select("cantidad").eq("codigo", montura_venta).execute().data
                                    if frame_data:
                                        supabase.table("inventario").update({"cantidad": frame_data[0]["cantidad"] + 1}).eq("codigo", montura_venta).execute()
                                    case_data = supabase.table("inventario").select("cantidad").eq("codigo", "ESTUCHE-GENERICO").execute().data
                                    if case_data:
                                        supabase.table("inventario").update({"cantidad": case_data[0]["cantidad"] + 1}).eq("codigo", "ESTUCHE-GENERICO").execute()
                                    st.session_state.global_toast = f"Factura ANULADA. Stock de la montura {montura_venta} restaurado."
                                except Exception:
                                    st.session_state.global_toast = "Factura ANULADA. No se pudo restaurar el stock automáticamente -- revísalo manualmente."
                                    st.session_state.global_toast_icon = "⚠️"
                            else:
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
        st.caption("Se pueden editar las **últimas 10 facturas normales** y las **últimas 10 ventas "
                   "menores** (no legado, no anuladas), por separado. Para facturas más antiguas, usa "
                   "Anular y crea una nueva si hace falta corregir algo, para no alterar el historial "
                   "financiero ya cerrado.")

        # Categorías separadas: las ventas menores usan un identificador tipo
        # timestamp (p.ej. "MEN-20260805175510638939") que, como número, es
        # miles de millones de veces más grande que cualquier factura real
        # -- mezclarlas en una sola lista de "últimas 10" hacía que las
        # ventas menores desplazaran por completo a las facturas normales
        # en cuanto hubiera alguna reciente.
        categoria_editar = st.radio(
            "¿Qué quieres editar?", ["🧾 Facturas Normales", "🧦 Ventas Menores"],
            horizontal=True, key="categoria_editar_reciente",
        )
        es_categoria_menor = categoria_editar == "🧦 Ventas Menores"

        todas_actual = traer_todas_las_filas(
            "ventas_facturacion",
            filtros_fn=lambda q: q.neq("estado", "ANULADA").eq("origen", "ACTUAL"),
        )
        if es_categoria_menor:
            candidatas = [v for v in todas_actual if str(v.get("numero_factura", "")).startswith("MEN-")]
            candidatas.sort(key=lambda v: v.get("fecha_venta") or "", reverse=True)
        else:
            candidatas = [v for v in todas_actual if not str(v.get("numero_factura", "")).startswith("MEN-")]
            candidatas.sort(key=lambda v: valor_numerico_factura(v.get("numero_factura")), reverse=True)
        ultimas_10 = candidatas[:10]

        sel_key = st.session_state.get("editar_factura_sel")
        venta_e = next((v for v in ultimas_10 if v["numero_factura"] == sel_key), None) if sel_key else None

        if not venta_e:
            if not ultimas_10:
                st.info(f"Todavía no hay {'ventas menores' if es_categoria_menor else 'facturas normales'} recientes para editar.")
            else:
                st.markdown(f"##### Elige una de las últimas {len(ultimas_10)}:")
                for v in ultimas_10:
                    with st.container(border=True):
                        vc1, vc2 = st.columns([4, 1])
                        if es_categoria_menor:
                            vc1.markdown(f"**{v.get('descripcion','')}** -- ${format_currency_co(v.get('total', 0))} "
                                         f"· {hora_co(v.get('fecha_venta'), '%d/%m/%Y %H:%M')}")
                        else:
                            vc1.markdown(f"**Fac N° {formatear_numero_factura_display(v['numero_factura'])}** -- "
                                         f"{v.get('titular_nombre','')} -- ${format_currency_co(v.get('total', 0))}")
                        if v.get("modificado_por"):
                            vc1.caption(f"✏️ Última edición: {v['modificado_por']} · "
                                        f"{hora_co(v.get('modificado_fecha'), '%d/%m/%Y %H:%M')}")
                        if vc2.button("✏️ Editar", key=f"sel_editar_{v['numero_factura']}", use_container_width=True):
                            st.session_state.editar_factura_sel = v["numero_factura"]
                            st.rerun()
        else:
            if st.button("🔙 Ver la lista"):
                st.session_state.editar_factura_sel = None
                st.rerun()

            if es_categoria_menor:
                # Formulario simplificado: una venta menor no tiene fórmula
                # ni paciente vinculado, mostrar todo eso sería ruido inútil.
                st.info(f"✏️ Editando venta menor: **{venta_e.get('descripcion','')}**")
                with st.form("form_editar_venta_menor"):
                    fm1, fm2 = st.columns(2)
                    em_desc = fm1.text_input("Descripción", value=(venta_e.get("descripcion") or "")).upper()
                    em_metodo = fm2.selectbox("Método de Pago", METODOS_PAGO_VENTA,
                                               index=METODOS_PAGO_VENTA.index(venta_e.get("metodo_pago", "EFECTIVO")) if venta_e.get("metodo_pago") in METODOS_PAGO_VENTA else 0)
                    em_total = st.number_input("Valor total ($)", min_value=0, step=1000, value=int(venta_e.get("total") or 0))
                    guardar_menor_edit = st.form_submit_button("💾 Guardar Cambios", type="primary", use_container_width=True)

                if guardar_menor_edit:
                    supabase.table("ventas_facturacion").update({
                        "descripcion": em_desc, "metodo_pago": em_metodo,
                        "total": int(em_total), "subtotal": int(em_total),
                        "abono": int(em_total), "saldo": 0,
                        **sello_auditoria(),
                    }).eq("numero_factura", venta_e["numero_factura"]).execute()
                    st.session_state.global_toast = f"Venta menor actualizada: {em_desc}"
                    st.session_state.editar_factura_sel = None
                    st.session_state.trigger_clear_editar = True
                    st.rerun()

            else:
                st.info(f"✏️ Editando Factura N° **{formatear_numero_factura_display(venta_e['numero_factura'])}**")

                with st.form("form_editar_factura"):
                    st.markdown("##### Datos generales")
                    fe1, fe2 = st.columns(2)
                    e_desc = fe1.text_input("Descripción", value=(venta_e.get("descripcion") or "")).upper()
                    e_metodo = fe2.selectbox("Método de Pago", METODOS_PAGO_VENTA,
                                              index=METODOS_PAGO_VENTA.index(venta_e.get("metodo_pago", "EFECTIVO")) if venta_e.get("metodo_pago") in METODOS_PAGO_VENTA else 0)

                    fe3, fe4, fe5 = st.columns(3)
                    e_total = fe3.number_input("Total ($)", min_value=0, step=1000, value=int(venta_e.get("total") or 0))
                    e_abono = fe4.number_input("Abono ($)", min_value=0, step=1000, value=int(venta_e.get("abono") or 0))
                    e_saldo_calc = max(0, e_total - e_abono)
                    fe5.metric("Saldo (calculado)", f"${format_currency_co(e_saldo_calc)}")

                    e_entrega = st.text_input("Fecha/Hora Entrega", value=(venta_e.get("fecha_entrega") or "")).upper()

                    st.markdown("##### Fórmula (Rx)")
                    esf_od_prev, cil_od_prev, eje_od_prev = rx_string_a_numeros(venta_e.get("rx_final_od"))
                    esf_oi_prev, cil_oi_prev, eje_oi_prev = rx_string_a_numeros(venta_e.get("rx_final_oi"))
                    dp_prev = str(venta_e.get("dp", "") or "")
                    dp_od_prev, dp_oi_prev = (dp_prev.split("/") + [""])[:2] if "/" in dp_prev else (dp_prev, dp_prev)

                    st.markdown("**OD**")
                    eo1, eo2, eo3, eo4, eo5 = st.columns(5)
                    e_esf_od = eo1.number_input("Esfera OD", step=0.25, format="%.2f", value=esf_od_prev, key=f"e_esf_od_{venta_e['numero_factura']}")
                    e_cil_od = eo2.number_input("Cilindro OD", step=0.25, format="%.2f", value=cil_od_prev, key=f"e_cil_od_{venta_e['numero_factura']}")
                    e_eje_od = eo3.number_input("Eje OD", min_value=-5, max_value=180, step=5, value=eje_od_prev, key=f"e_eje_od_{venta_e['numero_factura']}")
                    e_av_od = eo4.text_input("AV OD", value=(venta_e.get("av_od") or "")).upper()
                    e_dp_od = eo5.text_input("DP OD", value=dp_od_prev.strip()).upper()

                    st.markdown("**OI**")
                    ei1, ei2, ei3, ei4, ei5 = st.columns(5)
                    e_esf_oi = ei1.number_input("Esfera OI", step=0.25, format="%.2f", value=esf_oi_prev, key=f"e_esf_oi_{venta_e['numero_factura']}")
                    e_cil_oi = ei2.number_input("Cilindro OI", step=0.25, format="%.2f", value=cil_oi_prev, key=f"e_cil_oi_{venta_e['numero_factura']}")
                    e_eje_oi = ei3.number_input("Eje OI", min_value=-5, max_value=180, step=5, value=eje_oi_prev, key=f"e_eje_oi_{venta_e['numero_factura']}")
                    e_av_oi = ei4.text_input("AV OI", value=(venta_e.get("av_oi") or "")).upper()
                    e_dp_oi = ei5.text_input("DP OI", value=dp_oi_prev.strip()).upper()

                    add_prev = 0.0
                    try:
                        add_prev = abs(float(str(venta_e.get("adicion", "") or "0").replace("+", "")))
                    except ValueError:
                        pass
                    e_add = st.number_input("Adición (ADD)", min_value=0.00, step=0.25, format="%.2f", value=add_prev)

                    st.markdown("##### 📋 Datos del paciente")
                    st.caption("Corrige aquí si algo quedó mal capturado -- por ejemplo, si por error se "
                               "escribió un nombre en el campo de documento.")
                    pe1, pe2 = st.columns(2)
                    e_pac_nombre = pe1.text_input("Nombre del titular", value=(venta_e.get("titular_nombre") or "")).upper()
                    e_pac_doc = pe2.text_input("Documento del titular", value=(venta_e.get("titular_doc") or "")).upper()
                    e_pac_tel = st.text_input("Celular del titular", value=(venta_e.get("titular_tel") or "")).upper()

                    guardar_edicion = st.form_submit_button("💾 Guardar Cambios", type="primary", use_container_width=True)

                if guardar_edicion:
                    if e_abono > e_total:
                        st.error(f"⚠️ El abono (${format_currency_co(int(e_abono))}) no puede ser mayor que el "
                                 f"total (${format_currency_co(int(e_total))}). Corrige los valores y guarda de nuevo.")
                    elif e_pac_doc and not es_documento_numerico(e_pac_doc):
                        st.error(f"⚠️ El documento solo debe contener números. '{e_pac_doc}' no es válido.")
                    else:
                        e_cil_od, e_eje_od = normalizar_cil_eje(e_cil_od, e_eje_od)
                        e_cil_oi, e_eje_oi = normalizar_cil_eje(e_cil_oi, e_eje_oi)
                        doc_original = venta_e.get("paciente_documento") or venta_e.get("titular_doc") or ""
                        ok_doc, msg_doc = True, ""
                        if doc_original and e_pac_doc and doc_original != e_pac_doc:
                            ok_doc, msg_doc, _ = corregir_documento_paciente(doc_original, e_pac_doc)

                        if not ok_doc:
                            st.error(f"⚠️ {msg_doc}")
                        else:
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
                                "titular_nombre": e_pac_nombre, "titular_doc": e_pac_doc, "titular_tel": e_pac_tel,
                                "paciente_documento": e_pac_doc if e_pac_doc else venta_e.get("paciente_documento"),
                                **sello_auditoria(),
                            }).eq("numero_factura", venta_e["numero_factura"]).execute()
                            # Se intenta vincular/actualizar la ficha del paciente
                            # correspondiente al documento FINAL (sea el original sin
                            # cambios, o uno recién asignado a una venta que antes no
                            # tenía documento) -- .update().eq() simplemente no hace
                            # nada si ese documento no corresponde a ningún paciente
                            # existente, así que es seguro intentarlo siempre. Antes
                            # esto solo se intentaba si la venta YA tenía un documento
                            # (dejaba sin actualizar al paciente cuando se le agregaba
                            # el documento por primera vez a una venta walk-in).
                            doc_final = e_pac_doc or doc_original
                            if doc_final:
                                try:
                                    supabase.table("pacientes").update({
                                        "nombre_completo": e_pac_nombre, "celular": e_pac_tel,
                                    }).eq("documento", doc_final).execute()
                                except Exception:
                                    pass
                            st.session_state.global_toast = (
                                f"Factura #{formatear_numero_factura_display(venta_e['numero_factura'])} actualizada."
                                + (f" {msg_doc}" if msg_doc else "")
                            )
                            st.session_state.editar_factura_sel = None
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

    # ---------------------------------------------------------------
    # BASE INICIAL EN GAVETA — se registra UNA SOLA VEZ al día
    # ---------------------------------------------------------------
    # El registro vive en la tabla 'configuracion', que es global al
    # negocio y no por usuario: por eso, una vez que alguien confirma la
    # base del día, ningún otro usuario que abra sesión después vuelve a
    # verla pedida, y nadie puede modificarla hasta el día siguiente.
    # Junto con el valor se guarda la HORA exacta y QUIÉN la registró.
    #
    # La lectura se hace en cada ejecución y NO se cachea en session_state:
    # cachearla haría que (a) una sesión abierta desde ayer siguiera
    # creyendo que la base de hoy ya está confirmada al pasar la medianoche,
    # y (b) un usuario con la sesión abierta no viera la base que acaba de
    # registrar un compañero desde otro equipo.
    hoy_str_caja = now_co().strftime("%Y-%m-%d")
    CLAVES_BASE = ("base_caja_inicial", "base_caja_confirmada_fecha",
                   "base_caja_confirmada_hora", "base_caja_confirmada_por")

    def _leer_config_base():
        """Devuelve {clave: valor} de las claves de base de caja. Ante fallo
        de red devuelve None, para poder distinguir 'no hay registro' de
        'no se pudo consultar' y no bloquear el módulo por un error de red."""
        try:
            filas = supabase.table("configuracion").select("clave,valor").in_(
                "clave", list(CLAVES_BASE)).execute().data or []
            return {f["clave"]: f["valor"] for f in filas}
        except Exception:
            return None

    cfg_base = _leer_config_base()
    lectura_fallida = cfg_base is None
    cfg_base = cfg_base or {}

    try:
        base_guardada = int(cfg_base.get("base_caja_inicial") or 50000)
    except (TypeError, ValueError):
        base_guardada = 50000

    base_confirmada_hoy = cfg_base.get("base_caja_confirmada_fecha") == hoy_str_caja
    # Si la consulta falló, se respeta lo que ya se había confirmado en esta
    # sesión para no volver a pedir la base por un corte momentáneo de red.
    if lectura_fallida and st.session_state.get("base_confirmada_sesion") == hoy_str_caja:
        base_confirmada_hoy = True

    if not base_confirmada_hoy:
        st.warning("🔒 Antes de continuar, confirma la **Base Inicial en Gaveta** de hoy.")
        st.caption("Se registra una sola vez al día. Queda guardada la hora y el "
                   "usuario que la ingresó, y no vuelve a pedirse aunque entre otra persona.")
        base_dia_nueva = st.number_input(
            "Base Inicial en Gaveta ($)", min_value=0,
            value=base_guardada, step=10000, key="base_caja_dia_input",
        )
        if st.button("✅ Confirmar y Continuar", type="primary", use_container_width=True):
            momento = now_co()
            try:
                supabase.table("configuracion").upsert([
                    {"clave": "base_caja_inicial",           "valor": str(int(base_dia_nueva))},
                    {"clave": "base_caja_confirmada_fecha",  "valor": hoy_str_caja},
                    {"clave": "base_caja_confirmada_hora",   "valor": momento.isoformat()},
                    {"clave": "base_caja_confirmada_por",    "valor": st.session_state.get("user_info", {}).get("nombre", "Desconocido")},
                ]).execute()
                st.session_state.base_confirmada_sesion = hoy_str_caja
                st.session_state.global_toast = (
                    f"Base inicial registrada: ${format_currency_co(int(base_dia_nueva))} "
                    f"a las {momento.strftime('%H:%M')}"
                )
                st.rerun()
            except Exception:
                st.error("No se pudo guardar la base inicial. Revisa la conexión "
                         "e inténtalo de nuevo; el cuadre no se abre sin este registro.")
        st.stop()

    # Ya confirmada: el valor queda BLOQUEADO hasta mañana. Se muestra como
    # dato de solo lectura -- antes era un number_input que reescribía la
    # base en cada cambio, lo que permitía alterarla a media jornada y
    # descuadraba el cierre respecto a lo que realmente había en la gaveta.
    base_caja_inicial = base_guardada
    hora_base = hora_co(cfg_base.get("base_caja_confirmada_hora"))
    quien_base = cfg_base.get("base_caja_confirmada_por") or "—"

    col_fc1, col_fc2 = st.columns([2, 1])
    with col_fc1:
        fecha_consulta = st.date_input("Selecciona la fecha a consultar:", now_co().date(), format="DD/MM/YYYY")
    with col_fc2:
        st.markdown(
            '<div style="font-size:14px; font-weight:500; color:#000; margin-bottom:4px;">'
            'Base Inicial en Gaveta ($)</div>'
            '<div style="background-color:#f2f2f2; border:1.5px solid #b0b0b0; border-radius:6px;'
            ' padding:8px 12px; font-size:15px; display:flex; align-items:center;'
            ' justify-content:space-between; gap:8px;">'
            f'<span style="font-weight:700;">${format_currency_co(base_caja_inicial)}</span>'
            '<span style="font-size:0.78em; color:#555;">🔒 bloqueada</span>'
            '</div>',
            unsafe_allow_html=True
        )
        st.caption(f"Registrada hoy a las **{hora_base}** por **{quien_base}**.")

    fecha_str = fecha_consulta.strftime("%Y-%m-%d")
    
    tab_resumen, tab_gastos, tab_gastos_mensuales = st.tabs(
        ["💰 Resumen y Movimientos", "💸 Registrar Gasto de Caja", "📅 Gastos Mensuales"]
    )

    ventas = supabase.table("ventas_facturacion").select("*").gte("fecha_venta", f"{fecha_str}T00:00:00-05:00").lte("fecha_venta", f"{fecha_str}T23:59:59-05:00").neq("estado", "ANULADA").execute().data or []
    recaudos = supabase.table("pagos_saldos").select("*").gte("fecha_pago", f"{fecha_str}T00:00:00-05:00").lte("fecha_pago", f"{fecha_str}T23:59:59-05:00").execute().data or []
    gastos_todos_dia = supabase.table("gastos_caja").select("*").gte("fecha_gasto", f"{fecha_str}T00:00:00-05:00").lte("fecha_gasto", f"{fecha_str}T23:59:59-05:00").execute().data or []
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
        
        # La hora de apertura ya no se inventa: es la que quedó registrada al
        # confirmar la base del día. Al consultar una fecha pasada no hay
        # registro de aquella jornada, así que se marca con "--:--".
        hora_apertura = hora_base if fecha_consulta == now_co().date() else "--:--"
        movimientos = [{"Hora": hora_apertura, "Tipo": "BASE", "Detalle": "Apertura de Caja Inicial", "Monto": base_caja_inicial, "Método": "EFECTIVO"}]
        for v in ventas:
            if v.get('abono', 0) > 0:
                # Las ventas menores (cordones, líquidos, etc.) no tienen un
                # titular real -- mostrar la descripción del producto es más
                # útil que "Fac #MEN-... - VENTA MENOR".
                es_venta_menor = str(v.get('numero_factura', '')).startswith('MEN-')
                detalle_venta = v.get('descripcion', '') if es_venta_menor else f"Fac #{formatear_numero_factura_display(v['numero_factura'])} - {v['titular_nombre']}"
                movimientos.append({"Hora": hora_co(v['fecha_venta']), "Tipo": "VENTA", "Detalle": detalle_venta, "Monto": v['abono'], "Método": v['metodo_pago']})
        for r in recaudos:
            movimientos.append({"Hora": hora_co(r['fecha_pago']), "Tipo": "RECAUDO", "Detalle": f"Saldo Fac #{formatear_numero_factura_display(r['numero_factura'])}", "Monto": r['monto_pagado'], "Método": r['metodo_pago']})
        for g in gastos:
            movimientos.append({"Hora": hora_co(g['fecha_gasto']), "Tipo": "GASTO", "Detalle": str(g['descripcion']).upper(), "Monto": -g['monto'], "Método": g['metodo_pago']})
        
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
        hay_categoria = columna_existe("gastos_caja", "categoria_gasto")

        col_g1, col_g2, col_g3 = st.columns([2, 1, 1])
        with col_g1: desc_gasto = st.text_input("Concepto / Descripción del Gasto", placeholder="Ej: Pago mensajería laboratorio", key="desc_gasto_input").upper()
        with col_g2: monto_gasto = parse_money_co(st.text_input("Valor ($)", key="monto_gasto_input", on_change=on_monto_gasto_change))
        with col_g3: metodo_gasto = st.selectbox("Forma de Salida", METODOS_PAGO_GASTO, key="metodo_gasto_input")

        if hay_categoria:
            categoria_gasto = st.selectbox(
                "Categoría del gasto", CATEGORIAS_GASTO, key="categoria_gasto_input",
                help="Qué CLASE de gasto es. Es independiente de si es diario o mensual: "
                     "un pago al laboratorio puede ser cualquiera de los dos.\n\n"
                     "· NOMINA: personal de planta (asesores).\n"
                     "· HONORARIOS POR CONSULTA: la optómetra, que cobra por paciente atendido.\n"
                     "· HONORARIOS POR TURNO: el doctor que cubre un día completo.",
            )
        else:
            categoria_gasto = None
            st.caption("ℹ️ Para clasificar por categoría (nómina, laboratorio, arriendo…) "
                       "falta añadir la columna `categoria_gasto` en Supabase.")

        # Eco del importe interpretado: la persona ve exactamente lo que se
        # va a guardar ANTES de guardarlo. Es la defensa más simple contra
        # un cero de más, que en un campo de texto pasa desapercibido.
        if monto_gasto > 0:
            if monto_gasto >= UMBRAL_GASTO_ALTO:
                st.warning(f"🔎 Vas a registrar **${format_currency_co(monto_gasto)}**. "
                           f"Es un importe alto: confirma que está bien escrito.")
                confirmado = st.checkbox(
                    f"Sí, el gasto es de ${format_currency_co(monto_gasto)}",
                    key="confirmar_gasto_alto")
            else:
                st.caption(f"Se guardará: **${format_currency_co(monto_gasto)}**")
                confirmado = True
        else:
            confirmado = True

        if st.button("💾 Guardar Gasto de Caja", type="primary"):
            if not desc_gasto or monto_gasto <= 0:
                st.warning("⚠️ Ingresa una descripción y valor válidos.")
            elif not confirmado:
                st.error(f"Marca la casilla de confirmación para registrar "
                         f"${format_currency_co(monto_gasto)}.")
            else:
                fila_gasto = {
                    "descripcion": desc_gasto, "monto": monto_gasto, "metodo_pago": metodo_gasto,
                    "fecha_gasto": now_co().isoformat(),
                    "tipo_gasto": "MENSUAL" if es_mensual else "DIARIO",
                }
                if hay_categoria:
                    fila_gasto["categoria_gasto"] = categoria_gasto
                supabase.table("gastos_caja").insert(fila_gasto).execute()
                st.session_state.global_toast = "Gasto registrado correctamente."
                st.session_state.trigger_clear_gastos = True
                st.rerun()

        st.divider()
        st.markdown("#### 🔄 Reclasificar Gastos Recientes")
        st.caption("¿Registraste un gasto con el tipo o la categoría equivocados? "
                   "Cámbialo aquí sin necesidad de borrarlo y volver a crearlo.")
        dias_reclasificar = st.slider("Ver gastos de los últimos N días:", 1, 30, 7, key="dias_reclasificar")
        limite_reclasificar = (now_co() - timedelta(days=dias_reclasificar)).isoformat()
        gastos_recientes = supabase.table("gastos_caja").select("*") \
            .gte("fecha_gasto", limite_reclasificar).order("fecha_gasto", desc=True).execute().data or []

        # La actualización se hace por id_gasto, la clave real de la fila.
        # Antes se identificaba por la terna fecha+descripción+monto: dos
        # gastos idénticos el mismo día -- por ejemplo dos "ROSA NOMINA" de
        # $40.000, que ocurren de verdad -- se modificaban AMBOS a la vez.
        def _actualizar_gasto(gasto, cambios):
            id_g = gasto.get("id_gasto")
            q = supabase.table("gastos_caja").update(cambios)
            if id_g is not None:
                q = q.eq("id_gasto", id_g)
            else:
                # Respaldo para filas sin id: se conserva el criterio antiguo
                # avisando de que puede alcanzar a más de una.
                q = (q.eq("fecha_gasto", gasto["fecha_gasto"])
                      .eq("descripcion", gasto["descripcion"])
                      .eq("monto", gasto["monto"]))
            q.execute()

        if gastos_recientes:
            for idx, g in enumerate(gastos_recientes):
                tipo_actual = str(g.get("tipo_gasto") or "DIARIO").upper()
                cat_actual = str(g.get("categoria_gasto") or CATEGORIA_POR_DEFECTO)
                with st.container(border=True):
                    gc1, gc2, gc3 = st.columns([3, 1, 1])
                    fecha_g = hora_co(g.get("fecha_gasto"), "%d/%m/%Y %H:%M")
                    gc1.markdown(f"**{g.get('descripcion','')}** -- ${format_currency_co(g.get('monto',0))} "
                                 f"· {fecha_g} · {'📅 Mensual' if tipo_actual == 'MENSUAL' else '🗓️ Diario'}"
                                 + (f" · 🏷️ {cat_actual}" if hay_categoria else ""))

                    if tipo_actual == "DIARIO":
                        if gc3.button("➡️ Pasar a Mensual", key=f"a_mensual_{idx}", use_container_width=True):
                            _actualizar_gasto(g, {"tipo_gasto": "MENSUAL"})
                            st.session_state.global_toast = f"'{g.get('descripcion','')}' ahora es un gasto mensual."
                            st.rerun()
                    else:
                        if gc3.button("⬅️ Pasar a Diario", key=f"a_diario_{idx}", use_container_width=True):
                            _actualizar_gasto(g, {"tipo_gasto": "DIARIO"})
                            st.session_state.global_toast = f"'{g.get('descripcion','')}' ahora es un gasto diario."
                            st.rerun()

                    if hay_categoria:
                        opciones_cat = CATEGORIAS_GASTO + ([CATEGORIA_POR_DEFECTO]
                                                           if cat_actual not in CATEGORIAS_GASTO else [])
                        nueva_cat = gc2.selectbox(
                            "Categoría", opciones_cat,
                            index=opciones_cat.index(cat_actual) if cat_actual in opciones_cat else 0,
                            key=f"cat_gasto_{idx}", label_visibility="collapsed")
                        if nueva_cat != cat_actual:
                            if gc2.button("💾", key=f"guardar_cat_{idx}", use_container_width=True,
                                          help=f"Clasificar como {nueva_cat}"):
                                _actualizar_gasto(g, {"categoria_gasto": nueva_cat})
                                st.session_state.global_toast = f"'{g.get('descripcion','')}' → {nueva_cat}"
                                st.rerun()
        else:
            st.info(f"No hay gastos registrados en los últimos {dias_reclasificar} día(s).")

    with tab_gastos_mensuales:
        st.markdown("### 📅 Balance de Gastos Mensuales")
        st.caption("Gastos grandes recurrentes (nómina, arriendo, pagos a proveedores) que no forman "
                   "parte del cuadre de caja del día a día, comparados contra el ingreso del mes.")

        hoy_gm = now_co()
        meses_atras = st.slider("Meses hacia atrás a mostrar:", 1, 12, 6, key="meses_gastos_mensuales")
        mes_opciones = [(hoy_gm - pd.DateOffset(months=i)).strftime("%Y-%m") for i in range(meses_atras)]
        mes_sel_gm = st.selectbox("Mes a consultar:", mes_opciones, key="mes_gastos_mensuales")

        inicio_mes = f"{mes_sel_gm}-01T00:00:00-05:00"
        anio_gm, mes_num_gm = int(mes_sel_gm[:4]), int(mes_sel_gm[5:7])
        ultimo_dia = calendar.monthrange(anio_gm, mes_num_gm)[1]
        fin_mes = f"{mes_sel_gm}-{ultimo_dia:02d}T23:59:59-05:00"

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
    tab_catalogo, tab_ingreso, tab_ajuste, tab_editar_prod = st.tabs(["📋 Catálogo y Stock", "➕ Registrar Producto", "🔄 Ajuste Rápido", "✏️ Editar Producto"])
    
    with tab_catalogo:
        inventario = traer_todas_las_filas("inventario", orden_col="marca", orden_desc=False)
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
                val_compra = parse_money_co(c_pc.text_input("Precio Compra Unitario $", key="p_compra_m", on_change=on_p_compra_m_change))
                val_venta = parse_money_co(c_pv.text_input("Precio Venta Unitario $", key="p_venta_m", on_change=on_p_venta_m_change))
                
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
                    codigos_lote = [r for r, c in monturas_data]
                    codigos_repetidos = {r for r in codigos_lote if codigos_lote.count(r) > 1}
                    if not inv_marca or any(not r or not c for r, c in monturas_data):
                        st.error("⚠️ Marca, Referencia y Color son obligatorios para todas las monturas listadas.")
                    elif codigos_repetidos:
                        st.error(f"⚠️ Hay referencias repetidas en esta lista: {', '.join(codigos_repetidos)}. "
                                 f"Cada montura necesita un código único.")
                    else:
                        # Se verifica ANTES de insertar cuáles códigos ya existen
                        # en el inventario -- de lo contrario, si una montura a
                        # mitad de la lista fallaba por código duplicado, el
                        # insert se detenía ahí dejando un estado parcial (unas
                        # sí guardadas, otras no) sin explicar claramente por qué.
                        existentes = supabase.table("inventario").select("codigo").in_("codigo", codigos_lote).execute().data or []
                        codigos_existentes = {e["codigo"] for e in existentes}
                        if codigos_existentes:
                            st.error(f"⚠️ Ya existe(n) en el inventario: {', '.join(codigos_existentes)}. "
                                     f"Usa una referencia distinta o edita el producto existente.")
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
                val_compra = parse_money_co(c2.text_input("Precio Compra $", key="p_compra_input", on_change=on_p_compra_change))
                val_venta = parse_money_co(c3.text_input("Precio Venta $", key="p_venta_input", on_change=on_p_venta_change))
                    
                if st.button("💾 Guardar Producto", type="primary", use_container_width=True):
                    if not inv_codigo or not inv_marca or not inv_desc: 
                        st.error("⚠️ Código, Marca y Descripción son obligatorios.")
                    else:
                        # Se verifica ANTES de insertar si el código ya existe,
                        # para dar un mensaje claro en vez del error técnico de
                        # la base de datos ("duplicate key value...").
                        ya_existe = supabase.table("inventario").select("codigo").eq("codigo", inv_codigo).execute().data
                        if ya_existe:
                            st.error(f"⚠️ Ya existe un producto con el código '{inv_codigo}'. "
                                     f"Usa otro código, o ajusta el stock existente desde 'Ajuste Rápido'.")
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
                            supabase.table("inventario").update({"cantidad": nuevo_stock, **sello_auditoria()}).eq("codigo", codigo_ajuste).execute()
                            st.session_state.global_toast = f"Stock actualizado a {nuevo_stock}."
                            st.session_state.trigger_clear_ajuste = True
                            st.rerun()

    with tab_editar_prod:
        st.markdown("#### ✏️ Editar Producto")
        st.caption("Corrige marca, descripción, categoría, proveedor o precios de un producto ya "
                   "registrado. Para cambiar solo la cantidad en stock, usa 'Ajuste Rápido'.")
        codigo_editar_prod = st.text_input("Buscar por Código:", key="codigo_editar_prod_input").upper()

        if codigo_editar_prod:
            res_edit_prod = supabase.table("inventario").select("*").eq("codigo", codigo_editar_prod).execute().data
            if not res_edit_prod:
                st.error(f"No se encontró ningún producto con el código '{codigo_editar_prod}'.")
            else:
                prod_e = res_edit_prod[0]
                st.info(f"✏️ Editando: **{prod_e.get('marca','')} — {prod_e.get('descripcion','')}**")

                with st.form("form_editar_producto"):
                    CATEGORIAS_INV = ["Montura", "Lente de Contacto", "Accesorio", "Estuche", "Líquido", "Otro"]
                    ep1, ep2 = st.columns(2)
                    ep_marca = ep1.text_input("Marca", value=(prod_e.get("marca") or "")).upper()
                    ep_categoria = ep2.selectbox("Categoría", CATEGORIAS_INV,
                                                  index=CATEGORIAS_INV.index(prod_e.get("categoria")) if prod_e.get("categoria") in CATEGORIAS_INV else 0)
                    ep_desc = st.text_input("Descripción", value=(prod_e.get("descripcion") or "")).upper()
                    ep_prov = st.text_input("Proveedor", value=(prod_e.get("proveedor") or "")).upper()

                    ep3, ep4 = st.columns(2)
                    ep_p_compra = ep3.number_input("Precio Compra ($)", min_value=0, step=1000, value=int(prod_e.get("precio_compra") or 0))
                    ep_p_venta = ep4.number_input("Precio Venta ($)", min_value=0, step=1000, value=int(prod_e.get("precio_venta") or 0))

                    guardar_prod_edit = st.form_submit_button("💾 Guardar Cambios", type="primary", use_container_width=True)

                if guardar_prod_edit:
                    if not ep_marca or not ep_desc:
                        st.error("⚠️ Marca y Descripción son obligatorios.")
                    else:
                        supabase.table("inventario").update({
                            "marca": ep_marca, "categoria": ep_categoria, "descripcion": ep_desc,
                            "proveedor": ep_prov, "precio_compra": int(ep_p_compra), "precio_venta": int(ep_p_venta),
                            **sello_auditoria(),
                        }).eq("codigo", codigo_editar_prod).execute()
                        st.session_state.global_toast = f"Producto '{codigo_editar_prod}' actualizado."
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
        labs_db = traer_todas_las_filas("laboratorios")
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
                    border_color = COLOR_URGENTE; badge_bg = "#ffebee"; badge_fg = "#c62828"
                elif est_act == "En Laboratorio":
                    border_color = COLOR_ALERTA; badge_bg = "#fff3e0"; badge_fg = "#ef6c00"
                elif est_act == "Recibido en Óptica":
                    border_color = COLOR_INFO; badge_bg = "#e3f2fd"; badge_fg = "#1565c0"
                else:
                    border_color = COLOR_EXITO; badge_bg = "#e8f5e9"; badge_fg = "#2e7d32"

                with st.container(border=True):
                    # El color de estado se dibuja como una franja HTML dentro
                    # de la tarjeta. Antes se intentaba con un <script> que
                    # escribía data-estado en el contenedor para que lo pintara
                    # el CSS; ese script nunca se ejecutaba (innerHTML no corre
                    # <script>), así que todas las tarjetas salían grises y se
                    # perdía el semáforo del flujo de laboratorio. Una franja
                    # en HTML plano se renderiza siempre.
                    st.markdown(
                        f'<div style="height:6px; background:{border_color}; border-radius:3px;'
                        f' margin:0 0 12px 0;"></div>'
                        f'<div style="margin-bottom:10px;">'
                        f'<span style="background-color:{badge_bg}; color:{badge_fg}; padding:4px 12px;'
                        f' border-radius:20px; font-weight:700; font-size:0.8em; letter-spacing:0.6px;">'
                        f'{est_act.upper()}</span></div>',
                        unsafe_allow_html=True
                    )

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

                        orden_lab_act = t.get("numero_orden_lab") or ""
                        nuevo_orden_lab = orden_lab_act
                        if nuevo_est == "En Laboratorio":
                            nuevo_orden_lab = st.text_input(
                                "N° de Orden del Laboratorio:", value=orden_lab_act,
                                key=f"orden_lab_{fac_id}",
                                help="Referencia que asigna el laboratorio externo, para hacer seguimiento del trabajo con ellos."
                            ).strip()
                        elif orden_lab_act:
                            st.caption(f"📋 Orden Lab: `{orden_lab_act}`")

                        if nuevo_est != est_act or nuevo_lab_sel != lab_act or nuevo_orden_lab != orden_lab_act:
                            if st.button(f"💾 Guardar #{fac_id_display}", key=f"btn_est_{fac_id}", type="primary"):
                                supabase.table("ventas_facturacion").update({
                                    "estado_lab": nuevo_est,
                                    "laboratorio": nuevo_lab_sel if nuevo_lab_sel != "NO ASIGNADO" else None,
                                    "numero_orden_lab": nuevo_orden_lab or None,
                                }).eq("numero_factura", fac_id).execute()
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

        # Historial de compras por documento -- se trae UNA sola vez para
        # todos los pacientes de la lista (evita una consulta por tarjeta).
        compras_por_doc = {}
        if pacientes_para_llamar:
            docs_lista = [p["Documento"] for p in pacientes_para_llamar]
            ventas_crm = traer_todas_las_filas(
                "ventas_facturacion",
                filtros_fn=lambda q: q.in_("paciente_documento", docs_lista).neq("estado", "ANULADA"),
                columnas="paciente_documento,total",
            )
            for v in ventas_crm:
                doc_v = v.get("paciente_documento")
                if not doc_v:
                    continue
                reg = compras_por_doc.setdefault(doc_v, {"cantidad": 0, "total": 0})
                reg["cantidad"] += 1
                reg["total"] += v.get("total", 0) or 0

        if pacientes_para_llamar:
            st.info(f"Se encontraron **{len(pacientes_para_llamar)}** pacientes para control anual.")

            POR_PAGINA_ANUAL = 10
            total_anual = len(pacientes_para_llamar)
            total_pags_anual = max(1, (total_anual + POR_PAGINA_ANUAL - 1) // POR_PAGINA_ANUAL)
            if "anual_pagina" not in st.session_state: st.session_state.anual_pagina = 1
            pag_anual = min(st.session_state.anual_pagina, total_pags_anual)
            inicio_anual = (pag_anual - 1) * POR_PAGINA_ANUAL
            pagina_anual_actual = pacientes_para_llamar[inicio_anual:inicio_anual + POR_PAGINA_ANUAL]

            st.caption(f"Página **{pag_anual}** de **{total_pags_anual}**")

            for item in pagina_anual_actual:
                nombre_corto = item['Nombre'].split()[0]
                msg_final = st.session_state.tpl_anual.replace("[NOMBRE]", nombre_corto)
                compras = compras_por_doc.get(item["Documento"])
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 2])
                    etiqueta_legado = "" if item["Activo"] else "  ·  📜 solo en histórico"
                    c1.markdown(f"**👤 {str(item['Nombre']).upper()}**{etiqueta_legado}\n\nCédula: {item['Documento']} | Última visita: {item['Ultima_Consulta']}")
                    if compras:
                        c1.caption(f"🛍️ {compras['cantidad']} compra(s) -- ${format_currency_co(compras['total'])} en total")
                    else:
                        c1.caption("🛍️ Sin registro de compras en el sistema")
                    c2.markdown(f"📱 Cel: `{item['Celular'] or '—'}`")
                    if normalizar_texto_busqueda(item['Celular']) and item['Celular']:
                        c3.link_button("💬 Enviar WhatsApp", get_whatsapp_link(item['Celular'], msg_final), use_container_width=True)
                    else:
                        c3.button("💬 Enviar WhatsApp", disabled=True, use_container_width=True,
                                  key=f"wa_off_anual_{item['Documento']}", help="Sin celular registrado")

            if total_pags_anual > 1:
                nva1, nva2, nva3, nva4, nva5 = st.columns([1, 1, 2, 1, 1])
                if nva1.button("⏮ Primera", key="anual_first", disabled=(pag_anual == 1)):
                    st.session_state.anual_pagina = 1; st.rerun()
                if nva2.button("◀ Anterior", key="anual_prev", disabled=(pag_anual == 1)):
                    st.session_state.anual_pagina = pag_anual - 1; st.rerun()
                nva3.markdown(f"<div style='text-align:center; padding-top:8px;'>{pag_anual} / {total_pags_anual}</div>", unsafe_allow_html=True)
                if nva4.button("Siguiente ▶", key="anual_next", disabled=(pag_anual == total_pags_anual)):
                    st.session_state.anual_pagina = pag_anual + 1; st.rerun()
                if nva5.button("Última ⏭", key="anual_last", disabled=(pag_anual == total_pags_anual)):
                    st.session_state.anual_pagina = total_pags_anual; st.rerun()
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
        # Se detectan pacientes con documento inválido (el mismo tipo de
        # error que se encontró: un nombre tecleado por accidente en el
        # campo Documento) para poder corregirlos aquí mismo, sin depender
        # de que tengan una factura reciente para usar "Editar Reciente".
        pacientes_doc_invalido = [p for p in todos_pacientes if not documento_parece_valido(p.get("documento"))]
        if pacientes_doc_invalido:
            with st.expander(f"⚠️ {len(pacientes_doc_invalido)} paciente(s) con documento inválido -- revisar", expanded=True):
                st.caption("El campo Documento no parece un número de identificación válido "
                           "(probablemente se escribió un nombre por error). Corrígelo aquí.")
                for p in pacientes_doc_invalido:
                    with st.container(border=True):
                        st.markdown(f"**{p.get('nombre_completo','')}** -- documento actual: `{p.get('documento','')}`")
                        cc1, cc2 = st.columns([3, 1])
                        doc_nuevo_dir = cc1.text_input(
                            "Documento correcto", key=f"fix_doc_{p['documento']}"
                        ).strip().upper()
                        if cc2.button("💾 Corregir", key=f"fix_btn_{p['documento']}", use_container_width=True):
                            if not doc_nuevo_dir:
                                st.warning("⚠️ Escribe el documento correcto antes de guardar.")
                            else:
                                ok_fix, msg_fix, es_colision = corregir_documento_paciente(p["documento"], doc_nuevo_dir)
                                if ok_fix:
                                    st.session_state.global_toast = msg_fix
                                    st.session_state[f"colision_pend_{p['documento']}"] = None
                                    st.rerun()
                                elif es_colision:
                                    # El documento correcto ya existe como OTRO
                                    # registro -- probablemente es la misma
                                    # persona duplicada. Se guarda para ofrecer
                                    # fusionar en el próximo render (no se puede
                                    # mostrar el botón en esta misma pasada
                                    # porque el layout de columnas ya se cerró).
                                    st.session_state[f"colision_pend_{p['documento']}"] = doc_nuevo_dir
                                    st.rerun()
                                else:
                                    st.error(f"⚠️ {msg_fix}")

                        doc_en_colision = st.session_state.get(f"colision_pend_{p['documento']}")
                        if doc_en_colision:
                            st.warning(f"⚠️ Ya existe un paciente registrado con el documento "
                                       f"'{doc_en_colision}'. Si es la misma persona duplicada, "
                                       f"puedes fusionar los dos registros -- esto traslada todo el "
                                       f"historial y las ventas hacia ese documento, y elimina esta "
                                       f"ficha duplicada. Esta acción no se puede deshacer.")
                            if st.button("🔀 Fusionar con el registro existente",
                                         key=f"fusionar_btn_{p['documento']}"):
                                ok_merge, msg_merge = fusionar_pacientes(p["documento"], doc_en_colision)
                                st.session_state[f"colision_pend_{p['documento']}"] = None
                                if ok_merge:
                                    st.session_state.global_toast = msg_merge
                                    st.rerun()
                                else:
                                    st.error(f"⚠️ {msg_merge}")

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
            st.dataframe(
                df_dir, use_container_width=True, hide_index=True,
                column_config={
                    "documento": "Documento",
                    "nombre_completo": "Nombre completo",
                    "celular": "Celular",
                    "direccion": "Dirección",
                    "fecha_nacimiento": "Fecha de nacimiento",
                },
            )

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
    
    with st.spinner("Cargando datos de ventas..."):
        ventas_db = traer_todas_las_filas(
            "ventas_facturacion",
            filtros_fn=lambda q: q.neq("estado", "ANULADA"),
            orden_col="fecha_venta", orden_desc=True)
    hoy_an = now_co()
    mes_actual = hoy_an.strftime("%Y-%m")
    # Se compara el mes en hora Colombia real (no el string crudo que
    # devuelve Postgres, normalizado a UTC) -- una venta de las 8pm del
    # 31 de julio en Colombia podía aparecer como "agosto" al comparar
    # el string tal cual llega de la base de datos.
    ventas_mes = [v for v in ventas_db if hora_co(v.get("fecha_venta"), "%Y-%m") == mes_actual]
    total_mes = sum(int(v.get("total",0)) for v in ventas_mes)
    recaudado_mes = sum(int(v.get("abono",0)) for v in ventas_mes)
    pendiente_mes = total_mes - recaudado_mes
    
    km1, km2, km3, km4 = st.columns(4)
    km1.metric("🛍️ Ventas del mes",    f"{len(ventas_mes)}")
    km2.metric("💰 Facturado",          f"${format_currency_co(total_mes)}")
    km3.metric("✅ Recaudado",          f"${format_currency_co(recaudado_mes)}")
    km4.metric("⏳ Por recaudar",       f"${format_currency_co(pendiente_mes)}")
    st.markdown("---")
    gastos_db = traer_todas_las_filas("gastos_caja")

    # -----------------------------------------------------------------
    # FASE 1 -- clasificación sin tocar la base de datos
    # -----------------------------------------------------------------
    # El dato ya existía pero este módulo lo ignoraba: 'tipo_gasto' solo
    # se usaba en Cuadre de Caja, así que aquí el arriendo se sumaba junto
    # con la mensajería del martes y todo se rotulaba "Gastos Operativos".
    def _es_gasto_mensual(g):
        """Las filas migradas del histórico pueden no traer tipo_gasto;
        se asumen DIARIAS, que es como las trata el resto de la app."""
        return str(g.get("tipo_gasto") or "DIARIO").upper() == "MENSUAL"

    def _partir_gastos(lista):
        """Devuelve (diarios, mensuales, total) a partir de una lista de gastos."""
        diarios = sum(g.get("monto", 0) for g in lista if not _es_gasto_mensual(g))
        mensuales = sum(g.get("monto", 0) for g in lista if _es_gasto_mensual(g))
        return diarios, mensuales, diarios + mensuales

    # Las ventas menores llevan el prefijo MEN- en el número de factura.
    # Mientras no exista una columna 'tipo_venta' (fase 2), el prefijo es
    # el único discriminador disponible -- pero basta para no promediar
    # un estuche de $8.000 con unas progresivas de $900.000.
    def _es_venta_menor(num_factura):
        return str(num_factura or "").upper().startswith("MEN-")

    def _por_categoria(lista):
        """Agrupa gastos por categoría, de mayor a menor. Las filas sin
        clasificar (todo el histórico migrado) caen en su propio grupo en
        vez de desaparecer, para que el total siempre cuadre."""
        acum = {}
        for g in lista:
            cat = str(g.get("categoria_gasto") or CATEGORIA_POR_DEFECTO)
            acum[cat] = acum.get(cat, 0) + g.get("monto", 0)
        return sorted(acum.items(), key=lambda kv: -kv[1])

    def _tabla_categorias(lista, titulo):
        """Pinta el desglose por categoría si la columna existe y hay algo
        que mostrar. Separa además el costo de laboratorio del resto: es
        costo de lo vendido, no gasto de operar, y mezclarlos impide ver
        el margen."""
        if not columna_existe("gastos_caja", "categoria_gasto"):
            return
        filas = _por_categoria(lista)
        if not filas or (len(filas) == 1 and filas[0][0] == CATEGORIA_POR_DEFECTO):
            return
        total_cat = sum(v for _, v in filas)
        st.markdown(f"##### {titulo}")
        df_cat = pd.DataFrame([
            {"Categoría": c, "Monto": v, "% del gasto": f"{v / total_cat * 100:.1f}%"}
            for c, v in filas
        ])
        st.dataframe(
            df_cat.style.format({"Monto": lambda x: f"${format_currency_co(x)}"}),
            use_container_width=True, hide_index=True)

    def _money(v):
        """Formatea con el signo DELANTE del símbolo: '-$250.000' y no
        '$-250.000', que es donde queda si se antepone el '$' a secas.
        Importa en el resultado del mes, que es la cifra que puede salir
        en rojo y debe leerse como pérdida de un vistazo."""
        v = int(v or 0)
        return f"-${format_currency_co(abs(v))}" if v < 0 else f"${format_currency_co(v)}"
    
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
            df_dash['fecha_venta'], format='ISO8601', errors='coerce', utc=True)
        filas_antes = len(df_dash)
        df_dash = df_dash.dropna(subset=['fecha_venta'])
        if len(df_dash) < filas_antes:
            st.caption(f"⚠️ Se omitieron {filas_antes - len(df_dash)} registro(s) "
                       f"con fecha inválida en el análisis.")
        # Se convierte explícitamente a hora Colombia antes de extraer
        # mes/día: Postgres normaliza timestamptz a UTC al devolverlo, así
        # que sin esta conversión, ventas de la noche cerca de fin de mes
        # o fin de día podían agruparse en el mes/día siguiente por error
        # (el mismo problema que ya se corrigió en Cuadre de Caja).
        df_dash['fecha_venta'] = df_dash['fecha_venta'].dt.tz_convert(timezone(timedelta(hours=-5)))
        df_dash['mes_anio'] = df_dash['fecha_venta'].dt.strftime('%Y-%m')

        # Las filas migradas del histórico pueden no traer todas las
        # columnas. Sin esto, un solo registro antiguo sin 'abono' tumba
        # el módulo entero con un KeyError al calcular lo recaudado.
        for _col, _defecto in (("abono", 0), ("total", 0), ("saldo", 0), ("numero_factura", "")):
            if _col not in df_dash.columns:
                df_dash[_col] = _defecto
            else:
                df_dash[_col] = df_dash[_col].fillna(_defecto)

        # Fechas futuras: el histórico migrado trae facturas fechadas
        # DESPUÉS de hoy (errores de tecleo del Excel original). Antes solo
        # se excluían del selector de meses, así que seguían sumando en el
        # total global, en el ticket promedio y en la cartera. Se descartan
        # aquí, una sola vez, y así quedan fuera de todos los cálculos.
        _ahora = now_co()
        _futuras = df_dash[df_dash['fecha_venta'] > _ahora]
        if len(_futuras):
            df_dash = df_dash[df_dash['fecha_venta'] <= _ahora]
            _ejemplos = ", ".join(
                f"{r['numero_factura']} ({r['fecha_venta'].strftime('%d/%m/%Y')})"
                for _, r in _futuras.head(3).iterrows())
            st.warning(
                f"⚠️ **{len(_futuras)} factura(s) con fecha futura** quedaron fuera del análisis "
                f"por valor de ${format_currency_co(int(_futuras['total'].sum()))}. "
                f"Una venta no puede ser de un día que no ha llegado: son datos corruptos "
                f"heredados de la migración y conviene corregirlos en la base. "
                f"Ejemplos: {_ejemplos}.")
        
        total_cartera_pendiente = df_dash['saldo'].sum()
        
        modo_analitica = st.radio("Modo de Visualización:", ["Resumen Global", "Filtrar por Mes Específico", "Comparativa Multimes"], horizontal=True)
        # Salvaguarda del selector. Ya no debería hacer falta, porque las
        # filas con fecha futura se descartan más arriba, pero se mantiene
        # como segunda barrera: cuesta nada y el dato migrado ha demostrado
        # traer fechas imposibles (facturas de nov. y dic. de 2026 vistas
        # en agosto de 2026), pese a que se dieran por corregidas.
        mes_actual_str = hoy_an.strftime("%Y-%m")
        meses_disponibles = sorted(
            (m for m in df_dash['mes_anio'].unique() if m <= mes_actual_str),
            reverse=True)
        
        if modo_analitica == "Filtrar por Mes Específico":
            mes_sel = st.selectbox("Selecciona el mes a analizar:", meses_disponibles)
            df_filtered = df_dash[df_dash['mes_anio'] == mes_sel]
            gastos_filtered = [g for g in gastos_db if _fecha_gasto_seguro(g.get('fecha_gasto')) == mes_sel] if gastos_db else []
            
            # Facturado y recaudado son cosas distintas y antes se
            # mezclaban: la variable se llamaba 'total_recaudado' pero
            # sumaba 'total' (lo facturado). Restarle a eso los gastos ya
            # pagados inflaba la ganancia por toda la cartera pendiente.
            total_facturado = df_filtered['total'].sum()
            total_cobrado = df_filtered['abono'].sum()
            total_facturas = len(df_filtered)
            g_diarios, g_mensuales, total_gastos = _partir_gastos(gastos_filtered)

            st.markdown(f"### 🎯 Resumen Financiero - {mes_sel}")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("🧾 Facturado", f"${format_currency_co(total_facturado)}")
            m2.metric("✅ Recaudado", f"${format_currency_co(total_cobrado)}")
            m3.metric("💸 Gastos totales", f"${format_currency_co(total_gastos)}", delta="- Salidas", delta_color="inverse")
            m4.metric("📈 Resultado sobre lo facturado", _money(total_facturado - total_gastos))
            st.caption("**Facturado** es lo que vendiste; **Recaudado**, lo que realmente entró. "
                       "El resultado se calcula sobre lo facturado: si la cartera es alta, "
                       "el dinero disponible es menor que esa cifra.")

            g1, g2 = st.columns(2)
            g1.metric("🗓️ Gastos diarios (operativos)", f"${format_currency_co(g_diarios)}")
            g2.metric("📅 Gastos mensuales (nómina, arriendo…)", f"${format_currency_co(g_mensuales)}")

            # Ticket promedio separado: mezclarlos no informaba de nada.
            df_gafas = df_filtered[~df_filtered['numero_factura'].apply(_es_venta_menor)]
            df_menor = df_filtered[df_filtered['numero_factura'].apply(_es_venta_menor)]
            t1, t2, t3 = st.columns(3)
            t1.metric("👓 Ticket promedio gafas",
                      f"${format_currency_co(df_gafas['total'].mean() if len(df_gafas) else 0)}",
                      help=f"{len(df_gafas)} factura(s) de gafas en el mes.")
            t2.metric("🧦 Ticket promedio venta menor",
                      f"${format_currency_co(df_menor['total'].mean() if len(df_menor) else 0)}",
                      help=f"{len(df_menor)} venta(s) menor(es) en el mes.")
            t3.metric("🧮 N° de facturas", f"{total_facturas}")

            _tabla_categorias(gastos_filtered, f"🏷️ Gastos por categoría — {mes_sel}")

            # Margen bruto: solo tiene sentido si el costo de laboratorio
            # está identificado. Es la cifra que dice si los precios dan.
            _lab = sum(g.get("monto", 0) for g in gastos_filtered
                       if str(g.get("categoria_gasto") or "").startswith("LABORATORIO"))
            if _lab > 0:
                _margen = total_facturado - _lab
                mb1, mb2 = st.columns(2)
                mb1.metric("🔬 Costo de laboratorio", f"${format_currency_co(_lab)}")
                mb2.metric("📐 Margen bruto", _money(_margen),
                           help="Facturado menos el costo de laboratorio, antes de los "
                                "gastos de operar. Indica si los precios están bien puestos.")
                if total_facturado:
                    st.caption(f"Margen bruto sobre lo facturado: **{_margen / total_facturado * 100:.1f}%**")

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
                    gastos_del_mes = [g for g in gastos_db if _fecha_gasto_seguro(g.get('fecha_gasto')) == m]
                    gd_m, gm_m, gastos_m = _partir_gastos(gastos_del_mes)
                    ganancia_m = ventas_m - gastos_m
                    tabla_comp.append({
                        "Mes": m, "Facturado": ventas_m,
                        "Gastos diarios": gd_m, "Gastos mensuales": gm_m,
                        "Resultado": ganancia_m, "N° Facturas": fact_m,
                    })
                
                df_tabla_comp = pd.DataFrame(tabla_comp)
                st.dataframe(
                    df_tabla_comp.style.format({
                        "Facturado": lambda x: f"${format_currency_co(x)}",
                        "Gastos diarios": lambda x: f"${format_currency_co(x)}",
                        "Gastos mensuales": lambda x: f"${format_currency_co(x)}",
                        "Resultado": lambda x: f"${format_currency_co(x)}",
                    }),
                    use_container_width=True, hide_index=True,
                )
                
                df_melted = df_tabla_comp.melt(
                    id_vars=['Mes'],
                    value_vars=['Facturado', 'Gastos diarios', 'Gastos mensuales', 'Resultado'],
                    var_name='Concepto', value_name='Valor')
                chart = alt.Chart(df_melted).mark_bar(width=20).encode(
                    x=alt.X('Mes:N', title='Mes', axis=alt.Axis(labelAngle=0)),
                    y=alt.Y('Valor:Q', title='Valor ($)'),
                    color=alt.Color('Concepto:N', scale=alt.Scale(
                        domain=['Facturado', 'Gastos diarios', 'Gastos mensuales', 'Resultado'],
                        range=[COLOR_INFO, COLOR_ALERTA, COLOR_URGENTE, COLOR_EXITO]), title='Concepto'),
                    xOffset='Concepto:N'
                ).properties(height=320)
                
                st.altair_chart(chart, use_container_width=True)
            else:
                st.warning("Selecciona al menos un mes para la comparativa.")
        else:
            total_facturado = df_dash['total'].sum()
            total_cobrado = df_dash['abono'].sum()
            total_facturas = len(df_dash)
            g_diarios, g_mensuales, total_gastos = _partir_gastos(gastos_db)

            st.markdown("### 🎯 Resumen Financiero Histórico Global")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("🧾 Facturado", f"${format_currency_co(total_facturado)}")
            m2.metric("✅ Recaudado", f"${format_currency_co(total_cobrado)}")
            m3.metric("💸 Gastos totales", f"${format_currency_co(total_gastos)}", delta="- Salidas", delta_color="inverse")
            m4.metric("📈 Resultado sobre lo facturado", _money(total_facturado - total_gastos))

            g1, g2, g3 = st.columns(3)
            g1.metric("🗓️ Gastos diarios", f"${format_currency_co(g_diarios)}")
            g2.metric("📅 Gastos mensuales", f"${format_currency_co(g_mensuales)}")
            g3.metric("🧮 N° de facturas", f"{total_facturas}")

            _tabla_categorias(gastos_db, "🏷️ Gastos por categoría — histórico completo")
            
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
                chart_tendencia = alt.Chart(df_tendencia.groupby('mes_anio')['total'].sum().reset_index()).mark_bar(width=25, color=COLOR_MARCA).encode(
                    x=alt.X('mes_anio:N', title='Mes', sort=None),
                    y=alt.Y('total:Q', title='Total ($)')
                ).properties(height=280)
                st.altair_chart(chart_tendencia, use_container_width=True)
                
                st.markdown("**💳 Uso de Métodos de Pago**")
                if 'metodo_pago' in df_dash.columns:
                    chart_pagos = alt.Chart(df_dash['metodo_pago'].value_counts().reset_index()).mark_bar(width=25, color=COLOR_MARCA).encode(
                        x=alt.X('metodo_pago:N', title='Método'),
                        y=alt.Y('count:Q', title='Cantidad')
                    ).properties(height=280)
                    st.altair_chart(chart_pagos, use_container_width=True)
                    
            with c2:
                st.markdown("**🏭 Ranking de Laboratorios (Asignaciones)**")
                if 'laboratorio' in df_dash.columns:
                    labs_count = df_dash['laboratorio'].fillna('NO ASIGNADO').value_counts().reset_index()
                    chart_labs = alt.Chart(labs_count).mark_bar(width=25, color=COLOR_MARCA).encode(
                        x=alt.X('laboratorio:N', title='Laboratorio'),
                        y=alt.Y('count:Q', title='Trabajos')
                    ).properties(height=280)
                    st.altair_chart(chart_labs, use_container_width=True)
                else:
                    st.info("Aún no has asignado facturas a laboratorios externos.")
                    
                st.markdown("**🔥 Top 5 de Ventas Más Altas**")
                top_ventas = df_dash[['numero_factura', 'titular_nombre', 'total', 'fecha_venta']].sort_values(by='total', ascending=False).head(5)
                top_ventas['fecha_venta'] = top_ventas['fecha_venta'].dt.strftime('%d/%m/%Y')
                st.dataframe(
                    top_ventas.style.format({"total": lambda x: f"${format_currency_co(x)}"}),
                    use_container_width=True, hide_index=True,
                    column_config={
                        "numero_factura": "N° Factura",
                        "titular_nombre": "Titular",
                        "total": "Total",
                        "fecha_venta": "Fecha",
                    },
                )

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

# =====================================================================
# AVISO DE CAMBIOS SIN GUARDAR — respaldo con beforeunload del navegador
# =====================================================================
# El diálogo de confirmación (_confirmar_salida_sin_guardar) cubre la
# navegación DENTRO de la app (cambiar de módulo con el sidebar). Pero
# si la persona cierra la pestaña o recarga el navegador directamente,
# Streamlit nunca se entera de eso -- por eso también se activa el
# aviso NATIVO del navegador (beforeunload), como respaldo para ese caso.
#
# Tiene que ir por st.components.v1.html y NO por st.markdown: este último
# inyecta el HTML con innerHTML, y los <script> insertados así no se
# ejecutan nunca. components.html lo monta en un iframe con su propio
# documento, donde el script sí corre; desde ahí se alcanza la pestaña
# real con window.parent.
if st.session_state.get("user_info"):
    _hay_cambios_js = "true" if hay_cambios_sin_guardar() else "false"
    components.html(f"""
        <script>
        (function() {{
            var win = window.parent || window;
            if ({_hay_cambios_js}) {{
                win.onbeforeunload = function(e) {{
                    e.preventDefault();
                    e.returnValue = "";
                    return "";
                }};
            }} else {{
                win.onbeforeunload = null;
            }}
        }})();
        </script>
    """, height=0)
