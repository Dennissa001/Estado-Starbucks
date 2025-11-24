# app.py
import streamlit as st
from datetime import date
import pandas as pd

from utils import (
    load_data, load_users, authenticate,
    add_employee_entry, filter_data,
    compute_kpis, get_alerts,
    generate_pdf_full, generate_pdf_alerts,
    generate_pdf_charts, generate_pdf_by_sede,
    generate_pdf_personal
)

st.set_page_config(page_title="Bienestar Starbucks", layout="wide")

DATA_PATH = "data.json"
USERS_PATH = "users.json"


# ---------------------------------------------
# MANEJO SEGURO DE RERUN
# ---------------------------------------------
def safe_rerun():
    try:
        st.rerun()
    except:
        pass


# ---------------------------------------------
# SESSION
# ---------------------------------------------
if "user" not in st.session_state:
    st.session_state.user = None
if "logged" not in st.session_state:
    st.session_state.logged = False


# ---------------------------------------------
# LOGIN
# ---------------------------------------------
def login_view():
    st.title("Bienestar Starbucks — Iniciar sesión")

    users = load_users(USERS_PATH)

    username = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")

    if st.button("Ingresar", key="login_btn"):
        user = authenticate(username, password, users)
        if user:
            # normaliza "rol" ↔ "role"
            if "role" not in user:
                user["role"] = user.get("rol", "empleado")

            st.session_state.user = user
            st.session_state.logged = True
            st.success(f"Bienvenido/a {user.get('nombre', username)}")
            safe_rerun()
        else:
            st.error("Usuario o contraseña incorrectos")

    st.info("Inicia sesión usando un usuario del archivo users.json")


# ---------------------------------------------
# LOGOUT
# ---------------------------------------------
def logout():
    st.session_state.clear()
    safe_rerun()


# ---------------------------------------------
# VISTA EMPLEADO
# ---------------------------------------------
def employee_view(user):
    st.header("Registro de turno — Empleado")
    st.write(f"Sede: **{user.get('sede','(no definida)')}**")

    fecha_hoy = date.today().isoformat()
    st.info(f"Fecha: {fecha_hoy}")

    hora_inicio = st.time_input("Hora de inicio")
    hora_salida = st.time_input("Hora de salida")

    descanso_min = st.number_input("Minutos de descanso", min_value=0, max_value=240, value=45)
    estres = st.slider("Nivel de estrés (0-10)", min_value=0, max_value=10, value=5)
    estado = st.selectbox("¿Cómo te sientes hoy?", ["Feliz", "Tranquilo", "Normal", "Estresado", "Agotado"])
    comentario = st.text_area("Comentario (opcional)")

    if st.button("Registrar", key="reg_employee"):
        add_employee_entry(
            DATA_PATH, user, fecha_hoy,
            hora_inicio, hora_salida,
            int(descanso_min), int(estres),
            estado, comentario
        )
        st.success("Registro guardado correctamente")
        safe_rerun()

    # ----------------------------------------
    # MIS REGISTROS
    # ----------------------------------------
    st.subheader("Mis registros")

    data = load_data(DATA_PATH)
    nombre_u = user.get("nombre", user.get("username"))
    mis_registros = [r for r in data if r.get("nombre") == nombre_u]

    if mis_registros:
        df = pd.DataFrame(mis_registros).sort_values("fecha", ascending=False)
        st.dataframe(df, use_container_width=True, height=300)

        if st.button("📄 Descargar PDF — Mis registros", key="pdf_personal_btn"):
            pdf = generate_pdf_personal(mis_registros)
            with open(pdf, "rb") as f:
                st.download_button(
                    "Descargar PDF",
                    f.read(),
                    file_name=f"mis_registros_{nombre_u}.pdf",
                    mime="application/pdf"
                )
    else:
        st.info("Aún no tienes registros.")

    st.markdown("---")

    if st.button("Cerrar sesión", key="logout_employee"):
        logout()


