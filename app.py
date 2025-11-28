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
            d.columns = [c.strip() for c in d.columns]
            for c in ['CPF','Padrao','Pergunta','Auditor_CPF']:
                if c in d.columns: d[c] = d[c].astype(str).str.strip()
            dfs.append(d)
        if dfs:
            st.session_state['resultados'] = pd.concat(dfs, ignore_index=True).to_dict('records')
            st.sidebar.success(f"📦 Consolidado: {len(st.session_state['resultados'])} regs")
    except Exception as e: st.sidebar.error(f"Erro Histórico: {e}")

# Login
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
                st.sidebar.subheader("🔐 Login")
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
                    else: st.sidebar.error("CPF não autorizado.")
        else:
            st.session_state['auditor_logado'] = {'Nome': 'Geral', 'CPF': '000'}
            st.session_state['permissoes'] = {'filiais': 'TODAS', 'padroes': 'TODOS', 'perfil': 'Gestor'}
    except: pass

# Sidebar Download
if st.session_state['resultados']:
    st.sidebar.markdown("---")
    st.sidebar.write("📂 **Backup**")
    df_dw = pd.DataFrame(st.session_state['resultados'])
    perms = st.session_state['permissoes']
    if st.session_state['auditor_logado'] and perms.get('perfil') != 'Gestor' and perms.get('filiais') != 'TODAS':
        if 'Filial' in df_dw.columns: df_dw = df_dw[df_dw['Filial'].isin(perms['filiais'])]
    
    excel_data = gerar_excel(df_dw)
    if excel_data: st.sidebar.download_button("📥 Baixar Planilha", excel_data, "Backup_Auditoria.xlsx", mime="application/vnd.ms-excel")

st.sidebar.markdown("---")
pagina = st.sidebar.radio("Menu:", ["📝 EXECUTAR DTO 01", "📊 Painel Gerencial"])

# Leitura Base
df_treinos, df_perguntas, dados_ok = pd.DataFrame(), pd.DataFrame(), False
if uploaded_file:
    try:
        df_treinos = pd.read_excel(uploaded_file, sheet_name='Base_Treinamentos')
        df_perguntas = pd.read_excel(uploaded_file, sheet_name='Padroes_Perguntas')
        for df in [df_treinos, df_perguntas]:
            for col in df.columns:
                if col in ['CPF', 'Codigo_Padrao', 'Filial', 'Pergunta', 'Nome_Padrao']:
                    df[col] = df[col].astype(str).str.strip()
        dados_ok = True
    except Exception as e: st.error(f"Erro Base: {e}")
        # ================= EXECUÇÃO =================
