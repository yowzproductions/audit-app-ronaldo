import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
import os
import gspread
import pytz
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="DTO - DCS SCANIA", page_icon="🚛", layout="wide")

# Ciclo usado para linhas antigas que ainda não têm a coluna "DTO" preenchida
DTO_PADRAO = "DTO 01"

def norm_dto(v):
    s = str(v).strip() if v is not None else ""
    return DTO_PADRAO if s in ("", "nan", "None") else s

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

def limpar_texto(df, coluna):
    if coluna in df.columns:
        df[coluna] = df[coluna].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    return df

# --- CACHE INTELIGENTE ---
@st.cache_data(ttl=600, show_spinner="Lendo Bases...")
def carregar_bases_estaticas():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df_t = conn.read(worksheet="Base_Treinamentos")
        df_p = conn.read(worksheet="Padroes_Perguntas")
        try: df_a = conn.read(worksheet="Cadastro_Auditores")
        except: df_a = None
        
        # Limpeza
        for df in [df_t, df_p]:
            df.dropna(how='all', inplace=True)
            df.columns = [c.strip() for c in df.columns]
            col_f = achar_coluna(df, 'filial'); 
            if col_f: df = limpar_texto(df, col_f)
            col_c = achar_coluna(df, 'cpf'); 
            if col_c: df = limpar_texto(df, col_c)
            col_p = achar_coluna(df, 'padrao') or achar_coluna(df, 'codigo'); 
            if col_p: df = limpar_texto(df, col_p)
            col_pg = achar_coluna(df, 'pergunta'); 
            if col_pg: df = limpar_texto(df, col_pg)

        # Coluna DTO: obrigatória nas perguntas (sem ela, tudo vira DTO 01).
        # Em Base_Treinamentos é opcional: sem a coluna, a base vale para todos os DTOs.
        if 'DTO' not in df_p.columns: df_p['DTO'] = DTO_PADRAO
        df_p['DTO'] = df_p['DTO'].apply(norm_dto)
        if 'DTO' in df_t.columns: df_t['DTO'] = df_t['DTO'].apply(norm_dto)

        if df_a is not None:
            df_a.dropna(how='all', inplace=True)
            df_a.columns = [c.strip() for c in df_a.columns]
            c_cpf_aud = achar_coluna(df_a, 'cpf')
            if c_cpf_aud: df_a = limpar_texto(df_a, c_cpf_aud)
            
        return df_t, df_p, df_a, True
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), None, False

def carregar_respostas_nuvem():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        # Lemos tudo (TTL=0 garante que ele pegue o dado que acabamos de salvar)
        df = conn.read(worksheet="Respostas_DB", ttl=0)
        
        if df.empty: return pd.DataFrame()

        # 1. Limpeza de Colunas (Padrão)
        df.columns = [c.strip() for c in df.columns]
        for c in ['CPF', 'Padrao', 'Pergunta', 'Data']:
            if c in df.columns:
                df[c] = df[c].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        # Linhas antigas (sem DTO) contam como DTO 01
        if 'DTO' not in df.columns: df['DTO'] = DTO_PADRAO
        df['DTO'] = df['DTO'].apply(norm_dto)

        # 2. A MÁGICA (Deduplicação Inteligente)
        # Chave composta: Ciclo + Quem + Onde + O Que.
        # O DTO entra na chave para uma resposta do DTO 02 não sobrescrever a do DTO 01.
        if not df.empty and 'CPF' in df.columns and 'Padrao' in df.columns and 'Pergunta' in df.columns:
            df = df.drop_duplicates(subset=['DTO', 'CPF', 'Padrao', 'Pergunta'], keep='last')
        
        return df

    except Exception as e:
        # st.error(f"Erro silencioso nuvem: {e}") # Comentado para não sujar a tela
        return pd.DataFrame()

# --- 4. BARRA LATERAL ---
st.sidebar.header("1. Conexão")
if os.path.exists("logo.png"): st.sidebar.image("logo.png", use_container_width=True)
else: st.sidebar.write("🏢 DTO - DCS SCANIA")

# Carga Inicial
df_treinos, df_perguntas, df_auditores, dados_ok = carregar_bases_estaticas()

