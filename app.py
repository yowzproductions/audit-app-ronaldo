import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
import os
import pytz

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="DTO 01 - DCS 2025", 
    page_icon="🏢", 
    layout="wide"
)

# --- 2. INICIALIZAÇÃO DE MEMÓRIA ---
if 'resultados' not in st.session_state:
    st.session_state['resultados'] = []

if 'pagina_atual' not in st.session_state:
    st.session_state['pagina_atual'] = 0

if 'auditor_logado' not in st.session_state:
    st.session_state['auditor_logado'] = None

# --- 3. FUNÇÕES AUXILIARES ---
def obter_hora_brasilia():
    fuso = pytz.timezone('America/Sao_Paulo')
    return datetime.now(fuso).strftime("%d/%m/%Y %H:%M")

# --- 4. BARRA LATERAL ---
st.sidebar.header("1. Configuração")

# Logo
if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", use_container_width=True)
else:
    st.sidebar.write("🏢 DTO 01 - DCS 2025")

# Upload Base de Dados
uploaded_file = st.sidebar.file_uploader("Base (Excel)", type=["xlsx"], key="base")

# Upload Histórico (Múltiplos Arquivos)
uploaded_hist = st.sidebar.file_uploader(
    "Carregar Histórico (Opcional)", 
    type=["xlsx"], 
    key="hist", 
    accept_multiple_files=True
)

# Processamento do Histórico
if uploaded_hist and not st.session_state['resultados']:
    lista_dfs = []
    try:
        for arquivo in uploaded_hist:
            df_temp = pd.read_excel(arquivo)
            # Limpa nomes das colunas
            df_temp.columns = [c.strip() for c in df_temp.columns]
            
            # Converte colunas chave para texto
            colunas_texto = ['CPF', 'Padrao', 'Pergunta', 'Auditor_CPF']
            for col in colunas_texto:
                if col in df_temp.columns:
                    df_temp[col] = df_temp[col].astype(str).str.strip()
            
            lista_dfs.append(df_temp)

        if lista_dfs:
            df_final = pd.concat(lista_dfs, ignore_index=True)
            st.session_state['resultados'] = df_final.to_dict('records')
            qtd_regs = len(st.session_state['resultados'])
            st.sidebar.success(f"📦 Consolidado: {qtd_regs} registros.")
            
    except Exception as e:
        st.sidebar.error(f"Erro ao ler histórico: {e}")

# Lógica de Login do Auditor
df_auditores = None
auditor_valido = None

if uploaded_file:
    try:
        xls = pd.ExcelFile(uploaded_file)
        if 'Cadastro_Auditores' in xls.sheet_names:
            df_auditores = pd.read_excel(uploaded_file, sheet_name='Cadastro_Auditores')
            df_auditores['CPF_Auditor'] = df_auditores['CPF_Auditor'].astype(str).str.strip()
            
            st.sidebar.markdown("---")
            cpf_digitado = st.sidebar.text_input("Seu CPF (Login)", type="password")
            
            if cpf_digitado:
                busca = df_auditores[df_auditores['CPF_Auditor'] == cpf_digitado.strip()]
                if not busca.empty:
                    auditor_valido = {
                        'Nome': busca.iloc[0]['Nome_Auditor'], 
                        'CPF': cpf_digitado
                    }
                    st.sidebar.success(f"Olá, {auditor_valido['Nome']}!")
                else:
                    st.sidebar.error("CPF não encontrado.")
        else:
            # Modo sem cadastro (liberado)
            auditor_valido = {'Nome': 'Geral', 'CPF': '000'}
            
    except Exception as e:
        st.sidebar.warning(f"Aviso Login: {e}")

st.sidebar.markdown("---")
pagina = st.sidebar.radio("Navegação:", ["📝 Execução da Auditoria", "📊 Painel Gerencial"])

# --- 5. LEITURA DA BASE PRINCIPAL ---
df_treinos = pd.DataFrame()
df_perguntas = pd.DataFrame()
dados_ok = False

if uploaded_file:
    try:
        df_treinos = pd.read_excel(uploaded_file, sheet_name='Base_Treinamentos')
        df_perguntas = pd.read_excel(uploaded_file, sheet_name='Padroes_Perguntas')
        
        # Blindagem de Tipos (Força Texto)
        if 'CPF' in df_treinos.columns:
            df_treinos['CPF'] = df_treinos['CPF'].astype(str).str.strip()
        if 'Codigo_Padrao' in df_treinos.columns:
            df_treinos['Codigo_Padrao'] = df_treinos['Codigo_Padrao'].astype(str).str.strip()
            
        if 'Codigo_Padrao' in df_perguntas.columns:
            df_perguntas['Codigo_Padrao'] = df_perguntas['Codigo_Padrao'].astype(str).str.strip()
        if 'Pergunta' in df_perguntas.columns:
            df_perguntas['Pergunta'] = df_perguntas['Pergunta'].astype(str).str.strip()
            
        dados_ok = True
    except Exception as e:
        st.error(f"Erro ao ler abas do Excel: {e}")
        # ================= PÁGINA 1: EXECUÇÃO =================