if pagina == "📝 EXECUTAR DTO 01":
    if not dados_ok: st.info("👈 Carregue a Base.")
    elif df_auditores is not None and st.session_state['auditor_logado'] is None: st.warning("🔒 Faça Login.")
    else:
        st.title("📝 EXECUTAR DTO 01")
        perms = st.session_state['permissoes']
        
        # Filtros com Segurança
        st.sidebar.header("Filtros Execução")
        todas_f = sorted(df_treinos['Filial'].dropna().unique())
        if perms['filiais'] == 'TODAS': opts_f = todas_f
        else: opts_f = sorted([f for f in todas_f if f in perms['filiais']])
        sel_fil = st.sidebar.multiselect("Filiais", opts_f, default=opts_f if len(opts_f)==1 else None)
        
        todas_p = sorted(df_perguntas['Codigo_Padrao'].dropna().unique())
        if perms['padroes'] == 'TODOS': opts_p = todas_p
        else: opts_p = sorted([p for p in todas_p if str(p) in perms['padroes']])
        sel_pad = list(opts_p) if st.sidebar.checkbox("Todos Padrões", key="pe") else st.sidebar.multiselect("Padrões", opts_p)

        if sel_fil and sel_pad:
            df_m = df_treinos[(df_treinos['Filial'].isin(sel_fil)) & (df_treinos['Codigo_Padrao'].isin(sel_pad))]
            if df_m.empty: st.warning("Sem dados.")
            else:
                # Metadados
                mapa_nomes = {}
                if 'Nome_Padrao' in df_perguntas.columns:
                    tn = df_perguntas[['Codigo_Padrao', 'Nome_Padrao']].drop_duplicates()
                    mapa_nomes = pd.Series(tn.Nome_Padrao.values, index=tn.Codigo_Padrao).to_dict()
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
                
                mem = {f"{str(r.get('CPF','')).strip()}_{str(r.get('Padrao','')).strip()}_{str(r.get('Pergunta','')).strip()}": {'res':r.get('Resultado'),'obs':r.get('Observacao')} for r in st.session_state['resultados']}
                
                for _, row in pg_rank.iterrows():
                    cpf, nome, fil = str(row['CPF']).strip(), row['Nome_Funcionario'], row['Filial']
                    qtd_pads = row['Qtd']
                    
                    # Status
                    pads_no_filtro = df_m[df_m['CPF'].astype(str).str.strip() == cpf]['Codigo_Padrao'].unique()
                    pads_no_filtro = [str(p).strip() for p in pads_no_filtro]
                    meta_tot = sum(dict_metas.get(p,0) for p in pads_no_filtro)
                    resp_tot = 0
                    for r in st.session_state['resultados']:
                        if str(r.get('CPF','')).strip() == cpf and str(r.get('Padrao','')).strip() in pads_no_filtro: resp_tot += 1
                    
                    if resp_tot == 0: icon = "⚪"
                    elif resp_tot >= meta_tot and meta_tot > 0: icon = "🟢"
                    else: icon = "🟡"
                    
                    with st.expander(f"{icon} {nome} | {fil} ({qtd_pads} Padrões | {resp_tot}/{meta_tot})"):
                        with st.form(key=f"f_{cpf}"):
                            c_top, _ = st.columns([1, 4])
                            s_top = c_top.form_submit_button("💾 Salvar", key=f"t_{cpf}")
                            st.markdown("---")
                            resps, obss = {}, {}
                            pads_orig = df_m[df_m['CPF'].astype(str).str.strip() == cpf]['Codigo_Padrao'].unique()
                            for p in pads_orig:
                                p_str = str(p).strip()
                                n_p = mapa_nomes.get(p_str, "")
                                st.markdown(f"**{p_str} - {n_p}**")
                                pergs = df_perguntas[df_perguntas['Codigo_Padrao'].astype(str).str.strip() == p_str]
                                for idx, pr in pergs.iterrows():
                                    txt, k_wd = pr['Pergunta'], f"{cpf}_{p_str}_{idx}"
                                    prev = mem.get(f"{cpf}_{p_str}_{txt}")
                                    idx_r = ["Conforme","Não Conforme","Não se Aplica"].index(prev['res']) if prev and prev['res'] in ["Conforme","Não Conforme","Não se Aplica"] else None
                                    st.write(txt)
                                    resps[k_wd] = st.radio("R", ["Conforme","Não Conforme","Não se Aplica"], key=k_wd, horizontal=True, index=idx_r, label_visibility="collapsed")
                                    obss[k_wd] = st.text_input("Obs", value=(prev['obs'] if prev else ""), key=f"o_{k_wd}")
                                    st.markdown("---")
                            s_bot = st.form_submit_button("💾 Salvar", key=f"b_{cpf}")
                            
                            if s_top or s_bot:
                                dh = obter_hora()
                                for k, v in resps.items():
                                    if v:
                                        _, pr, ir = k.split('_', 2)
                                        try: pt = df_perguntas.loc[int(ir), 'Pergunta']
                                        except: pt = "Erro"
                                        st.session_state['resultados'] = [r for r in st.session_state['resultados'] if not (str(r.get('CPF','')).strip()==cpf and str(r.get('Padrao','')).strip()==pr and str(r.get('Pergunta','')).strip()==pt)]
                                        reg = {"Data":dh, "Filial":fil, "Funcionario":nome, "CPF":cpf, "Padrao":pr, "Pergunta":pt, "Resultado":v, "Observacao":obss.get(k,"")}
                                        if st.session_state['auditor_logado']: reg.update({"Auditor_Nome":st.session_state['auditor_logado']['Nome'], "Auditor_CPF":st.session_state['auditor_logado']['CPF']})
                                        st.session_state['resultados'].append(reg)
                                st.success("Salvo!"); st.rerun()
                
                if st.session_state['resultados']:
                    st.markdown("---"); st.subheader("📋 Resumo")
                    st.dataframe(pd.DataFrame(st.session_state['resultados']), use_container_width=True)
                    if st.button("🗑️ Apagar Tudo"): st.session_state['resultados']=[]; st.rerun()
                        # ================= PAINEL =================
