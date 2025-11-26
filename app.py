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

# Inicialização segura
if 'resultados' not in st.session_state:
    st.session_state['resultados'] = []
if 'pagina_atual' not in st.session_state:
    st.session_state['pagina_atual'] = 0
if 'auditor_logado' not in st.session_state:
    st.session_state['auditor_logado'] = None

def obter_hora_brasilia():
    fuso = pytz.timezone('America/Sao_Paulo')
    return datetime.now(fuso).strftime("%d/%m/%Y %H:%M")

# --- BARRA LATERAL ---
st.sidebar.header("1. Configuração Inicial")

if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", use_container_width=True)
else:
    st.sidebar.write("🏢 DTO 01 - DCS 2025")

# 1. Base
uploaded_file = st.sidebar.file_uploader("Base de Dados (Excel)", type=["xlsx"], key="base")

# 2. Login do Auditor
df_auditores = None
auditor_validado = None

if uploaded_file:
    try:
        xls = pd.ExcelFile(uploaded_file)
        if 'Cadastro_Auditores' in xls.sheet_names:
            df_auditores = pd.read_excel(uploaded_file, sheet_name='Cadastro_Auditores')
            df_auditores['CPF_Auditor'] = df_auditores['CPF_Auditor'].astype(str).str.strip()
            
            st.sidebar.markdown("---")
            st.sidebar.subheader("🔐 Identificação")
            cpf_input = st.sidebar.text_input("Digite seu CPF (apenas números)", type="password")
            
            if cpf_input:
                auditor_encontrado = df_auditores[df_auditores['CPF_Auditor'] == cpf_input.strip()]
                if not auditor_encontrado.empty:
                    nome_auditor = auditor_encontrado.iloc[0]['Nome_Auditor']
                    auditor_validado = {'Nome': nome_auditor, 'CPF': cpf_input}
                    st.sidebar.success(f"Olá, {nome_auditor}!")
                else:
                    st.sidebar.error("CPF não autorizado.")
        else:
            # Modo legado (sem login)
            auditor_validado = {'Nome': 'Auditor Geral', 'CPF': '000'}
    except Exception as e:
        st.sidebar.warning(f"Erro ao ler cadastro: {e}")

st.sidebar.markdown("---")
uploaded_history_list = st.sidebar.file_uploader(
    "Carregar Histórico(s)", type=["xlsx"], key="hist", accept_multiple_files=True
)

# --- CARREGAMENTO DE HISTÓRICO ---
if uploaded_history_list and not st.session_state['resultados']:
    all_dataframes = []
    try:
        for arquivo in uploaded_history_list:
            df_temp = pd.read_excel(arquivo)
            df_temp.columns = [c.strip() for c in df_temp.columns]
            
            cols_str = ['CPF', 'Padrao', 'Pergunta', 'Auditor_CPF']
            for col in cols_str:
                if col in df_temp.columns: df_temp[col] = df_temp[col].astype(str).str.strip()
            
            all_dataframes.append(df_temp)

        if all_dataframes:
            df_final_hist = pd.concat(all_dataframes, ignore_index=True)
            st.session_state['resultados'] = df_final_hist.to_dict('records')
            st.sidebar.success(f"📦 Consolidado: {len(st.session_state['resultados'])} registros.")
    except Exception as e:
        st.sidebar.error(f"Erro histórico: {e}")

# --- NAVEGAÇÃO ---
st.sidebar.markdown("---")
pagina = st.sidebar.radio("Ir para:", ["📝 Execução da Auditoria", "📊 Painel Gerencial"])

# --- LEITURA DA BASE PRINCIPAL ---
df_treinos = pd.DataFrame()
df_perguntas = pd.DataFrame()
dados_carregados = False

if uploaded_file:
    try:
        df_treinos = pd.read_excel(uploaded_file, sheet_name='Base_Treinamentos')
        df_perguntas = pd.read_excel(uploaded_file, sheet_name='Padroes_Perguntas')
        
        # Blindagem
        df_treinos['CPF'] = df_treinos['CPF'].astype(str).str.strip()
        df_treinos['Codigo_Padrao'] = df_treinos['Codigo_Padrao'].astype(str).str.strip()
        df_perguntas['Codigo_Padrao'] = df_perguntas['Codigo_Padrao'].astype(str).str.strip()
        df_perguntas['Pergunta'] = df_perguntas['Pergunta'].astype(str).str.strip()
        
        dados_carregados = True
    except Exception as e:
        st.error(f"Erro na Base de Dados: {e}")
        st.stop()