if dados_ok:
    st.sidebar.success("✅ Base Conectada")
    if not st.session_state['lista_auditores'] and df_auditores is not None:
        c_nome = achar_coluna(df_auditores, 'nome')
        if c_nome: st.session_state['lista_auditores'] = df_auditores[c_nome].unique().tolist()
    
    # Sincronia Automática da Nuvem
    if not st.session_state['resultados']:
        df_cloud = carregar_respostas_nuvem()
        if not df_cloud.empty:
            df_cloud.columns = [c.strip() for c in df_cloud.columns]
            for c in df_cloud.columns: df_cloud = limpar_texto(df_cloud, c)
            st.session_state['resultados'] = df_cloud.to_dict('records')
            st.sidebar.info(f"☁️ {len(st.session_state['resultados'])} registros.")
else:
    st.sidebar.warning("Tentando reconectar...")
    if st.sidebar.button("Forçar Recarga"): 
        st.cache_data.clear()
        st.rerun()

# Login Inteligente
if dados_ok:
    if df_auditores is not None:
        col_cpf = achar_coluna(df_auditores, 'cpf')
        if col_cpf:
            st.sidebar.markdown("---")
            if st.session_state['auditor_logado']:
                user = st.session_state['auditor_logado']
                perms = st.session_state['permissoes']
                st.sidebar.success(f"👤 {user['Nome']}")
                
                if st.sidebar.button("Sair"):
                    st.session_state['auditor_logado'] = None
                    st.session_state['permissoes'] = {'filiais': [], 'padroes': [], 'perfil': ''}
                    st.rerun()
            else:
                st.sidebar.subheader("🔐 Login")
                cpf_in = st.sidebar.text_input("CPF (Apenas números)", type="password")
                if st.sidebar.button("Entrar"):
                    cpf_clean = cpf_in.replace('.','').replace('-','').strip()
                    match = df_auditores[df_auditores[col_cpf] == cpf_clean]
                    
                    if not match.empty:
                        dados = match.iloc[0]
                        c_nome = achar_coluna(df_auditores, 'nome') or col_cpf
                        c_perf = achar_coluna(df_auditores, 'perfil')
                        c_fil = achar_coluna(df_auditores, 'filia')
                        c_pad = achar_coluna(df_auditores, 'padrao')
                        c_dto = 'DTOs_Permitidos' if 'DTOs_Permitidos' in df_auditores.columns else None

                        nome = dados[c_nome]
                        perfil = str(dados.get(c_perf, 'Auditor')).strip() if c_perf else 'Auditor'
                        
                        raw_f = str(dados.get(c_fil, 'Todas')) if c_fil else 'Todas'
                        if 'todas' in raw_f.lower() or pd.isna(raw_f) or raw_f == 'nan':
                            fils_perm = 'TODAS'
                        else:
                            fils_perm = [x.strip() for x in raw_f.split(',')]
                            
                        raw_p = str(dados.get(c_pad, 'Todos')) if c_pad else 'Todos'
                        if 'todos' in raw_p.lower() or pd.isna(raw_p) or raw_p == 'nan':
                            pads_perm = 'TODOS'
                        else:
                            pads_perm = [x.strip() for x in raw_p.split(',')]

                        raw_d = str(dados.get(c_dto, 'Todos')) if c_dto else 'Todos'
                        if 'todos' in raw_d.lower() or raw_d.strip() in ('', 'nan'):
                            dtos_perm = 'TODOS'
                        else:
                            dtos_perm = [x.strip() for x in raw_d.split(',')]

                        st.session_state['auditor_logado'] = {'Nome': nome, 'CPF': cpf_clean}
                        st.session_state['permissoes'] = {'filiais': fils_perm, 'padroes': pads_perm, 'perfil': perfil, 'dtos': dtos_perm}
                        st.rerun()
                    else: st.sidebar.error("CPF não encontrado.")
    else:
        st.session_state['auditor_logado'] = {'Nome': 'Geral', 'CPF': '000'}
        st.session_state['permissoes'] = {'filiais': 'TODAS', 'padroes': 'TODOS', 'perfil': 'Gestor'}

st.sidebar.markdown("---")