if pagina == "📝 Execução da Auditoria":
    
    if not dados_ok:
        st.info("👈 Por favor, carregue a Base de Dados na barra lateral.")
    elif df_auditores is not None and auditor_valido is None:
        st.warning("🔒 ACESSO BLOQUEADO: Identifique-se na barra lateral.")
    else:
        st.title("📝 Execução da Auditoria")
        
        # Filtros
        st.sidebar.header("Filtros Execução")
        
        lista_filiais = df_treinos['Filial'].dropna().unique()
        if st.sidebar.checkbox("Todas as Filiais"):
            filiais_sel = list(lista_filiais)
        else:
            filiais_sel = st.sidebar.multiselect("Filiais", lista_filiais)
        
        lista_padroes = df_perguntas['Codigo_Padrao'].dropna().unique()
        if st.sidebar.checkbox("Todos os Padrões"):
            padroes_sel = list(lista_padroes)
        else:
            padroes_sel = st.sidebar.multiselect("Padrões", lista_padroes)

        if filiais_sel and padroes_sel:
            # Filtra a base
            df_match = df_treinos[
                (df_treinos['Filial'].isin(filiais_sel)) & 
                (df_treinos['Codigo_Padrao'].isin(padroes_sel))
            ]
            
            if df_match.empty:
                st.warning("Nenhum funcionário encontrado para estes filtros.")
            else:
                # Ranking
                ranking = df_match.groupby(['CPF','Nome_Funcionario','Filial']).size().reset_index(name='Qtd')
                ranking = ranking.sort_values(by=['Qtd','Filial'], ascending=[False,True])
                
                # Paginação
                total_p = (len(ranking)-1)//10 + 1
                
                c1, c2, c3 = st.columns([1,3,1])
                with c1:
                    if st.button("⬅️ Anterior") and st.session_state['pagina_atual'] > 0:
                        st.session_state['pagina_atual'] -= 1
                        st.rerun()
                with c3:
                    if st.button("Próximo ➡️") and st.session_state['pagina_atual'] < total_p - 1:
                        st.session_state['pagina_atual'] += 1
                        st.rerun()
                with c2:
                    st.markdown(f"<div style='text-align:center'>Pág {st.session_state['pagina_atual']+1}/{total_p}</div>", unsafe_allow_html=True)
                
                inicio = st.session_state['pagina_atual'] * 10
                fim = inicio + 10
                ranking_pagina = ranking.iloc[inicio:fim]
                
                # Memória Rápida
                memoria = {}
                for r in st.session_state['resultados']:
                    chave = f"{str(r.get('CPF','')).strip()}_{str(r.get('Padrao','')).strip()}_{str(r.get('Pergunta','')).strip()}"
                    memoria[chave] = {'res': r.get('Resultado'), 'obs': r.get('Observacao')}
                
                # Renderiza Cards
                for _, row in ranking_pagina.iterrows():
                    cpf = row['CPF']
                    nome = row['Nome_Funcionario']
                    filial = row['Filial']
                    
                    respondidos = sum(1 for r in st.session_state['resultados'] if str(r.get('CPF','')).strip() == cpf)
                    icon = "🟢" if respondidos > 0 else "⚪"
                    
                    with st.expander(f"{icon} {nome} | {filial}"):
                        padroes_func = df_match[df_match['CPF'] == cpf]['Codigo_Padrao'].unique()
                        
                        with st.form(key=f"f_{cpf}"):
                            respostas_temp = {}
                            obs_temp = {}
                            
                            for pad in padroes_func:
                                st.markdown(f"**--- Padrão {pad} ---**")
                                perguntas_do_padrao = df_perguntas[df_perguntas['Codigo_Padrao'] == pad]
                                
                                for idx, p_row in perguntas_do_padrao.iterrows():
                                    texto_perg = p_row['Pergunta']
                                    key_widget = f"{cpf}_{pad}_{idx}"
                                    key_busca = f"{cpf}_{pad}_{texto_perg}"
                                    
                                    # Recupera dados
                                    dados_antigos = memoria.get(key_busca)
                                    idx_radio = None
                                    val_obs = ""
                                    
                                    if dados_antigos:
                                        opcoes = ["Conforme", "Não Conforme", "Não se Aplica"]
                                        if dados_antigos['res'] in opcoes:
                                            idx_radio = opcoes.index(dados_antigos['res'])
                                        val_obs = dados_antigos['obs'] if dados_antigos['obs'] else ""
                                    
                                    st.write(texto_perg)
                                    respostas_temp[key_widget] = st.radio(
                                        "R", 
                                        ["Conforme", "Não Conforme", "Não se Aplica"], 
                                        key=key_widget, 
                                        horizontal=True, 
                                        index=idx_radio, 
                                        label_visibility="collapsed"
                                    )
                                    obs_temp[key_widget] = st.text_input("Obs", value=val_obs, key=f"obs_{key_widget}")
                                    st.markdown("---")
                            
                            # Botão Salvar
                            if st.form_submit_button("💾 Salvar"):
                                hora_agora = obter_hora_brasilia()
                                cont_salvos = 0
                                
                                for k, val_res in respostas_temp.items():
                                    if val_res:
                                        _, pad_ref, idx_ref = k.split('_', 2)
                                        try:
                                            txt_perg = df_perguntas.loc[int(idx_ref), 'Pergunta']
                                        except:
                                            txt_perg = "Erro"
                                        
                                        # Upsert
                                        st.session_state['resultados'] = [
                                            r for r in st.session_state['resultados'] 
                                            if not (str(r.get('CPF','')).strip() == cpf and 
                                                    str(r.get('Padrao','')).strip() == pad_ref and 
                                                    str(r.get('Pergunta','')).strip() == txt_perg)
                                        ]
                                        
                                        novo_reg = {
                                            "Data": hora_agora,
                                            "Filial": filial,
                                            "Funcionario": nome,
                                            "CPF": cpf,
                                            "Padrao": pad_ref,
                                            "Pergunta": txt_perg,
                                            "Resultado": val_res,
                                            "Observacao": obs_temp.get(k, "")
                                        }
                                        if auditor_valido:
                                            novo_reg["Auditor_Nome"] = auditor_valido['Nome']
                                            novo_reg["Auditor_CPF"] = auditor_valido['CPF']
                                        
                                        st.session_state['resultados'].append(novo_reg)
                                        cont_salvos += 1
                                
                                if cont_salvos > 0:
                                    st.success("Salvo com sucesso!")
                                    st.rerun()

