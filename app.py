# app.py
import streamlit as st
from datetime import date, datetime
import pandas as pd

from utils import (
    load_data, load_users, authenticate,
    add_employee_entry, filter_data, compute_kpis,
    get_alerts, generate_pdf_report_by_sede, generate_pdf_report
)

st.set_page_config(page_title="Bienestar Starbucks", layout="wide")

DATA_PATH = "data.json"
USERS_PATH = "users.json"

# ---------------- Session state ----------------
if "user" not in st.session_state:
    st.session_state.user = None
if "logged" not in st.session_state:
    st.session_state.logged = False

# ----------------- LOGIN VIEW -----------------
def login_view():
    st.title("Bienestar Starbucks — Iniciar sesión")
    users = load_users(USERS_PATH)

    username = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")

    if st.button("Ingresar"):
        user = authenticate(username, password, users)
        if user:
            if "role" not in user:
                user["role"] = user.get("rol", "empleado")
            st.session_state.user = user
            st.session_state.logged = True
        else:
            st.error("Usuario o contraseña incorrectos")

    st.markdown("---")
    st.info("Usa un usuario del archivo users.json (admin o empleado).")

# ----------------- LOGOUT -----------------
def logout():
    st.session_state.user = None
    st.session_state.logged = False
    st.experimental_rerun()

# ----------------- EMPLEADO VIEW -----------------
def employee_view(user):
    st.header("Registro de turno — Empleado")
    st.write(f"Sede: **{user.get('sede','(no definida)')}**")

    fecha_hoy = date.today().isoformat()
    st.info(f"Fecha: {fecha_hoy}")

    hora_inicio = st.time_input("Hora de inicio")
    hora_salida = st.time_input("Hora de salida")

    descanso_min = st.number_input("Minutos de descanso", min_value=0, max_value=240, value=45, step=5)
    estres = st.slider("Nivel de estrés (0-10)", min_value=0, max_value=10, value=5)
    estado = st.selectbox("¿Cómo te sientes hoy?", ["Feliz", "Tranquilo", "Normal", "Estresado", "Agotado"])
    comentario = st.text_area("Comentario (opcional)")

    if st.button("Registrar"):
        add_employee_entry(
            DATA_PATH,
            user,
            fecha_hoy,
            hora_inicio,
            hora_salida,
            int(descanso_min),
            int(estres),
            estado,
            comentario
        )
        st.success("Registro guardado correctamente ✅")

    st.markdown("---")
    st.subheader("Mis registros")
    data = load_data(DATA_PATH)
    nombre_usuario = user.get("nombre", user.get("username"))
    mis_registros = [r for r in data if r.get("nombre") == nombre_usuario]
    
    if mis_registros:
        df_mis = pd.DataFrame(mis_registros).sort_values(by=["fecha"], ascending=False)
        st.dataframe(df_mis, use_container_width=True, height=300)

        if st.button("📄 Descargar PDF — Mis registros"):
            pdf_path = generate_pdf_report(mis_registros)
            with open(pdf_path, "rb") as f:
                st.download_button("Descargar PDF (Mis registros)", f.read(), file_name=f"mis_registros_{nombre_usuario}.pdf", mime="application/pdf")
    else:
        st.info("Aún no tienes registros guardados.")

    st.markdown("---")
    if st.button("Cerrar sesión"):
        logout()

