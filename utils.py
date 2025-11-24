# utils.py
import json
from datetime import datetime, date, timedelta
import pandas as pd
import tempfile
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import matplotlib.pyplot as plt
import os

# -----------------------------
# Helpers JSON
# -----------------------------
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

# -----------------------------
# Add entry
# -----------------------------
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

# -----------------------------
# Filters & alerts
# -----------------------------
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

# -----------------------------
# KPIs & Charts
# -----------------------------
def compute_kpis(data):
    """
    Devuelve: estres_promedio, pct_descanso, alertas_count, fig_week (matplotlib.Figure or None),
    pie_estado (Figure or None)
    """
    if not data:
        return {
            "estres_promedio": 0.0,
            "pct_descanso": 0.0,
            "alertas_count": 0,
            "fig_week": None,
            "pie_estado": None
        }

    df = pd.DataFrame(data)

    # safe numeric
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

    # FIG: weekly bar (last 7 days)
    fig_week = None
    try:
        if "fecha" in df.columns:
            df_dates = df.copy()
            df_dates["fecha"] = pd.to_datetime(df_dates["fecha"], errors="coerce")
            df_dates = df_dates.dropna(subset=["fecha"])
            if not df_dates.empty:
                maxd = df_dates["fecha"].max()
                start = maxd - pd.Timedelta(days=6)
                df_week = df_dates[df_dates["fecha"] >= start]
                if not df_week.empty:
                    agg = df_week.groupby(df_week["fecha"].dt.date)["estres"].mean().sort_index()
                    fig_week, ax = plt.subplots()
                    ax.bar(agg.index.astype(str), agg.values)
                    ax.set_title("Estrés promedio (últimos 7 días)")
                    ax.set_xlabel("Fecha")
                    ax.set_ylabel("Promedio estrés")
                    plt.xticks(rotation=45)
                    plt.tight_layout()
    except Exception:
        fig_week = None

    # PIE: estado
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

# -----------------------------
# PDF helpers
# -----------------------------
def _safe_get_mean(df, col):
    if col not in df.columns:
        return 0.0
    try:
        return pd.to_numeric(df[col], errors="coerce").fillna(0).mean()
    except Exception:
        return 0.0

def _draw_table_paginated(c, df, headers, x_positions, y_start=650, line_height=12, font="Helvetica", font_size=9):
    """Dibuja toda la tabla en el canvas c, paginando cuando y < 60"""
    y = y_start
    c.setFont(font, font_size)
    for _, row in df.iterrows():
        for h, x in zip(headers, x_positions):
            c.drawString(x, y, str(row.get(h, "")))
        y -= line_height
        if y < 60:
            c.showPage()
            y = y_start
            c.setFont("Helvetica-Bold", font_size+2)
            for h, x in zip(headers, x_positions):
                c.drawString(x, y, h)
            y -= (line_height + 3)
            c.setFont(font, font_size)
    return

# -----------------------------
# PDF: full data (ALL rows)
# -----------------------------
def generate_pdf_full(data):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(tmp.name, pagesize=letter)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, 770, "Reporte — Bienestar Starbucks (Datos)")
    c.line(40, 765, 560, 765)

    if not data:
        c.setFont("Helvetica", 12)
        c.drawString(40, 740, "No hay datos.")
        c.showPage()
        c.save()
        return tmp.name

    df = pd.DataFrame(data)

    estres_prom = _safe_get_mean(df, "estres")
    pct_desc = 0.0
    if "descanso" in df.columns:
        try:
            pct_desc = (pd.to_numeric(df["descanso"], errors="coerce").fillna(0) >= 45).mean() * 100
        except Exception:
            pct_desc = 0.0

    c.setFont("Helvetica", 12)
    c.drawString(40, 740, f"Estrés promedio: {estres_prom:.2f}")
    c.drawString(40, 725, f"% descansos ≥ 45 min: {pct_desc:.1f}%")

    # Table header + all rows (paginar)
    headers = ["fecha", "sede", "nombre", "estres"]
    x_positions = [40, 160, 300, 480]

    # draw header
    y = 700
    c.setFont("Helvetica-Bold", 11)
    for h, x in zip(headers, x_positions):
        c.drawString(x, y, h.capitalize())
    y -= 15

    # body
    c.setFont("Helvetica", 9)
    for _, row in df.iterrows():
        c.drawString(x_positions[0], y, str(row.get("fecha", "")))
        c.drawString(x_positions[1], y, str(row.get("sede", ""))[:25])
        c.drawString(x_positions[2], y, str(row.get("nombre", ""))[:30])
        c.drawString(x_positions[3], y, str(row.get("estres", "")))
        y -= 12
        if y < 60:
            c.showPage()
            y = 700
            c.setFont("Helvetica-Bold", 11)
            for h, x in zip(headers, x_positions):
                c.drawString(x, y, h.capitalize())
            y -= 15
            c.setFont("Helvetica", 9)

    c.showPage()
    c.save()
    return tmp.name

