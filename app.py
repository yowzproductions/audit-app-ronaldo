import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
import os
import pytz

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="DTO 01 - DCS SCANIA", page_icon="🚛", layout="wide")

# --- 2. MEMÓRIA ---
if 'resultados' not in st.session_state: st.session_state['resultados'] = []
if 'pagina_atual' not in st.session_state: st.session_state['pagina_atual'] = 0
if 'auditor_logado' not in st.session_state: st.session_state['auditor_logado'] = None
if 'permissoes' not in st.session_state: 
    st.session_state['permissoes'] = {'filiais': [], 'padroes': [], 'perfil': ''}

# --- 3. FUNÇÕES ---
def obter_hora():
    return datetime.now(pytz.timezone('America/Sao_Paulo')).strftime("%d/%m/%Y %H:%M")

def gerar_excel(df_input):
    out = BytesIO()
    with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
        df_input.to_excel(writer, index=False)
    return out.getvalue()

# --- 4. BARRA LATERAL ---
st.sidebar.header("1. Configuração")
if os.path.exists("logo.png"): st.sidebar.image("logo.png", use_container_width=True)
else: st.sidebar.write("🏢 DTO 01 - DCS SCANIA")

# Uploads
uploaded_file = st.sidebar.file_uploader("Base (Excel)", type=["xlsx"], key="base")
uploaded_hist = st.sidebar.file_uploader("Histórico", type=["xlsx"], key="hist", accept_multiple_files=True)

# Processamento Histórico
if uploaded_hist and not st.session_state['resultados']:
    dfs = []
    try:
        for f in uploaded_hist:
            d = pd.read_excel(f)
            # Limpeza CRÍTICA de colunas e dados
            d.columns = [c.strip() for c in d.columns]
            for c in ['CPF','Padrao','Pergunta','Auditor_CPF','Filial']:
                if c in d.columns: d[c] = d[c].astype(str).str.strip()
            dfs.append(d)
        if dfs:
            st.session_state['resultados'] = pd.concat(dfs, ignore_index=True).to_dict('records')
            st.sidebar.success(f"📦 Consolidado: {len(st.session_state['resultados'])} regs")
    except Exception as e: st.sidebar.error(f"Erro Histórico: {e}")

# --- LOGIN (SEGURANÇA REFORÇADA) ---
df_auditores = None

if uploaded_file:
    try:
        xls = pd.ExcelFile(uploaded_file)
        if 'Cadastro_Auditores' in xls.sheet_names:
            df_auditores = pd.read_excel(uploaded_file, sheet_name='Cadastro_Auditores')
            df_auditores['CPF_Auditor'] = df_auditores['CPF_Auditor'].astype(str).str.strip()
            
            st.sidebar.markdown("---")
            
            if st.session_state['auditor_logado']:
                st.sidebar.success(f"👤 {st.session_state['auditor_logado']['Nome']}")
                if st.sidebar.button("Sair"):
                    st.session_state['auditor_logado'] = None
                    st.session_state['permissoes'] = {'filiais': [], 'padroes': [], 'perfil': ''}
                    st.rerun()
            else:
                st.sidebar.subheader("🔐 Acesso Restrito")
                cpf = st.sidebar.text_input("CPF (Apenas números)", type="password")
                if st.sidebar.button("Entrar"):
                    match = df_auditores[df_auditores['CPF_Auditor']==cpf.strip()]
                    if not match.empty:
                        user_data = match.iloc[0]
                        
                        # Processa Permissões
                        raw_fil = str(user_data.get('Filiais_Permitidas', 'Todas'))
                        if 'todas' in raw_fil.lower(): fils_perm = 'TODAS'
                        else: fils_perm = [x.strip() for x in raw_fil.split(',')]
                            
                        raw_pad = str(user_data.get('Padroes_Permitidos', 'Todos'))
                        if 'todos' in raw_pad.lower() or 'todas' in raw_pad.lower(): pads_perm = 'TODOS'
                        else: pads_perm = [x.strip() for x in raw_pad.split(',')]

                        st.session_state['auditor_logado'] = {'Nome': user_data['Nome_Auditor'], 'CPF': cpf}
                        st.session_state['permissoes'] = {
                            'filiais': fils_perm, 
                            'padroes': pads_perm, 
                            'perfil': str(user_data.get('Perfil', 'Auditor')).strip()
                        }
                        st.rerun()
                    else:
                        st.sidebar.error("CPF não autorizado.")
        else:
            # Modo Legado
            st.session_state['auditor_logado'] = {'Nome': 'Geral', 'CPF': '000'}
            st.session_state['permissoes'] = {'filiais': 'TODAS', 'padroes': 'TODOS', 'perfil': 'Gestor'}
    except Exception as e: st.sidebar.warning(f"Erro Login: {e}")

