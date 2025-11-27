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

def gerar_excel():
    if not st.session_state['resultados']: return None
    df = pd.DataFrame(st.session_state['resultados'])
    out = BytesIO()
    with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
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
df_auditores, auditor_valido = None, None
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
                    auditor_valido = {'Nome': match.iloc[0]['Nome_Auditor'], 'CPF': cpf}
                    st.sidebar.success(f"Olá, {auditor_valido['Nome']}!")
                else: st.sidebar.error("CPF Inválido")
        else: auditor_valido = {'Nome': 'Geral', 'CPF': '000'}
    except: pass

# --- ÁREA DE DOWNLOAD (Texto Simplificado) ---
if st.session_state['resultados']:
    st.sidebar.markdown("---")
    st.sidebar.write("📂 **Exportar Dados**") # Título mais amigável
    excel_data = gerar_excel()
    if excel_data:
        nome_arq = f"Auditoria_{obter_hora().replace('/','-').replace(':','h')}.xlsx"
        st.sidebar.download_button("📥 Baixar Planilha", excel_data, nome_arq, mime="application/vnd.ms-excel")

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
        dados_ok = True
    except Exception as e: st.error(f"Erro Base: {e}")
        # ================= EXECUÇÃO =================
if pagina == "📝 EXECUTAR DTO 01":
    if not dados_ok: st.info("👈 Carregue a Base.")
    elif df_auditores is not None and auditor_valido is None: st.warning("🔒 Faça Login.")
    else:
        st.title("📝 EXECUTAR DTO 01")
        st.sidebar.header("Filtros Execução")
        
        t_fil = df_treinos['Filial'].dropna().unique()
        sel_fil = st.sidebar.multiselect("Selecione a(s) Filial(is)", t_fil)
        
        t_pad = df_perguntas['Codigo_Padrao'].dropna().unique()
        sel_pad = list(t_pad) if st.sidebar.checkbox("Todos Padrões", key="pe") else st.sidebar.multiselect("Padrões", t_pad)

        if sel_fil and sel_pad:
            # Filtra Base
            df_m = df_treinos[(df_treinos['Filial'].isin(sel_fil)) & (df_treinos['Codigo_Padrao'].isin(sel_pad))]
            
            if df_m.empty: st.warning("Sem dados.")
            else:
                mapa_nomes = {}
                meta_por_padrao = df_perguntas.groupby('Codigo_Padrao').size().to_dict()
                
                if 'Nome_Padrao' in df_perguntas.columns:
                    tn = df_perguntas[['Codigo_Padrao', 'Nome_Padrao']].drop_duplicates()
                    mapa_nomes = pd.Series(tn.Nome_Padrao.values, index=tn.Codigo_Padrao).to_dict()

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
                    
                    pads_no_filtro = df_m[df_m['CPF']==cpf]['Codigo_Padrao'].unique()
                    meta_perguntas = sum(meta_por_padrao.get(p, 0) for p in pads_no_filtro)
                    respondidos = 0
                    for r in st.session_state['resultados']:
                        if str(r.get('CPF','')).strip() == cpf and str(r.get('Padrao','')).strip() in pads_no_filtro:
                            respondidos += 1
                    
                    if respondidos == 0: icon = "⚪"
                    elif respondidos >= meta_perguntas and meta_perguntas > 0: icon = "🟢"
                    else: icon = "🟡"
                    
                    with st.expander(f"{icon} {nome} | {fil} ({qtd_pads} Padrões)"):
                        pads = df_m[df_m['CPF']==cpf]['Codigo_Padrao'].unique()
                        with st.form(key=f"f_{cpf}"):
                            # --- BOTÃO TOPO (COM KEY ÚNICA) ---
                            col_save_top, _ = st.columns([1, 4])
                            submit_top = col_save_top.form_submit_button("💾 Salvar", key=f"save_top_{cpf}")
                            st.markdown("---")

                            resps, obss = {}, {}
                            for p in pads:
                                nome_p = mapa_nomes.get(p, "")
                                st.markdown(f"**{p} - {nome_p}**" if nome_p else f"**{p}**")
                                pergs = df_perguntas[df_perguntas['Codigo_Padrao']==p]
                                for idx, pr in pergs.iterrows():
                                    pt = pr['Pergunta']
                                    kb = f"{cpf}_{p}_{pt}"
                                    kw = f"{cpf}_{p}_{idx}"
                                    prev = mem.get(kb)
                                    idx_r = ["Conforme","Não Conforme","Não se Aplica"].index(prev['res']) if prev and prev['res'] in ["Conforme","Não Conforme","Não se Aplica"] else None
                                    st.write(pt)
                                    resps[kw] = st.radio("R", ["Conforme","Não Conforme","Não se Aplica"], key=kw, horizontal=True, index=idx_r, label_visibility="collapsed")
                                    obss[kw] = st.text_input("Obs", value=(prev['obs'] if prev else ""), key=f"obs_{kw}")
                                    st.markdown("---")
                            
                            # --- BOTÃO FIM (COM KEY ÚNICA) ---
                            submit_bottom = st.form_submit_button("💾 Salvar", key=f"save_bottom_{cpf}")
                            
                            if submit_top or submit_bottom:
                                dh = obter_hora()
                                cnt = 0
                                for k, v in resps.items():
                                    if v:
                                        _, pr, ir = k.split('_', 2)
                                        try: pt_txt = df_perguntas.loc[int(ir), 'Pergunta']
                                        except: pt_txt = "Erro"
                                        st.session_state['resultados'] = [r for r in st.session_state['resultados'] if not (str(r.get('CPF','')).strip()==cpf and str(r.get('Padrao','')).strip()==pr and str(r.get('Pergunta','')).strip()==pt_txt)]
                                        reg = {"Data":dh, "Filial":fil, "Funcionario":nome, "CPF":cpf, "Padrao":pr, "Pergunta":pt_txt, "Resultado":v, "Observacao":obss.get(k,"")}
                                        if auditor_valido: reg.update({"Auditor_Nome":auditor_valido['Nome'], "Auditor_CPF":auditor_valido['CPF']})
                                        st.session_state['resultados'].append(reg)
                                        cnt+=1
                                if cnt: st.success("Salvo!"); st.rerun()

