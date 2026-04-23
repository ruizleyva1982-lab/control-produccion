import streamlit as st
import pandas as pd
from datetime import datetime
import os, time, glob
from gsheets_helper import cargar_produccion_sheets, guardar_produccion_sheets

# ── SESSION STATE ─────────────────────────────────────────────────────────────
if "produccion_real" not in st.session_state:
    st.session_state.produccion_real = {}
if "sheets_cargado" not in st.session_state:
    st.session_state.sheets_cargado = False
if "registro_count" not in st.session_state:
    st.session_state.registro_count = 0

st.set_page_config(
    page_title="Control de Producción",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.main-header {
    background: linear-gradient(135deg, #0e7490 0%, #0891b2 50%, #06b6d4 100%);
    padding: 2rem 2.5rem; border-radius: 16px; margin-bottom: 1.5rem;
    box-shadow: 0 8px 32px rgba(0,0,0,0.15);
}
.main-header h1 { color: #fff; font-size: 2rem; font-weight: 700; margin: 0; }
.main-header p  { color: #e0f7fa; margin: 0.3rem 0 0; font-size: 0.95rem; }
.kpi-card {
    background: #e0f7fa; border: 1px solid #b2ebf2; border-radius: 12px;
    padding: 1.2rem 1.4rem; text-align: center;
    box-shadow: 0 4px 16px rgba(0,0,0,0.08);
}
.kpi-label { color: #0e7490; font-size: 0.78rem; font-weight: 500;
             text-transform: uppercase; letter-spacing: 0.06em; }
.kpi-value { font-size: 2rem; font-weight: 700; margin: 0.2rem 0 0; }
.kpi-blue   { color: #0369a1; }
.kpi-green  { color: #0e7490; }
.kpi-orange { color: #b45309; }
.kpi-red    { color: #b91c1c; }
.kpi-white  { color: #164e63; }
.section-title {
    font-size: 1.1rem; font-weight: 600; color: #c8d8e8;
    border-left: 4px solid #06b6d4; padding-left: 0.8rem;
    margin: 1.5rem 0 1rem;
}
.stDataFrame { border-radius: 10px; overflow: hidden; }
.stButton > button {
    border-radius: 8px; font-weight: 600; transition: all 0.2s;
    border: 1px solid #0891b2;
}
.stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(8,145,178,0.3); }
[data-testid="stSidebar"] { background: #f0f9ff; }
[data-testid="stSidebar"] .stMarkdown { color: #164e63; }
[data-testid="stMetricValue"] { color: #0369a1; font-size: 1.6rem !important; }
.stNumberInput input { border-radius: 8px; }
div[data-testid="stExpander"] { background:#ffffff; border:1px solid #b2ebf2; border-radius:10px; }
div[data-testid="stExpander"] p,
div[data-testid="stExpander"] label,
div[data-testid="stExpander"] span { color: #1a1a2e !important; }
</style>
""", unsafe_allow_html=True)

# ── RUTAS (relativas al repo — funciona en Streamlit Cloud y local) ───────────
BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
PRODUCTOS_FILE   = os.path.join(BASE_DIR, "maestro_productos.xlsx")
PROGRAMACION_DIR = os.path.join(BASE_DIR, "programacion")

# ── FUNCIONES ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def cargar_productos(path: str) -> pd.DataFrame:
    df = pd.read_excel(path, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    rename = {}
    for c in df.columns:
        if c in ("CÓDIGO","CODIGO"):  rename[c] = "CODIGO"
        if c in ("LÍNEA","LINEA"):    rename[c] = "LINEA"
        if c == "PRODUCTO":           rename[c] = "PRODUCTO"
    df = df.rename(columns=rename)
    return df[["CODIGO","PRODUCTO","LINEA"]].drop_duplicates(subset="CODIGO")

@st.cache_data(ttl=60)
def cargar_programacion(carpeta: str) -> pd.DataFrame:
    archivos = sorted(glob.glob(os.path.join(carpeta, "????????.xlsx")))
    if not archivos:
        return pd.DataFrame()
    frames = []
    for arch in archivos:
        nombre = os.path.basename(arch).replace(".xlsx","")
        try:
            df = pd.read_excel(arch, dtype={"Cod Item": str, "Nro Documento": str})
            df.columns = [c.strip() for c in df.columns]
            if "Fecha de Vencimiento" not in df.columns:
                df["Fecha de Vencimiento"] = pd.to_datetime(nombre, format="%Y%m%d", errors="coerce")
            else:
                df["Fecha de Vencimiento"] = pd.to_datetime(df["Fecha de Vencimiento"], errors="coerce")
                if df["Fecha de Vencimiento"].isna().all():
                    df["Fecha de Vencimiento"] = pd.to_datetime(nombre, format="%Y%m%d", errors="coerce")
            df["_archivo"] = nombre
            frames.append(df)
        except Exception:
            pass
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

def key_reg(fecha_str: str, codigo: str) -> str:
    return f"{fecha_str}||{codigo}"

def fmt_fecha(d) -> str:
    s = d.strftime("%d/%m/%Y (%A)")
    for en, es in [("Monday","Lunes"),("Tuesday","Martes"),("Wednesday","Miércoles"),
                   ("Thursday","Jueves"),("Friday","Viernes"),("Saturday","Sábado"),("Sunday","Domingo")]:
        s = s.replace(en, es)
    return s

def archivos_disponibles(carpeta: str) -> list:
    archs = sorted(glob.glob(os.path.join(carpeta, "????????.xlsx")), reverse=True)
    return [os.path.basename(a).replace(".xlsx","") for a in archs]

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Configuración")
    productos_path = PRODUCTOS_FILE
    prog_dir       = PROGRAMACION_DIR

    st.markdown("---")
    auto_refresh = st.toggle("🔄 Auto-actualizar", value=False)
    intervalo    = st.slider("Intervalo (seg)", 30, 300, 60, disabled=not auto_refresh)

    if st.button("🔃 Recargar datos ahora", use_container_width=True):
        st.cache_data.clear()
        st.session_state.produccion_real  = cargar_produccion_sheets()
        st.session_state.sheets_cargado   = True
        st.rerun()

    st.markdown("---")
    st.markdown("### 📂 Estado de archivos")
    if os.path.exists(productos_path):
        mt = datetime.fromtimestamp(os.path.getmtime(productos_path)).strftime("%d/%m/%Y %H:%M")
        st.success("✅ maestro_productos.xlsx")
        st.caption(f"Modificado: {mt}")
    else:
        st.error("❌ maestro_productos.xlsx no encontrado")

    if os.path.exists(prog_dir):
        archs = archivos_disponibles(prog_dir)
        st.success(f"✅ carpeta programacion/")
        st.caption(f"{len(archs)} archivo(s):")
        for a in archs[:8]:
            st.caption(f"• {a}")
    else:
        st.error("❌ carpeta programacion/ no encontrada")

    st.markdown("---")
    st.markdown("### ⚠️ Pendientes")
    st.page_link("pages/pateadas.py", label="Ver Pateadas 🔴", icon="⚠️",
                 help="Productos con BATCH sin declarar de días anteriores a hoy")
    st.markdown("---")
    st.markdown("### 📈 Análisis")
    st.page_link("pages/avance.py", label="Avance de Producción 📊", icon="📈",
                 help="Avance porcentual por fecha y por línea con gráficos")
    st.markdown("---")
    st.caption("🏭 **Control de Producción v5.0 Local**")

# ── AUTO REFRESH ──────────────────────────────────────────────────────────────
if auto_refresh:
    time.sleep(intervalo)
    st.cache_data.clear()
    st.rerun()

# ── HEADER ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="main-header">
  <div style="display:flex;align-items:center;gap:1.5rem;">
    <img src="data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEBLAEsAAD/4gI0SUNDX1BST0ZJTEUAAQEAAAIkYXBwbAQAAABtbnRyUkdCIFhZWiAH4QAHAAcADQAWACBhY3NwQVBQTAAAAABBUFBMAAAAAAAAAAAAAAAAAAAAAAAA9tYAAQAAAADTLWFwcGzKGpWCJX8QTTiZE9XR6hWCAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAApkZXNjAAAA/AAAAGVjcHJ0AAABZAAAACN3dHB0AAABiAAAABRyWFlaAAABnAAAABRnWFlaAAABsAAAABRiWFlaAAABxAAAABRyVFJDAAAB2AAAACBjaGFkAAAB+AAAACxiVFJDAAAB2AAAACBnVFJDAAAB2AAAACBkZXNjAAAAAAAAAAtEaXNwbGF5IFAzAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAHRleHQAAAAAQ29weXJpZ2h0IEFwcGxlIEluYy4sIDIwMTcAAFhZWiAAAAAAAADzUQABAAAAARbMWFlaIAAAAAAAAIPfAAA9v////7tYWVogAAAAAAAASr8AALE3AAAKuVhZWiAAAAAAAAAoOAAAEQsAAMi5cGFyYQAAAAAAAwAAAAJmZgAA8qcAAA1ZAAAT0AAACltzZjMyAAAAAAABDEIAAAXe///zJgAAB5MAAP2Q///7ov///aMAAAPcAADAbv/bAEMAAwICAwICAwMDAwQDAwQFCAUFBAQFCgcHBggMCgwMCwoLCw0OEhANDhEOCwsQFhARExQVFRUMDxcYFhQYEhQVFP/bAEMBAwQEBQQFCQUFCRQNCw0UFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFP/CABEIAMgAyAMBIgACEQEDEQH/xAAcAAEAAgMBAQEAAAAAAAAAAAAABwgEBQYCAQP/xAAbAQEAAgMBAQAAAAAAAAAAAAAABQYCAwQHAf/aAAwDAQACEAMQAAABtSAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB59Vt5ZayCnKPs9yPmmrP2wNsFOfnDPXJYGfNUQPuIAAAAAACt1ka3Rls4d83kB6VJ0K7vG6IzXecvE5Za3udg51y8KDLWAAAAAAArdZGt8ZbOElGMp8i7dAMjR7OvzOEMPPxOSatznYGfcfDAy1gAAAAAAEJ/nw2GcEHvn2cEHicEHicEHyZt4+kHVEgAAAAAVszdhn170yHvnrzGW4AAB3nByh0xXC2Sg2fJKp7cTNGAAAAAAjHxKLlmIuSjr8c4+dt7x28MlFnzxd3G5bOcN8eAAAAAAAAqxPdYoS/Pu11MPebW7yFZqtXjgdMWAAAAAAAAPhBsU7jUVL2mbYQ/Xw+be2FN7PSNX6sTnn4AAAAAAADSbtjsqn1dgUbakITe7YKqcqyu5ZYJGsAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAf/EACoQAAAFAgQFBQEBAAAAAAAAAAABBAUGAgMRFRdAEhMUMDEHECE0NmBQ/9oACAEBAAEFAv63EhxEOIvbEhxEOItnM/iQYjEwzK+tanVYa1yxBmeCAsEOxmn6D2jjnyYl7H4Q/S2M0/QH4eknROKVfyGxtS9avUkVKk/CH6Wxmn6A/E2S8JiCpOc8KvtH4Q/S2MyI6pAdurCWJepjXLqEBScpuU01GpO3Vgg+UP8Ak3PUK6VzUK+NQr41CvjUK+NQr41CvjUK+NQr4j7vnTf3ZBIVS5ewS682mZ4n2GyTG1sdDutt3mByN1a+2/Q5X1rBCjxP4PsMcasvMfohrrVeaW6lqQd2uAIqq9PkY0+RjT5GNPkY0+RjT5GNPkY0+RhparTOk2ShwSpKs8bxQ8oLle2kDjmbsCM6TZHAnRs2kocMvZhS3V1NY9P3DC5tJ+u5isI7KQ4eGddlzmXyWzeFmYOfkcqoGWHtFl3XMmyerl2015C5CLsyqy9iZtChS65C5CD2VaL+u//EADsRAAECBAEFDAgHAAAAAAAAAAECBAADBRESBhUhMKETFDEyQVFSYXGRweEWIjRjcqKx0SBAQ1BT8PH/2gAIAQMBAT8B/PUxhnGcZWLDovHor775fOKfSVPpsyUVYcEeivvvl84UMJI1OTPtivhP1EFYCwjnvst94bSA0W4nHgJvsv8AW8JNxeJnHOpya9sV8PiIfztxeNTzkjvtFbn7ixXbl0d/lCD6oiZxzqcwVDobRGYKh0NojMFQ6G0RmCodDaIdUp2zRuk5Nh2jULcUneACrWtwDjf7+GpKbJlJLoercf09UZQTmUyUgSSCrq5tRnd+P1TCarUVmyZhMZwqvSV3Rnh//KYn1B05TgnLuNVkw10LcnsHjCVpXe3JFTa7zdLlDg5OzV05vvVqiV1Qza72Mw474jeMp210ocDs+3jqpasCwoi9on5Rzp0pUooGkWhg9UwnbsgXh5XZj2SZC5Y0/sH/xAArEQAABAQFAgYDAAAAAAAAAAAAAQIDBBETMBIUITFRBRUgM1JigaFAUOH/2gAIAQIBAT8B/OiHqCcUpjuPt+w/EkyklSnMdy9v2C1Kz1DyvkS0mHF1CQkGE7WY/wAr5DCMTTghEYniB7hO1nOscjOscjOscjOschuJbdPCk7BIia2n88MOThqOnuIFLpKPFtYyrPpBwzBbpFCG4IZVn0hDLbZzSVrqDmzYMjIQ7lVslW311HDUHXKktNh05epotKKZSCIBCFEqYeaJ5OEw1BpaXjI/0H//xAA6EAABAgMDCAcGBgMAAAAAAAABAgMABBESITQQMUBBkqGx0RMiMHFyc8EyQlGBkZMFI1JTYGEUUPH/2gAIAQEABj8C/lueM8Z8ueM+hzFP0p4ZM8Sr+tTYr364mX63LcNO7VkN8S/lp4aE/wCFHDLOmvWl7dPnm45TDHlp4aE/4UcIMOtj2blp7iKxPS379jcYl2P3HAPlrh4C4BaqfWDDHlp4aE/4UcIMSEwPfasH5f8AcheOZlFfmbucP+YrjBhjy08NCfoCeqnMP6g9VX0htxIqWrC/T1j2VfSH3iKFxyl/wEPEJNLatX9weqr6RL+Wnh/qlWZNFmt1Vxg29sxg29sxg29sxg29sxg29sxg29sxg29sxg29sx/kFvojaKSK17Z5KXltMIUUpQg0zazCkTSnJhil2tSTB7FyVZSRNKcJDmoDnHSibe6T42zDMwoUWblU+I7Rx6TR0zTirVmtCmFO/iaBZpRLNreaQexcWOpN9IbLh4RYLAQP1lYsw1LJNqwL1fE9soh99IJrSou3RiH93KMQ/u5RiH93KMQ/u5RiH93KMQ/u5RiH93KMQ/u5QJdkqUmtqqs5OhhL8w2yo3gLVSMdL/cEBKZxhSiaABwX6O+9WqK2UeEZKi4jXDEx7yh1vFr0V9QNHF/lp7zkXO+4l0NbskxJKOf8xHr6aKxKg3Nptq7zkMoqYZDzjZcp0grazj0yS8xqQrrd2vRZl/Utd3dqyewdmL7skuomq0Do1d40OZLDanHiiylKBU1MYCY+3Eu5MSjzbaam0pF1aZEuy0s66C2LRQmorfGAmPtxMsTEs60hVFpK00Fdfp/Lv//EACkQAAIBAgMIAwEBAQAAAAAAAAERACFRMZGhEEBBYYHB8PEwcbFg0VD/2gAIAQEAAT8h/rVcGc5DOchnsIsSJyGc5DOAvcrMZaS1znGcWcZBqhno1AxzhIVcBWgCNc5zFTC8ECKAIHRuqLIwDlR6oAQWzRTzlm5o0fRAjaMfUXcYRiajHUJ0UIP4n1djgwUoLBlNFPOWbmjojF2oE/NCNCy2KozwpyGkeYuminnLNyKowBZDwzkavmARBBlENHtsIRkxFR/0mHQSMC905Gr4YIGB/B/yXASuINtPjSefdp592nn3aefdp592nn3aefdp592hABhBUMcRn8xog3cZUMSYY8zUmwIk4RguX8JV2GAJyZyRX9m5n9g0MA2HI8DkV+/IEFHliWSyK4hzg0kVO5+IKViR8IBwmOKQVQsYJuxFY50rpCXwqATiyc/mN0AAl+ke3l7eXt5e3l7eXt5e3l7eTqAkdkbmNhCGZF6zxPvALzEglbHdiUIi0dGDOp67BArTAcDeWQkbBTVutL46I+gZmEBdtgV2eaHXZgwCo3wH9brwDtdAaDXYSjgNIzexoEFYR2haL6aCYQAQWDx3MlCsK3ZHTpoAgBJAEmwnv0IaAlYhbOxYA/iPXczkMFGAOlm4r/RK9JdAGJnYLysdQPF9KewQm253gAy0f13/2gAMAwEAAgADAAAAEPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPyaC3PPPPPPPPKhXV1vPPPPPPPLrwtnvPPPPPPMMMsss9PPPPPLAogQQVt/PPPPPLLCgzzHPPPPPPPPA0tvPPPPPPPPPIc0vPPPPPPPPLgjJfPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP/xAAnEQEAAQIEBwACAwAAAAAAAAABEQAhMDFhcUFRgZGhsfAQ0SBAUP/aAAgBAwEBPxD+9wBlKJyQiJOf4Hh0hYm8pEScntRQ3VyYwkK1zCOoPpVum7aBT3UghxryX3g2zc1JyNkugHmHpQLV4nqv7URd4FeS+8EQmP3rWl+9a0v3rWl+9azDUJku7K8MC4JFkXbZks16sNzK38JG3TTeEceYvtUxK5xYgyKaxA9OOAEg8H6qca5AL6pAl+G1fQfqpnZ5hjPphAB/Ur0d6i7mUO/LzUKIlO5c7ZbmGDxCBd275WruJ95ELnF9u1RGyv2ZfjnhHFhDDkwzDvQ6Q0hZJI51BAoSHK+1GaELiyIyJ/gf/8QAKREAAQIDBwQCAwAAAAAAAAAAAQARITFxMEFRYbHR8IGRweEg8UBQof/aAAgBAgEBPxD85lvjTbGuC5/RBNgItD+rj9ETBsZNGhQMndBA7vsij5gN1cjQBAxIUmljLo0KYt4APZyo1kI9vbIS5SaWLHqdlyg7LlB2XKDso1RobB/LneZeDRsviAjZh4M8EXxIZe8+vWwySAuABOS7ntZZMjg2UcVT48plJvin2nI1HHs8HiYUEAmQwsaqZLqND4snMCzoADLEG65Pva9DRbin6D//xAAnEAEAAQIEBQUBAQAAAAAAAAABEQAhMUFRYRAwQIGRcaGx8PHBYP/aAAgBAQABPxD/AFqxEExEV+ar8VwRQSZKV+ar81QAREczosSJSFEsL+xX76kCAqRIrVLo6KAoGMLC4IkVP31bwWbRomwWGAdFfXaOM3pCjGH78dqgpTAE8Pevh6Ol9dopKjESeKP2cAgAgeiHaoXUdMPnMFDUozCYRV2K7UB0BcAIdgK96+Ho6X12ivttGo7wwGXL3eAHNZZkT/1O3CP718PR0nsYgEkhIblb1Phdqv4NzISKNg9q+g/yrzlsqAGOVEXGggRccK3pPC7U50pjqdJYdJNMBdKxojlwgsjMGXJTp06dOnTp8GYX9biDCDE1qeZlRXvhiJMQoFuwSBugfwU3AMruIrFkzG1sTQ0lXkjygTXAFmEgES85QnDGectwhskUMiloKW0DEDKYy5k72Eo0BhIURkGEtKKaSl00XqCDALdVwBMfASdBTkla7zkYmYvMoSKN4ir2czw3JRsSpDyrgUh5SmDIg5qSRRbtBAVYKlCc78l06dOnTp06NrBXAZWADAADKo6K+vmWUQEKSRPDAw7TdWABcrBHTAioBiuVOxXWwEUPVT8Up0i2JMg3EGgMkEsZVjKxTZOlaNxcxJUN/DUAALBYreSSUrntwVLT5zJBPU8D0t/RAHXF3Gam+FCNzFQAjIDqCIpQGIkmNKLD3EWvzO1CmEIGRNejBFABdcqlLndcFjqG1JgCV9Cvp38paU4qXhqBEbjZpJ/l85Iru9GiwnXgIg3EtqAAQhB+NR6Th9KYWu2dYqKClucFBAxxu1fZf5TXtgKMYkSyby06SKjjH+W//9k="
         style="height:80px;width:80px;object-fit:contain;border-radius:10px;background:#fff;padding:6px;">
    <div>
      <h1 style="font-size:2.6rem;margin:0;">Control de Producción</h1>
      <p style="margin:0.3rem 0 0;">Seguimiento en tiempo real · Versión Local · Multi-archivo por día</p>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── VALIDAR ARCHIVOS ──────────────────────────────────────────────────────────
errores = []
if not os.path.exists(productos_path):
    errores.append(f"❌ No se encuentra `maestro_productos.xlsx` en: `{base_dir}`")
if not os.path.exists(prog_dir):
    errores.append(f"❌ No se encuentra la carpeta `programacion/` en: `{base_dir}`")
elif not archivos_disponibles(prog_dir):
    errores.append("❌ La carpeta `programacion/` está vacía.")
if errores:
    for e in errores:
        st.error(e)
    st.stop()

try:
    df_productos    = cargar_productos(productos_path)
    df_programacion = cargar_programacion(prog_dir)
except Exception as e:
    st.error(f"❌ Error al leer archivos: {e}")
    st.stop()

if df_programacion.empty:
    st.warning("⚠️ No se pudo leer ningún archivo de programación.")
    st.stop()

# Cargar produccion_real solo la primera vez
if not st.session_state.sheets_cargado:
    st.session_state.produccion_real = cargar_produccion_sheets()
    st.session_state.sheets_cargado  = True

produccion_real = st.session_state.produccion_real

# ── FILTROS ───────────────────────────────────────────────────────────────────
fechas_disponibles = sorted(
    df_programacion["Fecha de Vencimiento"].dropna().dt.date.unique(), reverse=True
)

col_f, col_l = st.columns([2, 2])
with col_f:
    fecha_sel = st.selectbox("📅 Fecha de Programación", options=fechas_disponibles,
                             format_func=fmt_fecha, index=0)
with col_l:
    lineas_disponibles = sorted(df_productos["LINEA"].dropna().unique().tolist())
    linea_sel = st.selectbox("🏭 Línea de Producción", ["— Todas las líneas —"] + lineas_disponibles)

fecha_str = fecha_sel.strftime("%Y-%m-%d")
buscar    = st.text_input("🔍 Buscar producto", placeholder="Código o nombre...")

# ── CRUCE DE DATOS ────────────────────────────────────────────────────────────
prog_fecha    = df_programacion[df_programacion["Fecha de Vencimiento"].dt.date == fecha_sel]
prog_filtrado = prog_fecha[prog_fecha["Cod Item"].isin(df_productos["CODIGO"])]

resumen_prog = prog_filtrado.groupby("Cod Item").agg(
    BATCH_PLAN=("Nro Documento", "count"),
    CANT_PLAN=("Cantidad Planificada", "sum")
).reset_index()

df_base = df_productos[["CODIGO","PRODUCTO","LINEA"]].copy()
if linea_sel != "— Todas las líneas —":
    df_base = df_base[df_base["LINEA"] == linea_sel]
df_base = df_base.merge(resumen_prog, left_on="CODIGO", right_on="Cod Item", how="left")
df_base["BATCH_PLAN"] = df_base["BATCH_PLAN"].fillna(0).astype(int)
df_base["CANT_PLAN"]  = pd.to_numeric(df_base["CANT_PLAN"], errors="coerce").fillna(0).round(2)
df_base = df_base.reset_index(drop=True)

if buscar.strip():
    mask = (df_base["CODIGO"].str.contains(buscar, case=False, na=False) |
            df_base["PRODUCTO"].str.contains(buscar, case=False, na=False))
    df_base = df_base[mask].reset_index(drop=True)

# ── KPIs ──────────────────────────────────────────────────────────────────────
total_prods   = len(df_base)
con_prog      = int((df_base["BATCH_PLAN"] > 0).sum())
total_batch   = int(df_base["BATCH_PLAN"].sum())
total_cant    = float(df_base["CANT_PLAN"].sum())
dias_cargados = int(df_programacion["Fecha de Vencimiento"].dropna().dt.date.nunique())

batch_prod_total = 0
cant_prod_total  = 0.0
for _, row in df_base.iterrows():
    k = key_reg(fecha_str, row["CODIGO"])
    if k in produccion_real:
        batch_prod_total += produccion_real[k].get("batch_real", 0)
        cant_prod_total  += produccion_real[k].get("cant_real", 0.0)

pct_batch = (batch_prod_total / total_batch * 100) if total_batch > 0 else 0

c1, c2, c3, c4, c5, c6 = st.columns(6)
for col, lbl, val, cls in [
    (c1, "📅 Días Cargados",     str(dias_cargados),                        "kpi-white"),
    (c2, "✅ Con Programación",  str(con_prog),                             "kpi-blue"),
    (c3, "🔢 BATCH Plan",        str(total_batch),                          "kpi-blue"),
    (c4, "⚖️ Cantidad Plan",    f"{total_cant:,.1f}",                      "kpi-blue"),
    (c5, "🟢 BATCH Producido",   f"{batch_prod_total} ({pct_batch:.0f}%)",  "kpi-green"),
    (c6, "📊 Cant. Producida",   f"{cant_prod_total:,.1f}",                 "kpi-green"),
]:
    with col:
        st.markdown(f'<div class="kpi-card"><div class="kpi-label">{lbl}</div>'
                    f'<div class="kpi-value {cls}">{val}</div></div>', unsafe_allow_html=True)

st.markdown("")

if total_batch > 0:
    color = "#0e7490" if pct_batch >= 80 else "#b45309" if pct_batch >= 40 else "#b91c1c"
    st.markdown(f"""
    <div style="background:#e0f7fa;border:1px solid #b2ebf2;border-radius:10px;
                padding:1rem 1.2rem;margin-bottom:1rem;">
      <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
        <span style="color:#164e63;font-weight:600;font-size:0.9rem;">
          📈 Avance del día — {fecha_sel.strftime('%d/%m/%Y')}</span>
        <span style="color:{color};font-weight:700;">{pct_batch:.1f}% completado</span>
      </div>
      <div style="background:#b2ebf2;border-radius:6px;height:14px;overflow:hidden;">
        <div style="width:{min(pct_batch,100):.1f}%;height:100%;background:{color};border-radius:6px;"></div>
      </div>
      <div style="display:flex;justify-content:space-between;margin-top:5px;font-size:0.78rem;color:#0e7490;">
        <span>BATCH: {batch_prod_total} producidos / {total_batch} planificados</span>
        <span>Pendiente: {total_batch - batch_prod_total} BATCH · {max(total_cant - cant_prod_total,0):,.1f} unid.</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ── TABS ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "📋 Tablero de Control",
    "✍️ Registro de Producción",
    "📊 Resumen por Línea",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — TABLERO
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown('<div class="section-title">Detalle de Productos — Estado de Producción</div>',
                unsafe_allow_html=True)
    filas = []
    for _, row in df_base.iterrows():
        k    = key_reg(fecha_str, row["CODIGO"])
        real = produccion_real.get(k, {})
        bp, cp = int(row["BATCH_PLAN"]), float(row["CANT_PLAN"])
        br = real.get("batch_real", 0)
        cr = real.get("cant_real", 0.0)
        pend_b = max(bp - br, 0)
        pend_c = max(cp - cr, 0)
        pct    = round(br / bp * 100, 1) if bp > 0 else 0.0
        if bp == 0:       estado = "Sin programación"
        elif br == 0:     estado = "Pendiente"
        elif pend_b == 0: estado = "Completado"
        else:             estado = "En proceso"
        filas.append({
            "CÓDIGO": row["CODIGO"], "PRODUCTO": row["PRODUCTO"], "LÍNEA": row["LINEA"],
            "BATCH Plan": bp, "Cant. Plan": round(cp,2),
            "BATCH Real": br, "Cant. Real": round(cr,2),
            "BATCH Pend.": pend_b, "Cant. Pend.": round(pend_c,2),
            "Avance %": pct, "Estado": estado,
        })
    df_tabla = pd.DataFrame(filas)

    estados_fil = st.multiselect(
        "Filtrar por estado:",
        ["Sin programación","Pendiente","En proceso","Completado"],
        default=["Pendiente","En proceso","Completado"],
    )
    if estados_fil:
        df_tabla = df_tabla[df_tabla["Estado"].isin(estados_fil)]

    def color_estado(val):
        return {"Completado":"background-color:#0d2a1a;color:#4ecf8c;font-weight:600",
                "En proceso":"background-color:#2a1f0a;color:#ffaa44;font-weight:600",
                "Pendiente":"background-color:#2a1010;color:#ff8080;font-weight:600",
                "Sin programación":"background-color:#12192a;color:#5a7090"}.get(val,"")

    def color_avance(val):
        if val >= 100: return "color:#0e7490;font-weight:700"
        if val >= 50:  return "color:#b45309;font-weight:600"
        if val > 0:    return "color:#b45309"
        return "color:#5a7090"

    st.dataframe(
        df_tabla.style.map(color_estado, subset=["Estado"]).map(color_avance, subset=["Avance %"])
        .format({"Cant. Plan":"{:,.2f}","Cant. Real":"{:,.2f}","Cant. Pend.":"{:,.2f}","Avance %":"{:.1f}%"})
        .hide(axis="index"),
        use_container_width=True, height=520
    )
    csv = df_tabla.to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ Exportar CSV", csv, f"produccion_{fecha_str}.csv", "text/csv")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — REGISTRO DE PRODUCCIÓN
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown('<div class="section-title">Ingreso de Producción Real por Operario</div>',
                unsafe_allow_html=True)
    df_con_prog = df_base[df_base["BATCH_PLAN"] > 0].copy().reset_index(drop=True)

    if df_con_prog.empty:
        st.info(f"ℹ️ No hay productos programados para el {fecha_sel.strftime('%d/%m/%Y')}.")
    else:
        subtitulo = f"**{len(df_con_prog)}** productos para el **{fecha_sel.strftime('%d/%m/%Y')}**"
        if linea_sel != "— Todas las líneas —":
            subtitulo += f" — Línea: **{linea_sel}**"
        st.markdown(subtitulo)
        st.markdown("")

        for pos, (_, row) in enumerate(df_con_prog.iterrows()):
            k    = key_reg(fecha_str, row["CODIGO"])
            ukey = f"{k}||{pos}"
            real = produccion_real.get(k, {"batch_real": 0, "cant_real": 0.0})
            bp, cp = int(row["BATCH_PLAN"]), float(row["CANT_PLAN"])
            br = real.get("batch_real", 0)
            cr = real.get("cant_real", 0.0)
            pend_b = max(bp - br, 0)
            pend_c = max(cp - cr, 0)
            pct    = (br / bp * 100) if bp > 0 else 0

            if br == 0:       hcolor, estado_txt = "#b91c1c", "🔴 Pendiente"
            elif pend_b == 0: hcolor, estado_txt = "#0e7490", "🟢 Completado"
            else:             hcolor, estado_txt = "#b45309", "🟡 En proceso"

            titulo = (f"{row['CODIGO']}  —  {row['PRODUCTO'][:60]}"
                      f"{'...' if len(row['PRODUCTO'])>60 else ''}   {estado_txt}")

            with st.expander(titulo, expanded=(br > 0 and pend_b > 0)):
                st.markdown(f"""
                <div style="background:#f0f9ff;border-radius:8px;padding:0.6rem 1rem;
                            margin-bottom:0.8rem;border-left:3px solid {hcolor};">
                  <span style="color:#555;font-size:0.82rem;">LÍNEA: </span>
                  <span style="color:#1a1a2e;font-size:0.85rem;font-weight:600;">{row['LINEA']}</span>
                  &nbsp;&nbsp;&nbsp;
                  <span style="color:#555;font-size:0.82rem;">AVANCE: </span>
                  <span style="color:{hcolor};font-size:0.85rem;font-weight:700;">{pct:.0f}%</span>
                  &nbsp;&nbsp;&nbsp;
                  <span style="color:#555;font-size:0.82rem;">BATCH PLAN: </span>
                  <span style="color:#1a1a2e;font-size:0.85rem;font-weight:600;">{bp}</span>
                  &nbsp;&nbsp;&nbsp;
                  <span style="color:#555;font-size:0.82rem;">CANT. PLAN: </span>
                  <span style="color:#1a1a2e;font-size:0.85rem;font-weight:600;">{cp:,.2f}</span>
                </div>
                """, unsafe_allow_html=True)

                mc1, mc2, mc3, mc4 = st.columns(4)
                mc1.metric("✅ BATCH Producido", br, delta=f"-{pend_b} pend." if pend_b > 0 else "✓ OK")
                mc2.metric("📦 Cant. Producida", f"{cr:,.2f}", delta=f"-{pend_c:,.2f} pend." if pend_c > 0 else "✓ OK")
                mc3.metric("⏳ BATCH Pendiente", pend_b)
                mc4.metric("⏳ Cant. Pendiente", f"{pend_c:,.2f}")

                # Si ya está completo, bloquear ingreso
                if pend_b == 0:
                    st.success(f"✅ Completado — {br} de {bp} BATCH producidos. No hay pendientes.")
                else:
                    st.markdown(f"**Ingresa los BATCH que produces ahora** (pendiente: {pend_b} BATCH · {pend_c:,.2f} unid.)")
                    ci1, ci2, ci3 = st.columns([2, 2, 1])
                    with ci1:
                        nuevo_batch = st.number_input(
                            "BATCH a registrar ahora",
                            min_value=0, max_value=pend_b,
                            value=0, step=1,
                            key=f"batch_{ukey}"
                        )
                    with ci2:
                        nueva_cant = st.number_input(
                            "Cantidad a registrar ahora",
                            min_value=0.0, max_value=float(pend_c) if pend_c > 0 else float(cp),
                            value=0.0, step=0.5, format="%.2f",
                            key=f"cant_{ukey}"
                        )
                    with ci3:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("💾 Registrar", key=f"save_{ukey}_{st.session_state.registro_count}", use_container_width=True):
                            if nuevo_batch == 0:
                                st.warning("⚠️ Ingresa al menos 1 BATCH")
                            else:
                                # ACUMULAR: sumar al total ya producido
                                batch_acum = br + nuevo_batch
                                cant_acum  = cr + nueva_cant
                                datos = {
                                    "batch_real": batch_acum,
                                    "cant_real":  cant_acum,
                                    "timestamp":  datetime.now().isoformat(),
                                    "codigo":     row["CODIGO"],
                                    "producto":   row["PRODUCTO"],
                                    "fecha":      fecha_str
                                }
                                with st.spinner("Guardando..."):
                                    guardar_produccion_sheets(st.session_state.produccion_real, k, datos)
                                st.session_state.registro_count += 1
                                pend_nuevo = max(bp - batch_acum, 0)
                                if pend_nuevo == 0:
                                    st.success(f"✅ ¡Completado! {batch_acum} de {bp} BATCH producidos.")
                                else:
                                    st.success(f"✅ Registrado — Total: {batch_acum}/{bp} BATCH · Pendiente: {pend_nuevo} BATCH")
                                time.sleep(0.5)
                                st.rerun()



# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — RESUMEN POR LÍNEA
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown('<div class="section-title">Resumen Consolidado por Línea de Producción</div>',
                unsafe_allow_html=True)
    df_todos = df_productos[["CODIGO","PRODUCTO","LINEA"]].copy()
    df_todos = df_todos.merge(resumen_prog, left_on="CODIGO", right_on="Cod Item", how="left")
    df_todos["BATCH_PLAN"] = df_todos["BATCH_PLAN"].fillna(0).astype(int)
    df_todos["CANT_PLAN"]  = pd.to_numeric(df_todos["CANT_PLAN"], errors="coerce").fillna(0).round(2)

    resumen_linea = []
    for linea in sorted(df_todos["LINEA"].dropna().unique()):
        sub  = df_todos[df_todos["LINEA"] == linea]
        bp_l = int(sub["BATCH_PLAN"].sum())
        cp_l = float(sub["CANT_PLAN"].sum())
        br_l = sum(produccion_real.get(key_reg(fecha_str, r["CODIGO"]),{}).get("batch_real",0) for _,r in sub.iterrows())
        cr_l = sum(produccion_real.get(key_reg(fecha_str, r["CODIGO"]),{}).get("cant_real",0.0) for _,r in sub.iterrows())
        resumen_linea.append({
            "Línea": linea, "Productos": len(sub), "Con Prog.": int((sub["BATCH_PLAN"]>0).sum()),
            "BATCH Plan": bp_l, "BATCH Real": br_l, "BATCH Pend.": max(bp_l-br_l,0),
            "Avance % (BATCH)": round(br_l/bp_l*100,1) if bp_l>0 else 0.0,
            "Cant. Plan": round(cp_l,2), "Cant. Real": round(cr_l,2),
            "Variación Cant.": round(cr_l-cp_l,2),
        })

    df_lineas = pd.DataFrame(resumen_linea)

    def bg_avance(val):
        if val >= 100: return "background-color:#dcfce7;color:#166534;font-weight:700"
        if val >= 50:  return "background-color:#fef9c3;color:#854d0e;font-weight:600"
        if val > 0:    return "background-color:#ffedd5;color:#9a3412;font-weight:600"
        return "color:#5a7090"

    st.markdown('<div class="section-title">📊 Avance por BATCH — Métrica principal</div>', unsafe_allow_html=True)
    cols_b = ["Línea","Productos","Con Prog.","BATCH Plan","BATCH Real","BATCH Pend.","Avance % (BATCH)"]
    st.dataframe(
        df_lineas[cols_b].style.map(bg_avance, subset=["Avance % (BATCH)"])
        .format({"Avance % (BATCH)":"{:.1f}%"}).hide(axis="index"),
        use_container_width=True, height=460
    )

    df_g = df_lineas[df_lineas["BATCH Plan"]>0].set_index("Línea")[["BATCH Plan","BATCH Real"]]
    if not df_g.empty:
        st.markdown('<div class="section-title">BATCH Plan vs Real por Línea</div>', unsafe_allow_html=True)
        st.bar_chart(df_g, use_container_width=True, height=300)

    st.markdown('<div class="section-title">🔬 Análisis de Cantidades — Referencial</div>', unsafe_allow_html=True)

    def color_var(val):
        if val > 0: return "color:#0e7490;font-weight:600"
        if val < 0: return "color:#b91c1c;font-weight:600"
        return "color:#7a92a8"

    cols_c = ["Línea","Cant. Plan","Cant. Real","Variación Cant."]
    st.dataframe(
        df_lineas[cols_c].style.map(color_var, subset=["Variación Cant."])
        .format({"Cant. Plan":"{:,.2f}","Cant. Real":"{:,.2f}","Variación Cant.":"{:+,.2f}"})
        .hide(axis="index"),
        use_container_width=True, height=460
    )




# ── FOOTER ────────────────────────────────────────────────────────────────────
st.markdown("---")
n_dias = int(df_programacion["_archivo"].nunique()) if not df_programacion.empty else 0
st.markdown(
    f'<p style="text-align:center;color:#0891b2;font-size:0.78rem;">'
    f'🏭 Control de Producción v5.0 · {n_dias} día(s) cargado(s) · '
    f'Datos en <code>Google Sheets</code></p>',
    unsafe_allow_html=True
)