# Sidebar Download
if st.session_state['resultados']:
    st.sidebar.markdown("---")
    df_dw = pd.DataFrame(st.session_state['resultados'])
    perms = st.session_state['permissoes']
    # Segurança no Download
    if st.session_state['auditor_logado'] and perms.get('perfil') != 'Gestor' and perms.get('filiais') != 'TODAS':
        if 'Filial' in df_dw.columns:
            df_dw = df_dw[df_dw['Filial'].isin(perms['filiais'])]
    
    excel_data = gerar_excel(df_dw)
    if excel_data:
        st.sidebar.download_button("📥 Baixar Meus Dados", excel_data, "Backup_Auditoria.xlsx", mime="application/vnd.ms-excel")

st.sidebar.markdown("---")
pagina = st.sidebar.radio("Menu:", ["📝 EXECUTAR DTO 01", "📊 Painel Gerencial"])

# Leitura Base (Blindada)
df_treinos, df_perguntas, dados_ok = pd.DataFrame(), pd.DataFrame(), False
if uploaded_file:
    try:
        df_treinos = pd.read_excel(uploaded_file, sheet_name='Base_Treinamentos')
        df_perguntas = pd.read_excel(uploaded_file, sheet_name='Padroes_Perguntas')
        
        # Converte tudo para string
        for df in [df_treinos, df_perguntas]:
            for col in df.columns:
                if col in ['CPF', 'Codigo_Padrao', 'Filial', 'Pergunta', 'Nome_Padrao']:
                    df[col] = df[col].astype(str).str.strip()
        dados_ok = True
    except Exception as e: st.error(f"Erro Base: {e}")
        # ================= EXECUÇÃO =================
