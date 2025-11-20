# utils.py
import json
import os
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
from io import BytesIO, StringIO

# -----------------------
# Archivo/IO
# -----------------------
def load_data(path="data.json"):
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_data(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_users(path="users.json"):
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

# -----------------------
# Autenticación
# -----------------------
def authenticate(username, password, users):
    for u in users:
        if u.get("username") == username and u.get("password") == password:
            return u
    return None

# -----------------------
# Añadir registro de empleado
# -----------------------
def add_employee_entry(path, user, hora_inicio, hora_salida,
                       descanso_cumplido, motivo_descanso,
                       estres, estado, comentario=""):
    """
    Guarda un registro en data.json.
    hora_inicio / hora_salida: datetime.time (st.time_input)
    user: dict con keys username,nombre,sede,role
    """
    data = load_data(path)
    entry = {
        "username": user.get("username"),
        "nombre": user.get("nombre", user.get("username")),
        "sede": user.get("sede", ""),
        "fecha": str(datetime.today().date()),
        "hora_inicio": (hora_inicio.strftime("%H:%M") if hasattr(hora_inicio, "strftime") else str(hora_inicio)),
        "hora_salida": (hora_salida.strftime("%H:%M") if hasattr(hora_salida, "strftime") else str(hora_salida)),
        "descanso": bool(descanso_cumplido),
        "motivo_descanso": motivo_descanso if not descanso_cumplido else "",
        "estres": float(estres) if estres is not None else None,
        "estado": estado,
        "comentario": comentario
    }
    data.append(entry)
    save_data(path, data)

# -----------------------
# Filtrado seguro
# -----------------------
def filter_data(data, fecha=None, sede=None):
    df = pd.DataFrame(data)
    if df.empty:
        return []
    if fecha is not None and "fecha" in df.columns:
        df = df[df["fecha"] == str(fecha)]
    if sede is not None and "sede" in df.columns:
        df = df[df["sede"] == sede]
    return df.to_dict(orient="records")

# -----------------------
# Alertas
# -----------------------
def get_alerts(data):
    """
    data: list[dict] o DataFrame-compatible list.
    Devuelve lista de alertas {nombre, motivo}
    """
    if not data:
        return []
    df = pd.DataFrame(data)
    alerts = []
    for _, row in df.iterrows():
        nombre = row.get("nombre", row.get("username", "Desconocido"))
        # 1) Salida no registrada
        if not row.get("hora_salida"):
            alerts.append({"nombre": nombre, "motivo": "Salida no registrada"})
        # 2) Horas excesivas (>9)
        try:
            hi = datetime.strptime(row.get("hora_inicio", "00:00"), "%H:%M")
            hs = datetime.strptime(row.get("hora_salida", "00:00"), "%H:%M")
            dur = (hs - hi).seconds / 3600
            if dur > 9:
                alerts.append({"nombre": nombre, "motivo": f"Exceso de jornada ({dur:.1f}h)"})
        except Exception:
            pass
        # 3) Estrés alto
        try:
            if float(row.get("estres", 0)) >= 8:
                alerts.append({"nombre": nombre, "motivo": "Estrés muy alto (>=8)"})
        except Exception:
            pass
        # 4) Descanso incumplido
        if row.get("descanso") in [False, "False", 0]:
            motivo = row.get("motivo_descanso", "")
            alerts.append({"nombre": nombre, "motivo": f"Descanso no cumplido ({motivo})"})
        # 5) Ingreso tardío (>=10:00)
        try:
            hi = datetime.strptime(row.get("hora_inicio", "00:00"), "%H:%M")
            if hi.hour >= 10:
                alerts.append({"nombre": nombre, "motivo": "Ingreso tardío (>=10:00)"})
        except Exception:
            pass
    return alerts

# -----------------------
# KPIs y gráficos
# -----------------------
def compute_kpis(data):
    df = pd.DataFrame(data)
    if df.empty:
        return {
            "estres_promedio": 0.0,
            "pct_descanso": 0.0,
            "alertas_count": 0,
            "fig_bar_estr": None,
            "fig_trend": None
        }
    # estrés promedio
    try:
        estres_prom = float(pd.to_numeric(df.get("estres", pd.Series()), errors="coerce").mean())
    except Exception:
        estres_prom = 0.0
    # % descanso cumplido
    try:
        pct_descanso = float(df.get("descanso", pd.Series()).apply(bool).mean() * 100)
    except Exception:
        pct_descanso = 0.0
    # alertas count
    alerts = get_alerts(data)
    alert_count = len(alerts)

    # gráfico barras por sede (estrés promedio)
    fig_bar = None
    if "sede" in df.columns and "estres" in df.columns:
        try:
            fig_bar, ax = plt.subplots()
            grp = df.groupby("sede")["estres"].apply(lambda s: pd.to_numeric(s, errors="coerce").fillna(0).mean())
            grp.plot(kind="bar", ax=ax)
            ax.set_title("Estrés promedio por sede")
            ax.set_ylabel("Estrés promedio")
            plt.tight_layout()
        except Exception:
            fig_bar = None

    # tendencia por fecha
    fig_trend = None
    if "fecha" in df.columns and "estres" in df.columns:
        try:
            fig_trend, ax2 = plt.subplots()
            grp2 = df.groupby("fecha")["estres"].apply(lambda s: pd.to_numeric(s, errors="coerce").fillna(0).mean())
            grp2.plot(kind="line", marker="o", ax=ax2)
            ax2.set_title("Tendencia del estrés por fecha")
            ax2.set_ylabel("Estrés promedio")
            plt.tight_layout()
        except Exception:
            fig_trend = None

    return {
        "estres_promedio": estres_prom,
        "pct_descanso": pct_descanso,
        "alertas_count": alert_count,
        "fig_bar_estr": fig_bar,
        "fig_trend": fig_trend
    }

# -----------------------
# Reportes CSV
# -----------------------
def generate_csv_report_by_sede(data, sede):
    df = pd.DataFrame(data)
    if df.empty or "sede" not in df.columns:
        return "".encode("utf-8")
    df_s = df[df["sede"] == sede]
    buf = StringIO()
    df_s.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")
