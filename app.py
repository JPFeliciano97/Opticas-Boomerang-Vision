"""
=====================================================================
 BOOMERANG VISIÓN — ERP Óptico
 Versión 2.0  ·  Refactor UI/UX + Arquitectura
=====================================================================
Cambios estructurales frente a v1.0:
  · Tema nativo vía .streamlit/config.toml (elimina ~250 líneas de CSS)
  · Capa de datos centralizada y cacheada (db.*)
  · Navegación por st.radio (sin bucles de botones + rerun)
  · Diálogos nativos (@st.dialog) para acciones destructivas
  · st.popover para acciones secundarias
  · Corrección de N+1 queries y del bug de descarga de PDF
=====================================================================
"""

import streamlit as st
from supabase import create_client
import os
import io
import base64
import urllib.parse
import pandas as pd
import altair as alt
from dotenv import load_dotenv
from fpdf import FPDF
from datetime import datetime, timezone, timedelta
import bcrypt

# =====================================================================
# 1. CONFIGURACIÓN Y CONSTANTES
# =====================================================================
TZ_CO = timezone(timedelta(hours=-5))          # Colombia GMT-5
APP_VERSION = "2.0"
LOGO_PATH = "logo.png"

METODOS_PAGO = ["EFECTIVO", "BOLD", "LLAVE", "NEQUI", "DAVIPLATA"]
ESTADOS_LAB = ["Pendiente de enviar", "En Laboratorio", "Recibido en Óptica", "Entregado"]

# Paleta semántica por estado de trabajo (usada en Control de Trabajos)
ESTADO_THEME = {
    "Pendiente de enviar": {"color": "#E61B23", "icon": "🔴", "bg": "#FFF5F5"},
    "En Laboratorio":      {"color": "#FF9800", "icon": "🟠", "bg": "#FFFAF2"},
    "Recibido en Óptica":  {"color": "#2196F3", "icon": "🔵", "bg": "#F3F8FF"},
    "Entregado":           {"color": "#4CAF50", "icon": "🟢", "bg": "#F4FDF4"},
}


def now_co() -> datetime:
    """Fecha y hora actual en zona horaria de Colombia (GMT-5)."""
    return datetime.now(TZ_CO)


st.set_page_config(
    page_title="Boomerang Visión",
    layout="wide",
    page_icon="👓",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------
# CSS mínimo. El grueso del tema vive en .streamlit/config.toml.
# Aquí solo quedan ajustes que la API de temas no cubre.
# ---------------------------------------------------------------------
st.markdown("""
<style>
  #MainMenu, footer {visibility: hidden;}
  .block-container {padding-top: 2.2rem; padding-bottom: 3rem;}

  /* Tabs con indicador de marca */
  .stTabs [data-baseweb="tab-list"] {gap: 4px;}
  .stTabs [aria-selected="true"] {font-weight: 700;}

  /* Encabezado de módulo */
  .bv-head {
      display: flex; align-items: baseline; gap: .6rem;
      border-bottom: 2px solid #F5C2C2;
      padding-bottom: .6rem; margin-bottom: 1.4rem;
  }
  .bv-head h2 {margin: 0; font-size: 1.5rem; font-weight: 700; color: #111;}
  .bv-head span {color: #777; font-size: .88rem;}

  /* Píldora de estado */
  .bv-pill {
      display: inline-block; padding: 3px 12px; border-radius: 20px;
      font-size: .72rem; font-weight: 700; letter-spacing: .5px;
  }

  /* Barra lateral de color en tarjetas de trabajo */
  .bv-stripe {
      height: 4px; border-radius: 4px; margin-bottom: .7rem;
  }
</style>
""", unsafe_allow_html=True)


# =====================================================================
# 2. CONEXIÓN Y CAPA DE DATOS CENTRALIZADA
# =====================================================================
load_dotenv()
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except Exception:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")


@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)


supabase = init_connection()


class db:
    """
    Capa de acceso a datos.

    Todas las lecturas frecuentes están cacheadas con TTL corto. Las
    escrituras invalidan el caché con `db.invalidar()`, de modo que la
    UI siempre refleja el estado real tras un guardado.

    Motivo: en v1 cada rerun disparaba consultas idénticas repetidas
    (el inventario de la barra lateral se leía en cada interacción).
    """

    # ---------- Lecturas cacheadas ----------
    @staticmethod
    @st.cache_data(ttl=90, show_spinner=False)
    def inventario():
        return supabase.table("inventario").select("*").order("marca").execute().data or []

    @staticmethod
    @st.cache_data(ttl=90, show_spinner=False)
    def laboratorios():
        return supabase.table("laboratorios").select("*").execute().data or []

    @staticmethod
    @st.cache_data(ttl=60, show_spinner=False)
    def pacientes():
        return supabase.table("pacientes").select("*").execute().data or []

    @staticmethod
    @st.cache_data(ttl=60, show_spinner=False)
    def ventas_activas():
        return (supabase.table("ventas_facturacion").select("*")
                .neq("estado", "ANULADA")
                .order("fecha_venta", desc=True).execute().data or [])

    @staticmethod
    @st.cache_data(ttl=120, show_spinner=False)
    def gastos():
        return supabase.table("gastos_caja").select("*").execute().data or []

    @staticmethod
    @st.cache_data(ttl=120, show_spinner=False)
    def historias_resumen():
        """Solo las columnas necesarias para el CRM (evita traer texto largo)."""
        return (supabase.table("historias_clinicas")
                .select("paciente_documento,fecha").execute().data or [])

    @staticmethod
    @st.cache_data(ttl=300, show_spinner=False)
    def config_kv():
        try:
            rows = supabase.table("configuracion").select("clave,valor").execute().data or []
            return {r["clave"]: r["valor"] for r in rows}
        except Exception:
            return {}

    # ---------- Lecturas puntuales (sin caché: deben ser exactas) ----------
    @staticmethod
    def paciente_por_doc(doc: str):
        r = supabase.table("pacientes").select("*").eq("documento", doc).execute().data
        return r[0] if r else None

    @staticmethod
    def historias_de(doc: str, limite: int | None = None):
        q = (supabase.table("historias_clinicas").select("*")
             .eq("paciente_documento", doc).order("fecha", desc=True))
        if limite:
            q = q.limit(limite)
        return q.execute().data or []

    @staticmethod
    def factura(num: str):
        r = supabase.table("ventas_facturacion").select("*").eq("numero_factura", num).execute().data
        return r[0] if r else None

    @staticmethod
    def buscar_factura(criterio: str, solo_con_saldo: bool = False):
        q = (supabase.table("ventas_facturacion").select("*")
             .or_(f"numero_factura.eq.{criterio},paciente_documento.eq.{criterio}")
             .neq("estado", "ANULADA"))
        if solo_con_saldo:
            q = q.gt("saldo", 0)
        return q.order("fecha_venta", desc=True).execute().data or []

    @staticmethod
    def producto(codigo: str):
        r = supabase.table("inventario").select("*").eq("codigo", codigo).execute().data
        return r[0] if r else None

    @staticmethod
    def movimientos_dia(fecha_str: str):
        """Las tres consultas del día en un solo punto."""
        ini, fin = f"{fecha_str}T00:00:00", f"{fecha_str}T23:59:59"
        ventas = (supabase.table("ventas_facturacion").select("*")
                  .gte("fecha_venta", ini).lte("fecha_venta", fin)
                  .neq("estado", "ANULADA").execute().data or [])
        recaudos = (supabase.table("pagos_saldos").select("*")
                    .gte("fecha_pago", ini).lte("fecha_pago", fin).execute().data or [])
        gastos = (supabase.table("gastos_caja").select("*")
                  .gte("fecha_gasto", ini).lte("fecha_gasto", fin).execute().data or [])
        return ventas, recaudos, gastos

    # ---------- Escrituras ----------
    @staticmethod
    def invalidar(*fns):
        """Limpia el caché. Sin argumentos limpia todo."""
        if fns:
            for f in fns:
                try:
                    f.clear()
                except Exception:
                    pass
        else:
            st.cache_data.clear()

    @staticmethod
    def upsert_paciente(data: dict):
        supabase.table("pacientes").upsert(data).execute()
        db.invalidar(db.pacientes)

    @staticmethod
    def insert_historia(data: dict):
        supabase.table("historias_clinicas").insert(data).execute()
        db.invalidar(db.historias_resumen)

    @staticmethod
    def insert_venta(data: dict):
        supabase.table("ventas_facturacion").insert(data).execute()
        db.invalidar(db.ventas_activas)

    @staticmethod
    def update_venta(num: str, data: dict):
        supabase.table("ventas_facturacion").update(data).eq("numero_factura", num).execute()
        db.invalidar(db.ventas_activas)

    @staticmethod
    def insert_pago(data: dict):
        supabase.table("pagos_saldos").insert(data).execute()
        db.invalidar(db.ventas_activas)

    @staticmethod
    def insert_gasto(data: dict):
        supabase.table("gastos_caja").insert(data).execute()
        db.invalidar(db.gastos)

    @staticmethod
    def insert_producto(data: dict):
        supabase.table("inventario").insert(data).execute()
        db.invalidar(db.inventario)

    @staticmethod
    def update_stock(codigo: str, cantidad: int):
        supabase.table("inventario").update({"cantidad": cantidad}).eq("codigo", codigo).execute()
        db.invalidar(db.inventario)

    @staticmethod
    def descontar_stock(codigo: str, unidades: int = 1):
        p = db.producto(codigo)
        if p:
            db.update_stock(codigo, max(0, int(p.get("cantidad", 0)) - unidades))

    @staticmethod
    def insert_laboratorio(nombre: str):
        supabase.table("laboratorios").insert({"nombre": nombre}).execute()
        db.invalidar(db.laboratorios)

    @staticmethod
    def guardar_config(clave: str, valor: str) -> bool:
        try:
            supabase.table("configuracion").upsert({"clave": clave, "valor": valor}).execute()
            db.invalidar(db.config_kv)
            return True
        except Exception:
            return False


# =====================================================================
# 3. UTILIDADES DE FORMATEO
# =====================================================================
def clean_numeric_string(val_str):
    val = str(val_str).strip()
    if not val:
        return ""
    return "".join(c for c in val if c.isdigit())


def format_currency_co(val):
    if val is None or val == "":
        return ""
    if isinstance(val, (int, float)):
        val = int(val)
    val_str = str(val).strip()
    if val_str.endswith(".0"):
        val_str = val_str[:-2]
    digits = clean_numeric_string(val_str)
    if not digits:
        return ""
    rev = digits[::-1]
    res = ""
    for i, char in enumerate(rev):
        if i > 0 and i % 3 == 0:
            res += "'" if i % 6 == 0 else "."
        res += char
    return res[::-1]


def format_add(add_val):
    if not add_val:
        return ""
    val_str = str(add_val).strip().upper()
    if val_str in ["0", "0.0", "0.00", "+0.00", "-0.00", "N/A", "NEUTRO"]:
        return ""
    return val_str


def normalizar_celular(celular) -> str:
    """Devuelve el celular en 10 dígitos nacionales (sin prefijo 57)."""
    d = clean_numeric_string(celular)
    if d.startswith("57") and len(d) == 12:
        d = d[2:]
    return d


def get_whatsapp_link(celular, mensaje):
    d = normalizar_celular(celular)
    if not d or len(d) < 10:
        return "#"
    return f"https://wa.me/57{d}?text={urllib.parse.quote(mensaje)}"


def convert_df_to_excel(df, sheet_name="Reporte"):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()


def fmt_fecha(raw, con_hora=False):
    """Normaliza cualquier fecha de Supabase a DD/MM/YYYY."""
    if not raw:
        return "—"
    try:
        s = str(raw)
        if "T" in s:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            if dt.tzinfo:
                dt = dt.astimezone(TZ_CO).replace(tzinfo=None)
        else:
            dt = datetime.strptime(s[:10], "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y %H:%M" if con_hora else "%d/%m/%Y")
    except Exception:
        return str(raw)[:10]


def parse_fecha(raw):
    """Convierte una fecha de Supabase a datetime naive en hora Colombia."""
    if not raw:
        return None
    try:
        s = str(raw)
        if "T" in s:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            if dt.tzinfo:
                dt = dt.astimezone(TZ_CO)
            return dt.replace(tzinfo=None)
        return datetime.strptime(s[:10], "%Y-%m-%d")
    except Exception:
        return None


def build_rx_string(sph, cyl, axis):
    sph_str = "NEUTRO" if sph == 0.0 else f"{sph:+.2f}"
    if cyl == 0.0:
        return sph_str
    return f"{sph_str} {-abs(cyl):.2f} x {int(axis)}°"


def format_rx_ui(rx_str):
    if not rx_str or rx_str == "N/A":
        return "N/A"
    rx_str = str(rx_str).strip().upper()
    if "0.00 X 0" in rx_str or "0.0 X 0" in rx_str:
        clean = rx_str.split("0.0")[0].strip()
        if clean:
            return clean
    return rx_str


def parse_dp_individual(dp_str):
    if not dp_str or dp_str == "N/A":
        return "N/A", "N/A"
    dp_str = str(dp_str).upper()
    if "/" in dp_str:
        parts = dp_str.split("/")
        return parts[0].strip(), parts[1].strip()
    return dp_str, "N/A"


