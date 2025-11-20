import json
import pandas as pd
import io
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

# =======================
# Funciones de datos
# =======================
def load_data(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_data(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def load_users(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def authenticate(username, password, users):
    for u in users:
        if u['username'] == username and u['password'] == password:
            return u
    return None

# =======================
# Registro de empleado
# =======================
def add_employee_entry(path, user, hora_inicio, hora_salida, descanso_cumplido, motivo_descanso, estres, comentario):
    data = load_data(path)
    new_id = max([d.get('id',0) for d in data], default=0) + 1
    entry = {
        'id': new_id,
        'nombre': user['username'],
        'sede': user['sede'],
        'hora_inicio': str(hora_inicio),
        'hora_salida': str(hora_salida),
        'descanso_cumplido': descanso_cumplido,
        'motivo_descanso': motivo_descanso if not descanso_cumplido else "",
        'estres': estres,
        'comentario': comentario,
        'fecha': str(datetime.today().date())
    }
    data.append(entry)
    save_data(path, data)

# =======================
# Filtrado y KPIs
# =======================
def filter_data(data, fecha=None, sede=None):
    df = pd.DataFrame(data)
    if 'fecha' in df.columns and fecha is not None:
        df = df[df['fecha'] == str(fecha)]
    if 'sede' in df.columns and sede is not None:
        df = df[df['sede'] == sede]
    return df.to_dict(orient='records')

def get_alerts(filtered_data):
    if not filtered_data:
        return []
    df = pd.DataFrame(filtered_data)
    alerts = []
    for _, row in df.iterrows():
        try:
            if float(row.get('estres',0)) >= 8:
                alerts.append({'id': row.get('id'), 'nombre': row.get('nombre'), 'motivo': 'Estrés muy alto'})
        except ValueError:
            pass
        try:
            hi = datetime.strptime(row.get('hora_inicio','00:00:00'), '%H:%M:%S')
            hs = datetime.strptime(row.get('hora_salida','00:00:00'), '%H:%M:%S')
            if (hs-hi).seconds/3600 > 9:
                alerts.append({'id': row.get('id'), 'nombre': row.get('nombre'), 'motivo': 'Horas trabajadas > 9'})
        except Exception:
            pass
        if not row.get('descanso_cumplido', True):
            alerts.append({'id': row.get('id'), 'nombre': row.get('nombre'), 'motivo': f'Descanso no cumplido: {row.get("motivo_descanso","")}'})
    seen = set()
    uniq = []
    for a in alerts:
        key = (a['id'], a['motivo'])
        if key not in seen:
            seen.add(key)
            uniq.append(a)
    return uniq

def compute_kpis(filtered_data):
    if not filtered_data:
        fig_empty = plt.figure()
        return {'pct_descanso':0.0,'estres_promedio':0.0,'alertas_count':0,'fig_estr':fig_empty,'fig_evo':fig_empty,'fig_dept':fig_empty}

    df = pd.DataFrame(filtered_data)
    pct_desc = df.get('descanso_cumplido', pd.Series()).apply(bool).mean()*100
    estres_prom = pd.to_numeric(df.get('estres', pd.Series()), errors='coerce').fillna(0).mean()

    # Histograma de estrés
    fig1 = plt.figure()
    plt.hist(pd.to_numeric(df.get('estres', pd.Series()), errors='coerce').dropna(), bins=5, color='skyblue')
    plt.title('Histograma de estrés')

    # Tendencia semanal simulada
    fig2 = plt.figure()
    try:
        today = pd.to_datetime(df['fecha']).max()
    except Exception:
        today = pd.to_datetime(datetime.today().date())
    days = [today - timedelta(days=i) for i in range(6,-1,-1)]
    vals = [max(0, estres_prom + (i-3)*0.1) for i,_ in enumerate(days)]
    plt.plot(days, vals, marker='o')
    plt.title('Evolución semanal (simulada)')

    # Promedio de estrés por sede
    fig3 = plt.figure()
    if 'sede' in df.columns:
        grp = df.groupby('sede')['estres'].apply(lambda s: pd.to_numeric(s, errors='coerce').fillna(0).mean())
        grp.plot(kind='bar', color='salmon')
        plt.title('Estrés promedio por sede')

    alerts = get_alerts(filtered_data)

    return {
        'pct_descanso': pct_desc,
        'estres_promedio': estres_prom,
        'alertas_count': len(alerts),
        'fig_estr': fig1,
        'fig_evo': fig2,
        'fig_dept': fig3
    }

def generate_csv_report_by_sede(data, sede):
    df = pd.DataFrame(data)
    if 'sede' in df.columns:
        df_sede = df[df['sede']==sede]
    else:
        df_sede = pd.DataFrame()
    buf = io.StringIO()
    df_sede.to_csv(buf, index=False)
    return buf.getvalue().encode('utf-8')
