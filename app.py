import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
import os
import requests
import hashlib

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Ciuccoli Hnos - Sistema Mayorista", layout="wide", page_icon="🍎")

# Ocultar menú de Streamlit por defecto
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "agentes_db_postgres"),
        database=os.getenv("DB_NAME", "db_agente"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASS"),
        port=os.getenv("DB_PORT", "5432")
    )

# --- SISTEMA DE LOGIN ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def check_login(username, password):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT password_hash FROM usuarios_ui WHERE usuario = %s", (username,))
    record = cur.fetchone()
    conn.close()
    
    if record:
        if record[0] == hash_password(password):
            return True
    return False

# Inicializar estado de sesión
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False

# --- PANTALLA DE LOGIN ---
if not st.session_state['autenticado']:
    st.markdown("<h1 style='text-align: center; color: #2e7d32;'>🍏 Ciuccoli Hnos - Acceso</h1>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        with st.form("login_form"):
            user = st.text_input("Usuario")
            pwd = st.text_input("Contraseña", type="password")
            submit = st.form_submit_button("Ingresar al Sistema")
            
            if submit:
                if check_login(user, pwd):
                    st.session_state['autenticado'] = True
                    st.session_state['usuario_actual'] = user
                    st.rerun()
                else:
                    st.error("❌ Usuario o contraseña incorrectos.")
else:
    # --- PANTALLA PRINCIPAL (Solo si está logueado) ---
    
    # Botón de Cerrar Sesión arriba a la derecha
    c1, c2 = st.columns([8, 1])
    with c2:
        if st.button("🚪 Cerrar Sesión"):
            st.session_state['autenticado'] = False
            st.rerun()

    st.title("🍏 Panel de Control - Ciuccoli Hnos")

    menu = st.sidebar.selectbox("Navegación", ["📈 Dashboard Hoy", "📊 Analíticas Semanales", "👥 Gestión de Vendedores", "💬 CRM Chatwoot", "📤 Carga de Stock"])

    # (AQUÍ PEGAS TODO EL RESTO DE TU CÓDIGO ACTUAL)
    # Por ejemplo, el bloque if menu == "📈 Dashboard Hoy": ... etc.
    
    # --- 1. DASHBOARD HOY ---
    if menu == "📈 Dashboard Hoy":
        st.header("📊 Resultados del Día")
        conn = get_connection()
        # ... (Tu código actual del Dashboard)
        conn.close()

    # ... (Pega el resto de los menús aquí respetando la indentación)
