# utils.py
import json
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from io import StringIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import tempfile

# ---------- IO ----------
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

# ---------- AUTH ----------
def authenticate(username, password, users):
    for u in users:
        if u.get("username") == username and u.get("password") == password:
            return u
    return None

# ---------- ADD ENTRY ----------
def add_employee_entry(path, user, fecha, hora_inicio, hora_salida, descanso_min, estres, estado, comentario=""):
    data = load_data(path)
    # hora_inicio/hora_salida may be time objects or strings
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

# ---------- FILTER ----------
def filter_data(data, fecha=None, sede=None):
    # data is list[dict]
    res = data
    if fecha:
        # accept date or string
        s = fecha if isinstance(fecha, str) else fecha.strftime("%Y-%m-%d")
        res = [d for d in res if d.get("fecha") == s]
    if sede and sede != "Todas":
        res = [d for d in res if d.get("sede") == sede]
    return res

# ---------- ALERTAS ----------
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
        try:
            if int(estres) >= 8:
                alerts.append({"sede": sede, "nombre": nombre, "motivo": "Estrés muy alto (>=8)", "estres": estres, "fecha": fecha})
        except:
            pass
        try:
            if int(descanso) < 45:
                alerts.append({"sede": sede, "nombre": nombre, "motivo": f"Descanso insuficiente ({descanso} min)", "estres": estres, "fecha": fecha})
        except:
            pass
        if str(estado).lower() in ["estresado", "agotado", "estresado 😣", "agotado 😫"]:
            alerts.append({"sede": sede, "nombre": nombre, "motivo": f"Estado emocional: {estado}", "estres": estres, "fecha": fecha})
    # dedupe
    seen = set()
    uniq = []
    for a in alerts:
        key = (a["sede"], a["nombre"], a["motivo"], a["fecha"])
        if key not in seen:
            seen.add(key)
            uniq.append(a)
    return uniq

# ---------- KPIS y GRÁFICOS ----------
def compute_kpis(data):
    if not data:
        return {"estres_promedio": 0.0, "pct_descanso": 0.0, "alertas_count": 0, "pie_estado": None, "fig_week": None}
    df = pd.DataFrame(data)
    df["estres"] = pd.to_numeric(df.get("estres", 0), errors="coerce").fillna(0)
    df["descanso"] = pd.to_numeric(df.get("descanso", 0), errors="coerce").fillna(0)
    estres_prom = float(df["estres"].mean()) if not df.empty else 0.0
    pct_desc = float((df["descanso"] >= 45).mean() * 100) if not df.empty else 0.0
    alert_count = len(get_alerts(data))
    # pie
    fig_pie = None
    try:
        if "estado" in df.columns and not df["estado"].isna().all():
            counts = df["estado"].value_counts()
            fig_pie, ax = plt.subplots(figsize=(4,4))
            ax.pie(counts.values, labels=counts.index, autopct="%1.1f%%")
            ax.set_title("Estado emocional")
    except:
        fig_pie = None
    # weekly
    fig_week = None
    try:
        if "fecha" in df.columns:
            df["fecha_dt"] = pd.to_datetime(df["fecha"], errors="coerce")
            max_date = df["fecha_dt"].max()
            week_start = (max_date - pd.Timedelta(days=max_date.weekday())).normalize()
            week_end = week_start + pd.Timedelta(days=6)
            dfw = df[(df["fecha_dt"] >= week_start) & (df["fecha_dt"] <= week_end)]
            if not dfw.empty:
                series = dfw.groupby(dfw["fecha_dt"].dt.date)["estres"].mean()
                fig_week, axw = plt.subplots(figsize=(8,3))
                axw.bar([d.strftime("%Y-%m-%d") for d in series.index], series.values)
                axw.set_title("Estrés promedio por día (última semana)")
                axw.set_xlabel("Fecha")
                axw.set_ylabel("Estrés promedio")
                plt.xticks(rotation=45)
    except:
        fig_week = None
    return {"estres_promedio": estres_prom, "pct_descanso": pct_desc, "alertas_count": alert_count, "pie_estado": fig_pie, "fig_week": fig_week}

