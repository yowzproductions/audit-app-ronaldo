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
            d.columns = [c.strip() for c in d.columns]
            for c in ['CPF','Padrao','Pergunta','Auditor_CPF']:
                if c in d.columns: d[c] = d[c].astype(str).str.strip()
            dfs.append(d)
        if dfs:
            st.session_state['resultados'] = pd.concat(dfs, ignore_index=True).to_dict('records')
            st.sidebar.success(f"📦 Consolidado: {len(st.session_state['resultados'])} regs")
    except Exception as e: st.sidebar.error(f"Erro Histórico: {e}")

# --- LOGIN COM PERMISSÕES (RBAC CORRIGIDO) ---
df_auditores, auditor_valido = None, None
permissoes = {'filiais': [], 'padroes': [], 'perfil': ''}

if uploaded_file:
    try:
        xls = pd.ExcelFile(uploaded_file)
        if 'Cadastro_Auditores' in xls.sheet_names:
            df_auditores = pd.read_excel(uploaded_file, sheet_name='Cadastro_Auditores')
            df_auditores['CPF_Auditor'] = df_auditores['CPF_Auditor'].astype(str).str.strip()
            
            st.sidebar.markdown("---")
            cpf = st.sidebar.text_input("Login (CPF)", type="password")
            if cpf:
                match = df_auditores[df_auditores['CPF_Auditor']==cpf.strip()]
                if not match.empty:
                    user_data = match.iloc[0]
                    nome_user = user_data['Nome_Auditor']
                    perfil_user = str(user_data.get('Perfil', 'Auditor')).strip()
                    
                    # Processa Filiais (Normalizando espaços)
                    raw_fil = str(user_data.get('Filiais_Permitidas', 'Todas'))
                    if 'todas' in raw_fil.lower():
                        fils_perm = 'TODAS'
                    else:
                        fils_perm = [x.strip() for x in raw_fil.split(',')]
                        
                    # Processa Padrões
                    raw_pad = str(user_data.get('Padroes_Permitidos', 'Todos'))
                    if 'todos' in raw_pad.lower() or 'todas' in raw_pad.lower():
                        pads_perm = 'TODOS'
                    else:
                        pads_perm = [x.strip() for x in raw_pad.split(',')]

                    auditor_valido = {'Nome': nome_user, 'CPF': cpf}
                    permissoes = {'filiais': fils_perm, 'padroes': pads_perm, 'perfil': perfil_user}
                    
                    st.sidebar.success(f"Olá, {nome_user}")
                    # Debug Visual (Para você conferir se ele leu certo)
                    if fils_perm != 'TODAS':
                        st.sidebar.caption(f"Filiais: {', '.join(fils_perm)}")
                else: st.sidebar.error("CPF não cadastrado.")
        else:
            auditor_valido = {'Nome': 'Geral', 'CPF': '000'}
            permissoes = {'filiais': 'TODAS', 'padroes': 'TODOS', 'perfil': 'Gestor'}
    except: pass

# Download Rápido
if st.session_state['resultados']:
    st.sidebar.markdown("---")
    st.sidebar.write("📂 **Exportar**")
    df_dw = pd.DataFrame(st.session_state['resultados'])
    # Filtra download se for auditor
    if auditor_valido and permissoes['perfil'] != 'Gestor' and permissoes['filiais'] != 'TODAS':
        df_dw = df_dw[df_dw['Filial'].isin(permissoes['filiais'])]
    
    excel_data = gerar_excel(df_dw)
    if excel_data:
        st.sidebar.download_button("📥 Baixar Planilha", excel_data, "Backup_Auditoria.xlsx", mime="application/vnd.ms-excel")

st.sidebar.markdown("---")
pagina = st.sidebar.radio("Menu:", ["📝 EXECUTAR DTO 01", "📊 Painel Gerencial"])

