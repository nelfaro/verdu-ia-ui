import streamlit as st
import pandas as pd
import psycopg2
import os

# Configuración inicial
st.set_page_config(page_title="Verdu IA", layout="wide")

# Función de conexión con manejo de errores real
def get_connection():
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "db_postgres"),
            database=os.getenv("DB_NAME", "db_agente"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASS", "Q!6x$8wLtwqbWv2"),
            port=os.getenv("DB_PORT", "5432"),
            connect_timeout=3
        )
        return conn
    except Exception as e:
        # Esto imprimirá el error en la web en lugar de cerrar la app
        st.error(f"❌ Error de conexión a la Base de Datos: {e}")
        st.info("Revisa que DB_HOST coincida con el nombre del servicio en Easypanel")
        return None

conn = get_connection()

if conn is None:
    st.warning("La aplicación está corriendo en modo desconectado. Verifica las credenciales.")
    st.stop() # Detiene la ejecución del resto del script pero MANTIENE la web abierta
