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

# --- BARRA LATERAL ---
st.sidebar.header("1. Carga de Dados")

if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", use_container_width=True)
else:
    st.sidebar.write("🏢 DTO 01 - DCS 2025")

# 1. Base
uploaded_file = st.sidebar.file_uploader("1º Passo: Base de Dados (Excel)", type=["xlsx"], key="base")

# 2. Histórico
st.sidebar.markdown("---")
st.sidebar.markdown("**Vai continuar uma auditoria anterior?**")
uploaded_history = st.sidebar.file_uploader("2º Passo: Carregar Histórico (Opcional)", type=["xlsx"], key="hist")

# --- LÓGICA DE CARREGAMENTO DO HISTÓRICO ---
if uploaded_history is not None and not st.session_state['resultados']:
    try:
        df_hist = pd.read_excel(uploaded_history)
        
        # Normalização de Tipos
        if 'CPF' in df_hist.columns:
            df_hist['CPF'] = df_hist['CPF'].astype(str).str.strip()
        if 'Padrao' in df_hist.columns:
            df_hist['Padrao'] = df_hist['Padrao'].astype(str).str.strip()
        if 'Pergunta' in df_hist.columns:
            df_hist['Pergunta'] = df_hist['Pergunta'].astype(str).str.strip()
            
        st.session_state['resultados'] = df_hist.to_dict('records')
        st.sidebar.success(f"♻️ Histórico restaurado! {len(st.session_state['resultados'])} registros carregados.")
    except Exception as e:
        st.sidebar.error(f"Erro ao ler histórico: {e}")

# --- TÍTULO ---
st.title("🏢 DTO 01 - DCS 2025")
st.markdown("### Auditoria de Padrões e Processos")
st.markdown("---")

