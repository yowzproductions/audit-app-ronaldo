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

    # Padrões da Base_Treinamentos que não têm pergunta cadastrada neste DTO não aparecem
    # (senão o auditor vê um padrão vazio, sem nome e sem perguntas)
    _c_pad_tr = achar_coluna(df_treinos, 'padrao')
    _c_pad_pg = achar_coluna(df_perguntas, 'padrao')
    if _c_pad_tr and _c_pad_pg:
        _com_pergunta = set(df_perguntas[_c_pad_pg].astype(str).str.strip())
        _tem = df_treinos[_c_pad_tr].astype(str).str.strip().isin(_com_pergunta)
        df_treinos = df_treinos[_tem]

def resultados_dto():
    return [r for r in st.session_state['resultados'] if norm_dto(r.get('DTO')) == sel_dto]

# --- AUSÊNCIA DO COLABORADOR NO CICLO ---
# Gravada no Respostas_DB como UMA linha: Padrao = "AUSENTE", Pergunta = PERGUNTA_AUSENTE.
# Resultado "Colaborador Ausente" marca; "Ausência cancelada" desfaz (vale a última linha).
MARCA_AUSENTE = "AUSENTE"
PERGUNTA_AUSENTE = "Colaborador ausente no ciclo"
RES_AUSENTE = "Colaborador Ausente"
RES_AUSENCIA_CANCELADA = "Ausência cancelada"

def ausentes_dto():
    """cpf -> registro de ausência ativo no ciclo escolhido."""
    ult = {}
    for r in resultados_dto():
        if str(r.get('Padrao', '')).strip() == MARCA_AUSENTE:
            ult[str(r.get('CPF', '')).strip()] = r
    return {c: r for c, r in ult.items() if str(r.get('Resultado', '')).strip() == RES_AUSENTE}

def gravar_respostas(novos):
    """Grava no Respostas_DB (a partir da coluna A) e atualiza a memória da sessão. Levanta erro se falhar."""
    colunas_ordem = ["Data", "Filial", "Funcionario", "CPF", "Padrao", "Pergunta", "Resultado",
                     "Observacao", "Auditor_Nome", "Auditor_CPF", "DTO"]
    valores = [[str(item.get(c, "")) for c in colunas_ordem] for item in novos]
    creds = st.secrets["connections"]["gsheets"]
    gc = gspread.service_account_from_dict(creds)
    wks = gc.open_by_url(creds["spreadsheet"]).worksheet("Respostas_DB")
    # table_range="A1" força a gravação a começar na coluna A, mesmo que haja lixo em outras colunas
    wks.append_rows(valores, value_input_option="USER_ENTERED", table_range="A1")
    chaves = {(str(n['CPF']).strip(), str(n['Padrao']).strip(), str(n['Pergunta']).strip()) for n in novos}
    st.session_state['resultados'] = [
        r for r in st.session_state['resultados']
        if not (norm_dto(r.get('DTO')) == sel_dto and
                (str(r.get('CPF', '')).strip(), str(r.get('Padrao', '')).strip(), str(r.get('Pergunta', '')).strip()) in chaves)
    ]
    st.session_state['resultados'].extend(novos)
    st.session_state.pop('backup_erro', None)

