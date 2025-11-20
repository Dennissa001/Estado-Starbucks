# utils.py
import json
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
from io import BytesIO


# -------------------------
# CARGA Y GUARDADO
# -------------------------
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


# -------------------------
# LOGIN
# -------------------------
def authenticate(username, password, users):
    for u in users:
        if u["username"] == username and u["password"] == password:
            return u
    return None


# -------------------------
# AGREGAR REGISTRO
# -------------------------
def add_employee_entry(path, user, hora_inicio, hora_salida,
                       descanso, motivo, estres, comentario):

    data = load_data(path)

    entry = {
        "nombre": user["username"],
        "sede": user["sede"],
        "fecha": str(datetime.today().date()),
        "hora_inicio": str(hora_inicio),
        "hora_salida": str(hora_salida),
        "descanso": descanso,
        "motivo_descanso": motivo,
        "estres": estres,
        "estado_emocional": comentario
    }

    data.append(entry)
    save_data(path, data)


# -------------------------
# FILTRO
# -------------------------
def filter_data(data, fecha=None, sede=None):
    df = pd.DataFrame(data)

    if df.empty:
        return []

    if fecha and "fecha" in df.columns:
        df = df[df["fecha"] == fecha]

    if sede and "sede" in df.columns:
        df = df[df["sede"] == sede]

    return df.to_dict(orient="records")


# -------------------------
# KPIS + GRAFICOS
# -------------------------
def compute_kpis(data):
    df = pd.DataFrame(data)

    # Valores vacíos
    if df.empty:
        return {
            "estres_promedio": 0,
            "pct_descanso": 0,
            "alertas_count": 0,
            "fig_trend": plt.figure(),
            "fig_pie_estado": plt.figure(),
            "fig_bar_estr": plt.figure()
        }

    # Métricas básicas
    estres_prom = df["estres"].mean()
    pct_desc = (df["descanso"].mean() * 100) if "descanso" in df.columns else 0

    # Alertas
    alertas = get_alerts(data)

    # ------------------- TENDENCIA SEMANAL -------------------
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["semana"] = df["fecha"].dt.isocalendar().week

    sem = df.groupby("semana")["estres"].mean()

    fig_trend = plt.figure(figsize=(6, 3))
    plt.bar(sem.index, sem.values)
    plt.title("Tendencia semanal del estrés")
    plt.xlabel("Semana")
    plt.ylabel("Estrés promedio")

    # ------------------- PIE ESTADO EMOCIONAL -------------------
    fig_pie = plt.figure(figsize=(4, 4))
    estados = df["estado_emocional"].value_counts()
    plt.pie(estados, labels=estados.index, autopct="%1.1f%%")
    plt.title("Estado emocional del personal")

    # ------------------- BARRA POR SEDE -------------------
    fig_bar = plt.figure(figsize=(6, 3))
    sede_bar = df.groupby("sede")["estres"].mean()
    plt.bar(sede_bar.index, sede_bar.values)
    plt.title("Estrés por sede")

    return {
        "estres_promedio": estres_prom,
        "pct_descanso": pct_desc,
        "alertas_count": len(alertas),
        "fig_trend": fig_trend,
        "fig_pie_estado": fig_pie,
        "fig_bar_estr": fig_bar
    }


# -------------------------
# ALERTAS
# -------------------------
def get_alerts(data):
    alerts = []

    for d in data:
        if d["estres"] >= 8:
            alerts.append({
                "nombre": d["nombre"],
                "motivo": "Estrés muy alto (>=8)",
                "fecha": d["fecha"],
                "sede": d["sede"]
            })

        if not d["descanso"]:
            alerts.append({
                "nombre": d["nombre"],
                "motivo": "Descanso NO cumplido",
                "fecha": d["fecha"],
                "sede": d["sede"]
            })

    return alerts


# -------------------------
# CSV ORDENADO
# -------------------------
def generate_csv_report_by_sede(data, sede):
    df = pd.DataFrame(data)
    df = df[df["sede"] == sede]

    df = df[[
        "sede", "fecha", "nombre", "hora_inicio", "hora_salida",
        "descanso", "estres", "estado_emocional", "motivo_descanso"
    ]]

    df = df.sort_values(by=["fecha", "nombre"])

    return df.to_csv(index=False).encode("utf-8")