if pagina == "📝 EXECUTAR DTO 01":
    if not dados_ok: st.info("👈 Carregue a Base.")
    elif df_auditores is not None and st.session_state['auditor_logado'] is None:
        st.warning("🔒 Acesso Bloqueado. Faça login na barra lateral.")
    else:
        st.title("📝 EXECUTAR DTO 01")
        perms = st.session_state['permissoes']
        
        # --- FILTROS COM SEGURANÇA APLICADA ---
        todas_f = sorted(df_treinos['Filial'].dropna().unique())
        if perms['filiais'] == 'TODAS': opts_f = todas_f
        else: opts_f = sorted([f for f in todas_f if f in perms['filiais']])
            
        sel_fil = st.multiselect("Filiais Permitidas", opts_f, default=opts_f if len(opts_f)==1 else None)
        
        todas_p = sorted(df_perguntas['Codigo_Padrao'].dropna().unique())
        if perms['padroes'] == 'TODOS': opts_p = todas_p
        else: opts_p = sorted([p for p in todas_p if str(p) in perms['padroes']])
            
        sel_pad = st.multiselect("Padrões", opts_p, default=opts_p if st.checkbox("Selecionar Todos Padrões") else None)

        if sel_fil and sel_pad:
            df_m = df_treinos[(df_treinos['Filial'].isin(sel_fil)) & (df_treinos['Codigo_Padrao'].isin(sel_pad))]
            
            if df_m.empty: st.warning("Nenhum dado encontrado.")
            else:
                # Mapas e Metas
                mapa_nomes = {}
                if 'Nome_Padrao' in df_perguntas.columns:
                    tn = df_perguntas[['Codigo_Padrao', 'Nome_Padrao']].drop_duplicates()
                    mapa_nomes = pd.Series(tn.Nome_Padrao.values, index=tn.Codigo_Padrao).to_dict()
                
                # Meta por padrão (Qtd Perguntas)
                dict_metas = df_perguntas.groupby('Codigo_Padrao').size().to_dict()

                rank = df_m.groupby(['CPF','Nome_Funcionario','Filial']).size().reset_index(name='Qtd')
                rank = rank.sort_values(by=['Qtd','Filial'], ascending=[False,True])
                
                # Paginação
                tot_p = (len(rank)-1)//10 + 1
                c1,c2,c3 = st.columns([1,3,1])
                if c1.button("⬅️") and st.session_state['pagina_atual']>0: st.session_state['pagina_atual']-=1; st.rerun()
                if c3.button("➡️") and st.session_state['pagina_atual']<tot_p-1: st.session_state['pagina_atual']+=1; st.rerun()
                c2.markdown(f"<div style='text-align:center'>Pág {st.session_state['pagina_atual']+1}/{tot_p}</div>", unsafe_allow_html=True)
                
                pg_rank = rank.iloc[st.session_state['pagina_atual']*10 : (st.session_state['pagina_atual']+1)*10]
                
                # Memória Rápida
                memoria = {}
                for r in st.session_state['resultados']:
                    k = f"{str(r.get('CPF','')).strip()}_{str(r.get('Padrao','')).strip()}_{str(r.get('Pergunta','')).strip()}"
                    memoria[k] = {'res': r.get('Resultado'), 'obs': r.get('Observacao')}
                
                for _, row in pg_rank.iterrows():
                    cpf = str(row['CPF']).strip()
                    nome = row['Nome_Funcionario']
                    filial = row['Filial']
                    
                    # Status
                    pads_cpf = df_m[df_m['CPF']==cpf]['Codigo_Padrao'].unique()
                    meta_tot = sum(dict_metas.get(p,0) for p in pads_cpf)
                    
                    # Realizado (na memória)
                    resp_tot = 0
                    for r in st.session_state['resultados']:
                        if str(r.get('CPF','')).strip() == cpf and str(r.get('Padrao','')).strip() in pads_cpf:
                            resp_tot += 1
                    
                    if resp_tot == 0: icon = "⚪"
                    elif resp_tot >= meta_tot and meta_tot > 0: icon = "🟢"
                    else: icon = "🟡"
                    
                    with st.expander(f"{icon} {nome} | {filial} ({resp_tot}/{meta_tot} Perguntas)"):
                        with st.form(key=f"f_{cpf}"):
                            resps, obss = {}, {}
                            for p in pads_cpf:
                                nome_p = mapa_nomes.get(p, "")
                                st.markdown(f"**{p} - {nome_p}**")
                                pergs = df_perguntas[df_perguntas['Codigo_Padrao']==p]
                                for idx, pr in pergs.iterrows():
                                    txt = pr['Pergunta']
                                    kb = f"{cpf}_{p}_{txt}"
                                    kw = f"{cpf}_{p}_{idx}"
                                    
                                    prev = memoria.get(kb)
                                    idx_r = ["Conforme","Não Conforme","Não se Aplica"].index(prev['res']) if prev and prev['res'] in ["Conforme","Não Conforme","Não se Aplica"] else None
                                    st.write(txt)
                                    resps[kw] = st.radio("R", ["Conforme","Não Conforme","Não se Aplica"], key=kw, horizontal=True, index=idx_r, label_visibility="collapsed")
                                    obss[kw] = st.text_input("Obs", value=(prev['obs'] if prev else ""), key=f"o_{kw}")
                                    st.markdown("---")
                            
                            # BOTÃO ÚNICO DE SALVAR (ROBUSTO)
                            if st.form_submit_button("💾 Salvar Auditoria"):
                                dh = obter_hora()
                                cnt = 0
                                for k, v in resps.items():
                                    if v:
                                        _, pr, ir = k.split('_', 2)
                                        try: pt = df_perguntas.loc[int(ir), 'Pergunta']
                                        except: pt = "Erro"
                                        
                                        # Remove anterior
                                        st.session_state['resultados'] = [r for r in st.session_state['resultados'] if not (str(r.get('CPF','')).strip()==cpf and str(r.get('Padrao','')).strip()==pr and str(r.get('Pergunta','')).strip()==pt)]
                                        
                                        reg = {"Data":dh, "Filial":filial, "Funcionario":nome, "CPF":cpf, "Padrao":pr, "Pergunta":pt, "Resultado":v, "Observacao":obss.get(k,"")}
                                        if st.session_state['auditor_logado']:
                                            reg.update({"Auditor_Nome":st.session_state['auditor_logado']['Nome'], "Auditor_CPF":st.session_state['auditor_logado']['CPF']})
                                        
                                        st.session_state['resultados'].append(reg)
                                        cnt+=1
                                if cnt: st.success("Salvo!"); st.rerun()

