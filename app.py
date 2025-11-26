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

# 1. Upload Base
uploaded_file = st.sidebar.file_uploader(
    "Base de Dados (Excel)", 
    type=["xlsx"], 
    key="base"
)

st.sidebar.markdown("---")

# 2. Upload Histórico
uploaded_history = st.sidebar.file_uploader(
    "Carregar Histórico (Opcional)", 
    type=["xlsx"], 
    key="hist"
)

# --- CARREGAMENTO DO HISTÓRICO (Refeito para evitar erros) ---
if uploaded_history is not None and not st.session_state['resultados']:
    try:
        df_hist = pd.read_excel(uploaded_history)
        
        # Tratamento de colunas em linhas separadas para segurança
        if 'CPF' in df_hist.columns:
            df_hist['CPF'] = df_hist['CPF'].astype(str).str.strip()
            
        if 'Padrao' in df_hist.columns:
            df_hist['Padrao'] = df_hist['Padrao'].astype(str).str.strip()
            
        if 'Pergunta' in df_hist.columns:
            df_hist['Pergunta'] = df_hist['Pergunta'].astype(str).str.strip()
            
        st.session_state['resultados'] = df_hist.to_dict('records')
        st.sidebar.success(f"♻️ Histórico: {len(st.session_state['resultados'])} regs.")
    except Exception as e:
        st.sidebar.error(f"Erro histórico: {e}")