# ---------- PDF por SEDE (registros + alertas) ----------
def generate_pdf_by_sede(data, sede):
    """Genera PDF con registros + alertas de la sede"""
    df = pd.DataFrame([d for d in data if d.get("sede") == sede])
    alerts = [a for a in get_alerts(data) if a["sede"] == sede]

    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(temp_pdf.name, pagesize=letter)
    x_margin = 40
    y = 750

    c.setFont("Helvetica-Bold", 16)
    c.drawString(x_margin, y, f"Reporte por sede — {sede}")
    y -= 20
    c.setFont("Helvetica", 11)
    c.drawString(x_margin, y, f"Fecha generación: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    y -= 20
    c.line(x_margin, y, 560, y)
    y -= 20

    # Registros
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x_margin, y, "Registros")
    y -= 18
    c.setFont("Helvetica", 10)
    if df.empty:
        c.drawString(x_margin, y, "No hay registros.")
        y -= 20
    else:
        df = df.sort_values(by=["fecha", "nombre"])
        for _, row in df.iterrows():
            line = f"{row.get('fecha','')} | {row.get('nombre','')} | {row.get('hora_inicio','')}-{row.get('hora_salida','')} | Desc: {row.get('descanso','')} | Estres: {row.get('estres','')} | {row.get('estado','')}"
            c.drawString(x_margin, y, line[:120])
            y -= 14
            if y < 80:
                c.showPage()
                y = 750

    y -= 10
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x_margin, y, "Alertas")
    y -= 18
    c.setFont("Helvetica", 10)
    if not alerts:
        c.drawString(x_margin, y, "No hay alertas.")
        y -= 20
    else:
        for a in alerts:
            txt = f"{a.get('fecha','')} — {a.get('nombre','')} — {a.get('motivo','')} (estrés {a.get('estres','')})"
            c.drawString(x_margin, y, txt[:120])
            y -= 14
            if y < 80:
                c.showPage()
                y = 750

    c.showPage()
    c.save()
    return temp_pdf.name

# ---------- PDF general (KPIs + gráficas + resumen) ----------
def generate_pdf_report(data):
    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(temp_pdf.name, pagesize=letter)
    x_margin = 40
    y = 760

    c.setFont("Helvetica-Bold", 18)
    c.drawString(x_margin, y, "Reporte general — Bienestar Starbucks")
    y -= 30

    df = pd.DataFrame(data)
    c.setFont("Helvetica", 11)
    if df.empty:
        c.drawString(x_margin, y, "No hay datos disponibles.")
        c.showPage()
        c.save()
        return temp_pdf.name

    # KPIs
    df["estres"] = pd.to_numeric(df.get("estres", 0), errors="coerce").fillna(0)
    df["descanso"] = pd.to_numeric(df.get("descanso", 0), errors="coerce").fillna(0)
    estres_prom = df["estres"].mean()
    pct_desc = (df["descanso"] >= 45).mean() * 100

    c.drawString(x_margin, y, f"Estrés promedio: {estres_prom:.2f}")
    y -= 16
    c.drawString(x_margin, y, f"% descansos ≥ 45 min: {pct_desc:.1f}%")
    y -= 24

    # Gráfica semanal (guardar imagen temporal y pegar)
    try:
        df["fecha_dt"] = pd.to_datetime(df["fecha"], errors="coerce")
        max_date = df["fecha_dt"].max()
        week_start = (max_date - pd.Timedelta(days=max_date.weekday())).normalize()
        week_end = week_start + pd.Timedelta(days=6)
        dfw = df[(df["fecha_dt"] >= week_start) & (df["fecha_dt"] <= week_end)]
        if not dfw.empty:
            series = dfw.groupby(dfw["fecha_dt"].dt.date)["estres"].mean()
            fig, ax = plt.subplots(figsize=(6,3))
            ax.bar(series.index.astype(str), series.values)
            ax.set_title("Estrés semanal")
            plt.xticks(rotation=45)
            img = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            plt.savefig(img.name, bbox_inches="tight")
            plt.close()
            c.drawImage(img.name, x_margin, y-200, width=500, height=180)
            y -= 220
    except:
        pass

    # Pie chart
    try:
        if "estado" in df.columns:
            counts = df["estado"].value_counts()
            fig2, ax2 = plt.subplots(figsize=(4,3))
            ax2.pie(counts.values, labels=counts.index, autopct="%1.1f%%")
            ax2.set_title("Estados emocionales")
            img2 = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            plt.savefig(img2.name, bbox_inches="tight")
            plt.close()
            c.drawImage(img2.name, x_margin, y-200, width=300, height=180)
            y -= 200
    except:
        pass

    c.showPage()
    c.save()
    return temp_pdf.name

