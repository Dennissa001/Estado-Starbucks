import json
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from io import StringIO

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
import tempfile

# --------------------------------------------------------
# ---------------------- LOAD / SAVE ---------------------
# --------------------------------------------------------

def load_data(path="data.json"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_data(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_users(path="users.json"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

# --------------------------------------------------------
# ------------------------- AUTH -------------------------
# --------------------------------------------------------

def authenticate(username, password, users):
    for u in users:
        if u.get("username") == username and u.get("password") == password:
            return u
    return None

# --------------------------------------------------------
# ------------------- ADD ENTRY EMPLOYEE -----------------
# --------------------------------------------------------

def add_employee_entry(path, user, fecha, hora_inicio, hora_salida,
                       descanso_min, estres, estado, comentario=""):
    data = load_data(path)

    if hasattr(hora_inicio, "strftime"):
        hi = hora_inicio.strftime("%H:%M")
    else:
        hi = str(hora_inicio)

    if hasattr(hora_salida, "strftime"):
        hs = hora_salida.strftime("%H:%M")
    else:
        hs = str(hora_salida)

    entry = {
        "sede": user.get("sede", ""),
        "fecha": fecha,
        "nombre": user.get("nombre", user.get("username")),
        "hora_inicio": hi,
        "hora_salida": hs,
        "descanso": int(descanso_min),
        "estres": int(estres),
        "estado": estado,
        "comentario": comentario
    }

    data.append(entry)
    save_data(path, data)

# --------------------------------------------------------
# ---------------------- FILTER DATA ----------------------
# --------------------------------------------------------

def filter_data(data, fecha=None, sede=None):
    res = data
    if fecha:
        res = [d for d in res if d.get("fecha") == fecha]
    if sede:
        res = [d for d in res if d.get("sede") == sede]
    return res

# --------------------------------------------------------
# -------------------------- ALERTS -----------------------
# --------------------------------------------------------

def get_alerts(data):
    alerts = []
    if not data:
        return alerts

    df = pd.DataFrame(data)
    if "sede" not in df.columns:
        return alerts

    df = df.sort_values(by=["sede", "fecha", "nombre"])

    for _, row in df.iterrows():
        nombre = row.get("nombre", "")
        sede = row.get("sede", "")
        fecha = row.get("fecha", "")
        estres = row.get("estres", 0)
        descanso = row.get("descanso", 0)
        estado = row.get("estado", "")

        if int(estres) >= 8:
            alerts.append({
                "sede": sede, "nombre": nombre,
                "motivo": "Estrés muy alto (>=8)",
                "estres": estres, "fecha": fecha
            })

        try:
            if int(descanso) < 45:
                alerts.append({
                    "sede": sede, "nombre": nombre,
                    "motivo": f"Descanso insuficiente ({descanso} min)",
                    "estres": estres, "fecha": fecha
                })
        except:
            pass

        if str(estado).lower() in ["estresado", "agotado"]:
            alerts.append({
                "sede": sede,
                "nombre": nombre,
                "motivo": f"Estado emocional: {estado}",
                "estres": estres,
                "fecha": fecha
            })

    # Remove duplicates
    uniq = []
    seen = set()
    for a in alerts:
        k = (a["sede"], a["nombre"], a["motivo"], a["fecha"])
        if k not in seen:
            seen.add(k)
            uniq.append(a)

    return uniq

# --------------------------------------------------------
# -------------------- KPI + GRÁFICOS --------------------
# --------------------------------------------------------

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
    df["estres"] = pd.to_numeric(df["estres"], errors="coerce").fillna(0)
    df["descanso"] = pd.to_numeric(df["descanso"], errors="coerce").fillna(0)

    estres_prom = df["estres"].mean()
    pct_desc = (df["descanso"] >= 45).mean() * 100
    alerta_count = len(get_alerts(data))

    # Pie chart
    fig_pie = None
    try:
        if "estado" in df.columns:
            counts = df["estado"].value_counts()
            fig_pie, ax = plt.subplots(figsize=(4,4))
            ax.pie(counts.values, labels=counts.index, autopct="%1.1f%%")
            ax.set_title("Estado emocional")
    except:
        pass

    # Weekly trend
    fig_week = None
    try:
        df["fecha_dt"] = pd.to_datetime(df["fecha"])
        max_date = df["fecha_dt"].max()
        week_start = (max_date - pd.Timedelta(days=max_date.weekday())).normalize()
        week_end = week_start + pd.Timedelta(days=6)

        dfw = df[(df["fecha_dt"] >= week_start) & (df["fecha_dt"] <= week_end)]

        if not dfw.empty:
            series = dfw.groupby(dfw["fecha_dt"].dt.date)["estres"].mean()
            fig_week, ax = plt.subplots(figsize=(8,3))
            ax.bar(series.index.astype(str), series.values)
            plt.xticks(rotation=45)
    except:
        pass

    return {
        "estres_promedio": float(estres_prom),
        "pct_descanso": float(pct_desc),
        "alertas_count": alerta_count,
        "pie_estado": fig_pie,
        "fig_week": fig_week
    }

# --------------------------------------------------------
# ------------------ PDF por SEDE (nuevo) ----------------
# --------------------------------------------------------

def generate_pdf_by_sede(data, sede):
    """Genera un PDF con registros + alertas solo de la sede indicada."""

    df = pd.DataFrame([d for d in data if d.get("sede") == sede])
    alerts = [a for a in get_alerts(data) if a["sede"] == sede]

    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(temp_pdf.name, pagesize=letter)

    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, 750, f"Reporte por sede — {sede}")

    c.setFont("Helvetica", 12)
    c.drawString(40, 730, f"Total registros: {len(df)}")
    c.drawString(40, 715, f"Alertas: {len(alerts)}")
    c.line(40, 710, 560, 710)

    y = 690

    # --- REGISTROS ---
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, "Registros")
    y -= 20
    c.setFont("Helvetica", 10)

    if df.empty:
        c.drawString(40, y, "No hay registros para esta sede.")
        y -= 20
    else:
        df = df.sort_values(by=["fecha", "nombre"])
        for _, row in df.iterrows():
            text = (
                f"{row['fecha']} | {row['nombre']} | Inicio {row['hora_inicio']} | "
                f"Salida {row['hora_salida']} | Desc {row['descanso']} | "
                f"Estres {row['estres']} | {row['estado']}"
            )
            c.drawString(40, y, text)
            y -= 15
            if y < 80:
                c.showPage()
                y = 750

    # --- ALERTAS ---
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y - 10, "Alertas")
    y -= 30
    c.setFont("Helvetica", 10)

    if not alerts:
        c.drawString(40, y, "No hay alertas.")
    else:
        for a in alerts:
            txt = f"{a['fecha']} — {a['nombre']} — {a['motivo']} (estrés {a['estres']})"
            c.drawString(40, y, txt)
            y -= 15
            if y < 80:
                c.showPage()
                y = 750

    c.showPage()
    c.save()

    return temp_pdf.name

