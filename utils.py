import json
import os
import pandas as pd
from datetime import datetime


# ----------------------------------------
# Cargar y guardar datos
# ----------------------------------------

DATA_FILE = "data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return []

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# ----------------------------------------
# Filtro seguro (evita KeyError)
# ----------------------------------------

def filter_data(data, fecha=None, sede=None):
    df = pd.DataFrame(data)

    if df.empty:
        return []

    if 'fecha' in df.columns and fecha:
        df = df[df['fecha'] == str(fecha)]

    if 'sede' in df.columns and sede:
        df = df[df['sede'] == sede]

    return df.to_dict(orient='records')


# ----------------------------------------
# ALERTAS PRO
# ----------------------------------------

def generar_alertas(df):
    if df.empty:
        return df

    alertas_totales = []

    for _, row in df.iterrows():
        alertas = []

        # 1. Salida no registrada
        if row.get("hora_salida") in ["", None, "null"]:
            alertas.append("Salida no registrada")

        # 2. Cálculo de horas trabajadas
        try:
            h_in = datetime.strptime(row["hora_ingreso"], "%H:%M")
            h_out = datetime.strptime(row["hora_salida"], "%H:%M")
            horas = (h_out - h_in).seconds / 3600
            if horas > 8:
                alertas.append("Exceso de jornada (>8h)")
        except:
            pass

        # 3. Estado emocional crítico
        estado = str(row.get("estado", "")).lower()
        if estado in ["triste", "estresado", "ansioso", "mal"]:
            alertas.append("Estado emocional crítico")

        # 4. Ingreso tarde
        try:
            h_in = datetime.strptime(row["hora_ingreso"], "%H:%M")
            if h_in.hour >= 10:
                alertas.append("Ingreso tardío")
        except:
            pass

        alertas_totales.append(alertas)

    df["alertas"] = alertas_totales
    return df