# --- SELEÇÃO DO CICLO (DTO) ---
sel_dto = DTO_PADRAO
if dados_ok and not df_perguntas.empty:
    todos_dtos = sorted(df_perguntas['DTO'].unique())
    perm_dtos = st.session_state['permissoes'].get('dtos', 'TODOS')
    opts_dto = todos_dtos if perm_dtos == 'TODOS' else [d for d in todos_dtos if d in perm_dtos]
    if not opts_dto: opts_dto = [DTO_PADRAO]
    sel_dto = st.sidebar.selectbox("Ciclo:", opts_dto, key="sel_dto")
    if st.session_state.get('dto_anterior') != sel_dto:
        st.session_state['dto_anterior'] = sel_dto
        st.session_state['pagina_atual'] = 0

    # A partir daqui o app só enxerga o DTO escolhido
    df_perguntas = df_perguntas[df_perguntas['DTO'] == sel_dto]
    if 'DTO' in df_treinos.columns:
        df_treinos = df_treinos[df_treinos['DTO'] == sel_dto]

def resultados_dto():
    return [r for r in st.session_state['resultados'] if norm_dto(r.get('DTO')) == sel_dto]

pagina = st.sidebar.radio("Menu:", ["📝 EXECUTAR DTO", "📊 Painel Gerencial"])
# ================= EXECUÇÃO =================
if pagina == "📝 EXECUTAR DTO":
    if not dados_ok: st.info("⏳ Aguardando dados...")
    elif df_auditores is not None and st.session_state['auditor_logado'] is None:
        st.warning("🔒 Acesso Bloqueado. Faça login na barra lateral.")
    else:
        st.title(f"📝 EXECUTAR {sel_dto}")
        perms = st.session_state['permissoes']
        st.sidebar.header("Filtros Execução")
        
        c_fil_tr = achar_coluna(df_treinos, 'filial')
        todas_f = sorted(df_treinos[c_fil_tr].dropna().unique())
        if perms['filiais'] == 'TODAS': opts_f = todas_f
        else: opts_f = sorted([f for f in todas_f if f.strip() in perms['filiais']])
        sel_fil = st.sidebar.multiselect("Selecione Filiais", opts_f, default=opts_f if len(opts_f)==1 else None)
        
        c_pad_pg = achar_coluna(df_perguntas, 'padrao')
        todas_p = sorted(df_perguntas[c_pad_pg].dropna().unique())
        if perms['padroes'] == 'TODOS': opts_p = todas_p
        else: opts_p = sorted([p for p in todas_p if str(p).strip() in perms['padroes']])
            
        modo_busca = st.sidebar.radio("Modo de Busca:", ["Por Padrões", "Por Colaborador"])
        df_m = pd.DataFrame()
        sel_pad = []

        c_pad_tr = achar_coluna(df_treinos, 'padrao')
        c_nom_tr = achar_coluna(df_treinos, 'nome')
        c_cpf_tr = achar_coluna(df_treinos, 'cpf')

        if modo_busca == "Por Padrões":
            sel_pad = list(opts_p) if st.sidebar.checkbox("Todos Meus Padrões", key="pe") else st.sidebar.multiselect("Padrões", opts_p)
            if sel_fil and sel_pad:
                df_m = df_treinos[(df_treinos[c_fil_tr].isin(sel_fil)) & (df_treinos[c_pad_tr].isin(sel_pad))]
        else:
            if sel_fil:
                pessoas = sorted(df_treinos[df_treinos[c_fil_tr].isin(sel_fil)][c_nom_tr].unique())
                sel_pessoa = st.sidebar.selectbox("Selecione o Colaborador", pessoas)
                if sel_pessoa:
                    df_pessoa = df_treinos[(df_treinos[c_fil_tr].isin(sel_fil)) & (df_treinos[c_nom_tr]==sel_pessoa)]
                    if perms['padroes'] != 'TODOS':
                        df_pessoa = df_pessoa[df_pessoa[c_pad_tr].isin(perms['padroes'])]
                    df_m = df_pessoa
                    sel_pad = df_m[c_pad_tr].unique().tolist()

        if not df_m.empty:
            mapa_nomes = {}
            c_nom_pg = achar_coluna(df_perguntas, 'nome')
            if c_nom_pg:
                tn = df_perguntas[[c_pad_pg, c_nom_pg]].drop_duplicates()
                mapa_nomes = pd.Series(tn[c_nom_pg].values, index=tn[c_pad_pg].astype(str).str.strip()).to_dict()
            
            dict_metas = df_perguntas.groupby(c_pad_pg).size().to_dict()

            rank = df_m.groupby([c_cpf_tr,c_nom_tr,c_fil_tr]).size().reset_index(name='Qtd')
            if modo_busca == "Por Padrões":
                rank = rank.sort_values(by=['Qtd',c_fil_tr], ascending=[False,True])
            
            if 'pagina_atual' not in st.session_state: st.session_state['pagina_atual'] = 0
            tot_p = (len(rank)-1)//10 + 1
            c1,c2,c3 = st.columns([1,3,1])
            if c1.button("⬅️") and st.session_state['pagina_atual']>0: st.session_state['pagina_atual']-=1; st.rerun()
            if c3.button("➡️") and st.session_state['pagina_atual']<tot_p-1: st.session_state['pagina_atual']+=1; st.rerun()
            c2.markdown(f"<div style='text-align:center'>Pág {st.session_state['pagina_atual']+1}/{tot_p}</div>", unsafe_allow_html=True)
            
            pg_rank = rank.iloc[st.session_state['pagina_atual']*10 : (st.session_state['pagina_atual']+1)*10]
            
            res_dto = resultados_dto()
            mem = {}
            for r in res_dto:
                c_r = str(r.get('CPF', r.get('cpf', ''))).strip()
                p_r = str(r.get('Padrao', r.get('padrao', ''))).strip()
                t_r = str(r.get('Pergunta', r.get('pergunta', ''))).strip()
                mem[f"{c_r}_{p_r}_{t_r}"] = {'res':r.get('Resultado'),'obs':r.get('Observacao')}
            
            for _, row in pg_rank.iterrows():
                cpf, nome, fil = str(row[c_cpf_tr]).strip(), row[c_nom_tr], row[c_fil_tr]
                qtd_pads = row['Qtd']
                
                pads_nf = df_m[df_m[c_cpf_tr].astype(str).str.strip() == cpf][c_pad_tr].unique()
                pads_nf = [str(p).strip() for p in pads_nf]
                meta_total = sum(dict_metas.get(p,0) for p in pads_nf)
                
                resp_tot = 0
                for r in res_dto:
                    if str(r.get('CPF','')).strip() == cpf and str(r.get('Padrao','')).strip() in pads_nf: resp_tot += 1
                
                if resp_tot == 0: icon = "⚪"
                elif resp_tot >= meta_total and meta_total > 0: icon = "🟢"
                else: icon = "🟡"
                
                abrir_auto = True if modo_busca == "Por Colaborador" else False
                
                with st.expander(f"{icon} {nome} | {fil} ({qtd_pads} Padrões | {resp_tot}/{meta_total})", expanded=abrir_auto):
                    with st.form(key=f"f_{cpf}"):
                        alerta_topo = st.empty()
                        c_top, _ = st.columns([1, 4])
                        submit_top = c_top.form_submit_button("💾 Salvar na Nuvem", key=f"t_{cpf}")
                        st.markdown("---")
                        resps, obss = {}, {}
                        pads_orig = df_m[df_m[c_cpf_tr].astype(str).str.strip() == cpf][c_pad_tr].unique()
                        for p in pads_orig:
                            p_str = str(p).strip()
                            st.markdown(f"**{p_str} - {mapa_nomes.get(p_str, '')}**")
                            pergs = df_perguntas[df_perguntas[c_pad_pg].astype(str).str.strip() == p_str]
                            for idx, pr in pergs.iterrows():
                                c_perg = achar_coluna(df_perguntas, 'pergunta')
                                txt, k_wd = pr[c_perg], f"{cpf}_{p_str}_{idx}"
                                prev = mem.get(f"{cpf}_{p_str}_{txt}")
                                ir = ["Conforme","Não Conforme","Não se Aplica"].index(prev['res']) if prev and prev['res'] in ["Conforme","Não Conforme","Não se Aplica"] else None
                                st.write(txt)
                                resps[k_wd] = st.radio("R", ["Conforme", "Não Conforme", "Não se Aplica"], key=k_wd, horizontal=True, index=ir, label_visibility="collapsed")
                                obss[k_wd] = st.text_input("Obs (Obrigatório se NC)", value=(prev['obs'] if prev else ""), key=f"o_{k_wd}")
                                st.markdown("---")
                        
                        alerta_fim = st.empty()
                        s_bot = st.form_submit_button("💾 Salvar na Nuvem", key=f"b_{cpf}")
                        if submit_top or s_bot:
                            dh = obter_hora()
                            novos = []
                            erro_val = False
                            lista_erros = []
                            
                            # --- 1. PARTE QUE MANTIVEMOS (Validação e Memória) ---
                            for k, v in resps.items():
                                # Verifica se é NC sem observação
                                if v == "Não Conforme" and not obss.get(k, "").strip():
                                    erro_val = True
                                    try:
                                        idx_e = int(k.rsplit('_', 1)[-1])
                                        c_pg_err = achar_coluna(df_perguntas, 'pergunta')
                                        txt_e = df_perguntas.loc[idx_e, c_pg_err]
                                        pad_e = k.split('_')[1]
                                        lista_erros.append(f"**PADRÃO {pad_e}:** {txt_e}")
                                    except: lista_erros.append("Item sem observação")
                                
                                if v:
                                    _, pr, ir = k.split('_', 2)
                                    c_pg = achar_coluna(df_perguntas, 'pergunta')
                                    try: pt = df_perguntas.loc[int(ir), c_pg]
                                    except: pt = "Erro"
                                    
                                    # Limpa resposta anterior da memória local
                                    st.session_state['resultados'] = [r for r in st.session_state['resultados'] if not (norm_dto(r.get('DTO'))==sel_dto and str(r.get('CPF','')).strip()==cpf and str(r.get('Padrao','')).strip()==str(pr).strip() and str(r.get('Pergunta','')).strip()==pt)]
                                    
                                    reg = {"DTO":sel_dto, "Data":dh, "Filial":fil, "Funcionario":nome, "CPF":cpf, "Padrao":str(pr).strip(), "Pergunta":pt, "Resultado":v, "Observacao":obss.get(k,"")}
                                    if st.session_state['auditor_logado']: reg.update({"Auditor_Nome":st.session_state['auditor_logado']['Nome'], "Auditor_CPF":st.session_state['auditor_logado']['CPF']})
                                    
                                    novos.append(reg)
                            
                            # Exibe erros se houver
                            if erro_val:
                                msg_erro = "⛔ **ERRO: PREENCHIMENTO OBRIGATÓRIO!**\n\nVocê marcou 'Não Conforme' nos itens abaixo sem justificativa:\n\n" + "\n".join([f"- {e}" for e in lista_erros])
                                alerta_topo.error(msg_erro)
                                alerta_fim.error(msg_erro)
                            
                            # --- 2. PARTE QUE MUDAMOS (O Salvamento Seguro - Append) ---
                            elif novos:
                                try:
                                    # Preparar dados para o formato de lista
                                    # DTO vai na 11ª coluna (K) do Respostas_DB, depois das que já existem
                                    colunas_ordem = ["Data", "Filial", "Funcionario", "CPF", "Padrao", "Pergunta", "Resultado", "Observacao", "Auditor_Nome", "Auditor_CPF", "DTO"]
                                    
                                    valores_para_adicionar = []
                                    for item in novos:
                                        linha = [str(item.get(c, "")) for c in colunas_ordem]
                                        valores_para_adicionar.append(linha)

                                    # Conexão Direta usando gspread (Mais Rápido e Seguro)
                                    creds = st.secrets["connections"]["gsheets"]
                                    gc = gspread.service_account_from_dict(creds)
                                    
                                    # Abrir planilha pela URL
                                    sh = gc.open_by_url(creds["spreadsheet"])
                                    wks = sh.worksheet("Respostas_DB")
                                    
                                    # Mágica: Adicionar ao final (Append)
                                    wks.append_rows(valores_para_adicionar, value_input_option="USER_ENTERED")
                                    
                                    # Atualiza memória local
                                    st.session_state['resultados'].extend(novos)
                                    
                                    st.success(f"✅ Salvo com Sucesso! ({len(novos)} atualizações)")
                                    
                                    import time
                                    time.sleep(1)
                                    st.rerun()
                                    
                                except Exception as e:
                                    st.error(f"❌ Erro ao Salvar: {e}")
                                    df_bck = pd.DataFrame(novos)
                                    st.download_button("🚨 Baixar Backup Local", gerar_excel(df_bck), "Backup_Erro.xlsx")
            st.markdown("---")
            if resultados_dto():
                st.subheader(f"📋 Resumo Sessão - {sel_dto}")
                st.dataframe(pd.DataFrame(resultados_dto()), use_container_width=True)
        else: st.info("Selecione filtros.")
            # ================= PAINEL =================
