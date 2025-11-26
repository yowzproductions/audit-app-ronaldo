import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime

st.set_page_config(page_title="AuditFlow IA", layout="wide")
st.title("🛡️ AuditFlow - Gestão de Conformidade")
st.markdown("---")

st.sidebar.header("1. Carga de Dados")
# Tenta ler o arquivo localmente se o usuário não subir outro
local_file = 'dados_auditoria.xlsx'
uploaded_file = st.sidebar.file_uploader("Suba o arquivo Excel", type=["xlsx"])

df_treinos = None
df_perguntas = None

# Lógica Híbrida: Usa o upload OU o arquivo que já está na pasta
arquivo_para_ler = None
if uploaded_file:
    arquivo_para_ler = uploaded_file
elif os.path.exists(local_file):
    st.sidebar.info(f"Usando arquivo local: {local_file}")
    arquivo_para_ler = local_file

if arquivo_para_ler:
    try:
        df_treinos = pd.read_excel(arquivo_para_ler, sheet_name='Base_Treinamentos')
        df_perguntas = pd.read_excel(arquivo_para_ler, sheet_name='Padroes_Perguntas')
        df_treinos['CPF'] = df_treinos['CPF'].astype(str)
        st.sidebar.success("Dados carregados!")
    except Exception as e:
        st.error(f"Erro ao ler arquivo: {e}")
        st.stop()

    # --- LÓGICA DO APP ---
    st.sidebar.header("2. Configuração")
    filiais = df_treinos['Filial'].unique()
    filial_selecionada = st.sidebar.selectbox("Filial", filiais)
    padroes_disponiveis = df_perguntas['Codigo_Padrao'].unique()
    padroes_selecionados = st.sidebar.multiselect("Padrões a Auditar", padroes_disponiveis)

    if filial_selecionada and padroes_selecionados:
        df_filial = df_treinos[df_treinos['Filial'] == filial_selecionada]
        df_match = df_filial[df_filial['Codigo_Padrao'].isin(padroes_selecionados)]

        if df_match.empty:
            st.warning("Nenhum funcionário encontrado com esses critérios.")
        else:
            ranking = df_match.groupby(['CPF', 'Nome_Funcionario']).size().reset_index(name='Qtd_Padroes')
            ranking = ranking.sort_values(by='Qtd_Padroes', ascending=False)

            st.subheader(f"📍 Fila: {filial_selecionada}")

            if 'resultados' not in st.session_state:
                st.session_state['resultados'] = []

            for index, row in ranking.iterrows():
                cpf = row['CPF']
                nome = row['Nome_Funcionario']
                qtd = row['Qtd_Padroes']

                with st.expander(f"👤 {nome} (Match: {qtd} padrões)"):
                    padroes_do_funcionario = df_match[df_match['CPF'] == cpf]['Codigo_Padrao'].unique()
                    with st.form(key=f"form_{cpf}"):
                        respostas = {}
                        for padrao in padroes_do_funcionario:
                            st.markdown(f"**--- Padrão {padrao} ---**")
                            perguntas_padrao = df_perguntas[df_perguntas['Codigo_Padrao'] == padrao]
                            for idx, p_row in perguntas_padrao.iterrows():
                                p_txt = p_row['Pergunta']
                                k = f"{cpf}_{padrao}_{idx}"
                                st.write(p_txt)
                                respostas[k] = st.radio("R", ["Conforme", "Não Conforme", "N/A"], key=k, horizontal=True)
                                st.text_input("Obs", key=f"obs_{k}")

                        if st.form_submit_button("Salvar Auditoria"):
                            data_hora = datetime.now().strftime("%d/%m/%Y %H:%M")
                            for k, v in respostas.items():
                                _, padrao_ref, idx_ref = k.split('_', 2)
                                obs = st.session_state[f"obs_{k}"]
                                p_orig = df_perguntas.loc[int(idx_ref), 'Pergunta']
                                st.session_state['resultados'].append({
                                    "Data": data_hora, "Filial": filial_selecionada,
                                    "Nome": nome, "Padrao": padrao_ref,
                                    "Pergunta": p_orig, "Resultado": v, "Obs": obs
                                })
                            st.success("Salvo!")

    if st.session_state.get('resultados'):
        st.markdown("---")
        df_export = pd.DataFrame(st.session_state['resultados'])
        st.dataframe(df_export)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_export.to_excel(writer, index=False)
        st.download_button("📥 Baixar Excel", data=output.getvalue(), file_name="auditoria.xlsx")
else:
    st.info("Aguardando arquivo de dados...")
"""

with open("app.py", "w") as f:
    f.write(code)

print("✅ Arquivo do aplicativo criado com sucesso!")