elif pagina == "📊 Painel Gerencial":
    st.title("📊 Painel Gerencial")
    if not dados_ok: st.info("👈 Carregue a Base.")
    elif df_auditores is not None and st.session_state['auditor_logado'] is None: st.warning("🔒 Faça Login.")
    else:
        perms = st.session_state['permissoes']
        with st.expander("🔍 Raio-X", expanded=False):
            colisao = df_treinos.groupby('CPF')['Nome_Funcionario'].nunique()
            errados = colisao[colisao > 1]
            if not errados.empty: st.error(f"CPFs Duplicados: {len(errados)}")
            else: st.success("Base OK.")

        st.sidebar.header("Filtros Dashboard")
        todas_f = sorted(df_treinos['Filial'].unique())
        if perms['filiais'] == 'TODAS': opts_f = todas_f
        else: opts_f = sorted([f for f in todas_f if f in perms['filiais']])
        f_sel = st.sidebar.multiselect("Filiais", opts_f, default=opts_f)
        
        todas_p = sorted(df_perguntas['Codigo_Padrao'].unique())
        if perms['padroes'] == 'TODOS': opts_p = todas_p
        else: opts_p = sorted([p for p in todas_p if str(p) in perms['padroes']])
        p_sel = st.sidebar.multiselect("Padrões", opts_p, default=opts_p)
        
        st.markdown("---")
        df_esc = df_treinos[(df_treinos['Filial'].isin(f_sel)) & (df_treinos['Codigo_Padrao'].isin(p_sel))]
        
        df_res = pd.DataFrame(st.session_state['resultados'])
        df_rf = pd.DataFrame()
        if not df_res.empty:
            if 'Filial' in df_res.columns and 'Padrao' in df_res.columns:
                df_rf = df_res[(df_res['Filial'].isin(f_sel)) & (df_res['Padrao'].isin(p_sel))]
        
        metas = df_perguntas.groupby('Codigo_Padrao').size().to_dict()
        
        st.write("Visualização:")
        visao = st.radio("V", ["👥 Por Pessoa", "📏 Por Padrão"], horizontal=True, label_visibility="collapsed")
        st.markdown("---")

        if visao == "👥 Por Pessoa":
            total = df_esc['CPF'].nunique()
            counts = {'P':0, 'A':0, 'C':0}
            data_list = []
            
            resps = {}
            if not df_rf.empty: resps = df_rf.groupby('CPF').size().to_dict()
            
            for cpf in df_esc['CPF'].unique():
                pads = df_esc[df_esc['CPF']==cpf]['Codigo_Padrao'].unique()
                meta = sum(metas.get(p,0) for p in pads)
                real = resps.get(cpf, 0)
                
                if real == 0: stt="🔴"; counts['P']+=1
                elif real >= meta and meta>0: stt="🟢"; counts['C']+=1
                else: stt="🟡"; counts['A']+=1
                
                info = df_esc[df_esc['CPF']==cpf].iloc[0]
                pct = int((real/meta)*100) if meta>0 else 0
                data_list.append({"Filial":info['Filial'], "Nome":info['Nome_Funcionario'], "Status":stt, "Prog":f"{real}/{meta} ({pct}%)"})
            
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Pessoas", total)
            c2.metric("Concluídos", counts['C'])
            c3.metric("Parcial", counts['A'])
            c4.metric("Pendentes", counts['P'])
            prog = counts['C']/total if total else 0
            st.progress(prog, f"Taxa: {int(prog*100)}%")
            
            df_d = pd.DataFrame(data_list)
            if not df_d.empty:
                t1,t2,t3 = st.tabs(["🔴","🟡","🟢"])
                with t1: st.dataframe(df_d[df_d['Status']=="🔴"], use_container_width=True)
                with t2: st.dataframe(df_d[df_d['Status']=="🟡"], use_container_width=True)
                with t3: st.dataframe(df_d[df_d['Status']=="🟢"], use_container_width=True)
                st.download_button("📥 Baixar Status", gerar_excel(df_d), "Status_Pessoas.xlsx")

        else:
            total_vol = len(df_esc) 
            counts_v = {'Z':0, 'I':0, 'C':0}
            vol_data = []
            
            mapa_nomes = {}
            if 'Nome_Padrao' in df_perguntas.columns:
                tn = df_perguntas[['Codigo_Padrao', 'Nome_Padrao']].drop_duplicates()
                mapa_nomes = pd.Series(tn.Nome_Padrao.values, index=tn.Codigo_Padrao).to_dict()
            
            resps_det = {}
            if not df_rf.empty: resps_det = df_rf.groupby(['CPF', 'Padrao']).size().to_dict()

            for _, r in df_esc.iterrows():
                c, p = r['CPF'], r['Codigo_Padrao']
                m = metas.get(p,0)
                rv = resps_det.get((c,p), 0)
                if rv == 0: counts_v['Z']+=1
                elif rv >= m and m>0: counts_v['C']+=1
                else: counts_v['I']+=1

            for p in df_esc['Codigo_Padrao'].unique():
                sub = df_esc[df_esc['Codigo_Padrao']==p]
                qm = len(sub)
                qok = 0
                for c in sub['CPF']:
                    m = metas.get(p,0)
                    if resps_det.get((c,p),0) >= m and m>0: qok+=1
                
                n_p = mapa_nomes.get(p,p)
                pct = int((qok/qm)*100) if qm>0 else 0
                vol_data.append({"Padrão":p, "Desc":n_p, "Vol":qm, "Ok":qok, "%":f"{pct}%"})

            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Volume Total", total_vol)
            c2.metric("Concluídas", counts_v['C'])
            c3.metric("Andamento", counts_v['I'])
            c4.metric("Zero", counts_v['Z'])
            prog_v = counts_v['C']/total_vol if total_vol else 0
            st.progress(prog_v, f"Cobertura: {int(prog_v*100)}%")
            
            df_v = pd.DataFrame(vol_data)
            st.dataframe(df_v, use_container_width=True)
            if not df_v.empty: st.download_button("📥 Baixar Volumetria", gerar_excel(df_v), "Status_Volume.xlsx")

        st.markdown("---")
        b1,b2 = st.columns([3,1])
        if not df_res.empty:
            out = BytesIO()
            with pd.ExcelWriter(out, engine='xlsxwriter') as writer: df_res.to_excel(writer, index=False)
            b1.download_button("📥 Baixar Master", out.getvalue(), f"Master_{obter_hora().replace('/','-')}.xlsx")
        
        if b2.button("🗑️ Limpar Tudo", key="trash_dash"): st.session_state['resultados']=[]; st.rerun()
