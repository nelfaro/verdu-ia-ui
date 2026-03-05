import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
import os
import requests

st.set_page_config(page_title="Verdu IA - Sistema Mayorista", layout="wide", page_icon="🍎")

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "agentes_db_postgres"),
        database=os.getenv("DB_NAME", "db_agente"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASS"),
        port=os.getenv("DB_PORT", "5432")
    )

st.title("🍏 Panel de Control Inteligente - Verdu IA")

menu = st.sidebar.selectbox("Navegación", ["📈 Dashboard Hoy", "📊 Analíticas Semanales", "👥 Gestión de Vendedores", "💬 CRM Chatwoot", "📤 Carga de Stock"])

# --- 1. DASHBOARD HOY ---
if menu == "📈 Dashboard Hoy":
    st.header("📊 Resultados del Día")
    conn = get_connection()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        res = pd.read_sql("SELECT SUM(beneficio) as b FROM pedidos WHERE fecha = CURRENT_DATE", conn)
        st.metric("Beneficio Neto Hoy", f"${(res['b'].iloc[0] or 0):,.0f}")
    with col2:
        res = pd.read_sql("SELECT COUNT(*) as c FROM pedidos WHERE fecha = CURRENT_DATE", conn)
        st.metric("Pedidos Totales", res['c'].iloc[0])
    with col3:
        res = pd.read_sql("SELECT COUNT(*) as c FROM log_conversaciones WHERE fecha::date = CURRENT_DATE", conn)
        st.metric("Chats Atendidos", res['c'].iloc[0])

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🎯 Ventas: Agente vs Vendedores")
        query_torta = """
            SELECT 
                CASE WHEN v.nombre IS NULL THEN 'Agente (Venta Directa)' ELSE 'Vendedores Oficiales' END as tipo,
                SUM(p.total_venta) as total
            FROM pedidos p
            LEFT JOIN vendedores v ON p.cliente_whatsapp = v.whatsapp
            WHERE p.fecha = CURRENT_DATE
            GROUP BY tipo
        """
        df_t = pd.read_sql(query_torta, conn)
        if not df_t.empty:
            fig_t = px.pie(df_t, values='total', names='tipo', hole=.4, color_discrete_sequence=['#2e7d32', '#81c784'])
            st.plotly_chart(fig_t, use_container_width=True)
        else:
            st.info("Sin ventas registradas hoy.")

    with c2:
        st.subheader("⚠️ Stock Crítico")
        df_s = pd.read_sql("SELECT nombre, stock FROM productos WHERE stock >= 0 AND stock < 15 ORDER BY stock ASC LIMIT 8", conn)
        st.dataframe(df_s, use_container_width=True)
    conn.close()

# --- 2. ANALÍTICAS SEMANALES (GRÁFICOS DE BARRA) ---
elif menu == "📊 Analíticas Semanales":
    st.header("📅 Rendimiento de los últimos 7 días")
    
    try:
        conn = get_connection()
        
        # Query para Beneficios y Pedidos
        query_pedidos = """
            SELECT fecha, SUM(beneficio) as beneficio, COUNT(id) as pedidos 
            FROM pedidos 
            WHERE fecha >= CURRENT_DATE - INTERVAL '7 days' 
            GROUP BY fecha 
            ORDER BY fecha ASC
        """
        df_pedidos = pd.read_sql(query_pedidos, conn)

        # Query para Chats Atendidos
        query_chats = """
            SELECT fecha::date as fecha, COUNT(*) as chats 
            FROM log_conversaciones 
            WHERE tipo_mensaje = 'incoming' 
            AND fecha >= CURRENT_DATE - INTERVAL '7 days' 
            GROUP BY fecha::date 
            ORDER BY fecha::date ASC
        """
        df_chats = pd.read_sql(query_chats, conn)
        
        conn.close()

        # Mostrar gráficos en 3 columnas para una vista ejecutiva
        col1, col2, col3 = st.columns(3)

        with col1:
            st.subheader("💰 Beneficio por Día")
            if not df_pedidos.empty:
                st.bar_chart(df_pedidos, x="fecha", y="beneficio", color="#2e7d32")
            else:
                st.info("Sin datos de beneficio.")

        with col2:
            st.subheader("📦 Pedidos Cerrados")
            if not df_pedidos.empty:
                st.bar_chart(df_pedidos, x="fecha", y="pedidos", color="#1976d2")
            else:
                st.info("Sin datos de pedidos.")

        with col3:
            st.subheader("💬 Chats Atendidos")
            if not df_chats.empty:
                # Usamos color naranja para diferenciar los chats
                st.bar_chart(df_chats, x="fecha", y="chats", color="#f57c00") 
            else:
                st.info("Sin actividad de chats.")

    except Exception as e:
        st.error(f"Error al cargar las analíticas semanales: {e}")

