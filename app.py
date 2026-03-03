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

st.title("🍏 Panel de Control Verdu IA")

# --- MENÚ LATERAL ---
menu = st.sidebar.selectbox("Navegación", ["📈 Dashboard BI", "👥 Gestión de Vendedores", "💬 CRM Chatwoot", "📤 Carga de Stock", "📲 WhatsApp QR"])

# --- 1. DASHBOARD BI ---
if menu == "📈 Dashboard BI":
    st.header("📊 Analíticas del Día")
    conn = get_connection()
    
    # Verificar si hay datos hoy
    check_data = pd.read_sql("SELECT COUNT(*) FROM foto_stock_diario", conn).iloc[0,0]
    
    if check_data == 0:
        st.warning("⚠️ Todavía no se ha cargado el stock de hoy. Ve a 'Carga de Stock' para iniciar.")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        res = pd.read_sql("SELECT SUM(beneficio) as b FROM pedidos WHERE fecha::date = (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date", conn)
        val = res['b'].iloc[0] or 0
        st.metric("Beneficio Neto Hoy", f"${val:,.0f}")
    with col2:
        res = pd.read_sql("SELECT COUNT(*) as c FROM pedidos WHERE fecha::date = (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date", conn)
        st.metric("Pedidos Totales", res['c'].iloc[0])
    with col3:
        res = pd.read_sql("SELECT COUNT(*) as c FROM log_conversaciones WHERE fecha::date = (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date", conn)
        st.metric("Chats Atendidos", res['c'].iloc[0])

    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("💰 Ganancia por Vendedor")
        query = """
            SELECT v.nombre, SUM(p.beneficio) as ganancia
            FROM pedidos p
            JOIN vendedores v ON p.cliente_whatsapp = v.whatsapp
            WHERE p.fecha::date = (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date
            GROUP BY v.nombre
        """
        df_v = pd.read_sql(query, conn)
        if not df_v.empty:
            fig = px.pie(df_v, values='ganancia', names='nombre', hole=.4)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Esperando ventas de vendedores...")

    with c2:
        st.subheader("⚠️ Stock Crítico (Próximos a agotar)")
        # Ajustamos la query para que no traiga negativos y solo valores reales bajos
        query_stock = "SELECT nombre, stock FROM productos WHERE stock > 0 AND stock < 15 ORDER BY stock ASC LIMIT 8"
        df_s = pd.read_sql(query_stock, conn)
        if not df_s.empty:
            st.dataframe(df_s, use_container_width=True)
        else:
            st.success("El stock está en niveles óptimos.")
    conn.close()

# --- 2. GESTIÓN DE VENDEDORES (MEJORADA) ---
elif menu == "👥 Gestión de Vendedores":
    st.header("👥 Administración de Personal")
    conn = get_connection()
    cur = conn.cursor()

    col_izq, col_der = st.columns(2)

    with col_izq:
        st.subheader("➕ Registrar Nuevo")
        # Ayudamos al dueño mostrando los últimos que escribieron
        st.write("Selecciona un contacto reciente para hacerlo vendedor:")
        recientes = pd.read_sql("SELECT nombre, whatsapp FROM clientes ORDER BY fecha_registro DESC LIMIT 5", conn)
        for i, r in recientes.iterrows():
            if st.button(f"Asignar a: {r['nombre']} ({r['whatsapp']})"):
                cur.execute("INSERT INTO vendedores (whatsapp, nombre) VALUES (%s, %s) ON CONFLICT DO NOTHING", (r['whatsapp'], r['nombre']))
                conn.commit()
                st.success(f"{r['nombre']} ahora es vendedor.")
                st.rerun()

    with col_der:
        st.subheader("📋 Vendedores Activos")
        vendedores = pd.read_sql("SELECT * FROM vendedores", conn)
        for i, v in vendedores.iterrows():
            c1, c2 = st.columns([3,1])
            c1.write(f"**{v['nombre']}**")
            if c2.button("Eliminar", key=v['whatsapp']):
                cur.execute("DELETE FROM vendedores WHERE whatsapp = %s", (v['whatsapp'],))
                conn.commit()
                st.rerun()
    conn.close()

# --- 3. CRM CHATWOOT ---
elif menu == "💬 CRM Chatwoot":
    st.header("💬 Gestión de Clientes (Chatwoot)")
    st.info("Usa Chatwoot para ver las conversaciones detalladas y supervisar al Agente.")
    st.link_button("Ir al CRM Chatwoot", "https://agentes-chatwoot.xjkmv6.easypanel.host/")
    # Intentamos embeberlo
    st.components.v1.iframe("https://agentes-chatwoot.xjkmv6.easypanel.host/", height=700, scrolling=True)

# --- 4. CARGA DE STOCK ---
elif menu == "📤 Carga de Stock":
    st.header("📤 Actualizar Inventario")
    archivo = st.file_uploader("Sube el CSV del día", type=["csv"])
    if archivo:
        if st.button("Procesar Archivo"):
            # Enviar al webhook de n8n
            url_n8n = "TU_WEBHOOK_N8N_ACA" 
            requests.post(url_n8n, files={"file": archivo.getvalue()})
            st.success("Stock enviado correctamente.")

# --- 5. WHATSAPP QR ---
elif menu == "📲 WhatsApp QR":
    st.header("📲 Estado del Puente")
    st.components.v1.iframe("https://agentes-puentewhatsapp.xjkmv6.easypanel.host/", height=600)
