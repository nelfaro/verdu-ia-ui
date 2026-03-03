import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
import os
import requests

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Verdu IA - Control", layout="wide", page_icon="🍎")

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "agentes_db_postgres"),
        database=os.getenv("DB_NAME", "db_agente"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASS"),
        port=os.getenv("DB_PORT", "5432")
    )

# --- ESTILOS PERSONALIZADOS ---
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

st.title("🍏 Sistema de Gestión Verdu IA")
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2329/2329865.png", width=100)
menu = st.sidebar.selectbox("Navegación", ["📈 Dashboard BI", "👥 Vendedores Oficiales", "📤 Carga de Stock", "📲 Conexión WhatsApp"])

# --- 1. DASHBOARD BI (Puntos 1 a 5 de Analíticas) ---
if menu == "📈 Dashboard BI":
    st.header("📊 Analíticas del Negocio")
    conn = get_connection()
    
    # KPIs Superiores
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Analítica 1: Beneficio Real
        res = pd.read_sql("SELECT SUM(beneficio) as b FROM pedidos WHERE fecha::date = (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date", conn)
        val = res['b'].iloc[0] or 0
        st.metric("Beneficio Real (Hoy)", f"${val:,.2f}")
        
    with col2:
        # Analítica 3: Pedidos Cerrados
        res = pd.read_sql("SELECT COUNT(*) as c FROM pedidos WHERE fecha::date = (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date", conn)
        st.metric("Ventas Cerradas", res['c'].iloc[0])

    with col3:
        # Analítica 2: Actividad
        res = pd.read_sql("SELECT COUNT(*) as c FROM log_conversaciones WHERE fecha::date = (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date", conn)
        st.metric("Chats Atendidos", res['c'].iloc[0])

    with col4:
        # Analítica 4: Producto Estrella
        st.metric("Producto Top", "Ver Detalle")

    st.divider()

    # Gráfico de Ventas por Vendedor
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("💰 Rentabilidad por Vendedor")
        query = """
            SELECT v.nombre, SUM(p.beneficio) as ganancia
            FROM pedidos p
            JOIN vendedores v ON p.cliente_whatsapp = v.whatsapp
            WHERE p.fecha::date = (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date
            GROUP BY v.nombre
        """
        df_v = pd.read_sql(query, conn)
        if not df_v.empty:
            fig = px.pie(df_v, values='ganancia', names='nombre', hole=.4, color_discrete_sequence=px.colors.sequential.Greens_r)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.write("No hay datos de vendedores hoy.")

    with c2:
        st.subheader("📉 Stock Crítico (Prorrateo)")
        # Muestra qué productos tienen poco stock
        df_s = pd.read_sql("SELECT nombre, stock FROM productos WHERE stock < 10 ORDER BY stock ASC LIMIT 5", conn)
        st.table(df_s)

    conn.close()

# --- 2. GESTIÓN DE VENDEDORES (CRUD) ---
elif menu == "👥 Vendedores Oficiales":
    st.header("👥 Administración de Personal")
    conn = get_connection()
    cur = conn.cursor()

    # Formulario para agregar
    with st.form("nuevo_v"):
        st.write("Registrar nuevo vendedor oficial")
        n_nombre = st.text_input("Nombre y Apellido")
        n_tel = st.text_input("WhatsApp ID (ej: 5493794... @s.whatsapp.net o @lid)")
        if st.form_submit_button("Guardar Vendedor"):
            cur.execute("INSERT INTO vendedores (whatsapp, nombre) VALUES (%s, %s)", (n_tel, n_nombre))
            conn.commit()
            st.success("Vendedor guardado correctamente.")
            st.rerun()

    # Listado con opción de borrado
    st.subheader("Vendedores Registrados")
    vendedores = pd.read_sql("SELECT * FROM vendedores", conn)
    for i, v in vendedores.iterrows():
        col_v, col_b = st.columns([4, 1])
        col_v.write(f"✅ **{v['nombre']}** | {v['whatsapp']}")
        if col_b.button("Dar de Baja", key=f"del_{v['whatsapp']}"):
            cur.execute("DELETE FROM vendedores WHERE whatsapp = %s", (v['whatsapp'],))
            conn.commit()
            st.error("Vendedor eliminado.")
            st.rerun()
    conn.close()

# --- 3. CARGA DE STOCK ---
elif menu == "📤 Carga de Stock":
    st.header("📤 Actualización de Inventario")
    st.info("Sube el archivo CSV del día. n8n procesará los datos automáticamente.")
    
    archivo = st.file_uploader("Subir CSV", type=["csv"])
    if archivo is not None:
        if st.button("Enviar al Agente"):
            # Enviar el archivo a tu Webhook de n8n que procesa el stock
            try:
                # REEMPLAZA ESTA URL CON TU WEBHOOK DE N8N
                url_n8n = "https://agentes-n8n.xjkmv6.easypanel.host/webhook/tu-url-csv"
                r = requests.post(url_n8n, files={"file": archivo.getvalue()})
                st.success("✅ Archivo enviado. El stock se actualizará en unos segundos.")
            except:
                st.error("No se pudo conectar con el servidor de n8n.")

# --- 4. WHATSAPP ---
elif menu == "📲 Conexión WhatsApp":
    st.header("📲 Conexión de Puente")
    st.write("Escanea el QR si el bot se desconecta.")
    # Embebe la URL de tu puente de WhatsApp
    st.components.v1.iframe("https://agentes-puentewhatsapp.xjkmv6.easypanel.host/", height=600)