# --- 3. GESTIÓN DE VENDEDORES (CRUD) ---
elif menu == "👥 Gestión de Vendedores":
    st.header("👥 Administrar Vendedores")
    conn = get_connection()
    cur = conn.cursor()
    
    st.subheader("Personas que escribieron (Sugeridos para Vendedor)")
    recientes = pd.read_sql("SELECT DISTINCT nombre, whatsapp FROM clientes ORDER BY whatsapp DESC LIMIT 10", conn)
    for i, r in recientes.iterrows():
        if st.button(f"Hacer Vendedor a: {r['nombre']} ({r['whatsapp']})", key=f"btn_{r['whatsapp']}"):
            cur.execute("INSERT INTO vendedores (whatsapp, nombre) VALUES (%s, %s) ON CONFLICT (whatsapp) DO UPDATE SET nombre = EXCLUDED.nombre", (r['whatsapp'], r['nombre']))
            conn.commit()
            st.rerun()

    st.divider()
    st.subheader("Vendedores Actuales")
    vendedores = pd.read_sql("SELECT * FROM vendedores", conn)
    for i, v in vendedores.iterrows():
        c1, c2 = st.columns([4, 1])
        c1.write(f"👤 **{v['nombre']}** | ID: {v['whatsapp']}")
        if c2.button("Dar de Baja", key=f"del_{v['whatsapp']}"):
            cur.execute("DELETE FROM vendedores WHERE whatsapp = %s", (v['whatsapp'],))
            conn.commit()
            st.rerun()
    conn.close()

# --- 4. CRM CHATWOOT ---
elif menu == "💬 CRM Chatwoot":
    st.header("💬 CRM Chatwoot")
    st.link_button("🚀 Abrir Chatwoot Pantalla Completa", "https://agentes-chatwoot.xjkmv6.easypanel.host/")
    st.components.v1.iframe("https://agentes-chatwoot.xjkmv6.easypanel.host/", height=700, scrolling=True)


# --- 5. CARGA DE STOCK ---
elif menu == "📤 Carga de Stock":
    st.header("📤 Actualizar Inventario")
    
    # 1. Mostrar último archivo cargado
    try:
        conn = get_connection()
        ultimo = pd.read_sql("SELECT nombre_archivo, fecha_proceso AT TIME ZONE 'UTC' AT TIME ZONE 'America/Argentina/Buenos_Aires' as fecha FROM control_cargas ORDER BY fecha_proceso DESC LIMIT 1", conn)
        if not ultimo.empty:
            st.info(f"Último archivo procesado: **{ultimo.iloc[0,0]}** (el {ultimo.iloc[0,1].strftime('%d/%m/%Y %H:%M')})")
        conn.close()
    except Exception as e:
        st.warning("No se pudo conectar a la base de datos para ver el historial.")

    # 2. Formulario de carga
    archivo = st.file_uploader("Sube el CSV del día", type=["csv"])
    
    if archivo:
        if st.button("Procesar y Actualizar Stock"):
            url_n8n = "https://agentes-n8n.xjkmv6.easypanel.host/webhook/subir-stock-manual"
            files = {'file': (archivo.name, archivo.getvalue(), 'text/csv')}
            
            with st.spinner("Enviando archivo a n8n..."):
                try:
                    res = requests.post(url_n8n, files=files, timeout=20)
                    
                    # Verificamos si n8n respondió con éxito (200)
                    if res.status_code == 200:
                        st.success("✅ ¡Éxito! El stock ha sido actualizado.")
                    
                    # Verificamos si n8n lo rechazó por duplicado (400)
                    elif res.status_code == 400:
                        # Intentamos sacar el mensaje exacto que configuraste en n8n
                        try:
                            msg = res.json().get("mensaje", "Archivo duplicado.")
                        except:
                            msg = "Archivo rechazado por reglas de negocio."
                        st.warning(f"⚠️ {msg}")
                    
                    # Cualquier otro error HTTP (500, 404)
                    else:
                        st.error(f"❌ Error del servidor de n8n (Código {res.status_code})")

                # Solo entra aquí si el servidor no responde en 20 segundos
                except requests.exceptions.Timeout:
                    st.warning("⏳ El servidor tardó en responder. Verifica el log en 2 minutos.")
                
                # Solo entra aquí si la URL no existe o no hay internet
                except requests.exceptions.RequestException as e:
                    st.error("❌ No se pudo conectar con n8n. Revisa que el Webhook esté activo.")

