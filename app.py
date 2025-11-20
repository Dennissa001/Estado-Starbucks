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

# inicializar session_state
if "user" not in st.session_state:
    st.session_state.user = None
if "logged" not in st.session_state:
    st.session_state.logged = False

# ------ Login view ------
def login_view():
    st.title("Bienestar Starbucks — Iniciar sesión")
    users = load_users(USERS_PATH)

    col1, col2 = st.columns([2,1])
    with col1:
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")

    with col2:
        if st.button("Ingresar"):
            user = authenticate(username, password, users)
            if user:
                st.session_state.user = user
                st.session_state.logged = True
                st.rerun()   # <-- CORREGIDO
            else:
                st.error("Usuario o contraseña incorrectos")

    st.markdown("---")
    st.info("Si no existe un usuario admin, crea uno en users.json. Usa los ejemplos provistos.")

# ------ Logout ------
def logout():
    st.session_state.user = None
    st.session_state.logged = False
    st.rerun()   # <-- CORREGIDO

# ------ Empleado view ------
def employee_view(user):
    st.header("Registro de turno — Empleado")
    st.write(f"Sede detectada: **{user.get('sede','(no definida)')}**")

    hora_inicio = st.time_input("Hora de inicio", value=datetime.now().time(), key="hi")
    hora_salida = st.time_input("Hora de salida", value=datetime.now().time(), key="hs")

    descanso_ok = st.radio("¿Cumpliste tu descanso?", ["Sí","No"]) == "Sí"
    motivo = ""
    if not descanso_ok:
        motivo = st.selectbox("Motivo del descanso no cumplido", [
            "Alta demanda de clientes", "No quiso", "Falta de personal", "Otro"
        ])

    estres = st.slider("Nivel de estrés (0-10)", 0, 10, 5)
    estado = st.selectbox("¿Cómo te sientes hoy?", [
        "Feliz 😊", "Tranquilo 😌", "Normal 😐", "Estresado 😣", "Agotado 😫"
    ])
    comentario = st.text_area("Comentario (opcional)")

    if st.button("Registrar testimonio"):
        add_employee_entry(
            DATA_PATH, user,
            hora_inicio, hora_salida,
            descanso_ok, motivo,
            estres, estado if comentario == "" else comentario
        )
        st.success("Registro guardado. Gracias por compartir 💚")

    if st.button("Cerrar sesión"):
        logout()

# ------ Admin view ------
def admin_view(user):
    st.header("Panel administrador — Bienestar y cumplimiento")
    data = load_data(DATA_PATH)

    if not data:
        st.warning("No hay registros todavía.")
        if st.button("Cerrar sesión"):
            logout()
        return

    # filtros
    fecha_filtro = st.sidebar.date_input("Filtrar por fecha", value=datetime.today().date())
    sedes = sorted(list({d.get("sede","(no definida)") for d in data}))
    sedes = ["Todas"] + sedes
    sede_sel = st.sidebar.selectbox("Filtrar por sede", sedes)
    sede_filter = None if sede_sel == "Todas" else sede_sel

    filtered = filter_data(data, fecha=str(fecha_filtro), sede=sede_filter)

    # KPIs
    kpis = compute_kpis(filtered)

    c1, c2, c3 = st.columns(3)
    c1.metric("Estrés promedio", f"{kpis['estres_promedio']:.1f}")
    c2.metric("% descanso cumplido", f"{kpis['pct_descanso']:.1f}%")
    c3.metric("Alertas", kpis['alertas_count'])

    st.markdown("---")

    # Tabla
    if filtered:
        df = pd.DataFrame(filtered)
        st.subheader("Registros")
        st.dataframe(df)

        st.subheader("Alertas detectadas")
        alerts = get_alerts(filtered)
        if not alerts:
            st.success("No hay alertas 🎉")
        else:
            for a in alerts:
                st.warning(f"{a.get('nombre')}: {a.get('motivo')}")
    else:
        st.info("No hay registros para los filtros seleccionados.")

    st.markdown("---")

    # Gráficos
    if kpis.get("fig_bar_estr") is not None:
        st.subheader("Estrés por sede")
        st.pyplot(kpis["fig_bar_estr"])

    if kpis.get("fig_trend") is not None:
        st.subheader("Tendencia del estrés")
        st.pyplot(kpis["fig_trend"])

    # Reportes
    st.subheader("Exportar reportes por sede")
    sedes_disponibles = sorted(list({d.get("sede","") for d in data}))
    for s in sedes_disponibles:
        if st.button(f"Generar CSV - {s}"):
            out = generate_csv_report_by_sede(data, s)
            st.download_button(
                label=f"Descargar {s}",
                data=out,
                file_name=f"reporte_{s}.csv",
                mime="text/csv"
            )

    if st.sidebar.button("Cerrar sesión"):
        logout()

# ------ Main ------
def main():
    if not st.session_state.logged:
        login_view()
    else:
        user = st.session_state.user
        role = user.get("role", "empleado")
        if role == "admin":
            admin_view(user)
        else:
            employee_view(user)

if __name__ == "__main__":
    main()
