import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
import os
import pytz

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="DTO 01 - DCS 2025", page_icon="🏢", layout="wide")

# --- MEMÓRIA ---
if 'resultados' not in st.session_state: st.session_state['resultados'] = []
if 'pagina_atual' not in st.session_state: st.session_state['pagina_atual'] = 0
if 'auditor_logado' not in st.session_state: st.session_state['auditor_logado'] = None

def obter_hora():
    return datetime.now(pytz.timezone('America/Sao_Paulo')).strftime("%d/%m/%Y %H:%M")

# --- BARRA LATERAL ---
st.sidebar.header("1. Configuração")
if os.path.exists("logo.png"): st.sidebar.image("logo.png", use_container_width=True)
else: st.sidebar.write("🏢 DTO 01 - DCS 2025")

# Uploads
uploaded_file = st.sidebar.file_uploader("Base (Excel)", type=["xlsx"], key="base")
uploaded_hist = st.sidebar.file_uploader("Histórico", type=["xlsx"], key="hist", accept_multiple_files=True)

# Lógica Histórico
if uploaded_hist and not st.session_state['resultados']:
    all_dfs = []
    try:
        for arq in uploaded_hist:
            df = pd.read_excel(arq)
            df.columns = [c.strip() for c in df.columns]
            for c in ['CPF','Padrao','Pergunta','Auditor_CPF']:
                if c in df.columns: df[c] = df[c].astype(str).str.strip()
            all_dfs.append(df)
        if all_dfs:
            st.session_state['resultados'] = pd.concat(all_dfs, ignore_index=True).to_dict('records')
            st.sidebar.success(f"📦 Consolidado: {len(st.session_state['resultados'])} regs.")
    except Exception as e: st.sidebar.error(f"Erro: {e}")

# Login Auditor
df_auditores, auditor_valido = None, None
if uploaded_file:
    try:
        xls = pd.ExcelFile(uploaded_file)
        if 'Cadastro_Auditores' in xls.sheet_names:
            df_auditores = pd.read_excel(uploaded_file, sheet_name='Cadastro_Auditores')
            df_auditores['CPF_Auditor'] = df_auditores['CPF_Auditor'].astype(str).str.strip()
            st.sidebar.markdown("---")
            cpf_in = st.sidebar.text_input("Seu CPF (Login)", type="password")
            if cpf_in:
                match = df_auditores[df_auditores['CPF_Auditor'] == cpf_in.strip()]
                if not match.empty:
                    auditor_valido = {'Nome': match.iloc[0]['Nome_Auditor'], 'CPF': cpf_in}
                    st.sidebar.success(f"Olá, {auditor_valido['Nome']}!")
                else: st.sidebar.error("CPF inválido.")
        else: auditor_valido = {'Nome': 'Geral', 'CPF': '000'}
    except: pass

st.sidebar.markdown("---")
pagina = st.sidebar.radio("Navegação:", ["📝 Execução", "📊 Painel Gerencial"])

# Leitura Base
df_treinos, df_perguntas, dados_ok