# -----------------------------
# PDF: alerts (alerts is list of dicts with keys: sede,nombre,motivo,estres,fecha)
# -----------------------------
def generate_pdf_alerts(alerts):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(tmp.name, pagesize=letter)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, 770, "Reporte — Alertas")
    c.line(40, 765, 560, 765)

    if not alerts:
        c.setFont("Helvetica", 12)
        c.drawString(40, 740, "No se detectaron alertas.")
        c.showPage()
        c.save()
        return tmp.name

    df = pd.DataFrame(alerts)

    c.setFont("Helvetica", 12)
    c.drawString(40, 740, f"Alertas encontradas: {len(df)}")

    headers = ["fecha", "sede", "nombre", "motivo", "estres"]
    x_positions = [40, 140, 260, 360, 520]

    y = 710
    c.setFont("Helvetica-Bold", 11)
    for h, x in zip(headers, x_positions):
        c.drawString(x, y, h.capitalize())
    y -= 15

    c.setFont("Helvetica", 9)
    for _, row in df.iterrows():
        c.drawString(x_positions[0], y, str(row.get("fecha", "")))
        c.drawString(x_positions[1], y, str(row.get("sede", ""))[:20])
        c.drawString(x_positions[2], y, str(row.get("nombre", ""))[:20])
        c.drawString(x_positions[3], y, str(row.get("motivo", ""))[:60])
        c.drawString(x_positions[4], y, str(row.get("estres", "")))
        y -= 12
        if y < 60:
            c.showPage()
            y = 710
            c.setFont("Helvetica-Bold", 11)
            for h, x in zip(headers, x_positions):
                c.drawString(x, y, h.capitalize())
            y -= 15
            c.setFont("Helvetica", 9)

    c.showPage()
    c.save()
    return tmp.name

# -----------------------------
# PDF: charts (genera imágenes de las figuras y las inserta en un PDF)
# -----------------------------
def generate_pdf_charts(data):
    """
    Genera un PDF que contiene las gráficas: fig_week y pie_estado.
    Si una figura no existe, la omite.
    """
    kpis = compute_kpis(data)
    figs = []
    tmp_images = []

    # collect figures (fig_week, pie_estado)
    if kpis.get("fig_week"):
        figs.append(kpis["fig_week"])
    if kpis.get("pie_estado"):
        figs.append(kpis["pie_estado"])

    # if no figures, generar PDF que diga "no hay graficas"
    tmp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(tmp_pdf.name, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, 770, "Gráficas — Bienestar Starbucks")
    c.line(40, 765, 560, 765)

    if not figs:
        c.setFont("Helvetica", 12)
        c.drawString(40, 740, "No hay gráficas disponibles para los filtros seleccionados.")
        c.showPage()
        c.save()
        return tmp_pdf.name

    # Save each figure to a temporary PNG and draw it
    y_pos = 650
    for fig in figs:
        # Save fig to temp png
        tmp_img = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        try:
            fig.savefig(tmp_img.name, bbox_inches="tight")
            plt.close(fig)
        except Exception:
            try:
                plt.close(fig)
            except:
                pass
            tmp_img.close()
            os.unlink(tmp_img.name)
            continue

        tmp_images.append(tmp_img.name)
        # Insert image on PDF page (resize to fit)
        # If y_pos too low, create new page
        if y_pos < 200:
            c.showPage()
            y_pos = 650
        # Draw image with width 500 and height auto (approx)
        try:
            c.drawImage(tmp_img.name, 40, y_pos - 250, width=520, height=250)
        except Exception:
            # fallback draw smaller
            try:
                c.drawImage(tmp_img.name, 40, y_pos - 200, width=400, height=200)
            except Exception:
                pass
        y_pos -= 280

    c.showPage()
    c.save()

    # cleanup tmp images
    for p in tmp_images:
        try:
            os.unlink(p)
        except Exception:
            pass

    return tmp_pdf.name