# ----------------- ADMIN VIEW -----------------
def admin_view(user):
    st.header("Panel Administrador — Bienestar y cumplimiento")

    data = load_data(DATA_PATH)

    if not data:
        st.warning("No hay registros aún.")
        if st.button("Cerrar sesión"):
            logout()
        return

    # Sidebar
    st.sidebar.title("Filtros")
    ver_todo = st.sidebar.checkbox("Ver todo el historial", value=False)
    sede_options = ["Todas"] + sorted(list({d.get("sede", "") for d in data if d.get("sede","")}))
    sede_sel = st.sidebar.selectbox("Sede", sede_options)
    fecha_sel = st.sidebar.date_input("Filtrar por fecha (opcional)", value=None)

    if ver_todo:
        filtered = data.copy()
    else:
        fecha_filter = None if fecha_sel is None else fecha_sel.strftime("%Y-%m-%d")
        sede_filter = None if sede_sel == "Todas" else sede_sel
        filtered = filter_data(data, fecha=fecha_filter, sede=sede_filter)

    tab_reg, tab_alert, tab_graph, tab_report = st.tabs(["📋 Registros", "🚨 Alertas", "📊 Gráficas", "📄 Reportes"])

    # ----- TAB REGISTROS -----
    with tab_reg:
        st.subheader("Registros (filtrados)")
        if not filtered:
            st.info("No hay registros para los filtros aplicados.")
        else:
            df_filtered = pd.DataFrame(filtered)
            cols = ["sede", "fecha", "nombre", "hora_inicio", "hora_salida", "descanso", "estres", "estado", "comentario"]
            cols_present = [c for c in cols if c in df_filtered.columns]
            st.dataframe(df_filtered[cols_present].sort_values(by=["sede","fecha","nombre"]), use_container_width=True, height=350)

            if st.button("📄 Descargar PDF — Registros filtrados"):
                pdf_path = generate_pdf_report(filtered)
                with open(pdf_path, "rb") as f:
                    st.download_button("Descargar PDF (Registros filtrados)", f.read(), file_name="registros_filtrados.pdf", mime="application/pdf")

    # ----- TAB ALERTAS -----
    with tab_alert:
        st.subheader("Alertas ordenadas")
        alerts = get_alerts(filtered)
        if not alerts:
            st.success("No se detectaron alertas 🎉")
        else:
            df_alerts = pd.DataFrame(alerts)
            df_alerts = df_alerts[["sede","nombre","motivo","estres","fecha"]] if not df_alerts.empty else df_alerts
            st.dataframe(df_alerts.sort_values(by=["sede","fecha","nombre"]), use_container_width=True, height=300)

            if st.button("📄 Descargar PDF — Alertas filtradas"):
                pdf_path = generate_pdf_report(alerts)
                with open(pdf_path, "rb") as f:
                    st.download_button("Descargar PDF (Alertas filtradas)", f.read(), file_name="alertas_filtradas.pdf", mime="application/pdf")

    # ----- TAB GRAFICAS -----
    with tab_graph:
        st.subheader("KPIs y Gráficas")
        kpis = compute_kpis(filtered)

        c1, c2, c3 = st.columns(3)
        c1.metric("Estrés promedio", f"{kpis['estres_promedio']:.1f}")
        c2.metric("% descanso ≥ 45 min", f"{kpis['pct_descanso']:.1f}%")
        c3.metric("Alertas detectadas", kpis['alertas_count'])

        st.markdown("---")

        if st.button("📄 Descargar PDF — General (KPIs + Gráficas)"):
            pdf_path = generate_pdf_report(data)
            with open(pdf_path, "rb") as f:
                st.download_button("Descargar PDF general", f.read(), file_name="reporte_general.pdf", mime="application/pdf")

    # ----- TAB REPORTES -----
    with tab_report:
        st.subheader("Reportes por sede (PDF)")
        sedes_unicas = sorted(list({d.get("sede", "") for d in data if d.get("sede","")}))

        if not sedes_unicas:
            st.info("No hay sedes registradas.")
        else:
            for s in sedes_unicas:
                st.write(f"**{s}**")
                if st.button(f"📄 Generar PDF — {s}", key=f"pdf_sede_{s}"):
                    pdf_path = generate_pdf_report_by_sede(data, s)
                    with open(pdf_path, "rb") as f:
                        st.download_button(f"Descargar PDF — {s}", f.read(), file_name=f"reporte_{s}.pdf", mime="application/pdf")

    st.sidebar.markdown("---")
    if st.sidebar.button("Cerrar sesión"):
        logout()

# ----------------- MAIN -----------------
def main():
    if not st.session_state.logged or st.session_state.user is None:
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
