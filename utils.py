import streamlit as st
import pandas as pd
from datetime import datetime
from utils import load_data, save_data, filter_data, generar_alertas

st.set_page_config(page_title="Estado Starbucks", page_icon="☕")

# ----------------------------
# Manejo de sesión
# ----------------------------
if "user" not in st.session_state:
    st.session_state.user = None


# ----------------------------
# LOGIN
# ----------------------------
def login():
    st.title("☕ Starbucks - Bienestar Laboral")

    usuario = st.text_input("Usuario:")
    password = st.text_input("Contraseña:", type="password")

    if st.button("Ingresar"):
        if usuario == "admin" and password == "admin123":
            st.session_state.user = "admin"
        else:
            st.session_state.user = usuario  # empleado cualquiera
        st.rerun()


# ----------------------------
# CERRAR SESIÓN
# ----------------------------
def cerrar_sesion():
    if st.button("Cerrar sesión"):
        st.session_state.user = None
        st.rerun()


# ----------------------------
# VISTA EMPLEADO
# ----------------------------
def vista_empleado():
    st.header("Registro de Estado - Empleado")

    fecha = st.date_input("Fecha")
    sede = st.selectbox("Sede", ["Larcomar", "San Miguel", "Jockey", "Miraflores"])

    # ➤ EDICIÓN manual de horas
    hora_ingreso = st.text_input("Hora de ingreso (HH:MM)", placeholder="08:00")
    hora_salida = st.text_input("Hora de salida (HH:MM)", placeholder="17:00")

    # ➤ Estado emocional con opciones
    estado = st.selectbox("¿Cómo te sientes hoy?", [
        "Feliz", "Neutral", "Cansado", "Estresado", "Triste", "Ansioso"
    ])

    testimonio = st.text_area("Describe tu día laboral:")

    if st.button("Guardar registro"):
        data = load_data()

        data.append({
            "usuario": st.session_state.user,
            "fecha": str(fecha),
            "sede": sede,
            "hora_ingreso": hora_ingreso,
            "hora_salida": hora_salida,
            "estado": estado,
            "testimonio": testimonio
        })

        save_data(data)
        st.success("Registro guardado correctamente 💚")

    cerrar_sesion()


# ----------------------------
# VISTA ADMIN
# ----------------------------
def vista_admin():
    st.title("📊 Panel Administrador - Starbucks")

    data = load_data()

    if not data:
        st.warning("No hay datos registrados aún.")
        cerrar_sesion()
        return

    df = pd.DataFrame(data)

    # Filtros
    fecha = st.date_input("Filtrar por fecha", value=None)
    sede = st.selectbox("Filtrar por sede", ["", "Larcomar", "San Miguel", "Jockey", "Miraflores"])

    filtered = filter_data(data, fecha=str(fecha) if fecha else None, sede=sede if sede else None)
    df_filtered = pd.DataFrame(filtered)

    # Generar alertas
    df_filtered = generar_alertas(df_filtered)

    st.subheader("Registros de empleados")
    st.dataframe(df_filtered)

    # -------------------------
    # Gráfico (estado emocional)
    # -------------------------
    st.subheader("Gráfico de estados emocionales")

    if "estado" in df.columns:
        conteo = df["estado"].value_counts()
        st.bar_chart(conteo)

    cerrar_sesion()


# ----------------------------
# CONTROL PRINCIPAL
# ----------------------------

if st.session_state.user is None:
    login()
elif st.session_state.user == "admin":
    vista_admin()
else:
    vista_empleado()
