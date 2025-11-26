import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
import os
import pytz # Biblioteca de Fuso Horário

# --- CONFIGURAÇÃO DA PÁGINA (BRANDING DTO 01) ---
st.set_page_config(
    page_title="DTO 01 - DCS 2025", 
    page_icon="🏢", 
    layout="wide"
)

# Inicialização segura da memória
if 'resultados' not in st.session_state:
    st.session_state['resultados'] = []

# --- FUNÇÃO DE HORÁRIO BRASÍLIA ---
def obter_hora_brasilia():
    fuso = pytz.timezone('America/Sao_Paulo')
    return datetime.now(fuso).strftime("%d/%m/%Y %H:%M")

# --- BARRA LATERAL COM LOGO E NOME ---
st.sidebar.header("1. Carga de Dados")

if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", use_container_width=True)
else:
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
                                
                                # Tenta pré-carregar valor se já existir no histórico (Opcional, mas avançado)
                                # Por enquanto mantemos index=None para forçar atenção do auditor
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

                        submit = st.form_submit_button("✅ Salvar/Atualizar Respostas")
                        
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

                                    # --- LÓGICA DE ATUALIZAÇÃO (UPSERT) ---
                                    # Antes de adicionar, removemos qualquer registro anterior 
                                    # que tenha o mesmo CPF, Padrão e Pergunta.
                                    # Isso garante que a informação seja atualizada e não duplicada.
                                    st.session_state['resultados'] = [
                                        r for r in st.session_state['resultados'] 
                                        if not (r['CPF'] == cpf and r['Padrao'] == padrao_ref and r['Pergunta'] == pergunta_texto)
                                    ]

                                    # Adiciona o novo registro (agora limpo)
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
                                st.success(f"{itens_salvos} respostas de {nome} foram salvas/atualizadas!")
                                st.rerun()
                            else:
                                st.warning("Você não selecionou nenhuma resposta.")

    # --- ÁREA DE GESTÃO DE DADOS ---
    st.markdown("---")
    st.header("📂 Gestão de Resultados")
    
    col_download, col_limpar = st.columns([3, 1])

    if st.session_state['resultados']:
        df_export = pd.DataFrame(st.session_state['resultados'])
        
        with col_download:
            st.dataframe(df_export, height=200) # Mostra prévia
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_export.to_excel(writer, index=False, sheet_name='Auditoria')
            
            file_name_date = obter_hora_brasilia().replace("/","-").replace(":", "h").replace(" ", "_")
            st.download_button(
                label="📥 Baixar Excel Completo",
                data=output.getvalue(),
                file_name=f"Auditoria_DTO01_{file_name_date}.xlsx",
                mime="application/vnd.ms-excel"
            )
        
        with col_limpar:
            st.write("") # Espaço para alinhar
            st.write("") 
            # Botão de Limpeza com verificação de segurança (não pede senha, mas exige clique)
            if st.button("🗑️ LIMPAR Histórico", type="primary", help="Apaga todos os dados da sessão atual para começar do zero"):
                st.session_state['resultados'] = []
                st.rerun()
    else:
        st.info("Nenhuma auditoria realizada nesta sessão.")

else:
    st.info("👈 Por favor, carregue o arquivo de dados na barra lateral para começar.")