# Leitura Base
df_treinos, df_perguntas, dados_ok = pd.DataFrame(), pd.DataFrame(), False
if uploaded_file:
    try:
        df_treinos = pd.read_excel(uploaded_file, sheet_name='Base_Treinamentos')
        df_perguntas = pd.read_excel(uploaded_file, sheet_name='Padroes_Perguntas')
        for df in [df_treinos, df_perguntas]:
            if 'CPF' in df.columns: df['CPF'] = df['CPF'].astype(str).str.strip()
            if 'Codigo_Padrao' in df.columns: df['Codigo_Padrao'] = df['Codigo_Padrao'].astype(str).str.strip()
        if 'Pergunta' in df_perguntas.columns: df_perguntas['Pergunta'] = df_perguntas['Pergunta'].astype(str).str.strip()
        if 'Nome_Padrao' in df_perguntas.columns: df_perguntas['Nome_Padrao'] = df_perguntas['Nome_Padrao'].astype(str).str.strip()
        
        # Normaliza Filiais para bater com cadastro
        if 'Filial' in df_treinos.columns:
            df_treinos['Filial'] = df_treinos['Filial'].str.strip()
            
        dados_ok = True
    except Exception as e: st.error(f"Erro Base: {e}")
        # ================= EXECUÇÃO =================
