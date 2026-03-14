import streamlit as st
import pandas as pd
from datetime import datetime
import json, io, time
import gspread
from google.oauth2.service_account import Credentials

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

# ── GOOGLE SHEETS ─────────────────────────────────────────────────────────────
SHEET_ID = "1NduVjrPt8QgoP7GhTMGlNCwdtd2uiuLfS6s9iwkpLGw"
SCOPES   = ["https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"]

@st.cache_resource
def get_gsheet_client():
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)

@st.cache_resource
def get_spreadsheet():
    return get_gsheet_client().open_by_key(SHEET_ID)

@st.cache_data(ttl=120)
def cargar_productos_gsheet() -> pd.DataFrame:
    sh  = get_spreadsheet()
    ws  = sh.worksheet("PRODUCTOS")
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    if df.empty:
        return pd.DataFrame(columns=["CODIGO","PRODUCTO","LINEA"])
    rename = {}
    for c in df.columns:
        if c in ("CÓDIGO","CODIGO"):  rename[c] = "CODIGO"
        if c in ("LÍNEA","LINEA"):    rename[c] = "LINEA"
        if c == "PRODUCTO":           rename[c] = "PRODUCTO"
    df = df.rename(columns=rename)
    return df[["CODIGO","PRODUCTO","LINEA"]].drop_duplicates(subset="CODIGO").astype(str)

@st.cache_data(ttl=120)
def cargar_programacion_gsheet() -> pd.DataFrame:
    sh   = get_spreadsheet()
    ws   = sh.worksheet("PROGRAMACION")
    data = ws.get_all_records()
    df   = pd.DataFrame(data)
    if df.empty:
        return pd.DataFrame()
    df.columns = [c.strip() for c in df.columns]
    if "Cod Item" in df.columns:
        df["Cod Item"] = df["Cod Item"].astype(str)
    if "Fecha de Vencimiento" in df.columns:
        df["Fecha de Vencimiento"] = pd.to_datetime(df["Fecha de Vencimiento"], errors="coerce")
    return df

@st.cache_data(ttl=0)
def cargar_produccion_gsheet() -> dict:
    sh   = get_spreadsheet()
    ws   = sh.worksheet("PRODUCCION_REAL")
    data = ws.get_all_records()
    result = {}
    for row in data:
        k = row.get("key","")
        if k:
            result[k] = {
                "batch_real": int(row.get("batch_real", 0)),
                "cant_real":  float(row.get("cant_real", 0.0)),
                "timestamp":  row.get("timestamp",""),
                "codigo":     row.get("codigo",""),
                "producto":   row.get("producto",""),
                "fecha":      row.get("fecha",""),
            }
    return result

def guardar_produccion_gsheet(key: str, datos: dict):
    sh = get_spreadsheet()
    ws = sh.worksheet("PRODUCCION_REAL")
    fila = [
        key,
        datos.get("batch_real", 0),
        datos.get("cant_real", 0.0),
        datos.get("timestamp",""),
        datos.get("codigo",""),
        datos.get("producto",""),
        datos.get("fecha",""),
    ]
    # Asegurar encabezado
    todos = ws.get_all_values()
    if not todos:
        ws.append_row(["key","batch_real","cant_real","timestamp","codigo","producto","fecha"])
        todos = [["key","batch_real","cant_real","timestamp","codigo","producto","fecha"]]

    # Buscar si ya existe la fila con ese key
    row_num = None
    for i, row in enumerate(todos):
        if row and row[0] == key:
            row_num = i + 1
            break

    if row_num:
        ws.update(f"A{row_num}:G{row_num}", [fila])
    else:
        ws.append_row(fila)

def init_hoja_produccion():
    """Crea encabezado en PRODUCCION_REAL si está vacía."""
    try:
        sh = get_spreadsheet()
        ws = sh.worksheet("PRODUCCION_REAL")
        if not ws.get_all_values():
            ws.append_row(["key","batch_real","cant_real","timestamp","codigo","producto","fecha"])
    except Exception:
        pass

def key_reg(fecha_str: str, codigo: str) -> str:
    return f"{fecha_str}||{codigo}"

