import json
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

# ------------------------------------------------------------
# LOAD / SAVE
# ------------------------------------------------------------
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
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return []

# ------------------------------------------------------------
# AUTH
# ------------------------------------------------------------
def authenticate(username, password, users):
    for u in users:
        if u["username"] == username and u["password"] == password:
            return u
    return None

# ------------------------------------------------------------
# ADD ENTRY
# ------------------------------------------------------------
def add_employee_entry(path, user, fecha, h_in, h_out, descanso, estres, estado):
    data = load_data(path)
    data.append({
        "sede": user["sede"],
        "fecha": fecha,
        "nombre": user["nombre"],
        "hora_inicio": h_in,
        "hora_salida": h_out,
        "descanso": descanso,
        "estres": estres,
        "estado_emocional": estado
    })
    save_data(path, data)

# ------------------------------------------------------------
# FILTERS
# ------------------------------------------------------------
def filter_data(data, fecha=None, sede=None):
    result = data
    if fecha:
        result = [d for d in result if d["fecha"] == fecha]
    if sede:
        result = [d for d in result if d["sede"] == sede]
    return result

# ------------------------------------------------------------
# KPIs
# ------------------------------------------------------------
def compute_kpis(data):
    if not data:
        return {"estres_promedio": 0, "pct_descanso": 0, "alertas_count": 0}

    df = pd.DataFrame(data)

    estres_prom = df["estres"].mean()

    pct_desc = len(df[df["descanso"].astype(int) >= 45]) / len(df) * 100

    alertas = get_alerts(data)

    return {
        "estres_promedio": estres_prom,
        "pct_descanso": pct_desc,
        "alertas_count": len(alertas)
    }

# ------------------------------------------------------------
# ALERTAS ORDENADAS
# ------------------------------------------------------------
def get_alerts(data):
    df = pd.DataFrame(data)
    if df.empty:
        return []

    df = df.sort_values(["sede", "fecha", "nombre"])

    alertas = []

    for _, row in df.iterrows():

        if int(row["estres"]) >= 7:
            alertas.append({
                "sede": row["sede"],
                "nombre": row["nombre"],
                "motivo": "Estrés alto",
                "estres": row["estres"],
                "fecha": row["fecha"]
            })

        if row["estado_emocional"] in ["Estresado", "Agotado"]:
            alertas.append({
                "sede": row["sede"],
                "nombre": row["nombre"],
                "motivo": f"Estado emocional: {row['estado_emocional']}",
                "estres": row["estres"],
                "fecha": row["fecha"]
            })

    return alertas

# ------------------------------------------------------------
# TENDENCIA SEMANAL
# ------------------------------------------------------------
def tendencia_semanal_estres(data):
    df = pd.DataFrame(data)

    if df.empty:
        return None, None

    df["fecha"] = pd.to_datetime(df["fecha"])
    df["semana"] = df["fecha"].dt.isocalendar().week
    semana_actual = df["semana"].max()

    df_semana = df[df["semana"] == semana_actual]

    tendencia = df_semana.groupby("fecha")["estres"].mean().reset_index()

    return tendencia["fecha"], tendencia["estres"]

# ------------------------------------------------------------
# PIE CHART EMOCIONES
# ------------------------------------------------------------
def pie_emociones(data):
    if not data:
        return [], []

    df = pd.DataFrame(data)
    counts = df["estado_emocional"].value_counts()

    return list(counts.index), list(counts.values)

# ------------------------------------------------------------
# CSV POR SEDE
# ------------------------------------------------------------
def generate_csv_report_by_sede(data, sede):
    df = pd.DataFrame([d for d in data if d["sede"] == sede])
    df = df.sort_values(["fecha", "nombre"])
    return df.to_csv(index=False)
