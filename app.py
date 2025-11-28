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
# NOVA MEMÓRIA DE PERMISSÕES
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

# --- LOGIN COM MEMÓRIA PERSISTENTE ---
df_auditores = None

if uploaded_file:
    try:
        xls = pd.ExcelFile(uploaded_file)
        if 'Cadastro_Auditores' in xls.sheet_names:
            df_auditores = pd.read_excel(uploaded_file, sheet_name='Cadastro_Auditores')
            df_auditores['CPF_Auditor'] = df_auditores['CPF_Auditor'].astype(str).str.strip()
            
            st.sidebar.markdown("---")
            
            # Se já estiver logado, mostra quem é
            if st.session_state['auditor_logado']:
                st.sidebar.success(f"Logado: {st.session_state['auditor_logado']['Nome']}")
                if st.sidebar.button("Sair"):
                    st.session_state['auditor_logado'] = None
                    st.session_state['permissoes'] = {'filiais': [], 'padroes': [], 'perfil': ''}
                    st.rerun()
            else:
                cpf = st.sidebar.text_input("Login (CPF)", type="password")
                if st.sidebar.button("Entrar"):
                    match = df_auditores[df_auditores['CPF_Auditor']==cpf.strip()]
                    if not match.empty:
                        user_data = match.iloc[0]
                        
                        # Processa Filiais
                        raw_fil = str(user_data.get('Filiais_Permitidas', 'Todas'))
                        if 'todas' in raw_fil.lower(): fils_perm = 'TODAS'
                        else: fils_perm = [x.strip() for x in raw_fil.split(',')]
                            
                        # Processa Padrões
                        raw_pad = str(user_data.get('Padroes_Permitidos', 'Todos'))
                        if 'todos' in raw_pad.lower() or 'todas' in raw_pad.lower(): pads_perm = 'TODOS'
                        else: pads_perm = [x.strip() for x in raw_pad.split(',')]

                        # SALVA NO COFRE
                        st.session_state['auditor_logado'] = {'Nome': user_data['Nome_Auditor'], 'CPF': cpf}
                        st.session_state['permissoes'] = {
                            'filiais': fils_perm, 
                            'padroes': pads_perm, 
                            'perfil': str(user_data.get('Perfil', 'Auditor')).strip()
                        }
                        st.rerun()
                    else:
                        st.sidebar.error("CPF não encontrado.")
        else:
            # Modo Legado
            st.session_state['auditor_logado'] = {'Nome': 'Geral', 'CPF': '000'}
            st.session_state['permissoes'] = {'filiais': 'TODAS', 'padroes': 'TODOS', 'perfil': 'Gestor'}
    except Exception as e: st.sidebar.warning(f"Erro Login: {e}")

# Sidebar Download
if st.session_state['resultados']:
    st.sidebar.markdown("---")
    st.sidebar.write("📂 **Exportar Dados**")
    df_dw = pd.DataFrame(st.session_state['resultados'])
    
    # Filtro de segurança no download
    perms = st.session_state['permissoes']
    if st.session_state['auditor_logado'] and perms['perfil'] != 'Gestor' and perms['filiais'] != 'TODAS':
        df_dw = df_dw[df_dw['Filial'].isin(perms['filiais'])]
    
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
        if 'Filial' in df_treinos.columns: df_treinos['Filial'] = df_treinos['Filial'].astype(str).str.strip()
        dados_ok = True
    except Exception as e: st.error(f"Erro Base: {e}")
        # ================= EXECUÇÃO =================
if pagina == "📝 EXECUTAR DTO 01":
    if not dados_ok: st.info("👈 Carregue a Base.")
    elif df_auditores is not None and st.session_state['auditor_logado'] is None:
        st.warning("🔒 Acesso Bloqueado. Faça login na barra lateral.")
    else:
        st.title("📝 EXECUTAR DTO 01")
        st.sidebar.header("Filtros Execução")
        
        perms = st.session_state['permissoes']
        
        # Filtros Blindados
        todas_f_base = df_treinos['Filial'].dropna().unique()
        if perms['filiais'] == 'TODAS':
            opts_f = sorted(todas_f_base)
        else:
            opts_f = sorted([f for f in todas_f_base if f in perms['filiais']])
            
        sel_fil = st.sidebar.multiselect("Selecione Filiais", opts_f, default=opts_f if len(opts_f)==1 else None)
        
        todas_p_base = df_perguntas['Codigo_Padrao'].dropna().unique()
        if perms['padroes'] == 'TODOS':
            opts_p = todas_p_base
        else:
            opts_p = [p for p in todas_p_base if str(p) in perms['padroes']]
            
        sel_pad = list(opts_p) if st.sidebar.checkbox("Todos Meus Padrões", key="pe") else st.sidebar.multiselect("Padrões", opts_p)

        if sel_fil and sel_pad:
            df_m = df_treinos[(df_treinos['Filial'].isin(sel_fil)) & (df_treinos['Codigo_Padrao'].isin(sel_pad))]
            
            if df_m.empty: st.warning("Sem dados para o seu perfil.")
            else:
                # Mapas
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
                                        reg
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
        
        # Filtros Blindados
        todas_f_base = df_treinos['Filial'].unique()
        if perms['filiais'] == 'TODAS':
            opts_f = sorted(todas_f_base)
        else:
            opts_f = sorted([f for f in todas_f_base if f in perms['filiais']])
            
        f_sel = st.sidebar.multiselect("Filiais", opts_f, default=opts_f)
        
        todas_p_base = df_perguntas['Codigo_Padrao'].unique()
        if perms['padroes'] == 'TODOS':
            opts_p = todas_p_base
        else:
            opts_p = [p for p in todas_p_base if str(p) in perms['padroes']]
            
        p_sel = st.sidebar.multiselect("Padrões", opts_p, default=opts_p)
        
        st.markdown("---")
        
        df_esc = df_treinos[(df_treinos['Filial'].isin(f_sel)) & (df_treinos['Codigo_Padrao'].isin(p_sel))]
        
        df_res = pd.DataFrame(st.session_state['resultados'])
        df_rf = pd.DataFrame()
        if not df_res.empty:
            if 'Filial' in df_res.columns and 'Padrao' in df_res.columns:
                df_rf = df_res[(df_res['Filial'].isin(f_sel)) & (df_res['Padrao'].isin(p_sel))]
        
        aux_meta = df_perguntas.groupby('Codigo_Padrao').size()
        aux_meta.index = aux_meta.index.astype(str).str.strip()
        metas = aux_meta.to_dict()
        
        st.write("Visualização:")
        visao = st.radio("V", ["👥 Por Pessoa", "📏 Por Padrão"], horizontal=True, label_visibility="collapsed")
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
                meta = sum(metas.get(p,0) for p in pads)
                real = resps.get(cpf, 0)
