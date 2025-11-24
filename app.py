import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from utils import load_users, load_alerts, load_records, save_record

st.set_page_config(page_title="Dashboard Starbucks", layout="wide")

# ---------- SESIÓN ----------
if "logged_user" not in st.session_state:
    st.session_state.logged_user = None

# ---------- LOGIN ----------
if st.session_state.logged_user is None:
    st.title("☕ Sistema Starbucks – Login")

    users = load_users()
    username = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")

    if st.button("Ingresar"):
        user = users.query("username == @username and password == @password")
        if len(user) == 1:
            st.session_state.logged_user = username
            st.success("Ingresaste correctamente")
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos")

    st.stop()

# ---------- MENÚ ----------
st.sidebar.title(f"Bienvenido, {st.session_state.logged_user}")
page = st.sidebar.radio(
    "Navegación",
    ["Registrar Estrés", "Gráfica Semanal", "Descargas", "Cerrar Sesión"]
)

# ---------- CERRAR SESIÓN ----------
if page == "Cerrar Sesión":
    st.session_state.clear()
    st.success("Cerraste sesión correctamente.")
    st.rerun()

# ---------- REGISTRO ----------
if page == "Registrar Estrés":
    st.title("Registrar nivel de estrés")

    nivel = st.slider("Nivel de Estrés", 1, 10)
    comentario = st.text_area("Comentario (opcional)")

    if st.button("Guardar Registro"):
        save_record(st.session_state.logged_user, nivel, comentario)
        st.success("Registro guardado.")

# ---------- GRÁFICA ----------
elif page == "Gráfica Semanal":
    st.title("📊 Gráfico semanal del estrés")

    df = load_records()
    df_user = df[df["usuario"] == st.session_state.logged_user]

    if df_user.empty:
        st.info("Aún no tienes registros.")
        st.stop()

    df_user["fecha"] = pd.to_datetime(df_user["fecha"])
    df_agg = df_user.groupby("fecha")["nivel"].mean()

    # --- GRÁFICO ---
    fig, ax = plt.subplots()
    ax.bar(df_agg.index, df_agg.values)
    ax.set_xlabel("Fecha")
    ax.set_ylabel("Promedio Nivel de Estrés")
    ax.set_title("Promedio de estrés por día")

    st.pyplot(fig)

    # --- DESCARGA DE GRÁFICA ---
    buffer = BytesIO()
    fig.savefig(buffer, format="png")
    buffer.seek(0)

    st.download_button(
        label="Descargar Gráfica",
        data=buffer,
        file_name="grafica_estres.png",
        mime="image/png"
    )


# ---------- DESCARGAS ----------
elif page == "Descargas":
    st.title("📥 Descarga de Registros y Alertas")

    df_records = load_records()
    df_alerts = load_alerts()

    # CSV Registros
    st.download_button(
        "Descargar registros (CSV)",
        df_records.to_csv(index=False).encode("utf-8"),
        "registros.csv",
        "text/csv",
    )

    # CSV Alertas
    st.download_button(
        "Descargar alertas (CSV)",
        df_alerts.to_csv(index=False).encode("utf-8"),
        "alertas.csv",
        "text/csv",
    )

