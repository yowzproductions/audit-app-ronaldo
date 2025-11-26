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

# --- LÓGICA DE CARREGAMENTO (MANTIDA) ---
if uploaded_history is not None and not st.session_state['resultados']:
    try:
        df_hist = pd.read_excel(uploaded_history)
        if 'CPF' in df_hist.columns: df_hist['CPF'] = df_hist['CPF'].astype(str).str.strip()
        if 'Padrao' in df_hist.columns: df_hist['Padrao'] = df_hist['Padrao'].astype(str).str.strip()
        if 'Pergunta' in df_hist.columns: df_hist['Pergunta'] = df_hist['Pergunta'].astype(str).str.strip()
        st.session_state['resultados'] = df_hist.to_dict('records')
        st.sidebar.success(f"♻️ Histórico: {len(st.session_state['resultados'])} registros.")
    except Exception as e:
        st.sidebar.error(f"Erro histórico: {e}")

# --- NAVEGAÇÃO ENTRE PÁGINAS ---
st.sidebar.markdown("---")
st.sidebar.header("2. Navegação")
pagina = st.sidebar.radio("Ir para:", ["📝 Execução da Auditoria", "📊 Painel Gerencial"])

# --- LÓGICA PRINCIPAL ---
if uploaded_file:
    try:
        df_treinos = pd.read_excel(uploaded_file, sheet_name='Base_Treinamentos')
        df_perguntas = pd.read_excel(uploaded_file, sheet_name='Padroes_Perguntas')
        
        # Blindagem de Tipos
        df_treinos['CPF'] = df_treinos['CPF'].astype(str).str.strip()
        df_treinos['Codigo_Padrao'] = df_treinos['Codigo_Padrao'].astype(str).str.strip()
        df_perguntas['Codigo_Padrao'] = df_perguntas['Codigo_Padrao'].astype(str).str.strip()
        df_perguntas['Pergunta'] = df_perguntas['Pergunta'].astype(str).str.strip()
        
    except Exception as e:
        st.error(f"Erro na Base de Dados: {e}")
        st.stop()

    # --- FILTROS GLOBAIS (AGORA MULTI-FILIAL) ---
    st.sidebar.header("3. Filtros")
    
    # Lógica "Selecionar Todas"
    todas_filiais = df_treinos['Filial'].unique()
    usar_todas = st.sidebar.checkbox("Selecionar TODAS as Filiais", value=False)
    
    if usar_todas:
        filiais_selecionadas = todas_filiais
        st.sidebar.info("Modo: Rede Completa")
    else:
        filiais_selecionadas = st.sidebar.multiselect("Selecione as Filiais", todas_filiais)
    
    padroes_disponiveis = df_perguntas['Codigo_Padrao'].unique()
    padroes_selecionados = st.sidebar.multiselect("Selecione os Padrões", padroes_disponiveis)

    # Verifica se tem filtros ativos para processar
    if len(filiais_selecionadas) > 0 and len(padroes_selecionados) > 0:
        
        # Filtra a Base Principal (Agora usando .isin para aceitar múltiplas filiais)
        df_filial = df_treinos[df_treinos['Filial'].isin(filiais_selecionadas)]
        df_match = df_filial[df_filial['Codigo_Padrao'].isin(padroes_selecionados)]

        # Prepara Ranking
        ranking = df_match.groupby(['CPF', 'Nome_Funcionario', 'Filial']).size().reset_index(name='Qtd_Padroes')
        ranking = ranking.sort_values(by=['Qtd_Padroes', 'Filial'], ascending=[False, True])

        # ==============================================================================
        # PÁGINA 1: EXECUÇÃO (AUDITORIA)
        # ==============================================================================
        if pagina == "📝 Execução da Auditoria":
            st.title("📝 Execução da Auditoria")
            st.markdown(f"**Escopo:** {len(filiais_selecionadas)} Filiais selecionadas | {len(padroes_selecionados)} Padrões")
            st.markdown("---")

            if df_match.empty:
                st.warning("Nenhum funcionário encontrado com esses filtros.")
            else:
                st.info(f"Encontramos {len(ranking)} funcionários na fila de auditoria.")
                
                # Memória Rápida
                memoria_respostas = {}
                for item in st.session_state['resultados']:
                    c, p, q = str(item['CPF']).strip(), str(item['Padrao']).strip(), str(item['Pergunta']).strip()
                    memoria_respostas[f"{c}_{p}_{q}"] = {"resultado": item['Resultado'], "obs": item['Observacao']}

                # Renderiza Lista
                for index, row in ranking.iterrows():
                    cpf = row['CPF']
                    nome = row['Nome_Funcionario']
                    filial_func = row['Filial']
                    qtd = row['Qtd_Padroes']
                    
                    # Status Visual
                    respondidos_count = sum(1 for r in st.session_state['resultados'] if str(r['CPF']).strip() == cpf)
                    status_icon = "🟢" if respondidos_count > 0 else "⚪"
                    
                    with st.expander(f"{status_icon} {nome} | {filial_func} (Match: {qtd})"):
                        padroes_do_funcionario = df_match[df_match['CPF'] == cpf]['Codigo_Padrao'].unique()
                        
                        with st.form(key=f"form_{cpf}"):
                            respostas = {}
                            for padrao in padroes_do_funcionario:
                                st.markdown(f"**--- Padrão {padrao} ---**")
                                perguntas_padrao = df_perguntas[df_perguntas['Codigo_Padrao'] == padrao]
                                
                                for idx, p_row in perguntas_padrao.iterrows():
                                    pergunta = p_row['Pergunta']
                                    chave_pergunta = f"{cpf}_{padrao}_{idx}"
                                    chave_busca = f"{cpf}_{padrao}_{pergunta}"
                                    
                                    # Preenchimento
                                    dados_previos = memoria_respostas.get(chave_busca)
                                    index_previo = None
                                    obs_previa = ""
                                    if dados_previos:
                                        opcoes = ["Conforme", "Não Conforme", "Não se Aplica"]
                                        if dados_previos['resultado'] in opcoes:
                                            index_previo = opcoes.index(dados_previos['resultado'])
                                        obs_previa = dados_previos['obs'] if not pd.isna(dados_previos['obs']) else ""

                                    st.write(pergunta)
                                    respostas[chave_pergunta] = st.radio("R", ["Conforme", "Não Conforme", "Não se Aplica"], key=chave_pergunta, horizontal=True, label_visibility="collapsed", index=index_previo)
                                    obs = st.text_input("Obs", value=obs_previa, key=f"obs_{chave_pergunta}")
                                    st.markdown("---")

                            submit = st.form_submit_button("💾 Salvar")
                            
                            if submit:
                                data_hora = obter_hora_brasilia()
                                itens_salvos = 0
                                for chave, resultado in respostas.items():
                                    if resultado is not None:
                                        _, padrao_ref, idx_ref = chave.split('_', 2)
                                        obs_ref = st.session_state[f"obs_{chave}"]
                                        try: p_txt = df_perguntas.loc[int(idx_ref), 'Pergunta']
                                        except: p_txt = "Erro"

                                        # Upsert
                                        st.session_state['resultados'] = [r for r in st.session_state['resultados'] if not (str(r['CPF']).strip() == cpf and str(r['Padrao']).strip() == padrao_ref and str(r['Pergunta']).strip() == p_txt)]
                                        st.session_state['resultados'].append({
                                            "Data": data_hora, "Filial": filial_func, "Funcionario": nome, "CPF": cpf,
                                            "Padrao": padrao_ref, "Pergunta": p_txt, "Resultado": resultado, "Observacao": obs_ref
                                        })
                                        itens_salvos += 1
                                if itens_salvos > 0:
                                    st.success("Salvo!")
                                    st.rerun()

        # ==============================================================================
        # PÁGINA 2: DASHBOARD GERENCIAL
        # ==============================================================================
        elif pagina == "📊 Painel Gerencial":
            st.title("📊 Painel de Controle e Gestão")
            st.markdown("Visão consolidada do progresso das auditorias.")
            st.markdown("---")

            # Cálculos de KPI
            total_funcionarios = len(ranking)
            
            # Filtra resultados salvos para bater com os filtros da tela (Filiais e Padrões selecionados)
            auditados_reais = [
                r['CPF'] for r in st.session_state['resultados'] 
                if r['Filial'] in filiais_selecionadas and str(r['Padrao']) in padroes_selecionados
            ]
            auditados_unicos = len(set(auditados_reais))
            pendentes = total_funcionarios - auditados_unicos
            progresso = auditados_unicos / total_funcionarios if total_funcionarios > 0 else 0

            # KPIs Visuais
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("🏢 Filiais no Escopo", len(filiais_selecionadas))
            col2.metric("👥 Total Funcionários", total_funcionarios)
            col3.metric("✅ Iniciados/Concluídos", auditados_unicos)
            col4.metric("⏳ Pendentes", pendentes, delta_color="inverse")
            
            st.progress(progresso, text=f"Progresso Global do Escopo Selecionado: {int(progresso*100)}%")

            # Tabela Detalhada por Filial
            st.subheader("📉 Status por Filial")
            dados_filial = []
            for filial in filiais_selecionadas:
                # Meta da Filial
                meta_filial = df_match[df_match['Filial'] == filial]['CPF'].nunique()
                # Realizado da Filial
                real_filial = len(set([r['CPF'] for r in st.session_state['resultados'] if r['Filial'] == filial and str(r['Padrao']) in padroes_selecionados]))
                
                pct = int((real_filial/meta_filial)*100) if meta_filial > 0 else 0
                dados_filial.append({
                    "Filial": filial,
                    "Meta (Pessoas)": meta_filial,
                    "Auditados": real_filial,
                    "% Conclusão": f"{pct}%"
                })
            
            df_view_filial = pd.DataFrame(dados_filial)
            st.dataframe(df_view_filial, use_container_width=True, hide_index=True)

            # Botões de Ação do Dashboard (Download)
            st.markdown("---")
            st.subheader("📂 Exportação de Dados")
            
            col_down, col_clean = st.columns([3, 1])
            with col_down:
                if st.session_state['resultados']:
                    df_export = pd.DataFrame(st.session_state['resultados'])
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df_export.to_excel(writer, index=False)
                    fname = obter_hora_brasilia().replace("/","-").replace(":", "
