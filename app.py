import streamlit as st
import pandas as pd
import psycopg2
import os

st.set_page_config(page_title="Verdu IA - Panel", layout="wide")

# Función de conexión ultra-segura
def get_connection():
    try:
        return psycopg2.connect(
            host=os.getenv("DB_HOST", "agentes_db_postgres"),
            database=os.getenv("DB_NAME", "db_agente"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASS"),
            port=os.getenv("DB_PORT", "5432"),
            connect_timeout=3
        )
    except Exception as e:
        return None

st.title("🍎 Panel de Control - Verdu IA")

conn = get_connection()

if conn is None:
    st.error("❌ No se pudo conectar a la base de datos.")
    st.info("Verifica las variables de entorno en Easypanel y que el nombre del host sea correcto.")
    st.stop() # Esto detiene el script pero NO cierra el contenedor

# El resto de tu lógica de Dashboard y Vendedores...
st.success("✅ Conectado a la base de datos db_agente")
