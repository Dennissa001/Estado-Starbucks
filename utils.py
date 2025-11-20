import json
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from io import StringIO


# ---- Cargar y guardar ----
def load_data(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return []


def save_data(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


def load_users(path):
    with open(path, "r") as f:
        return json.load(f)


# ---- Login ----
def authenticate(username, password, users):
    for u in users:
        if u["username"] == username and u["password"] == password:
            return u
    return None


# ---- Registro empleado ----
def add_employee_entry(path, user, hi, hs, descanso, motivo, estres, estado, comentario):
    data = load_data(path)

    entry = {
        "nombre": user["username"],
        "sede": user["sede"],
        "fecha": str(datetime.now().date()),
        "hora_inicio": hi.strftime("%H:%M"),
        "hora_salida": hs.strftime("%H:%M"),
        "descanso": descanso,
        "motivo": motivo if not descanso else "",
        "estres": estres,
        "estado": estado,
        "comentario": comentario
    }

    data.append(entry)
    save_data(path, data)


# ---- Filtros ----
def filter_data(data, fecha=None, sede=None):
    f = data
    if fecha:
        f = [d for d in f if d["fecha"] == fecha]
    if sede:
        f = [d for d in f if d["sede"] == sede]
    return f


# ---- KPIs ----
def compute_kpis(data):
    if not data:
        return {
            "estres_promedio": 0,
            "pct_descanso": 0,
            "alertas_count": 0,
            "pie_estado": None,
            "fig_semana": None
        }

    df = pd.DataFrame(data)

    estres_prom = df["estres"].mean()
    pct_descanso = (df["descanso"].mean()) * 100

    # ---- Alertas ----
    alertas = df[(df["estres"] >= 8) | (df["descanso"] == False)]

    # ---- Pie chart ----
    fig_pie = None
    try:
        fig_pie, ax = plt.subplots()
        df["estado"].value_counts().plot.pie(autopct="%1.1f%%", ax=ax)
        ax.set_ylabel("")
    except:
        fig_pie = None

    # ---- Tendencia semanal ----
    fig_semana = None
    try:
        df["fecha"] = pd.to_datetime(df["fecha"])
        df["semana"] = df["fecha"].dt.isocalendar().week
        sem = df.groupby("semana")["estres"].mean()

        fig_semana, ax = plt.subplots()
        sem.plot(kind="bar", ax=ax)
        ax.set_title("Estrés promedio por semana")
        ax.set_ylabel("Estrés")
        ax.set_xlabel("Semana")
    except:
        fig_semana = None

    return {
        "estres_promedio": estres_prom,
        "pct_descanso": pct_descanso,
        "alertas_count": len(alertas),
        "pie_estado": fig_pie,
        "fig_semana": fig_semana
    }


# ---- Alertas detalladas ----
def get_alerts(data):
    alerts = []
    for d in data:
        if d["estres"] >= 8:
            alerts.append({
                "nombre": d["nombre"],
                "sede": d["sede"],
                "fecha": d["fecha"],
                "estres": d["estres"],
                "motivo": "Alto estrés (≥ 8)"
            })
        if not d["descanso"]:
            alerts.append({
                "nombre": d["nombre"],
                "sede": d["sede"],
                "fecha": d["fecha"],
                "estres": d["estres"],
                "motivo": "No cumplió descanso"
            })
    return alerts


# ---- CSV ----
def generate_csv_report_by_sede(data, sede):
    df = pd.DataFrame([d for d in data if d["sede"] == sede])

    df = df.sort_values(by=["fecha", "nombre"])

    csv = StringIO()
    df.to_csv(csv, index=False)
    return csv.getvalue()
