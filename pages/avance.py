import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
import os, glob
from gsheets_helper import cargar_produccion_sheets

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Avance de Producción",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.main-header {
    background: linear-gradient(135deg, #1e3a5f 0%, #1d4ed8 50%, #2563eb 100%);
    padding: 1.6rem 2.5rem; border-radius: 16px; margin-bottom: 1.5rem;
    box-shadow: 0 8px 32px rgba(0,0,0,0.18);
}
.main-header h1 { color: #fff; font-size: 2rem; font-weight: 700; margin: 0; }
.main-header p  { color: #bfdbfe; margin: 0.3rem 0 0; font-size: 0.95rem; }
.kpi-card {
    background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 12px;
    padding: 1.1rem 1.2rem; text-align: center;
    box-shadow: 0 4px 16px rgba(0,0,0,0.07);
}
.kpi-label { color: #1d4ed8; font-size: 0.76rem; font-weight: 500;
             text-transform: uppercase; letter-spacing: 0.06em; }
.kpi-value { font-size: 1.9rem; font-weight: 700; margin: 0.2rem 0 0; }
.kpi-blue   { color: #1d4ed8; }
.kpi-green  { color: #16a34a; }
.kpi-orange { color: #b45309; }
.kpi-red    { color: #b91c1c; }
.section-title {
    font-size: 1.05rem; font-weight: 600; color: #c8d8e8;
    border-left: 4px solid #2563eb; padding-left: 0.8rem;
    margin: 1.5rem 0 1rem;
}
[data-testid="stSidebar"] { background: #eff6ff; }
</style>
""", unsafe_allow_html=True)

# ── RUTAS ─────────────────────────────────────────────────────────────────────
_ROOT            = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRODUCTOS_FILE   = os.path.join(_ROOT, "maestro_productos.xlsx")
PROGRAMACION_DIR = os.path.join(_ROOT, "programacion")

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Filtros")
    if st.button("🔃 Recargar datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.markdown("---")
    st.page_link("app.py",             label="← Control de Producción", icon="🏭")
    st.page_link("pages/pateadas.py",  label="Ver Pateadas 🔴",         icon="⚠️")
    st.markdown("---")
    st.caption("📈 **Avance de Producción**")

# ── FUNCIONES ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def cargar_productos(path):
    df = pd.read_excel(path, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    rename = {}
    for c in df.columns:
        if c in ("CÓDIGO","CODIGO"):  rename[c] = "CODIGO"
        if c in ("LÍNEA","LINEA"):    rename[c] = "LINEA"
        if c == "PRODUCTO":           rename[c] = "PRODUCTO"
    return df.rename(columns=rename)[["CODIGO","PRODUCTO","LINEA"]].drop_duplicates(subset="CODIGO")

@st.cache_data(ttl=60)
def cargar_programacion(carpeta):
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
            frames.append(df)
        except Exception:
            pass
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

def color_pct(pct):
    if pct >= 100: return "#16a34a"
    if pct >= 75:  return "#2563eb"
    if pct >= 50:  return "#f59e0b"
    return "#b91c1c"

# ── VALIDAR ARCHIVOS ──────────────────────────────────────────────────────────
errores = []
if not os.path.exists(PRODUCTOS_FILE):   errores.append("❌ No se encuentra `maestro_productos.xlsx`")
if not os.path.exists(PROGRAMACION_DIR): errores.append("❌ No se encuentra la carpeta `programacion/`")
if errores:
    for e in errores: st.error(e)
    st.stop()

df_productos    = cargar_productos(PRODUCTOS_FILE)
df_programacion = cargar_programacion(PROGRAMACION_DIR)
produccion_real = cargar_produccion_sheets()

if df_programacion.empty:
    st.warning("⚠️ No se pudo leer ningún archivo de programación.")
    st.stop()

# ── CONSTRUIR TABLA BASE ──────────────────────────────────────────────────────
df = df_programacion[df_programacion["Cod Item"].isin(df_productos["CODIGO"])].copy()
df = df.merge(df_productos[["CODIGO","PRODUCTO","LINEA"]],
              left_on="Cod Item", right_on="CODIGO", how="left")
df["fecha_date"] = pd.to_datetime(df["Fecha de Vencimiento"], errors="coerce").dt.date
df["fecha_str"]  = pd.to_datetime(df["Fecha de Vencimiento"], errors="coerce").dt.strftime("%Y-%m-%d")
df["fecha_disp"] = pd.to_datetime(df["Fecha de Vencimiento"], errors="coerce").dt.strftime("%d/%m/%Y")
df = df[df["fecha_date"].notna()]
df["Cantidad Planificada"] = pd.to_numeric(df["Cantidad Planificada"], errors="coerce").fillna(0)

# Agregar real por producto+fecha
def get_real(codigo, fecha):
    r = produccion_real.get(f"{fecha}||{codigo}", {})
    return r.get("batch_real", 0), r.get("cant_real", 0.0)

resumen = df.groupby(["CODIGO","PRODUCTO","LINEA","fecha_str","fecha_disp","fecha_date"]).agg(
    BATCH_PLAN=("Nro Documento","count"),
    CANT_PLAN=("Cantidad Planificada","sum")
).reset_index()

resumen[["BATCH_REAL","CANT_REAL"]] = resumen.apply(
    lambda r: pd.Series(get_real(r["CODIGO"], r["fecha_str"])), axis=1)
resumen["BATCH_REAL"] = resumen["BATCH_REAL"].clip(upper=resumen["BATCH_PLAN"])
resumen["PCT_BATCH"]  = (resumen["BATCH_REAL"] / resumen["BATCH_PLAN"] * 100).clip(0, 100).round(1)
resumen["PCT_CANT"]   = (resumen["CANT_REAL"]  / resumen["CANT_PLAN"]  * 100).clip(0, 100).round(1)

hoy = date.today()

# ── FILTROS EN SIDEBAR ────────────────────────────────────────────────────────
with st.sidebar:
    fechas_disp = sorted(resumen["fecha_date"].unique())
    fechas_label = {str(f): datetime.strptime(str(f), "%Y-%m-%d").strftime("%d/%m/%Y")
                    for f in fechas_disp}
    fechas_sel = st.multiselect(
        "📅 Fechas a analizar",
        options=[str(f) for f in fechas_disp],
        default=[str(f) for f in fechas_disp],
        format_func=lambda x: fechas_label[x]
    )
    lineas_disp = ["— Todas —"] + sorted(resumen["LINEA"].dropna().unique().tolist())
    linea_sel   = st.selectbox("🏭 Línea", lineas_disp)

# Aplicar filtros
df_f = resumen[resumen["fecha_str"].isin(fechas_sel)].copy()
if linea_sel != "— Todas —":
    df_f = df_f[df_f["LINEA"] == linea_sel]

if df_f.empty:
    st.warning("No hay datos para los filtros seleccionados.")
    st.stop()

# ── HEADER ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="main-header">
  <div style="display:flex;align-items:center;gap:1.2rem;">
    <span style="font-size:3rem;">📈</span>
    <div>
      <h1>Avance de Producción</h1>
      <p>Análisis porcentual por fecha y por línea · {hoy.strftime('%d/%m/%Y')}</p>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── KPIs GENERALES ────────────────────────────────────────────────────────────
total_plan  = int(df_f["BATCH_PLAN"].sum())
total_real  = int(df_f["BATCH_REAL"].sum())
total_pend  = max(total_plan - total_real, 0)
pct_global  = round(total_real / total_plan * 100, 1) if total_plan > 0 else 0
n_completos = int((df_f.groupby(["CODIGO","fecha_str"])["PCT_BATCH"].mean() >= 100).sum())
n_total_prod = len(df_f.groupby(["CODIGO","fecha_str"]))

k1, k2, k3, k4, k5 = st.columns(5)
for col, lbl, val, cls in [
    (k1, "🎯 Avance Global",        f"{pct_global}%",    "kpi-blue"),
    (k2, "✅ BATCH Producidos",     f"{total_real:,}",    "kpi-green"),
    (k3, "📋 BATCH Planificados",   f"{total_plan:,}",    "kpi-blue"),
    (k4, "🔴 BATCH Pendientes",     f"{total_pend:,}",    "kpi-red"),
    (k5, "🏆 Prod. Completados",    f"{n_completos}/{n_total_prod}", "kpi-green"),
]:
    with col:
        st.markdown(f'<div class="kpi-card"><div class="kpi-label">{lbl}</div>'
                    f'<div class="kpi-value {cls}">{val}</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# GRÁFICO 1 — AVANCE % POR FECHA
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-title">📅 Avance porcentual por Fecha</div>',
            unsafe_allow_html=True)

por_fecha = df_f.groupby(["fecha_str","fecha_disp"]).agg(
    BATCH_PLAN=("BATCH_PLAN","sum"),
    BATCH_REAL=("BATCH_REAL","sum"),
    CANT_PLAN=("CANT_PLAN","sum"),
    CANT_REAL=("CANT_REAL","sum"),
).reset_index().sort_values("fecha_str")

por_fecha["PCT"] = (por_fecha["BATCH_REAL"] / por_fecha["BATCH_PLAN"] * 100).clip(0,100).round(1)
por_fecha["BATCH_PEND"] = (por_fecha["BATCH_PLAN"] - por_fecha["BATCH_REAL"]).clip(lower=0).astype(int)
por_fecha["color"] = por_fecha["PCT"].apply(color_pct)

fig_fecha = go.Figure()

# Barras apiladas: producido + pendiente
fig_fecha.add_trace(go.Bar(
    x=por_fecha["fecha_disp"],
    y=por_fecha["BATCH_REAL"],
    name="BATCH Producido",
    marker_color="#2563eb",
    text=por_fecha["BATCH_REAL"],
    textposition="inside",
    insidetextanchor="middle",
    textfont=dict(color="white", size=12, family="Inter"),
))
fig_fecha.add_trace(go.Bar(
    x=por_fecha["fecha_disp"],
    y=por_fecha["BATCH_PEND"],
    name="BATCH Pendiente",
    marker_color="#fca5a5",
    text=por_fecha["BATCH_PEND"],
    textposition="inside",
    insidetextanchor="middle",
    textfont=dict(color="#7f1d1d", size=12, family="Inter"),
))

# Línea de porcentaje encima
fig_fecha.add_trace(go.Scatter(
    x=por_fecha["fecha_disp"],
    y=por_fecha["PCT"],
    name="% Avance",
    yaxis="y2",
    mode="lines+markers+text",
    line=dict(color="#16a34a", width=3),
    marker=dict(size=10, color="#16a34a"),
    text=[f"{p}%" for p in por_fecha["PCT"]],
    textposition="top center",
    textfont=dict(color="#16a34a", size=13, family="Inter", weight=700),
))

fig_fecha.update_layout(
    barmode="stack",
    yaxis=dict(title="BATCH", gridcolor="#e2e8f0"),
    yaxis2=dict(title="% Avance", overlaying="y", side="right",
                range=[0, 115], showgrid=False,
                tickformat=".0f", ticksuffix="%"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    plot_bgcolor="white", paper_bgcolor="white",
    margin=dict(t=40, b=20, l=20, r=20),
    height=400,
    font=dict(family="Inter"),
)
st.plotly_chart(fig_fecha, use_container_width=True)

# Tabla resumen por fecha
df_tabla_fecha = por_fecha[["fecha_disp","BATCH_PLAN","BATCH_REAL","BATCH_PEND","PCT"]].copy()
df_tabla_fecha.columns = ["Fecha","BATCH Plan","BATCH Real","BATCH Pend.","% Avance"]

def highlight_pct(val):
    if isinstance(val, float):
        c = color_pct(val)
        return f"color:{c};font-weight:700"
    return ""

st.dataframe(
    df_tabla_fecha.style
    .map(highlight_pct, subset=["% Avance"])
    .format({"% Avance": "{:.1f}%"})
    .hide(axis="index"),
    use_container_width=True, height=200
)

# ══════════════════════════════════════════════════════════════════════════════
# GRÁFICO 2 — AVANCE % POR LÍNEA
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-title">🏭 Avance porcentual por Línea</div>',
            unsafe_allow_html=True)

por_linea = df_f.groupby("LINEA").agg(
    BATCH_PLAN=("BATCH_PLAN","sum"),
    BATCH_REAL=("BATCH_REAL","sum"),
).reset_index()
por_linea["PCT"]        = (por_linea["BATCH_REAL"] / por_linea["BATCH_PLAN"] * 100).clip(0,100).round(1)
por_linea["BATCH_PEND"] = (por_linea["BATCH_PLAN"] - por_linea["BATCH_REAL"]).clip(lower=0).astype(int)
por_linea = por_linea.sort_values("PCT", ascending=True)
por_linea["color"] = por_linea["PCT"].apply(color_pct)

fig_linea = go.Figure()
fig_linea.add_trace(go.Bar(
    x=por_linea["PCT"],
    y=por_linea["LINEA"],
    orientation="h",
    marker_color=por_linea["color"],
    text=[f"{p}%  ({r}/{pl} BATCH)" for p, r, pl in
          zip(por_linea["PCT"], por_linea["BATCH_REAL"], por_linea["BATCH_PLAN"])],
    textposition="auto",
    textfont=dict(family="Inter", size=12, color="white"),
))
fig_linea.add_vline(x=100, line_dash="dash", line_color="#6b7280", line_width=1.5)

fig_linea.update_layout(
    xaxis=dict(title="% Avance", range=[0, 115], ticksuffix="%", gridcolor="#e2e8f0"),
    yaxis=dict(title=""),
    plot_bgcolor="white", paper_bgcolor="white",
    margin=dict(t=20, b=20, l=20, r=20),
    height=max(300, len(por_linea) * 45),
    font=dict(family="Inter"),
    showlegend=False,
)
st.plotly_chart(fig_linea, use_container_width=True)

# ── NOTA AL PIE ───────────────────────────────────────────────────────────────
st.markdown("---")

# Leyenda de colores
lc1, lc2, lc3, lc4 = st.columns(4)
for col, color, lbl in [
    (lc1, "#16a34a", "✅ 100% — Completado"),
    (lc2, "#2563eb", "🔵 75–99% — Avanzando"),
    (lc3, "#f59e0b", "🟡 50–74% — En proceso"),
    (lc4, "#b91c1c", "🔴 0–49%  — Crítico"),
]:
    with col:
        st.markdown(
            f'<div style="background:{color};color:white;border-radius:8px;'
            f'padding:0.4rem 0.8rem;text-align:center;font-size:0.82rem;font-weight:600;">'
            f'{lbl}</div>', unsafe_allow_html=True)

st.markdown(
    f'<p style="text-align:center;color:#6b7280;font-size:0.78rem;margin-top:0.8rem;">'
    f'📈 Avance de Producción · Control de Producción v5.0 · {hoy.strftime("%d/%m/%Y")}</p>',
    unsafe_allow_html=True
)
