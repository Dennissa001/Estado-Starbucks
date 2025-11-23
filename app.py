# app.py
import streamlit as st
import pandas as pd
from datetime import datetime, date
from utils import (
    load_data, load_users, authenticate, add_employee_entry,
    filter_data, get_alerts, compute_kpis, generate_pdf_by_sede, generate_pdf_report
)

st.set_page_config(page_title="Bienestar Starbucks", layout="wide")
DATA_PATH = "data.json"
USERS_PATH = "users.json"

# ---------------- Session & login ----------------
if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    st.title("Bienestar Starbucks — Iniciar sesión")
    users = load_users(USERS_PATH)
    username = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")
    if st.button("Ingresar"):
        user = authenticate(username, password, users)
        if user:
            # ensure role key exists (default to empleado)
            if "role" not in user:
                user["role"] = user.get("rol", "empleado")
            st.session_state.user = user
            st.experimental_rerun()
        else:
            st.error("Usuario o contraseña incorrectos")
    st.info("Usa un usuario del archivo users.json (admin o empleado).")
    st.stop()

user = st.session_state.user
role = user.get("role", "empleado")

# ---------------- Sidebar (filtros) ----------------
st.sidebar.title(f"Bienvenido, {user.get('nombre', user.get('username'))}")
st.sidebar.markdown("Filtros:")

data_raw = load_data(DATA_PATH)
# convert list to DataFrame for easier choices
df_all = pd.DataFrame(data_raw) if data_raw else pd.DataFrame(columns=["sede", "fecha"])

sede_options = ["Todas"] + sorted(df_all["sede"].dropna().unique().tolist()) if not df_all.empty else ["Todas"]
sede_sel = st.sidebar.selectbox("Sede", sede_options)
fecha_sel = st.sidebar.date_input("Filtrar por fecha (opcional)", value=None)

if st.sidebar.button("Cerrar sesión"):
    st.session_state.user = None
    st.experimental_rerun()

# ---------------- Tabs arriba ----------------
tab1, tab2, tab3, tab4 = st.tabs(["📋 Registros", "🚨 Alertas", "📊 Gráficas", "📄 Reportes"])

# ------------- TAB: REGISTROS -------------
with tab1:
    st.header("Registros (filtrados)")
    # apply filters
    filtered = filter_data(data_raw, fecha=fecha_sel.strftime("%Y-%m-%d") if fecha_sel else None, sede=sede_sel if sede_sel != "Todas" else None)

    # If non-admin, show only own records
    if role != "admin":
        nombre_usuario = user.get("nombre", user.get("username"))
        filtered = [r for r in filtered if r.get("nombre") == nombre_usuario]

    if not filtered:
        st.info("No hay registros para los filtros aplicados.")
    else:
        df_filtered = pd.DataFrame(filtered).sort_values(by=["sede", "fecha", "nombre"])
        # show small table with scroll (st.dataframe already scrolls)
        st.dataframe(df_filtered, use_container_width=True, height=400)

        # download PDF only if admin or looking at own
        if role == "admin":
            st.download_button(
                "📄 Descargar PDF (Registros filtrados)",
                data=open(generate_pdf_report(filtered), "rb").read(),
                file_name="registros_filtrados.pdf",
                mime="application/pdf"
            )

# ------------- TAB: ALERTAS -------------
with tab2:
    st.header("Alertas ordenadas")
    alerts_all = get_alerts(data_raw)
    # apply sede filter to alerts if set
    if sede_sel != "Todas":
        alerts_show = [a for a in alerts_all if a.get("sede") == sede_sel]
    else:
        alerts_show = alerts_all

    # if not admin, show only user's alerts
    if role != "admin":
        nombre_usuario = user.get("nombre", user.get("username"))
        alerts_show = [a for a in alerts_show if a.get("nombre") == nombre_usuario]

    if not alerts_show:
        st.success("No se detectaron alertas para los filtros seleccionados.")
    else:
        df_alerts = pd.DataFrame(alerts_show).sort_values(by=["sede", "fecha", "nombre"])
        st.dataframe(df_alerts, use_container_width=True, height=350)
        if role == "admin":
            st.download_button(
                "📄 Descargar PDF (Alertas)",
                data=open(generate_pdf_report(alerts_show), "rb").read(),
                file_name="alertas_filtradas.pdf",
                mime="application/pdf"
            )

# ------------- TAB: GRAFICAS -------------
with tab3:
    st.header("Gráficas y KPIs")
    # compute kpis on filtered (global or per sede)
    filtered_for_kpis = filter_data(data_raw, fecha=None, sede=sede_sel if sede_sel != "Todas" else None)
    kpis = compute_kpis(filtered_for_kpis)

    c1, c2, c3 = st.columns(3)
    c1.metric("Estrés promedio", f"{kpis['estres_promedio']:.1f}")
    c2.metric("% descanso ≥ 45 min", f"{kpis['pct_descanso']:.1f}%")
    c3.metric("Alertas detectadas", f"{kpis['alertas_count']}")

    if kpis.get("fig_week"):
        st.pyplot(kpis["fig_week"])
    if kpis.get("pie_estado"):
        st.pyplot(kpis["pie_estado"])

    # allow admin to download pdf with graphs (general)
    if role == "admin":
        if st.button("📄 Descargar PDF con gráficas (General)"):
            st.download_button(
                "Descargar PDF con gráficas",
                data=open(generate_pdf_report(data_raw), "rb").read(),
                file_name="pdf_graficas_general.pdf",
                mime="application/pdf"
            )

# ------------- TAB: REPORTES -------------
with tab4:
    st.header("Reportes por sede")
    if role != "admin":
        st.info("Solo administradores pueden descargar reportes por sede.")
    else:
        sedes = sorted(df_all["sede"].dropna().unique().tolist()) if not df_all.empty else []
        for s in sedes:
            st.write(f"### {s}")
            if st.button(f"📄 Descargar PDF — {s}", key=f"pdf_{s}"):
                path = generate_pdf_by_sede(data_raw, s)
                with open(path, "rb") as f:
                    st.download_button(f"Descargar {s}.pdf", data=f.read(), file_name=f"reporte_{s}.pdf", mime="application/pdf")

