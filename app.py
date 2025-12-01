import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
import os
import pytz
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="DTO 01 - DCS SCANIA", page_icon="🚛", layout="wide")

# --- 2. MEMÓRIA ---
if 'resultados' not in st.session_state: st.session_state['resultados'] = []
if 'pagina_atual' not in st.session_state: st.session_state['pagina_atual'] = 0
if 'auditor_logado' not in st.session_state: st.session_state['auditor_logado'] = None
if 'permissoes' not in st.session_state: 
    st.session_state['permissoes'] = {'filiais': [], 'padroes': [], 'perfil': ''}
if 'lista_auditores' not in st.session_state: st.session_state['lista_auditores'] = []

# --- 3. FUNÇÕES ---
def obter_hora():
    return datetime.now(pytz.timezone('America/Sao_Paulo')).strftime("%d/%m/%Y %H:%M")

def gerar_excel(df_input):
    out = BytesIO()
    with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
        df_input.to_excel(writer, index=False)
    return out.getvalue()

def achar_coluna(df, termo):
    for col in df.columns:
        if termo.lower() in col.lower(): return col
    return None

# --- 4. BARRA LATERAL ---
st.sidebar.header("1. Conexão")
if os.path.exists("logo.png"): st.sidebar.image("logo.png", use_container_width=True)
else: st.sidebar.write("🏢 DTO 01 - DCS SCANIA")

# Globais
df_treinos = pd.DataFrame()
df_perguntas = pd.DataFrame()
df_auditores = None
dados_ok = False

# Conexão Google
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    with st.spinner('Sincronizando...'):
        df_treinos = conn.read(worksheet="Base_Treinamentos", ttl=600)
        df_perguntas = conn.read(worksheet="Padroes_Perguntas", ttl=600)
        try: df_auditores = conn.read(worksheet="Cadastro_Auditores", ttl=600)
        except: df_auditores = None

        for df in [df_treinos, df_perguntas]:
            df.dropna(how='all', inplace=True)
            df.columns = [c.strip() for c in df.columns]
            for c in df.columns:
                if c in ['CPF','Codigo_Padrao','Filial','Pergunta','Nome_Padrao']:
                    df[c] = df[c].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        
        if df_auditores is not None:
            df_auditores.dropna(how='all', inplace=True)
            df_auditores.columns = [c.strip() for c in df_auditores.columns]
            c_cpf_aud = achar_coluna(df_auditores, 'cpf')
            if c_cpf_aud: 
                df_auditores[c_cpf_aud] = df_auditores[c_cpf_aud].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                c_nm_g = achar_coluna(df_auditores, 'nome') or c_cpf_aud
                st.session_state['lista_auditores'] = df_auditores[c_nm_g].unique().tolist()
        dados_ok = True
        st.sidebar.success("✅ Base Conectada")
except Exception as e: st.sidebar.error(f"Erro Conexão: {e}")

# Histórico
st.sidebar.markdown("---")
uploaded_hist = st.sidebar.file_uploader("Carregar Histórico", type=["xlsx"], key="hist", accept_multiple_files=True)
if uploaded_hist and not st.session_state['resultados']:
    dfs = []
    try:
        for f in uploaded_hist:
            d = pd.read_excel(f)
            d.columns = [c.strip() for c in d.columns]
            for c in ['CPF','Padrao','Pergunta','Auditor_CPF','Filial']:
                if c in d.columns: d[c] = d[c].astype(str).str.strip()
            dfs.append(d)
        if dfs:
            st.session_state['resultados'] = pd.concat(dfs, ignore_index=True).to_dict('records')
            st.sidebar.success(f"📦 Histórico: {len(st.session_state['resultados'])} regs")
    except: pass

