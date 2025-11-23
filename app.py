import streamlit as st
import pandas as pd
from datetime import datetime, time
from utils import (
    load_data, save_data, load_users, authenticate, add_employee_entry,
    filter_data, get_alerts, compute_kpis, generate_csv_report_by_sede,
    generate_pdf_report
)

DATA_PATH = "data.json"

# ---------------- LOGIN ----------------
st.set_page_config(page_title="Bienestar Starbucks", layout="wide")

if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    st.title("☕ Bienestar Starbucks — Login")

    users = load_users()
    username = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")
    login_btn = st.button("Ingresar")

    if login_btn:
        user = authenticate(username, password, users)
        if user:
            st.session_state.user = user
            st.experimental_rerun()
        else:
            st.error("Credenciales inválidas.")
    st.stop()

# Logged user
user = st.session_state.user

# ---------------- Sidebar ----------------
st.sidebar.title(f"Bienvenido, {user.get('nombre', user.get('username'))}")
opt = st.sidebar.radio(
    "Navegación",
    ["Registrar ingreso", "Ver registros", "Alertas", "Reportes"]
)
if st.sidebar.button("Cerrar sesión"):
    st.session_state.user = None
    st.experimental_rerun()

# --------------------------------------------------
# ------------- 1. REGISTRO DE INGRESO --------------
# --------------------------------------------------
if opt == "Registrar ingreso":
    st.title("📝 Registrar ingreso del colaborador")

    fecha = st.date_input("Fecha", datetime.now())
    hora_inicio = st.time_input("Hora de inicio", time(8, 0))
    hora_salida = st.time_input("Hora de salida", time(17, 0))
    descanso = st.number_input("Minutos de descanso", 0, 180, 45)
    estres = st.slider("Nivel de estrés (1-10)", 1, 10, 5)
    estado = st.selectbox("Estado emocional", [
        "Tranquilo", "Normal", "Estresado 😣", "Agotado 😫"
    ])
    comentario = st.text_area("Comentario opcional")

    if st.button("Guardar registro"):
        add_employee_entry(
            DATA_PATH, user,
            fecha.strftime("%Y-%m-%d"),
            hora_inicio, hora_salida,
            descanso, estres, estado, comentario
        )
        st.success("Registro guardado correctamente.")

# --------------------------------------------------
# ---------------- 2. VER REGISTROS ----------------
# --------------------------------------------------
elif opt == "Ver registros":
    st.title("📋 Registros del personal")
    data = load_data()

    if not data:
        st.info("No hay registros aún.")
        st.stop()

    fecha_filtro = st.date_input("Filtrar por fecha (opcional)", None)
    sede_filtro = st.selectbox("Filtrar por sede (opcional)", ["", "Lima Norte", "San Isidro", "Miraflores"])

    data_filtrada = filter_data(
        data,
        fecha_filtro.strftime("%Y-%m-%d") if fecha_filtro else None,
        sede_filtro if sede_filtro else None
    )

    st.write(f"Mostrando **{len(data_filtrada)} registros**:")
    st.dataframe(pd.DataFrame(data_filtrada))

# --------------------------------------------------
# -------------------- ALERTAS ----------------------
# --------------------------------------------------
elif opt == "Alertas":
    st.title("🚨 Alertas de bienestar")

    data = load_data()
    if not data:
        st.info("No hay datos para generar alertas.")
        st.stop()

    alerts = get_alerts(data)

    if not alerts:
        st.success("No se detectaron alertas.")
        st.stop()

    df = pd.DataFrame(alerts)
    st.dataframe(df)

# --------------------------------------------------
# -------------------- REPORTES ---------------------
# --------------------------------------------------
elif opt == "Reportes":
    st.title("📊 Reportes y descargas")
    data = load_data()

    if not data:
        st.info("No hay datos para generar reportes.")
        st.stop()

    df = pd.DataFrame(data)

    # ------------ KPIs -------------
    st.subheader("Indicadores globales")
    kpis = compute_kpis(data)

    col1, col2, col3 = st.columns(3)
    col1.metric("Estrés promedio", f"{kpis['estres_promedio']:.2f}")
    col2.metric("% descansos ≥ 45 min", f"{kpis['pct_descanso']:.1f}%")
    col3.metric("Alertas detectadas", kpis["alertas_count"])

    # ------------ Gráficos -------------
    st.subheader("Gráficos")

    if kpis["pie_estado"]:
        st.pyplot(kpis["pie_estado"])

    if kpis["fig_week"]:
        st.pyplot(kpis["fig_week"])

    # ------------ DESCARGAS -------------
    st.subheader("Descargas de reportes")

    sede = st.selectbox("Seleccionar sede para CSV", ["Lima Norte", "San Isidro", "Miraflores"])

    if st.button("Descargar CSV de la sede"):
        csv_data = generate_csv_report_by_sede(data, sede)
        st.download_button(
            label=f"Descargar CSV — {sede}",
            data=csv_data,
            file_name=f"reporte_{sede}.csv",
            mime="text/csv"
        )

    if st.button("Descargar PDF general"):
        pdf_path = generate_pdf_report(data)
        with open(pdf_path, "rb") as f:
            st.download_button(
                "Descargar PDF completo",
                f.read(),
                file_name="Reporte_general.pdf",
                mime="application/pdf"
            )