if pagina == "📝 EXECUTAR DTO 01":
    if not dados_ok: st.info("👈 Carregue a Base.")
    elif df_auditores is not None and auditor_valido is None: st.warning("🔒 Faça Login.")
    else:
        st.title("📝 EXECUTAR DTO 01")
        st.sidebar.header("Filtros Execução")
        
        # --- APLICAÇÃO RÍGIDA DE PERMISSÕES (EXECUÇÃO) ---
        todas_f = df_treinos['Filial'].dropna().unique()
        if permissoes['filiais'] == 'TODAS':
            opts_f = todas_f
        else:
            opts_f = [f for f in todas_f if f in permissoes['filiais']]
            
        todas_p = df_perguntas['Codigo_Padrao'].dropna().unique()
        if permissoes['padroes'] == 'TODOS':
            opts_p = todas_p
        else:
            opts_p = [p for p in todas_p if str(p) in permissoes['padroes']]

        sel_fil = st.sidebar.multiselect("Filiais", opts_f, default=opts_f if len(opts_f)==1 else None)
        
        check_todos = st.sidebar.checkbox("Todos meus Padrões", value=False, key="check_exec")
        if check_todos: sel_pad = list(opts_p)
        else: sel_pad = st.sidebar.multiselect("Padrões", opts_p)

        if sel_fil and sel_pad:
            df_m = df_treinos[(df_treinos['Filial'].isin(sel_fil)) & (df_treinos['Codigo_Padrao'].isin(sel_pad))]
            
            if df_m.empty: st.warning("Sem dados.")
            else:
                mapa_nomes = {}
                meta_por_padrao = df_perguntas.groupby('Codigo_Padrao').size()
                meta_por_padrao.index = meta_por_padrao.index.astype(str).str.strip()
                dict_metas = meta_por_padrao.to_dict()
                
                if 'Nome_Padrao' in df_perguntas.columns:
                    tn = df_perguntas[['Codigo_Padrao', 'Nome_Padrao']].drop_duplicates()
                    mapa_nomes = pd.Series(tn.Nome_Padrao.values, index=tn.Codigo_Padrao.astype(str).str.strip()).to_dict()

                rank = df_m.groupby(['CPF','Nome_Funcionario','Filial']).size().reset_index(name='Qtd')
                rank = rank.sort_values(by=['Qtd','Filial'], ascending=[False,True])
                
                tot_p = (len(rank)-1)//10 + 1
                c1,c2,c3 = st.columns([1,3,1])
                if c1.button("⬅️") and st.session_state['pagina_atual']>0: 
                    st.session_state['pagina_atual']-=1; st.rerun()
                if c3.button("➡️") and st.session_state['pagina_atual']<tot_p-1: 
                    st.session_state['pagina_atual']+=1; st.rerun()
                c2.markdown(f"<div style='text-align:center'>Pág {st.session_state['pagina_atual']+1}/{tot_p}</div>", unsafe_allow_html=True)
                
                pg_rank = rank.iloc[st.session_state['pagina_atual']*10 : (st.session_state['pagina_atual']+1)*10]
                mem = {f"{str(r.get('CPF','')).strip()}_{str(r.get('Padrao','')).strip()}_{str(r.get('Pergunta','')).strip()}": {'res':r.get('Resultado'),'obs':r.get('Observacao')} for r in st.session_state['resultados']}
                
                for _, row in pg_rank.iterrows():
                    cpf, nome, fil = row['CPF'], row['Nome_Funcionario'], row['Filial']
                    qtd_pads = row['Qtd']
                    
                    pads_no_filtro = df_m[df_m['CPF'].astype(str).str.strip() == cpf]['Codigo_Padrao'].unique()
                    pads_no_filtro = [str(p).strip() for p in pads_no_filtro]
                    meta_total = sum(dict_metas.get(p, 0) for p in pads_no_filtro)
                    
                    respondidos = 0
                    for r in st.session_state['resultados']:
                        if str(r.get('CPF','')).strip() == cpf and str(r.get('Padrao','')).strip() in pads_no_filtro: respondidos += 1
                    
                    if respondidos == 0: icon = "⚪"
                    elif respondidos >= meta_total and meta_total > 0: icon = "🟢"
                    else: icon = "🟡"
                    
                    with st.expander(f"{icon} {nome} | {fil} ({qtd_pads} Padrões | {respondidos}/{meta_total})"):
                        pads_orig = df_m[df_m['CPF'].astype(str).str.strip() == cpf]['Codigo_Padrao'].unique()
                        with st.form(key=f"f_{cpf}"):
                            c_t, _ = st.columns([1,4]); s_t = c_t.form_submit_button("💾 Salvar", key=f"t_{cpf}")
                            st.markdown("---")
                            resps, obss = {}, {}
                            for p in pads_orig:
                                p_str = str(p).strip()
                                n_p = mapa_nomes.get(p_str, "")
                                st.markdown(f"**{p_str} - {n_p}**" if n_p else f"**{p_str}**")
                                pergs = df_perguntas[df_perguntas['Codigo_Padrao'].astype(str).str.strip() == p_str]
                                for idx, pr in pergs.iterrows():
                                    pt = pr['Pergunta']
                                    kb = f"{cpf}_{p_str}_{pt}"
                                    kw = f"{cpf}_{p_str}_{idx}"
                                    prev = mem.get(kb)
                                    idx_r = ["Conforme","Não Conforme","Não se Aplica"].index(prev['res']) if prev and prev['res'] in ["Conforme","Não Conforme","Não se Aplica"] else None
                                    st.write(pt)
                                    resps[kw] = st.radio("R", ["Conforme","Não Conforme","Não se Aplica"], key=kw, horizontal=True, index=idx_r, label_visibility="collapsed")
                                    obss[kw] = st.text_input("Obs", value=(prev['obs'] if prev else ""), key=f"o_{kw}")
                                    st.markdown("---")
                            s_b = st.form_submit_button("💾 Salvar", key=f"b_{cpf}")
                            if s_t or s_b:
                                dh = obter_hora()
                                cnt = 0
                                for k, v in resps.items():
                                    if v:
                                        _, pr, ir = k.split('_', 2)
                                        try: pt = df_perguntas.loc[int(ir), 'Pergunta']
                                        except: pt = "Erro"
                                        st.session_state['resultados'] = [r for r in st.session_state['resultados'] if not (str(r.get('CPF','')).strip()==cpf and str(r.get('Padrao','')).strip()==pr and str(r.get('Pergunta','')).strip()==pt)]
                                        reg = {"Data":dh, "Filial":fil, "Funcionario":nome, "CPF":cpf, "Padrao":pr, "Pergunta":pt, "Resultado":v, "Observacao":obss.get(k,"")}
                                        if auditor_valido: reg.update({"Auditor_Nome":auditor_valido['Nome'], "Auditor_CPF":auditor_valido['CPF']})
                                        st.session_state['resultados'].append(reg)
                                        cnt+=1
                                if cnt: st.success("Salvo!"); st.rerun()
                
                st.markdown("---")
                st.subheader("📋 Resumo Sessão")
                if st.session_state['resultados']:
                    st.dataframe(pd.DataFrame(st.session_state['resultados']), use_container_width=True)
                    if st.button("🗑️ Apagar Tudo", type="primary", key="limpar_exec"): st.session_state['resultados']=[]; st.rerun()
                else: st.info("Vazio.")