# Login
if dados_ok:
    if df_auditores is not None:
        col_cpf = achar_coluna(df_auditores, 'cpf')
        if col_cpf:
            st.sidebar.markdown("---")
            if st.session_state['auditor_logado']:
                user = st.session_state['auditor_logado']
                st.sidebar.success(f"👤 {user['Nome']}")
                if st.sidebar.button("Sair"):
                    st.session_state['auditor_logado'] = None
                    st.session_state['permissoes'] = {'filiais': [], 'padroes': [], 'perfil': ''}
                    st.rerun()
            else:
                st.sidebar.subheader("🔐 Login")
                cpf_in = st.sidebar.text_input("CPF (Apenas números)", type="password")
                if st.sidebar.button("Entrar"):
                    cpf_cl = cpf_in.replace('.','').replace('-','').strip()
                    match = df_auditores[df_auditores[col_cpf]==cpf_cl]
                    if not match.empty:
                        dat = match.iloc[0]
                        c_nm = achar_coluna(df_auditores, 'nome') or col_cpf
                        c_pf = achar_coluna(df_auditores, 'perfil')
                        c_fil = achar_coluna(df_auditores, 'filiais')
                        # CORREÇÃO DA VARIÁVEL AQUI
                        c_pad = achar_coluna(df_auditores, 'padroes') or achar_coluna(df_auditores, 'padrões')

                        nome = dat[c_nm]
                        perf = str(dat[c_pf]).strip() if c_pf else 'Auditor'
                        
                        rf = str(dat.get(c_fil, 'Todas')) if c_fil else 'Todas'
                        pf = 'TODAS' if 'todas' in rf.lower() or rf=='nan' else [x.strip() for x in rf.split(',')]
                        
                        rp = str(dat.get(c_pad, 'Todos')) if c_pad else 'Todos'
                        pp = 'TODOS' if 'todos' in rp.lower() or rp=='nan' else [x.strip() for x in rp.split(',')]

                        st.session_state['auditor_logado'] = {'Nome': nome, 'CPF': cpf_cl}
                        st.session_state['permissoes'] = {'filiais': pf, 'padroes': pp, 'perfil': perf}
                        st.rerun()
                    else: st.sidebar.error("CPF não encontrado.")
    else:
        st.session_state['auditor_logado'] = {'Nome': 'Geral', 'CPF': '000'}
        st.session_state['permissoes'] = {'filiais': 'TODAS', 'padroes': 'TODOS', 'perfil': 'Gestor'}

# Download
if st.session_state['resultados']:
    st.sidebar.markdown("---")
    st.sidebar.write("📂 **Backup**")
    df_dw = pd.DataFrame(st.session_state['resultados'])
    perms = st.session_state['permissoes']
    if st.session_state['auditor_logado'] and perms.get('perfil')!='Gestor' and perms.get('filiais')!='TODAS':
        if 'Filial' in df_dw.columns: df_dw = df_dw[df_dw['Filial'].isin(perms['filiais'])]
    
    excel_data = gerar_excel(df_dw)
    if excel_data: st.sidebar.download_button("📥 Baixar Planilha", excel_data, "Backup_Auditoria.xlsx", mime="application/vnd.ms-excel")