# -----------------------------
# PDF: report by sede
# -----------------------------
def generate_pdf_by_sede(data, sede):
    df = pd.DataFrame([d for d in data if d.get("sede") == sede])

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(tmp.name, pagesize=letter)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, 770, f"Reporte — Sede {sede}")
    c.line(40, 765, 560, 765)

    if df.empty:
        c.setFont("Helvetica", 12)
        c.drawString(40, 740, "No hay datos para esta sede.")
        c.showPage()
        c.save()
        return tmp.name

    estres_prom = _safe_get_mean(df, "estres")
    pct_desc = 0.0
    if "descanso" in df.columns:
        try:
            pct_desc = (pd.to_numeric(df["descanso"], errors="coerce").fillna(0) >= 45).mean() * 100
        except Exception:
            pct_desc = 0.0

    c.setFont("Helvetica", 12)
    c.drawString(40, 740, f"Estrés promedio: {estres_prom:.2f}")
    c.drawString(40, 725, f"% descansos ≥45 min: {pct_desc:.1f}%")

    headers = ["fecha", "nombre", "estres"]
    x_positions = [40, 200, 480]

    y = 700
    c.setFont("Helvetica-Bold", 11)
    for h, x in zip(headers, x_positions):
        c.drawString(x, y, h.capitalize())
    y -= 15

    c.setFont("Helvetica", 9)
    for _, row in df.iterrows():
        c.drawString(x_positions[0], y, str(row.get("fecha", "")))
        c.drawString(x_positions[1], y, str(row.get("nombre", ""))[:30])
        c.drawString(x_positions[2], y, str(row.get("estres", "")))
        y -= 12
        if y < 60:
            c.showPage()
            y = 700
            c.setFont("Helvetica-Bold", 11)
            for h, x in zip(headers, x_positions):
                c.drawString(x, y, h.capitalize())
            y -= 15
            c.setFont("Helvetica", 9)

    c.showPage()
    c.save()
    return tmp.name

# -----------------------------
# PDF: personal (mis registros)
# -----------------------------
def generate_pdf_personal(data):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(tmp.name, pagesize=letter)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, 770, "Mis registros — Bienestar Starbucks")
    c.line(40, 765, 560, 765)

    if not data:
        c.setFont("Helvetica", 12)
        c.drawString(40, 740, "No hay registros personales.")
        c.showPage()
        c.save()
        return tmp.name

    df = pd.DataFrame(data)

    headers = ["fecha", "sede", "hora_inicio", "hora_salida", "descanso", "estres", "estado", "comentario"]
    x_positions = [40, 120, 220, 300, 380, 440, 480, 520]

    y = 720
    c.setFont("Helvetica-Bold", 10)
    for h, x in zip(headers, x_positions):
        c.drawString(x, y, h.capitalize())
    y -= 15

    c.setFont("Helvetica", 9)
    for _, row in df.iterrows():
        c.drawString(x_positions[0], y, str(row.get("fecha", "")))
        c.drawString(x_positions[1], y, str(row.get("sede", ""))[:12])
        c.drawString(x_positions[2], y, str(row.get("hora_inicio", ""))[:8])
        c.drawString(x_positions[3], y, str(row.get("hora_salida", ""))[:8])
        c.drawString(x_positions[4], y, str(row.get("descanso", "")))
        c.drawString(x_positions[5], y, str(row.get("estres", "")))
        c.drawString(x_positions[6], y, str(row.get("estado", ""))[:10])
        c.drawString(x_positions[7], y, str(row.get("comentario", ""))[:50])
        y -= 12
        if y < 60:
            c.showPage()
            y = 720
            c.setFont("Helvetica-Bold", 10)
            for h, x in zip(headers, x_positions):
                c.drawString(x, y, h.capitalize())
            y -= 15
            c.setFont("Helvetica", 9)

    c.showPage()
    c.save()
    return tmp.name
