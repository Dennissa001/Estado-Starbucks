import streamlit as st
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt

from utils import (
    load_data, save_data, load_users, authenticate,
    add_employee_entry, filter_data, compute_kpis,
    get_alerts, generate_csv_report_by_sede,
    tendencia_semanal_estres, pie_emociones
)

st.set_page_config(page_title="Bienestar Starbucks", layout="wide")

DATA_PATH = "data.json"
USERS_PATH = "users.json"

# Inicializar session_state
if "user" not in st.session_state:
    st.session_state.user = None
if "logged" not in st.session_state:
    st.session_state.logged = False

# ------------------------------------------------------------
# LOGIN VIEW
# ------------------------------------------------------------
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
            st.experimental_rerun()
        else:
            st.error("Usuario o contraseña incorrectos")

# ------------------------------------------------------------
# LOGOUT
# ------------------------------------------------------------
def logout():
    st.session_state.user = None
    st.session_state.logged = False
    st.experimental_rerun()

# ------------------------------------------------------------
# EMPLOYEE VIEW
# ------------------------------------------------------------
def employee_view(user):
    st.header("Registro de bienestar — Empleado")
    st.write(f"Sede detectada: **{user.get('sede','(no definida)')}**")

    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    st.info(f"Fecha: {fecha_hoy}")

    # Ahora sí se puede seleccionar la hora
    hora_ingreso = st.time_input("Hora de ingreso")
    hora_salida = st.time_input("Hora de salida")

    descanso = st.number_input("Minutos de descanso", 0, 120, 45)

    estres = st.slider("Nivel de estrés (1= bajo, 10 = alto)", 1, 10, 5)

    estado_emocional = st.selectbox(
        "¿Cómo te sientes hoy?",
        ["Feliz", "Tranquilo", "Normal", "Estresado", "Agotado"]
    )

    if st.button("Registrar"):
        add_employee_entry(
            DATA_PATH, user, fecha_hoy,
            str(hora_ingreso), str(hora_salida),
            str(descanso), estres, estado_emocional
        )
        st.success("Registro guardado exitosamente 💚")
        st.experimental_rerun()

    st.button("Cerrar sesión", on_click=logout)

# ------------------------------------------------------------
# ADMIN VIEW
# ------------------------------------------------------------
def admin_view(user):
    st.header("Panel Administrador — Bienestar del Personal")

    data = load_data(DATA_PATH)
    if not data:
        st.warning("No existen datos aún.")
        st.button("Cerrar sesión", on_click=logout)
        return

    # SIDEBAR — FILTROS
    fecha_filtro = st.sidebar.date_input("Filtrar por fecha", value=datetime.today())
    sedes = sorted(list({d["sede"] for d in data}))
    sedes = ["Todas"] + sedes
    sede_sel = st.sidebar.selectbox("Sede", sedes)
    sede_filter = None if sede_sel == "Todas" else sede_sel

    filtered = filter_data(data, fecha=str(fecha_filtro), sede=sede_filter)

    # KPIs
    kpis = compute_kpis(filtered)

    c1, c2, c3 = st.columns(3)
    c1.metric("Estrés promedio", f"{kpis['estres_promedio']:.1f}")
    c2.metric("% descanso cumplido (45 min)", f"{kpis['pct_descanso']:.1f}%")
    c3.metric("Alertas activas", kpis['alertas_count'])

    st.markdown("---")

    # TABLA
    st.subheader("Registros filtrados")
    if filtered:
        df = pd.DataFrame(filtered)
        st.dataframe(df)
    else:
        st.info("No hay registros para los filtros.")

    st.markdown("---")

    # ALERTAS ORDENADAS
    st.subheader("🚨 Alertas detectadas (ordenadas)")
    alertas = get_alerts(filtered)
    if alertas:
        for a in alertas:
            st.warning(
                f"Sede: **{a['sede']}** — {a['nombre']} | "
                f"{a['motivo']} | Estrés: {a['estres']} | {a['fecha']}"
            )
    else:
        st.success("No se han detectado alertas.")

    st.markdown("---")

    # GRAFICO — TENDENCIA SEMANAL
    st.subheader("📊 Tendencia semanal del estrés (barras)")

    fechas, valores = tendencia_semanal_estres(data)

    if fechas is not None:
        fig, ax = plt.subplots()
        ax.bar(fechas, valores)
        ax.set_xlabel("Fecha")
        ax.set_ylabel("Estrés promedio")
        ax.set_title("Tendencia semanal del estrés")
        st.pyplot(fig)
    else:
        st.info("Aún no hay suficientes datos para la tendencia semanal.")

    st.markdown("---")

    # PIE CHART EMOCIONES
    st.subheader("🟢 Distribución emocional (gráfico circular)")

    labels, sizes = pie_emociones(filtered)
    if labels:
        fig2, ax2 = plt.subplots()
        ax2.pie(sizes, labels=labels, autopct="%1.1f%%")
        ax2.set_title("Estado emocional del personal")
        st.pyplot(fig2)
    else:
        st.info("No hay datos disponibles para este análisis.")

    st.markdown("---")

    # EXPORTAR CSV POR SEDE
    st.subheader("📥 Exportar reportes por sede")
    sedes_unicas = sorted(list({d["sede"] for d in data}))

    for s in sedes_unicas:
        if st.button(f"Generar CSV — {s}"):
            out = generate_csv_report_by_sede(data, s)
            st.download_button(
                label=f"Descargar reporte {s}",
                data=out,
                file_name=f"reporte_{s}.csv",
                mime="text/csv"
            )

    st.sidebar.button("Cerrar sesión", on_click=logout)

# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
def main():
    if not st.session_state.logged:
        login_view()
    else:
        role = st.session_state.user.get("role", "empleado")
        if role == "admin":
            admin_view(st.session_state.user)
        else:
            employee_view(st.session_state.user)

if __name__ == "__main__":
    main()
