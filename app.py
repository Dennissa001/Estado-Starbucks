# app.py
import streamlit as st
from datetime import datetime, date
import pandas as pd
import matplotlib.pyplot as plt

from utils import (
    load_data, save_data, load_users, authenticate,
    add_employee_entry, filter_data, compute_kpis,
    get_alerts, generate_csv_report_by_sede
)

st.set_page_config(page_title="Bienestar Starbucks", layout="wide")

DATA_PATH = "data.json"
USERS_PATH = "users.json"

# Session state
if "user" not in st.session_state:
    st.session_state.user = None
if "logged" not in st.session_state:
    st.session_state.logged = False

# ----------------- LOGIN -----------------
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
        else:
            st.error("Usuario o contraseña incorrectos")

    st.markdown("---")
    st.info("Usa un usuario del archivo users.json (admin o empleado).")

# ----------------- LOGOUT -----------------
def logout():
    st.session_state.user = None
    st.session_state.logged = False

# ----------------- EMPLEADO -----------------
def employee_view(user):
    st.header("Registro de turno — Empleado")
    st.write(f"Sede: **{user.get('sede','(no definida)')}**")

    # Fecha (fija al día actual para el registro)
    fecha_hoy = date.today().isoformat()
    st.info(f"Fecha: {fecha_hoy}")

    # Hora de inicio / salida (editable por el empleado)
    hora_inicio = st.time_input("Hora de inicio")
    hora_salida = st.time_input("Hora de salida")

    # Descanso en minutos
    descanso_min = st.number_input("Minutos de descanso", min_value=0, max_value=240, value=45, step=5)

    # Estrés y estado emocional
    estres = st.slider("Nivel de estrés (0-10)", min_value=0, max_value=10, value=5)
    estado = st.selectbox("¿Cómo te sientes hoy?", ["Feliz", "Tranquilo", "Normal", "Estresado", "Agotado"])

    comentario = st.text_area("Comentario (opcional)")

    if st.button("Registrar"):
        # Guardamos y mostramos confirmación
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
    if st.button("Cerrar sesión"):
        logout()

