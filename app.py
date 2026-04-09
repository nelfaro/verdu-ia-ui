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
        menu = st.radio("Navegación", ["📈 Dashboard Hoy", "📊 Analíticas Semanales", "👥 Gestión de Vendedores", "💬 CRM Chatwoot", "📱 Conectar WhatsApp", "📤 Carga de Stock", "📖 Diccionario de Sinónimos", "⚙️ Configuración del Agente"])
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
        
        # Selector de fecha
        from datetime import date, timedelta
        fecha_hoy = date.today()
        fecha_sel = st.date_input("📅 Seleccionar fecha", value=fecha_hoy, max_value=fecha_hoy)
        es_hoy = fecha_sel == fecha_hoy
        
        fecha_str = fecha_sel.strftime('%Y-%m-%d')
        
        if es_hoy:
            # Datos en vivo de carga_sesiones
            query_kpi = f"""
                SELECT 
                    SUM(COALESCE((item->>'cantidad')::numeric * (item->>'precio')::numeric, 0)) as total_venta,
                    SUM(COALESCE((item->>'cantidad')::numeric * ((item->>'precio')::numeric - COALESCE(f.precio_costo, 0)), 0)) as beneficio_neto,
                    COUNT(DISTINCT c.id) as cantidad_pedidos
                FROM carga_sesiones c
                LEFT JOIN LATERAL jsonb_array_elements(c.anotados) as item ON true
                LEFT JOIN foto_stock_diario f ON f.nombre = item->>'nombre'
                WHERE c.fecha = '{fecha_str}'
                AND c.estado NOT IN ('cancelado')
                AND jsonb_typeof(c.anotados) = 'array'
                AND jsonb_array_length(c.anotados) > 0
            """
        else:
            # Datos historicos de pedidos
            query_kpi = f"""
                SELECT 
                    COALESCE(SUM(total_venta), 0) as total_venta,
                    COALESCE(SUM(beneficio), 0) as beneficio_neto,
                    COUNT(*) as cantidad_pedidos
                FROM pedidos
                WHERE fecha = '{fecha_str}'
                AND estado = 'cerrado'
                AND total_venta > 0
            """
        
        res_kpi = pd.read_sql(query_kpi, conn)
        
        venta_total = res_kpi['total_venta'].iloc[0] or 0
        beneficio = res_kpi['beneficio_neto'].iloc[0] or 0
        pedidos_tot = res_kpi['cantidad_pedidos'].iloc[0] or 0
 
        # KPIs
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Venta Total", f"${venta_total:,.0f}")
        with col2:
            st.metric("Beneficio Neto", f"${beneficio:,.0f}")
        with col3:
            st.metric("Pedidos", int(pedidos_tot))
        with col4:
            res_chats = pd.read_sql(f"SELECT COUNT(*) as c FROM log_conversaciones WHERE tipo_mensaje = 'incoming' AND fecha::date = '{fecha_str}'", conn)
            st.metric("Chats Atendidos", res_chats['c'].iloc[0])
 
        st.divider()
 
        c1, c2 = st.columns([1, 1.5])
        
        with c1:
            st.subheader("🎯 Ventas: Agente vs Vendedores")
            if es_hoy:
                query_torta = f"""
                    SELECT 
                        CASE WHEN v.nombre IS NULL THEN 'Agente (Venta Directa)' ELSE 'Vendedores Oficiales' END as tipo,
                        SUM(COALESCE((item->>'cantidad')::numeric * (item->>'precio')::numeric, 0)) as total
                    FROM carga_sesiones c
                    LEFT JOIN LATERAL jsonb_array_elements(c.anotados) as item ON true
                    LEFT JOIN vendedores v ON c.whatsapp_id = v.whatsapp
                    WHERE c.fecha = '{fecha_str}'
                    AND c.estado NOT IN ('cancelado')
                    AND jsonb_typeof(c.anotados) = 'array'
                    AND jsonb_array_length(c.anotados) > 0
                    GROUP BY tipo
                """
            else:
                query_torta = f"""
                    SELECT 
                        CASE WHEN v.nombre IS NULL THEN 'Agente (Venta Directa)' ELSE 'Vendedores Oficiales' END as tipo,
                        SUM(total_venta) as total
                    FROM pedidos p
                    LEFT JOIN vendedores v ON p.cliente_whatsapp = v.whatsapp
                    WHERE p.fecha = '{fecha_str}'
                    AND p.estado = 'cerrado'
                    AND p.total_venta > 0
                    GROUP BY tipo
                """
            df_t = pd.read_sql(query_torta, conn)
            if not df_t.empty and df_t['total'].sum() > 0:
                fig_t = px.pie(df_t, values='total', names='tipo', hole=.4, color_discrete_sequence=['#2e7d32', '#81c784'])
                st.plotly_chart(fig_t, use_container_width=True)
            else:
                st.info("Sin ventas registradas para esta fecha.")
 
        with c2:
            titulo_pedidos = "📦 Pedidos del Día (En Vivo)" if es_hoy else f"📦 Pedidos del {fecha_sel.strftime('%d/%m/%Y')}"
            st.subheader(titulo_pedidos)
            if es_hoy:
                query_pedidos = f"""
                    SELECT 
                        c.cliente_final_nombre AS "Cliente",
                        COALESCE(SUM((item->>'cantidad')::numeric * (item->>'precio')::numeric), 0) AS "Monto Estimado ($)",
                        c.estado AS "Estado"
                    FROM carga_sesiones c
                    LEFT JOIN LATERAL jsonb_array_elements(c.anotados) as item ON true
                    WHERE c.fecha = '{fecha_str}'
                    AND jsonb_typeof(c.anotados) = 'array'
                    AND jsonb_array_length(c.anotados) > 0
                    AND c.estado != 'cancelado'
                    GROUP BY c.id, c.cliente_final_nombre, c.estado
                    HAVING COALESCE(SUM((item->>'cantidad')::numeric * (item->>'precio')::numeric), 0) > 0
                    ORDER BY c.id DESC
                """
            else:
                query_pedidos = f"""
                    SELECT 
                        cliente_final_nombre AS "Cliente",
                        total_venta AS "Monto Estimado ($)",
                        estado AS "Estado"
                    FROM pedidos
                    WHERE fecha = '{fecha_str}'
                    AND estado = 'cerrado'
                    AND total_venta > 0
                    ORDER BY id DESC
                """
            df_pedidos = pd.read_sql(query_pedidos, conn)
            
            if not df_pedidos.empty:
                df_pedidos["Monto Estimado ($)"] = df_pedidos["Monto Estimado ($)"].apply(lambda x: f"${x:,.0f}")
                st.dataframe(df_pedidos, use_container_width=True, hide_index=True)
            else:
                st.info("No hay pedidos registrados para esta fecha.")
        
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
                COALESCE(SUM(p.beneficio), 0) AS beneficio,
                COUNT(DISTINCT p.id) AS pedidos 
            FROM dias d
            LEFT JOIN pedidos p 
                ON p.fecha = d.fecha_calendario 
                AND p.estado = 'cerrado'
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
    # PESTAÑA 6: DICCIONARIO DE SINÓNIMOS
    # ==========================================
    elif menu == "📖 Diccionario de Sinónimos":
        st.header("📖 Diccionario de la Inteligencia Artificial")
        st.write("Enseña al Agente a entender cómo llaman los clientes a tus productos.")
        
        conn = get_connection()
        cur = conn.cursor()
        col_izq, col_der = st.columns([1, 2])
        with col_izq:
            st.subheader("➕ Nuevo Sinónimo")
            with st.form("form_sinonimo"):
                st.write("Ej: Cliente dice 'Zapallito' -> Sistema lee 'ZAP'")
                st.write("Podés agregar varios sinónimos para la misma palabra.")
                term_orig = st.text_input("Palabra del cliente (termino)").lower().strip()
                sinonimo = st.text_input("Nombre en el sistema (sinonimo)").upper().strip()
                
                submit_sin = st.form_submit_button("💾 Guardar Sinónimo", use_container_width=True)
                
                if submit_sin:
                    if term_orig and sinonimo:
                        try:
                            cur.execute(
                                "SELECT id FROM sinonimos_productos WHERE termino = %s AND sinonimo = %s", 
                                (term_orig, sinonimo)
                            )
                            if cur.fetchone():
                                st.warning("Esa combinación ya existe.")
                            else:
                                cur.execute(
                                    "INSERT INTO sinonimos_productos (termino, sinonimo) VALUES (%s, %s)", 
                                    (term_orig, sinonimo)
                                )
                                conn.commit()
                                st.success(f"✅ Agregado: {term_orig} -> {sinonimo}")
                                st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al guardar: {e}")
                            conn.rollback()
                    else:
                        st.warning("Completa ambos campos.")
        with col_der:
              st.subheader("📋 Sinónimos Registrados")
              try:
                  df_sinonimos = pd.read_sql(
                      "SELECT * FROM sinonimos_productos ORDER BY termino ASC, sinonimo ASC", 
                      conn
                  )
                  
                  if not df_sinonimos.empty:
                      for i, row in df_sinonimos.iterrows():
                          c1, c2, c3 = st.columns([2, 2, 1])
                          c1.write(f"🗣️ **Dice:** {row['termino']}")
                          c2.write(f"💾 **Busca:** {row['sinonimo']}")
                          if c3.button("🗑️ Borrar", key=f"del_sin_{row['id']}"):
                              cur.execute("DELETE FROM sinonimos_productos WHERE id = %s", (row['id'],))
                              conn.commit()
                              st.rerun()
                  else:
                      st.info("No hay sinónimos registrados aún.")
              except Exception as e:
                  st.error(f"Error al cargar la tabla: {e}")         
        conn.close()
    # ==========================================
    # PESTAÑA 7: CONFIGURACIÓN DEL AGENTE Y NEGOCIO
    # ==========================================
    elif menu == "⚙️ Configuración del Agente":
        st.header("⚙️ Configuración del Sistema y Negocio")
        st.write("Controla las reglas de la IA, los horarios operativos y la información que ven los clientes.")
        
        conn = get_connection()
        cur = conn.cursor()
        
        # 1. Leer estado actual
        cur.execute("SELECT clave, valor FROM configuracion")
        config_db = {row[0]: row[1] for row in cur.fetchall()}
        
        cur.execute("SELECT mensaje_comercial FROM info_negocio ORDER BY id DESC LIMIT 1")
        info_db = cur.fetchone()
        mensaje_actual = info_db[0] if info_db else "Horario normal de 07:00 a 13:00 hs."

        # --- FORMULARIO MAESTRO ---
        with st.form("config_form"):
            
            # SECCIÓN A: SEGURIDAD
            st.subheader("🔒 Seguridad y Acceso")
            estado_verif = True if config_db.get('verificacion_clientes') == 'true' else False
            nuevo_estado_verif = st.checkbox("Exigir Verificación de Clientes (Solo usuarios registrados)", value=estado_verif)
            st.divider()

            # SECCIÓN B: HORARIOS
            st.subheader("🕒 Horarios de Cierre (Prorrateo)")
            hora_actual_str = config_db.get('hora_cierre', '22:00')
            try:
                hora_obj = pd.to_datetime(hora_actual_str, format='%H:%M').time()
            except:
                hora_obj = pd.to_datetime('20:00', format='%H:%M').time()
            
            nueva_hora = st.time_input("Hora exacta de Cierre de Jornada", value=hora_obj)
            st.caption("A esta hora, el servidor dejará de tomar pedidos y generará los tickets.")
            st.divider()

            # SECCIÓN C: INFO PÚBLICA
            st.subheader("📢 Información de la Empresa (Para la IA)")
            st.write("Este texto es el 'cerebro' de la IA cuando un cliente pregunte por horarios, dirección o feriados.")
            nuevo_mensaje = st.text_area("Mensaje Comercial Actual", value=mensaje_actual, height=150)

            # BOTÓN DE GUARDAR
            st.write("")
            submit_config = st.form_submit_button("💾 Guardar Toda la Configuración", use_container_width=True)

        # LÓGICA DE GUARDADO
        if submit_config:
            try:
                # 1. DB: Seguridad
                val_verif = 'true' if nuevo_estado_verif else 'false'
                cur.execute("UPDATE configuracion SET valor = %s WHERE clave = 'verificacion_clientes'", (val_verif,))
                
                # 2. DB: Horario
                hora_str = nueva_hora.strftime('%H:%M')
                cur.execute("UPDATE configuracion SET valor = %s WHERE clave = 'hora_cierre'", (hora_str,))
                
                # 3. DB: Mensaje
                cur.execute("UPDATE info_negocio SET mensaje_comercial = %s", (nuevo_mensaje,))
                
                conn.commit()
                
                # 4. N8N API: Actualizar Reloj
                with st.spinner("Sincronizando reloj del servidor..."):
                    hora, minuto = hora_str.split(':')
                    
                    # === ATENCIÓN: VERIFICA ESTA URL ===
                    webhook_n8n_api = "https://agentes-n8n.xjkmv6.easypanel.host/webhook/actualizar-horario"
                    
                    payload = {
                        "hora": int(hora),
                        "minuto": int(minuto),
                        # === ATENCIÓN: VERIFICA ESTE ID ===
                        "workflow_id": "L3Y8NKwOaPX2D8xa" 
                    }
                    
                    try:
                        res = requests.post(webhook_n8n_api, json=payload, timeout=10)
                        if res.status_code == 200:
                            st.success(f"✅ ¡Éxito! Base de datos actualizada y el reloj se reprogramó para las {hora_str} hs.")
                        else:
                            st.warning(f"Configuración guardada en la base de datos, pero el webhook de n8n devolvió el código {res.status_code}. Asegúrate de que la URL del webhook sea la de Producción y no la de Test.")
                    except Exception as api_err:
                        st.warning("Configuración en BD exitosa. (Aviso: El Webhook de n8n no está conectado).")

            except Exception as e:
                st.error(f"❌ Error al guardar en base de datos: {e}")
                conn.rollback()
            finally:
                conn.close()