# --------------------------------------------------------
# ------------------ PDF GENERAL COMPLETO ----------------
# --------------------------------------------------------

def generate_pdf_report(data):
    """PDF general con gráficos y KPIs"""
    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(temp_pdf.name, pagesize=letter)

    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, 750, "Reporte general — Bienestar Starbucks")
    c.line(40, 740, 560, 740)

    df = pd.DataFrame(data)

    if df.empty:
        c.drawString(40, 720, "No hay datos.")
        c.save()
        return temp_pdf.name

    df["fecha_dt"] = pd.to_datetime(df["fecha"])
    estres_prom = df["estres"].mean()
    pct_desc = (df["descanso"] >= 45).mean() * 100

    c.setFont("Helvetica", 12)
    c.drawString(40, 720, f"Estrés promedio: {estres_prom:.1f}")
    c.drawString(40, 705, f"% descansos ≥ 45 min: {pct_desc:.1f}%")

    # Gráfico semanal
    try:
        max_date = df["fecha_dt"].max()
        week_start = (max_date - pd.Timedelta(days=max_date.weekday())).normalize()
        week_end = week_start + pd.Timedelta(days=6)
        dfw = df[(df["fecha_dt"] >= week_start) & (df["fecha_dt"] <= week_end)]

        if not dfw.empty:
            series = dfw.groupby(dfw["fecha_dt"].dt.date)["estres"].mean()

            fig, ax = plt.subplots(figsize=(4,3))
            ax.bar(series.index.astype(str), series.values)
            ax.set_title("Estrés semanal")
            plt.xticks(rotation=45)

            img = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            plt.savefig(img.name, bbox_inches="tight")
            plt.close()

            c.drawImage(img.name, 40, 400, width=500, height=250)
    except:
        pass

    # Pie chart
    try:
        counts = df["estado"].value_counts()
        fig2, ax2 = plt.subplots(figsize=(4,3))
        ax2.pie(counts.values, labels=counts.index, autopct="%1.1f%%")
        ax2.set_title("Estados emocionales")

        img2 = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        plt.savefig(img2.name, bbox_inches="tight")
        plt.close()

        c.drawImage(img2.name, 40, 150, width=450, height=200)
    except:
        pass

    c.showPage()
    c.save()

    return temp_pdf.name
