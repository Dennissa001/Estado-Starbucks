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

# ---- Session State ----
if "user" not in st.session_state:
    st.session_state.user = None
if "logged" not in st.session_state:
    st.session_state.logged = False


# ---- Login ----
def login_view():
    st.title("Bienestar Starbucks — Login")

    users = load_users(USERS_PATH)

    username = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")

    if st.button("Ingresar"):
        user = authenticate(username, password, users)
        if user:
            st.session_state.user = user
            st.session_state.logged = True
        else:
            st.error("Credenciales incorrectas.")


# ---- Logout ----
def logout():
    st.session_state.user = None
    st.session_state.logged = False


# ---- Empleado ----
def employee_view(user):
    st.header("Registro de turno — Empleado")
    st.write(f"Sede: **{user['sede']}**")

    now = datetime.now().time()

    hi = st.time_input("Hora de inicio", value=now)
    hs = st.time_input("Hora de salida", value=now)

    descanso_ok = st.radio("¿Tuviste descanso?", ["Sí", "No"]) == "Sí"

    motivo = ""
    if not descanso_ok:
        motivo = st.selectbox("Motivo de no descanso", [
            "Alta demanda", "No quiso", "Falta de personal", "Otro"
        ])

    estres = st.slider("Nivel de estrés (0-10)", 0, 10, 5)

    estado = st.selectbox("Estado emocional", [
        "Feliz 😊", "Tranquilo 😌", "Normal 😐", "Estresado 😣", "Agotado 😫"
    ])

    comentario = st.text_area("Comentario (opcional)")

    if st.button("Guardar registro"):
        add_employee_entry(
            DATA_PATH, user,
            hi, hs, descanso_ok, motivo,
            estres, estado, comentario
        )
        st.success("Registro guardado correctamente.")

    st.button("Cerrar sesión", on_click=logout)


# ---- Admin ----
def admin_view(user):
    st.title("Panel Administrador — Bienestar Starbucks")

    data = load_data(DATA_PATH)
    if not data:
        st.warning("No hay registros.")
        st.button("Cerrar sesión", on_click=logout)
        return

    # ---- Filtros ----
    fecha = st.sidebar.date_input("Filtrar por fecha")
    sedes = ["Todas"] + sorted(list({d['sede'] for d in data}))
    sede_sel = st.sidebar.selectbox("Filtrar por sede", sedes)

    sede_filter = None if sede_sel == "Todas" else sede_sel

    filtered = filter_data(data, fecha=str(fecha), sede=sede_filter)

    # ---- KPIs ----
    kpis = compute_kpis(filtered)

    col1, col2, col3 = st.columns(3)
    col1.metric("Estrés promedio", f"{kpis['estres_promedio']:.1f}")
    col2.metric("% descanso cumplido", f"{kpis['pct_descanso']:.1f}%")
    col3.metric("Alertas detectadas", kpis['alertas_count'])

    st.markdown("---")

    # ---- Tabla principal ----
    if filtered:
        st.subheader("Registros filtrados")
        st.dataframe(pd.DataFrame(filtered))
    else:
        st.info("No hay registros con estos filtros.")

    # ---- Alertas ordenadas ----
    st.subheader("Alertas")
    alerts = get_alerts(filtered)
    if alerts:
        df_alert = pd.DataFrame(alerts).sort_values(by=["sede", "fecha"])
        st.dataframe(df_alert)
    else:
        st.success("Sin alertas.")

    # ---- Gráfico circular ----
    if kpis["pie_estado"] is not None:
        st.subheader("Distribución emocional")
        st.pyplot(kpis["pie_estado"])

    # ---- Tendencia semanal ----
    if kpis["fig_semana"] is not None:
        st.subheader("Tendencia semanal del estrés")
        st.pyplot(kpis["fig_semana"])

    st.markdown("---")

    # ---- Reportes ----
    st.subheader("Exportar CSV por sede")
    for s in sorted(list({d["sede"] for d in data})):
        if st.button(f"Generar CSV - {s}"):
            csv = generate_csv_report_by_sede(data, s)
            st.download_button(
                f"Descargar {s}",
                csv,
                file_name=f"reporte_{s}.csv",
                mime="text/csv"
            )

    st.sidebar.button("Cerrar sesión", on_click=logout)


# ---- Main ----
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
