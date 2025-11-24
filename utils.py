import json
from datetime import datetime, date, timedelta
import pandas as pd
import tempfile
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import matplotlib.pyplot as plt
import os

# ==========================================
# JSON LOAD / SAVE
# ==========================================
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


# ==========================================
# EMPLOYEE ENTRIES
# ==========================================
def add_employee_entry(path, user, fecha, hora_inicio, hora_salida, descanso, estres, estado, comentario):
    data = load_data(path)

    entry = {
        "nombre": user.get("nombre", user.get("username", "")),
        "sede": user.get("sede", ""),
        "fecha": fecha,
        "hora_inicio": hora_inicio.strftime("%H:%M") if hasattr(hora_inicio, "strftime") else str(hora_inicio),
        "hora_salida": hora_salida.strftime("%H:%M") if hasattr(hora_salida, "strftime") else str(hora_salida),
        "descanso": int(descanso) if descanso is not None else 0,
        "estres": int(estres) if estres is not None else 0,
        "estado": estado,
        "comentario": comentario.strip() if comentario else ""
    }

    data.append(entry)
    save_data(path, data)


# ==========================================
# FILTERS / ALERTS
# ==========================================
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
        estres_val = int(d.get("estres", 0))
        descanso_val = int(d.get("descanso", 0))

        if estres_val >= 8:
            motivos.append("Estrés alto ≥ 8")
        if descanso_val < 30:
            motivos.append("Descanso insuficiente < 30 min")
        if d.get("estado") in ["Estresado", "Agotado"]:
            motivos.append(f"Estado emocional: {d.get('estado')}")

        if motivos:
            alerts.append({
                "sede": d.get("sede", ""),
                "nombre": d.get("nombre", ""),
                "motivo": ", ".join(motivos),
                "estres": estres_val,
                "fecha": d.get("fecha", "")
            })
    return alerts


# ==========================================
# KPI & GRÁFICOS
# ==========================================
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
    df["estres"] = pd.to_numeric(df.get("estres", 0), errors="coerce").fillna(0)
    df["descanso"] = pd.to_numeric(df.get("descanso", 0), errors="coerce").fillna(0)

    estres_prom = df["estres"].mean()
    pct_desc = (df["descanso"] >= 45).mean() * 100
    alerts = get_alerts(data)

    # ------ FIGURA SEMANAL ------
    fig_week = None
    try:
        df2 = df.copy()
        df2["fecha"] = pd.to_datetime(df2.get("fecha"), errors="coerce")
        df2 = df2.dropna(subset=["fecha"])
        if not df2.empty:
            maxd = df2["fecha"].max()
            start = maxd - pd.Timedelta(days=6)
            df_week = df2[df2["fecha"] >= start]
            if not df_week.empty:
                agg = df_week.groupby(df_week["fecha"].dt.date)["estres"].mean()
                fig_week, ax = plt.subplots()
                ax.bar(agg.index.astype(str), agg.values)
                ax.set_title("Estrés promedio últimos 7 días")
                plt.xticks(rotation=30)
                plt.tight_layout()
    except:
        fig_week = None

    # ------ PIE ------
    pie_estado = None
    try:
        counts = df["estado"].value_counts()
        if not counts.empty:
            pie_estado, ax2 = plt.subplots()
            ax2.pie(counts.values, labels=counts.index, autopct="%1.1f%%")
            ax2.set_title("Estado emocional")
            plt.tight_layout()
    except:
        pie_estado = None

    return {
        "estres_promedio": float(estres_prom),
        "pct_descanso": float(pct_desc),
        "alertas_count": len(alerts),
        "fig_week": fig_week,
        "pie_estado": pie_estado,
    }


# ==========================================
# PDF REPORTS
# ==========================================
def _safe_get_mean(df, col):
    if col not in df.columns:
        return 0
    return pd.to_numeric(df[col], errors="coerce").fillna(0).mean()


def generate_pdf_report(data):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(tmp.name, pagesize=letter)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, 750, "Reporte Starbucks — Datos filtrados")
    c.line(40, 745, 560, 745)

    if not data:
        c.drawString(40, 720, "No hay datos.")
        c.save()
        return tmp.name

    df = pd.DataFrame(data)
    estres_prom = _safe_get_mean(df, "estres")

    desc_df = pd.to_numeric(df.get("descanso", 0), errors="coerce").fillna(0)
    pct_desc = (desc_df >= 45).mean() * 100

    c.setFont("Helvetica", 12)
    c.drawString(40, 725, f"Estrés promedio: {estres_prom:.2f}")
    c.drawString(40, 710, f"% descansos ≥45 min: {pct_desc:.2f}%")

    headers = ["Fecha", "Sede", "Nombre", "Estrés"]
    x = [40, 140, 270, 450]

    y = 680
    c.setFont("Helvetica-Bold", 11)
    for h, xx in zip(headers, x):
        c.drawString(xx, y, h)
    y -= 15

    c.setFont("Helvetica", 9)
    for _, row in df.iterrows():
        c.drawString(x[0], y, str(row.get("fecha", "")))
        c.drawString(x[1], y, str(row.get("sede", "")))
        c.drawString(x[2], y, str(row.get("nombre", "")))
        c.drawString(x[3], y, str(row.get("estres", "")))
        y -= 12
        if y < 60:
            c.showPage()
            y = 750
            c.setFont("Helvetica-Bold", 11)
            for h, xx in zip(headers, x):
                c.drawString(xx, y, h)
            y -= 15
            c.setFont("Helvetica", 9)

    c.save()
    return tmp.name


def generate_pdf_report_by_sede(data, sede):
    df = pd.DataFrame([d for d in data if d.get("sede") == sede])

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(tmp.name, pagesize=letter)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, 750, f"Reporte Starbucks — Sede {sede}")
    c.line(40, 745, 560, 745)

    if df.empty:
        c.drawString(40, 720, "No hay datos para esta sede.")
        c.save()
        return tmp.name

    estres_prom = _safe_get_mean(df, "estres")
    desc_df = pd.to_numeric(df.get("descanso", 0), errors="coerce").fillna(0)
    pct_desc = (desc_df >= 45).mean() * 100

    c.setFont("Helvetica", 12)
    c.drawString(40, 725, f"Estrés promedio: {estres_prom:.2f}")
    c.drawString(40, 710, f"% descansos ≥45 min: {pct_desc:.2f}%")

    headers = ["Fecha", "Nombre", "Estrés"]
    x = [40, 180, 420]

    y = 680
    c.setFont("Helvetica-Bold", 11)
    for h, xx in zip(headers, x):
        c.drawString(xx, y, h)
    y -= 15

    c.setFont("Helvetica", 9)
    for _, row in df.iterrows():
        c.drawString(x[0], y, str(row.get("fecha", "")))
        c.drawString(x[1], y, str(row.get("nombre", "")))
        c.drawString(x[2], y, str(row.get("estres", "")))
        y -= 12

        if y < 60:
            c.showPage()
            y = 750
            c.setFont("Helvetica-Bold", 11)
            for h, xx in zip(headers, x):
                c.drawString(xx, y, h)
            y -= 15
            c.setFont("Helvetica", 9)

    c.save()
    return tmp.name
