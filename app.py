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

# 2. Login do Auditor (Lógica de Segurança)
df_auditores = None
auditor_validado = None

if uploaded_file:
    try:
        # Tenta ler a aba de auditores
        df_auditores = pd.read_excel(uploaded_file, sheet_name='Cadastro_Auditores')
        df_auditores['CPF_Auditor'] = df_auditores['CPF_Auditor'].astype(str).str.strip()
        
        st.sidebar.markdown("---")
        st.sidebar.subheader("🔐 Identificação")
        cpf_input = st.sidebar.text_input("Digite seu CPF (apenas números)", type="password")
        
        if cpf_input:
            # Verifica se existe
            auditor_encontrado = df_auditores[df_auditores['CPF_Auditor'] == cpf_input.strip()]
            
            if not auditor_encontrado.empty:
                nome_auditor = auditor_encontrado.iloc[0]['Nome_Auditor']
                auditor_validado = {'Nome': nome_auditor, 'CPF': cpf_input}
                st.sidebar.success(f"Olá, {nome_auditor}!")
            else:
                st.sidebar.error("CPF não autorizado.")
    except Exception as e:
        # Se a aba não existir, avisa mas não trava o app (modo legado)
        st.sidebar.warning("Aba 'Cadastro_Auditores' não encontrada no Excel.")

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

