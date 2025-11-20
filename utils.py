import json
import pandas as pd
import io
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

# Cargar datos
def load_data(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

# Filtrar por fecha y sede
def filter_data(data, fecha=None, sede=None):
    df = pd.DataFrame(data)
    if fecha is not None:
        df = df[df['fecha'] == str(fecha)]
    if sede is not None:
        df = df[df.get('sede') == sede]
    return df.to_dict(orient='records')

# Añadir registro de empleado
def add_employee_entry(path, nombre, sede, hora_inicio, hora_salida, descanso_cumplido, estres):
    data = load_data(path)
    new_id = max([d['id'] for d in data], default=0) + 1
    entry = {
        'id': new_id,
        'nombre': nombre,
        'sede': sede,
        'hora_inicio': str(hora_inicio),
        'hora_salida': str(hora_salida),
        'descanso_cumplido': descanso_cumplido,
        'estres': estres,
        'fecha': str(datetime.today().date())
    }
    data.append(entry)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

# KPIs y gráficos
def compute_kpis(filtered_data):
    df = pd.DataFrame(filtered_data)
    if df.empty:
        fig_empty = plt.figure()
        return {'pct_descanso':0.0,'estres_promedio':0.0,'alertas_count':0,'fig_estr':fig_empty,'fig_evo':fig_empty,'fig_dept':fig_empty}

    pct_desc = df['descanso_cumplido'].fillna(False).apply(bool).mean()*100
    estres_prom = pd.to_numeric(df['estres'], errors='coerce').fillna(0).mean()

    fig1 = plt.figure()
    plt.hist(pd.to_numeric(df['estres'], errors='coerce').dropna(), bins=5)
    plt.title('Histograma de estrés')

    fig2 = plt.figure()
    today = pd.to_datetime(df['fecha']).max()
    days = [today - timedelta(days=i) for i in range(6,-1,-1)]
    vals = [max(0, estres_prom + (i-3)*0.1) for i,_ in enumerate(days)]
    plt.plot(days, vals)
    plt.title('Evolución semanal (simulada)')

    fig3 = plt.figure()
    if 'sede' in df.columns:
        grp = df.groupby('sede')['estres'].apply(lambda s: pd.to_numeric(s, errors='coerce').fillna(0).mean())
        grp.plot(kind='bar')
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

# Alertas
def get_alerts(filtered_data):
    df = pd.DataFrame(filtered_data)
    alerts = []
    for _, row in df.iterrows():
        if float(row.get('estres',0)) >= 8:
            alerts.append({'id': row.get('id'), 'nombre': row.get('nombre'), 'motivo': 'Estrés muy alto'})
        try:
            hi = datetime.strptime(row.get('hora_inicio','00:00:00'), '%H:%M:%S')
            hs = datetime.strptime(row.get('hora_salida','00:00:00'), '%H:%M:%S')
            if (hs-hi).seconds/3600 > 9:
                alerts.append({'id': row.get('id'), 'nombre': row.get('nombre'), 'motivo': 'Horas trabajadas > 9'})
        except Exception:
            pass
        if not row.get('descanso_cumplido', True):
            alerts.append({'id': row.get('id'), 'nombre': row.get('nombre'), 'motivo': 'Descanso no cumplido'})
    seen = set()
    uniq = []
    for a in alerts:
        key = (a['id'], a['motivo'])
        if key not in seen:
            seen.add(key)
            uniq.append(a)
    return uniq

# Reportes por sede
def generate_csv_report_by_sede(data, sede):
    df = pd.DataFrame(data)
    df_sede = df[df['sede']==sede]
    buf = io.StringIO()
    df_sede.to_csv(buf, index=False)
    return buf.getvalue().encode('utf-8')
