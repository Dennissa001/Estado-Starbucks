import pandas as pd
from datetime import datetime

def generar_alertas(df):
    """
    Añade una columna 'alertas' al DataFrame con lista de advertencias
    basadas en la jornada y el estado emocional.
    """
    if df.empty:
        return df

    alertas_generadas = []

    for _, row in df.iterrows():
        alertas = []

        # 1. ALERTA: ausencia de hora de salida
        if row.get("hora_salida") in [None, "", "0", "null"]:
            alertas.append("Salida no registrada")

        # 2. ALERTA: horas excesivas
        try:
            if row.get("hora_ingreso") and row.get("hora_salida"):
                h_in = datetime.strptime(row["hora_ingreso"], "%H:%M")
                h_out = datetime.strptime(row["hora_salida"], "%H:%M")
                horas = (h_out - h_in).seconds / 3600

                if horas > 8:
                    alertas.append("Posible exceso de jornada laboral (>8h)")
        except:
            pass

        # 3. ALERTA: estado emocional crítico
        estado = str(row.get("estado", "")).lower()
        criticos = ["estresado", "ansioso", "triste", "mal"]
        if estado in criticos:
            alertas.append("Estado emocional crítico reportado")

        # 4. ALERTA: ingreso después de 10am
        try:
            if row.get("hora_ingreso"):
                h_in = datetime.strptime(row["hora_ingreso"], "%H:%M")
                if h_in.hour >= 10:
                    alertas.append("Ingreso tardío (después de 10:00 AM)")
        except:
            pass

        alertas_generadas.append(alertas)

    df["alertas"] = alertas_generadas
    return df