# =========================================================
# PÁGINA 1: EXECUÇÃO DA AUDITORIA
# =========================================================
if pagina == "📝 Execução da Auditoria":
    if not dados_carregados:
        st.info("👈 Por favor, carregue a Base de Dados na barra lateral.")
    else:
        st.title("📝 Execução da Auditoria")

        # TRAVA DE SEGURANÇA
        if df_auditores is not None and auditor_validado is None:
            st.warning("🔒 ACESSO BLOQUEADO: Identifique-se na barra lateral.")
            st.stop()

        # --- FILTROS LOCAIS DA EXECUÇÃO ---
        st.sidebar.header("3. Filtros de Execução")
        todas_filiais = df_treinos['Filial'].dropna().unique()
        
        if st.sidebar.checkbox("Todas as Filiais", value=False):
            filiais_selecionadas = list(todas_filiais)
        else:
            filiais_selecionadas = st.sidebar.multiselect("Selecione Filiais", todas_filiais)
        
        padroes_disponis = df_perguntas['Codigo_Padrao'].dropna().unique()
        if st.sidebar.checkbox("Todos os Padrões", value=False):
            padroes_selecionados = list(padroes_disponis)
        else:
            padroes_selecionados = st.sidebar.multiselect("Selecione Padrões", padroes_disponis)

        if not filiais_selecionadas or not padroes_selecionados:
            st.info("👈 Selecione Filiais e Padrões na barra lateral para carregar a fila.")
        else:
            nome_aud_display = auditor_validado['Nome'] if auditor_validado else "Geral"
            st.markdown(f"**Auditor:** {nome_aud_display} | **Filtro:** {len(filiais_selecionadas)} Filiais")
            st.markdown("---")

            # Processamento da Fila
            df_match = df_treinos[
                (df_treinos['Filial'].isin(filiais_selecionadas)) & 
                (df_treinos['Codigo_Padrao'].isin(padroes_selecionados))
            ]

            if df_match.empty:
                st.warning("Nenhum funcionário encontrado para estes filtros.")
            else:
                ranking = df_match.groupby(['CPF', 'Nome_Funcionario', 'Filial']).size().reset_index(name='Qtd_Padroes')
                ranking = ranking.sort_values(by=['Qtd_Padroes', 'Filial'], ascending=[False, True])

                # Mapa de Perguntas
                mapa_perguntas = {}
                for padrao in padroes_selecionados:
                    perguntas = df_perguntas[df_perguntas['Codigo_Padrao'] == padrao]
                    mapa_perguntas[padrao] = list(zip(perguntas.index, perguntas['Pergunta']))

                # Paginação
                total_funcionarios = len(ranking)
                ITENS_POR_PAGINA = 10
                total_paginas = (total_funcionarios - 1) // ITENS_POR_PAGINA + 1
                
                c1, c2, c3 = st.columns([1, 3, 1])
                with c1:
                    if st.button("⬅️ Anterior") and st.session_state['pagina_atual'] > 0:
                        st.session_state['pagina_atual'] -= 1
                        st.rerun()
                with c3:
                    if st.button("Próximo ➡️") and st.session_state['pagina_atual'] < total_paginas - 1:
                        st.session_state['pagina_atual'] += 1
                        st.rerun()
                with c2:
                    st.markdown(f"<div style='text-align: center'><b>Página {st.session_state['pagina_atual'] + 1} de {total_paginas}</b></div>", unsafe_allow_html=True)
                
                start = st.session_state['pagina_atual'] * ITENS_POR_PAGINA
                end = start + ITENS_POR_PAGINA
                ranking_pagina = ranking.iloc[start:end]

                # Memória Rápida
                memoria = {}
                for r in st.session_state['resultados']:
                    key = f"{str(r.get('CPF','')).strip()}_{str(r.get('Padrao','')).strip()}_{str(r.get('Pergunta','')).strip()}"
                    memoria[key] = {"res": r.get('Resultado'), "obs": r.get('Observacao')}

                st.markdown("---")

                # Renderização dos Cards
                for idx, row in ranking_pagina.iterrows():
                    cpf = row['CPF']
                    nome = row['Nome_Funcionario']
                    filial = row['Filial']
                    
                    resps_salvas = sum(1 for r in st.session_state['resultados'] if str(r.get('CPF','')).strip() == cpf)
                    icon = "⚪" if resps_salvas == 0 else "🟢"
                    
                    with st.expander(f"{icon} {nome} | {filial}"):
                        pads_func = df_match[df_match['CPF'] == cpf]['Codigo_Padrao'].unique()
                        
                        # --- FORMULÁRIO (CORRIGIDO) ---
                        with st.form(key=f"form_{cpf}"):
                            respostas_form = {}
                            
                            # Loop de Padrões
                            for padrao in pads_func:
                                st.markdown(f"**--- Padrão {padrao} ---**")
                                # Loop de Perguntas
                                for idx_p, txt_p in mapa_perguntas.get(padrao, []):
                                    key_p = f"{cpf}_{padrao}_{idx_p}"
                                    key_b = f"{cpf}_{padrao}_{txt_p}"
                                    
                                    dados = memoria.get(key_b)
                                    idx_val, obs_val = None, ""
                                    if dados:
                                        opts = ["Conforme", "Não Conforme", "Não se Aplica"]
                                        if dados['res'] in opts: idx_val = opts.index(dados['res'])
                                        obs_val = dados['obs'] if not pd.isna(dados['obs']) else ""

                                    st.write(txt_p)
                                    respostas_form[key_p] = st.radio("R", ["Conforme", "Não Conforme", "Não se Aplica"], key=key_p, horizontal=True, label_visibility="collapsed", index=idx_val)
                                    st.text_input("Obs", value=obs_val, key=f"obs_{key_p}")
                                    st.markdown("---")
                            
                            # --- BOTÃO DE SUBMIT (AGORA DENTRO DO FORM, MAS FORA DOS LOOPS) ---
                            submitted = st.form_submit_button("💾 Salvar")
                            
                            if submitted:
                                data_hora = obter_hora_brasilia()
                                salvos = 0
                                for k, res in respostas_form.items():
                                    if res is not None:
                                        _, pad_ref, idx_ref = k.split('_', 2)
                                        try: p_txt = df_perguntas.loc[int(idx_ref), 'Pergunta']
                                        except: p_txt = "Erro"
                                        
                                        # Remove anterior
                                        st.session_state['resultados'] = [r for r in st.session_state['resultados'] if not (str(r.get('CPF','')).strip() == cpf and str(r.get('Padrao','')).strip() == pad_ref and str(r.get('Pergunta','')).strip() == p_txt)]
                                        
                                        obs_ref = st.session_state.get(f"obs_{k}", "")
                                        novo_reg = {
                                            "Data": data_hora, "Filial": filial, "Funcionario": nome, "CPF": cpf,
                                            "Padrao": pad_ref, "Pergunta": p_txt, "Resultado": res, "Observacao": obs_ref
                                        }
                                        if auditor_validado:
                                            novo_reg["Auditor_Nome"] = auditor_validado['Nome']
                                            novo_reg["Auditor_CPF"] = auditor_validado['CPF']
                                            
                                        st.session_state['resultados'].append(novo_reg)
                                        salvos += 1
                                if salvos > 0:
                                    st.success("Salvo com sucesso!")
                                    st.rerun()

# =========================================================
# PÁGINA 2: DASHBOARD (SEPARADO E INDEPENDENTE)
# =========================================================
elif pagina == "📊 Painel Gerencial":
    st.title("📊 Painel Gerencial & Rastreabilidade")
    
    if not dados_carregados:
        st.info("👈 Por favor, carregue a Base de Dados para ver os KPIs.")
    elif not st.session_state['resultados']:
        st.info("Sem dados consolidados. Carregue históricos ou realize auditorias.")
    else:
        df_resultados = pd.DataFrame(st.session_state['resultados'])
        
        # --- FILTROS DO DASHBOARD ---
        st.sidebar.header("3. Filtros do Dashboard")
        filiais_dash = df_treinos['Filial'].dropna().unique()
        filiais_sel_dash = st.sidebar.multiselect("Filtrar KPIs por Filial", filiais_dash, default=filiais_dash)

        # 1. Auditoria de Conflitos (Sempre visível)
        st.markdown("