# --- LÓGICA PRINCIPAL ---
if uploaded_file:
    try:
        df_treinos = pd.read_excel(uploaded_file, sheet_name='Base_Treinamentos')
        df_perguntas = pd.read_excel(uploaded_file, sheet_name='Padroes_Perguntas')
        
        # Blindagem
        df_treinos['CPF'] = df_treinos['CPF'].astype(str).str.strip()
        df_treinos['Codigo_Padrao'] = df_treinos['Codigo_Padrao'].astype(str).str.strip()
        df_perguntas['Codigo_Padrao'] = df_perguntas['Codigo_Padrao'].astype(str).str.strip()
        df_perguntas['Pergunta'] = df_perguntas['Pergunta'].astype(str).str.strip()
        
    except Exception as e:
        st.error(f"Erro na Base de Dados: {e}")
        st.stop()

    # --- FILTROS ---
    st.sidebar.header("3. Filtros")
    todas_filiais = df_treinos['Filial'].dropna().unique()
    if st.sidebar.checkbox("Todas as Filiais", value=False):
        filiais_selecionadas = list(todas_filiais)
    else:
        filiais_selecionadas = st.sidebar.multiselect("Selecione Filiais", todas_filiais)
    
    padroes_disponiveis = df_perguntas['Codigo_Padrao'].dropna().unique()
    if st.sidebar.checkbox("Todos os Padrões", value=False):
        padroes_selecionados = list(padroes_disponiveis)
    else:
        padroes_selecionados = st.sidebar.multiselect("Selecione Padrões", padroes_disponiveis)

    # Processamento
    if len(filiais_selecionadas) > 0 and len(padroes_selecionados) > 0:
        
        df_match = df_treinos[
            (df_treinos['Filial'].isin(filiais_selecionadas)) & 
            (df_treinos['Codigo_Padrao'].isin(padroes_selecionados))
        ]

        ranking = df_match.groupby(['CPF', 'Nome_Funcionario', 'Filial']).size().reset_index(name='Qtd_Padroes')
        ranking = ranking.sort_values(by=['Qtd_Padroes', 'Filial'], ascending=[False, True])

        # Mapa de Perguntas
        mapa_perguntas = {}
        for padrao in padroes_selecionados:
            perguntas = df_perguntas[df_perguntas['Codigo_Padrao'] == padrao]
            mapa_perguntas[padrao] = list(zip(perguntas.index, perguntas['Pergunta']))

        # =========================================================
        # PÁGINA 1: EXECUÇÃO (BLOQUEADA SE NÃO TIVER LOGIN)
        # =========================================================
        if pagina == "📝 Execução da Auditoria":
            st.title("📝 Execução da Auditoria")
            
            # TRAVA DE SEGURANÇA
            if auditor_validado is None:
                st.warning("🔒 ACESSO BLOQUEADO: Por favor, identifique-se com seu CPF na barra lateral para iniciar.")
                st.stop()
            
            st.markdown(f"**Auditor Responsável:** {auditor_validado['Nome']} | **Escopo:** {len(filiais_selecionadas)} Filiais")
            st.markdown("---")

            if df_match.empty:
                st.warning("Nenhum funcionário encontrado.")
            else:
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

                for idx, row in ranking_pagina.iterrows():
                    cpf = row['CPF']
                    nome = row['Nome_Funcionario']
                    filial = row['Filial']
                    qtd_pads = row['Qtd_Padroes']
                    
                    resps_salvas = sum(1 for r in st.session_state['resultados'] if str(r.get('CPF','')).strip() == cpf)
                    
                    icon = "⚪" if resps_salvas == 0 else "🟢"
                    
                    with st.expander(f"{icon} {nome} | {filial}"):
                        pads_func = df_match[df_match['CPF'] == cpf]['Codigo_Padrao'].unique()
                        
                        with st.form(key=f"form_{cpf}"):
                            respostas_form = {}
                            for padrao in pads_func:
                                st.markdown(f"**--- Padrão {padrao} ---**")
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

                            if st.form_submit_button("💾 Salvar"):
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
                                        # ADICIONA RASTREABILIDADE
                                        st.session_state['resultados'].append({
                                            "Data": data_hora, "Filial": filial, "Funcionario": nome, "CPF": cpf,
                                            "Padrao": pad_ref, "Pergunta": p_txt, "Resultado": res, "Observacao": obs_ref,
                                            "Auditor_Nome": auditor_validado['Nome'], "Auditor_CPF": auditor_validado['CPF']
                                        })
                                        salvos += 1
                                if salvos > 0:
                                    st.success("Salvo com sucesso!")
                                    st.rerun()

        # =========================================================
        # PÁGINA 2: DASHBOARD E DETECTOR DE CONFLITOS
        # =========================================================
        elif pagina == "📊 Painel Gerencial":
            st.title("📊 Painel Gerencial & Rastreabilidade")
            
            if not st.session_state['resultados']:
                st.info("Sem dados consolidados.")
            else:
                df_resultados = pd.DataFrame(st.session_state['resultados'])
                
                # --- DETECTOR DE CONFLITOS ---
                st.markdown("### 🕵️ Auditoria de Conflitos")
                
                # Agrupa por Funcionário+Pergunta e vê se tem mais de uma entrada
                # (Nota: O sistema de execução já faz Upsert, mas ao consolidar múltiplos arquivos
                # de auditores diferentes, podem aparecer duplicatas reais)
                duplicatas = df_resultados[df_resultados.duplicated(subset=['CPF', 'Padrao', 'Pergunta'], keep=False)]
                
                if not duplicatas.empty:
                    st.error(f"⚠️ ATENÇÃO: Foram encontrados {len(duplicatas)} registros de conflito (mesma pergunta respondida em arquivos diferentes).")
                    
                    # Mostra tabela focada no problema
                    st.dataframe(
                        duplicatas[['Filial', 'Funcionario', 'Padrao', 'Pergunta', 'Resultado', 'Auditor_Nome', 'Data']].sort_values(by=['Funcionario', 'Pergunta']),
                        use_container_width=True
                    )
                    st.markdown("*Dica: Baixe o Excel para tratar esses casos manualmente.*")
                else:
                    st.success("✅ Nenhum conflito de duplicidade detectado na base consolidada.")

                st.markdown("---")
                
                # KPIs Gerais
                st.subheader("📈 Progresso Geral")
                total_pessoas = len(ranking)
                
                # Lógica de Progresso (similar a anterior)
                resultados_escopo = df_resultados[df_resultados['Filial'].isin(filiais_selecionadas)]
                if not resultados_escopo.empty:
                    respostas_por_cpf = resultados_escopo.groupby('CPF').size().to_dict()
                else:
                    respostas_por_cpf = {}
                
                concluidos = 0
                qtd_perguntas_por_padrao = df_perguntas.groupby('Codigo_Padrao').size().to_dict()

                for index, row in ranking.iterrows():
                    cpf = row['CPF']
                    pads_func = df_match[df_match['CPF'] == cpf]['Codigo_Padrao'].unique()
                    meta = sum(qtd_perguntas_por_padrao.get(p, 0) for p in pads_func)
                    if respostas_por_cpf.get(cpf, 0) >= meta and meta > 0:
                        concluidos += 1
                
                prog = concluidos / total_pessoas if total_pessoas > 0 else 0
                st.metric("Taxa de Conclusão (100% Respondido)", f"{int(prog*100)}%", f"{concluidos}/{total_pessoas} Pessoas")
                st.progress(prog)

                # Exportação
                st.markdown("---")
                cd, cc = st.columns([3, 1])
                with cd:
                    out = BytesIO()
                    with pd.ExcelWriter(out, engine='xlsxwriter') as writer: df_resultados.to_excel(writer, index=False)
                    fname = obter_hora_brasilia().replace("/", "-").replace(":", "h").replace(" ", "_")
                    st.download_button("📥 Baixar Excel Consolidado (Com Rastreabilidade)", data=out.getvalue(), file_name=f"Master_{fname}.xlsx", mime="application/vnd.ms-excel")
                with cc:
                    if st.button("🗑️ LIMPAR", type="primary"):
                        st.session_state['resultados'] = []
                        st.rerun()

    else:
        st.info("👈 Selecione filtros.")
else:
    st.info("👈 Carregue a Base de Dados.")