# ================= PÁGINA 2: DASHBOARD =================
elif pagina == "📊 Painel Gerencial":
    st.title("📊 Painel Gerencial")
    
    if not dados_ok:
        st.info("👈 Carregue a Base de Dados.")
    elif not st.session_state['resultados']:
        st.info("Sem dados consolidados.")
    else:
        df_res = pd.DataFrame(st.session_state['resultados'])
        
        # Filtros Dash
        st.sidebar.header("Filtros Dash")
        lista_filiais_dash = df_treinos['Filial'].unique()
        sel_filiais_dash = st.sidebar.multiselect(
            "Filtrar Filiais", 
            lista_filiais_dash, 
            default=lista_filiais_dash
        )
        
        # Detector de Conflitos
        colunas_necessarias = ['CPF','Padrao','Pergunta']
        if all(x in df_res.columns for x in colunas_necessarias):
            duplicatas = df_res[df_res.duplicated(subset=colunas_necessarias, keep=False)]
            if not duplicatas.empty:
                st.error(f"⚠️ {len(duplicatas)} Conflitos encontrados (Duplicidade)!")
                st.dataframe(duplicatas)
            else:
                st.success("✅ Sem conflitos de duplicidade.")
        
        st.markdown("---")
        
        # KPIs
        df_scope = df_treinos[df_treinos['Filial'].isin(sel_filiais_dash)]
        total_pessoas = df_scope['CPF'].nunique()
        
        concluidos = 0
        
        # Filtra resultados
        if 'Filial' in df_res.columns:
            df_res_filt = df_res[df_res['Filial'].isin(sel_filiais_dash)]
        else:
            df_res_filt = pd.DataFrame()
        
        if not df_res_filt.empty and 'CPF' in df_res_filt.columns:
            resps_cpf = df_res_filt.groupby('CPF').size().to_dict()
            meta_pads = df_perguntas.groupby('Codigo_Padrao').size().to_dict()
            
            for cpf in df_scope['CPF'].unique():
                pads = df_scope[df_scope['CPF'] == cpf]['Codigo_Padrao'].unique()
                meta = sum(meta_pads.get(p, 0) for p in pads)
                if resps_cpf.get(cpf, 0) >= meta and meta > 0:
                    concluidos += 1
        
        c1, c2 = st.columns(2)
        c1.metric("Total Pessoas (Filtro)", total_pessoas)
        prog = concluidos / total_pessoas if total_pessoas > 0 else 0
        c2.metric("Concluídos (100%)", f"{concluidos}", f"{int(prog*100)}%")
        st.progress(prog)
        
        # Download
        st.markdown("---")
        b1, b2 = st.columns([3, 1])
        
        out = BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
            df_res.to_excel(writer, index=False)
        
        fname = obter_hora_brasilia().replace("/", "-").replace(":", "h")
        b1.download_button(
            "📥 Baixar Excel Master", 
            out.getvalue(), 
            f"Relatorio_{fname}.xlsx"
        )
        
        if b2.button("🗑️ Limpar"):
            st.session_state['resultados'] = []
            st.rerun()
