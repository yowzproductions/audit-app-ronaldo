import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
import os

# --- CONFIGURAÇÃO DA PÁGINA (BRANDING DTO 01) ---
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
            st.warning("Nenhum funcionário nesta filial possui treinamento nos padrões selecionados.")
        else:
            # Ranking
            ranking = df_match.groupby(['CPF', 'Nome_Funcionario']).size().reset_index(name='Qtd_Padroes')
            ranking = ranking.sort_values(by='Qtd_Padroes', ascending=False)
            
            st.subheader(f"📍 Fila de Auditoria - {filial_selecionada}")
            st.info(f"Encontramos {len(ranking)} funcionários aptos. Clique no nome para abrir a auditoria.")

            # --- RENDERIZAÇÃO DA LISTA ---
            for index, row in ranking.iterrows():
                cpf = row['CPF']
                nome = row['Nome_Funcionario']
                qtd = row['Qtd_Padroes']
                
                with st.expander(f"👤 {nome} (Coincidência de Padrões: {qtd})"):
                    st.write(f"**CPF:** {cpf}")
                    
                    padroes_do_funcionario = df_match[df_match['CPF'] == cpf]['Codigo_Padrao'].unique()
                    lista_padroes = ", ".join([str(p) for p in padroes_do_funcionario])
                    st.write(f"**Padrões a auditar:** {lista_padroes}")
                    
                    with st.form(key=f"form_{cpf}"):
                        respostas = {}
                        
                        for padrao in padroes_do_funcionario:
                            st.markdown(f"**--- Padrão {padrao} ---**")
                            perguntas_padrao = df_perguntas[df_perguntas['Codigo_Padrao'] == padrao]
                            
                            for idx, p_row in perguntas_padrao.iterrows():
                                pergunta = p_row['Pergunta']
                                chave_pergunta = f"{cpf}_{padrao}_{idx}"
                                
                                st.write(pergunta)
                                
                                # Começa vazio (index=None)
                                respostas[chave_pergunta] = st.radio(
                                    "Avaliação", 
                                    ["Conforme", "Não Conforme", "Não se Aplica"], 
                                    key=chave_pergunta,
                                    horizontal=True,
                                    label_visibility="collapsed",
                                    index=None 
                                )
                                obs = st.text_input("Observação", key=f"obs_{chave_pergunta}")
                                st.markdown("---")

                        submit = st.form_submit_button("✅ Salvar Respostas Preenchidas")
                        
                        if submit:
                            data_hora = datetime.now().strftime("%d/%m/%Y %H:%M")
                            itens_salvos = 0
                            
                            for chave, resultado in respostas.items():
                                if resultado is not None:
                                    _, padrao_ref, idx_ref = chave.split('_', 2)
                                    obs_ref = st.session_state[f"obs_{chave}"]
                                    try:
                                        pergunta_texto = df_perguntas.loc[int(idx_ref), 'Pergunta']
                                    except:
                                        pergunta_texto = "Pergunta não localizada"

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
                                st.success(f"{itens_salvos} respostas de {nome} foram salvas!")
                                st.rerun()
                            else:
                                st.warning("Você não selecionou nenhuma resposta. Nada foi salvo.")

    # --- DOWNLOAD ---
    st.markdown("---")
    st.header("📂 Exportar Resultados")
    
    if st.session_state['resultados']:
        df_export = pd.DataFrame(st.session_state['resultados'])
        st.dataframe(df_export)
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_export.to_excel(writer, index=False, sheet_name='Auditoria')
        
        st.download_button(
            label="📥 Baixar Planilha de Resultados",
            data=output.getvalue(),
            file_name="resultado_DTO01_DCS.xlsx",
            mime="application/vnd.ms-excel"
        )
    else:
        st.info("Nenhuma auditoria realizada ainda.")

else:
    st.info("👈 Por favor, carregue o arquivo de dados na barra lateral para começar.")
