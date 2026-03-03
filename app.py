import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
import os
import requests

st.set_page_config(page_title="Verdu IA - Sistema de Gestión", layout="wide", page_icon="🍎")

# Conexión a Base de Datos
def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "agentes_db_postgres"),
        database=os.getenv("DB_NAME", "db_agente"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASS"),
        port=os.getenv("DB_PORT", "5432")
    )

st.title("🍏 Panel de Control Verdu IA")

menu = st.sidebar.selectbox("Navegación", ["📈 Dashboard Hoy", "📊 Analíticas Semanales", "👥 Gestión de Vendedores", "💬 CRM Chatwoot", "📤 Carga de Stock"])

# --- 1. DASHBOARD HOY (KPIs y Distribución) ---
if menu == "📈 Dashboard Hoy":
    st.header("📊 Analíticas del Día")
    conn = get_connection()
    
    # KPIs DIARIOS (Recuperados)
    col1, col2, col3 = st.columns(3)
    with col1:
        res = pd.read_sql("SELECT SUM(beneficio) as b FROM pedidos WHERE fecha::date = (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date", conn)
        st.metric("Beneficio Neto Hoy", f"${(res['b'].iloc[0] or 0):,.0f}")
    with col2:
        res = pd.read_sql("SELECT COUNT(*) as c FROM pedidos WHERE fecha::date = (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date", conn)
        st.metric("Pedidos Totales", res['c'].iloc[0])
    with col3:
        res = pd.read_sql("SELECT COUNT(*) as c FROM log_conversaciones WHERE fecha::date = (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date", conn)
        st.metric("Chats Atendidos", res['c'].iloc[0])

    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🎯 Distribución de Ventas (Agente vs Vendedores)")
        query_torta = """
            SELECT 
                CASE WHEN v.nombre IS NULL THEN 'Agente (Venta Directa)' ELSE 'Vendedores' END as tipo_venta,
                SUM(p.total_venta) as total
            FROM pedidos p
            LEFT JOIN vendedores v ON p.cliente_whatsapp = v.whatsapp
            WHERE p.fecha::date = (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date
            GROUP BY tipo_venta
        """
        df_t = pd.read_sql(query_torta, conn)
        if not df_t.empty:
            fig_t = px.pie(df_t, values='total', names='tipo_venta', hole=.4, color_discrete_sequence=['#2e7d32', '#81c784'])
            st.plotly_chart(fig_t, use_container_width=True)
        else:
            st.info("Sin ventas registradas hoy.")

    with c2:
        st.subheader("⚠️ Stock Crítico (Prorrateo)")
        df_s = pd.read_sql("SELECT nombre, stock FROM productos WHERE stock >= 0 AND stock < 15 ORDER BY stock ASC LIMIT 10", conn)
        st.dataframe(df_s, use_container_width=True)
    conn.close()

# --- 2. ANALÍTICAS SEMANALES (Graficos de Barra) ---
elif menu == "📊 Analíticas Semanales":
    st.header("📅 Rendimiento Semanal")
    conn = get_connection()
    
    query_semana = """
        SELECT fecha, SUM(beneficio) as beneficio, COUNT(id) as pedidos
        FROM pedidos 
        WHERE fecha > CURRENT_DATE - INTERVAL '7 days'
        GROUP BY fecha ORDER BY fecha ASC
    """
    df_semana = pd.read_sql(query_semana, conn)

    tab1, tab2, tab3 = st.tabs(["Beneficio por día", "Pedidos por día", "Actividad Chats"])
    with tab1:
        st.bar_chart(df_semana, x="fecha", y="beneficio", color="#2e7d32")
    with tab2:
        st.bar_chart(df_semana, x="fecha", y="pedidos", color="#81c784")
    with tab3:
        df_chats = pd.read_sql("SELECT fecha::date as f, COUNT(*) as c FROM log_conversaciones GROUP BY f ORDER BY f ASC LIMIT 7", conn)
        st.bar_chart(df_chats, x="f", y="c")
    conn.close()

# --- 3. GESTIÓN DE VENDEDORES (CRUD Corregido) ---
elif menu == "👥 Gestión de Vendedores":
    st.header("👥 Administrar Vendedores")
    conn = get_connection()
    cur = conn.cursor()
    
    st.subheader("Asignación Rápida")
    st.write("Selecciona un contacto reciente para hacerlo vendedor oficial:")
    recientes = pd.read_sql("SELECT DISTINCT nombre, whatsapp FROM clientes ORDER BY whatsapp DESC LIMIT 10", conn)
    
    for i, r in recientes.iterrows():
        if st.button(f"Asignar: {r['nombre']} ({r['whatsapp']})", key=f"btn_{r['whatsapp']}"):
            cur.execute("INSERT INTO vendedores (whatsapp, nombre) VALUES (%s, %s) ON CONFLICT (whatsapp) DO UPDATE SET nombre = EXCLUDED.nombre", (r['whatsapp'], r['nombre']))
            conn.commit()
            st.success(f"{r['nombre']} ahora es vendedor.")
            st.rerun()

    st.divider()
    st.subheader("Lista de Vendedores Oficiales")
    vendedores = pd.read_sql("SELECT * FROM vendedores", conn)
    for i, v in vendedores.iterrows():
        c1, c2 = st.columns([4, 1])
        c1.write(f"✅ **{v['nombre']}** | ID: {v['whatsapp']}")
        # Botón de baja corregido
        if c2.button("Eliminar", key=f"del_{v['whatsapp']}"):
            cur.execute("DELETE FROM vendedores WHERE whatsapp = %s", (v['whatsapp'],))
            conn.commit()
            st.rerun()
    conn.close()

# --- 4. CRM CHATWOOT ---
elif menu == "💬 CRM Chatwoot":
    st.header("💬 Acceso al CRM")
    st.link_button("🚀 Abrir Chatwoot", "https://agentes-chatwoot.xjkmv6.easypanel.host/")
    st.components.v1.iframe("https://agentes-chatwoot.xjkmv6.easypanel.host/", height=800)

# --- 5. CARGA DE STOCK ---
elif menu == "📤 Carga de Stock":
    st.header("📤 Cargar Stock Manual")
    conn = get_connection()
    ultimo = pd.read_sql("SELECT nombre_archivo, fecha_proceso FROM control_cargas ORDER BY fecha_proceso DESC LIMIT 1", conn)
    if not ultimo.empty:
        st.success(f"Último archivo procesado: **{ultimo.iloc[0,0]}**")
    
    archivo = st.file_uploader("Subir CSV", type=["csv"])
    if archivo:
        if st.button("Enviar a n8n"):
            url_n8n = "https://agentes-n8n.xjkmv6.easypanel.host/webhook/subir-stock-manual"
            # IMPORTANTE: Enviamos el archivo bajo la propiedad 'file'
            files = {'file': (archivo.name, archivo.getvalue(), 'text/csv')}
            try:
                r = requests.post(url_n8n, files=files)
                if r.status_code == 200:
                    st.success("✅ Recibido por n8n. El stock se actualizará en segundos.")
                else:
                    st.error(f"❌ Error {r.status_code}: {r.text}")
            except Exception as e:
                st.error(f"❌ Fallo de conexión: {e}")