# ================= PAINEL =================
elif pagina == "📊 Painel Gerencial":
    st.title("📊 Painel Gerencial")
    if not dados_ok: st.info("👈 Carregue a Base.")
    else:
        perms = st.session_state['permissoes']
        
        # Filtros Dashboard (Com Segurança)
        todas_f = sorted(df_treinos['Filial'].unique())
        if perms['filiais'] == 'TODAS': opts_f = todas_f
        else: opts_f = sorted([f for f in todas_f if f in perms['filiais']])
        
        st.write("Filtros:")
        col_f, col_p = st.columns(2)
        f_sel = col_f.multiselect("Filiais", opts_f, default=opts_f)
        
        todas_p = sorted(df_perguntas['Codigo_Padrao'].unique())
        if perms['padroes'] == 'TODOS': opts_p = todas_p
        else: opts_p = sorted([p for p in todas_p if str(p) in perms['padroes']])
        p_sel = col_p.multiselect("Padrões", opts_p, default=opts_p)
        
        st.markdown("---")
        
        # --- CÁLCULOS (META vs REALIZADO) ---
        # 1. Meta (Escopo)
        df_esc = df_treinos[(df_treinos['Filial'].isin(f_sel)) & (df_treinos['Codigo_Padrao'].isin(p_sel))]
        total_pessoas = df_esc['CPF'].nunique()
        total_vol = len(df_esc)
        
        # 2. Realizado (Memória)
        df_res = pd.DataFrame(st.session_state['resultados'])
        df_rf = pd.DataFrame()
        if not df_res.empty:
            # Filtra resultados pelas filiais/padrões selecionados no dash
            if 'Filial' in df_res.columns and 'Padrao' in df_res.columns:
                df_rf = df_res[(df_res['Filial'].isin(f_sel)) & (df_res['Padrao'].isin(p_sel))]
        
        resps_cpf = {}
        resps_det = {}
        if not df_rf.empty:
            resps_cpf = df_rf.groupby('CPF').size().to_dict()
            resps_det = df_rf.groupby(['CPF', 'Padrao']).size().to_dict()
            
        dict_metas = df_perguntas.groupby('Codigo_Padrao').size().to_dict()
        
        # --- SELETOR ---
        visao = st.radio("Visualização", ["👥 Pessoas", "📏 Padrões (Volume)"], horizontal=True)
        st.markdown("---")

        if visao == "👥 Pessoas":
            counts = {'P':0, 'A':0, 'C':0}
            data_det = []
            
            for cpf in df_esc['CPF'].unique():
                pads = df_esc[df_esc['CPF']==cpf]['Codigo_Padrao'].unique()
                meta = sum(dict_metas.get(p,0) for p in pads)
                real = resps_cpf.get(cpf, 0)
                
                info = df_esc[df_esc['CPF']==cpf].iloc[0]
                
                if real == 0: stts="🔴 Pendente"; counts['P']+=1
                elif real >= meta and meta>0: stts="🟢 Concluído"; counts['C']+=1
                else: stts="🟡 Parcial"; counts['A']+=1
                
                pct = int((real/meta)*100) if meta>0 else 0
                data_det.append({"Filial":info['Filial'], "Nome":info['Nome_Funcionario'], "Status":stts, "Progresso":f"{pct}%"})
            
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Pessoas", total_pessoas)
            c2.metric("Concluídos", counts['C'])
            c3.metric("Parcial", counts['A'])
            c4.metric("Pendentes", counts['P'])
            
            df_d = pd.DataFrame(data_det)
            if not df_d.empty:
                t1,t2,t3 = st.tabs(["🔴","🟡","🟢"])
                with t1: st.dataframe(df_d[df_d['Status'].str.contains("Pendente")], use_container_width=True)
                with t2: st.dataframe(df_d[df_d['Status'].str.contains("Parcial")], use_container_width=True)
                with t3: st.dataframe(df_d[df_d['Status'].str.contains("Concluído")], use_container_width=True)

        else:
            counts_v = {'Z':0, 'I':0, 'C':0}
            vol_data = []
            
            # Itera sobre cada par (Pessoa, Padrão) que deve ser auditado
            for _, r in df_esc.iterrows():
                c, p = r['CPF'], r['Codigo_Padrao']
                meta = dict_metas.get(p, 0)
                real = resps_det.get((c, p), 0)
                
                if real == 0: counts_v['Z']+=1
                elif real >= meta and meta>0: counts_v['C']+=1
                else: counts_v['I']+=1
            
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Volume Total", total_vol)
            c2.metric("Concluídas", counts_v['C'])
            c3.metric("Andamento", counts_v['I'])
            c4.metric("Zero", counts_v['Z'])
            
            # Tabela Agrupada por Padrão
            for p in df_esc['Codigo_Padrao'].unique():
                q_meta = len(df_esc[df_esc['Codigo_Padrao']==p])
                q_ok = 0
                # Verifica quantos concluíram ESTE padrão
                sub = df_esc[df_esc['Codigo_Padrao']==p]
                for c_sub in sub['CPF']:
                    m = dict_metas.get(p,0)
                    r = resps_det.get((c_sub, p), 0)
                    if r >= m and m>0: q_ok += 1
                
                pct = int((q_ok/q_meta)*100) if q_meta>0 else 0
                vol_data.append({"Padrão": p, "Vol": q_meta, "Ok": q_ok, "%": f"{pct}%"})
            
            st.dataframe(pd.DataFrame(vol_data), use_container_width=True)

        st.markdown("---")
        if st.button("🗑️ Limpar Tudo"): st.session_state['resultados']=[]; st.rerun()
        