def get_cerca_rx(rx_str, adicion_val):
    if not rx_str or rx_str == "N/A":
        return "N/A"
    try:
        add_f = float(str(adicion_val).replace("+", "").strip()) if adicion_val else 0.0
        if "X" not in rx_str.upper():
            esfera = 0.0 if "NEUTRO" in rx_str.upper() else float(rx_str)
            esf_cerca = esfera + add_f
            return "NEUTRO" if esf_cerca == 0.0 else f"{esf_cerca:+.2f}"
        parts = rx_str.upper().replace("X", " ").split()
        if len(parts) >= 3:
            esfera = 0.0 if parts[0] in ["N", "NEUTRO"] else float(parts[0])
            cilindro = float(parts[1])
            eje = int(float(parts[2].replace("°", "")))
            esf_cerca = esfera + add_f
            sph_cerca_str = "NEUTRO" if esf_cerca == 0.0 else f"{esf_cerca:+.2f}"
            if cilindro == 0.0:
                return sph_cerca_str
            return f"{sph_cerca_str} {cilindro:.2f} x {eje}°"
    except Exception:
        pass
    return rx_str


def procesar_historia_factura(historia, tipo_gafas):
    h = historia.copy()
    if tipo_gafas == "Lejos":
        h["adicion"] = ""
    elif tipo_gafas == "Cerca":
        h["rx_final_od"] = get_cerca_rx(h.get("rx_final_od"), h.get("adicion"))
        h["rx_final_oi"] = get_cerca_rx(h.get("rx_final_oi"), h.get("adicion"))
        h["adicion"] = ""
    return h


def parse_for_grid(rx_str):
    if not rx_str or rx_str == "N/A":
        return "NEUTRO", "", ""
    if "X" not in rx_str.upper():
        return rx_str.upper(), "", ""
    parts = rx_str.upper().replace("X", " ").split()
    esf = "NEUTRO" if parts[0] in ["N", "NEUTRO"] else parts[0].upper()
    return esf, parts[1], parts[2].upper()


# =====================================================================
# 4. PRIMITIVAS DE INTERFAZ
# =====================================================================
def page_header(titulo: str, icono: str = "", subtitulo: str = ""):
    """Encabezado uniforme de módulo."""
    sub = f"<span>{subtitulo}</span>" if subtitulo else ""
    st.markdown(
        f'<div class="bv-head"><h2>{icono} {titulo}</h2>{sub}</div>',
        unsafe_allow_html=True,
    )


def pill(texto: str, color: str, bg: str) -> str:
    return f'<span class="bv-pill" style="background:{bg};color:{color};">{texto}</span>'


def pdf_viewer(pdf_bytes: bytes, filename: str, altura: int = 600):
    """
    Visor PDF embebido en iframe + botón de descarga.

    Los bytes se reciben ya materializados (no se generan aquí), de modo
    que el visor sobrevive a los reruns que dispara el botón de descarga.
    """
    st.download_button(
        "📥 Descargar PDF",
        data=pdf_bytes,
        file_name=filename,
        mime="application/pdf",
        use_container_width=True,
        key=f"dl_{filename}",
    )
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    st.markdown(
        f"""
        <iframe src="data:application/pdf;base64,{b64}"
                width="100%" height="{altura}px" style="border:1px solid #E0E0E0;border-radius:8px;"
                sandbox="allow-scripts allow-same-origin">
            <p>Tu navegador no puede mostrar el PDF.
            <a href="data:application/pdf;base64,{b64}" download="{filename}">Descárgalo aquí</a>.</p>
        </iframe>
        """,
        unsafe_allow_html=True,
    )


