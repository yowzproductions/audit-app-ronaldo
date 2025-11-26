import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
import os
import pytz

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="DTO 01 - DCS 2025", 
    page_icon="🏢", 
    layout="wide"
)

# Inicialização segura da memória
if 'resultados' not in st.session_state:
    st.session_state['resultados'] = []

def obter_hora_brasilia():
    fuso = pytz.timezone('America/Sao_Paulo')
    return datetime.now(fuso).strftime("%d/%m/%Y %H:%M")

# --- BARRA LATERAL (CONFIGURAÇÃO GLOBAL) ---
st.sidebar.header("1. Carga de Dados")

if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", use_container_width=True)
else:
    st.sidebar.write("🏢 DTO 01 - DCS 2025")

# 1. Uploads
uploaded_file = st.sidebar.file_uploader("Base de Dados (Excel)", type=["xlsx"], key="base")

st.sidebar.markdown("---")
uploaded_history = st.sidebar.file_uploader("Carregar Histórico (Opcional)", type=["xlsx"], key="hist")

# --- LÓGICA DE CARREGAMENTO DO HISTÓRICO ---
if uploaded_history is not None and not st.session_state['resultados']:
    try:
        df_hist = pd.read_excel(uploaded_history)
        if 'CPF' in df_hist.columns: df_hist['CPF'] = df_hist['CPF'].astype(str).str.strip()
        if 'Padrao' in df_hist.columns: df_hist['Padrao'] = df_hist['Padrao'].astype(str).str.strip()
        if 'Pergunta' in df