st.sidebar.markdown("---")
pagina = st.sidebar.radio("Menu:", ["📝 EXECUTAR DTO 01", "📊 Painel Gerencial"])
# ================= EXECUÇÃO =================
if pagina == "📝 EXECUTAR DTO 01":
    if not dados_ok: st.info("⏳ Aguardando dados...")
    elif df_auditores is not None and st.session_state['auditor_logado'] is None:
        st.warning("🔒 Acesso Bloqueado. Faça login na barra lateral.")
    else:
        st.title("📝 EXECUTAR DTO 01")
        perms = st.session_state['permissoes']
        st.sidebar.header("Filtros Execução")
        
        t_fil = sorted(df_treinos['Filial'].dropna().unique())
        if perms['filiais'] == 'TODAS': opts_f = t_fil
        else: opts_f = sorted([f for f in t_fil if f in perms['filiais']])
        sel_fil = st.sidebar.multiselect("Selecione Filiais", opts_f, default=opts_f if len(opts_f)==1 else None)
        
        t_pad = sorted(df_perguntas['Codigo_Padrao'].dropna().unique())
        if perms['padroes'] == 'TODOS': opts_p = t_pad
        else: opts_p = sorted([p for p in t_pad if str(p) in perms['padroes']])
        sel_pad = list(opts_p) if st.sidebar.checkbox("Todos Meus Padrões", key="pe") else st.sidebar.multiselect("Padrões", opts_p)

        if sel_fil and sel_pad:
            df_m = df_treinos[(df_treinos['Filial'].isin(sel_fil)) & (df_treinos['Codigo_Padrao'].isin(sel_pad))]
            
            if df_m.empty: st.warning("Sem dados.")
            else:
                m_nom = {}
                if 'Nome_Padrao' in df_perguntas.columns:
                    tn = df_perguntas[['Codigo_Padrao', 'Nome_Padrao']].drop_duplicates()
                    m_nom = pd.Series(tn.Nome_Padrao.values, index=tn.Codigo_Padrao.astype(str).str.strip()).to_dict()
                
                dict_metas = df_perguntas.groupby('Codigo_Padrao').size().to_dict()

                rank = df_m.groupby(['CPF','Nome_Funcionario','Filial']).size().reset_index(name='Qtd')
                rank = rank.sort_values(by=['Qtd','Filial'], ascending=[False,True])
                
                tot_p = (len(rank)-1)//10 + 1
                c1,c2,c3 = st.columns([1,3,1])
                if c1.button("⬅️") and st.session_state['pagina_atual']>0: st.session_state['pagina_atual']-=1; st.rerun()
                if c3.button("➡️") and st.session_state['pagina_atual']<tot_p-1: st.session_state['pagina_atual']+=1; st.rerun()
                c2.markdown(f"<div style='text-align:center'>Pág {st.session_state['pagina_atual']+1}/{tot_p}</div>", unsafe_allow_html=True)
                
                pg_rank = rank.iloc[st.session_state['pagina_atual']*10 : (st.session_state['pagina_atual']+1)*10]
                mem = {f"{str(r.get('CPF','')).strip()}_{str(r.get('Padrao','')).strip()}_{str(r.get('Pergunta','')).strip()}": {'res':r.get('Resultado'),'obs':r.get('Observacao')} for r in st.session_state['resultados']}
                
                for _, row in pg_rank.iterrows():
                    cpf, nome, fil = str(row['CPF']).strip(), row['Nome_Funcionario'], row['Filial']
                    q_pd = row['Qtd']
                    
                    p_nf = df_m[df_m['CPF'].astype(str).str.strip() == cpf]['Codigo_Padrao'].unique()
                    p_nf = [str(p).strip() for p in p_nf]
                    m_tot = sum(dict_metas.get(p,0) for p in p_nf)
                    
                    r_tot = 0
                    for r in st.session_state['resultados']:
                        if str(r.get('CPF','')).strip() == cpf and str(r.get('Padrao','')).strip() in p_nf: r_tot += 1
                    
                    if r_tot == 0: icon = "⚪"
                    elif r_tot >= m_tot and m_tot > 0: icon = "🟢"
                    else: icon = "🟡"
                    
                    with st.expander(f"{icon} {nome} | {fil} ({q_pd} Padrões | {r_tot}/{m_tot})"):
                        with st.form(key=f"f_{cpf}"):
                            c_top, _ = st.columns([1, 4])
                            s_top = c_top.form_submit_button("💾 Salvar na Nuvem", key=f"t_{cpf}")
                            st.markdown("---")
                            resps, obss = {}, {}
                            p_orig = df_m[df_m['CPF'].astype(str).str.strip() == cpf]['Codigo_Padrao'].unique()
                            for p in p_orig:
                                p_str = str(p).strip()
                                st.markdown(f"**{p_str} - {m_nom.get(p_str, '')}**")
                                pergs = df_perguntas[df_perguntas['Codigo_Padrao'].astype(str).str.strip() == p_str]
                                for idx, pr in pergs.iterrows():
                                    txt, k_wd = pr['Pergunta'], f"{cpf}_{p_str}_{idx}"
                                    prev = mem.get(f"{cpf}_{p_str}_{txt}")
                                    ir = ["Conforme","Não Conforme","Não se Aplica"].index(prev['res']) if prev and prev['res'] in ["Conforme","Não Conforme","Não se Aplica"] else None
                                    st.write(txt)
                                    resps[k_wd] = st.radio("R", ["Conforme", "Não Conforme", "Não se Aplica"], key=k_wd, horizontal=True, index=ir, label_visibility="collapsed")
                                    obss[k_wd] = st.text_input("Obs", value=(prev['obs'] if prev else ""), key=f"o_{k_wd}")
                                    st.markdown("---")
                            s_bot = st.form_submit_button("💾 Salvar na Nuvem", key=f"b_{cpf}")
                            
                            if s_top or s_bot:
                                dh = obter_hora()
                                novos = []
                                for k, v in resps.items():
                                    if v:
                                        _, pr, ir = k.split('_', 2)
                                        try: pt = df_perguntas.loc[int(ir), 'Pergunta']
                                        except: pt = "Erro"
                                        st.session_state['resultados'] = [r for r in st.session_state['resultados'] if not (str(r.get('CPF','')).strip()==cpf and str(r.get('Padrao','')).strip()==pr and str(r.get('Pergunta','')).strip()==pt)]
                                        reg = {"Data":dh, "Filial":fil, "Funcionario":nome, "CPF":cpf, "Padrao":pr, "Pergunta":pt, "Resultado":v, "Observacao":obss.get(k,"")}
                                        if st.session_state['auditor_logado']: reg.update({"Auditor_Nome":st.session_state['auditor_logado']['Nome'], "Auditor_CPF":st.session_state['auditor_logado']['CPF']})
                                        st.session_state['resultados'].append(reg)
                                        novos.append(reg)
                                
                                if novos:
                                    try:
                                        conn = st.connection("gsheets", type=GSheetsConnection)
                                        df_up = pd.DataFrame(st.session_state['resultados'])
                                        conn.update(worksheet="Respostas_DB", data=df_up)
                                        st.success("Salvo na Nuvem!"); st.rerun()
                                    except Exception as e: st.error(f"Erro Nuvem: {e}")
                
                st.markdown("---")
                if st.session_state['resultados']:
                    st.subheader("📋 Resumo")
                    st.dataframe(pd.DataFrame(st.session_state['resultados']), use_container_width=True)
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

        # PERFORMANCE AUDITOR
        if perms.get('perfil') == 'Gestor' and df_auditores is not None:
            st.subheader("🏆 Performance Operacional")
            try:
                tbl_perf = []
                l_auds = st.session_state.get('lista_auditores', [])
                if not l_auds:
                     cn = achar_coluna(df_auditores, 'nome')
                     if cn: l_auds = df_auditores[cn].unique().tolist()

                for nm in l_auds:
                    da = pd.Series()
                    cn = achar_coluna(df_auditores, 'nome')
                    if cn:
                        m = df_auditores[df_auditores[cn] == nm]
                        if not m.empty: da = m.iloc[0]
                    
                    pa = achar_coluna(df_auditores, 'perfil')
                    if pa and 'gestor' in str(da.get(pa, '')).lower(): continue

                    cf, cp = achar_coluna(df_auditores, 'filiais'), achar_coluna(df_auditores, 'padroes')
                    rf = str(da.get(cf, 'Todas')) if cf else 'Todas'
                    lf = list(df_treinos['Filial'].unique()) if 'todas' in rf.lower() else [x.strip() for x in rf.split(',')]
                    rp = str(da.get(cp, 'Todos')) if cp else 'Todos'
                    lp = list(df_perguntas['Codigo_Padrao'].unique()) if 'todos' in rp.lower() else [x.strip() for x in rp.split(',')]
                    
                    df_uni = df_treinos[(df_treinos['Filial'].isin(lf)) & (df_treinos['Codigo_Padrao'].isin(lp))]
                    m_aud = sum(metas.get(str(r['Codigo_Padrao']),0) for _, r in df_uni.iterrows())
                    r_aud = len(df_rf[df_rf['Auditor_Nome'] == nm]) if not df_rf.empty and 'Auditor_Nome' in df_rf.columns else 0
                    
                    pend = max(0, m_aud - r_aud)
                    pct = int((r_aud/m_aud)*100) if m_aud > 0 else 0
                    tbl_perf.append({"Auditor": nm, "Meta": m_aud, "Real": r_aud, "Pend": pend, "%": f"{pct}%"})
                st.dataframe(pd.DataFrame(tbl_perf).sort_values(by="Real", ascending=False), use_container_width=True)
            except: pass
            st.markdown("---")

        st.write("Visualização:")
        visao = st.radio("V", ["👥 Pessoas", "📏 Padrões"], horizontal=True, label_visibility="collapsed")
        st.markdown("---")

        if visao == "👥 Pessoas":
            total = df_esc['CPF'].nunique()
            cnt = {'P':0, 'A':0, 'C':0}
            d_list = []
            resps = {}
            if not df_rf.empty: resps = df_rf.groupby('CPF').size().to_dict()
            for cpf in df_esc['CPF'].unique():
                pads = df_esc[df_esc['CPF']==cpf]['Codigo_Padrao'].unique()
                mt = sum(metas.get(p,0) for p in pads)
                rl = resps.get(cpf, 0)
                if rl == 0: stt="🔴 Pendente"; cnt['P']+=1
                elif rl >= mt and mt>0: stt="🟢 Concluído"; cnt['C']+=1
                else: stt="🟡 Parcial"; cnt['A']+=1
                inf = df_esc[df_esc['CPF']==cpf].iloc[0]
                pct = int((rl/mt)*100) if mt>0 else 0
                d_list.append({"Filial":inf['Filial'], "Nome":inf['Nome_Funcionario'], "Status":stt, "Prog":f"{rl}/{mt} ({pct}%)"})
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Pessoas", total)
            c2.metric("Concluídos", cnt['C'])
            c3.metric("Parcial", cnt['A'])
            c4.metric("Pendentes", cnt['P'])
            st.progress(cnt['C']/total if total else 0)
            df_d = pd.DataFrame(d_list)
            if not df_d.empty:
                t1,t2,t3 = st.tabs(["🔴 Pendentes","🟡 Parciais","🟢 Concluídos"])
                with t1: st.dataframe(df_d[df_d['Status'].str.contains("Pendente")], use_container_width=True)
                with t2: st.dataframe(df_d[df_d['Status'].str.contains("Parcial")], use_container_width=True)
                with t3: st.dataframe(df_d[df_d['Status'].str.contains("Concluído")], use_container_width=True)
                st.download_button("📥 Baixar Status", gerar_excel(df_d), "Status_Pessoas.xlsx")

        else:
            tot_v = len(df_esc) 
            cnt_v = {'Z':0, 'I':0, 'C':0}
            v_data = []
            m_nom = {}
            if 'Nome_Padrao' in df_perguntas.columns:
                tn = df_perguntas[['Codigo_Padrao', 'Nome_Padrao']].drop_duplicates()
                m_nom = pd.Series(tn.Nome_Padrao.values, index=tn.Codigo_Padrao.astype(str).str.strip()).to_dict()
            r_det = {}
            if not df_rf.empty: r_det = df_rf.groupby(['CPF', 'Padrao']).size().to_dict()
            for _, r in df_esc.iterrows():
                c, p = r['CPF'], r['Codigo_Padrao']
                m = metas.get(p,0)
                rv = r_det.get((c,p), 0)
                if rv == 0: cnt_v['Z']+=1
                elif rv >= m and m>0: cnt_v['C']+=1
                else: cnt_v['I']+=1
            for p in df_esc['Codigo_Padrao'].unique():
                sub = df_esc[df_esc['Codigo_Padrao']==p]
                qm = len(sub)
                qo = 0
                for c in sub['CPF']:
                    m = metas.get(p,0)
                    if r_det.get((c,p),0) >= m and m>0: qo+=1
                pct = int((qo/qm)*100) if qm>0 else 0
                v_data.append({"Padrão":p, "Desc":m_nom.get(p,p), "Vol":qm, "Ok":qo, "%":f"{pct}%"})

            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Volume Total", tot_v)
            c2.metric("Concluídas", cnt_v['C'])
            c3.metric("Andamento", cnt_v['I'])
            c4.metric("Zero", cnt_v['Z'])
            st.progress(cnt_v['C']/tot_v if tot_v else 0)
            df_v = pd.DataFrame(v_data)
            st.dataframe(df_v, use_container_width=True)
            if not df_v.empty: st.download_button("📥 Baixar Volumetria", gerar_excel(df_v), "Status_Volume.xlsx")

        st.markdown("---")
        b1,b2 = st.columns([3,1])
        if not df_res.empty:
            out = BytesIO()
            with pd.ExcelWriter(out, engine='xlsxwriter') as writer: df_res.to_excel(writer, index=False)
            b1.download_button("📥 Baixar Master", out.getvalue(), f"Master_{obter_hora().replace('/','-')}.xlsx")
        
        if b2.button("🗑️ Limpar Tudo", key="trash_dash"):
            try:
                conn = st.connection("gsheets", type=GSheetsConnection)
                conn.update(worksheet="Respostas_DB", data=pd.DataFrame(columns=['Data']))
                st.session_state['resultados'] = []
                st.rerun()
            except: pass