if uploaded_file:
    try:
        df_treinos = pd.read_excel(uploaded_file, sheet_name='Base_Treinamentos')
        df_perguntas = pd.read_excel(uploaded_file, sheet_name='Padroes_Perguntas')
        
        # Blindagem Base de Dados
        df_treinos['CPF'] = df_treinos['CPF'].astype(str).str.strip()
        df_treinos['Codigo_Padrao'] = df_treinos['Codigo_Padrao'].astype(str).str.strip()
        df_perguntas['Codigo_Padrao'] = df_perguntas['Codigo_Padrao'].astype(str).str.strip()
        df_perguntas['Pergunta'] = df_perguntas['Pergunta'].astype(str).str.strip()
        
    except Exception as e:
        st.error(f"Erro ao ler base de dados: {e}")
        st.stop()

    # --- MEMÓRIA RÁPIDA ---
    memoria_respostas = {}
    for item in st.session_state['resultados']:
        c = str(item['CPF']).strip()
        p = str(item['Padrao']).strip()
        q = str(item['Pergunta']).strip()
        chave_unica = f"{c}_{p}_{q}"
        memoria_respostas[chave_unica] = {
            "resultado": item['Resultado'],
            "obs": item['Observacao']
        }

    # --- FILTROS ---
    st.sidebar.header("2. Configuração")
    filiais = df_treinos['Filial'].unique()
    filial_selecionada = st.sidebar.selectbox("Selecione a Filial", filiais)
    
    padroes_disponiveis = df_perguntas['Codigo_Padrao'].unique()
    padroes_selecionados = st.sidebar.multiselect("Quais padrões auditar?", padroes_disponiveis)

    if filial_selecionada and padroes_selecionados:
        
        df_filial = df_treinos[df_treinos['Filial'] == filial_selecionada]
        df_match = df_filial[df_filial['Codigo_Padrao'].isin(padroes_selecionados)]
        
        if df_match.empty:
            st.warning("Nenhum funcionário encontrado.")
        else:
            # Ranking de Funcionários Elegíveis
            ranking = df_match.groupby(['CPF', 'Nome_Funcionario']).size().reset_index(name='Qtd_Padroes')
            ranking = ranking.sort_values(by='Qtd_Padroes', ascending=False)

            # --- 📊 DASHBOARD DE GESTÃO (NOVO) ---
            st.markdown("### 📊 Painel de Controle")
            
            # Cálculo de KPIs
            total_funcionarios = len(ranking)
            
            # Identifica quem já foi auditado (pelo menos 1 resposta salva para os padrões selecionados)
            # Filtra resultados atuais para considerar apenas a filial e padrões selecionados
            auditorias_realizadas = [
                r['CPF'] for r in st.session_state['resultados'] 
                if r['Filial'] == filial_selecionada and str(r['Padrao']) in padroes_selecionados
            ]
            # Conta CPFs únicos que já têm registro
            auditados_unicos = len(set(auditorias_realizadas))
            
            pendentes = total_funcionarios - auditados_unicos
            progresso = auditados_unicos / total_funcionarios if total_funcionarios > 0 else 0

            # Exibição Visual
            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("Total Pessoas (Escopo)", total_funcionarios)
            kpi2.metric("✅ Auditados (Iniciado)", auditados_unicos)
            kpi3.metric("⏳ Pendentes", pendentes, delta_color="inverse")
            
            st.progress(progresso, text=f"Progresso Geral: {int(progresso*100)}%")
            
            # Visão detalhada por Padrão (Expansor)
            with st.expander("📉 Ver Status por Padrão (Detalhado)"):
                # Cria uma tabela cruzada simples
                status_padroes = []
                for padrao in padroes_selecionados:
                    # Quantas pessoas deveriam ter esse padrão?
                    qtd_meta = df_match[df_match['Codigo_Padrao'] == padrao]['CPF'].nunique()
                    # Quantas pessoas já tem registro desse padrão?
                    qtd_real = len(set([
                        r['CPF'] for r in st.session_state['resultados'] 
                        if str(r['Padrao']) == padrao and r['Filial'] == filial_selecionada
                    ]))
                    status_padroes.append({
                        "Padrão": padrao,
                        "Meta (Pessoas)": qtd_meta,
                        "Realizado": qtd_real,
                        "% Conclusão": f"{int((qtd_real/qtd_meta)*100)}%" if qtd_meta > 0 else "0%"
                    })
                st.dataframe(pd.DataFrame(status_padroes), hide_index=True, use_container_width=True)
            
            st.markdown("---")
            # --- FIM DO DASHBOARD ---

            st.subheader(f"📍 Fila de Auditoria - {filial_selecionada}")
            
            for index, row in ranking.iterrows():
                cpf = row['CPF']
                nome = row['Nome_Funcionario']
                qtd = row['Qtd_Padroes']
                
                # Feedback Visual
                respondidos_count = sum(1 for r in st.session_state['resultados'] if str(r['CPF']).strip() == cpf)
                
                # Ícone muda se já iniciou
                status_icon = "🟢" if respondidos_count > 0 else "⚪"
                label_status = "Iniciado" if respondidos_count > 0 else "Pendente"
                
                with st.expander(f"{status_icon} {nome} | {label_status} (Match: {qtd} padrões)"):
                    st.write(f"**CPF:** {cpf}")
                    
                    padroes_do_funcionario = df_match[df_match['CPF'] == cpf]['Codigo_Padrao'].unique()
                    
                    with st.form(key=f"form_{cpf}"):
                        respostas = {}
                        for padrao in padroes_do_funcionario:
                            st.markdown(f"**--- Padrão {padrao} ---**")
                            perguntas_padrao = df_perguntas[df_perguntas['Codigo_Padrao'] == padrao]
                            
                            for idx, p_row in perguntas_padrao.iterrows():
                                pergunta = p_row['Pergunta']
                                chave_pergunta = f"{cpf}_{padrao}_{idx}"
                                
                                # Busca Memória
                                chave_busca = f"{cpf}_{padrao}_{pergunta}"
                                dados_previos = memoria_respostas.get(chave_busca)
                                
                                index_previo = None
                                obs_previa = ""
                                if dados_previos:
                                    opcoes = ["Conforme", "Não Conforme", "Não se Aplica"]
                                    if dados_previos['resultado'] in opcoes:
                                        index_previo = opcoes.index(dados_previos['resultado'])
                                    obs_previa = dados_previos['obs']
                                    if pd.isna(obs_previa): obs_previa = ""

                                st.write(pergunta)
                                respostas[chave_pergunta] = st.radio(
                                    "Avaliação", ["Conforme", "Não Conforme", "Não se Aplica"], 
                                    key=chave_pergunta, horizontal=True, label_visibility="collapsed", index=index_previo
                                )
                                obs = st.text_input("Observação", value=obs_previa, key=f"obs_{chave_pergunta}")
                                st.markdown("---")

                        submit = st.form_submit_button("💾 Salvar/Atualizar")
                        
                        if submit:
                            data_hora = obter_hora_brasilia()
                            itens_salvos = 0
                            for chave, resultado in respostas.items():
                                if resultado is not None:
                                    _, padrao_ref, idx_ref = chave.split('_', 2)
                                    obs_ref = st.session_state[f"obs_{chave}"]
                                    try:
                                        pergunta_texto = df_perguntas.loc[int(idx_ref), 'Pergunta']
                                    except:
                                        pergunta_texto = "Pergunta não localizada"

                                    st.session_state['resultados'] = [
                                        r for r in st.session_state['resultados'] 
                                        if not (str(r['CPF']).strip() == cpf and str(r['Padrao']).strip() == padrao_ref and str(r['Pergunta']).strip() == pergunta_texto)
                                    ]
                                    st.session_state['resultados'].append({
                                        "Data": data_hora, "Filial": filial_selecionada, "Funcionario": nome, "CPF": cpf,
                                        "Padrao": padrao_ref, "Pergunta": pergunta_texto, "Resultado": resultado, "Observacao": obs_ref
                                    })
                                    itens_salvos += 1
                            if itens_salvos > 0:
                                st.success(f"Dados salvos!")
                                st.rerun()

    # --- DOWNLOAD E LIMPEZA ---
    st.markdown("---")
    st.header("📂 Gestão de Resultados")
    
    col_download, col_limpar = st.columns([3, 1])

    if st.session_state['resultados']:
        df_export = pd.DataFrame(st.session_state['resultados'])
        
        with col_download:
            st.dataframe(df_export, height=200)
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_export.to_excel(writer, index=False)
            file_name_date = obter_hora_brasilia().replace("/","-").replace(":", "h").replace(" ", "_")
            st.download_button(
                "📥 Baixar Excel Completo (Backup)", data=output.getvalue(),
                file_name=f"Auditoria_DTO01_{file_name_date}.xlsx", mime="application/vnd.ms-excel"
            )
        
        with col_limpar:
            st.write("")
            st.write("")
            if st.button("🗑️ LIMPAR Histórico", type="primary"):
                st.session_state['resultados'] = []
                st.rerun()

else:
    st.info("👈 Carregue a Base de Dados na barra lateral.")
