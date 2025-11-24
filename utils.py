# utils.py
import json
from datetime import datetime, date, timedelta
import pandas as pd
import tempfile
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import matplotlib.pyplot as plt
import os

# -------------------------
# JSON load/save helpers
# -------------------------
def load_data(path="data.json"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_data(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_users(path="users.json"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def authenticate(username, password, users):
    for u in users:
        if u.get("username") == username and u.get("password") == password:
            return u
    return None

# -------------------------
# Employee entries
# -------------------------
def add_employee_entry(path, user, fecha, hora_inicio, hora_salida, descanso, estres, estado, comentario):
    data = load_data(path)

    entry = {
        "nombre": user.get("username", user.get("nombre", "")),
        "sede": user.get("sede", ""),
        "fecha": fecha,
        "hora_inicio": hora_inicio.strftime("%H:%M"),
        "hora_salida": hora_salida.strftime("%H:%M"),
        "descanso": int(descanso),
        "estres": int(estres),
        "estado": estado,
        "comentario": comentario.strip() if comentario else ""
    }
    data.append(entry)
    save_data(path, data)

# -------------------------
# Filters / alerts / dataframe
# -------------------------
def filter_data(data, fecha=None, sede=None):
    filtered = data
    if fecha:
        filtered = [d for d in filtered if d.get("fecha") == fecha]
    if sede:
        filtered = [d for d in filtered if d.get("sede") == sede]
    return filtered

def get_alerts(data):
    alerts = []
    for d in data:
        motivos = []
        if d.get("estres", 0) >= 8:
            motivos.append("Estrés alto ≥ 8")
        if d.get("descanso", 0) < 30:
            motivos.append("Descanso insuficiente < 30 min")
        if d.get("estado", "") in ["Estresado", "Agotado"]:
            motivos.append(f"Estado emocional: {d.get('estado')}")
        if motivos:
            alerts.append({
                "sede": d.get("sede", ""),
                "nombre": d.get("nombre", ""),
                "motivo": ", ".join(motivos),
                "estres": d.get("estres", 0),
                "fecha": d.get("fecha", "")
            })
    return alerts

def get_dataframe_ordered(data):
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    cols = ["sede","fecha","nombre","hora_inicio","hora_salida","descanso","estres","estado","comentario"]
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    df = df[cols]
    df = df.sort_values(by=["sede","fecha","nombre"])
    return df

# -------------------------
# KPIs and charts
# -------------------------
def compute_kpis(data):
    if not data:
        return {
            "estres_promedio": 0.0,
            "pct_descanso": 0.0,
            "alertas_count": 0,
            "fig_week": None,
            "pie_estado": None
        }

    df = pd.DataFrame(data)
    # Ensure numeric types
    if "estres" in df.columns:
        df["estres"] = pd.to_numeric(df["estres"], errors="coerce").fillna(0)
    else:
        df["estres"] = 0
    if "descanso" in df.columns:
        df["descanso"] = pd.to_numeric(df["descanso"], errors="coerce").fillna(0)
    else:
        df["descanso"] = 0

    estres_prom = df["estres"].mean()
    pct_desc = (df["descanso"] >= 45).mean() * 100

    alerts = get_alerts(data)

    # --- Figura semanal (promedio estrés por fecha) ---
    fig_week = None
    try:
        df_dates = df.copy()
        if "fecha" in df_dates.columns:
            df_dates["fecha"] = pd.to_datetime(df_dates["fecha"], errors="coerce")
            # Keep last 7 days from max date in data
            max_date = df_dates["fecha"].max()
            start_date = max_date - pd.Timedelta(days=6)
            df_week = df_dates[df_dates["fecha"] >= start_date]
            if not df_week.empty:
                agg = df_week.groupby(df_week["fecha"].dt.date)["estres"].mean().sort_index()
                fig_week, ax = plt.subplots()
                ax.bar(agg.index.astype(str), agg.values)
                ax.set_xlabel("Fecha")
                ax.set_ylabel("Promedio nivel de estrés")
                ax.set_title("Promedio de estrés por día (últimos 7 días)")
                plt.xticks(rotation=45)
                plt.tight_layout()
    except Exception:
        fig_week = None

    # --- Pie estado ---
    pie_estado = None
    try:
        if "estado" in df.columns:
            counts = df["estado"].value_counts()
            if not counts.empty:
                pie_estado, ax2 = plt.subplots()
                ax2.pie(counts.values, labels=counts.index, autopct="%1.1f%%")
                ax2.set_title("Estado emocional")
                plt.tight_layout()
    except Exception:
        pie_estado = None

    return {
        "estres_promedio": float(estres_prom),
        "pct_descanso": float(pct_desc),
        "alertas_count": len(alerts),
        "fig_week": fig_week,
        "pie_estado": pie_estado
    }

# -------------------------
# PDF generation (returns file path)
# -------------------------
def generate_pdf_report(data):
    # create temp file
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(tmp.name, pagesize=letter)

    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, 750, "Reporte — Bienestar Starbucks")
    c.line(40, 744, 560, 744)

    if not data:
        c.setFont("Helvetica", 12)
        c.drawString(40, 720, "No hay datos disponibles.")
        c.showPage()
        c.save()
        return tmp.name

    df = pd.DataFrame(data)
    # KPIs
    estres_prom = df["estres"].mean() if "estres" in df.columns else 0
    pct_desc = (df["descanso"] >= 45).mean() * 100 if "descanso" in df.columns else 0

    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, 720, "KPIs generales:")
    c.setFont("Helvetica", 12)
    c.drawString(40, 700, f"• Estrés promedio: {estres_prom:.2f}")
    c.drawString(40, 685, f"• % descansos ≥ 45 min: {pct_desc:.1f}%")

    # Add simple table header (first 20 rows)
    c.setFont("Helvetica-Bold", 12)
    y = 650
    c.drawString(40, y, "Fecha")
    c.drawString(120, y, "Sede")
    c.drawString(260, y, "Nombre")
    c.drawString(380, y, "Estrés")
    y -= 15
    c.setFont("Helvetica", 10)
    for i, row in df.head(20).iterrows():
        c.drawString(40, y, str(row.get("fecha", "")))
        c.drawString(120, y, str(row.get("sede", ""))[:20])
        c.drawString(260, y, str(row.get("nombre", ""))[:20])
        c.drawString(380, y, str(row.get("estres", "")))
        y -= 12
        if y < 60:
            c.showPage()
            y = 750

    c.showPage()
    c.save()
    return tmp.name

def generate_pdf_report_by_sede(data, sede):
    df = pd.DataFrame([d for d in data if d.get("sede") == sede])

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(tmp.name, pagesize=letter)

    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, 750, f"Reporte — Sede {sede}")
    c.line(40, 744, 560, 744)

    if df.empty:
        c.setFont("Helvetica", 12)
        c.drawString(40, 720, "No hay datos para esta sede.")
        c.showPage()
        c.save()
        return tmp.name

    estres_prom = df["estres"].mean() if "estres" in df.columns else 0
    pct_desc = (df["descanso"] >= 45).mean() * 100 if "descanso" in df.columns else 0

    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, 720, "KPIs:")
    c.setFont("Helvetica", 12)
    c.drawString(40, 700, f"• Estrés promedio: {estres_prom:.2f}")
    c.drawString(40, 685, f"• % descansos ≥ 45 min: {pct_desc:.1f}%")

    # small table
    c.setFont("Helvetica-Bold", 12)
    y = 650
    c.drawString(40, y, "Fecha")
    c.drawString(120, y, "Nombre")
    c.drawString(300, y, "Estrés")
    y -= 15
    c.setFont("Helvetica", 10)
    for i, row in df.head(30).iterrows():
        c.drawString(40, y, str(row.get("fecha", "")))
        c.drawString(120, y, str(row.get("nombre", ""))[:30])
        c.drawString(300, y, str(row.get("estres", "")))
        y -= 12
        if y < 60:
            c.showPage()
            y = 750

    c.showPage()
    c.save()
    return tmp.name
        c.setFo


