# app.py
import streamlit as st
from datetime import datetime, time
import pandas as pd

from utils import (
    load_data,
    save_data,
    load_users,
    authenticate,
    add_employee_entry,
    filter_data,
    compute_kpis,
    get_alerts,
    generate_csv_report_by_sede
)

st.set_page_config(page_title="Bienestar Starbucks", layout="wide")

DATA_PATH = "data.json"
USERS_PATH = "users.json"

# -------------------------
# Sesión y estado inicial
# -------------------------
if "user" not in st.session_state:
    st.session_state.user = None
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# -------------------------
# Pantalla de login
# -------------------------
def login_view():
    st.title("Bienestar Starbucks — Iniciar sesión")
    users = load_users(USERS_PATH)

    username = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")

    if st.button("Ingresar"):
        user = authenticate(username, password, users)
        if user:
            # asegurar keys mínimas
            if "nombre" not in user:
                user["nombre"] = user.get("username", username)
            if "sede" not in user:
                user["sede"] = user.get("sede", "")
            st.session_state.user = user
            st.session_state.logged_in = True
            st.experimental_rerun()
        else:
            st.error("Usuario o contraseña incorrectos")

    st.markdown("---")
    st.info("Si no tienes cuenta de administrador, puedes ingresar con un usuario empleado definido en users.json.")

# -------------------------
# Cerrar sesión
# -------------------------
def logout():
    st.session_state.user = None
    st.session_state.logged_in = False
    st.experimental_rerun()

# -------------------------
# Vista: registro empleado
# -------------------------
def view_employee(user):
    st.header("Registro de turno — Empleado")
    st.markdown("Registra aquí tu turno y sensación del día. La sede se asocia automáticamente a tu usuario.")

    # Horas editables por el empleado (manual)
    hora_inicio = st.time_input("Hora de ingreso", value=datetime.now().time(), key="hi")
    hora_salida = st.time_input("Hora de salida", value=datetime.now().time(), key="hs")

    # Descanso + motivo si no cumplió
    descanso_ok = st.radio("¿Cumpliste tu descanso?", ["Sí", "No"]) == "Sí"
    motivo_descanso = ""
    if not descanso_ok:
        motivo_descanso = st.selectbox("Motivo del descanso no cumplido", [
            "Alta demanda de clientes", "No quiso", "Falta de personal", "Otro"
        ])

    # Nivel de estrés y estado emocional con opciones
    estres = st.slider("Nivel de estrés (0-10)", 0, 10, 5)
    estado_emocional = st.selectbox("¿Cómo te sientes hoy?", [
        "Feliz 😊", "Tranquilo 😌", "Normal 😐", "Estresado 😣", "Agotado 😫"
    ])

    comentario = st.text_area("Opcional: añade algún comentario o detalle (opcional)")

    if st.button("Registrar testimonio"):
        # Llamada a util que guarda el registro
        add_employee_entry(
            DATA_PATH,
            user,
            hora_inicio,
            hora_salida,
            descanso_ok,
            motivo_descanso,
            estres,
            estado_emocional if comentario == "" else comentario  # prefer comment if provided
        )
        st.success("Registro guardado. Gracias por compartir tu experiencia 💚")

# -------------------------
# Vista: administrador
# -------------------------
def view_admin(user):
    st.header("Panel administrador — Bienestar y cumplimiento")

    data = load_data(DATA_PATH)
    if not data:
        st.warning("No hay registros aún.")
        # show logout
        if st.button("Cerrar sesión"):
            logout()
        return

    # filtros de fecha y sede
    fecha_filtro = st.sidebar.date_input("Filtrar por fecha", value=datetime.today().date())
    sedes = sorted(list({d.get("sede", "Sin sede") for d in data}))
    sedes = ["Todas"] + sedes
    sede_sel = st.sidebar.selectbox("Filtrar por sede", sedes)
    sede_filter = None if sede_sel == "Todas" else sede_sel

    # aplicar filtro seguro mediante util
    filtered = filter_data(data, fecha=str(fecha_filtro), sede=sede_filter)

    # métricas y gráficos via util
    kpis = compute_kpis(filtered)

    # Mostrar KPIs
    col1, col2, col3 = st.columns(3)
    col1.metric("Estrés promedio", f"{kpis.get('estres_promedio', 0):.1f}")
    col2.metric("% descanso cumplido", f"{kpis.get('pct_descanso', 0):.1f}%")
    col3.metric("Alertas detectadas", kpis.get('alertas_count', 0))

    st.markdown("---")

    # Tabla de registros filtrados (si existen)
    if filtered:
        df_show = pd.DataFrame(filtered)
        # generar alertas detalladas usando get_alerts (util)
        alerts = get_alerts(filtered)
        st.subheader("Registros (filtrados)")
        st.dataframe(df_show)

        # Mostrar alertas individuales
        st.subheader("Alertas detectadas")
        if not alerts:
            st.success("No se detectaron alertas para estos filtros 🎉")
        else:
            for a in alerts:
                st.warning(f"{a.get('nombre', 'Empleado')}: {a.get('motivo')}")

    else:
        st.info("No hay registros para los filtros seleccionados.")

    st.markdown("---")
    # Gráfico (si util devolvió figura)
    fig = kpis.get("fig_bar_estr") or kpis.get("fig_bar") or kpis.get("fig_dept")
    if fig is not None:
        st.subheader("Gráfico de estrés por sede / tendencia")
        st.pyplot(fig)

    # REPORTES: generar por sede y descargar
    st.subheader("Exportar reportes por sede")
    sedes_disponibles = sorted(list({d.get("sede", "") for d in data}))
    for s in sedes_disponibles:
        if st.button(f"Generar CSV - {s}"):
            csv_bytes = generate_csv_report_by_sede(data, s)
            # generate_csv_report_by_sede puede devolver bytes o str; acomodamos
            if isinstance(csv_bytes, str):
                csv_bytes = csv_bytes.encode("utf-8")
            st.download_button(label=f"Descargar {s}", data=csv_bytes, file_name=f"reporte_{s}.csv", mime="text/csv")

    # Logout
    if st.sidebar.button("Cerrar sesión"):
        logout()

# -------------------------
# Programa principal
# -------------------------
def main():
    if not st.session_state.logged_in:
        login_view()
    else:
        user = st.session_state.user
        # asegurar claves mínimas
        user.setdefault("username", user.get("username", "unknown"))
        user.setdefault("nombre", user.get("nombre", user.get("username")))
        user.setdefault("sede", user.get("sede", ""))

        # menú por rol
        if user.get("role") == "admin":
            view_admin(user)
        else:
            view_employee(user)

# Ejecutar
if __name__ == "__main__":
    main()
