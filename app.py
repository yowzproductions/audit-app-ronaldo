import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
import os
import pytz

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="DTO 01 - DCS SCANIA", 
    page_icon="🚛", 
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
    st.sidebar.write("🏢 DTO 01 - DCS SCANIA")

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
            df_temp.columns = [c.strip() for c in df_temp.columns]
            for col in ['CPF', 'Padrao', 'Pergunta', 'Auditor_CPF']:
                if col in df_temp.columns:
                    df_temp[col] = df_temp[col].astype(str).str.strip()
            lista_dfs.append(df_temp)

        if lista_dfs:
            df_final = pd.concat(lista_dfs, ignore_index=True)
            st.session_state['resultados'] = df_final.to_dict('records')
            qtd_regs = len(st.session_state['resultados'])
            st.sidebar.success(f"📦 Consolidado: {qtd_regs} registros.")
    except Exception as e:
        st.sidebar.error
        # ================= PÁGINA 1: EXECUÇÃO =================
if pagina == "📝 EXECUTAR DTO 01 - DCS SCANIA":
    
    if not dados_ok:
        st.info("👈 Por favor, carregue a Base de Dados.")
    elif df_auditores is not None and auditor_valido is None:
        st.warning("🔒 ACESSO BLOQUEADO: Identifique-se na barra lateral.")
    else:
        st.title("📝 EXECUTAR DTO 01 - DCS SCANIA")
        
        # Filtros Específicos da Execução
        st.sidebar.header("📍 Filtros de Execução")
        
        lista_filiais = df_treinos['Filial'].dropna().unique()
        filiais_sel = st.sidebar.multiselect("Selecione a(s) Filial(is)", lista_filiais)
        
        lista_padroes = df_perguntas['Codigo_Padrao'].dropna().unique()
        if st.sidebar.checkbox("Todos os Padrões", value=False):
            padroes_sel = list(lista_padroes)
        else:
            padroes_sel = st.sidebar.multiselect("Selecione Padrões", lista_padroes)

        if filiais_sel and padroes_sel:
            df_match = df_treinos[
                (df_treinos['Filial'].isin(filiais_sel)) & 
                (df_treinos['Codigo_Padrao'].isin(padroes_sel))
            ]
            
            if df_match.empty:
                st.warning("Nenhum funcionário encontrado.")
            else:
                ranking = df_match.groupby(['CPF','Nome_Funcionario','Filial']).size().reset_index(name='Qtd')
                ranking = ranking.sort_values(by=['Qtd','Filial'], ascending=[False,True])
                
                # Paginação
                total_p = (len(ranking)-1)//10 + 1
                c1, c2, c3 = st.columns([1,3,1])
                with c1:
                    if st.button("⬅️") and st.session_state['pagina_atual'] > 0:
                        st.session_state['pagina_atual'] -= 1
                        st.rerun()
                with c3:
                    if st.button("➡️") and st.session_state['pagina_atual'] < total_p - 1:
                        st.session_state['pagina_atual'] += 1
                        st.rerun()
                with c2:
                    st.markdown(f"<div style='text-align:center'>Pág {st.session_state['pagina_atual']+1}/{total_p}</div>", unsafe_allow_html=True)
                
                inicio = st.session_state['pagina_atual'] * 10
                fim = inicio + 10
                ranking_pagina = ranking.iloc[inicio:fim]
                
                # Memória
                memoria = {}
                for r in st.session_state['resultados']:
                    k = f"{str(r.get('CPF','')).strip()}_{str(r.get('Padrao','')).strip()}_{str(r.get('Pergunta','')).strip()}"
                    memoria[k] = {'res': r.get('Resultado'), 'obs': r.get('Observacao')}
                
                for _, row in ranking_pagina.iterrows():
                    cpf = row['CPF']
                    nome = row['Nome_Funcionario']
                    filial = row['Filial']
                    
                    respondidos = sum(1 for r in st.session_state['resultados'] if str(r.get('CPF','')).strip() == cpf)
                    icon = "🟢" if respondidos > 0 else "⚪"
                    
                    with st.expander(f"{icon} {nome} | {filial}"):
                        padroes_func = df_match[df_match['CPF'] == cpf]['Codigo_Padrao'].unique()
                        with st.form(key=f"f_{cpf}"):
                            respostas_temp = {}
                            obs_temp = {}
                            for pad in padroes_func:
                                st.markdown(f"**{pad}**")
                                pergs_pad = df_perguntas[df_perguntas['Codigo_Padrao'] == pad]
                                for idx, p_row in pergs_pad.iterrows():
                                    txt_p = p_row['Pergunta']
                                    kw = f"{cpf}_{pad}_{idx}"
                                    kb = f"{cpf}_{pad}_{txt_p}"
                                    
                                    prev = memoria.get(kb)
                                    idx_r = None
                                    obs_v = ""
                                    if prev:
                                        opts = ["Conforme", "Não Conforme", "Não se Aplica"]
                                        if prev['res'] in opts: idx_r = opts.index(prev['res'])
                                        obs_v = prev['obs'] if prev['obs'] else ""
                                    
                                    st.write(txt_p)
                                    respostas_temp[kw] = st.radio("R", ["Conforme", "Não Conforme", "Não se Aplica"], key=kw, horizontal=True, index=idx_r, label_visibility="collapsed")
                                    obs_temp[kw] = st.text_input("Obs", value=obs_v, key=f"obs_{kw}")
                                    st.markdown("---")
                            
                            if st.form_submit_button("💾 Salvar"):
                                dh = obter_hora_brasilia()
                                cnt = 0
                                for k, v in respostas_temp.items():
                                    if v:
                                        _, pr, ir = k.split('_', 2)
                                        try: pt = df_perguntas.loc[int(ir), 'Pergunta']
                                        except:
