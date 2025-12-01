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

# --- 4. BARRA LATERAL E CONEXÃO ---
st.sidebar.header("1. Conexão")
if os.path.exists("logo.png"): st.sidebar.image("logo.png", use_container_width=True)
else: st.sidebar.write("🏢 DTO 01 - DCS SCANIA")

# --- CONEXÃO GOOGLE SHEETS (AUTOMÁTICA) ---
dados_ok = False
df_treinos = pd.DataFrame()
df_perguntas = pd.DataFrame()
df_auditores = None

try:
    # Cria a conexão usando os Segredos
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    with st.spinner('Conectando à Base DCS Scania...'):
        # Lê as abas diretamente da nuvem (TTL de 10 min para cache)
        df_treinos = conn.read(worksheet="Base_Treinamentos", ttl=600)
        df_perguntas = conn.read(worksheet="Padroes_Perguntas", ttl=600)
        
        # Tenta ler auditores (se existir)
        try:
            df_auditores = conn.read(worksheet="Cadastro_Auditores", ttl=600)
        except:
            df_auditores = None

        # Normalização de Dados (Limpeza)
        for df in [df_treinos, df_perguntas]:
            # Remove linhas vazias
            df.dropna(how='all', inplace=True)
            # Limpa colunas
            df.columns = [c.strip() for c in df.columns]
            for col in df.columns:
                if col in ['CPF', 'Codigo_Padrao', 'Filial', 'Pergunta', 'Nome_Padrao']:
                    df[col] = df[col].astype(str).str.strip()
        
        if df_auditores is not None:
            df_auditores.dropna(how='all', inplace=True)
            df_auditores.columns = [c.strip() for c in df_auditores.columns]
            # Acha coluna CPF
            col_cpf = achar_coluna(df_auditores, 'cpf')
            if col_cpf: df_auditores[col_cpf] = df_auditores[col_cpf].astype(str).str.strip()

        dados_ok = True
        st.sidebar.success("✅ Base Conectada (Google Cloud)")
        
except Exception as e:
    st.sidebar.error(f"Erro de Conexão: {e}")
    st.sidebar.info("Verifique se a planilha tem as abas: Base_Treinamentos, Padroes_Perguntas")

# Upload Histórico (Mantido Manual por enquanto)
st.sidebar.markdown("---")
uploaded_hist = st.sidebar.file_uploader("Carregar Histórico (Opcional)", type=["xlsx"], key="hist", accept_multiple_files=True)

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
    except Exception as e: st.sidebar.error(f"Erro Histórico: {e}")

# --- LOGIN (VIA GOOGLE SHEETS) ---
auditor_valido = None
if dados_ok and df_auditores is not None:
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
        cpf_input = st.sidebar.text_input("CPF (Apenas números)", type="password")
        if st.sidebar.button("Entrar"):
            col_cpf = achar_coluna(df_auditores, 'cpf')
            if col_cpf:
                match = df_auditores[df_auditores[col_cpf]==cpf_input.strip()]
                if not match.empty:
                    dados = match.iloc[0]
                    # Mapeamento
                    c_nome = achar_coluna(df_auditores, 'nome') or col_cpf
                    c_perf = achar_coluna(df_auditores, 'perfil')
                    c_fil = achar_coluna(df_auditores, 'filiais')
                    c_pad = achar_coluna(df_auditores, 'padroes')
                    if not c_pad: c_pad = achar_coluna(df_auditores, 'padrões')

                    nome = dados[c_nome]
                    perfil = str(dados[c_perf]).strip() if c_perf else 'Auditor'
                    
                    # Filiais
                    raw_fil = str(dados.get(c_fil, 'Todas')) if c_fil else 'Todas'
                    if 'todas' in raw_fil.lower() or raw_fil=='nan': fils_perm = 'TODAS'
                    else: fils_perm = [x.strip() for x in raw_fil.split(',')]
                    
                    # Padrões
                    raw_pad = str(dados.get(c_pad, 'Todos')) if c_pad else 'Todos'
                    if 'todos' in raw_pad.lower() or raw_pad=='nan': pads_perm = 'TODOS'
                    else: pads_perm = [x.strip() for x in raw_pad.split(',')]

                    st.session_state['auditor_logado'] = {'Nome': nome, 'CPF': cpf_input}
                    st.session_state['permissoes'] = {'filiais': fils_perm, 'padroes': pads_perm, 'perfil': perfil}
                    st.rerun()
                else: st.sidebar.error("CPF não encontrado.")
elif dados_ok:
    # Fallback se não tiver aba Auditores
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
    if not dados_ok: st.info("⏳ Conectando à base de dados...")
    elif df_auditores is not None and st.session_state['auditor_logado'] is None:
        st.warning("🔒 Acesso Bloqueado. Faça login na barra lateral.")
    else:
        st.title("📝 EXECUTAR DTO 01")
        perms = st.session_state['permissoes']
        st.sidebar.header("Filtros Execução")
        
        # Filtros
        todas_f = sorted(df_treinos['Filial'].dropna().unique())
        if perms['filiais'] == 'TODAS': opts_f = todas_f
        else: opts_f = sorted([f for f in todas_f if f in perms['filiais']])
        sel_fil = st.sidebar.multiselect("Selecione Filiais", opts_f, default=opts_f if len(opts_f)==1 else None)
        
        todas_p = sorted(df_perguntas['Codigo_Padrao'].dropna().unique())
        if perms['padroes'] == 'TODOS': opts_p = todas_p
        else: opts_p = sorted([p for p in todas_p if str(p) in perms['padroes']])
        sel_pad = list(opts_p) if st.sidebar.checkbox("Todos Meus Padrões", key="pe") else st.sidebar.multiselect("Padrões", opts_p)

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
                if c1.button("⬅️") and st.session_state['pagina_atual']>0: st.session_state['pagina_atual']-=1; st.rerun()
                if c3.button("➡️") and st.session_state['pagina_atual']<tot_p-1: st.session_state['pagina_atual']+=1; st.rerun()
                c2.markdown(f"<div style='text-align:center'>Pág {st.session_state['pagina_atual']+1}/{tot_p}</div>", unsafe_allow_html=True)
                
                pg_rank = rank.iloc[st.session_state['pagina_atual']*10 : (st.session_state['pagina_atual']+1)*10]
                mem = {f"{str(r.get('CPF','')).strip()}_{str(r.get('Padrao','')).strip()}_{str(r.get('Pergunta','')).strip()}": {'res':r.get('Resultado'),'obs':r.get('Observacao')} for r in st.session_state['resultados']}
                
                for _, row in pg_rank.iterrows():
                    cpf, nome, fil = str(row['CPF']).strip(), row['Nome_Funcionario'], row['Filial']
                    qtd_pads = row['Qtd']
                    
                    pads_no_filtro = df_m[df_m['CPF'].astype(str).str.strip() == cpf]['Codigo_Padrao'].unique()
                    pads_no_filtro = [str(p).strip() for p in pads_no_filtro]
                    meta_total = sum(dict_metas.get(p,0) for p in pads_no_filtro)
                    
                    resp_tot = 0
                    for r in st.session_state['resultados']:
                        if str(r.get('CPF','')).strip() == cpf and str(r.get('Padrao','')).strip() in pads_no_filtro: resp_tot += 1
                    
                    if resp_tot == 0: icon = "⚪"
                    elif resp_tot >= meta_total and meta_total > 0: icon = "🟢"
                    else: icon = "🟡"
                    
                    with st.expander(f"{icon} {nome} | {fil} ({qtd_pads} Padrões | {resp_tot}/{meta_total})"):
                        with st.form(key=f"f_{cpf}"):
                            c_top, _ = st.columns([1, 4])
                            submit_top = c_top.form_submit_button("💾 Salvar", key=f"t_{cpf}")
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
                                    resps[k_wd] = st.radio("R", ["Conforme", "Não Conforme", "Não se Aplica"], key=k_wd, horizontal=True, index=idx_r, label_visibility="collapsed")
                                    obss[k_wd] = st.text_input("Obs", value=(prev['obs'] if prev else ""), key=f"o_{k_wd}")
                                    st.markdown("---")
                            
                            s_bot = st.form_submit_button("💾 Salvar", key=f"b_{cpf}")
                            if submit_top or s_bot:
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
                st.markdown("---")
                if st.session_state['resultados']:
                    st.subheader("📋 Resumo")
                    st.dataframe(pd.DataFrame(st.session_state['resultados']), use_container_width=True)
                    if st.button("🗑️ Apagar Tudo", type="primary"): st.session_state['resultados']=[]; st.rerun()
                       # ================= PAINEL =================
elif pagina == "📊 Painel Gerencial":
    st.title("📊 Painel Gerencial")
    if not dados_ok: st.info("⏳ Conectando à base...")
    elif df_auditores is not None and st.session_state['auditor_logado'] is None: st.warning("🔒 Faça Login.")
    else:
        perms = st.session_state['permissoes']
        with st.expander("🔍 Raio-X", expanded=False):
            colisao = df_treinos.groupby('CPF')['Nome_Funcionario'].nunique()
            errados = colisao[colisao > 1]
            if not errados.empty: st.error(f"CPFs Duplicados: {len(errados)}")
            else: st.success("Base OK.")

        st.sidebar.header("Filtros Dashboard")
        todas_f = sorted(df_treinos['Filial'].dropna().unique())
        if perms['filiais'] == 'TODAS': opts_f = todas_f
        else: opts_f = sorted([f for f in todas_f if f in perms['filiais']])
        f_sel = st.sidebar.multiselect("Filiais", opts_f, default=opts_f)
        
        todas_p = sorted(df_perguntas['Codigo_Padrao'].dropna().unique())
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
        
        # Performance Auditor (Gestor)
        if perms.get('perfil') == 'Gestor' and df_auditores is not None:
            st.subheader("🏆 Performance Operacional")
            try:
                tbl_perf = []
                for _, u_row in df_auditores.iterrows():
                    u_nome = u_row['Nome_Auditor']
                    # Ignora gestores na lista
                    if 'gestor' in str(u_row.get('Perfil','')).lower(): continue
                    
                    # Meta
                    u_fils = str(u_row.get('Filiais_Permitidas','Todas'))
                    u_f_list = list(df_treinos['Filial'].unique()) if 'todas' in u_fils.lower() else [x.strip() for x in u_fils.split(',')]
                    
                    u_pads = str(u_row.get('Padroes_Permitidos','Todos'))
                    u_p_list = list(df_perguntas['Codigo_Padrao'].unique()) if 'todos' in u_pads.lower() else [x.strip() for x in u_pads.split(',')]
                    
                    df_uni = df_treinos[(df_treinos['Filial'].isin(u_f_list)) & (df_treinos['Codigo_Padrao'].isin(u_p_list))]
                    meta_aud = 0
                    for _, r in df_uni.iterrows(): meta_aud += metas.get(str(r['Codigo_Padrao']).strip(),0)
                    
                    real_aud = 0
                    if not df_rf.empty and 'Auditor_Nome' in df_rf.columns:
                        real_aud = len(df_rf[df_rf['Auditor_Nome'] == u_nome])
                    
                    pend_aud = meta_aud - real_aud
                    if pend_aud < 0: pend_aud = 0
                    pct = int((real_aud/meta_aud)*100) if meta_aud > 0 else 0
                    tbl_perf.append({"Auditor": u_nome, "Meta": meta_aud, "Realizado": real_aud, "Pendente": pend_aud, "%": f"{pct}%"})
                
                st.dataframe(pd.DataFrame(tbl_perf).sort_values(by="Realizado", ascending=False), use_container_width=True, hide_index=True)
            except: st.info("Cadastros incompletos para ranking.")
            st.markdown("---")

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
                if real == 0: stt="🔴 Pendente"; counts['P']+=1
                elif real >= meta and meta>0: stt="🟢 Concluído"; counts['C']+=1
                else: stt="🟡 Parcial"; counts['A']+=1
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
                with t1: st.dataframe(df_d[df_d['Status'].str.contains("Pendente")], use_container_width=True)
                with t2: st.dataframe(df_d[df_d['Status'].str.contains("Parcial")], use_container_width=True)
                with t3: st.dataframe(df_d[df_d['Status'].str.contains("Concluído")], use_container_width=True)
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
