# utils.py
import json
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from io import StringIO

# PDF
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
import tempfile

# ----- IO -----
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

# ----- AUTH -----
def authenticate(username, password, users):
    for u in users:
        if u.get("username") == username and u.get("password") == password:
            return u
    return None

# ----- ADD ENTRY -----
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

# ----- FILTER SAFE -----
def filter_data(data, fecha=None, sede=None):
    # data is list[dict]
    res = data
    if fecha:
        res = [d for d in res if d.get("fecha") == fecha]
    if sede:
        res = [d for d in res if d.get("sede") == sede]
    return res

# ----- ALERTAS ORDENADAS -----
def get_alerts(data):
    alerts = []
    if not data:
        return alerts
    df = pd.DataFrame(data)
    # ensure columns
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
        # Estrés alto
        if int(estres) >= 8:
            alerts.append({"sede": sede, "nombre": nombre, "motivo": "Estrés muy alto (>=8)", "estres": estres, "fecha": fecha})
        # Descanso insuficiente (<45 min)
        try:
            if int(descanso) < 45:
                alerts.append({"sede": sede, "nombre": nombre, "motivo": f"Descanso insuficiente ({descanso} min)", "estres": estres, "fecha": fecha})
        except Exception:
            pass
        # Estado emocional crítico
        if str(estado).lower() in ["estresado", "agotado", "estresado 😣", "agotado 😫"]:
            alerts.append({"sede": sede, "nombre": nombre, "motivo": f"Estado emocional: {estado}", "estres": estres, "fecha": fecha})
    # dedupe exact duplicates
    seen = set()
    uniq = []
    for a in alerts:
        key = (a["sede"], a["nombre"], a["motivo"], a["fecha"])
        if key not in seen:
            seen.add(key)
            uniq.append(a)
    return uniq

# ----- KPIS y GRÁFICOS -----
def compute_kpis(data):
    if not data:
        return {
            "estres_promedio": 0.0,
            "pct_descanso": 0.0,
            "alertas_count": 0,
            "fig_week": None,
            "pie_estado": None,
            "fig_semana": None
        }
    df = pd.DataFrame(data)
    # convert types
    df["estres"] = pd.to_numeric(df["estres"], errors="coerce").fillna(0)
    df["descanso"] = pd.to_numeric(df["descanso"], errors="coerce").fillna(0)
    # KPIs
    estres_prom = float(df["estres"].mean())
    pct_descanso = float((df["descanso"] >= 45).mean() * 100)
    alertas = get_alerts(data)
    alert_count = len(alertas)
    # Pie chart (estado)
    fig_pie = None
    try:
        if "estado" in df.columns and not df["estado"].isna().all():
            counts = df["estado"].value_counts()
            fig_pie, axp = plt.subplots(figsize=(4,4))
            axp.pie(counts.values, labels=counts.index, autopct="%1.1f%%", startangle=140)
            axp.set_title("Estado emocional")
    except Exception:
        fig_pie = None
    # Weekly trend: last week by max date in data
    fig_week = None
    try:
        if "fecha" in df.columns:
            df["fecha_dt"] = pd.to_datetime(df["fecha"])
            max_date = df["fecha_dt"].max()
            week_start = (max_date - pd.Timedelta(days=max_date.weekday())).normalize()
            week_end = week_start + pd.Timedelta(days=6)
            mask = (df["fecha_dt"] >= week_start) & (df["fecha_dt"] <= week_end)
            df_week = df.loc[mask]
            if not df_week.empty:
                series = df_week.groupby(df_week["fecha_dt"].dt.date)["estres"].mean().reindex(
                    pd.date_range(week_start.date(), week_end.date(), freq="D").date, fill_value=0)
                fig_week, axw = plt.subplots(figsize=(8,3))
                axw.bar([d.strftime("%Y-%m-%d") for d in series.index], series.values)
                axw.set_title("Estrés promedio por día (última semana)")
                axw.set_xlabel("Fecha")
                axw.set_ylabel("Estrés promedio")
                plt.xticks(rotation=45)
    except Exception:
        fig_week = None
    return {
        "estres_promedio": estres_prom,
        "pct_descanso": pct_descanso,
        "alertas_count": alert_count,
        "pie_estado": fig_pie,
        "fig_week": fig_week
    }

# ----- CSV por sede (ordenado) -----
def generate_csv_report_by_sede(data, sede):
    if not data:
        return "".encode("utf-8")
    df = pd.DataFrame([d for d in data if d.get("sede") == sede])
    if df.empty:
        return "".encode("utf-8")
    # ensure columns
    cols = ["sede","fecha","nombre","hora_inicio","hora_salida","descanso","estres","estado","comentario"]
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    df = df[cols]
    df = df.sort_values(by=["sede","fecha","nombre"])
    buf = StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")

# --------------------------------------------------------
# --------  NUEVO: GENERADOR DE PDF COMPLETO -------------
# --------------------------------------------------------

def generate_pdf_report(data):
    """Genera un PDF profesional con KPIs, gráficos y resumen total."""

    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(temp_pdf.name, pagesize=letter)

    # Título
    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, 750, "Reporte general — Bienestar Starbucks")
    c.setFont("Helvetica", 12)
    c.drawString(40, 735, "Incluye todas las sedes y todos los registros")
    c.line(40, 730, 560, 730)

    df = pd.DataFrame(data)

    # KPIs
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, 710, "KPIs generales")

    if not df.empty:
        estres_prom = df["estres"].mean()
        pct_desc = (df["descanso"] >= 45).mean() * 100

        c.setFont("Helvetica", 12)
        c.drawString(40, 690, f"• Estrés promedio: {estres_prom:.2f}")
        c.drawString(40, 675, f"• % descansos ≥ 45 min: {pct_desc:.1f}%")
    else:
        c.drawString(40, 690, "No hay datos disponibles.")

    # ----------- GRÁFICA SEMANAL --------------
    if not df.empty:
        df["fecha_dt"] = pd.to_datetime(df["fecha"])
        max_date = df["fecha_dt"].max()
        week_start = (max_date - pd.Timedelta(days=max_date.weekday())).normalize()
        week_end = week_start + pd.Timedelta(days=6)

        df_week = df[(df["fecha_dt"] >= week_start) & (df["fecha_dt"] <= week_end)]

        if not df_week.empty:
            series = df_week.groupby(df_week["fecha_dt"].dt.date)["estres"].mean()

            fig, ax = plt.subplots(figsize=(4,3))
            ax.bar(series.index.astype(str), series.values)
            ax.set_title("Estrés semanal")
            plt.xticks(rotation=45)

            img = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            plt.savefig(img.name, bbox_inches="tight")
            plt.close()

            c.drawImage(img.name, 40, 430, width=500, height=230)

    # -------- PIE CHART ESTADO EMOCIONAL --------
    if not df.empty and "estado" in df.columns:
        counts = df["estado"].value_counts()

        fig2, ax2 = plt.subplots(figsize=(4,3))
        ax2.pie(counts.values, labels=counts.index, autopct="%1.1f%%")
        ax2.set_title("Estado emocional")

        img2 = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        plt.savefig(img2.name, bbox_inches="tight")
        plt.close()

        c.drawImage(img2.name, 40, 180, width=450, height=200)

    # Final PDF
    c.showPage()
    c.save()

    return temp_pdf.name