# ----------------- ADMIN -----------------
def admin_view(user):
    st.header("Panel Administrador — Bienestar y cumplimiento")

    data = load_data(DATA_PATH)

    if not data:
        st.warning("No hay registros aún. Puedes usar la data de ejemplo o pedir pruebas.")
        if st.button("Cerrar sesión"):
            logout()
        return

    # Sidebar: filtros con opción "ver todo"
    st.sidebar.title("Filtros")
    ver_todo = st.sidebar.checkbox("Ver todo el historial", value=False)
    sede_options = ["Todas"] + sorted(list({d.get("sede", "") for d in data}))
    sede_sel = st.sidebar.selectbox("Sede", sede_options)

    if ver_todo:
        filtered = data.copy()
    else:
        fecha_sel = st.sidebar.date_input("Filtrar por fecha (opcional)", value=None)
        sede_filter = None if sede_sel == "Todas" else sede_sel
        if fecha_sel is None:
            # si no selecciona fecha, aplicar solo filtro de sede (si lo eligió distinto de Todas)
            filtered = filter_data(data, fecha=None, sede=sede_filter)
        else:
            filtered = filter_data(data, fecha=str(fecha_sel), sede=sede_filter)

    # KPIs y gráficos
    kpis = compute_kpis(filtered)

    col1, col2, col3 = st.columns(3)
    col1.metric("Estrés promedio", f"{kpis['estres_promedio']:.1f}")
    col2.metric("% descanso ≥ 45 min", f"{kpis['pct_descanso']:.1f}%")
    col3.metric("Alertas detectadas", kpis['alertas_count'])

    st.markdown("---")

    # Tabla de registros filtrados
    st.subheader("Registros (filtrados)")
    if filtered:
        df_filtered = pd.DataFrame(filtered)
        # mostrar con orden de columnas útil
        cols = ["sede", "fecha", "nombre", "hora_inicio", "hora_salida", "descanso", "estres", "estado", "comentario"]
        cols_present = [c for c in cols if c in df_filtered.columns]
        st.dataframe(df_filtered[cols_present].sort_values(by=["sede","fecha","nombre"]))
    else:
        st.info("No hay registros para los filtros aplicados.")

    st.markdown("---")

    # Alertas ordenadas (tabla)
    st.subheader("Alertas ordenadas")
    alerts = get_alerts(filtered)
    if alerts:
        df_alerts = pd.DataFrame(alerts)
        df_alerts = df_alerts[["sede","nombre","motivo","estres","fecha"]]
        st.table(df_alerts.sort_values(by=["sede","fecha","nombre"]))
    else:
        st.success("No se detectaron alertas para los filtros seleccionados 🎉")

    st.markdown("---")

    # Tendencia semanal del estrés (barras) — eje X con fechas de la semana
    st.subheader("Tendencia semanal del estrés (fechas de la semana)")
    # compute_kpis returns fig_week already; but we'll compute again to ensure x-axis labels are dates
    if filtered:
        # convert to df and compute last 7 days (by max fecha in filtered or data)
        df_all = pd.DataFrame(filtered)
        if not df_all.empty and "fecha" in df_all.columns:
            df_all["fecha_dt"] = pd.to_datetime(df_all["fecha"])
            max_date = df_all["fecha_dt"].max()
            week_start = (max_date - pd.Timedelta(days=max_date.weekday())).normalize()
            week_end = week_start + pd.Timedelta(days=6)
            mask = (df_all["fecha_dt"] >= week_start) & (df_all["fecha_dt"] <= week_end)
            df_week = df_all.loc[mask]
            if not df_week.empty:
                series = df_week.groupby(df_week["fecha_dt"].dt.date)["estres"].mean().reindex(
                    pd.date_range(week_start.date(), week_end.date(), freq="D").date, fill_value=0)
                figw, axw = plt.subplots(figsize=(8,3))
                axw.bar([d.strftime("%Y-%m-%d") for d in series.index], series.values)
                axw.set_xlabel("Fecha")
                axw.set_ylabel("Estrés promedio")
                axw.set_title("Estrés promedio por día (semana seleccionada)")
                plt.xticks(rotation=45)
                st.pyplot(figw)
            else:
                st.info("No hay datos en la semana más reciente para mostrar la tendencia.")
        else:
            st.info("No hay fechas disponibles para calcular la tendencia.")
    else:
        st.info("Filtra o activa 'Ver todo el historial' para ver la tendencia.")

    st.markdown("---")

    # Pie chart de estado emocional
    st.subheader("Distribución del estado emocional (pie chart)")
    if filtered:
        df_em = pd.DataFrame(filtered)
        if "estado" in df_em.columns:
            counts = df_em["estado"].value_counts()
            figp, axp = plt.subplots(figsize=(4,4))
            axp.pie(counts.values, labels=counts.index, autopct="%1.1f%%", startangle=140)
            axp.set_title("Estado emocional")
            st.pyplot(figp)
        else:
            st.info("No hay campo 'estado' en los registros.")
    else:
        st.info("No hay datos para el pie chart.")

    st.markdown("---")

    # Exportar CSV por sede
    st.subheader("Exportar CSV por sede")
    sedes_unicas = sorted(list({d.get("sede", "") for d in data}))
    for s in sedes_unicas:
        if st.button(f"Generar CSV — {s}"):
            csv_bytes = generate_csv_report_by_sede(data, s)
            st.download_button(
                label=f"Descargar reporte {s}",
                data=csv_bytes,
                file_name=f"reporte_{s}.csv",
                mime="text/csv"
            )

    if st.sidebar.button("Cerrar sesión"):
        logout()

# ----------------- MAIN -----------------
def main():
    if not st.session_state.logged:
        login_view()
    else:
        user = st.session_state.user
        if user.get("role") == "admin":
            admin_view(user)
        else:
            employee_view(user)

if __name__ == "__main__":
    main()
