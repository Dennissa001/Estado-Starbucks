import streamlit as st
from datetime import datetime
from utils import (
    load_data, save_data, filter_data, load_users,
    authenticate, add_employee_entry,
    compute_kpis, get_alerts,
    generate_csv_report_by_sede
)

st.set_page_config(page_title="Bienestar Starbucks", layout="wide")

DATA_PATH = "data.json"
USERS_PATH = "users.json"


# ------------------------------
# LOGIN
# ------------------------------

st.title("Bienestar Starbucks - Iniciar Sesión")

users = load_users(USERS_PATH)

if "login" not in st.session_state:
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
            st.rerun()
        else:
            st.error("Credenciales incorrectas")

else:
    user = st.session_state.user

    # SIDEBAR
    st.sidebar.title(f"Hola, {user['username']} ({user['role']})")

    if st.sidebar.button("Cerrar sesión"):
        st.session_state.login = False
        st.session_state.user = None
        st.rerun()

    # Opciones según rol
    pages = ["Registro Empleado"]
    if user["role"] == "admin":
        pages += ["Dashboard", "Alertas", "Reportes"]

    page = st.sidebar.selectbox("Ir a:", pages)

    # Cargar datos
    data = load_data(DATA_PATH)
    fecha_hoy = str(datetime.today().date())

    if user["role"] == "empleado":
        sede_filtrada = user["sede"]
    else:
        sedes = ["Todas"] + sorted(list({d.get("sede", "") for d in data}))
        sede_sel = st.sidebar.selectbox("Sede:", sedes)
        sede_filtrada = None if sede_sel == "Todas" else sede_sel

    filtrado = filter_data(data, fecha_hoy, sede_filtrada)

    # ------------------------------
    # EMPLEADO
    # ------------------------------
    if page == "Registro Empleado":
        st.header("Registro del Empleado")

        hora_inicio = st.time_input("Hora de inicio:", datetime.now().time())
        hora_salida = st.time_input("Hora de salida:", datetime.now().time())

        descanso_si = st.radio("¿Cumpliste tu descanso?", ["Sí", "No"])
        descanso = descanso_si == "Sí"

        motivo = ""
        if not descanso:
            motivo = st.selectbox("Motivo:", [
                "Alta demanda de clientes", "No quiso",
                "Falta de personal", "Otro"
            ])

        estres = st.slider("Nivel de estrés (0-10)", 0, 10, 5)

        estado = st.selectbox("¿Cómo te sientes?", [
            "Feliz 😊", "Tranquilo 😌", "Normal 😐",
            "Estresado 😣", "Agotado 😫"
        ])

        if st.button("Registrar"):
            add_employee_entry(
                DATA_PATH, user,
                hora_inicio, hora_salida,
                descanso, motivo,
                estres, estado
            )
            st.success("Registro guardado correctamente ✔")

    # ------------------------------
    # DASHBOARD ADMIN
    # ------------------------------
    if page == "Dashboard" and user["role"] == "admin":

        st.header("Dashboard de Bienestar")

        kpis = compute_kpis(filtrado)

        c1, c2, c3 = st.columns(3)
        c1.metric("Estrés promedio", f"{kpis['estres_promedio']:.1f}")
        c2.metric("% Descanso", f"{kpis['pct_descanso']:.1f}%")
        c3.metric("Alertas", kpis["alertas_count"])

        st.subheader("Estrés por sede")
        st.pyplot(kpis["fig_bar"])

    # ------------------------------
    # ALERTAS
    # ------------------------------
    if page == "Alertas" and user["role"] == "admin":
        st.header("Alertas detectadas")

        alerts = get_alerts(filtrado)

        if not alerts:
            st.success("Sin alertas 🎉")
        else:
            for a in alerts:
                st.warning(f"⚠ {a['nombre']}: {a['motivo']}")

    # ------------------------------
    # REPORTES
    # ------------------------------
    if page == "Reportes" and user["role"] == "admin":

        st.header("Reportes por sede")

        sedes_disponibles = sorted(list({d.get("sede", "") for d in data}))

        for s in sedes_disponibles:
            if st.button(f"Generar reporte de {s}"):
                out = generate_csv_report_by_sede(data, s)
                st.download_button(
                    label=f"Descargar {s}",
                    data=out,
                    file_name=f"reporte_{s}.csv",
                    mime="text/csv"
                )
