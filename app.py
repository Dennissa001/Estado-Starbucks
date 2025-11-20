import streamlit as st
from utils import load_data, load_users, authenticate, add_employee_entry, filter_data, compute_kpis, get_alerts, generate_csv_report_by_sede
from datetime import datetime
import pandas as pd

st.set_page_config(page_title="Bienestar Starbucks", layout="wide")

DATA_PATH = "data.json"
USERS_PATH = "users.json"

# -------------------------------
# LOGIN
# -------------------------------
st.title("Bienestar Starbucks - Iniciar Sesión")
users = load_users(USERS_PATH)

if 'login' not in st.session_state:
    st.session_state.login = False
    st.session_state.user = None

if not st.session_state.login:
    username = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")
    if st.button("Ingresar"):
        user = authenticate(username, password, users)
        if user:
            st.session_state.login = True
            st.session_state.user = user
        else:
            st.error("Usuario o contraseña incorrectos")
else:
    user = st.session_state.user
    st.sidebar.title(f"Hola, {user['username']} ({user['role']})")
    page = st.sidebar.selectbox("Ir a:", ["Dashboard", "Registro Empleado", "Alertas", "Reportes", "Tendencias"])

    # -------------------------------
    # CARGA DE DATOS
    # -------------------------------
    data = load_data(DATA_PATH)
    fecha_seleccionada = st.sidebar.date_input("Fecha:", value=pd.to_datetime(datetime.today()))
    sede_filtro = None
    if user['role']=="empleado":
        sede_filtro = user['sede']
    elif user['role']=="admin":
        sede_options = ["Todas"] + sorted(list({d.get('sede','No definida') for d in data}))
        sede_filtro = st.sidebar.selectbox("Sede:", options=sede_options)
        if sede_filtro=="Todas":
            sede_filtro = None
    filtered = filter_data(data, fecha=str(fecha_seleccionada), sede=sede_filtro)

    # -------------------------------
    # DASHBOARD
    # -------------------------------
    if page=="Dashboard":
        st.title("Dashboard de Bienestar y Cumplimiento")
        kpis = compute_kpis(filtered)
        c1, c2, c3 = st.columns(3)
        c1.metric("% Cumplen descansos", f"{kpis['pct_descanso']:.1f}%")
        c2.metric("Estrés promedio", f"{kpis['estres_promedio']:.1f}/10")
        c3.metric("Alertas activas", kpis['alertas_count'])
        st.markdown("---")
        st.subheader("Distribución de estrés")
        st.pyplot(kpis['fig_estr'])

    # -------------------------------
    # REGISTRO EMPLEADO
    # -------------------------------
    elif page=="Registro Empleado" and user['role']=="empleado":
        st.title("Registro de Turno")
        hora_inicio = st.time_input("Hora de inicio", value=datetime.now().time())
        hora_salida = st.time_input("Hora de salida", value=datetime.now().time())
        descanso_cumplido = st.radio("Cumplió su descanso?", ["Sí", "No"])=="Sí"
        motivo_descanso = ""
        if not descanso_cumplido:
            motivo_descanso = st.selectbox("Motivo del descanso no cumplido", ["Alta demanda de clientes", "No quiso", "Otro"])
        estres = st.slider("Nivel de estrés (0-10)", 0, 10, 5)
        comentario = st.text_area("¿Cómo te has sentido hoy?")

        if st.button("Registrar entrada"):
            add_employee_entry(DATA_PATH, user, hora_inicio, hora_salida, descanso_cumplido, motivo_descanso, estres, comentario)
            st.success("Registro guardado correctamente.")

    # -------------------------------
    # ALERTAS
    # -------------------------------
    elif page=="Alertas":
        st.title("Alertas")
        alerts = get_alerts(filtered)
        if not alerts:
            st.success("No hay alertas para los filtros actuales 🎉")
        else:
            for a in alerts:
                st.warning(f"ID {a['id']} - {a['nombre']}: {a['motivo']}")

    # -------------------------------
    # REPORTES
    # -------------------------------
    elif page=="Reportes" and user['role']=="admin":
        st.title("Reportes por sede")
        sedes = sorted(list({d.get('sede','No definida') for d in data}))
        for s in sedes:
            if st.button(f"Descargar CSV - {s}"):
                csv_bytes = generate_csv_report_by_sede(data, s)
                st.download_button(f"Descargar CSV {s}", data=csv_bytes, file_name=f"reporte_{s}.csv", mime="text/csv")

    # -------------------------------
    # TENDENCIAS
    # -------------------------------
    elif page=="Tendencias" and user['role']=="admin":
        st.title("Tendencias")
        kpis = compute_kpis(filtered)
        st.pyplot(kpis['fig_dept'])
