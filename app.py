import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
import os
import requests

st.set_page_config(page_title="Verdu IA BI", layout="wide", page_icon="📈")

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "agentes_db_postgres"),
        database=os.getenv("DB_NAME", "db_agente"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASS"),
        port=os.getenv("DB_PORT", "5432")
    )

st.title("🍏 Panel Inteligente - Verdu IA")

menu = st.sidebar.selectbox("Navegación", ["📈 Dashboard Hoy", "📊 Analíticas Semanales", "👥 Vendedores", "💬 CRM Chatwoot", "📤 Carga de Stock"])

# --- 1. DASHBOARD HOY ---
if menu == "📈 Dashboard Hoy":
    st.header("📊 Resultados del Día")
    conn = get_connection()
    
    # Gráfico de Torta: Vendedores vs IA (Ventas Totales)
    st.subheader("🎯 Distribución de Ventas (Sellers vs Directo)")
    query_torta = """
        SELECT 
            CASE WHEN v.nombre IS NULL THEN 'Agente (Venta Directa)' ELSE v.nombre END as origen,
            SUM(p.total_venta) as total
        FROM pedidos p
        LEFT JOIN vendedores v ON p.cliente_whatsapp = v.whatsapp
        WHERE p.fecha = (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date
        GROUP BY origen
    """
    df_t = pd.read_sql(query_torta, conn)
    if not df_t.empty:
        fig_t = px.pie(df_t, values='total', names='origen', hole=.4, title="Participación en Ventas")
        st.plotly_chart(fig_t, use_container_width=True)
    else:
        st.info("No hay ventas registradas aún.")
    conn.close()

# --- 2. ANALÍTICAS SEMANALES (BI) ---
elif menu == "📊 Analíticas Semanales":
    st.header("📅 Rendimiento de los últimos 7 días")
    conn = get_connection()
    
    query_semanal = """
        SELECT fecha, SUM(beneficio) as beneficio, COUNT(id) as pedidos
        FROM pedidos 
        WHERE fecha > CURRENT_DATE - INTERVAL '7 days'
        GROUP BY fecha ORDER BY fecha ASC
    """
    df_s = pd.read_sql(query_semanal, conn)
    
    c1, c2 = st.columns(2)
    with c1:
        st.write("💰 **Beneficio Diario**")
        st.bar_chart(df_s, x="fecha", y="beneficio")
    with c2:
        st.write("📦 **Pedidos Totales**")
        st.bar_chart(df_s, x="fecha", y="pedidos")
    
    st.write("💬 **Actividad de Chats (Log)**")
    df_logs = pd.read_sql("SELECT fecha::date as f, COUNT(*) as c FROM log_conversaciones GROUP BY f ORDER BY f DESC LIMIT 7", conn)
    st.line_chart(df_logs, x="f", y="c")
    conn.close()

# --- 3. GESTIÓN DE VENDEDORES (MEJORADA) ---
elif menu == "👥 Vendedores":
    st.header("👥 Gestión de Personal")
    conn = get_connection()
    cur = conn.cursor()
    
    st.subheader("Personas que escribieron recientemente (Sugeridos)")
    recientes = pd.read_sql("SELECT DISTINCT nombre, whatsapp FROM clientes ORDER BY whatsapp DESC LIMIT 5", conn)
    for i, r in recientes.iterrows():
        if st.button(f"Asignar como Vendedor: {r['nombre']}"):
            cur.execute("INSERT INTO vendedores (whatsapp, nombre) VALUES (%s, %s) ON CONFLICT DO NOTHING", (r['whatsapp'], r['nombre']))
            conn.commit()
            st.rerun()

    st.divider()
    st.subheader("Vendedores Actuales")
    vend = pd.read_sql("SELECT * FROM vendedores", conn)
    st.dataframe(vend, use_container_width=True)
    conn.close()

# --- 4. CRM CHATWOOT (EMBEBIDO) ---
elif menu == "💬 CRM Chatwoot":
    st.header("💬 CRM Chatwoot")
    # Intentamos embeberlo. Nota: Si Chatwoot bloquea iframes, aparecerá el botón.
    st.link_button("Abrir Chatwoot en pestaña nueva", "https://agentes-chatwoot.xjkmv6.easypanel.host/")
    st.components.v1.iframe("https://agentes-chatwoot.xjkmv6.easypanel.host/", height=800, scrolling=True)

# --- 5. CARGA DE STOCK ---
elif menu == "📤 Carga de Stock":
    st.header("📤 Carga de Archivo")
    conn = get_connection()
    ultimo = pd.read_sql("SELECT nombre_archivo, fecha_proceso FROM control_cargas ORDER BY fecha_proceso DESC LIMIT 1", conn)
    if not ultimo.empty:
        st.info(f"Último archivo cargado: **{ultimo.iloc[0,0]}** ({ultimo.iloc[0,1]})")
    conn.close()

    archivo = st.file_uploader("Sube el CSV del día", type=["csv"])
    if archivo:
        if st.button("Enviar a Procesar"):
            # REEMPLAZA CON TU WEBHOOK URL DE n8n
            url_webhook = "https://agentes-n8n.xjkmv6.easypanel.host/webhook/tu-url-de-carga"
            files = {'file': (archivo.name, archivo.getvalue(), 'text/csv')}
            res = requests.post(url_webhook, files=files)
            if res.status_code == 200:
                st.success("✅ Archivo enviado con éxito.")
            else:
                st.error("❌ Error en el servidor de carga.")