def registro_base(fil, nome, cpf):
    reg = {"DTO": sel_dto, "Data": obter_hora(), "Filial": fil, "Funcionario": nome, "CPF": cpf}
    if st.session_state.get('auditor_logado'):
        reg.update({"Auditor_Nome": st.session_state['auditor_logado']['Nome'],
                    "Auditor_CPF": st.session_state['auditor_logado']['CPF']})
    return reg

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
        mostrar_concluidos = st.sidebar.checkbox("Mostrar quem já concluiu este ciclo", key="mostrar_concl",
                                                 help="Por padrão, quem já tem todas as perguntas respondidas neste DTO some da lista.")
        df_m = pd.DataFrame()
        sel_pad = []

        c_pad_tr = achar_coluna(df_treinos, 'padrao')
        c_nom_tr = achar_coluna(df_treinos, 'nome')
        c_cpf_tr = achar_coluna(df_treinos, 'cpf')
        c_perg = achar_coluna(df_perguntas, 'pergunta')
        OPCOES = ["Conforme", "Não Conforme", "Não se Aplica"]

        # --- O que já foi respondido neste ciclo ---
        res_dto = resultados_dto()
        mem = {}
        respondidas = {}  # cpf -> {(padrao, pergunta)}
        for r in res_dto:
            c_r = str(r.get('CPF', r.get('cpf', ''))).strip()
            p_r = str(r.get('Padrao', r.get('padrao', ''))).strip()
            t_r = str(r.get('Pergunta', r.get('pergunta', ''))).strip()
            mem[f"{c_r}_{p_r}_{t_r}"] = {'res': r.get('Resultado'), 'obs': r.get('Observacao')}
            if str(r.get('Resultado', '')).strip() in OPCOES:
                respondidas.setdefault(c_r, set()).add((p_r, t_r))

        perg_por_pad = {}
        for p_k, t_k in zip(df_perguntas[c_pad_pg].astype(str).str.strip(), df_perguntas[c_perg].astype(str).str.strip()):
            perg_por_pad.setdefault(p_k, set()).add((p_k, t_k))

        def progresso(cpf, pads):
            """Devolve (respondidas, total) considerando só as perguntas dos padrões informados."""
            req = set().union(*[perg_por_pad.get(str(p).strip(), set()) for p in pads]) if len(pads) else set()
            return len(req & respondidas.get(str(cpf).strip(), set())), len(req)

        aus = ausentes_dto()

        def concluido(cpf, pads):
            """Concluído = todas as perguntas respondidas OU registrado como ausente no ciclo."""
            if str(cpf).strip() in aus:
                return True
            feitas, total = progresso(cpf, pads)
            return total > 0 and feitas >= total

        contagem = None  # (concluidos, ausentes, faltam)
        if modo_busca == "Por Padrões":
            sel_pad = list(opts_p) if st.sidebar.checkbox("Todos Meus Padrões", key="pe") else st.sidebar.multiselect("Padrões", opts_p)
            if sel_fil and sel_pad:
                df_m = df_treinos[(df_treinos[c_fil_tr].isin(sel_fil)) & (df_treinos[c_pad_tr].isin(sel_pad))]
        else:
            if sel_fil:
                df_fil = df_treinos[df_treinos[c_fil_tr].isin(sel_fil)]
                if perms['padroes'] != 'TODOS':
                    df_fil = df_fil[df_fil[c_pad_tr].isin(perms['padroes'])]
                pessoas = []
                n_c = n_a = n_f = 0
                for nm_p, g in df_fil.groupby(c_nom_tr):
                    cpf_p = str(g[c_cpf_tr].iloc[0]).strip()
                    feito_p = concluido(cpf_p, g[c_pad_tr].unique())
                    if cpf_p in aus: n_a += 1
                    elif feito_p: n_c += 1
                    else: n_f += 1
                    if feito_p and not mostrar_concluidos:
                        continue
                    pessoas.append(nm_p)
                contagem = (n_c, n_a, n_f)
                pessoas = sorted(pessoas)
                sel_pessoa = st.sidebar.selectbox("Selecione o Colaborador", pessoas)
                if sel_pessoa:
                    df_m = df_fil[df_fil[c_nom_tr] == sel_pessoa]
                    sel_pad = df_m[c_pad_tr].unique().tolist()

        # Mensagem do último salvamento (a pessoa pode ter saído da lista)
        if st.session_state.get('msg_salvo'):
            st.success(st.session_state.pop('msg_salvo'))
        if st.session_state.get('backup_erro'):
            st.error(f"❌ O último salvamento falhou ({st.session_state.get('backup_erro_msg','')}). "
                     "Nada foi gravado na planilha. Baixe o backup e tente salvar de novo.")
            st.download_button("🚨 Baixar Backup Local", st.session_state['backup_erro'], "Backup_Erro.xlsx")

        def mostrar_contagem(c):
            n_c, n_a, n_f = c
            partes = [f"✅ **{n_c}** concluído(s)"]
            if n_a: partes.append(f"🚷 **{n_a}** ausente(s)")
            partes.append(f"⏳ **{n_f}** falta(m)")
            st.markdown(" &nbsp;·&nbsp; ".join(partes))

        if contagem: mostrar_contagem(contagem)

        if not df_m.empty:
            mapa_nomes = {}
            c_nom_pg = achar_coluna(df_perguntas, 'nome')
            if c_nom_pg:
                tn = df_perguntas[[c_pad_pg, c_nom_pg]].drop_duplicates()
                mapa_nomes = pd.Series(tn[c_nom_pg].values, index=tn[c_pad_pg].astype(str).str.strip()).to_dict()

            rank = df_m.groupby([c_cpf_tr,c_nom_tr,c_fil_tr]).size().reset_index(name='Qtd')
            if modo_busca == "Por Padrões":
                pads_cpf = df_m.groupby(df_m[c_cpf_tr].astype(str).str.strip())[c_pad_tr].unique().to_dict()
                cpfs_r = rank[c_cpf_tr].astype(str).str.strip()
                feito = cpfs_r.map(lambda c: concluido(c, pads_cpf.get(c, [])))
                eh_a = cpfs_r.isin(aus)
                mostrar_contagem((int((feito & ~eh_a).sum()), int(eh_a.sum()), int((~feito).sum())))
                if not mostrar_concluidos:
                    rank = rank[~feito]
                rank = rank.sort_values(by=['Qtd',c_fil_tr], ascending=[False,True])

            if rank.empty:
                st.success(f"🎉 Todos os colaboradores deste filtro já foram auditados em {sel_dto}.")

            if 'pagina_atual' not in st.session_state: st.session_state['pagina_atual'] = 0
            tot_p = max(1, (len(rank)-1)//10 + 1)
            if st.session_state['pagina_atual'] > tot_p-1: st.session_state['pagina_atual'] = 0
            c1,c2,c3 = st.columns([1,3,1])
            if c1.button("⬅️") and st.session_state['pagina_atual']>0: st.session_state['pagina_atual']-=1; st.rerun()
            if c3.button("➡️") and st.session_state['pagina_atual']<tot_p-1: st.session_state['pagina_atual']+=1; st.rerun()
            c2.markdown(f"<div style='text-align:center'>Pág {st.session_state['pagina_atual']+1}/{tot_p}</div>", unsafe_allow_html=True)

            pg_rank = rank.iloc[st.session_state['pagina_atual']*10 : (st.session_state['pagina_atual']+1)*10]

            for _, row in pg_rank.iterrows():
                cpf, nome, fil = str(row[c_cpf_tr]).strip(), row[c_nom_tr], row[c_fil_tr]
                qtd_pads = row['Qtd']

                pads_orig = df_m[df_m[c_cpf_tr].astype(str).str.strip() == cpf][c_pad_tr].unique()
                resp_tot, meta_total = progresso(cpf, pads_orig)

                reg_aus = aus.get(cpf)
                if reg_aus: icon = "⚫"
                elif resp_tot == 0: icon = "⚪"
                elif resp_tot >= meta_total and meta_total > 0: icon = "🟢"
                else: icon = "🟡"

                abrir_auto = True if modo_busca == "Por Colaborador" else False
                txt_aus = f" | 🚷 AUSENTE" if reg_aus else ""

                with st.expander(f"{icon} {nome} | {fil} ({qtd_pads} Padrões | {resp_tot}/{meta_total}){txt_aus}", expanded=abrir_auto):
                    # ---------- Colaborador ausente ----------
                    if reg_aus:
                        st.info(f"🚷 **Registrado como ausente neste ciclo** — {reg_aus.get('Observacao','')}  \n"
                                f"Por {reg_aus.get('Auditor_Nome','')} em {reg_aus.get('Data','')}")
                        if st.button("↩️ Desfazer ausência", key=f"desf_{cpf}"):
                            reg = registro_base(fil, nome, cpf)
                            reg.update({"Padrao": MARCA_AUSENTE, "Pergunta": PERGUNTA_AUSENTE,
                                        "Resultado": RES_AUSENCIA_CANCELADA, "Observacao": ""})
                            try:
                                gravar_respostas([reg])
                                st.session_state['msg_salvo'] = f"↩️ {nome}: ausência desfeita."
                            except Exception as e:
                                st.session_state['backup_erro'] = gerar_excel(pd.DataFrame([reg]))
                                st.session_state['backup_erro_msg'] = f"{nome}: {e}"
                            st.rerun()
                    elif st.checkbox("🚷 Colaborador ausente neste ciclo (férias, licença...)", key=f"aus_chk_{cpf}"):
                        with st.form(key=f"aus_{cpf}"):
                            justif = st.text_input("Motivo da ausência (obrigatório)", key=f"aus_just_{cpf}",
                                                   placeholder="Ex.: férias de 03/11 a 22/11")
                            if st.form_submit_button("🚷 Registrar ausência"):
                                if not justif.strip():
                                    st.error("Escreva o motivo da ausência.")
                                else:
                                    reg = registro_base(fil, nome, cpf)
                                    reg.update({"Padrao": MARCA_AUSENTE, "Pergunta": PERGUNTA_AUSENTE,
                                                "Resultado": RES_AUSENTE, "Observacao": justif.strip()})
                                    try:
                                        gravar_respostas([reg])
                                        st.session_state['msg_salvo'] = f"🚷 {nome}: registrado como ausente."
                                    except Exception as e:
                                        st.session_state['backup_erro'] = gerar_excel(pd.DataFrame([reg]))
                                        st.session_state['backup_erro_msg'] = f"{nome}: {e}"
                                    st.rerun()

                    with st.form(key=f"f_{cpf}"):
                        alerta_topo = st.empty()
                        c_top, _ = st.columns([1, 4])
                        submit_top = c_top.form_submit_button("💾 Salvar na Nuvem", key=f"t_{cpf}")
                        st.markdown("---")
                        resps, obss, nsa_pad = {}, {}, {}
                        for p in pads_orig:
                            p_str = str(p).strip()
                            st.markdown(f"**{p_str} - {mapa_nomes.get(p_str, '')}**")
                            pergs = df_perguntas[df_perguntas[c_pad_pg].astype(str).str.strip() == p_str]

                            # Já estava todo como NSA? Então o botão vem marcado.
                            prevs_pad = [mem.get(f"{cpf}_{p_str}_{t}") for t in pergs[c_perg]]
                            todo_nsa = len(prevs_pad) > 0 and all(pv and pv['res'] == "Não se Aplica" for pv in prevs_pad)
                            nsa_pad[p_str] = st.checkbox("🚫 Este padrão inteiro não se aplica",
                                                         value=todo_nsa, key=f"nsa_{cpf}_{p_str}",
                                                         help="Ao salvar, todas as perguntas deste padrão são gravadas como 'Não se Aplica', "
                                                              "independente do que estiver marcado abaixo.")

                            for idx, pr in pergs.iterrows():
                                txt, k_wd = pr[c_perg], f"{cpf}_{p_str}_{idx}"
                                prev = mem.get(f"{cpf}_{p_str}_{txt}")
                                ir = OPCOES.index(prev['res']) if prev and prev['res'] in OPCOES else None
                                st.write(txt)
                                resps[k_wd] = st.radio("R", OPCOES, key=k_wd, horizontal=True, index=ir, label_visibility="collapsed")
                                obss[k_wd] = st.text_input("Obs (Obrigatório se NC)", value=(prev['obs'] if prev and pd.notna(prev['obs']) else ""), key=f"o_{k_wd}")
                                st.markdown("---")

                        alerta_fim = st.empty()
                        s_bot = st.form_submit_button("💾 Salvar na Nuvem", key=f"b_{cpf}")
                        if submit_top or s_bot:
                            dh = obter_hora()
                            novos = []
                            lista_erros = []

                            for k, v in resps.items():
                                _, pr, ir = k.split('_', 2)
                                pr = str(pr).strip()
                                if nsa_pad.get(pr):
                                    v = "Não se Aplica"   # botão do padrão inteiro manda
                                if not v:
                                    continue
                                try: pt = df_perguntas.loc[int(ir), c_perg]
                                except: pt = "Erro"

                                if v == "Não Conforme" and not str(obss.get(k, "")).strip():
                                    lista_erros.append(f"**PADRÃO {pr}:** {pt}")

                                reg = {"DTO":sel_dto, "Data":dh, "Filial":fil, "Funcionario":nome, "CPF":cpf, "Padrao":pr, "Pergunta":pt, "Resultado":v, "Observacao":obss.get(k,"")}
                                if st.session_state['auditor_logado']: reg.update({"Auditor_Nome":st.session_state['auditor_logado']['Nome'], "Auditor_CPF":st.session_state['auditor_logado']['CPF']})
                                novos.append(reg)

                            if lista_erros:
                                msg_erro = "⛔ **ERRO: PREENCHIMENTO OBRIGATÓRIO!**\n\nVocê marcou 'Não Conforme' nos itens abaixo sem justificativa:\n\n" + "\n".join([f"- {e}" for e in lista_erros])
                                alerta_topo.error(msg_erro)
                                alerta_fim.error(msg_erro)

                            elif novos:
                                try:
                                    gravar_respostas(novos)
                                    st.session_state['msg_salvo'] = f"✅ {nome}: salvo com sucesso! ({len(novos)} respostas)"
                                    st.rerun()

                                except Exception as e:
                                    # download_button não funciona dentro de form: guarda e mostra no topo
                                    st.session_state['backup_erro'] = gerar_excel(pd.DataFrame(novos))
                                    st.session_state['backup_erro_msg'] = f"{nome}: {e}"
                                    st.rerun()
                            else:
                                alerta_topo.warning("Nenhuma resposta marcada para salvar.")
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
        aus = ausentes_dto()
        eh_aus = df_esc[c_cpf_tr].astype(str).str.strip().isin(aus)
        df_aus = df_esc[eh_aus]
        df_esc = df_esc[~eh_aus]   # ausentes não entram nas metas do ciclo

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
                    
                    df_uni = df_treinos[(df_treinos[c_fil_tr].isin(lf)) & (df_treinos[c_pad_tr].isin(lp))
                                        & ~df_treinos[c_cpf_tr].astype(str).str.strip().isin(aus)]
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
            for cpf in df_aus[c_cpf_tr].unique():
                info = df_aus[df_aus[c_cpf_tr]==cpf].iloc[0]
                ra = aus.get(str(cpf).strip(), {})
                data_list.append({"Filial":info[c_fil_tr], "Nome":info[c_nom_tr], "Status":"⚫ Ausente",
                                  "Prog":"-", "Motivo":ra.get('Observacao',''), "Registrado por":ra.get('Auditor_Nome',''),
                                  "Data":ra.get('Data','')})
            n_aus = df_aus[c_cpf_tr].nunique()
            c1,c2,c3,c4,c5 = st.columns(5)
            c1.metric("Pessoas", total + n_aus)
            c2.metric("Concluídos", counts['C'])
            c3.metric("Parcial", counts['A'])
            c4.metric("Pendentes", counts['P'])
            c5.metric("Ausentes", n_aus)
            prog = counts['C']/total if total else 0
            st.progress(prog, f"Taxa: {int(prog*100)}% (ausentes fora da conta)")
            df_d = pd.DataFrame(data_list)
            if not df_d.empty:
                cols_base = ["Filial","Nome","Status","Prog"]
                t1,t2,t3,t4 = st.tabs(["🔴 Pendentes","🟡 Parciais","🟢 Concluídos","⚫ Ausentes"])
                with t1: st.dataframe(df_d[df_d['Status'].str.contains("Pendente")][cols_base], use_container_width=True)
                with t2: st.dataframe(df_d[df_d['Status'].str.contains("Parcial")][cols_base], use_container_width=True)
                with t3: st.dataframe(df_d[df_d['Status'].str.contains("Concluído")][cols_base], use_container_width=True)
                with t4: st.dataframe(df_d[df_d['Status'].str.contains("Ausente")].drop(columns=["Prog"], errors="ignore"), use_container_width=True)
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
            if len(df_aus):
                st.caption(f"⚫ {df_aus[c_cpf_tr].nunique()} colaborador(es) ausente(s) neste ciclo não entram na volumetria.")
            df_v = pd.DataFrame(vol_data)
            st.dataframe(df_v, use_container_width=True)
            if not df_v.empty: st.download_button("📥 Baixar Volumetria", gerar_excel(df_v), "Status_Volume.xlsx")

        st.markdown("---")
        b1,b2 = st.columns([3,1])
        if not df_res.empty:
            out = BytesIO()
            with pd.ExcelWriter(out, engine='xlsxwriter') as writer: df_res.to_excel(writer, index=False)
            b1.download_button("📥 Baixar Master", out.getvalue(), f"Master_{sel_dto.replace(' ','')}_{obter_hora().replace('/','-')}.xlsx")
