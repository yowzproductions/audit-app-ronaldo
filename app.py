import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="AuditFlow IA", layout="wide")

st.title("🛡️ AuditFlow - Gestão de Conformidade")
st.markdown("---")

# --- PASSO 1: CARREGAR DADOS ---
st.sidebar.header("1. Carga de Dados")
uploaded_file = st.sidebar.file_uploader("Suba o arquivo Excel (dados_auditoria.xlsx)", type=["xlsx"])

if uploaded_file:
    # Lendo as abas do Excel
    try:
        df_treinos = pd.read_excel(uploaded_file, sheet_name='Base_Treinamentos')
        df_perguntas = pd.read_excel(uploaded_file, sheet_name='Padroes_Perguntas')
        
        # Converter CPF para texto para evitar erros
        df_treinos['CPF'] = df_treinos['CPF'].astype(str)
        
        st.sidebar.success("Dados carregados com sucesso!")
    except Exception as e:
        st.error(f"Erro ao ler o arquivo: {e}. Verifique se as abas 'Base_Treinamentos' e 'Padroes_Perguntas' existem.")
        st.stop()

    # --- PASSO 2: FILTROS DO AUDITOR ---
    st.sidebar.header("2. Configuração da Auditoria")
    
    # Filtro de Filial
    filiais = df_treinos['Filial'].unique()
    filial_selecionada = st.sidebar.selectbox("Selecione a Filial", filiais)
    
    # Filtro de Padrões (Multiselect)
    padroes_disponiveis = df_perguntas['Codigo_Padrao'].unique()
    padroes_selecionados = st.sidebar.multiselect("Quais padrões você vai auditar hoje?", padroes_disponiveis)

    if filial_selecionada and padroes_selecionados:
        
        # --- LÓGICA DE RANKING (A MÁGICA DO AION) ---
        
        # 1. Filtra funcionários da filial
        df_filial = df_treinos[df_treinos['Filial'] == filial_selecionada]
        
        # 2. Filtra apenas os treinamentos que correspondem aos padrões selecionados pelo auditor
        df_match = df_filial[df_filial['Codigo_Padrao'].isin(padroes_selecionados)]
        
        if df_match.empty:
            st.warning("Nenhum funcionário nesta filial possui treinamento nos padrões selecionados.")
        else:
            # 3. Conta quantos padrões cada funcionário tem (Ranking)
            ranking = df_match.groupby(['CPF', 'Nome_Funcionario']).size().reset_index(name='Qtd_Padroes')
            ranking = ranking.sort_values(by='Qtd_Padroes', ascending=False)
            
            st.subheader(f"📍 Fila de Auditoria - {filial_selecionada}")
            st.info(f"Encontramos {len(ranking)} funcionários aptos para os padrões selecionados.")

            # --- CRIAÇÃO DA LISTA DE RESULTADOS ---
            if 'resultados' not in st.session_state:
                st.session_state['resultados'] = []

            # --- RENDERIZAÇÃO DOS CARTÕES DE FUNCIONÁRIOS ---
            for index, row in ranking.iterrows():
                cpf = row['CPF']
                nome = row['Nome_Funcionario']
                qtd = row['Qtd_Padroes']
                
                # Cria um expansor para cada funcionário (Cartão)
                with st.expander(f"👤 {nome} (Coincidência de Padrões: {qtd})"):
                    st.write(f"**CPF:** {cpf}")
                    
                    # Descobre quais padrões esse funcionário específico tem DENTRO da seleção do auditor
                    padroes_do_funcionario = df_match[df_match['CPF'] == cpf]['Codigo_Padrao'].unique()
                    
                    st.write(f"**Padrões a auditar:** {', '.join(padroes_do_funcionario)}")
                    
                    # Formulário de Perguntas
                    with st.form(key=f"form_{cpf}"):
                        respostas = {}
                        
                        for padrao in padroes_do_funcionario:
                            st.markdown(f"**--- Padrão {padrao} ---**")
                            # Pega as perguntas deste padrão
                            perguntas_padrao = df_perguntas[df_perguntas['Codigo_Padrao'] == padrao]
                            
                            for idx, p_row in perguntas_padrao.iterrows():
                                pergunta = p_row['Pergunta']
                                chave_pergunta = f"{cpf}_{padrao}_{idx}"
                                
                                col1, col2 = st.columns([3, 2])
                                with col1:
                                    st.write(pergunta)
                                with col2:
                                    respostas[chave_pergunta] = st.radio(
                                        "Resultado", 
                                        ["Conforme", "Não Conforme", "Não se Aplica"], 
                                        key=chave_pergunta,
                                        horizontal=True,
                                        label_visibility="collapsed"
                                    )
                                    # Campo condicional de justificativa
                                    obs = st.text_input("Observação (Obrigatório se Não Conforme)", key=f"obs_{chave_pergunta}")

                        # Botão de Salvar para este funcionário
                        submit = st.form_submit_button("✅ Finalizar Auditoria de " + nome)
                        
                        if submit:
                            # Processa as respostas
                            data_hora = datetime.now().strftime("%d/%m/%Y %H:%M")
                            for chave, resultado in respostas.items():
                                # Recupera dados da chave
                                _, padrao_ref, idx_ref = chave.split('_', 2)
                                obs_ref = st.session_state[f"obs_{chave}"]
                                pergunta_texto = df_perguntas.loc[int(idx_ref), 'Pergunta']
                                
                                # Salva na memória
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
                            st.success(f"Auditoria de {nome} salva com sucesso!")

    # --- ÁREA DE DOWNLOAD ---
    st.markdown("---")
    st.header("📂 Exportar Resultados")
    
    if st.session_state['resultados']:
        df_export = pd.DataFrame(st.session_state['resultados'])
        st.dataframe(df_export) # Mostra prévia
        
        # Converte para Excel em memória
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_export.to_excel(writer, index=False, sheet_name='Auditoria')
        
        st.download_button(
            label="📥 Baixar Planilha de Resultados",
            data=output.getvalue(),
            file_name="resultado_auditoria.xlsx",
            mime="application/vnd.ms-excel"
        )
    else:
        st.info("Nenhuma auditoria realizada ainda.")

else:
    st.info("👈 Por favor, carregue o arquivo de dados na barra lateral para começar.")
