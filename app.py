import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
import os
import pytz

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="DTO 01 - DCS 2025", 
    page_icon="🏢", 
    layout="wide"
)

# --- 2. INICIALIZAÇÃO DE MEMÓRIA ---
if 'resultados' not in st.session_state:
    st.session_state['resultados'] = []

if 'pagina_atual' not in st.session_state:
    st.session_state['pagina_atual'] = 0

if 'auditor_logado' not in st.session_state:
    st.session_state['auditor_logado'] = None

# --- 3. FUNÇÕES AUXILIARES ---
def obter_hora_brasilia():
    fuso = pytz.timezone('America/Sao_Paulo')
    return datetime.now(fuso).strftime("%d/%m/%Y %H:%M")

# --- 4. BARRA LATERAL ---
st.sidebar.header("1. Configuração")

# Logo
if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", use_container_width=True)
else:
    st.sidebar.write("🏢 DTO 01 - DCS 2025")

# Upload Base de Dados
uploaded_file = st.sidebar.file_uploader("Base (Excel)", type=["xlsx"], key="base")

# Upload Histórico (Múltiplos Arquivos)
uploaded_hist = st.sidebar.file_uploader(
    "Carregar Histórico (Opcional)", 
    type=["xlsx"], 
    key="hist", 
    accept_multiple_files=True
)

# Processamento do Histórico
if uploaded_hist and not st.session_state['resultados']:
    lista_dfs = []
    try:
        for arquivo in uploaded_hist:
            df_temp = pd.read_excel(arquivo)
            # Limpa nomes das colunas
            df_temp.columns = [c.strip() for c in df_temp.columns]
            
            # Converte colunas chave para texto
            colunas_texto = ['CPF', 'Padrao', 'Pergunta', 'Auditor_CPF']
            for col in colunas_texto:
                if col in df_temp.columns:
                    df_temp[col] = df_temp[col].astype(str).str.strip()
            
            lista_dfs.append(df_temp)

        if lista_dfs:
            df_final = pd.concat(lista_dfs, ignore_index=True)
            st.session_state['resultados'] = df_final.to_dict('records')
            qtd_regs = len(st.session_state['resultados'])
