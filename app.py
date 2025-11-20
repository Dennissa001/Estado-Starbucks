import streamlit as st
from utils import load_data, compute_kpis, get_alerts, generate_csv_report_by_sede, add_employee_entry, filter_data
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Dashboard Bienestar y Cumplimiento", layout="wide")

st.sidebar.title("Menú")
page = st.sidebar.selectbox("Ir a:", ["Dashboard", "Ingreso Empleado", "Alertas", "Reportes", "Tendencias"])

# Ruta de archivo
DATA_PATH = "data.json"

# Carga de datos
@st.cache_data
def cached_load(path):
    return load_data(path)

data = cached_load(DATA_PATH)

# FILTROS COMUNES
st.sidebar.header("Filtros")
fecha_seleccionada = st.sidebar.date_input("Fecha:", value=pd.to_datetime(datetime.today()))
sede = st.sidebar.selectbox("Sede:", options=["Todas"] + sorted(list({d.get('sede','No definida') for d in data})))
filtered = filter_data(data, fecha=str(fecha_seleccionada), sede=(None if sede=="Todas" else sede))

if page == "Dashboard":
    st.title("Dashboard de Bienestar y Cumplimiento")
    kpis = compute_kpis(filtered)

    c1, c2, c3 = st.columns(3)
    c1.metric("% Cumplen descansos", f"{kpis['pct_descanso']:.1f}%")
    c2.metric("Estrés promedio", f"{kpis['estres_promedio']:.1f}/10")
    c3.metric("Alertas activas", kpis['alertas_count'])

    st.markdown("---")
    st.subheader("Distribución de estrés")
    st.pyplot(kpis['fig_estr'])

elif page == "Ingreso Empleado":
    st.title("Ingreso de datos de empleado")
    nombre = st.text_input("Nombre")
    sede_input = st.text_input("Sede")
    hora_inicio = st.time_input("Hora de inicio", value=datetime.now().time())
    hora_salida = st.time_input("Hora de salida", value=datetime.now().time())
    descanso_cumplido = st.checkbox("Cumplió su descanso")
    estres = st.slider("Nivel de estrés (0-10)", 0, 10, 5)

    if st.button("Registrar entrada"):
        add_employee_entry(DATA_PATH, nombre, sede_input, hora_inicio, hora_salida, descanso_cumplido, estres)
        st.success("Registro guardado correctamente.")

elif page == "Alertas":
    st.title("Alertas inteligentes")
    alerts = get_alerts(filtered)
    if not alerts:
        st.success("No hay alertas para los filtros actuales 🎉")
    else:
        for a in alerts:
            st.warning(f"ID {a['id']} - {a['nombre']}: {a['motivo']}")

elif page == "Reportes":
    st.title("Generar reportes por sede")
    sedes = sorted(list({d.get('sede','No definida') for d in data}))
    for s in sedes:
        if st.button(f"Descargar CSV - {s}"):
            csv_bytes = generate_csv_report_by_sede(data, s)
            st.download_button(f"Descargar CSV {s}", data=csv_bytes, file_name=f"reporte_{s}.csv", mime="text/csv")

elif page == "Tendencias":
    st.title("Tendencias")
    st.write("Gráficos de tendencia por sede y promedio de estrés, cumplimiento y alertas.")
    st.pyplot(kpis['fig_dept'])
