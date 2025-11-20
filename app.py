import streamlit as st
from utils import load_data, save_data, filter_data, generar_alertas
from datetime import datetime

st.set_page_config(page_title="Bienestar Starbucks", layout="wide")

DATA_PATH = "data.json"
USERS_PATH = "users.json"

# -------------------------------------
# LOGIN SYSTEM
# -------------------------------------
st.title("Bienestar Starbucks - Iniciar Sesión")
users = load_users(USERS_PATH)

if "login" not in st.session_state:
    st.session_state.login = False
    st.session_state.user = None

# ----------- LOGIN VIEW -------------
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

# ---------- LOGGED IN -------------
else:
    user = st.session_state.user

    # SIDEBAR
    st.sidebar.title(f"Hola, {user['username']} ({user['role']})")

    # CERRAR SESIÓN
    if st.sidebar.button("Cerrar sesión 🔒"):
        st.session_state.login = False
        st.session_state.user = None
        st.rerun()

    # Menú lateral
    page_options = ["Registro Empleado"]
    if user["role"] == "admin":
        page_options += ["Dashboard", "Alertas", "Reportes", "Tendencias"]

    page = st.sidebar.selectbox("Ir a:", page_options)

    # Carga de datos
    data = load_data(DATA_PATH)
    fecha_seleccionada = datetime.today().date()

    if user["role"] == "empleado":
        sede_filtro = user["sede"]
    else:  # admin
        sedes = ["Todas"] + sorted(list({d.get("sede", "ND") for d in data}))
        sede_filtro = st.sidebar.selectbox("Sede:", options=sedes)
        if sede_filtro == "Todas":
            sede_filtro = None

    filtered = filter_data(data, fecha=str(fecha_seleccionada), sede=sede_filtro)

    # ---------------------------------------------------------
    # REGISTRO EMPLEADO
    # ---------------------------------------------------------
    if page == "Registro Empleado" and user["role"] == "empleado":
        st.title("Registro de Testimonio del Empleado")

        # Horarios editables
        hora_inicio = st.time_input(
            "Hora de inicio:",
            value=datetime.now().time(),
            key="hora_inicio"
        )

        hora_salida = st.time_input(
            "Hora de salida:",
            value=datetime.now().time(),
            key="hora_salida"
        )

        # Descanso
        descanso_cumplido = st.radio("¿Cumplió su descanso?", ["Sí", "No"]) == "Sí"
        motivo_descanso = ""
        if not descanso_cumplido:
            motivo_descanso = st.selectbox(
                "Motivo:",
                ["Alta demanda de clientes", "No quiso", "Falta de personal", "Otro"]
            )

        # Estrés
        estres = st.slider("Nivel de estrés (0 - 10)", 0, 10, 5)

        # Estado emocional (MEJORA PEDIDA)
        estado_emocional = st.selectbox(
            "¿Cómo te sientes hoy?",
            ["Feliz 😊", "Tranquilo 😌", "Normal 😐", "Estresado 😣", "Agotado 😫"]
        )

        if st.button("Registrar"):
            add_employee_entry(
                DATA_PATH,
                user,
                hora_inicio=hora_inicio,
                hora_salida=hora_salida,
                descanso_cumplido=descanso_cumplido,
                motivo_descanso=motivo_descanso,
                estres=estres,
                comentario=estado_emocional
            )
            st.success("Información registrada correctamente 💚")

    # ---------------------------------------------------------
    # ADMIN: DASHBOARD
    # ---------------------------------------------------------
    if page == "Dashboard" and user["role"] == "admin":
        st.title("Dashboard de Bienestar")

        kpis = compute_kpis(filtered)

        c1, c2, c3 = st.columns(3)
        c1.metric("Promedio de estrés", f"{kpis['estres_promedio']:.1f}/10")
        c2.metric("% de descanso cumplido", f"{kpis['pct_descanso']:.1f}%")
        c3.metric("Alertas detectadas", kpis["alertas_count"])

        st.markdown("---")

        st.subheader("Estrés promedio por sede (gráfico de barras)")
        st.pyplot(kpis["fig_bar_estr"])

    # ---------------------------------------------------------
    # ADMIN: ALERTAS
    # ---------------------------------------------------------
    if page == "Alertas" and user["role"] == "admin":
        st.title("Alertas de Cumplimiento Laboral")
        alerts = get_alerts(filtered)

        if not alerts:
            st.success("No hay alertas activas 🎉")
        else:
            for a in alerts:
                st.warning(f"⚠️ {a['nombre']} - {a['motivo']}")

    # ---------------------------------------------------------
    # REPORTES
    # ---------------------------------------------------------
    if page == "Reportes" and user["role"] == "admin":
        st.title("Reportes por sede")
        sedes = sorted(list({d.get("sede", "ND") for d in data}))
        for s in sedes:
            if st.button(f"Descargar reporte {s}"):
                csv_bytes = generate_csv_report_by_sede(data, s)
                st.download_button(
                    f"Descargar {s}",
                    data=csv_bytes,
                    file_name=f"reporte_{s}.csv",
                    mime="text/csv"
                )

    # ---------------------------------------------------------
    # TENDENCIAS
    # ---------------------------------------------------------
    if page == "Tendencias" and user["role"] == "admin":
        st.title("Tendencias del Bienestar")
        st.pyplot(kpis["fig_dept"])

