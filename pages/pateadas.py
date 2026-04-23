import streamlit as st
import pandas as pd
from datetime import datetime, date
import json, os, glob, time

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Pateadas — Pendientes Históricos",
    page_icon="⚠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── CSS (mismo estilo que app principal) ──────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.main-header {
    background: linear-gradient(135deg, #7f1d1d 0%, #b91c1c 50%, #dc2626 100%);
    padding: 1.6rem 2.5rem; border-radius: 16px; margin-bottom: 1.5rem;
    box-shadow: 0 8px 32px rgba(0,0,0,0.18);
}
.main-header h1 { color: #fff; font-size: 2rem; font-weight: 700; margin: 0; }
.main-header p  { color: #fecaca; margin: 0.3rem 0 0; font-size: 0.95rem; }
.kpi-card {
    background: #fff5f5; border: 1px solid #fecaca; border-radius: 12px;
    padding: 1.1rem 1.2rem; text-align: center;
    box-shadow: 0 4px 16px rgba(0,0,0,0.07);
}
.kpi-label { color: #991b1b; font-size: 0.76rem; font-weight: 500;
             text-transform: uppercase; letter-spacing: 0.06em; }
.kpi-value { font-size: 1.9rem; font-weight: 700; margin: 0.2rem 0 0; }
.kpi-red    { color: #b91c1c; }
.kpi-orange { color: #b45309; }
.kpi-green  { color: #0e7490; }
.section-title {
    font-size: 1.05rem; font-weight: 600; color: #c8d8e8;
    border-left: 4px solid #dc2626; padding-left: 0.8rem;
    margin: 1.5rem 0 1rem;
}
.prod-card {
    background: #fff5f5; border: 1px solid #fecaca; border-radius: 10px;
    padding: 0.75rem 1.1rem; margin-bottom: 0.6rem;
    border-left: 4px solid #b91c1c;
}
.prod-card-done {
    background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 10px;
    padding: 0.75rem 1.1rem; margin-bottom: 0.6rem;
    border-left: 4px solid #16a34a; opacity: 0.6;
}
.badge-fifo {
    background: #b91c1c; color: #fff; font-size: 0.70rem;
    padding: 2px 10px; border-radius: 12px; font-weight: 700;
}
.badge-queue {
    background: #e0f7fa; color: #0e7490; font-size: 0.70rem;
    padding: 2px 10px; border-radius: 12px;
}
.stButton > button {
    border-radius: 8px; font-weight: 600; transition: all 0.2s;
    border: 1px solid #b91c1c;
}
[data-testid="stSidebar"] { background: #fff5f5; }
[data-testid="stMetricValue"] { color: #b91c1c; font-size: 1.5rem !important; }
div[data-testid="stExpander"] { background:#ffffff; border:1px solid #fecaca; border-radius:10px; }
div[data-testid="stExpander"] p,
div[data-testid="stExpander"] label,
div[data-testid="stExpander"] span { color: #1a1a2e !important; }
</style>
""", unsafe_allow_html=True)

# ── SESSION STATE ─────────────────────────────────────────────────────────────
if "produccion_real_p" not in st.session_state:
    st.session_state.produccion_real_p = {}
if "pateadas_loaded" not in st.session_state:
    st.session_state.pateadas_loaded = False
if "reg_count_p" not in st.session_state:
    st.session_state.reg_count_p = 0

# ── RUTAS (relativas al repo — funciona en Streamlit Cloud y local) ───────────
_ROOT            = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR         = _ROOT
PRODUCTOS_FILE   = os.path.join(_ROOT, "maestro_productos.xlsx")
PROGRAMACION_DIR = os.path.join(_ROOT, "programacion")
PRODUCCION_FILE  = os.path.join(_ROOT, "produccion_real.json")

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Configuración")
    productos_path = PRODUCTOS_FILE
    prog_dir       = PROGRAMACION_DIR
    prod_file      = PRODUCCION_FILE

    st.markdown("---")
    if st.button("🔃 Recargar datos", use_container_width=True):
        st.session_state.pateadas_loaded = False
        st.rerun()

    st.markdown("---")
    st.page_link("app.py", label="← Volver al Control de Producción", icon="🏭")
    st.markdown("---")
    st.caption("⚠️ **Pateadas — Pendientes Históricos**")

# ── FUNCIONES ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def cargar_productos_p(path: str) -> pd.DataFrame:
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
def cargar_programacion_p(carpeta: str) -> pd.DataFrame:
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

def cargar_produccion_p(path: str) -> dict:
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}

def guardar_produccion_p(prod_file: str, key: str, datos: dict):
    st.session_state.produccion_real_p[key] = datos
    try:
        os.makedirs(os.path.dirname(prod_file), exist_ok=True)
        with open(prod_file, "w") as f:
            json.dump(st.session_state.produccion_real_p, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.warning(f"⚠️ Error guardando: {e}")

def key_reg(fecha_str: str, codigo: str) -> str:
    return f"{fecha_str}||{codigo}"

# ── VALIDAR Y CARGAR ARCHIVOS ─────────────────────────────────────────────────
errores = []
if not os.path.exists(productos_path):
    errores.append(f"❌ No se encuentra `maestro_productos.xlsx` en: `{BASE_DIR}`")
if not os.path.exists(prog_dir):
    errores.append(f"❌ No se encuentra la carpeta `programacion/` en: `{BASE_DIR}`")

if errores:
    for e in errores:
        st.error(e)
    st.stop()

try:
    df_productos    = cargar_productos_p(productos_path)
    df_programacion = cargar_programacion_p(prog_dir)
except Exception as e:
    st.error(f"❌ Error al leer archivos: {e}")
    st.stop()

if df_programacion.empty:
    st.warning("⚠️ No se pudo leer ningún archivo de programación.")
    st.stop()

if not st.session_state.pateadas_loaded:
    st.session_state.produccion_real_p = cargar_produccion_p(prod_file)
    st.session_state.pateadas_loaded   = True

produccion_real = st.session_state.produccion_real_p
hoy = date.today()

# ── CONSTRUIR RESUMEN HISTÓRICO (solo fechas < hoy) ───────────────────────────
df_hist = df_programacion[df_programacion["Cod Item"].isin(df_productos["CODIGO"])].copy()
df_hist = df_hist.merge(df_productos[["CODIGO","PRODUCTO","LINEA"]],
                        left_on="Cod Item", right_on="CODIGO", how="left")

# Normalizar a date puro, eliminando hora si la hubiera
df_hist["fecha_date"] = pd.to_datetime(df_hist["Fecha de Vencimiento"], errors="coerce").dt.date
df_hist["fecha_str"]  = pd.to_datetime(df_hist["Fecha de Vencimiento"], errors="coerce").dt.strftime("%Y-%m-%d")

# Eliminar filas sin fecha válida
df_hist = df_hist[df_hist["fecha_date"].notna()]

# ─ SOLO fechas ESTRICTAMENTE ANTERIORES a hoy (ayer hacia atrás) ─────────────
df_hist = df_hist[df_hist["fecha_date"] < hoy]

resumen = df_hist.groupby(["CODIGO","PRODUCTO","LINEA","fecha_str"]).agg(
    BATCH_PLAN=("Nro Documento","count"),
    CANT_PLAN=("Cantidad Planificada","sum")
).reset_index().sort_values(["CODIGO","fecha_str"])

resumen["CANT_PLAN"] = pd.to_numeric(resumen["CANT_PLAN"], errors="coerce").fillna(0)

def get_real(codigo, fecha):
    r = produccion_real.get(key_reg(fecha, codigo), {})
    return r.get("batch_real", 0), r.get("cant_real", 0.0)

resumen[["BATCH_REAL","CANT_REAL"]] = resumen.apply(
    lambda r: pd.Series(get_real(r["CODIGO"], r["fecha_str"])), axis=1)
resumen["BATCH_PEND"] = (resumen["BATCH_PLAN"] - resumen["BATCH_REAL"]).clip(lower=0).astype(int)
resumen["CANT_PEND"]  = (resumen["CANT_PLAN"]  - resumen["CANT_REAL"]).clip(lower=0).round(2)

# Solo los que tienen batch pendiente
pateadas = resumen[resumen["BATCH_PEND"] > 0].copy()

# ── HEADER ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="main-header">
  <div style="display:flex;align-items:center;gap:1.2rem;">
    <span style="font-size:3rem;">⚠️</span>
    <div>
      <h1 style="font-size:2.2rem;margin:0;">Pateadas — Pendientes Históricos</h1>
      <p style="margin:0.3rem 0 0;">
        Solo fechas anteriores a hoy ({hoy.strftime('%d/%m/%Y')}) · Orden FIFO
      </p>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── KPIs GENERALES ────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
for col, lbl, val, cls in [
    (k1, "🔴 Productos con Pateadas", str(pateadas["CODIGO"].nunique()),               "kpi-red"),
    (k2, "📅 Fechas Afectadas",       str(pateadas["fecha_str"].nunique()),             "kpi-orange"),
    (k3, "🔢 BATCH Pendientes Total", str(int(pateadas["BATCH_PEND"].sum())),           "kpi-orange"),
    (k4, "⚖️ Cant. Pendiente Total", f"{float(pateadas['CANT_PEND'].sum()):,.1f}",    "kpi-orange"),
]:
    with col:
        st.markdown(f'<div class="kpi-card"><div class="kpi-label">{lbl}</div>'
                    f'<div class="kpi-value {cls}">{val}</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

if pateadas.empty:
    st.success("🎉 ¡Sin pateadas! Todos los BATCH de fechas anteriores están declarados.")
    st.stop()

# ── FILTRO POR LÍNEA ──────────────────────────────────────────────────────────
st.markdown('<div class="section-title">🏭 Selecciona una Línea de Producción</div>',
            unsafe_allow_html=True)

lineas_con_pateadas = sorted(pateadas["LINEA"].dropna().unique().tolist())

col_lin, col_info = st.columns([2, 2])
with col_lin:
    linea_sel = st.selectbox(
        "Línea",
        options=["— Selecciona una línea —"] + lineas_con_pateadas,
        key="linea_pateadas"
    )

if linea_sel == "— Selecciona una línea —":
    # Mostrar resumen por línea mientras no se haya elegido
    st.markdown('<div class="section-title">📊 Resumen de Pateadas por Línea</div>',
                unsafe_allow_html=True)
    rows_lin = []
    for ln in lineas_con_pateadas:
        sub = pateadas[pateadas["LINEA"] == ln]
        rows_lin.append({
            "Línea": ln,
            "Productos": sub["CODIGO"].nunique(),
            "Fechas afectadas": sub["fecha_str"].nunique(),
            "BATCH Pendientes": int(sub["BATCH_PEND"].sum()),
            "Cant. Pendiente": round(float(sub["CANT_PEND"].sum()), 2),
        })
    df_lin = pd.DataFrame(rows_lin)
    st.dataframe(
        df_lin.style
        .format({"Cant. Pendiente": "{:,.2f}"})
        .hide(axis="index"),
        use_container_width=True, height=400
    )
    st.info("👆 Selecciona una línea arriba para ver el detalle de productos y declarar producción.")
    st.stop()

# ── DETALLE POR LÍNEA SELECCIONADA ────────────────────────────────────────────
pateadas_linea = pateadas[pateadas["LINEA"] == linea_sel].copy()

with col_info:
    n_prods  = pateadas_linea["CODIGO"].nunique()
    n_fechas = pateadas_linea["fecha_str"].nunique()
    n_batch  = int(pateadas_linea["BATCH_PEND"].sum())
    st.markdown(f"""
    <div style="background:#fff5f5;border:1px solid #fecaca;border-radius:10px;
                padding:0.9rem 1.2rem;margin-top:1.6rem;">
      <span style="color:#991b1b;font-size:0.82rem;font-weight:500;">LÍNEA: </span>
      <span style="color:#1a1a2e;font-weight:700;">{linea_sel}</span>
      &nbsp;&nbsp;
      <span style="color:#991b1b;font-size:0.82rem;">Productos: </span>
      <span style="color:#b91c1c;font-weight:700;">{n_prods}</span>
      &nbsp;&nbsp;
      <span style="color:#991b1b;font-size:0.82rem;">Fechas: </span>
      <span style="color:#b91c1c;font-weight:700;">{n_fechas}</span>
      &nbsp;&nbsp;
      <span style="color:#991b1b;font-size:0.82rem;">BATCH Pend.: </span>
      <span style="color:#b91c1c;font-weight:700;">{n_batch}</span>
    </div>
    """, unsafe_allow_html=True)

st.markdown('<div class="section-title">📦 Productos con Pateadas — Declara en orden FIFO ↓ (más antiguo primero)</div>',
            unsafe_allow_html=True)

# Agrupar por producto, luego por fecha (más antigua → más nueva)
productos_unicos = (pateadas_linea[["CODIGO","PRODUCTO"]]
                    .drop_duplicates()
                    .sort_values("PRODUCTO")
                    .reset_index(drop=True))

for _, prod_row in productos_unicos.iterrows():
    codigo   = prod_row["CODIGO"]
    producto = prod_row["PRODUCTO"]

    fechas_prod = (pateadas_linea[pateadas_linea["CODIGO"] == codigo]
                   .sort_values("fecha_str")
                   .reset_index(drop=True))

    total_batch_pend = int(fechas_prod["BATCH_PEND"].sum())
    total_cant_pend  = float(fechas_prod["CANT_PEND"].sum())
    n_fechas_prod    = len(fechas_prod)

    titulo_exp = (f"📦 {codigo}  —  {producto[:55]}{'...' if len(producto)>55 else ''}"
                  f"   🔴 {total_batch_pend} BATCH pendientes en {n_fechas_prod} fecha(s)")

    with st.expander(titulo_exp, expanded=False):
        # Info del producto
        st.markdown(f"""
        <div style="background:#fff5f5;border-radius:8px;padding:0.6rem 1rem;
                    margin-bottom:1rem;border-left:3px solid #b91c1c;font-size:0.85rem;">
          <span style="color:#555;">CÓDIGO: </span>
          <span style="color:#1a1a2e;font-weight:600;">{codigo}</span>
          &nbsp;&nbsp;&nbsp;
          <span style="color:#555;">LÍNEA: </span>
          <span style="color:#1a1a2e;font-weight:600;">{linea_sel}</span>
          &nbsp;&nbsp;&nbsp;
          <span style="color:#555;">BATCH Pend. Total: </span>
          <span style="color:#b91c1c;font-weight:700;">{total_batch_pend}</span>
          &nbsp;&nbsp;&nbsp;
          <span style="color:#555;">Cant. Pend. Total: </span>
          <span style="color:#b91c1c;font-weight:700;">{total_cant_pend:,.2f}</span>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**↓ Declara siempre desde la fecha más antigua (FIFO)**")
        st.markdown("")

        for fpos, (_, frow) in enumerate(fechas_prod.iterrows()):
            f_str    = frow["fecha_str"]
            f_disp   = datetime.strptime(f_str, "%Y-%m-%d").strftime("%d/%m/%Y")
            bp_f     = int(frow["BATCH_PLAN"])
            cp_f     = float(frow["CANT_PLAN"])
            br_f     = int(frow["BATCH_REAL"])
            cr_f     = float(frow["CANT_REAL"])
            pend_b_f = int(frow["BATCH_PEND"])
            pend_c_f = float(frow["CANT_PEND"])
            k_f      = key_reg(f_str, codigo)
            ukey_f   = f"pat_{codigo}_{f_str}_{fpos}"

            badge = (
                '<span class="badge-fifo">⬆ DECLARAR PRIMERO</span>'
                if fpos == 0 else
                f'<span class="badge-queue">#{fpos+1} en cola</span>'
            )

            st.markdown(f"""
            <div style="background:#f9fafb;border:1px solid #fecaca;border-radius:8px;
                        padding:0.5rem 1rem;margin:0.4rem 0;border-left:3px solid
                        {'#b91c1c' if fpos==0 else '#0891b2'};font-size:0.84rem;">
              <span style="color:#555;">Fecha: </span>
              <span style="color:#1a1a2e;font-weight:600;">{f_disp}</span>
              &nbsp;&nbsp;{badge}
              &nbsp;&nbsp;<span style="color:#555;">Plan: </span>
              <span style="color:#1a1a2e;font-weight:600;">{bp_f} BATCH</span>
              &nbsp;&nbsp;<span style="color:#555;">Producido: </span>
              <span style="color:#0e7490;font-weight:600;">{br_f} BATCH</span>
              &nbsp;&nbsp;<span style="color:#555;">Pendiente: </span>
              <span style="color:#b91c1c;font-weight:700;">{pend_b_f} BATCH</span>
            </div>
            """, unsafe_allow_html=True)

            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.metric("BATCH Plan",      bp_f)
            mc2.metric("BATCH Producido", br_f)
            mc3.metric("BATCH Pendiente", pend_b_f)
            mc4.metric("Cant. Pendiente", f"{pend_c_f:,.2f}")

            fi1, fi2, fi3 = st.columns([2, 2, 1])
            with fi1:
                nb_f = st.number_input(
                    "BATCH a registrar ahora",
                    min_value=0, max_value=pend_b_f, value=0, step=1,
                    key=f"nb_{ukey_f}_{st.session_state.reg_count_p}"
                )
            with fi2:
                nc_f = st.number_input(
                    "Cantidad a registrar ahora",
                    min_value=0.0,
                    max_value=float(pend_c_f) if pend_c_f > 0 else float(cp_f),
                    value=0.0, step=0.5, format="%.2f",
                    key=f"nc_{ukey_f}_{st.session_state.reg_count_p}"
                )
            with fi3:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("💾 Registrar", key=f"sv_{ukey_f}_{st.session_state.reg_count_p}",
                             use_container_width=True):
                    if nb_f == 0:
                        st.warning("⚠️ Ingresa al menos 1 BATCH")
                    else:
                        batch_acum = br_f + nb_f
                        cant_acum  = cr_f  + nc_f
                        datos = {
                            "batch_real": batch_acum,
                            "cant_real":  cant_acum,
                            "timestamp":  datetime.now().isoformat(),
                            "codigo":     codigo,
                            "producto":   producto,
                            "fecha":      f_str
                        }
                        with st.spinner("Guardando..."):
                            guardar_produccion_p(prod_file, k_f, datos)
                        st.session_state.reg_count_p += 1
                        pend_nuevo = max(bp_f - batch_acum, 0)
                        if pend_nuevo == 0:
                            st.success(f"✅ ¡Completado! {batch_acum}/{bp_f} BATCH — fecha {f_disp} saldada.")
                        else:
                            st.success(f"✅ Registrado — {batch_acum}/{bp_f} BATCH · Pendiente: {pend_nuevo}")
                        time.sleep(0.5)
                        st.rerun()

            st.markdown("---")

        # Tabla resumen del producto
        df_res = fechas_prod[["fecha_str","BATCH_PLAN","BATCH_REAL","BATCH_PEND",
                               "CANT_PLAN","CANT_REAL","CANT_PEND"]].copy()
        df_res.columns = ["Fecha","BATCH Plan","BATCH Real","BATCH Pend.",
                          "Cant. Plan","Cant. Real","Cant. Pend."]
        df_res["Fecha"] = pd.to_datetime(df_res["Fecha"]).dt.strftime("%d/%m/%Y")

        def color_pend(val):
            if isinstance(val, (int, float)) and val > 0:  return "color:#b91c1c;font-weight:600"
            if isinstance(val, (int, float)) and val == 0: return "color:#0e7490"
            return ""

        st.dataframe(
            df_res.style
            .map(color_pend, subset=["BATCH Pend.", "Cant. Pend."])
            .format({"Cant. Plan":"{:,.2f}", "Cant. Real":"{:,.2f}", "Cant. Pend.":"{:,.2f}"})
            .hide(axis="index"),
            use_container_width=True
        )

# ── FOOTER ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    f'<p style="text-align:center;color:#b91c1c;font-size:0.78rem;">'
    f'⚠️ Pateadas — Control de Producción v5.0 Local · '
    f'Fechas anteriores al {hoy.strftime("%d/%m/%Y")} · FIFO</p>',
    unsafe_allow_html=True
)
