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
            pwd_hash = hashlib.sha256(password.encode()).hexdigest()
            if record[0] == pwd_hash:
                return True
    except Exception as e:
        st.error(f"Error de base de datos: {e}")
    return False

# --- 3. PANTALLA DE LOGIN ---
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

# --- 4. PANTALLA PRINCIPAL ---
else:
    # --- MENÚ LATERAL ---
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/2329/2329865.png", width=80)
        st.markdown(f"**Usuario:** {st.session_state['usuario_actual']}")
        st.divider()
        menu = st.radio("Navegación", ["📈 Dashboard Hoy", "📊 Analíticas Semanales", "👥 Gestión de Vendedores", "💬 CRM Chatwoot", "📱 Conectar WhatsApp", "📤 Carga de Stock", "⚙️ Configuración del Agente"])
        st.divider()
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state['autenticado'] = False
            st.rerun()

    st.title("🍏 Panel de Control - Ciuccoli Hnos")

    # ==========================================
    # PESTAÑA 1: DASHBOARD HOY
    # ==========================================
    if menu == "📈 Dashboard Hoy":
        st.header("📊 Resultados del Día")
        conn = get_connection()
        
        # --- CÁLCULO DE KPIS (Leyendo el nombre y cantidad del JSON) ---
        query_kpi = """
            SELECT 
                SUM(COALESCE((item->>'cantidad')::numeric * (item->>'precio')::numeric, 0)) as total_venta,
                SUM(COALESCE((item->>'cantidad')::numeric * ((item->>'precio')::numeric - f.precio_costo), 0)) as beneficio_neto,
                COUNT(DISTINCT c.id) as cantidad_pedidos
            FROM carga_sesiones c
            LEFT JOIN LATERAL jsonb_array_elements(c.anotados) as item ON true
            LEFT JOIN foto_stock_diario f ON f.nombre = item->>'nombre'
            WHERE c.fecha = (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date
            AND c.estado != 'cancelado'
            AND jsonb_typeof(c.anotados) = 'array'
        """
        res_kpi = pd.read_sql(query_kpi, conn)
        
        venta_total = res_kpi['total_venta'].iloc[0] or 0
        beneficio = res_kpi['beneficio_neto'].iloc[0] or 0
        pedidos_tot = res_kpi['cantidad_pedidos'].iloc[0] or 0

        # KPIs
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Venta Total Hoy", f"${venta_total:,.0f}")
        with col2:
            st.metric("Beneficio Neto Hoy", f"${beneficio:,.0f}")
        with col3:
            res_chats = pd.read_sql("SELECT COUNT(*) as c FROM log_conversaciones WHERE tipo_mensaje = 'incoming' AND fecha::date = (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date", conn)
            st.metric("Chats Atendidos", res_chats['c'].iloc[0])

        st.divider()

        c1, c2 = st.columns([1, 1.5])
        
        with c1:
            st.subheader("🎯 Ventas: Agente vs Vendedores")
            query_torta = """
                SELECT 
                    CASE WHEN v.nombre IS NULL THEN 'Agente (Venta Directa)' ELSE 'Vendedores Oficiales' END as tipo,
                    SUM(COALESCE((item->>'cantidad')::numeric * (item->>'precio')::numeric, 0)) as total
                FROM carga_sesiones c
                LEFT JOIN LATERAL jsonb_array_elements(c.anotados) as item ON true
                LEFT JOIN vendedores v ON c.whatsapp_id = v.whatsapp
                WHERE c.fecha = (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date
                AND c.estado != 'cancelado'
                AND jsonb_typeof(c.anotados) = 'array'
                GROUP BY tipo
            """
            df_t = pd.read_sql(query_torta, conn)
            if not df_t.empty and df_t['total'].sum() > 0:
                fig_t = px.pie(df_t, values='total', names='tipo', hole=.4, color_discrete_sequence=['#2e7d32', '#81c784'])
                st.plotly_chart(fig_t, use_container_width=True)
            else:
                st.info("Sin ventas registradas hoy.")

        with c2:
            st.subheader("📦 Pedidos del Día (En Vivo)")
            query_pedidos = """
                SELECT 
                    c.cliente_final_nombre AS "Cliente",
                    COALESCE(SUM((item->>'cantidad')::numeric * (item->>'precio')::numeric), 0) AS "Monto Estimado ($)",
                    c.estado AS "Estado"
                FROM carga_sesiones c
                LEFT JOIN LATERAL jsonb_array_elements(c.anotados) as item ON true
                WHERE c.fecha = (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date
                AND jsonb_typeof(c.anotados) = 'array'
                GROUP BY c.id, c.cliente_final_nombre, c.estado
                ORDER BY c.id DESC
            """
            df_pedidos = pd.read_sql(query_pedidos, conn)
            
            if not df_pedidos.empty:
                df_pedidos["Monto Estimado ($)"] = df_pedidos["Monto Estimado ($)"].apply(lambda x: f"${x:,.0f}")
                st.dataframe(df_pedidos, use_container_width=True, hide_index=True)
            else:
                st.success("Aún no hay pedidos registrados el día de hoy.")
        
        conn.close()

    # ==========================================
    # PESTAÑA 2: ANALÍTICAS SEMANALES
    # ==========================================
    elif menu == "📊 Analíticas Semanales":
        st.header("📅 Rendimiento de los últimos 7 días")
        conn = get_connection()
        
        # Generamos un calendario de 7 días y cruzamos los datos de ventas
        query_hist = """
            WITH dias AS (
                SELECT generate_series(
                    (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date - INTERVAL '6 days', 
                    (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date, 
                    '1 day'::interval
                )::date AS fecha_calendario
            )
            SELECT 
                d.fecha_calendario AS fecha, 
                COALESCE(SUM((item->>'cantidad')::numeric * ((item->>'precio')::numeric - COALESCE(f.precio_costo, 0))), 0) AS beneficio,
                COUNT(DISTINCT c.id) AS pedidos 
            FROM dias d
            LEFT JOIN carga_sesiones c 
                ON c.fecha = d.fecha_calendario 
                AND c.estado != 'cancelado' 
                AND jsonb_typeof(c.anotados) = 'array'
            LEFT JOIN LATERAL jsonb_array_elements(c.anotados) as item ON c.id IS NOT NULL
            LEFT JOIN foto_stock_diario f ON f.nombre = item->>'nombre'
            GROUP BY d.fecha_calendario 
            ORDER BY d.fecha_calendario ASC
        """
        df_hist = pd.read_sql(query_hist, conn)

        query_chats = """
            WITH dias AS (
                SELECT generate_series(
                    (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date - INTERVAL '6 days', 
                    (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date, 
                    '1 day'::interval
                )::date AS fecha_calendario
            )
            SELECT 
                d.fecha_calendario AS fecha, 
                COUNT(l.id) AS chats 
            FROM dias d
            LEFT JOIN log_conversaciones l 
                ON l.fecha::date = d.fecha_calendario 
                AND l.tipo_mensaje = 'incoming'
            GROUP BY d.fecha_calendario 
            ORDER BY d.fecha_calendario ASC
        """
        df_chats = pd.read_sql(query_chats, conn)
        conn.close()

        # Mostramos los gráficos
        col1, col2, col3 = st.columns(3)

        with col1:
            st.subheader("💰 Beneficio por Día")
            st.bar_chart(df_hist, x="fecha", y="beneficio", color="#2e7d32")

        with col2:
            st.subheader("📦 Pedidos Cerrados")
            st.bar_chart(df_hist, x="fecha", y="pedidos", color="#1976d2")

        with col3:
            st.subheader("💬 Chats Atendidos")
            st.bar_chart(df_chats, x="fecha", y="chats", color="#f57c00")

    # ==========================================
    # PESTAÑA 3: GESTIÓN DE VENDEDORES
    # ==========================================
    elif menu == "👥 Gestión de Vendedores":
        st.header("👥 Administración de Personal")
        conn = get_connection()
        cur = conn.cursor()

        col_izq, col_der = st.columns(2)

        with col_izq:
            st.subheader("➕ Registrar Nuevo")
            st.write("Selecciona un contacto reciente para hacerlo vendedor oficial:")
            recientes = pd.read_sql("SELECT DISTINCT nombre, whatsapp FROM clientes ORDER BY whatsapp DESC LIMIT 10", conn)
            for i, r in recientes.iterrows():
                if st.button(f"Asignar a: {r['nombre']} ({r['whatsapp']})", key=f"btn_{r['whatsapp']}"):
                    cur.execute("INSERT INTO vendedores (whatsapp, nombre) VALUES (%s, %s) ON CONFLICT DO NOTHING", (r['whatsapp'], r['nombre']))
                    conn.commit()
                    st.success(f"{r['nombre']} ahora es vendedor.")
                    st.rerun()

        with col_der:
            st.subheader("📋 Vendedores Activos")
            vendedores = pd.read_sql("SELECT * FROM vendedores", conn)
            for i, v in vendedores.iterrows():
                c1, c2 = st.columns([3, 1])
                c1.write(f"✅ **{v['nombre']}** | {v['whatsapp']}")
                if c2.button("Eliminar", key=f"del_{v['whatsapp']}"):
                    cur.execute("DELETE FROM vendedores WHERE whatsapp = %s", (v['whatsapp'],))
                    conn.commit()
                    st.rerun()
        conn.close()

    # ==========================================
    # PESTAÑA 4: CRM CHATWOOT
    # ==========================================
    elif menu == "💬 CRM Chatwoot":
        st.header("💬 Gestión de Clientes (Chatwoot)")
        st.link_button("🚀 Abrir Chatwoot en pestaña completa", "https://agentes-chatwoot.xjkmv6.easypanel.host/")
        #st.components.v1.iframe("https://agentes-chatwoot.xjkmv6.easypanel.host/", height=700, scrolling=True)

    # ==========================================
    # PESTAÑA 5: CONECTAR WHATSAPP
    # ==========================================
    elif menu == "📱 Conectar WhatsApp":
        st.header("📱 Conectar WhatsApp al Agente")
        st.info("Escaneá el código QR con tu WhatsApp para vincular tu número al agente. Una vez conectado, el agente comenzará a recibir y responder mensajes automáticamente.")
        st.components.v1.iframe("https://agentes-puentewhatsapp.xjkmv6.easypanel.host/", height=700, scrolling=True)
        st.caption("⚠️ Si el QR no carga, verificá que el servicio de puente WhatsApp esté activo en Easypanel.")

    
    # ==========================================
    # PESTAÑA 6: CARGA DE STOCK
    # ==========================================
    elif menu == "📤 Carga de Stock":
        st.header("📤 Actualizar Inventario")
        
        try:
            conn = get_connection()
            ultimo = pd.read_sql("SELECT nombre_archivo, fecha_proceso AT TIME ZONE 'UTC' AT TIME ZONE 'America/Argentina/Buenos_Aires' as fecha FROM control_cargas ORDER BY fecha_proceso DESC LIMIT 1", conn)
            if not ultimo.empty:
                st.info(f"Último archivo procesado: **{ultimo.iloc[0,0]}** (el {ultimo.iloc[0,1].strftime('%d/%m/%Y %H:%M')})")
            conn.close()
        except:
            st.warning("No se pudo cargar el historial de archivos.")

        archivo = st.file_uploader("Sube el CSV del día", type=["csv"])
        
        if archivo:
            if st.button("Procesar y Actualizar Stock"):
                url_n8n = "https://agentes-n8n.xjkmv6.easypanel.host/webhook/subir-stock-manual"
                files = {'file': (archivo.name, archivo.getvalue(), 'text/csv')}
                
                with st.spinner("Enviando archivo a n8n..."):
                    try:
                        res = requests.post(url_n8n, files=files, timeout=20)
                        
                        if res.status_code == 200:
                            st.success("✅ ¡Éxito! El stock ha sido actualizado.")
                        elif res.status_code == 400:
                            try:
                                msg = res.json().get("mensaje", "Archivo duplicado.")
                            except:
                                msg = "Archivo rechazado (Duplicado o error de formato)."
                            st.warning(f"⚠️ {msg}")
                        else:
                            st.error(f"❌ Error del servidor (Código {res.status_code})")
                    except requests.exceptions.Timeout:
                        st.warning("⏳ El servidor tardó en responder. Verifica el log en unos minutos.")
                    except Exception as e:
                        st.error(f"❌ Fallo de conexión: {e}")

    # ==========================================
    # PESTAÑA 7: CONFIGURACIÓN DEL AGENTE
    # ==========================================
    elif menu == "⚙️ Configuración del Agente":
        st.header("⚙️ Configuración General de la IA")
        st.write("Controla las reglas de negocio y el comportamiento del asistente virtual.")
        
        conn = get_connection()
        cur = conn.cursor()
        
        # 1. Obtenemos el estado actual desde la base de datos
        cur.execute("SELECT valor FROM configuracion WHERE clave = 'verificacion_clientes'")
        resultado = cur.fetchone()
        
        # Si la clave existe y es 'true', el switch estará activado. Si no, apagado.
        estado_actual = True if resultado and resultado[0] == 'true' else False

        # 2. Interfaz Visual (Tarjeta de configuración)
        with st.container():
            st.markdown("""
            <div style="background-color: white; padding: 20px; border-radius: 8px; border: 1px solid #ddd; margin-bottom: 20px;">
                <h4 style="margin-top: 0; color: #1f2937;">Seguridad y Acceso</h4>
            </div>
            """, unsafe_allow_html=True)
            
            # El Switch visual (Toggle)
            nuevo_estado = st.toggle("🔒 Exigir Verificación de Clientes", value=estado_actual, help="Si se activa, el Agente solo atenderá a clientes que ya estén registrados en el sistema.")
            
            # Botón para guardar
            if st.button("💾 Guardar Configuración", type="primary"):
                valor_sql = 'true' if nuevo_estado else 'false'
                
                # Intentamos actualizar. Si no actualiza ninguna fila (porque la clave no existía), la insertamos.
                cur.execute("UPDATE configuracion SET valor = %s WHERE clave = 'verificacion_clientes'", (valor_sql,))
                if cur.rowcount == 0:
                    cur.execute("INSERT INTO configuracion (clave, valor) VALUES ('verificacion_clientes', %s)", (valor_sql,))
                
                conn.commit()
                st.success("✅ Configuración guardada correctamente. El Agente aplicará esta regla de inmediato.")
                st.rerun()

        # 3. Sección "Próximamente" (Para mostrarle al dueño lo que se viene)
        st.divider()
        st.subheader("🔜 Próximas Funcionalidades")
        st.info("""
        En futuras actualizaciones podrás configurar aquí:
        * 🕒 **Horarios de Atención:** (Apertura y cierre de toma de pedidos).
        * 🏢 **Información de la Empresa:** (Dirección, CBU para pagos, avisos de feriados).
        * 🚚 **Días de Logística:** (Avisos automáticos de ingreso de mercadería).
        """)
        
        conn.close()