# ---------------------------------------------
# VISTA ADMIN
# ---------------------------------------------
def admin_view(user):
    st.header("Panel Administrador — Bienestar y Cumplimiento")

    data = load_data(DATA_PATH)
    if not data:
        st.warning("No hay registros todavía.")
        if st.button("Cerrar sesión", key="logout_admin_empty"):
            logout()
        return

    # -----------------------------------------
    # SIDEBAR
    # -----------------------------------------
    st.sidebar.title("Filtros")

    ver_todo = st.sidebar.checkbox("Ver todo el historial", value=False)

    sedes = ["Todas"] + sorted({d.get("sede","") for d in data})
    sede_sel = st.sidebar.selectbox("Sede", sedes)

    fecha_sel = st.sidebar.date_input("Filtrar por fecha (opcional)", value=None)

    # Aplicación de filtros
    if ver_todo:
        filtered = data
    else:
        fecha_filter = None if fecha_sel is None else fecha_sel.strftime("%Y-%m-%d")
        sede_filter = None if sede_sel == "Todas" else sede_sel
        filtered = filter_data(data, fecha=fecha_filter, sede=sede_filter)

    # -----------------------------------------
    # TABS
    # -----------------------------------------
    tab_reg, tab_alert, tab_graph, tab_report = st.tabs([
        "📋 Registros", "🚨 Alertas", "📊 Gráficas", "📄 Reportes"
    ])

    # --- TAB REGISTROS ---
    with tab_reg:
        st.subheader("Registros filtrados")
        if not filtered:
            st.info("Sin resultados")
        else:
            df = pd.DataFrame(filtered)
            st.dataframe(df, use_container_width=True, height=350)

            if st.button("📄 Descargar PDF — Registros filtrados", key="pdf_filtrado_btn"):
                pdf = generate_pdf_full(filtered)
                with open(pdf, "rb") as f:
                    st.download_button(
                        "Descargar PDF",
                        f.read(),
                        file_name="registros_filtrados.pdf",
                        mime="application/pdf"
                    )

    # --- TAB ALERTAS ---
    with tab_alert:
        alerts = get_alerts(filtered)
        st.subheader("Alertas detectadas")

        if not alerts:
            st.success("No se detectaron alertas")
        else:
            df_a = pd.DataFrame(alerts)
            st.dataframe(df_a, use_container_width=True, height=320)

            if st.button("📄 Descargar PDF — Alertas filtradas", key="pdf_alertas_btn"):
                pdf = generate_pdf_alerts(alerts)
                with open(pdf, "rb") as f:
                    st.download_button(
                        "Descargar PDF",
                        f.read(),
                        file_name="alertas_filtradas.pdf",
                        mime="application/pdf"
                    )

    # --- TAB GRÁFICAS ---
    with tab_graph:
        st.subheader("KPIs y Gráficas")

        kpis = compute_kpis(filtered)

        c1, c2, c3 = st.columns(3)
        c1.metric("Estrés promedio", f"{kpis['estres_promedio']:.1f}")
        c2.metric("% descanso ≥ 45 min", f"{kpis['pct_descanso']:.1f}%")
        c3.metric("Alertas detectadas", kpis['alertas_count'])

        if kpis["fig_week"]:
            st.pyplot(kpis["fig_week"])
        if kpis["pie_estado"]:
            st.pyplot(kpis["pie_estado"])

        if st.button("📄 Descargar PDF — KPIs y gráficas", key="pdf_graph_btn"):
            pdf = generate_pdf_charts(filtered)
            with open(pdf, "rb") as f:
                st.download_button(
                    "Descargar PDF",
                    f.read(),
                    file_name="reporte_graficos.pdf",
                    mime="application/pdf"
                )

    # --- TAB REPORTES POR SEDE ---
    with tab_report:
        st.subheader("Reportes por sede")

        sedes_uni = sorted({d.get("sede","") for d in data})
        for s in sedes_uni:
            st.write(f"**{s}**")

            if st.button(f"📄 Generar PDF — {s}", key=f"pdf_sede_{s}"):
                pdf = generate_pdf_by_sede(data, s)
                with open(pdf, "rb") as f:
                    st.download_button(
                        f"Descargar PDF {s}",
                        f.read(),
                        file_name=f"reporte_{s}.pdf",
                        mime="application/pdf"
                    )

    st.sidebar.markdown("---")
    if st.sidebar.button("Cerrar sesión", key="logout_admin"):
        logout()


# ---------------------------------------------
# MAIN
# ---------------------------------------------
def main():
    if not st.session_state.logged:
        login_view()
    else:
        user = st.session_state.user
        role = user.get("role","empleado")

        if role == "admin":
            admin_view(user)
        else:
            employee_view(user)


if __name__ == "__main__":
    main()
