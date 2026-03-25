import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
import os
import requests
import hashlib

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Ciuccoli Hnos - Sistema Mayorista", layout="wide", page_icon="🍏")

# Ocultar menú de Streamlit por defecto
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .main { background-color: #f8f9fa; }
    </style>
""", unsafe_allow_html=True)

# Inicializar estado de sesión
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False

# --- 2. FUNCIONES DE BASE DE DATOS ---
def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "agentes_db_postgres"),
        database=os.getenv("DB_NAME", "db_agente"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASS"),
        port=os.getenv("DB_PORT", "5432")
    )

def check_login(username, password):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT password_hash FROM usuarios_ui WHERE usuario = %s", (username,))
        record = cur.fetchone()
        conn.close()
        
        if record:
            # Encripta la clave ingresada y la compara con la de la BD
            pwd_hash = hashlib.sha256(password.encode()).hexdigest()
            if record[0] == pwd_hash:
                return True
    except Exception as e:
        st.error(f"Error de base de datos: {e}")
    return False


# --- 3. PANTALLA DE LOGIN (Bloqueo Total) ---
if not st.session_state['autenticado']:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center; color: #2e7d32;'>🍏 Ciuccoli Hnos - Acceso Restringido</h1>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown("<div style='background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>", unsafe_allow_html=True)
        with st.form("login_form"):
            user = st.text_input("Usuario")
            pwd = st.text_input("Contraseña", type="password")
            submit = st.form_submit_button("Ingresar al Sistema", use_container_width=True)
            
            if submit:
                if check_login(user, pwd):
                    st.session_state['autenticado'] = True
                    st.session_state['usuario_actual'] = user
                    st.rerun()
                else:
                    st.error("❌ Usuario o contraseña incorrectos.")
        st.markdown("</div>", unsafe_allow_html=True)

# --- 4. PANTALLA PRINCIPAL (Solo si está autenticado) ---
else:
    # --- MENÚ LATERAL ---
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/2329/2329865.png", width=80)
        st.markdown(f"**Usuario:** {st.session_state['usuario_actual']}")
        st.divider()
        menu = st.radio("Navegación", ["📈 Dashboard Hoy", "📊 Analíticas Semanales", "👥 Gestión de Vendedores", "💬 CRM Chatwoot", "📤 Carga de Stock", "📲 WhatsApp QR"])
        st.divider()
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state['autenticado'] = False
            st.rerun()

    st.title("🍏 Panel de Control - Ciuccoli Hnos")

    # --- DASHBOARD HOY ---
    if menu == "📈 Dashboard Hoy":
        st.header("📊 Resultados del Día")
        conn = get_connection()
        
        # KPIs
        col1, col2, col3 = st.columns(3)
        with col1:
            res = pd.read_sql("SELECT SUM(total_venta) as b FROM pedidos WHERE fecha::date = (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date", conn)
            val = res['b'].iloc[0] or 0
            st.metric("Venta Total Hoy", f"${val:,.0f}")
        with col2:
            res = pd.read_sql("SELECT COUNT(*) as c FROM pedidos WHERE fecha::date = (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date", conn)
            st.metric("Pedidos Totales", res['c'].iloc[0])
        with col3:
            res = pd.read_sql("SELECT COUNT(*) as c FROM log_conversaciones WHERE fecha::date = (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date", conn)
            st.metric("Chats Atendidos", res['c'].iloc[0])

        st.divider()

        c1, c2 = st.columns([1, 1.5]) # Ajustamos el ancho para que la tabla de pedidos se vea mejor
        
        with c1:
            st.subheader("🎯 Ventas: Agente vs Vendedores")
            query_torta = """
                SELECT 
                    CASE WHEN v.nombre IS NULL THEN 'Agente (Venta Directa)' ELSE 'Vendedores Oficiales' END as tipo,
                    SUM(p.total_venta) as total
                FROM pedidos p
                LEFT JOIN vendedores v ON p.cliente_whatsapp = v.whatsapp
                WHERE p.fecha::date = (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date
                GROUP BY tipo
            """
            df_t = pd.read_sql(query_torta, conn)
            if not df_t.empty and df_t['total'].sum() > 0:
                fig_t = px.pie(df_t, values='total', names='tipo', hole=.4, color_discrete_sequence=['#2e7d32', '#81c784'])
                st.plotly_chart(fig_t, use_container_width=True)
            else:
                st.info("Sin ventas registradas hoy.")

        # --- NUEVO: TABLA DE PEDIDOS DEL DÍA ---
        with c2:
            st.subheader("📦 Pedidos del Día (En Vivo)")
            query_pedidos = """
                SELECT 
                    cliente_final_nombre AS "Cliente",
                    total_venta AS "Monto ($)",
                    estado AS "Estado"
                FROM pedidos
                WHERE fecha::date = (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date
                ORDER BY id DESC
            """
            df_pedidos = pd.read_sql(query_pedidos, conn)
            
            if not df_pedidos.empty:
                # Formateamos la columna de Monto para que se vea como moneda
                df_pedidos["Monto ($)"] = df_pedidos["Monto ($)"].apply(lambda x: f"${x:,.0f}")
                st.dataframe(df_pedidos, use_container_width=True, hide_index=True)
            else:
                st.success("Aún no hay pedidos registrados el día de hoy.")
        
        conn.close()

    # --- (AQUÍ CONTINÚA EL CÓDIGO DEL RESTO DE LOS MENÚS: Analíticas, Vendedores, etc.) ---
    # Asegúrate de mantener la indentación (todos deben estar dentro del bloque 'else:' principal)
