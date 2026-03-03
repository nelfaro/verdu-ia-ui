import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
import requests
import os

# Configuración de página
st.set_page_config(page_title="Verdu IA - Panel de Control", layout="wide")

# Conexión a la Base de Datos (Se usarán variables de entorno de Easypanel)
def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "agentes_db_postgres"),
        database=os.getenv("DB_NAME", "postgres),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASS", "Q!6x$8wLtwqbWv2"),
        port=os.getenv("DB_PORT", "5432")
    )

st.title("🍎 Verdu IA - Gestión Mayorista")

# --- MENÚ LATERAL ---
menu = st.sidebar.selectbox("Ir a:", ["Dashboard Analíticas", "Gestión de Vendedores", "Carga de Stock (CSV)", "Conexión WhatsApp"])

# --- PÁGINA 1: DASHBOARD ---
if menu == "Dashboard Analíticas":
    st.header("📊 Dashboard de Resultados")
    conn = get_connection()
    
    # KPIs Rápidos
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        beneficio = pd.read_sql("SELECT SUM(beneficio) FROM pedidos WHERE fecha = CURRENT_DATE", conn).iloc[0,0]
        st.metric("Beneficio Real Hoy", f"${beneficio:,.2f}" if beneficio else "$0")
    
    with col2:
        conversaciones = pd.read_sql("SELECT COUNT(*) FROM log_conversaciones WHERE fecha::date = CURRENT_DATE", conn).iloc[0,0]
        st.metric("Actividad (Chats)", conversaciones)

    # Gráfico de Ventas por Vendedor
    st.subheader("📈 Ventas por Vendedor")
    query_vendedores = """
        SELECT v.nombre, SUM(p.total_venta) as venta
        FROM pedidos p
        JOIN vendedores v ON p.cliente_whatsapp = v.whatsapp
        WHERE p.fecha = CURRENT_DATE
        GROUP BY v.nombre
    """
    df_vendedores = pd.read_sql(query_vendedores, conn)
    if not df_vendedores.empty:
        fig = px.bar(df_vendedores, x='nombre', y='venta', color='nombre', title="Ventas del Día")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Aún no hay pedidos registrados hoy.")
    conn.close()

# --- PÁGINA 2: GESTIÓN DE VENDEDORES ---
elif menu == "Gestión de Vendedores":
    st.header("👥 Administrar Vendedores Oficiales")
    conn = get_connection()
    cur = conn.cursor()

    # Formulario para agregar
    with st.expander("➕ Registrar Nuevo Vendedor"):
        with st.form("add_vendedor"):
            n_nombre = st.text_input("Nombre Completo")
            n_whatsapp = st.text_input("Número WhatsApp (con @s.whatsapp.net)")
            if st.form_submit_button("Guardar Vendedor"):
                cur.execute("INSERT INTO vendedores (whatsapp, nombre) VALUES (%s, %s)", (n_whatsapp, n_nombre))
                conn.commit()
                st.success("Vendedor registrado.")

    # Lista de vendedores para dar de baja
    st.subheader("Lista de Vendedores Activos")
    df_v = pd.read_sql("SELECT * FROM vendedores", conn)
    for index, row in df_v.iterrows():
        c1, c2 = st.columns([3, 1])
        c1.write(f"👤 {row['nombre']} ({row['whatsapp']})")
        if c2.button("Dar de Baja", key=row['whatsapp']):
            cur.execute("DELETE FROM vendedores WHERE whatsapp = %s", (row['whatsapp'],))
            conn.commit()
            st.rerun()
    conn.close()

# --- PÁGINA 3: CARGA DE CSV ---
elif menu == "Carga de Stock (CSV)":
    st.header("📤 Cargar Archivo de Stock")
    st.write("Sube el archivo .CSV para actualizar los precios y la foto diaria.")
    
    uploaded_file = st.file_uploader("Elegir archivo .CSV", type="csv")
    if uploaded_file is not None:
        if st.button("Procesar y Enviar a Drive"):
            # Enviamos el archivo al Webhook de n8n que ya tienes para que él lo suba al Drive
            files = {"file": uploaded_file.getvalue()}
            response = requests.post("TU_WEBHOOK_N8N_URL", files=files)
            if response.status_code == 200:
                st.success("Archivo enviado correctamente. n8n procesará el stock en segundos.")
            else:
                st.error("Error al conectar con n8n.")

# --- PÁGINA 4: WHATSAPP ---
elif menu == "Conexión WhatsApp":
    st.header("🔗 Puente WhatsApp")
    st.write("Si el agente se desconecta, escanea el código QR aquí abajo.")
    # Reemplaza con la URL de tu puente (Evolution API, o el que uses)

    st.components.v1.iframe("https://agentes-puentewhatsapp.xjkmv6.easypanel.host/", height=600, scrolling=True)