elif pagina == "📊 Painel Gerencial":
    st.title(f"📊 Painel Gerencial - {sel_dto}")
    if not dados_ok: st.info("👈 Carregue a Base.")
    elif df_auditores is not None and st.session_state['auditor_logado'] is None: st.warning("🔒 Faça Login.")
    else:
        perms = st.session_state['permissoes']
        
        # --- DEFINIÇÃO DE COLUNAS (CORRIGIDO) ---
        c_fil_tr = achar_coluna(df_treinos, 'filial')
        c_pad_tr = achar_coluna(df_treinos, 'padrao') # <--- ESTA LINHA FALTAVA
        c_cpf_tr = achar_coluna(df_treinos, 'cpf')
        c_nom_tr = achar_coluna(df_treinos, 'nome')
        c_pad_pg = achar_coluna(df_perguntas, 'padrao')

        with st.expander("🔍 Raio-X", expanded=False):
            colisao = df_treinos.groupby(c_cpf_tr)[c_nom_tr].nunique()
            errados = colisao[colisao > 1]
            if not errados.empty: st.error(f"CPFs Duplicados: {len(errados)}")
            else: st.success("Base OK.")

        st.sidebar.header("Filtros Dashboard")
        
        # Filtros Dinâmicos
        todas_f = sorted(df_treinos[c_fil_tr].dropna().unique())
        if perms['filiais'] == 'TODAS': opts_f = todas_f
        else: opts_f = sorted([f for f in todas_f if f.strip() in perms['filiais']])
        f_sel = st.sidebar.multiselect("Filiais", opts_f, default=opts_f)
        
        todas_p = sorted(df_perguntas[c_pad_pg].dropna().unique())
        if perms['padroes'] == 'TODOS': opts_p = todas_p
        else: opts_p = sorted([p for p in todas_p if str(p).strip() in perms['padroes']])
        p_sel = st.sidebar.multiselect("Padrões", opts_p, default=opts_p)
        
        st.markdown("---")
        
        # Agora c_pad_tr existe para fazer o filtro
        df_esc = df_treinos[(df_treinos[c_fil_tr].isin(f_sel)) & (df_treinos[c_pad_tr].isin(p_sel))]
        
        df_res = pd.DataFrame(resultados_dto())
        df_rf = pd.DataFrame()
        
        # Mapeia colunas do resultado
        c_fil_rs = None
        c_pad_rs = None
        c_cpf_rs = None
        
        if not df_res.empty:
            c_fil_rs = achar_coluna(df_res, 'filial')
            c_pad_rs = achar_coluna(df_res, 'padrao')
            c_cpf_rs = achar_coluna(df_res, 'cpf')
            c_aud_nm = achar_coluna(df_res, 'auditor_nome')
            
            if c_fil_rs and c_pad_rs:
                df_rf = df_res[(df_res[c_fil_rs].isin(f_sel)) & (df_res[c_pad_rs].isin(p_sel))]
        
        metas = df_perguntas.groupby(c_pad_pg).size().to_dict()

        # PERFORMANCE AUDITOR (GESTOR)
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
                    lf = list(df_treinos[c_fil_tr].unique()) if 'todas' in rf.lower() else [x.strip() for x in rf.split(',')]
                    rp = str(da.get(cp, 'Todos')) if cp else 'Todos'
                    lp = list(df_perguntas[c_pad_pg].unique()) if 'todos' in rp.lower() else [x.strip() for x in rp.split(',')]
                    
                    df_uni = df_treinos[(df_treinos[c_fil_tr].isin(lf)) & (df_treinos[c_pad_tr].isin(lp))]
                    meta_aud = sum(metas.get(str(r[c_pad_tr]),0) for _, r in df_uni.iterrows())
                    
                    r_aud = 0
                    if not df_rf.empty and c_aud_nm:
                        r_aud = len(df_rf[df_rf[c_aud_nm] == nm])
                    
                    pend = max(0, meta_aud - r_aud)
                    pct = int((r_aud/meta_aud)*100) if meta_aud > 0 else 0
                    tbl_perf.append({"Auditor": nm, "Meta": meta_aud, "Real": r_aud, "Pend": pend, "%": f"{pct}%"})
                st.dataframe(pd.DataFrame(tbl_perf).sort_values(by="Real", ascending=False), use_container_width=True)
            except: pass
            st.markdown("---")

        st.write("Visualização:")
        visao = st.radio("V", ["👥 Por Pessoa", "📏 Por Padrão"], horizontal=True, label_visibility="collapsed")
        st.markdown("---")

        if visao == "👥 Por Pessoa":
            total = df_esc[c_cpf_tr].nunique()
            counts = {'P':0, 'A':0, 'C':0}
            data_list = []
            resps = {}
            if not df_rf.empty and c_cpf_rs: resps = df_rf.groupby(c_cpf_rs).size().to_dict()
            
            for cpf in df_esc[c_cpf_tr].unique():
                pads = df_esc[df_esc[c_cpf_tr]==cpf][c_pad_tr].unique()
                meta = sum(metas.get(p,0) for p in pads)
                real = resps.get(cpf, 0)
                if real == 0: stt="🔴 Pendente"; counts['P']+=1
                elif real >= meta and meta>0: stt="🟢 Concluído"; counts['C']+=1
                else: stt="🟡 Parcial"; counts['A']+=1
                info = df_esc[df_esc[c_cpf_tr]==cpf].iloc[0]
                pct = int((real/meta)*100) if meta>0 else 0
                data_list.append({"Filial":info[c_fil_tr], "Nome":info[c_nom_tr], "Status":stt, "Prog":f"{real}/{meta} ({pct}%)"})
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Pessoas", total)
            c2.metric("Concluídos", counts['C'])
            c3.metric("Parcial", counts['A'])
            c4.metric("Pendentes", counts['P'])
            prog = counts['C']/total if total else 0
            st.progress(prog, f"Taxa: {int(prog*100)}%")
            df_d = pd.DataFrame(data_list)
            if not df_d.empty:
                t1,t2,t3 = st.tabs(["🔴 Pendentes","🟡 Parciais","🟢 Concluídos"])
                with t1: st.dataframe(df_d[df_d['Status'].str.contains("Pendente")], use_container_width=True)
                with t2: st.dataframe(df_d[df_d['Status'].str.contains("Parcial")], use_container_width=True)
                with t3: st.dataframe(df_d[df_d['Status'].str.contains("Concluído")], use_container_width=True)
                st.download_button("📥 Baixar Status", gerar_excel(df_d), "Status_Pessoas.xlsx")

        else:
            total_vol = len(df_esc) 
            counts_v = {'Z':0, 'I':0, 'C':0}
            vol_data = []
            mapa_nomes = {}
            c_nom_pg = achar_coluna(df_perguntas, 'nome')
            if c_nom_pg:
                tn = df_perguntas[[c_pad_pg, c_nom_pg]].drop_duplicates()
                mapa_nomes = pd.Series(tn[c_nom_pg].values, index=tn[c_pad_pg].astype(str).str.strip()).to_dict()
            r_det = {}
            if not df_rf.empty and c_cpf_rs and c_pad_rs: r_det = df_rf.groupby([c_cpf_rs, c_pad_rs]).size().to_dict()
            
            for _, r in df_esc.iterrows():
                c, p = r[c_cpf_tr], r[c_pad_tr]
                m = metas.get(p,0)
                rv = r_det.get((c,p), 0)
                if rv == 0: counts_v['Z']+=1
                elif rv >= m and m>0: counts_v['C']+=1
                else: counts_v['I']+=1
            
            for p in df_esc[c_pad_tr].unique():
                sub = df_esc[df_esc[c_pad_tr]==p]
                qm = len(sub)
                qok = 0
                for c in sub[c_cpf_tr]:
                    m = metas.get(p,0)
                    if r_det.get((c,p),0) >= m and m>0: qok+=1
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
            b1.download_button("📥 Baixar Master", out.getvalue(), f"Master_{sel_dto.replace(' ','')}_{obter_hora().replace('/','-')}.xlsx")