# ================= PAINEL =================
elif pagina == "📊 Painel Gerencial":
    st.title("📊 Painel Gerencial")
    if not dados_ok: st.info("👈 Carregue a Base.")
    else:
        with st.expander("🔍 Raio-X (Erros de Cadastro)", expanded=False):
            colisao = df_treinos.groupby('CPF')['Nome_Funcionario'].nunique()
            errados = colisao[colisao > 1]
            if not errados.empty:
                st.error(f"CPFs Duplicados: {len(errados)}")
                for cpf_e in errados.index:
                    ns = df_treinos[df_treinos['CPF']==cpf_e]['Nome_Funcionario'].unique()
                    st.write(f"{cpf_e}: {', '.join(ns)}")
            else: st.success("Base OK.")

        st.sidebar.header("Filtros Dashboard")
        t_fil_d = df_treinos['Filial'].unique()
        f_sel = list(t_fil_d) if st.sidebar.checkbox("Todas Filiais", value=True, key="fa") else st.sidebar.multiselect("Filiais", t_fil_d, default=t_fil_d)
        
        t_pad_d = df_perguntas['Codigo_Padrao'].unique()
        p_sel = list(t_pad_d) if st.sidebar.checkbox("Todos Padrões", value=True, key="pa") else st.sidebar.multiselect("Padrões", t_pad_d, default=t_pad_d)
        
        st.markdown("---")
        
        df_esc = df_treinos[(df_treinos['Filial'].isin(f_sel)) & (df_treinos['Codigo_Padrao'].isin(p_sel))]
        total = df_esc['CPF'].nunique()
        concluidos = 0
        
        df_res = pd.DataFrame(st.session_state['resultados'])
        df_rf = pd.DataFrame()
        if not df_res.empty:
            if 'Filial' in df_res.columns and 'Padrao' in df_res.columns:
                df_rf = df_res[(df_res['Filial'].isin(f_sel)) & (df_res['Padrao'].isin(p_sel))]
        
        if not df_rf.empty and 'CPF' in df_rf.columns:
            resps = df_rf.groupby('CPF').size().to_dict()
            metas = df_perguntas.groupby('Codigo_Padrao').size().to_dict()
            for cpf in df_esc['CPF'].unique():
                pads = df_esc[df_esc['CPF']==cpf]['Codigo_Padrao'].unique()
                meta = sum(metas.get(p,0) for p in pads)
                if resps.get(cpf,0) >= meta and meta>0: concluidos+=1
        
        c1,c2 = st.columns(2)
        c1.metric("Total Pessoas", total)
        prog = concluidos/total if total else 0
        c2.metric("Concluídos", concluidos, f"{int(prog*100)}%")
        st.progress(prog)
        
        st.markdown("---")
        b1,b2 = st.columns([3,1])
        if not df_res.empty:
            out = BytesIO()
            with pd.ExcelWriter(out, engine='xlsxwriter') as writer: df_res.to_excel(writer, index=False)
            b1.download_button("📥 Baixar Excel", out.getvalue(), f"Master_{obter_hora().replace('/','-')}.xlsx")
        
        if b2.button("🗑️ Limpar Tudo"): st.session_state['resultados']=[]; st.rerun()
