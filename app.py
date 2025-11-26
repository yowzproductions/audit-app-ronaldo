import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
import os

# --- CONFIGURAÇÃO DA PÁGINA (BRANDING ATUALIZADO) ---
st.set_page_config(
    page_title="DTO 01 - DCS 2025", 
    page_icon="🏢", 
    layout="wide"
)

# Inicialização segura da memória
if 'resultados' not in st.session_state:
    st.session_state['resultados'] = []

# --- BARRA LATERAL COM LOGO E NOME ---
st.sidebar.header("1. Carga de Dados")

# Tenta carregar a logo se ela existir no GitHub
if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", use_container_width=True)
else:
    # Se não achar a imagem, mostra o novo nome
    st.sidebar.write("🏢 DTO 01 - DCS 2025")

uploaded_file = st.sidebar.file_uploader("Suba o arquivo Excel (dados_auditoria.xlsx)", type=["xlsx"])

# --- TÍTULO PRINCIPAL DA PÁGINA ---
st.title("🏢 DTO 01 - DCS 2025")
st.markdown("### Auditoria de Padrões e Processos")
st.markdown("---")

if uploaded_file:
    try:
        df_treinos = pd.read_excel(uploaded_file, sheet_name='Base_Treinamentos')
        df_perguntas = pd.read_excel(uploaded_file, sheet_name='Padroes_Perguntas')
        
        # --- BLINDAGEM DE DADOS ---
        df_treinos['CPF'] = df_treinos['CPF'].astype(str)
        df_treinos['Codigo_Padrao'] = df_treinos['Codigo_Padrao'].astype(str)
        df_perguntas['Codigo_Padrao'] = df_perguntas['Codigo_Padrao'].astype(str)
        
        st.sidebar.success("Dados carregados e tratados com sucesso!")
    except Exception as e:
        st.error(f"Erro ao ler o arquivo: {e}")
        st.stop()

    # --- PASSO 2: FILTROS DO AUDITOR ---
    st.sidebar.header("2. Configuração da Auditoria")
    
    filiais = df_treinos['Filial'].unique()
    filial_selecionada = st.sidebar.selectbox("Selecione a Filial", filiais)
    
    padroes_disponiveis = df_perguntas['Codigo_Padrao'].unique()
    padroes_selecionados = st.sidebar.multiselect("Quais padrões você vai auditar hoje?", padroes_disponiveis)

    if filial_selecionada and padroes_selecionados:
        
        # Filtros
        df_filial = df_treinos[df_treinos['Filial'] == filial_selecionada]
        df_match = df_filial[df_filial['Codigo_Padrao'].isin(padroes_selecionados)]
        
        if df_match.empty:
            st.warning("Nenhum funcionário nesta filial possui
