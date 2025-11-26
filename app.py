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

# 1. Base (Obrigatória)
uploaded_file = st.sidebar.file_uploader("1º Passo: Base de Dados (Excel)", type=["xlsx"], key="base")

# 2. Histórico (Opcional)
st.sidebar.markdown("---")
st.sidebar.markdown("**Vai continuar uma auditoria anterior?**")
uploaded_history = st.sidebar.file_uploader("2º Passo: Carregar Histórico (Opcional)", type=["xlsx"], key="hist")

# --- LÓGICA DE CARREGAMENTO DO HISTÓRICO (CORRIGIDA) ---
if uploaded_history is not None and not st.session_state['resultados']:
    try:
        df_hist = pd.read_excel(uploaded_history)
        
        # --- CORREÇÃO DO ERRO (NORMALIZAÇÃO DE TIPOS) ---
        # Força CPF e Padrao a serem texto para bater com a Base de Dados
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
        # Cria chave garantindo que tudo é string e sem espaços extras
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
            ranking = df_match.groupby(['CPF', 'Nome_Funcionario']).size().reset_index(name='Qtd_Padroes')
            ranking = ranking.sort_values(by='Qtd_Padroes', ascending=False)
            
            st.subheader(f"📍 Fila de Auditoria - {filial_selecionada}")
            
            for index, row in ranking.iterrows():
                cpf = row['CPF']
                nome = row['Nome_Funcionario']
                qtd = row['Qtd_Padroes']
                
                # Feedback Visual (Ícone)
                respondidos_count = sum(1 for r in st.session_state['resultados'] if str(r['CPF']).strip() == cpf)
                status_icon = "✅" if respondidos_count > 0 else "👤"
                
                with st.expander(f"{status_icon} {nome} (Match: {qtd} | Respondidos: {respondidos_count})"):
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
                                
                                # Busca na Memória (Usando chaves tratadas)
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
                                    "Avaliação", 
                                    ["Conforme", "Não Conforme", "Não se Aplica"], 
                                    key=chave_pergunta,
                                    horizontal=True,
                                    label_visibility="collapsed",
                                    index=index_previo # Preenchimento automático
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

                                    # UPSERT (Atualização)
                                    # Remove anterior garantindo comparação de string limpa
                                    st.session_state['resultados'] = [
                                        r for r in st.session_state['resultados'] 
                                        if not (str(r['CPF']).strip() == cpf and str(r['Padrao']).strip() == padrao_ref and str(r['Pergunta']).strip() == pergunta_texto)
                                    ]

                                    st.session_state['resultados'].append({
                                        "Data": data_hora,
                                        "Filial": filial_selecionada,
                                        "Funcionario": nome,
                                        "CPF": cpf,
                                        "Padrao": padrao_ref,
                                        "Pergunta": pergunta_texto,
                                        "Resultado": resultado,
                                        "Observacao": obs_ref
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
                "📥 Baixar Excel Completo (Backup)",
                data=output.getvalue(),
                file_name=f"Auditoria_DTO01_{file_name_date}.xlsx",
                mime="application/vnd.ms-excel"
            )
        
        with col_limpar:
            st.write("")
            st.write("")
            if st.button("🗑️ LIMPAR Histórico", type="primary"):
                st.session_state['resultados'] = []
                st.rerun()

else:
    st.info("👈 Carregue a Base de Dados na barra lateral.")
