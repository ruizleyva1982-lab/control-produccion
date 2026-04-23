# ── MÓDULO COMPARTIDO: conexión a Google Sheets ───────────────────────────────
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
SHEET_ID   = st.secrets["sheets"]["spreadsheet_id"]
SHEET_NAME = "Sheet1"

@st.cache_resource
def get_sheet():
    creds  = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
    client = gspread.authorize(creds)
    sh     = client.open_by_key(SHEET_ID)
    try:
        ws = sh.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=SHEET_NAME, rows=5000, cols=7)
        ws.append_row(["key","batch_real","cant_real","timestamp","codigo","producto","fecha"])
    return ws

def cargar_produccion_sheets() -> dict:
    """Devuelve dict {key: {batch_real, cant_real, timestamp, codigo, producto, fecha}}"""
    try:
        ws      = get_sheet()
        records = ws.get_all_records()
        return {r["key"]: r for r in records if r.get("key")}
    except Exception as e:
        st.warning(f"⚠️ Error leyendo Google Sheets: {e}")
        return {}

def guardar_produccion_sheets(produccion_real: dict, key: str, datos: dict):
    """Upsert: si la key ya existe actualiza la fila, si no agrega."""
    try:
        ws = get_sheet()
        produccion_real[key] = datos
        fila = [
            key,
            datos["batch_real"],
            datos["cant_real"],
            datos["timestamp"],
            datos["codigo"],
            datos["producto"],
            datos["fecha"],
        ]
        # Buscar si ya existe la key
        cell = ws.find(key, in_column=1)
        if cell:
            ws.update(f"A{cell.row}:G{cell.row}", [fila])
        else:
            ws.append_row(fila)
    except Exception as e:
        st.error(f"❌ Error guardando en Google Sheets: {e}")