def get_image_base64(path):
    if os.path.exists(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None


def buscador(label: str, key: str, placeholder: str = "", ayuda: str = ""):
    """Campo de búsqueda uniforme, devuelve el texto en mayúsculas."""
    return st.text_input(
        label, key=key, placeholder=placeholder, help=ayuda or None
    ).strip().upper()


# =====================================================================
# 5. AUTENTICACIÓN
# =====================================================================
# Las contraseñas se almacenan como hash bcrypt.
# Para agregar o cambiar usuarios usa herramienta_contrasenas.py
USUARIOS_PERMITIDOS = {
    "1022396649": {"hash": "$2b$12$gFAaYBKx9MbY6LmB5jzlyua138yntPOt70A4vMek48tf7ar//iAVW", "nombre": "Dr. Mateo F.",     "rol": "admin",            "id": "1022396649"},
    "1024585129": {"hash": "$2b$12$B/6vCxYqn3UIhacSuTd/C.9AtZwQeHjVdLqpA8hLpc1RwhFx/A7zy", "nombre": "Dr. Juan Pablo",   "rol": "admin",            "id": "1024585129"},
    "39667008":   {"hash": "$2b$12$d20TxP8RA0VcZUIRDYS0OeZb1aj7ZJjFbFYxWYf5fq1tqDsC.t.ZG", "nombre": "Rosa (Asesora)",   "rol": "admin",            "id": "39667008"},
    "79203712":   {"hash": "$2b$12$utxfnI7yKTFK3bu/RckDiOeHLgk2wu6iGp5KUR30QYUlbuSdj2qWO", "nombre": "Nelson (Asesor)",  "rol": "admin",            "id": "79203712"},
    "asesor":     {"hash": "$2b$12$.qveRTit/Shp7AytkdWGveb6kl6fHPvJ9iMecNzFRII1kB19uMSl2", "nombre": "Asesor Invitado",  "rol": "asesor_limitado",  "id": "asesor"},
    "doctor":     {"hash": "$2b$12$v0DR0MvszR5DM2FCMotUqeHqCyc9bPqnZzs6v4.V06ibN9g2/oAvK", "nombre": "Doctor Invitado",  "rol": "doctor_limitado",  "id": "doctor"},
}

if "user_info" not in st.session_state:
    st.session_state.user_info = None

# Reanudar sesión desde token diario
if st.session_state.user_info is None and "auth_token" in st.query_params:
    try:
        decoded = base64.b64decode(st.query_params["auth_token"]).decode("utf-8")
        tok_user, tok_date = decoded.split("||")
        if tok_date == now_co().strftime("%Y-%m-%d") and tok_user in USUARIOS_PERMITIDOS:
            st.session_state.user_info = USUARIOS_PERMITIDOS[tok_user]
    except Exception:
        pass

if not st.session_state.user_info:
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col_login, _ = st.columns([1, 1.15, 1])
    with col_login:
        with st.container(border=True):
            b64_logo = get_image_base64(LOGO_PATH)
            if b64_logo:
                st.markdown(
                    f'<div style="text-align:center;padding:.5rem 0 1rem;">'
                    f'<img src="data:image/png;base64,{b64_logo}" width="78%"></div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown("<h2 style='text-align:center;'>👓 Boomerang Visión</h2>",
                            unsafe_allow_html=True)

            st.markdown(
                "<p style='text-align:center;color:#777;margin-bottom:1.2rem;'>"
                "Ingreso al Sistema Central</p>",
                unsafe_allow_html=True,
            )

            with st.form("login_form", border=False):
                user_input = st.text_input("Usuario (Documento)", autocomplete="username")
                pass_input = st.text_input("Contraseña", type="password",
                                           autocomplete="current-password")
                enviado = st.form_submit_button("🔐 Iniciar Sesión", type="primary",
                                                use_container_width=True)

            if enviado:
                u = user_input.strip().lower()
                ok = (u in USUARIOS_PERMITIDOS and
                      bcrypt.checkpw(pass_input.strip().encode(),
                                     USUARIOS_PERMITIDOS[u]["hash"].encode()))
                if ok:
                    st.session_state.user_info = USUARIOS_PERMITIDOS[u]
                    token = base64.b64encode(
                        f"{u}||{now_co().strftime('%Y-%m-%d')}".encode()
                    ).decode()
                    st.query_params["auth_token"] = token
                    st.rerun()
                else:
                    st.error("⚠️ Usuario o contraseña incorrectos.")
    st.stop()


# =====================================================================
# 6. GENERACIÓN DE PDF
# =====================================================================
# Estas funciones se conservan exactamente como en v1.0: producen los
# documentos legales de la óptica y su maquetación está validada en
# producción. Solo se accede a ellas mediante los helpers de abajo.
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


# ---------------------------------------------------------------------
# Constructores de documentos
# ---------------------------------------------------------------------
# En v1.0 los bytes del PDF se generaban dentro del `if st.button(...)`
# y se renderizaban en esa misma pasada. Al pulsar "Descargar",
# Streamlit reejecuta el script, la condición del botón vuelve a ser
# False y el PDF desaparecía. Aquí los bytes se construyen y se guardan
# en session_state, de modo que sobreviven a los reruns.
# ---------------------------------------------------------------------

def _nuevo_pdf():
    pdf = FPDF(orientation="P", unit="mm", format="Letter")
    pdf.set_compression(True)
    return pdf


def construir_paquete_factura(paciente, historia, venta, tipo_gafas, fecha=None):
    """Factura (2 copias) + orden(es) de laboratorio en un solo PDF."""
    pdf = _nuevo_pdf()
    hist_fact = procesar_historia_factura(historia, tipo_gafas)

    pdf.add_page()
    dibujar_media_carta(pdf, paciente, hist_fact, venta, "COPIA CLIENTE", fecha_impresion=fecha)
    pdf.add_page()
    dibujar_media_carta(pdf, paciente, hist_fact, venta, "COPIA ÓPTICA / CAJA", fecha_impresion=fecha)

    if tipo_gafas == "Dos Pares":
        h_lejos = historia.copy()
        h_lejos["adicion"] = ""
        pdf.add_page()
        dibujar_orden_laboratorio(pdf, paciente, h_lejos, venta, "DOS PARES - LEJOS", fecha_impresion=fecha)

        h_cerca = historia.copy()
        h_cerca["rx_final_od"] = get_cerca_rx(historia.get("rx_final_od"), historia.get("adicion"))
        h_cerca["rx_final_oi"] = get_cerca_rx(historia.get("rx_final_oi"), historia.get("adicion"))
        h_cerca["adicion"] = ""
        pdf.add_page()
        dibujar_orden_laboratorio(pdf, paciente, h_cerca, venta, "DOS PARES - CERCA", fecha_impresion=fecha)
    else:
        pdf.add_page()
        dibujar_orden_laboratorio(pdf, paciente, hist_fact, venta, tipo_gafas.upper(), fecha_impresion=fecha)

    return bytes(pdf.output())


def construir_factura_sola(paciente, historia, venta, fecha=None):
    pdf = _nuevo_pdf()
    pdf.add_page()
    dibujar_media_carta(pdf, paciente, historia, venta, "COPIA CLIENTE", fecha_impresion=fecha)
    pdf.add_page()
    dibujar_media_carta(pdf, paciente, historia, venta, "COPIA ÓPTICA / CAJA", fecha_impresion=fecha)
    return bytes(pdf.output())


def construir_orden_lab(paciente, historia, venta, tipo_orden="", fecha=None):
    pdf = _nuevo_pdf()
    pdf.add_page()
    dibujar_orden_laboratorio(pdf, paciente, historia, venta, tipo_orden, fecha_impresion=fecha)
    return bytes(pdf.output())


def construir_prescripcion(paciente, historia, detalles_rx, fecha=None):
    pdf = _nuevo_pdf()
    pdf.add_page()
    dibujar_prescripcion_clinica(pdf, paciente, historia, detalles_rx, fecha_impresion=fecha)
    return bytes(pdf.output())


def detalles_rx_desde_historia(hist: dict) -> dict:
    """Reconstruye el dict de detalles clínicos a partir de una historia guardada."""
    def _split(rx):
        p = str(rx or "").replace("(", "").replace(")", "").split()
        return (p[0] if len(p) > 0 else "",
                p[1] if len(p) > 1 else "",
                p[2] if len(p) > 2 else "")

    e_od, c_od, j_od = _split(hist.get("rx_final_od"))
    e_oi, c_oi, j_oi = _split(hist.get("rx_final_oi"))
    dp_od, dp_oi = parse_dp_individual(hist.get("dp", ""))
    return {
        "esf_od": e_od, "cil_od": c_od, "eje_od": j_od,
        "esf_oi": e_oi, "cil_oi": c_oi, "eje_oi": j_oi,
        "dp_od": dp_od, "dp_oi": dp_oi,
        "adicion": hist.get("adicion", ""),
        "av_lejos": "20/20", "av_cerca": "",
        "tipo_lente": "", "uso": "", "filtro": "", "prox_control": "",
    }


# =====================================================================
# 7. ESTADO DE SESIÓN Y CALLBACKS
# =====================================================================
def _fmt_money_cb(key):
    """Fábrica de callbacks: formatea un campo monetario al salir."""
    def _cb():
        st.session_state[key] = format_currency_co(st.session_state[key])
    return _cb


on_subtotal_change    = _fmt_money_cb("subtotal_input")
on_abono_change       = _fmt_money_cb("abono_input")
on_monto_rec_change   = _fmt_money_cb("monto_rec_input")
on_monto_gasto_change = _fmt_money_cb("monto_gasto_input")
on_p_compra_change    = _fmt_money_cb("p_compra_input")
on_p_venta_change     = _fmt_money_cb("p_venta_input")
on_p_compra_m_change  = _fmt_money_cb("p_compra_m")
on_p_venta_m_change   = _fmt_money_cb("p_venta_m")


def force_negative_cyl_od():
    if st.session_state.cil_od > 0:
        st.session_state.cil_od = -abs(st.session_state.cil_od)


def force_negative_cyl_oi():
    if st.session_state.cil_oi > 0:
        st.session_state.cil_oi = -abs(st.session_state.cil_oi)


def on_descuento_change():
    digits = clean_numeric_string(st.session_state.descuento_input)
    if not digits:
        st.session_state.descuento_input = ""
        return
    es_pct = st.session_state.get("tipo_descuento_widget") == "Porcentaje (%)"
    st.session_state.descuento_input = f"{digits}%" if es_pct else format_currency_co(digits)


on_tipo_descuento_change = on_descuento_change


def on_altura_focal_change():
    digits = clean_numeric_string(st.session_state.altura_focal_input)
    st.session_state.altura_focal_input = f"{digits} mm" if digits else ""


# Inicialización de claves de texto
for _k in ["subtotal_input", "abono_input", "descuento_input", "altura_focal_input",
           "monto_rec_input", "monto_gasto_input", "p_compra_input", "p_venta_input",
           "p_compra_m", "p_venta_m"]:
    st.session_state.setdefault(_k, "")

st.session_state.setdefault("last_fac_search", "")
st.session_state.setdefault("pdf_paquete", None)
st.session_state.setdefault("pdf_receta", None)

# Limpiezas diferidas solicitadas por el rerun anterior
if st.session_state.pop("trigger_clear_doc", False):
    for k in ["doc_input", "nom_input", "cel_input", "dir_input", "ocu_input",
              "edad_input", "mot_input", "ctrl_input", "dp_od_input", "dp_oi_input", "obs_input"]:
        st.session_state[k] = ""
    for k in ["esf_od", "cil_od", "esf_oi", "cil_oi", "add_input"]:
        st.session_state[k] = 0.0
    for k in ["eje_od", "eje_oi"]:
        st.session_state[k] = 0

if st.session_state.pop("trigger_clear_factura", False):
    for k in ["subtotal_input", "abono_input", "descuento_input", "altura_focal_input"]:
        st.session_state[k] = ""

if st.session_state.pop("trigger_clear_recaudo", False):
    st.session_state.monto_rec_input = ""
    st.session_state.last_fac_search = ""

# Toast global diferido
if "global_toast" in st.session_state:
    st.toast(st.session_state.pop("global_toast"),
             icon=st.session_state.pop("global_toast_icon", "✅"))


def toast_y_recargar(mensaje: str, icono: str = "✅"):
    """Programa un toast y reejecuta el script."""
    st.session_state.global_toast = mensaje
    st.session_state.global_toast_icon = icono
    st.rerun()


# =====================================================================
# 8. BARRA LATERAL Y NAVEGACIÓN
# =====================================================================
user      = st.session_state.user_info
user_rol  = user["rol"]
user_id   = user["id"]

ES_CLINICO = (user_rol == "admin" and user_id in ["1022396649", "1024585129"]) \
             or user_rol == "doctor_limitado"

# Estructura de navegación: {sección: [(etiqueta, icono)]}
NAV = {}
if ES_CLINICO:
    NAV["🏥 Área Clínica"] = ["Consultorio"]
if user_rol in ["admin", "asesor_limitado"]:
    NAV["🏬 Área Comercial"] = ["Facturación", "Cuadre de Caja"]
    NAV["⚙️ Operaciones"] = ["Inventario", "Control de Trabajos"]
if user_rol == "admin":
    NAV["📈 Administración"] = ["CRM y Fidelización", "Analítica"]

MODULO_ICONO = {
    "Consultorio": "👨‍⚕️", "Facturación": "🛍️", "Cuadre de Caja": "📊",
    "Inventario": "📦", "Control de Trabajos": "🔬",
    "CRM y Fidelización": "📅", "Analítica": "📈",
}

TODOS_MODULOS = [m for mods in NAV.values() for m in mods]
if not TODOS_MODULOS:
    st.error("Tu usuario no tiene módulos asignados. Contacta al administrador.")
    st.stop()


@st.cache_data(ttl=90, show_spinner=False)
def alertas_stock():
    """
    Resumen de stock crítico. Excluye Monturas: rotan constantemente
    y su stock unitario no representa una alerta real de reposición.
    """
    inv = db.inventario()
    relevantes = [p for p in inv if str(p.get("categoria", "")).lower() != "montura"]
    agotados = [p for p in relevantes if int(p.get("cantidad", 0)) == 0]
    bajos    = [p for p in relevantes if 0 < int(p.get("cantidad", 0)) <= 2]
    return agotados, bajos


with st.sidebar:
    b64_logo = get_image_base64(LOGO_PATH)
    if b64_logo:
        st.markdown(
            f'<div style="text-align:center;padding:.3rem 0 1rem;">'
            f'<img src="data:image/png;base64,{b64_logo}" width="82%"></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown("### 👓 Boomerang Visión")

    st.caption(f"👤 **{user['nombre']}**")

    # Navegación: un único st.radio sobre la lista completa de módulos.
    # En v1.0 cada módulo era un st.button dentro de un bucle que forzaba
    # st.rerun() en cada clic. Con un solo radio, Streamlit gestiona el
    # estado nativamente: menos reruns y sin desincronización entre grupos.
    st.markdown("**Navegación**")

    def _etiqueta(m):
        return f"{MODULO_ICONO.get(m, '')} {m}"

    st.session_state.setdefault("modulo_activo", TODOS_MODULOS[0])
    if st.session_state.modulo_activo not in TODOS_MODULOS:
        st.session_state.modulo_activo = TODOS_MODULOS[0]

    st.radio(
        "Módulo",
        TODOS_MODULOS,
        key="modulo_activo",
        label_visibility="collapsed",
        format_func=_etiqueta,
        captions=[
            next((s.split(" ", 1)[1] for s, ms in NAV.items() if m in ms), "")
            for m in TODOS_MODULOS
        ],
    )

    st.divider()

    if user_rol in ["admin", "asesor_limitado"]:
        try:
            agotados, bajos = alertas_stock()
            if agotados or bajos:
                with st.popover(f"⚠️ Stock ({len(agotados) + len(bajos)})",
                                use_container_width=True):
                    if agotados:
                        st.markdown(f"**🚨 Agotados ({len(agotados)})**")
                        for p in agotados:
                            st.caption(f"• {str(p.get('marca','')).upper()} — {p.get('codigo','')}")
                    if bajos:
                        st.markdown(f"**⚠️ Stock bajo ({len(bajos)})**")
                        for p in bajos:
                            st.caption(f"• {str(p.get('marca','')).upper()} — "
                                       f"{p.get('codigo','')} ({int(p.get('cantidad',0))} ud.)")
            else:
                st.caption("✅ Stock sin alertas")
        except Exception:
            pass

    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.user_info = None
        if "auth_token" in st.query_params:
            del st.query_params["auth_token"]
        st.rerun()

    st.caption(f"Boomerang Visión · v{APP_VERSION}")

modulo = st.session_state.modulo_activo


# =====================================================================
# 9. MÓDULOS
# =====================================================================

# ---------------------------------------------------------------------
# MÓDULO 1 · CONSULTORIO
# ---------------------------------------------------------------------
if modulo == "Consultorio":
    page_header("Consultorio", "👨‍⚕️", "Admisión, refracción e historia clínica")

    tab_adm, tab_ref, tab_cierre, tab_hist = st.tabs(
        ["📋 Admisión", "👁️ Refracción", "📝 Diagnóstico y Cierre", "📂 Historial"]
    )

    # ---------- Admisión ----------
    with tab_adm:
        with st.container(border=True):
            st.markdown("**Cargar paciente existente**")
            cb1, cb2 = st.columns([4, 1])
            doc_autofill = cb1.text_input(
                "Cédula", key="autofill_doc", label_visibility="collapsed",
                placeholder="Escribe la cédula y pulsa Buscar",
            ).strip().upper()
            if cb2.button("🔍 Buscar", use_container_width=True) and doc_autofill:
                p = db.paciente_por_doc(doc_autofill)
                if p:
                    st.session_state.doc_input  = p.get("documento", "")
                    st.session_state.nom_input  = p.get("nombre_completo", "")
                    st.session_state.cel_input  = p.get("celular", "")
                    st.session_state.dir_input  = p.get("direccion", "")
                    st.session_state.ocu_input  = p.get("ocupacion", "")
                    st.session_state.edad_input = p.get("edad", "")
                    st.toast("✅ Paciente cargado")
                    st.rerun()
                else:
                    st.warning("No se encontró ningún paciente con esa cédula.")

        st.markdown("")

        with st.container(border=True):
            st.markdown("##### 👤 Datos de identificación")
            c1, c2, c3 = st.columns(3)
            documento = c1.text_input("Documento *", key="doc_input")
            nombre    = c2.text_input("Nombre completo *", key="nom_input")
            celular   = c3.text_input("Celular *", key="cel_input",
                                      help="10 dígitos. El prefijo 57 se agrega solo.")

            st.markdown("##### 🏠 Datos complementarios")
            c4, c5, c6 = st.columns(3)
            direccion  = c4.text_input("Dirección", key="dir_input")
            ocupacion  = c5.text_input("Ocupación", key="ocu_input")
            fecha_nacimiento = c6.date_input(
                "Fecha de nacimiento",
                value=datetime(1995, 1, 1),
                min_value=datetime(1900, 1, 1),
                max_value=now_co().replace(tzinfo=None),
                format="DD/MM/YYYY",
            )
            edad = c4.text_input("Edad", key="edad_input")

        with st.container(border=True):
            st.markdown("##### 🩺 Motivo de la visita")
            cm1, cm2 = st.columns([2, 1])
            motivo         = cm1.text_input("Motivo de consulta", key="mot_input")
            ultimo_control = cm2.text_input("Último control", key="ctrl_input")

    # ---------- Refracción ----------
    with tab_ref:
        col_od, col_oi = st.columns(2)

        with col_od:
            with st.container(border=True):
                st.markdown("##### 👁️ Ojo Derecho (OD)")
                esfera_od   = st.number_input("Esfera", step=0.25, format="%.2f", key="esf_od")
                cilindro_od = st.number_input("Cilindro", step=0.25, format="%.2f",
                                              key="cil_od", on_change=force_negative_cyl_od,
                                              help="Se fuerza a valor negativo automáticamente.")
                eje_od      = st.number_input("Eje", min_value=0, max_value=175, step=5, key="eje_od")
                dp_od       = st.text_input("D.P. (mm)", key="dp_od_input")

        with col_oi:
            with st.container(border=True):
                st.markdown("##### 👁️ Ojo Izquierdo (OI)")
                esfera_oi   = st.number_input("Esfera", step=0.25, format="%.2f", key="esf_oi")
                cilindro_oi = st.number_input("Cilindro", step=0.25, format="%.2f",
                                              key="cil_oi", on_change=force_negative_cyl_oi,
                                              help="Se fuerza a valor negativo automáticamente.")
                eje_oi      = st.number_input("Eje", min_value=0, max_value=175, step=5, key="eje_oi")
                dp_oi       = st.text_input("D.P. (mm)", key="dp_oi_input")

        with st.container(border=True):
            ca1, ca2 = st.columns([1, 3])
            adicion = ca1.number_input("Adición", min_value=0.00, step=0.25,
                                       format="%.2f", key="add_input")
            with ca2:
                st.markdown("")
                rx_od_prev = build_rx_string(esfera_od, cilindro_od, eje_od)
                rx_oi_prev = build_rx_string(esfera_oi, cilindro_oi, eje_oi)
                st.caption("Vista previa de la fórmula")
                st.markdown(f"**OD:** `{rx_od_prev}`  ·  **OI:** `{rx_oi_prev}`"
                            + (f"  ·  **ADD:** `{adicion:+.2f}`" if adicion > 0 else ""))

    # ---------- Diagnóstico y cierre ----------
    with tab_cierre:
        with st.container(border=True):
            obs = st.text_area("Observaciones clínicas", height=120, key="obs_input")

        with st.container(border=True):
            habeas_ok = st.toggle(
                "El paciente autoriza el tratamiento de sus datos personales (Habeas Data)",
                key="habeas_check",
            )
            st.caption("Activa el interruptor una vez el paciente confirme verbalmente.")

        if st.button("💾 Guardar Historia Clínica", type="primary", use_container_width=True):
            if not documento or not nombre or not celular:
                st.error("⚠️ Documento, nombre y celular son obligatorios.")
            elif not habeas_ok:
                st.error("⚠️ Debes confirmar la autorización de Habeas Data.")
            else:
                doc_up = str(documento).upper()
                nom_up = str(nombre).upper()
                cel_norm = normalizar_celular(celular) or str(celular).upper()

                datos_pac = {
                    "documento": doc_up, "nombre_completo": nom_up, "celular": cel_norm,
                    "ocupacion": str(ocupacion).upper(), "direccion": str(direccion).upper(),
                    "fecha_nacimiento": fecha_nacimiento.strftime("%Y-%m-%d"),
                    "habeas_data": True, "habeas_data_fecha": now_co().isoformat(),
                }
                try:
                    db.upsert_paciente({**datos_pac, "edad": str(edad).upper()})
                except Exception:
                    db.upsert_paciente(datos_pac)   # tabla sin columna 'edad'

                db.insert_historia({
                    "paciente_documento": doc_up,
                    "motivo_consulta": str(motivo).upper(),
                    "rx_final_od": build_rx_string(esfera_od, cilindro_od, eje_od),
                    "rx_final_oi": build_rx_string(esfera_oi, cilindro_oi, eje_oi),
                    "dp": f"{dp_od}/{dp_oi}" if dp_od and dp_oi else (dp_od or dp_oi or ""),
                    "ultimo_control": str(ultimo_control).upper(),
                    "observaciones": str(obs).upper(),
                    "adicion": f"{adicion:+.2f}" if adicion > 0.0 else "",
                    "fecha": now_co().isoformat(),
                })
                st.session_state.trigger_clear_doc = True
                toast_y_recargar(f"Historia de {nom_up} guardada.")

    # ---------- Historial ----------
    with tab_hist:
        hb1, hb2 = st.columns([4, 1])
        doc_hist = hb1.text_input(
            "Cédula del paciente", key="doc_hist_input",
            label_visibility="collapsed", placeholder="Cédula del paciente a consultar",
        ).strip().upper()
        buscar_hist = hb2.button("🔍 Buscar", key="btn_buscar_hist", use_container_width=True)

        if buscar_hist and not doc_hist:
            st.warning("Escribe la cédula antes de buscar.")
        elif buscar_hist or st.session_state.get("hist_ultimo_doc"):
            doc_target = doc_hist or st.session_state.get("hist_ultimo_doc", "")
            if buscar_hist:
                st.session_state.hist_ultimo_doc = doc_hist
                doc_target = doc_hist

            with st.spinner("Consultando historial…"):
                p = db.paciente_por_doc(doc_target)
                historias = db.historias_de(doc_target, limite=10)

            if not p:
                st.error("No se encontró ningún paciente con ese documento.")
            else:
                with st.container(border=True):
                    i1, i2, i3, i4 = st.columns(4)
                    i1.metric("Paciente", str(p.get("nombre_completo", "")).upper()[:22])
                    i2.metric("Cédula", p.get("documento", "—"))
                    i3.metric("Celular", p.get("celular", "—"))
                    i4.metric("Consultas", len(historias))

                if not historias:
                    st.info("Este paciente aún no tiene historias clínicas registradas.")
                else:
                    st.markdown(f"##### Últimas {len(historias)} consulta(s)")
                    for h in historias:
                        etiqueta = f"📅 {fmt_fecha(h.get('fecha'))} — {h.get('motivo_consulta') or 'Sin motivo'}"
                        with st.expander(etiqueta):
                            e1, e2 = st.columns(2)
                            e1.markdown(f"**Rx OD:** `{format_rx_ui(h.get('rx_final_od','N/A'))}`")
                            e2.markdown(f"**Rx OI:** `{format_rx_ui(h.get('rx_final_oi','N/A'))}`")
                            add_v = format_add(h.get("adicion"))
                            if h.get("dp"):
                                e1.markdown(f"**D.P.:** `{h.get('dp')}`")
                            if add_v:
                                e2.markdown(f"**Adición:** `{add_v}`")
                            if h.get("ultimo_control"):
                                st.caption(f"Último control: {h.get('ultimo_control')}")
                            if h.get("observaciones"):
                                st.info(h.get("observaciones"))


# ---------------------------------------------------------------------
# MÓDULO 2 · FACTURACIÓN
# ---------------------------------------------------------------------
elif modulo == "Facturación":
    page_header("Facturación y Ventas", "🛍️", "Ventas, recaudos, anulación y reimpresión")

    tab_venta, tab_recaudo, tab_anular, tab_reimp = st.tabs(
        ["🛒 Nueva Venta", "💵 Recaudar Saldo", "🚫 Anular", "🖨️ Reimprimir"]
    )

    # =================== NUEVA VENTA ===================
    with tab_venta:
        search_doc = buscador("Cédula del paciente", "search_opt",
                              placeholder="🔍 Escribe la cédula del paciente")

        if not search_doc:
            st.info("Escribe la cédula del paciente para iniciar una venta.")
        else:
            paciente = db.paciente_por_doc(search_doc)

            # --- Paciente no registrado: alta rápida ---
            if not paciente:
                st.warning("⚠️ Paciente no registrado (fórmula externa o paciente nuevo).")
                with st.container(border=True):
                    st.markdown("##### ➕ Registrar paciente")
                    with st.form("alta_rapida"):
                        q1, q2 = st.columns(2)
                        q_nom = q1.text_input("Nombre completo *")
                        q_cel = q2.text_input("Celular *")
                        q_dir = st.text_input("Dirección (opcional)")
                        if st.form_submit_button("Guardar paciente", type="primary",
                                                 use_container_width=True):
                            if q_nom and q_cel:
                                db.upsert_paciente({
                                    "documento": search_doc,
                                    "nombre_completo": q_nom.upper(),
                                    "celular": normalizar_celular(q_cel),
                                    "direccion": q_dir.upper(),
                                    "habeas_data": True,
                                    "habeas_data_fecha": now_co().isoformat(),
                                })
                                toast_y_recargar("Paciente registrado.")
                            else:
                                st.error("Nombre y celular son obligatorios.")
            else:
                # --- Ficha del paciente ---
                with st.container(border=True):
                    p1, p2, p3 = st.columns([2, 1, 1])
                    p1.markdown(f"**👤 {paciente['nombre_completo']}**")
                    p2.markdown(f"**Cédula:** `{paciente['documento']}`")
                    p3.markdown(f"**Tel:** `{paciente.get('celular','—')}`")

                historias_data = db.historias_de(search_doc)
                if historias_data:
                    with st.expander(f"👁️ Fórmulas registradas ({len(historias_data)})"):
                        for h in historias_data:
                            add_v = format_add(h.get("adicion"))
                            st.markdown(
                                f"**{fmt_fecha(h.get('fecha'))}** — "
                                f"OD `{format_rx_ui(h.get('rx_final_od','N/A'))}` · "
                                f"OI `{format_rx_ui(h.get('rx_final_oi','N/A'))}`"
                                + (f" · ADD `{add_v}`" if add_v else "")
                                + (f" · DP `{h.get('dp')}`" if h.get("dp") else "")
                            )
                            if h.get("observaciones"):
                                st.caption(h["observaciones"])
                            st.divider()
                else:
                    st.info("Este paciente no tiene fórmulas guardadas. "
                            "Puedes usar la opción de fórmula externa.")

                # --- Titular de la factura ---
                with st.container(border=True):
                    es_mismo = st.checkbox("La factura queda a nombre del paciente registrado",
                                           value=True)
                    if es_mismo:
                        titular_nombre = paciente["nombre_completo"]
                        titular_doc    = paciente["documento"]
                        titular_tel    = paciente.get("celular", "N/A")
                    else:
                        st.markdown("##### 👤 Datos del titular / pagador")
                        t1, t2, t3 = st.columns(3)
                        titular_nombre = t1.text_input("Nombre del titular *").upper()
                        titular_doc    = t2.text_input("Cédula / NIT *").upper()
                        titular_tel    = t3.text_input("Celular *").upper()

                # --- Número de factura ---
                try:
                    res_max = (supabase.table("ventas_facturacion").select("numero_factura")
                               .order("numero_factura", desc=True).limit(1).execute())
                    sugerido = int(res_max.data[0]["numero_factura"]) + 1 if res_max.data else 5342
                except Exception:
                    sugerido = 5342

                with st.container(border=True):
                    nf1, nf2 = st.columns([1, 3])
                    num_factura = nf1.text_input("N° de Factura", value=str(sugerido))
                    factura_existe = False
                    if num_factura and db.factura(num_factura):
                        nf2.error(f"⚠️ La factura **{num_factura}** ya existe.")
                        factura_existe = True

                # --- Origen de la Rx ---
                with st.container(border=True):
                    st.markdown("##### 🔬 Origen de la fórmula")
                    opc_rx = (["Fórmula del Sistema"] if historias_data else []) + \
                             ["Fórmula Externa", "No aplica"]
                    origen_rx = st.pills("Fuente de la Rx", opc_rx, default=opc_rx[0],
                                         label_visibility="collapsed")

                    if origen_rx == "Fórmula del Sistema" and historias_data:
                        historia = historias_data[0]
                        st.success(
                            f"Usando fórmula del {fmt_fecha(historia.get('fecha'))} — "
                            f"OD `{format_rx_ui(historia.get('rx_final_od','N/A'))}` · "
                            f"OI `{format_rx_ui(historia.get('rx_final_oi','N/A'))}`"
                        )
                    elif origen_rx == "Fórmula Externa":
                        e1, e2, e3, e4 = st.columns(4)
                        historia = {
                            "rx_final_od": e1.text_input("RX OD").upper() or "N/A",
                            "rx_final_oi": e2.text_input("RX OI").upper() or "N/A",
                            "adicion":     e3.text_input("ADD").upper(),
                            "dp":          e4.text_input("DP").upper(),
                            "observaciones": "FÓRMULA EXTERNA",
                        }
                    else:
                        historia = {"rx_final_od": "N/A", "rx_final_oi": "N/A",
                                    "adicion": "", "dp": "", "observaciones": "NO APLICA RX"}

                    tipo_gafas = st.selectbox(
                        "Formato de impresión",
                        ["Lejos", "Cerca", "Adición (Bifocal/Progresivo)", "Dos Pares"],
                    )

                # --- Montura y descripción ---
                with st.container(border=True):
                    st.markdown("##### 🕶️ Montura y descripción")
                    origen_montura = st.pills(
                        "Origen de la montura",
                        ["Montura de Vitrina", "Montura del Paciente", "No aplica"],
                        default="Montura de Vitrina", label_visibility="collapsed",
                    )

                    desc_sug = "LENTES EN MONTURA DEL PACIENTE"
                    selected_frame_code = None

                    if origen_montura == "Montura de Vitrina":
                        v1, v2 = st.columns([1, 2])
                        ref_busqueda = v1.text_input("N° de referencia").upper()
                        if ref_busqueda:
                            m = db.producto(ref_busqueda)
                            es_montura = m and str(m.get("categoria", "")).lower() == "montura"
                            if es_montura and int(m.get("cantidad", 0)) > 0:
                                v2.success(f"✅ {m['marca']} · "
                                           f"${format_currency_co(m['precio_venta'])}")
                                selected_frame_code = m["codigo"]
                                desc_sug = f"LENTES + MONTURA {m['marca']} REF. {selected_frame_code}"
                            elif es_montura:
                                v2.error("⚠️ Sin stock disponible")
                                desc_sug = f"LENTES + MONTURA {m['marca']} REF. {ref_busqueda} (SIN STOCK)"
                            else:
                                v2.warning("⚠️ Referencia no encontrada en inventario")
                                desc_sug = f"LENTES + MONTURA REF. {ref_busqueda}"
                        else:
                            desc_sug = "LENTES + MONTURA REF. "
                    elif origen_montura == "No aplica":
                        desc_sug = "SERVICIO / OTRO (TRASPASO / SOLDADURA / PROVEEDOR)"

                    desc_producto = st.text_input("Descripción final", value=desc_sug).upper()

                # --- Valores ---
                with st.container(border=True):
                    st.markdown("##### 💰 Valores")
                    m1, m2, m3 = st.columns(3)
                    m1.text_input("Subtotal ($)", key="subtotal_input",
                                  on_change=on_subtotal_change)
                    m2.selectbox("Tipo de descuento",
                                 ["Sin Descuento", "Porcentaje (%)", "Valor Fijo ($)"],
                                 key="tipo_descuento_widget",
                                 on_change=on_tipo_descuento_change)
                    m3.text_input("Descuento aplicado", key="descuento_input",
                                  on_change=on_descuento_change)

                    sub_val   = int(clean_numeric_string(st.session_state.subtotal_input) or 0)
                    abono_val = int(clean_numeric_string(st.session_state.abono_input) or 0)
                    desc_val  = int(clean_numeric_string(st.session_state.descuento_input) or 0)
                    es_pct    = st.session_state.get("tipo_descuento_widget") == "Porcentaje (%)"
                    desc_calc = int((desc_val / 100.0) * sub_val) if es_pct else desc_val
                    tot_neto  = sub_val - desc_calc
                    sal_pend  = tot_neto - abono_val

                    n1, n2 = st.columns(2)
                    n1.text_input("Abono inicial ($)", key="abono_input",
                                  on_change=on_abono_change)
                    metodo_pago = n2.selectbox("Método de pago", METODOS_PAGO)

                    st.divider()
                    r1, r2, r3 = st.columns(3)
                    r1.metric("Subtotal", f"${format_currency_co(sub_val)}")
                    r2.metric("Total neto", f"${format_currency_co(tot_neto)}",
                              delta=f"-${format_currency_co(desc_calc)}" if desc_calc else None,
                              delta_color="inverse")
                    r3.metric("Saldo pendiente", f"${format_currency_co(sal_pend)}")

                # --- Entrega ---
                with st.container(border=True):
                    st.markdown("##### 📦 Entrega")
                    d1, d2 = st.columns(2)
                    fecha_entrega = d1.text_input(
                        "Fecha / hora de entrega",
                        placeholder="Ej: 3 días · Mañana · 15-ago").upper()
                    altura_focal = d2.text_input("Altura focal (opcional)",
                                                 key="altura_focal_input",
                                                 on_change=on_altura_focal_change).upper()

                with st.expander("🩺 Detalles para receta clínica (opcional)"):
                    rx1, rx2 = st.columns(2)
                    tipo_lente = rx1.selectbox("Tipo de lente",
                        ["MONOFOCAL", "PROGRESIVO", "BIFOCAL INVISIBLE",
                         "BIFOCAL FLAT TOP", "OCUPACIONAL", "DOS PARES"])
                    filtro = rx1.selectbox("Filtro",
                        ["SIN FILTRO", "ANTIRREFLEJO", "FOTOSENSIBLE",
                         "ANTIRREFLEJO + FOTOSENSIBLE"])
                    av_lejos = rx1.text_input("AV Lejos").upper()
                    uso = rx2.selectbox("Uso",
                        ["PERMANENTE", "PROLONGADO", "ESFUERZO VISUAL", "PROTECCIÓN"])
                    prox_control = rx2.text_input("Próximo control").upper()
                    av_cerca = rx2.text_input("AV Cerca").upper()
                    detalles_rx = {"tipo_lente": tipo_lente, "filtro": filtro, "uso": uso,
                                   "prox_control": prox_control,
                                   "av_lejos": av_lejos, "av_cerca": av_cerca}

                st.markdown("")
                b1, b2 = st.columns(2)
                gen_paquete = b1.button("📄 Generar Factura y Órdenes", type="primary",
                                        use_container_width=True, disabled=factura_existe)
                gen_receta  = b2.button("👁️ Generar Receta Clínica", use_container_width=True)

                # --- Generación del paquete ---
                if gen_paquete:
                    if not desc_producto or sub_val == 0 or not titular_nombre or not titular_doc:
                        st.warning("⚠️ Completa descripción, subtotal y datos del titular.")
                    else:
                        venta_data = {
                            "numero_factura": num_factura, "titular_nombre": titular_nombre,
                            "titular_doc": titular_doc, "titular_tel": titular_tel,
                            "descripcion": desc_producto, "subtotal": sub_val,
                            "descuento": desc_calc, "total": tot_neto, "abono": abono_val,
                            "saldo": sal_pend, "fecha_entrega": fecha_entrega,
                            "altura_focal": altura_focal, "metodo_pago": metodo_pago,
                        }
                        try:
                            db.insert_venta({
                                **venta_data,
                                "paciente_documento": paciente["documento"],
                                "estado": "ACTIVA",
                                "estado_lab": "Pendiente de enviar",
                                "fecha_venta": now_co().isoformat(),
                            })
                            if origen_montura == "Montura de Vitrina" and selected_frame_code:
                                db.descontar_stock(selected_frame_code, 1)
                                db.descontar_stock("ESTUCHE-GENERICO", 1)
                        except Exception as e:
                            st.error(f"Error al guardar en base de datos: {e}")

                        # Los bytes se guardan en session_state para que el
                        # visor y la descarga sobrevivan al rerun del botón.
                        st.session_state.pdf_paquete = {
                            "bytes": construir_paquete_factura(
                                paciente, historia, venta_data, tipo_gafas),
                            "nombre": f"Facturacion_{num_factura}.pdf",
                            "factura": num_factura,
                        }
                        st.session_state.trigger_clear_factura = True
                        toast_y_recargar(f"Venta registrada · Factura #{num_factura}")

                if gen_receta:
                    st.session_state.pdf_receta = {
                        "bytes": construir_prescripcion(paciente, historia, detalles_rx),
                        "nombre": f"Receta_{paciente['documento']}.pdf",
                    }
                    st.toast("🎉 Receta clínica generada")

        # --- Visores persistentes ---
        if st.session_state.pdf_paquete:
            st.divider()
            vc1, vc2 = st.columns([4, 1])
            vc1.markdown(f"##### 📄 Factura #{st.session_state.pdf_paquete['factura']}")
            if vc2.button("✖ Cerrar", key="close_paq", use_container_width=True):
                st.session_state.pdf_paquete = None
                st.rerun()
            pdf_viewer(st.session_state.pdf_paquete["bytes"],
                       st.session_state.pdf_paquete["nombre"])

        if st.session_state.pdf_receta:
            st.divider()
            rc1, rc2 = st.columns([4, 1])
            rc1.markdown("##### 👁️ Receta clínica")
            if rc2.button("✖ Cerrar", key="close_rec", use_container_width=True):
                st.session_state.pdf_receta = None
                st.rerun()
            pdf_viewer(st.session_state.pdf_receta["bytes"],
                       st.session_state.pdf_receta["nombre"])

    # =================== RECAUDAR SALDO ===================
    with tab_recaudo:
        fac_search = buscador("N° de factura o cédula", "recaudo_search",
                              placeholder="🔍 N° de factura o cédula del paciente")

        if fac_search:
            con_saldo = db.buscar_factura(fac_search, solo_con_saldo=True)
            cualquiera = db.buscar_factura(fac_search)

            if cualquiera and not con_saldo:
                f = cualquiera[0]
                st.success(
                    f"✅ La factura **{f['numero_factura']}** de **{f['titular_nombre']}** "
                    f"ya está cancelada en su totalidad "
                    f"(${format_currency_co(int(f.get('total', 0)))}). Sin saldo pendiente."
                )
            elif con_saldo:
                fac = con_saldo[0]
                saldo_actual = int(fac["saldo"])

                with st.container(border=True):
                    s1, s2, s3 = st.columns(3)
                    s1.metric("Factura", f"#{fac['numero_factura']}")
                    s2.metric("Total", f"${format_currency_co(int(fac.get('total',0)))}")
                    s3.metric("Saldo pendiente", f"${format_currency_co(saldo_actual)}")
                    st.caption(f"Paciente: **{fac['titular_nombre']}** · "
                               f"Estado: `{fac.get('estado_lab','—')}`")

                if st.session_state.last_fac_search != fac["numero_factura"]:
                    st.session_state.monto_rec_input = format_currency_co(saldo_actual)
                    st.session_state.last_fac_search = fac["numero_factura"]

                with st.container(border=True):
                    g1, g2, g3 = st.columns(3)
                    monto_rec = int(clean_numeric_string(
                        g1.text_input("Monto a abonar ($)", key="monto_rec_input",
                                      on_change=on_monto_rec_change)) or 0)
                    metodo_rec = g2.selectbox("Método de cobro", METODOS_PAGO, key="met_rec")
                    nuevo_est = g3.selectbox("Nuevo estado", ESTADOS_LAB, index=3)

                    if st.button("✅ Registrar pago y actualizar estado", type="primary",
                                 use_container_width=True):
                        if monto_rec <= 0:
                            st.error("⚠️ El monto debe ser mayor a cero.")
                        elif monto_rec > saldo_actual:
                            st.error(f"⚠️ El monto supera el saldo de "
                                     f"${format_currency_co(saldo_actual)}.")
                        else:
                            db.update_venta(fac["numero_factura"], {
                                "saldo": saldo_actual - monto_rec,
                                "abono": int(fac["abono"]) + monto_rec,
                                "estado_lab": nuevo_est,
                            })
                            db.insert_pago({
                                "numero_factura": fac["numero_factura"],
                                "paciente_documento": fac["paciente_documento"],
                                "monto_pagado": monto_rec,
                                "metodo_pago": metodo_rec,
                                "fecha_pago": now_co().isoformat(),
                            })
                            st.session_state.trigger_clear_recaudo = True
                            toast_y_recargar(
                                f"Pago registrado · Nuevo saldo: "
                                f"${format_currency_co(saldo_actual - monto_rec)}")
            else:
                st.warning("⚠️ No se encontraron facturas para ese criterio.")

    # =================== ANULAR ===================
    with tab_anular:
        @st.dialog("Confirmar anulación")
        def confirmar_anulacion(fac):
            st.warning("Esta acción es **irreversible**.")
            st.markdown(
                f"**Factura:** #{fac['numero_factura']}  \n"
                f"**Titular:** {fac['titular_nombre']}  \n"
                f"**Valor:** ${format_currency_co(fac['total'])}"
            )
            texto = st.text_input("Escribe ANULAR para confirmar").strip().upper()
            d1, d2 = st.columns(2)
            if d1.button("Cancelar", use_container_width=True):
                st.rerun()
            if d2.button("🚨 Anular factura", type="primary",
                         use_container_width=True, disabled=(texto != "ANULAR")):
                db.update_venta(fac["numero_factura"], {"estado": "ANULADA"})
                toast_y_recargar("Factura anulada.", "🚨")

        num_anular = buscador("N° de factura a anular", "input_anular",
                              placeholder="🔍 N° de factura")
        if num_anular:
            fac_a = db.factura(num_anular)
            if not fac_a:
                st.error("No existe ninguna factura con ese número.")
            elif fac_a.get("estado") == "ANULADA":
                st.error("⚠️ Esta factura ya se encuentra anulada.")
            else:
                with st.container(border=True):
                    a1, a2, a3 = st.columns(3)
                    a1.metric("Factura", f"#{fac_a['numero_factura']}")
                    a2.metric("Titular", str(fac_a["titular_nombre"])[:20])
                    a3.metric("Valor", f"${format_currency_co(fac_a['total'])}")
                    st.caption(f"Emitida el {fmt_fecha(fac_a.get('fecha_venta'), True)}")

                if st.button("🚫 Anular esta factura", type="primary"):
                    confirmar_anulacion(fac_a)

    # =================== REIMPRIMIR ===================
    with tab_reimp:
        st.caption("Los documentos se regeneran con la fecha original de emisión.")
        reimp_search = buscador("N° de factura o cédula", "reimp_search",
                                placeholder="🔍 N° de factura o cédula del paciente")

        if reimp_search:
            encontradas = db.buscar_factura(reimp_search)
            if not encontradas:
                st.error("No se encontró ninguna factura activa para ese criterio.")
            else:
                venta_r = encontradas[0]
                fecha_original = parse_fecha(venta_r.get("fecha_venta"))

                with st.container(border=True):
                    f1, f2, f3 = st.columns(3)
                    f1.metric("Factura", f"#{venta_r['numero_factura']}")
                    f2.metric("Total", f"${format_currency_co(int(venta_r.get('total',0)))}")
                    f3.metric("Saldo", f"${format_currency_co(int(venta_r.get('saldo',0)))}")
                    st.caption(
                        f"**{venta_r['titular_nombre']}** · "
                        f"Emitida el {fmt_fecha(venta_r.get('fecha_venta'), True)} · "
                        f"Estado `{venta_r.get('estado_lab','—')}`"
                    )
                    st.markdown(f"**Detalle:** {venta_r.get('descripcion','—')}")

                pac_doc = venta_r.get("paciente_documento", "")
                paciente_r = db.paciente_por_doc(pac_doc) or {
                    "nombre_completo": venta_r.get("titular_nombre", ""),
                    "documento": pac_doc, "direccion": "", "celular": "",
                }

                # Historia vigente al momento de la venta (no la más reciente)
                historias_r = db.historias_de(pac_doc)
                hist_r = None
                if historias_r and fecha_original:
                    for h in historias_r:
                        h_dt = parse_fecha(h.get("fecha"))
                        if h_dt and h_dt <= fecha_original:
                            hist_r = h
                            break
                if not hist_r:
                    hist_r = historias_r[-1] if historias_r else {
                        "rx_final_od": "", "rx_final_oi": "", "dp": "",
                        "adicion": "", "observaciones": "",
                    }

                if not hist_r.get("rx_final_od") and not hist_r.get("rx_final_oi"):
                    st.warning("⚠️ No hay fórmula registrada para este paciente. "
                               "La orden y la receta se generarán sin datos de Rx.")

                st.markdown("##### Documentos disponibles")
                dcol1, dcol2, dcol3 = st.columns(3)

                with dcol1:
                    with st.container(border=True):
                        st.markdown("**📄 Factura**")
                        st.caption("Copia cliente + óptica")
                        try:
                            st.download_button(
                                "⬇️ Descargar", use_container_width=True,
                                data=construir_factura_sola(paciente_r, hist_r, venta_r,
                                                            fecha_original),
                                file_name=f"Factura_{venta_r['numero_factura']}.pdf",
                                mime="application/pdf",
                                key=f"rf_{venta_r['numero_factura']}")
                        except Exception as e:
                            st.error(f"Error: {e}")

                with dcol2:
                    with st.container(border=True):
                        st.markdown("**🔬 Orden de Laboratorio**")
                        st.caption("Con Rx del trabajo")
                        try:
                            st.download_button(
                                "⬇️ Descargar", use_container_width=True,
                                data=construir_orden_lab(paciente_r, hist_r, venta_r,
                                                         fecha=fecha_original),
                                file_name=f"OrdenLab_{venta_r['numero_factura']}.pdf",
                                mime="application/pdf",
                                key=f"ro_{venta_r['numero_factura']}")
                        except Exception as e:
                            st.error(f"Error: {e}")

                with dcol3:
                    with st.container(border=True):
                        st.markdown("**📋 Prescripción**")
                        st.caption("Receta del optómetra")
                        try:
                            st.download_button(
                                "⬇️ Descargar", use_container_width=True,
                                data=construir_prescripcion(
                                    paciente_r, hist_r,
                                    detalles_rx_desde_historia(hist_r), fecha_original),
                                file_name=f"Prescripcion_{venta_r['numero_factura']}.pdf",
                                mime="application/pdf",
                                key=f"rp_{venta_r['numero_factura']}")
                        except Exception as e:
                            st.error(f"Error: {e}")


# ---------------------------------------------------------------------
# MÓDULO 3 · CUADRE DE CAJA
# ---------------------------------------------------------------------
elif modulo == "Cuadre de Caja":
    page_header("Cuadre de Caja", "📊", "Resumen diario de movimientos")

    with st.container(border=True):
        cf1, cf2 = st.columns([2, 1])
        fecha_consulta = cf1.date_input("Fecha a consultar", now_co().date(),
                                        format="DD/MM/YYYY")
        base_caja = cf2.number_input("Base inicial en gaveta ($)",
                                     min_value=0, value=50000, step=10000)

    fecha_str = fecha_consulta.strftime("%Y-%m-%d")
    ventas, recaudos, gastos_dia = db.movimientos_dia(fecha_str)

    tab_resumen, tab_gastos = st.tabs(["💰 Resumen y movimientos", "💸 Registrar gasto"])

    with tab_resumen:
        def _suma(items, campo, efectivo=True):
            return sum(
                i.get(campo, 0) for i in items
                if (str(i.get("metodo_pago") or "").upper() == "EFECTIVO") == efectivo
            )

        abono_ef   = _suma(ventas, "abono", True)
        abono_bk   = _suma(ventas, "abono", False)
        recaudo_ef = _suma(recaudos, "monto_pagado", True)
        recaudo_bk = _suma(recaudos, "monto_pagado", False)
        gastos_ef  = _suma(gastos_dia, "monto", True)

        efectivo_caja = base_caja + abono_ef + recaudo_ef - gastos_ef
        total_bancos  = abono_bk + recaudo_bk
        flujo_total   = (efectivo_caja - base_caja) + total_bancos + gastos_ef

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("💵 Efectivo en gaveta", f"${format_currency_co(efectivo_caja)}")
        k2.metric("🏦 Total bancos", f"${format_currency_co(total_bancos)}")
        k3.metric("💸 Gastos del día", f"${format_currency_co(gastos_ef)}",
                  delta="- Salidas" if gastos_ef else None, delta_color="inverse")
        k4.metric("✅ Flujo total", f"${format_currency_co(flujo_total)}")

        st.divider()
        st.markdown(f"##### 📜 Movimientos del {fecha_consulta.strftime('%d/%m/%Y')}")

        movimientos = [{"Hora": "08:00", "Tipo": "BASE",
                        "Detalle": "Apertura de caja", "Monto": base_caja,
                        "Método": "EFECTIVO"}]
        for v in ventas:
            if v.get("abono", 0) > 0:
                movimientos.append({
                    "Hora": str(v.get("fecha_venta", ""))[11:16], "Tipo": "VENTA",
                    "Detalle": f"Fac #{v['numero_factura']} · {v['titular_nombre']}",
                    "Monto": v["abono"], "Método": v.get("metodo_pago", "—")})
        for r in recaudos:
            movimientos.append({
                "Hora": str(r.get("fecha_pago", ""))[11:16], "Tipo": "RECAUDO",
                "Detalle": f"Saldo Fac #{r['numero_factura']}",
                "Monto": r["monto_pagado"], "Método": r.get("metodo_pago", "—")})
        for g in gastos_dia:
            movimientos.append({
                "Hora": str(g.get("fecha_gasto", ""))[11:16], "Tipo": "GASTO",
                "Detalle": str(g["descripcion"]).upper(),
                "Monto": -g["monto"], "Método": g.get("metodo_pago", "—")})

        df_mov = pd.DataFrame(movimientos).sort_values("Hora", ascending=False)
        st.dataframe(
            df_mov, use_container_width=True, hide_index=True,
            column_config={
                "Monto": st.column_config.NumberColumn("Monto", format="$ %d"),
                "Tipo": st.column_config.TextColumn("Tipo", width="small"),
                "Hora": st.column_config.TextColumn("Hora", width="small"),
            },
        )
        st.download_button(
            "📊 Descargar historial (.xlsx)",
            data=convert_df_to_excel(df_mov, "Caja"),
            file_name=f"Movimientos_{fecha_str}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    with tab_gastos:
        with st.container(border=True):
            st.markdown("##### 💸 Registrar salida de dinero")
            g1, g2, g3 = st.columns([2, 1, 1])
            desc_gasto = g1.text_input("Concepto",
                                       placeholder="Ej: Pago mensajería laboratorio").upper()
            monto_gasto = int(clean_numeric_string(
                g2.text_input("Valor ($)", key="monto_gasto_input",
                              on_change=on_monto_gasto_change)) or 0)
            metodo_gasto = g3.selectbox("Forma de salida",
                                        ["EFECTIVO", "BOLD", "NEQUI", "DAVIPLATA"])

            if st.button("💾 Guardar gasto", type="primary", use_container_width=True):
                if not desc_gasto or monto_gasto <= 0:
                    st.warning("⚠️ Ingresa un concepto y un valor válidos.")
                else:
                    db.insert_gasto({
                        "descripcion": desc_gasto, "monto": monto_gasto,
                        "metodo_pago": metodo_gasto, "fecha_gasto": now_co().isoformat(),
                    })
                    st.session_state.monto_gasto_input = ""
                    toast_y_recargar("Gasto registrado.")


# ---------------------------------------------------------------------
# MÓDULO 4 · INVENTARIO
# ---------------------------------------------------------------------
elif modulo == "Inventario":
    page_header("Inventario", "📦", "Bodega, vitrinas y ajustes de stock")

    tab_cat, tab_ing, tab_aju = st.tabs(
        ["📋 Catálogo", "➕ Registrar producto", "🔄 Ajuste rápido"])

    with tab_cat:
        inventario = db.inventario()
        if not inventario:
            st.info("La bodega está vacía.")
        else:
            filas, inv_total, potencial = [], 0, 0
            for p in inventario:
                cant   = int(p.get("cantidad", 0))
                compra = int(p.get("precio_compra", 0))
                venta  = int(p.get("precio_venta", 0))
                inv_total += cant * compra
                potencial += cant * venta
                filas.append({
                    "Código": str(p.get("codigo", "")),
                    "Categoría": str(p.get("categoria", "")),
                    "Marca": str(p.get("marca", "")).upper(),
                    "Descripción": str(p.get("descripcion", "")).upper(),
                    "Cant.": cant, "Costo": compra, "P. Venta": venta,
                    "Ingreso": fmt_fecha(p.get("fecha_ingreso")),
                })

            df_inv = pd.DataFrame(filas)

            k1, k2, k3 = st.columns(3)
            k1.metric("📦 Unidades en stock", f"{int(df_inv['Cant.'].sum())}")
            k2.metric("💵 Inversión", f"${format_currency_co(inv_total)}")
            k3.metric("📈 Ganancia proyectada",
                      f"${format_currency_co(potencial - inv_total)}")

            st.divider()
            fc1, fc2 = st.columns([2, 1])
            filtro_txt = fc1.text_input("🔍 Filtrar por código, marca o descripción").upper()
            cats = ["Todas"] + sorted({f["Categoría"] for f in filas if f["Categoría"]})
            filtro_cat = fc2.selectbox("Categoría", cats)

            df_vista = df_inv.copy()
            if filtro_cat != "Todas":
                df_vista = df_vista[df_vista["Categoría"] == filtro_cat]
            if filtro_txt:
                mask = (df_vista["Código"].str.contains(filtro_txt, na=False) |
                        df_vista["Marca"].str.contains(filtro_txt, na=False) |
                        df_vista["Descripción"].str.contains(filtro_txt, na=False))
                df_vista = df_vista[mask]

            st.caption(f"Mostrando **{len(df_vista)}** de **{len(df_inv)}** productos")
            st.dataframe(
                df_vista, use_container_width=True, hide_index=True,
                column_config={
                    "Costo": st.column_config.NumberColumn("Costo", format="$ %d"),
                    "P. Venta": st.column_config.NumberColumn("P. Venta", format="$ %d"),
                    "Cant.": st.column_config.NumberColumn("Cant.", width="small"),
                },
            )
            st.download_button(
                "📊 Exportar inventario (.xlsx)",
                data=convert_df_to_excel(df_inv, "Bodega"),
                file_name="Inventario.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    with tab_ing:
        st.caption("💡 Crea el código `ESTUCHE-GENERICO` para que se descuente "
                   "automáticamente al vender monturas.")
        with st.container(border=True):
            inv_categoria = st.selectbox(
                "Categoría",
                ["Montura", "Lente de Contacto", "Accesorio", "Estuche", "Líquido", "Otro"])

            if inv_categoria == "Montura":
                m1, m2 = st.columns(2)
                inv_marca = m1.text_input("Marca *", key="m_marca").upper()
                inv_prov  = m2.text_input("Proveedor", key="m_prov").upper()
                m3, m4 = st.columns(2)
                inv_mat  = m3.selectbox("Material",
                    ["METALICA", "TITANIO", "ALUMINIO", "ACERO", "PLASTICO", "ACETATO", "TR 90"])
                inv_cant = m4.number_input("Cantidad a ingresar", min_value=1, step=1, value=1)
                p1, p2 = st.columns(2)
                val_compra = int(clean_numeric_string(
                    p1.text_input("Precio compra unitario $", key="p_compra_m",
                                  on_change=on_p_compra_m_change)) or 0)
                val_venta = int(clean_numeric_string(
                    p2.text_input("Precio venta unitario $", key="p_venta_m",
                                  on_change=on_p_venta_m_change)) or 0)

                st.divider()
                st.markdown("**Referencias y colores**")
                monturas_data = []
                if inv_cant == 1:
                    r1, r2 = st.columns(2)
                    monturas_data.append((r1.text_input("N° referencia *").upper(),
                                          r2.text_input("Color *").upper()))
                else:
                    base_ref = st.text_input(
                        "Referencia base",
                        help="Si escribes '123' se autocompletará 123-1, 123-2, …").upper()
                    for i in range(int(inv_cant)):
                        r1, r2 = st.columns(2)
                        monturas_data.append((
                            r1.text_input(f"Ref. {i+1} *",
                                          value=f"{base_ref}-{i+1}" if base_ref else "",
                                          key=f"ref_{i}").upper(),
                            r2.text_input(f"Color {i+1} *", key=f"col_{i}").upper()))

                if st.button("💾 Guardar montura(s)", type="primary", use_container_width=True):
                    if not inv_marca or any(not r or not c for r, c in monturas_data):
                        st.error("⚠️ Marca, referencia y color son obligatorios.")
                    else:
                        try:
                            for r, c in monturas_data:
                                db.insert_producto({
                                    "codigo": r, "categoria": "Montura", "marca": inv_marca,
                                    "descripcion": f"MONTURA {inv_mat} - COLOR {c}",
                                    "proveedor": inv_prov, "cantidad": 1,
                                    "precio_compra": val_compra, "precio_venta": val_venta,
                                    "fecha_ingreso": now_co().isoformat(),
                                })
                            toast_y_recargar(f"{inv_cant} montura(s) registrada(s).")
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")
            else:
                i1, i2 = st.columns(2)
                inv_codigo = i1.text_input("Código *", key="inv_codigo").upper()
                inv_marca  = i1.text_input("Marca *", key="inv_marca").upper()
                inv_desc   = i2.text_input("Descripción *", key="inv_desc").upper()
                inv_prov   = i2.text_input("Proveedor", key="inv_prov").upper()

                c1, c2, c3 = st.columns(3)
                inv_cant = c1.number_input("Cantidad inicial", min_value=0, step=1, value=1)
                val_compra = int(clean_numeric_string(
                    c2.text_input("Precio compra $", key="p_compra_input",
                                  on_change=on_p_compra_change)) or 0)
                val_venta = int(clean_numeric_string(
                    c3.text_input("Precio venta $", key="p_venta_input",
                                  on_change=on_p_venta_change)) or 0)

                if st.button("💾 Guardar producto", type="primary", use_container_width=True):
                    if not inv_codigo or not inv_marca or not inv_desc:
                        st.error("⚠️ Código, marca y descripción son obligatorios.")
                    else:
                        try:
                            db.insert_producto({
                                "codigo": inv_codigo, "categoria": inv_categoria,
                                "marca": inv_marca, "descripcion": inv_desc,
                                "proveedor": inv_prov, "cantidad": inv_cant,
                                "precio_compra": val_compra, "precio_venta": val_venta,
                                "fecha_ingreso": now_co().isoformat(),
                            })
                            toast_y_recargar(f"Producto '{inv_codigo}' registrado.")
                        except Exception as e:
                            st.error(f"Error: {e}")

    with tab_aju:
        codigo_ajuste = buscador("Código del producto", "cod_ajuste",
                                 placeholder="🔍 Código exacto del producto")
        if codigo_ajuste:
            prod = db.producto(codigo_ajuste)
            if not prod:
                st.error("No se encontró ningún producto con ese código.")
            else:
                stock = int(prod["cantidad"])
                with st.container(border=True):
                    d1, d2, d3 = st.columns(3)
                    d1.metric("Producto", str(prod["marca"]).upper()[:18])
                    d2.metric("Categoría", prod.get("categoria", "—"))
                    d3.metric("Stock actual", stock)
                    st.caption(prod.get("descripcion", ""))

                with st.container(border=True):
                    a1, a2, a3 = st.columns([1, 1, 2])
                    accion = a1.radio("Acción", ["Sumar (+)", "Restar (−)"])
                    cant_aj = a2.number_input("Cantidad", min_value=1, step=1, value=1)
                    nuevo_stock = stock + cant_aj if accion.startswith("Sumar") else stock - cant_aj
                    with a3:
                        st.metric("Stock resultante", max(0, nuevo_stock),
                                  delta=cant_aj if accion.startswith("Sumar") else -cant_aj)
                    if st.button("Actualizar stock", type="primary", use_container_width=True):
                        if nuevo_stock < 0:
                            st.error("⚠️ El stock no puede quedar negativo.")
                        else:
                            db.update_stock(codigo_ajuste, nuevo_stock)
                            toast_y_recargar(f"Stock actualizado a {nuevo_stock}.")


# ---------------------------------------------------------------------
# MÓDULO 5 · CONTROL DE TRABAJOS
# ---------------------------------------------------------------------
elif modulo == "Control de Trabajos":
    page_header("Control de Trabajos", "🔬", "Trazabilidad de laboratorio")

    tab_trabajos, tab_labs = st.tabs(
        ["📋 Trabajos", "⚙️ Laboratorios"])

    # ---------- Gestión de laboratorios ----------
    with tab_labs:
        with st.container(border=True):
            st.markdown("##### ➕ Agregar laboratorio externo")
            l1, l2 = st.columns([3, 1])
            nuevo_lab = l1.text_input("Nombre", label_visibility="collapsed",
                                      placeholder="Ej: OPTILAB BOGOTÁ").upper()
            if l2.button("Añadir", type="primary", use_container_width=True):
                if not nuevo_lab:
                    st.warning("Escribe el nombre del laboratorio.")
                else:
                    try:
                        db.insert_laboratorio(nuevo_lab)
                        toast_y_recargar("Laboratorio añadido.")
                    except Exception:
                        st.error("⚠️ Ese laboratorio ya existe o falta crear la tabla "
                                 "`laboratorios` en Supabase.")

        labs_db = db.laboratorios()
        if labs_db:
            st.markdown("##### 🏭 Laboratorios registrados")
            cols = st.columns(3)
            for i, l in enumerate(labs_db):
                with cols[i % 3]:
                    with st.container(border=True):
                        st.markdown(f"**🏭 {l['nombre']}**")
        else:
            st.info("Aún no has registrado laboratorios externos.")

    # ---------- Control de trabajos ----------
    with tab_trabajos:
        with st.container(border=True):
            b1, b2 = st.columns(2)
            search_fac = b1.text_input("🔍 Buscar por N° de factura").strip().upper()
            filtro_estado = b2.selectbox("Filtrar por estado",
                                         ["Todos los Activos"] + ESTADOS_LAB)

        query = supabase.table("ventas_facturacion").select("*").neq("estado", "ANULADA")
        if filtro_estado != "Todos los Activos":
            query = query.eq("estado_lab", filtro_estado)
        if search_fac:
            query = query.eq("numero_factura", search_fac)
        trabajos = query.order("fecha_venta", desc=True).execute().data or []

        opciones_labs = ["NO ASIGNADO"] + [l["nombre"] for l in db.laboratorios()]

        # Resumen por estado
        if trabajos and not search_fac and filtro_estado == "Todos los Activos":
            conteo = {e: 0 for e in ESTADOS_LAB}
            for t in trabajos:
                est = t.get("estado_lab", ESTADOS_LAB[0])
                if est in conteo:
                    conteo[est] += 1
            kcols = st.columns(len(ESTADOS_LAB))
            for col, est in zip(kcols, ESTADOS_LAB):
                col.metric(f"{ESTADO_THEME[est]['icon']} {est}", conteo[est])
            st.divider()

        if not trabajos:
            st.info("No hay trabajos que coincidan con los filtros.")
        else:
            st.caption(f"**{len(trabajos)}** trabajo(s) encontrado(s)")

            for t in trabajos:
                est_act = t.get("estado_lab", ESTADOS_LAB[0])
                tema    = ESTADO_THEME.get(est_act, ESTADO_THEME[ESTADOS_LAB[0]])
                fac_id  = t["numero_factura"]

                with st.container(border=True):
                    # Franja de color del estado (reemplaza el hack de JS de v1.0:
                    # ahora es un simple div dentro del contenedor nativo)
                    st.markdown(
                        f'<div class="bv-stripe" style="background:{tema["color"]};"></div>'
                        + pill(est_act.upper(), tema["color"], tema["bg"]),
                        unsafe_allow_html=True,
                    )

                    c1, c2, c3 = st.columns([2, 2, 2])

                    with c1:
                        st.markdown(f"### Fac N° {fac_id}")
                        st.markdown(f"**Titular:** {t['titular_nombre']}")
                        st.markdown(f"**Detalle:** {t.get('descripcion','—')}")

                    with c2:
                        entrega = str(t.get("fecha_entrega", "") or "").strip()
                        st.markdown(f"**Entrega:** {entrega or '—'}")
                        saldo = int(t.get("saldo", 0))
                        if saldo > 0:
                            st.markdown(f"**Saldo:** ${format_currency_co(saldo)}")
                        else:
                            st.markdown("**Pagado 100%** ✅")
                        st.caption(f"Emitida el {fmt_fecha(t.get('fecha_venta'))}")

                    with c3:
                        nuevo_est = st.selectbox(
                            "Estado del trabajo", ESTADOS_LAB,
                            index=ESTADOS_LAB.index(est_act) if est_act in ESTADOS_LAB else 0,
                            key=f"est_{fac_id}")

                        lab_act = t.get("laboratorio") or "NO ASIGNADO"
                        nuevo_lab = st.selectbox(
                            "Laboratorio externo", opciones_labs,
                            index=opciones_labs.index(lab_act) if lab_act in opciones_labs else 0,
                            key=f"lab_{fac_id}")

                        if nuevo_est != est_act or nuevo_lab != lab_act:
                            if st.button(f"💾 Guardar cambios", key=f"btn_est_{fac_id}",
                                         type="primary", use_container_width=True):
                                db.update_venta(fac_id, {
                                    "estado_lab": nuevo_est,
                                    "laboratorio": nuevo_lab if nuevo_lab != "NO ASIGNADO" else None,
                                })
                                toast_y_recargar(f"Trabajo actualizado a: {nuevo_est}")

                        # ---- Aviso por WhatsApp (solo si ya llegó a la óptica) ----
                        if est_act == "Recibido en Óptica":
                            cel = str(t.get("titular_tel", "") or "").strip()
                            if not cel or cel.upper() in ("NONE", "N/A", ""):
                                pac = db.paciente_por_doc(str(t.get("paciente_documento", "")))
                                cel = str(pac.get("celular", "")) if pac else ""

                            cel_norm = normalizar_celular(cel)
                            nombre_pac = str(t.get("titular_nombre", "")).split()
                            nombre_pac = nombre_pac[0].capitalize() if nombre_pac else "paciente"

                            msg = (f"Hola {nombre_pac}, te saludamos de Boomerang Vision. "
                                   f"Te informamos que tus gafas ya se encuentran listas "
                                   f"para retirar en nuestra optica. Te esperamos!")

                            if cel_norm and len(cel_norm) >= 10:
                                st.link_button(
                                    "💬 Avisar al paciente",
                                    get_whatsapp_link(cel_norm, msg),
                                    use_container_width=True,
                                )
                            else:
                                st.button("💬 Avisar al paciente", disabled=True,
                                          use_container_width=True, key=f"wa_off_{fac_id}",
                                          help="Este paciente no tiene celular registrado.")


# ---------------------------------------------------------------------
# MÓDULO 6 · CRM Y FIDELIZACIÓN
# ---------------------------------------------------------------------
elif modulo == "CRM y Fidelización":
    page_header("CRM y Fidelización", "📅", "Retención y contacto con pacientes")

    hoy = now_co()
    if hoy.day == 1:
        st.success("🔔 **Inicia un nuevo mes.** Buen momento para revisar cumpleaños "
                   "y enviar recordatorios de control anual.")

    # Plantillas persistentes
    if "tpl_anual" not in st.session_state:
        cfg = db.config_kv()
        st.session_state.tpl_anual = cfg.get(
            "tpl_anual",
            "Hola [NOMBRE], te saludamos de Boomerang Vision. Ha pasado un año desde "
            "tu ultimo examen visual y queremos invitarte a tu control anual para "
            "cuidar de tu salud visual. Te gustaria agendar una cita?")
        st.session_state.tpl_cumple = cfg.get(
            "tpl_cumple",
            "Feliz cumpleanos, [NOMBRE]! Te deseamos un dia maravilloso de parte de "
            "todo el equipo de Boomerang Vision. Queremos regalarte un descuento "
            "especial del 20% en tu proximo par de lentes o montura este mes. "
            "Te esperamos!")

    tab_anual, tab_cumple, tab_dir, tab_tpl = st.tabs(
        ["🔄 Control Anual", "🎂 Cumpleaños", "📞 Directorio", "⚙️ Plantillas"])

    # Cargamos pacientes una sola vez para las tres primeras pestañas
    todos_pacientes = db.pacientes()
    # Índice por documento: convierte la búsqueda de O(n) por paciente
    # a O(1). En v1.0 el control anual ejecutaba una consulta a Supabase
    # por cada historia clínica (patrón N+1) — con 500 historias eran
    # 500 consultas por render.
    idx_pacientes = {str(p.get("documento", "")): p for p in todos_pacientes}

    # ---------- Control anual ----------
    with tab_anual:
        historias = db.historias_resumen()

        # Última consulta por paciente
        ultima = {}
        for h in historias:
            doc = str(h.get("paciente_documento", ""))
            f = parse_fecha(h.get("fecha"))
            if doc and f and (doc not in ultima or f > ultima[doc]):
                ultima[doc] = f

        para_llamar = []
        for doc, f in ultima.items():
            dias = (hoy.date() - f.date()).days
            if 330 <= dias <= 400:
                p = idx_pacientes.get(doc)
                if p:
                    para_llamar.append({
                        "doc": doc,
                        "nombre": str(p.get("nombre_completo", "")).upper(),
                        "celular": p.get("celular", ""),
                        "ultima": f.strftime("%d/%m/%Y"),
                        "dias": dias,
                    })
        para_llamar.sort(key=lambda x: x["dias"], reverse=True)

        if not para_llamar:
            st.info("No hay pacientes cumpliendo un año desde su última consulta.")
        else:
            st.metric("Pacientes para contactar", len(para_llamar))
            st.divider()
            for item in para_llamar:
                msg = st.session_state.tpl_anual.replace(
                    "[NOMBRE]", item["nombre"].split()[0].capitalize())
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 2])
                    c1.markdown(f"**👤 {item['nombre']}**")
                    c1.caption(f"Cédula {item['doc']} · Última visita {item['ultima']}")
                    c2.markdown(f"📱 `{item['celular'] or '—'}`")
                    with c3:
                        if normalizar_celular(item["celular"]):
                            st.link_button("💬 WhatsApp",
                                           get_whatsapp_link(item["celular"], msg),
                                           use_container_width=True)
                        else:
                            st.button("💬 WhatsApp", disabled=True,
                                      use_container_width=True,
                                      key=f"wa_an_{item['doc']}",
                                      help="Sin celular registrado")

    # ---------- Cumpleaños ----------
    with tab_cumple:
        cumples = []
        for p in todos_pacientes:
            f = parse_fecha(p.get("fecha_nacimiento"))
            if f and f.month == hoy.month:
                edad = hoy.year - f.year - ((hoy.month, hoy.day) < (f.month, f.day))
                cumples.append({
                    "doc": str(p.get("documento", "")),
                    "nombre": str(p.get("nombre_completo", "")).upper(),
                    "celular": p.get("celular", ""),
                    "dia": f.day, "edad": edad,
                    "fecha": f.strftime("%d/%m"),
                })
        cumples.sort(key=lambda x: x["dia"])

        if not cumples:
            st.info("No hay pacientes con cumpleaños registrado este mes.")
        else:
            st.metric("Cumpleaños este mes", len(cumples))
            st.divider()
            for c in cumples:
                msg = st.session_state.tpl_cumple.replace(
                    "[NOMBRE]", c["nombre"].split()[0].capitalize())
                es_hoy = c["dia"] == hoy.day
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 2])
                    c1.markdown(f"**🎂 {c['nombre']}**" + ("  ·  🎉 **¡HOY!**" if es_hoy else ""))
                    c1.caption(f"Cumple {c['edad']} años el {c['fecha']} · Cédula {c['doc']}")
                    c2.markdown(f"📱 `{c['celular'] or '—'}`")
                    with c3:
                        if normalizar_celular(c["celular"]):
                            st.link_button("🎁 Felicitar",
                                           get_whatsapp_link(c["celular"], msg),
                                           use_container_width=True)
                        else:
                            st.button("🎁 Felicitar", disabled=True,
                                      use_container_width=True,
                                      key=f"wa_cu_{c['doc']}",
                                      help="Sin celular registrado")

    # ---------- Directorio ----------
    with tab_dir:
        POR_PAGINA = 50
        busqueda = st.text_input("🔍 Filtrar por nombre o cédula").strip().upper()

        filas = []
        for p in todos_pacientes:
            nombre = str(p.get("nombre_completo", "")).upper()
            doc = str(p.get("documento", ""))
            if busqueda and busqueda not in nombre and busqueda not in doc:
                continue
            filas.append({
                "Documento": doc, "Nombre": nombre,
                "Celular": p.get("celular", "—"),
                "F. Nacimiento": fmt_fecha(p.get("fecha_nacimiento")),
                "Habeas Data": "Sí" if p.get("habeas_data") else "No",
            })

        if not filas:
            st.info("No hay registros que coincidan.")
        else:
            total = len(filas)
            total_pags = max(1, (total + POR_PAGINA - 1) // POR_PAGINA)
            st.session_state.setdefault("dir_pagina", 1)
            if busqueda:
                st.session_state.dir_pagina = 1
            pag = min(st.session_state.dir_pagina, total_pags)

            st.caption(f"**{total}** pacientes · Página **{pag}** de **{total_pags}**")
            st.dataframe(
                pd.DataFrame(filas[(pag - 1) * POR_PAGINA: pag * POR_PAGINA]),
                use_container_width=True, hide_index=True,
            )

            if total_pags > 1:
                n1, n2, n3, n4 = st.columns([1, 1, 1, 1])
                if n1.button("⏮ Primera", use_container_width=True, disabled=(pag == 1)):
                    st.session_state.dir_pagina = 1; st.rerun()
                if n2.button("◀ Anterior", use_container_width=True, disabled=(pag == 1)):
                    st.session_state.dir_pagina = pag - 1; st.rerun()
                if n3.button("Siguiente ▶", use_container_width=True, disabled=(pag == total_pags)):
                    st.session_state.dir_pagina = pag + 1; st.rerun()
                if n4.button("Última ⏭", use_container_width=True, disabled=(pag == total_pags)):
                    st.session_state.dir_pagina = total_pags; st.rerun()

            st.download_button(
                "📊 Descargar directorio completo (.xlsx)",
                data=convert_df_to_excel(pd.DataFrame(filas), "Pacientes"),
                file_name="Directorio.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    # ---------- Plantillas ----------
    with tab_tpl:
        with st.container(border=True):
            st.markdown("##### ⚙️ Mensajes de WhatsApp")
            st.caption("Usa la etiqueta `[NOMBRE]` para insertar el nombre del paciente.")
            st.session_state.tpl_anual = st.text_area(
                "Plantilla de control anual", value=st.session_state.tpl_anual, height=110)
            st.session_state.tpl_cumple = st.text_area(
                "Plantilla de cumpleaños", value=st.session_state.tpl_cumple, height=110)

            if st.button("💾 Guardar plantillas", type="primary", use_container_width=True):
                ok1 = db.guardar_config("tpl_anual", st.session_state.tpl_anual)
                ok2 = db.guardar_config("tpl_cumple", st.session_state.tpl_cumple)
                if ok1 and ok2:
                    st.success("Plantillas guardadas en la base de datos.")
                else:
                    st.warning("Plantillas activas solo en esta sesión. Para que "
                               "persistan, crea la tabla `configuracion` "
                               "(columnas `clave` y `valor`) en Supabase.")


# ---------------------------------------------------------------------
# MÓDULO 7 · ANALÍTICA
# ---------------------------------------------------------------------
elif modulo == "Analítica":
    page_header("Analítica", "📈", "Indicadores del negocio y respaldo")

    ventas_db = db.ventas_activas()
    gastos_db = db.gastos()

    if not ventas_db:
        st.info("Aún no hay ventas registradas para analizar.")
    else:
        hoy_an = now_co()
        mes_actual = hoy_an.strftime("%Y-%m")
        ventas_mes = [v for v in ventas_db
                      if str(v.get("fecha_venta", "")).startswith(mes_actual)]
        total_mes     = sum(int(v.get("total", 0)) for v in ventas_mes)
        recaudado_mes = sum(int(v.get("abono", 0)) for v in ventas_mes)

        st.markdown(f"##### 📅 Mes en curso · {hoy_an.strftime('%B %Y').capitalize()}")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("🛍️ Ventas", len(ventas_mes))
        k2.metric("💰 Facturado", f"${format_currency_co(total_mes)}")
        k3.metric("✅ Recaudado", f"${format_currency_co(recaudado_mes)}")
        k4.metric("⏳ Por recaudar", f"${format_currency_co(total_mes - recaudado_mes)}")
        st.divider()

        df = pd.DataFrame(ventas_db)
        df["fecha_venta"] = pd.to_datetime(df["fecha_venta"], format="mixed", utc=True)
        df["mes_anio"] = df["fecha_venta"].dt.strftime("%Y-%m")
        cartera = int(df["saldo"].sum())

        def gastos_de(mes):
            return sum(g.get("monto", 0) for g in gastos_db
                       if (parse_fecha(g.get("fecha_gasto")) or datetime(1900, 1, 1))
                       .strftime("%Y-%m") == mes)

        modo = st.radio("Modo de visualización",
                        ["Resumen Global", "Filtrar por Mes", "Comparativa Multimes"],
                        horizontal=True)
        meses = sorted(df["mes_anio"].unique(), reverse=True)

        # ----- Filtrar por mes -----
        if modo == "Filtrar por Mes":
            mes_sel = st.selectbox("Mes a analizar", meses)
            dfm = df[df["mes_anio"] == mes_sel]
            ventas_m = int(dfm["total"].sum())
            gastos_m = gastos_de(mes_sel)
            n_fact = len(dfm)

            st.markdown(f"##### 🎯 Resumen de {mes_sel}")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("💰 Ventas", f"${format_currency_co(ventas_m)}")
            m2.metric("💸 Gastos", f"${format_currency_co(gastos_m)}",
                      delta="- Salidas", delta_color="inverse")
            m3.metric("📈 Ganancia neta", f"${format_currency_co(ventas_m - gastos_m)}")
            m4.metric("📊 Ticket promedio",
                      f"${format_currency_co(int(ventas_m / n_fact) if n_fact else 0)}")
            st.info(f"📌 Cartera pendiente por cobrar: **${format_currency_co(cartera)}**")

        # ----- Comparativa -----
        elif modo == "Comparativa Multimes":
            sel = st.multiselect("Meses a comparar", meses,
                                 default=meses[:min(3, len(meses))])
            if not sel:
                st.warning("Selecciona al menos un mes.")
            else:
                filas = []
                for m in sorted(sel):
                    dfm = df[df["mes_anio"] == m]
                    v = int(dfm["total"].sum())
                    g = gastos_de(m)
                    filas.append({"Mes": m, "Ventas Brutas": v, "Gastos": g,
                                  "Ganancia Neta": v - g, "N° Facturas": len(dfm)})
                dfc = pd.DataFrame(filas)

                st.dataframe(
                    dfc, use_container_width=True, hide_index=True,
                    column_config={
                        "Ventas Brutas": st.column_config.NumberColumn(format="$ %d"),
                        "Gastos": st.column_config.NumberColumn(format="$ %d"),
                        "Ganancia Neta": st.column_config.NumberColumn(format="$ %d"),
                    })

                melted = dfc.melt(id_vars=["Mes"],
                                  value_vars=["Ventas Brutas", "Gastos", "Ganancia Neta"],
                                  var_name="Concepto", value_name="Valor")
                st.altair_chart(
                    alt.Chart(melted).mark_bar().encode(
                        x=alt.X("Mes:N", axis=alt.Axis(labelAngle=0)),
                        y=alt.Y("Valor:Q", title="Valor ($)"),
                        color=alt.Color("Concepto:N", scale=alt.Scale(
                            domain=["Ventas Brutas", "Gastos", "Ganancia Neta"],
                            range=["#2196F3", "#FF9800", "#4CAF50"])),
                        xOffset="Concepto:N",
                        tooltip=["Mes", "Concepto", "Valor"],
                    ).properties(height=340),
                    use_container_width=True)

        # ----- Global -----
        else:
            total_v = int(df["total"].sum())
            total_g = sum(g.get("monto", 0) for g in gastos_db)
            n = len(df)

            st.markdown("##### 🎯 Histórico global")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("💰 Ventas brutas", f"${format_currency_co(total_v)}")
            m2.metric("💸 Gastos", f"${format_currency_co(total_g)}",
                      delta="- Salidas", delta_color="inverse")
            m3.metric("📈 Ganancia neta", f"${format_currency_co(total_v - total_g)}")
            m4.metric("📊 Ticket promedio",
                      f"${format_currency_co(int(total_v / n) if n else 0)}")
            st.info(f"📌 Cartera pendiente por cobrar: **${format_currency_co(cartera)}**")

            st.divider()
            g1, g2 = st.columns(2)

            with g1:
                st.markdown("**📅 Tendencia mensual de ventas**")
                serie = df.groupby("mes_anio")["total"].sum().reset_index()
                st.altair_chart(
                    alt.Chart(serie).mark_bar(color="#E57373").encode(
                        x=alt.X("mes_anio:N", title="Mes", axis=alt.Axis(labelAngle=-45)),
                        y=alt.Y("total:Q", title="Total ($)"),
                        tooltip=["mes_anio", "total"],
                    ).properties(height=280), use_container_width=True)

                if "metodo_pago" in df.columns:
                    st.markdown("**💳 Métodos de pago**")
                    mp = df["metodo_pago"].value_counts().reset_index()
                    mp.columns = ["metodo", "cantidad"]
                    st.altair_chart(
                        alt.Chart(mp).mark_arc(innerRadius=55).encode(
                            theta="cantidad:Q",
                            color=alt.Color("metodo:N", title="Método"),
                            tooltip=["metodo", "cantidad"],
                        ).properties(height=280), use_container_width=True)

            with g2:
                st.markdown("**🏭 Trabajos por laboratorio**")
                if "laboratorio" in df.columns:
                    labs = df["laboratorio"].fillna("NO ASIGNADO").value_counts().reset_index()
                    labs.columns = ["laboratorio", "trabajos"]
                    st.altair_chart(
                        alt.Chart(labs).mark_bar(color="#2196F3").encode(
                            x=alt.X("trabajos:Q", title="Trabajos"),
                            y=alt.Y("laboratorio:N", title="", sort="-x"),
                            tooltip=["laboratorio", "trabajos"],
                        ).properties(height=280), use_container_width=True)
                else:
                    st.info("Aún no has asignado trabajos a laboratorios.")

                st.markdown("**🔥 Top 5 ventas más altas**")
                top = (df[["numero_factura", "titular_nombre", "total", "fecha_venta"]]
                       .sort_values("total", ascending=False).head(5).copy())
                top["fecha_venta"] = top["fecha_venta"].dt.strftime("%d/%m/%Y")
                top.columns = ["Factura", "Titular", "Total", "Fecha"]
                st.dataframe(
                    top, use_container_width=True, hide_index=True,
                    column_config={"Total": st.column_config.NumberColumn(format="$ %d")})

        # ----- Respaldo -----
        st.divider()
        with st.container(border=True):
            st.markdown("##### 💾 Respaldo total de la base de datos")
            st.caption("Genera un Excel con todas las tablas críticas del sistema.")

            if st.button("📥 Generar respaldo", type="primary"):
                with st.spinner("Consolidando tablas…"):
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine="openpyxl") as writer:
                        for tabla, hoja in [
                            ("pacientes", "Pacientes"),
                            ("historias_clinicas", "HistoriasClinicas"),
                            ("ventas_facturacion", "VentasFacturacion"),
                            ("inventario", "Inventario"),
                            ("gastos_caja", "GastosCaja"),
                        ]:
                            try:
                                data = supabase.table(tabla).select("*").execute().data
                                if data:
                                    pd.DataFrame(data).to_excel(writer, index=False,
                                                                sheet_name=hoja)
                            except Exception:
                                pass
                    st.session_state.backup_bytes = output.getvalue()
                st.success("Respaldo generado.")

            if st.session_state.get("backup_bytes"):
                st.download_button(
                    "📥 Descargar Master Backup (.xlsx)",
                    data=st.session_state.backup_bytes,
                    file_name=f"MasterBackup_BoomerangVision_"
                              f"{now_co().strftime('%d-%m-%Y')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True)