def fmt_fecha(d) -> str:
    s = d.strftime("%d/%m/%Y (%A)")
    for en, es in [("Monday","Lunes"),("Tuesday","Martes"),("Wednesday","Miércoles"),
                   ("Thursday","Jueves"),("Friday","Viernes"),("Saturday","Sábado"),("Sunday","Domingo")]:
        s = s.replace(en, es)
    return s

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📂 Actualizar Datos")

    st.markdown("**📦 Subir Maestro de Productos**")
    st.caption("Solo cuando agregues o cambies productos.")
    f_prod = st.file_uploader("", type=["xlsx"], key="up_prod", label_visibility="collapsed")
    if f_prod:
        with st.spinner("Subiendo a Google Sheets..."):
            try:
                df_up = pd.read_excel(io.BytesIO(f_prod.read()), dtype=str)
                df_up.columns = [c.strip() for c in df_up.columns]
                sh = get_spreadsheet()
                ws = sh.worksheet("PRODUCTOS")
                ws.clear()
                ws.append_row(df_up.columns.tolist())
                ws.append_rows(df_up.fillna("").values.tolist())
                cargar_productos_gsheet.clear()
                st.success(f"✅ {len(df_up)} productos actualizados")
            except Exception as e:
                st.error(f"❌ {e}")

    st.markdown("---")
    st.markdown("**📅 Subir Programación Diaria**")
    st.caption("Sube uno o varios `YYYYMMDD.xlsx`. Se **agregan** a los existentes.")
    f_prog = st.file_uploader("", type=["xlsx"], accept_multiple_files=True,
                               key="up_prog", label_visibility="collapsed")
    if f_prog:
        with st.spinner("Subiendo programación..."):
            try:
                frames = []
                for f in f_prog:
                    df_dia = pd.read_excel(io.BytesIO(f.read()),
                                           dtype={"Cod Item": str, "Nro Documento": str})
                    df_dia.columns = [c.strip() for c in df_dia.columns]
                    nombre = f.name.replace(".xlsx","")
                    if "Fecha de Vencimiento" not in df_dia.columns or df_dia["Fecha de Vencimiento"].isna().all():
                        df_dia["Fecha de Vencimiento"] = pd.to_datetime(nombre, format="%Y%m%d", errors="coerce")
                    frames.append(df_dia)

                sh  = get_spreadsheet()
                ws  = sh.worksheet("PROGRAMACION")
                # Leer existente y concatenar
                existing = ws.get_all_records()
                df_exist = pd.DataFrame(existing) if existing else pd.DataFrame()
                df_new   = pd.concat(frames, ignore_index=True)
                df_new["Fecha de Vencimiento"] = pd.to_datetime(
                    df_new["Fecha de Vencimiento"], errors="coerce").dt.strftime("%Y-%m-%d")

                if not df_exist.empty:
                    # Eliminar duplicados por Nro Documento
                    df_exist["Nro Documento"] = df_exist["Nro Documento"].astype(str)
                    df_new["Nro Documento"]   = df_new["Nro Documento"].astype(str)
                    df_combined = pd.concat([df_exist, df_new], ignore_index=True)
                    df_combined = df_combined.drop_duplicates(subset=["Nro Documento"], keep="last")
                else:
                    df_combined = df_new

                ws.clear()
                ws.append_row(df_combined.columns.tolist())
                ws.append_rows(df_combined.fillna("").astype(str).values.tolist())
                cargar_programacion_gsheet.clear()
                st.success(f"✅ Programación actualizada — {len(df_combined)} registros totales")
            except Exception as e:
                st.error(f"❌ {e}")

    st.markdown("---")
    if st.button("🔃 Recargar datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.caption("🏭 **Control de Producción v5.0**\nGoogle Sheets · Datos persistentes")

# ── HEADER ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
  <h1>🏭 Control de Producción</h1>
  <p>Seguimiento en tiempo real · Datos persistentes en Google Sheets</p>
</div>
""", unsafe_allow_html=True)

# ── CARGAR DATOS ──────────────────────────────────────────────────────────────
try:
    init_hoja_produccion()
    with st.spinner("Cargando datos..."):
        df_productos    = cargar_productos_gsheet()
        df_programacion = cargar_programacion_gsheet()
        produccion_real = cargar_produccion_gsheet()
except Exception as e:
    st.error(f"❌ Error conectando con Google Sheets: {e}")
    st.info("Verifica que los secrets de Streamlit estén configurados correctamente.")
    st.stop()

if df_productos.empty:
    st.warning("⚠️ No hay productos cargados. Sube el `maestro_productos.xlsx` desde la barra lateral.")
    st.stop()

if df_programacion.empty:
    st.warning("⚠️ No hay programación cargada. Sube un archivo `YYYYMMDD.xlsx` desde la barra lateral.")
    st.stop()

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
tab1, tab2, tab3, tab4 = st.tabs([
    "📋 Tablero de Control",
    "✍️ Registro de Producción",
    "📊 Resumen por Línea",
    "🕐 Pendientes Históricos FIFO"
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

                ci1, ci2, ci3 = st.columns([2, 2, 1])
                with ci1:
                    nuevo_batch = st.number_input("BATCH producidos", min_value=0, max_value=bp*3,
                                                  value=br, step=1, key=f"batch_{ukey}")
                with ci2:
                    nueva_cant  = st.number_input("Cantidad producida", min_value=0.0, max_value=float(cp*3),
                                                  value=float(cr), step=0.5, format="%.2f", key=f"cant_{ukey}")
                with ci3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("💾 Guardar", key=f"save_{ukey}", use_container_width=True):
                        datos = {"batch_real": nuevo_batch, "cant_real": nueva_cant,
                                 "timestamp": datetime.now().isoformat(),
                                 "codigo": row["CODIGO"], "producto": row["PRODUCTO"], "fecha": fecha_str}
                        with st.spinner("Guardando..."):
                            guardar_produccion_gsheet(k, datos)
                        st.cache_data.clear()
                        st.success(f"✅ Guardado en Google Sheets — Pend: {max(bp-nuevo_batch,0)} BATCH")
                        time.sleep(0.5)
                        st.rerun()

        st.markdown("---")
        if st.button("💾 GUARDAR TODO DE UNA VEZ", type="primary", use_container_width=True):
            with st.spinner("Guardando todos los registros..."):
                cambios = 0
                for pos, (_, row) in enumerate(df_con_prog.iterrows()):
                    k    = key_reg(fecha_str, row["CODIGO"])
                    ukey = f"{k}||{pos}"
                    bk, ck = f"batch_{ukey}", f"cant_{ukey}"
                    if bk in st.session_state:
                        datos = {"batch_real": st.session_state[bk], "cant_real": st.session_state[ck],
                                 "timestamp": datetime.now().isoformat(),
                                 "codigo": row["CODIGO"], "producto": row["PRODUCTO"], "fecha": fecha_str}
                        guardar_produccion_gsheet(k, datos)
                        cambios += 1
            st.cache_data.clear()
            st.success(f"✅ {cambios} registros guardados en Google Sheets")
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

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — PENDIENTES HISTÓRICOS FIFO
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown('<div class="section-title">🕐 Pendientes Históricos por Producto — Método FIFO</div>',
                unsafe_allow_html=True)
    st.markdown("Selecciona un producto y ve todos sus BATCH pendientes de **más antiguo a más reciente**.")

    df_hist = df_programacion[df_programacion["Cod Item"].isin(df_productos["CODIGO"])].copy()
    df_hist = df_hist.merge(df_productos[["CODIGO","PRODUCTO","LINEA"]], left_on="Cod Item", right_on="CODIGO", how="left")
    df_hist["fecha_str"] = df_hist["Fecha de Vencimiento"].dt.strftime("%Y-%m-%d")

    resumen_hist = df_hist.groupby(["CODIGO","PRODUCTO","LINEA","fecha_str"]).agg(
        BATCH_PLAN=("Nro Documento","count"), CANT_PLAN=("Cantidad Planificada","sum")
    ).reset_index().sort_values(["CODIGO","fecha_str"])

    resumen_hist["CANT_PLAN"] = pd.to_numeric(resumen_hist["CANT_PLAN"], errors="coerce").fillna(0)

    def get_real(codigo, fecha):
        r = produccion_real.get(key_reg(fecha, codigo), {})
        return r.get("batch_real",0), r.get("cant_real",0.0)

    resumen_hist[["BATCH_REAL","CANT_REAL"]] = resumen_hist.apply(
        lambda r: pd.Series(get_real(r["CODIGO"], r["fecha_str"])), axis=1)
    resumen_hist["BATCH_PEND"] = (resumen_hist["BATCH_PLAN"]-resumen_hist["BATCH_REAL"]).clip(lower=0).astype(int)
    resumen_hist["CANT_PEND"]  = (resumen_hist["CANT_PLAN"] -resumen_hist["CANT_REAL"]).clip(lower=0).round(2)
    hist_pend = resumen_hist[resumen_hist["BATCH_PEND"]>0].copy()

    kp1, kp2, kp3, kp4 = st.columns(4)
    for col, lbl, val, cls in [
        (kp1,"🔴 Productos con Pendiente", str(hist_pend["CODIGO"].nunique()),       "kpi-red"),
        (kp2,"📅 Fechas Afectadas",        str(hist_pend["fecha_str"].nunique()),    "kpi-orange"),
        (kp3,"🔢 BATCH Pendientes Total",  str(int(hist_pend["BATCH_PEND"].sum())), "kpi-orange"),
        (kp4,"⚖️ Cant. Pendiente Total",  f"{float(hist_pend['CANT_PEND'].sum()):,.1f}", "kpi-orange"),
    ]:
        with col:
            st.markdown(f'<div class="kpi-card"><div class="kpi-label">{lbl}</div>'
                        f'<div class="kpi-value {cls}">{val}</div></div>', unsafe_allow_html=True)
    st.markdown("")

    if hist_pend.empty:
        st.success("🎉 ¡Sin pendientes históricos! Todo está al día.")
    else:
        cbp1, cbp2 = st.columns([2,2])
        with cbp1:
            lineas_pend = ["— Todas —"] + sorted(hist_pend["LINEA"].dropna().unique().tolist())
            linea_pend  = st.selectbox("🏭 Filtrar por Línea", lineas_pend, key="linea_pend")
        prods_pend = hist_pend[hist_pend["LINEA"]==linea_pend] if linea_pend != "— Todas —" else hist_pend
        lista_prods = sorted(prods_pend[["CODIGO","PRODUCTO"]].drop_duplicates()
                             .apply(lambda r: f"{r['CODIGO']} — {r['PRODUCTO']}", axis=1).tolist())
        with cbp2:
            if not lista_prods:
                st.info("No hay pendientes para esta línea.")
                st.stop()
            prod_sel = st.selectbox("📦 Selecciona un producto", lista_prods, key="prod_pend")

        codigo_sel   = prod_sel.split(" — ")[0].strip()
        detalle_prod = hist_pend[hist_pend["CODIGO"]==codigo_sel].sort_values("fecha_str")

        if not detalle_prod.empty:
            nombre_prod = detalle_prod.iloc[0]["PRODUCTO"]
            linea_prod  = detalle_prod.iloc[0]["LINEA"]
            st.markdown(f"""
            <div style="background:#f0f9ff;border-radius:10px;padding:0.8rem 1.2rem;
                        margin:0.8rem 0;border-left:4px solid #b91c1c;">
              <span style="color:#555;font-size:0.82rem;">PRODUCTO: </span>
              <span style="color:#1a1a2e;font-size:0.95rem;font-weight:700;">{nombre_prod}</span>
              &nbsp;&nbsp;
              <span style="color:#555;font-size:0.82rem;">LÍNEA: </span>
              <span style="color:#1a1a2e;font-size:0.85rem;font-weight:600;">{linea_prod}</span>
              &nbsp;&nbsp;
              <span style="color:#555;font-size:0.82rem;">BATCH PENDIENTES TOTALES: </span>
              <span style="color:#b91c1c;font-size:0.95rem;font-weight:700;">{int(detalle_prod["BATCH_PEND"].sum())}</span>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("**Declara siempre desde la fecha más antigua ↓ (FIFO)**")

            for fpos, (_, frow) in enumerate(detalle_prod.iterrows()):
                f_str    = frow["fecha_str"]
                f_disp   = datetime.strptime(f_str,"%Y-%m-%d").strftime("%d/%m/%Y")
                bp_f, cp_f = int(frow["BATCH_PLAN"]), float(frow["CANT_PLAN"])
                br_f, cr_f = int(frow["BATCH_REAL"]), float(frow["CANT_REAL"])
                pend_b_f   = int(frow["BATCH_PEND"])
                pend_c_f   = float(frow["CANT_PEND"])
                k_f        = key_reg(f_str, codigo_sel)
                ukey_f     = f"fifo_{codigo_sel}_{f_str}_{fpos}"
                badge = ('<span style="background:#b91c1c;color:#fff;font-size:0.72rem;padding:2px 10px;border-radius:12px;font-weight:700;">⬆ DECLARAR PRIMERO</span>'
                         if fpos==0 else
                         f'<span style="background:#e0f7fa;color:#0e7490;font-size:0.72rem;padding:2px 10px;border-radius:12px;">#{fpos+1} en cola</span>')

                with st.expander(f"📅 {f_disp}  —  {pend_b_f} BATCH pendientes", expanded=(fpos==0)):
                    st.markdown(f"""
                    <div style="background:#f0f9ff;border-radius:8px;padding:0.5rem 1rem;
                                margin-bottom:0.8rem;border-left:3px solid #0891b2;font-size:0.85rem;">
                      <span style="color:#555;">Fecha: </span>
                      <span style="color:#1a1a2e;font-weight:600;">{f_disp}</span>&nbsp;&nbsp;{badge}
                      &nbsp;&nbsp;<span style="color:#555;">BATCH Plan: </span><span style="color:#1a1a2e;font-weight:600;">{bp_f}</span>
                      &nbsp;&nbsp;<span style="color:#555;">Ya producido: </span><span style="color:#0e7490;font-weight:600;">{br_f}</span>
                      &nbsp;&nbsp;<span style="color:#555;">Pendiente: </span><span style="color:#b91c1c;font-weight:700;">{pend_b_f}</span>
                    </div>
                    """, unsafe_allow_html=True)

                    fm1, fm2, fm3, fm4 = st.columns(4)
                    fm1.metric("BATCH Plan", bp_f)
                    fm2.metric("BATCH Producido", br_f)
                    fm3.metric("BATCH Pendiente", pend_b_f)
                    fm4.metric("Cant. Pendiente", f"{pend_c_f:,.2f}")

                    fi1, fi2, fi3 = st.columns([2,2,1])
                    with fi1:
                        nb_fifo = st.number_input("BATCH a declarar", min_value=0, max_value=bp_f*2,
                                                  value=br_f, step=1, key=f"nbatch_{ukey_f}")
                    with fi2:
                        nc_fifo = st.number_input("Cantidad a declarar", min_value=0.0, max_value=float(cp_f*2),
                                                  value=float(cr_f), step=0.5, format="%.2f", key=f"ncant_{ukey_f}")
                    with fi3:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("💾 Guardar", key=f"nsave_{ukey_f}", use_container_width=True):
                            datos = {"batch_real": nb_fifo, "cant_real": nc_fifo,
                                     "timestamp": datetime.now().isoformat(),
                                     "codigo": codigo_sel, "producto": nombre_prod, "fecha": f_str}
                            with st.spinner("Guardando..."):
                                guardar_produccion_gsheet(k_f, datos)
                            st.cache_data.clear()
                            st.success(f"✅ Guardado — Pendiente: {max(bp_f-nb_fifo,0)} BATCH")
                            time.sleep(0.5)
                            st.rerun()

            st.markdown("---")
            df_fr = detalle_prod[["fecha_str","BATCH_PLAN","BATCH_REAL","BATCH_PEND","CANT_PLAN","CANT_REAL","CANT_PEND"]].copy()
            df_fr.columns = ["Fecha","BATCH Plan","BATCH Real","BATCH Pend.","Cant. Plan","Cant. Real","Cant. Pend."]
            df_fr["Fecha"] = pd.to_datetime(df_fr["Fecha"]).dt.strftime("%d/%m/%Y")

            def color_pend(val):
                if isinstance(val,(int,float)) and val>0:  return "color:#b91c1c;font-weight:600"
                if isinstance(val,(int,float)) and val==0: return "color:#0e7490"
                return ""

            st.dataframe(
                df_fr.style.map(color_pend, subset=["BATCH Pend.","Cant. Pend."])
                .format({"Cant. Plan":"{:,.2f}","Cant. Real":"{:,.2f}","Cant. Pend.":"{:,.2f}"})
                .hide(axis="index"), use_container_width=True
            )

# ── FOOTER ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    f'<p style="text-align:center;color:#0891b2;font-size:0.78rem;">'
    f'🏭 Control de Producción v5.0 · Google Sheets · Datos persistentes · '
    f'{dias_cargados} día(s) cargado(s)</p>',
    unsafe_allow_html=True
)
