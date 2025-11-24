# utils.py
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
# FILTERS / ALERTS / ORDERED DF
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
        try:
            estres_val = int(d.get("estres", 0))
        except Exception:
            estres_val = 0
        try:
            descanso_val = int(d.get("descanso", 0))
        except Exception:
            descanso_val = 0

        if estres_val >= 8:
            motivos.append("Estrés alto ≥ 8")
        if descanso_val < 30:
            motivos.append("Descanso insuficiente < 30 min")
        if d.get("estado", "") in ["Estresado", "Agotado"]:
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
# KPIS & GRÁFICAS
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

    # SAFE numeric conversion
    if "estres" in df.columns:
        df["estres"] = pd.to_numeric(df["estres"], errors="coerce").fillna(0)
    else:
        df["estres"] = 0

    if "descanso" in df.columns:
        df["descanso"] = pd.to_numeric(df["descanso"], errors="coerce").fillna(0)
    else:
        df["descanso"] = 0

    estres_prom = df["estres"].mean() if not df.empty else 0.0
    pct_desc = (df["descanso"] >= 45).mean() * 100 if not df.empty else 0.0
    alerts = get_alerts(data)

    # =======================
    # FIGURA: estrés últimos 7 días
    # =======================
    fig_week = None
    try:
        df_dates = df.copy()
        if "fecha" in df_dates.columns:
            df_dates["fecha"] = pd.to_datetime(df_dates["fecha"], errors="coerce")
            df_dates = df_dates.dropna(subset=["fecha"])
            if not df_dates.empty:
                max_date = df_dates["fecha"].max()
                start_date = max_date - pd.Timedelta(days=6)
                df_week = df_dates[df_dates["fecha"] >= start_date]
                if not df_week.empty:
                    agg = df_week.groupby(df_week["fecha"].dt.date)["estres"].mean().sort_index()
                    fig_week, ax = plt.subplots()
                    ax.bar(agg.index.astype(str), agg.values)
                    ax.set_xlabel("Fecha")
                    ax.set_ylabel("Promedio nivel de estrés")
                    ax.set_title("Estrés promedio (últimos 7 días)")
                    plt.xticks(rotation=45)
                    plt.tight_layout()
    except Exception:
        fig_week = None

    # =======================
    # FIGURA: estados emocionales
    # =======================
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


# ==========================================
# PDF REPORTS (robusto y con paginación)
# ==========================================
def _safe_get_mean(df, col):
    if col in df.columns:
        try:
            return df[col].mean()
        except Exception:
            try:
                return pd.to_numeric(df[col], errors="coerce").fillna(0).mean()
            except Exception:
                return 0
    return 0

def generate_pdf_report(data):
    """
    Genera un PDF con TODOS los registros (no solo los primeros).
    Maneja la ausencia de columnas (ej. alerts no tiene 'descanso').
    """
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

    # safe KPI calculations
    estres_prom = _safe_get_mean(df, "estres")
    pct_desc = 0
    if "descanso" in df.columns:
        try:
            pct_desc = (pd.to_numeric(df["descanso"], errors="coerce").fillna(0) >= 45).mean() * 100
        except Exception:
            pct_desc = 0

    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, 720, "KPIs generales:")
    c.setFont("Helvetica", 12)
    c.drawString(40, 700, f"• Estrés promedio: {estres_prom:.2f}")
    c.drawString(40, 685, f"• % descansos ≥ 45 min: {pct_desc:.1f}%")

    # Table header
    c.setFont("Helvetica-Bold", 12)
    y = 650
    headers = ["Fecha", "Sede", "Nombre", "Estrés"]
    x_positions = [40, 140, 260, 420]
    for h, x in zip(headers, x_positions):
        c.drawString(x, y, h)
    y -= 15
    c.setFont("Helvetica", 10)

    # Iterate ALL rows and paginate when needed
    for _, row in df.iterrows():
        fecha = str(row.get("fecha", ""))
        sede = str(row.get("sede", ""))
        nombre = str(row.get("nombre", ""))[:30]
        estres_val = row.get("estres", "")
        c.drawString(x_positions[0], y, fecha)
        c.drawString(x_positions[1], y, sede[:20])
        c.drawString(x_positions[2], y, nombre)
        c.drawString(x_positions[3], y, str(estres_val))
        y -= 12
        if y < 60:
            c.showPage()
            y = 750
            c.setFont("Helvetica-Bold", 12)
            for h, x in zip(headers, x_positions):
                c.drawString(x, y, h)
            y -= 15
            c.setFont("Helvetica", 10)

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

    estres_prom = _safe_get_mean(df, "estres")
    pct_desc = 0
    if "descanso" in df.columns:
        try:
            pct_desc = (pd.to_numeric(df["descanso"], errors="coerce").fillna(0) >= 45).mean() * 100
        except Exception:
            pct_desc = 0

    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, 720, "KPIs:")
    c.setFont("Helvetica", 12)
    c.drawString(40, 700, f"• Estrés promedio: {estres_prom:.2f}")
    c.drawString(40, 685, f"• % descansos ≥ 45 min: {pct_desc:.1f}%")

    # Table per sede (ALL rows)
    c.setFont("Helvetica-Bold", 12)
    y = 650
    headers = ["Fecha", "Nombre", "Estrés"]
    x_positions = [40, 160, 400]
    for h, x in zip(headers, x_positions):
        c.drawString(x, y, h)
    y -= 15
    c.setFont("Helvetica", 10)

    for _, row in df.iterrows():
        c.drawString(x_positions[0], y, str(row.get("fecha", "")))
        c.drawString(x_positions[1], y, str(row.get("nombre", ""))[:30])
        c.drawString(x_positions[2], y, str(row.get("estres", "")))
        y -= 12
        if y < 60:
            c.showPage()
            y = 750
            c.setFont("Helvetica-Bold", 12)
            for h, x in zip(headers, x_positions):
                c.drawString(x, y, h)
            y -= 15
            c.setFont("Helvetica", 10)

    c.showPage()
    c.save()
    return tmp.name
