import json
from datetime import datetime, date
import pandas as pd
import tempfile
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import matplotlib.pyplot as plt


# =======================
# CARGA / GUARDADO DATA
# =======================

def load_data(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def save_data(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_users(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def authenticate(username, password, users):
    for u in users:
        if u["username"] == username and u["password"] == password:
            return u
    return None


# =======================
# REGISTRO DE EMPLEADOS
# =======================

def add_employee_entry(path, user, fecha, hora_inicio, hora_salida, descanso, estres, estado, comentario):
    data = load_data(path)

    entry = {
        "nombre": user.get("username", ""),
        "sede": user.get("sede", ""),
        "fecha": fecha,
        "hora_inicio": hora_inicio.strftime("%H:%M"),
        "hora_salida": hora_salida.strftime("%H:%M"),
        "descanso": descanso,
        "estres": estres,
        "estado": estado,
        "comentario": comentario.strip() if comentario else ""
    }

    data.append(entry)
    save_data(path, data)


# =======================
# FILTROS
# =======================

def filter_data(data, fecha=None, sede=None):
    filtered = data

    if fecha:
        filtered = [d for d in filtered if d.get("fecha") == fecha]

    if sede:
        filtered = [d for d in filtered if d.get("sede") == sede]

    return filtered


# =======================
# KPIs
# =======================

def compute_kpis(data):
    if not data:
        return {
            "estres_promedio": 0,
            "pct_descanso": 0,
            "alertas_count": 0
        }

    df = pd.DataFrame(data)

    estres_prom = df["estres"].mean()
    pct_descanso = (df["descanso"] >= 45).mean() * 100

    alertas = get_alerts(data)

    return {
        "estres_promedio": float(estres_prom),
        "pct_descanso": float(pct_descanso),
        "alertas_count": len(alertas)
    }


# =======================
# ALERTAS
# =======================

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


# ==========================================================
# DATAFRAME ORDENADO (para tablas en el panel administrador)
# ==========================================================

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


# =======================
# PDF GENERAL
# =======================

def generate_pdf_report(data):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(tmp.name, pagesize=letter)

    c.setFont("Helvetica-Bold", 20)
    c.drawString(40, 750, "Reporte General — Bienestar Starbucks")
    c.line(40, 745, 560, 745)

    if not data:
        c.drawString(40, 720, "No hay datos disponibles.")
        c.showPage()
        c.save()
        return tmp.name

    df = pd.DataFrame(data)

    # KPIs
    estres_prom = df["estres"].mean()
    pct_desc = (df["descanso"] >= 45).mean() * 100

    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, 720, "KPIs Generales:")

    c.setFont("Helvetica", 12)
    c.drawString(40, 700, f"• Estrés promedio: {estres_prom:.2f}")
    c.drawString(40, 685, f"• % descansos ≥ 45 min: {pct_desc:.1f}%")

    # PIE Chart
    counts = df["estado"].value_counts()
    fig, ax = plt.subplots(figsize=(4,3))
    ax.pie(counts.values, labels=counts.index, autopct="%1.1f%%")
    ax.set_title("Estado emocional")

    img = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    plt.savefig(img.name, bbox_inches="tight")
    plt.close()

    c.drawImage(img.name, 40, 420, width=450, height=230)

    c.showPage()
    c.save()

    return tmp.name


# =======================
# PDF POR SEDE
# =======================

def generate_pdf_report_by_sede(data, sede):
    df = pd.DataFrame([d for d in data if d.get("sede") == sede])

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(tmp.name, pagesize=letter)

    c.setFont("Helvetica-Bold", 20)
    c.drawString(40, 750, f"Reporte — Sede {sede}")
    c.line(40, 745, 560, 745)

    if df.empty:
        c.setFont("Helvetica", 12)
        c.drawString(40, 720, "No hay datos para esta sede.")
        c.showPage()
        c.save()
        return tmp.name

    # KPIs
    estres_prom = df["estres"].mean()
    pct_desc = (df["descanso"] >= 45).mean() * 100

    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, 720, "KPIs:")

    c.setFont("Helvetica", 12)
    c.drawString(40, 700, f"• Estrés promedio: {estres_prom:.2f}")
    c.drawString(40, 685, f"• % descansos ≥ 45 min: {pct_desc:.1f}%")

    # PIE chart
    counts = df["estado"].value_counts()
    fig, ax = plt.subplots(figsize=(4,3))
    ax.pie(counts.values, labels=counts.index, autopct="%1.1f%%")
    ax.set_title("Estado emocional")

    img = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    plt.savefig(img.name, bbox_inches="tight")
    plt.close()

    c.drawImage(img.name, 40, 420, width=450, height=230)

    c.showPage()
    c.save()
    return tmp.name
