# app.py
import streamlit as st
from datetime import datetime
import pandas as pd

from utils import (
    load_data, save_data, load_users, authenticate,
    add_employee_entry, filter_data, compute_kpis,
    get_alerts, generate_csv_report_by_sede
)

st.set_page_config(page_title="Bienestar Starbucks", layout="wide")

DATA_PATH = "data.json"
USERS_PATH = "users.json"

# Inicializar sesión
if "user" not in st.session_state:
    st.session_state.user = None
if "logged" not in st.session_state:
    st.session_state.logged = False


# ---------------------------
# LOGIN
# ---------------------------
def login_view():
    st.title("Bienestar Starbucks — Iniciar sesión")
    users = load_users(USERS_PATH)

    username = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")

    if st.button("Ingresar"):
        user = authenticate(username, password, users)
        if user:
            st.session_state.user = user
            st.session_state.logged = True
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos")


# ---------------------------
# LOGOUT
# ---------------------------
def logout():
    st.session_state.user = None
    st.session_state.logged = False
    st.rerun()


# ---------------------------
# EMPLEADO
# ---------------------------
def employee_view(user):

    st.header("Registro del Empleado")
    st.write(f"Sede: **{user.get('sede','(no definida)')}**")

    # horarios
    hora_inicio = st.time_input("Hora de inicio", value=datetime.now().time())
    hora_salida = st.time_input("Hora de salida", value=datetime.now().time())

    descanso_ok = st.radio("¿Cumpliste tu descanso?", ["Sí", "No"]) == "Sí"

    motivo = ""
    if not descanso_ok:
        motivo = st.selectbox(
            "Motivo:",
            ["Alta demanda", "No quiso", "Falta de personal", "Otro"]
        )

    estres = st.slider("Nivel de estrés (0-10)", 0, 10, 5)

    estado = st.selectbox(
        "¿Cómo te sientes hoy?",
        ["Feliz 😊", "Tranquilo 😌", "Normal 😐", "Estresado 😣", "Agotado 😫"]
    )

    comentario = st.text_area("Comentario (opcional)")

    if st.button("Registrar"):
        add_employee_entry(
            DATA_PATH, user,
            hora_inicio, hora_salida,
            descanso_ok, motivo,
            estres,
            estado if comentario == "" else comentario
        )
        st.success("Registro guardado correctamente 💚")

    st.markdown("---")
    if st.button("Cerrar sesión"):
        logout()


# ---------------------------
# ADMIN
# ---------------------------
def admin_view(user):
    st.title("Panel Administrador")
    data = load_data(DATA_PATH)

    if not data:
        st.warning("No hay registros todavía.")
        if st.button("Cerrar sesión"):
            logout()
        return

    # FILTROS
    fecha_filtro = st.sidebar.date_input("Fecha:", datetime.today())
    sedes = ["Todas"] + sorted(list({d.get("sede", "") for d in data}))
    sede_sel = st.sidebar.selectbox("Sede:", sedes)

    sede_filter = None if sede_sel == "Todas" else sede_sel
    filtered = filter_data(data, fecha=str(fecha_filtro), sede=sede_filter)

    # KPIs
    kpis = compute_kpis(filtered)

    c1, c2, c3 = st.columns(3)
    c1.metric("Estrés promedio", f"{kpis['estres_promedio']:.1f}")
    c2.metric("% descanso", f"{kpis['pct_descanso']:.1f}%")
    c3.metric("Alertas", kpis["alertas_count"])

    st.markdown("---")

    # TABLA
    if filtered:
        st.subheader("Registros filtrados")
        st.dataframe(pd.DataFrame(filtered))
    else:
        st.info("No hay registros para los filtros seleccionados.")

    # ALERTAS DETALLADAS
    st.subheader("Alertas detectadas")
    alerts = get_alerts(filtered)
    if not alerts:
        st.success("No hay alertas 🎉")
    else:
        for a in alerts:
            st.warning(f"⚠ {a['nombre']} — {a['motivo']}")

    st.markdown("---")

    # GRÁFICOS
    st.subheader("Tendencia semanal del estrés")
    st.pyplot(kpis["fig_trend"])

    st.subheader("Estado emocional del personal (Pie chart)")
    st.pyplot(kpis["fig_pie_estado"])

    st.subheader("Estrés por sede")
    st.pyplot(kpis["fig_bar_estr"])

    st.markdown("---")

    # REPORTES
    st.subheader("Reportes")
    sedes_csv = sorted(list({d.get("sede", "") for d in data}))

    for s in sedes_csv:
        if st.button(f"CSV — {s}"):
            out = generate_csv_report_by_sede(data, s)
            st.download_button(
                label=f"Descargar reporte {s}",
                data=out,
                file_name=f"reporte_{s}.csv",
                mime="text/csv"
            )

    if st.sidebar.button("Cerrar sesión"):
        logout()


# ---------------------------
# MAIN
# ---------------------------
def main():
    if not st.session_state.logged:
        login_view()
    else:
        user = st.session_state.user
        if user["role"] == "admin":
            admin_view(user)
        else:
            employee_view(user)


if __name__ == "__main__":
    main()