# ================= PAINEL =================
elif pagina == "📊 Painel Gerencial":
    st.title("📊 Painel Gerencial")
    if not dados_ok: st.info("👈 Carregue a Base.")
    elif df_auditores is not None and auditor_valido is None: st.warning("🔒 Faça Login.")
    else:
        # --- APLICAÇÃO RÍGIDA DE PERMISSÕES (DASHBOARD) ---
        st.sidebar.header("Filtros Dashboard")
        
        # 1. Filtro Filiais (Restrito)
        todas_f = df_treinos['Filial'].unique()
        if permissoes['filiais'] == 'TODAS':
            opts_f = todas_f
        else:
            opts_f = [f for f in todas_f if f in permissoes['filiais']]
            
        check_all_f = st.sidebar.checkbox("Todas as Filiais", value=True, key="daf")
        sel_f = list(opts_f) if check_all_f else st.sidebar.multiselect("Filiais", opts_f, default=opts_f)
        
        # 2. Filtro Padrões (Restrito)
        todas_p = df_perguntas['Codigo_Padrao'].unique()
        if permissoes['padroes'] == 'TODOS':
            opts_p = todas_p
        else:
            opts_p = [p for p in todas_p if str(p) in permissoes['padroes']]
            
        check_all_p = st.sidebar.checkbox("Todos os Padrões", value=True, key="dap")
        sel_p = list(opts_p) if check_all_p else st.sidebar.multiselect("Padrões", opts_p, default=opts_p)
        
        st.markdown("---")
        
        # Conflitos
        df_res = pd.DataFrame(st.session_state['resultados'])
        if not df_res.empty and all(c in df_res.columns for c in ['CPF','Padrao','Pergunta']):
            dups = df_res[df_res.duplicated(subset=['CPF','Padrao','Pergunta'], keep=False)]
            if not dups.empty: st.error(f"⚠️ {len(dups)} Conflitos!"); st.dataframe(dups)
            else: st.success("✅ Sem conflitos.")
        
        # --- CÁLCULOS COM FILTROS DE SEGURANÇA ---
        df_esc = df_treinos[(df_treinos['Filial'].isin(sel_f)) & (df_treinos['Codigo_Padrao'].isin(sel_p))]
        
        df_rf = pd.DataFrame()
        if not df_res.empty:
            if 'Filial' in df_res.columns and 'Padrao' in df_res.columns:
                df_rf = df_res[(df_res['Filial'].isin(sel_f)) & (df_res['Padrao'].isin(sel_p))]
        
        metas = df_perguntas.groupby('Codigo_Padrao').size()
        metas.index = metas.index.astype(str).str.strip()
        dict_metas = metas.to_dict()
        
        st.write("Modo de Visualização:")
        visao = st.radio("Escolha:", ["👥 Por Pessoa", "📏 Por Padrão (Volume)"], horizontal=True, label_visibility="collapsed")
        st.markdown("---")

        if visao == "👥 Por Pessoa":
            total = df_esc['CPF'].nunique()
            counts = {'Pendente': 0, 'Parcial': 0, 'Concluido': 0}
            lista_detalhe = []
            
            resps = {}
            if not df_rf.empty and 'CPF' in df_rf.columns:
                temp = df_rf.copy(); temp['CPF'] = temp['CPF'].astype(str).str.strip()
                resps = temp.groupby('CPF').size().to_dict()
            
            for cpf in df_esc['CPF'].astype(str).str.strip().unique():
                escopo_cpf = df_esc[df_esc['CPF'].astype(str).str.strip() == cpf]
                pads = escopo_cpf['Codigo_Padrao'].astype(str).str.strip().unique()
                meta = sum(dict_metas.get(p,0) for p in pads)
                real = resps.get(cpf, 0)
                info = escopo_cpf.iloc[0]
                
                status = "🔴 Pendente"
                if real == 0: counts['Pendente'] += 1
                elif real >= meta and meta > 0: 
                    counts['Concluido'] += 1; status = "🟢 Concluído"
                else: 
                    counts['Parcial'] += 1; status = "🟡 Parcial"
                
                pct = int((real/meta)*100) if meta > 0 else 0
                lista_detalhe.append({"Filial": info['Filial'], "CPF": cpf, "Nome": info['Nome_Funcionario'], "Status": status, "Progresso": f"{real}/{meta} ({pct}%)"})
            
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Total Pessoas", total)
            c2.metric("Concluídos", counts['Concluido'])
            c3.metric("Parcial", counts['Parcial'])
            c4.metric("Pendentes", counts['Pendente'])
            prog = counts['Concluido']/total if total else 0
            st.progress(prog, f"Taxa: {int(prog*100)}%")
            
            df_det = pd.DataFrame(lista_detalhe)
            t1, t2, t3 = st.tabs(["🔴 Pendentes", "🟡 Parciais", "🟢 Concluídos"])
            if not df_det.empty:
                with t1: st.dataframe(df_det[df_det['Status'].str.contains("Pendente")], use_container_width=True, hide_index=True)
                with t2: st.dataframe(df_det[df_det['Status'].str.contains("Parcial")], use_container_width=True, hide_index=True)
                with t3: st.dataframe(df_det[df_det['Status'].str.contains("Concluído")], use_container_width=True, hide_index=True)
                st.download_button("📥 Baixar Status Pessoas", gerar_excel(df_det), "Status_Pessoas.xlsx")

        else:
            total_vol = len(df_esc)
            counts_vol = {'Zero': 0, 'Iniciado': 0, 'Completo': 0}
            volumetria = []
            
            mapa_nomes = {}
            if 'Nome_Padrao' in df_perguntas.columns:
                tn = df_perguntas[['Codigo_Padrao', 'Nome_Padrao']].drop_duplicates()
                mapa_nomes = pd.Series(tn.Nome_Padrao.values, index=tn.Codigo_Padrao.astype(str).str.strip()).to_dict()
            
            resps_det = {}
            if not df_rf.empty:
                temp_rf = df_rf.copy()
                temp_rf['CPF'] = temp_rf['CPF'].astype(str).str.strip()
                temp_rf['Padrao'] = temp_rf['Padrao'].astype(str).str.strip()
                resps_det = temp_rf.groupby(['CPF', 'Padrao']).size().to_dict()

            for _, row in df_esc.iterrows():
                c = str(row['CPF']).strip(); p = str(row['Codigo_Padrao']).strip()
                meta = dict_metas.get(p, 0); real = resps_det.get((c, p), 0)
                if real == 0: counts_vol['Zero'] += 1
                elif real >= meta and meta > 0: counts_vol['Completo'] += 1
                else: counts_vol['Iniciado'] += 1

            for p in df_esc['Codigo_Padrao'].astype(str).str.strip().unique():
                linhas_p = df_esc[df_esc['Codigo_Padrao'].astype(str).str.strip() == p]
                qtd_meta = len(linhas_p)
                concluidos_este = 0
                for _, r_esc in linhas_p.iterrows():
                    c_check = str(r_esc['CPF']).strip()
                    meta_check = dict_metas.get(p, 0)
                    real_check = resps_det.get((c_check, p), 0)
                    if real_check >= meta_check and meta_check > 0: concluidos_este += 1
                
                nome_p = mapa_nomes.get(p, p)
                pct = int((concluidos_este / qtd_meta)*100) if qtd_meta > 0 else 0
                volumetria.append({"Código": p, "Descrição": nome_p, "Volume Total": qtd_meta, "Concluídas": concluidos_este, "%": f"{pct}%"})

            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Volume Total", total_vol)
            c2.metric("Concluídas", counts_vol['Completo'])
            c3.metric("Em Andamento", counts_vol['Iniciado'])
            c4.metric("Não Iniciadas", counts_vol['Zero'])
            prog_v = counts_vol['Completo']/total_vol if total_vol else 0
            st.progress(prog_v, f"Cobertura Volumétrica: {int(prog_v*100)}%")
            
            df_vol = pd.DataFrame(volumetria)
            st.dataframe(df_vol, use_container_width=True, hide_index=True)
            if not df_vol.empty: st.download_button("📥 Baixar Volumetria", gerar_excel(df_vol), "Status_Volume.xlsx")

        st.markdown("---")
        b1,b2 = st.columns([3,1])
        if not df_res.empty:
            out = BytesIO()
            with pd.ExcelWriter(out, engine='xlsxwriter') as writer: df_res.to_excel(writer, index=False)
            b1.download_button("📥 Baixar Excel", out.getvalue(), f"Master_{obter_hora().replace('/','-')}.xlsx")
        
        if b2.button("🗑️ Limpar Tudo", key="trash_dash"): st.session_state['resultados']=[]; st.rerun()