# --- NAVEGAÇÃO ---
st.sidebar.markdown("---")
st.sidebar.header("2. Navegação")
pagina = st.sidebar.radio(
    "Ir para:", 
    ["📝 Execução da Auditoria", "📊 Painel Gerencial"]
)

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

    # --- FILTROS GLOBAIS ---
    st.sidebar.header("3. Filtros")
    
    todas_filiais = df_treinos['Filial'].unique()
    usar_todas = st.sidebar.checkbox("Selecionar TODAS as Filiais", value=False)
    
    if usar_todas:
        filiais_selecionadas = todas_filiais
        st.sidebar.info("Modo: Rede Completa")
    else:
        filiais_selecionadas = st.sidebar.multiselect(
            "Selecione as Filiais", 
            todas_filiais
        )
    
    padroes_disponiveis = df_perguntas['Codigo_Padrao'].unique()
    padroes_selecionados = st.sidebar.multiselect(
        "Selecione os Padrões", 
        padroes_disponiveis
    )

    # Verifica filtros
    if len(filiais_selecionadas) > 0 and len(padroes_selecionados) > 0:
        
        df_filial = df_treinos[df_treinos['Filial'].isin(filiais_selecionadas)]
        df_match = df_filial[df_filial['Codigo_Padrao'].isin(padroes_selecionados)]

        ranking = df_match.groupby(
            ['CPF', 'Nome_Funcionario', 'Filial']
        ).size().reset_index(name='Qtd_Padroes')
        
        ranking = ranking.sort_values(
            by=['Qtd_Padroes', 'Filial'], 
            ascending=[False, True]
        )

        # ==========================================
        # PÁGINA 1: EXECUÇÃO
        # ==========================================
        if pagina == "📝 Execução da Auditoria":
            st.title("📝 Execução da Auditoria")
            st.markdown(f"**Escopo:** {len(filiais_selecionadas)} Filiais | {len(padroes_selecionados)} Padrões")
            st.markdown("---")

            if df_match.empty:
                st.warning("Nenhum funcionário encontrado.")
            else:
                st.info(f"Fila: {len(ranking)} funcionários.")
                
                # Memória Rápida
                memoria_respostas = {}
                for item in st.session_state['resultados']:
                    c = str(item['CPF']).strip()
                    p = str(item['Padrao']).strip()
                    q = str(item['Pergunta']).strip()
                    memoria_respostas[f"{c}_{p}_{q}"] = {
                        "resultado": item['Resultado'], 
                        "obs": item['Observacao']
                    }

                # Renderiza Lista
                for index, row in ranking.iterrows():
                    cpf = row['CPF']
                    nome = row['Nome_Funcionario']
                    filial_func = row['Filial']
                    qtd = row['Qtd_Padroes']
                    
                    # Status
                    respondidos = sum(1 for r in st.session_state['resultados'] if str(r['CPF']).strip() == cpf)
                    icon = "🟢" if respondidos > 0 else "⚪"
                    
                    with st.expander(f"{icon} {nome} | {filial_func} (Match: {qtd})"):
                        padroes_func = df_match[df_match['CPF'] == cpf]['Codigo_Padrao'].unique()
                        
                        with st.form(key=f"form_{cpf}"):
                            respostas = {}
                            for padrao in padroes_func:
                                st.markdown(f"**--- Padrão {padrao} ---**")
                                perguntas_padrao = df_perguntas[df_perguntas['Codigo_Padrao'] == padrao]
                                
                                for idx, p_row in perguntas_padrao.iterrows():
                                    pergunta = p_row['Pergunta']
                                    chave_p = f"{cpf}_{padrao}_{idx}"
                                    chave_b = f"{cpf}_{padrao}_{pergunta}"
                                    
                                    # Recuperação
                                    dados = memoria_respostas.get(chave_b)
                                    idx_prev = None
                                    obs_prev = ""
                                    if dados:
                                        opts = ["Conforme", "Não Conforme", "Não se Aplica"]
                                        if dados['resultado'] in opts:
                                            idx_prev = opts.index(dados['resultado'])
                                        obs_prev = dados['obs'] if not pd.isna(dados['obs']) else ""

                                    st.write(pergunta)
                                    respostas[chave_p] = st.radio(
                                        "R", 
                                        ["Conforme", "Não Conforme", "Não se Aplica"], 
                                        key=chave_p, 
                                        horizontal=True, 
                                        label_visibility="collapsed", 
                                        index=idx_prev
                                    )
                                    obs = st.text_input("Obs", value=obs_prev, key=f"obs_{chave_p}")
                                    st.markdown("---")

                            submit = st.form_submit_button("💾 Salvar")
                            
                            if submit:
                                data_hora = obter_hora_brasilia()
                                salvos = 0
                                for k, res in respostas.items():
                                    if res is not None:
                                        _, pad_ref, idx_ref = k.split('_', 2)
                                        obs_ref = st.session_state[f"obs_{k}"]
                                        try: p_txt = df_perguntas.loc[int(idx_ref), 'Pergunta']
                                        except: p_txt = "Erro"

                                        # Upsert
                                        st.session_state['resultados'] = [
                                            r for r in st.session_state['resultados'] 
                                            if not (str(r['CPF']).strip() == cpf and str(r['Padrao']).strip() == pad_ref and str(r['Pergunta']).strip() == p_txt)
                                        ]
                                        st.session_state['resultados'].append({
                                            "Data": data_hora, "Filial": filial_func, 
                                            "Funcionario": nome, "CPF": cpf,
                                            "Padrao": pad_ref, "Pergunta": p_txt, 
                                            "Resultado": res, "Observacao": obs_ref
                                        })
                                        salvos += 1
                                if salvos > 0:
                                    st.success("Salvo!")
                                    st.rerun()

        # ==========================================
        # PÁGINA 2: DASHBOARD
        # ==========================================
        elif pagina == "📊 Painel Gerencial":
            st.title("📊 Painel de Controle")
            st.markdown("---")

            total_funcs = len(ranking)
            
            # Filtra resultados salvos pelos filtros atuais
            auditados_reais = [
                r['CPF'] for r in st.session_state['resultados'] 
                if r['Filial'] in filiais_selecionadas and str(r['Padrao']) in padroes_selecionados
            ]
            unicos = len(set(auditados_reais))
            pendentes = total_funcs - unicos
            prog = unicos / total_funcs if total_funcs > 0 else 0

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("🏢 Filiais", len(filiais_selecionadas))
            c2.metric("👥 Total Pessoas", total_funcs)
            c3.metric("✅ Iniciados", unicos)
            c4.metric("⏳ Pendentes", pendentes, delta_color="inverse")
            
            st.progress(prog, text=f"Progresso: {int(prog*100)}%")

            st.subheader("📉 Status por Filial")
            dados_filial = []
            for filial in filiais_selecionadas:
                meta = df_match[df_match['Filial'] == filial]['CPF'].nunique()
                real = len(set([
                    r['CPF'] for r in st.session_state['resultados'] 
                    if r['Filial'] == filial and str(r['Padrao']) in padroes_selecionados
                ]))
                
                pct = int((real/meta)*100) if meta > 0 else 0
                dados_filial.append({
                    "Filial": filial,
                    "Meta": meta,
                    "Realizado": real,
                    "% Conclusão": f"{pct}%"
                })
            
            st.dataframe(
                pd.DataFrame(dados_filial), 
                use_container_width=True, 
                hide_index=True
            )

            st.markdown("---")
            st.subheader("📂 Exportação")
            
            cd, cc = st.columns([3, 1])
            with cd:
                if st.session_state['resultados']:
                    df_exp = pd.DataFrame(st.session_state['resultados'])
                    out = BytesIO()
                    with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
                        df_exp.to_excel(writer, index=False)
                    
                    fname = obter_hora_brasilia().replace("/", "-")
                    fname = fname.replace(":", "h").replace(" ", "_")
                    
                    st.download_button(
                        "📥 Baixar Relatório Gerencial", 
                        data=out.getvalue(), 
                        file_name=f"Relatorio_DTO01_{fname}.xlsx", 
                        mime="application/vnd.ms-excel"
                    )
                else:
                    st.info("Sem dados.")
            
            with cc:
                if st.button("🗑️ LIMPAR TUDO", type="primary"):
                    st.session_state['resultados'] = []
                    st.rerun()

    else:
        st.info("👈 Selecione Filial e Padrão para começar.")

else:
    st.info("👈 Carregue a Base de Dados.")
