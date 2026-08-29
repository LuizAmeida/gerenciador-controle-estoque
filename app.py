import streamlit as st
import pandas as pd
import sqlite3
import datetime
import io

# ==========================================
# CONFIGURAÇÃO DA PÁGINA E BANCO DE DADOS
# ==========================================
st.set_page_config(
    page_title="Controle de Estoque - AT",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_NAME = "estoque_at.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Tabela principal de itens
    c.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sku TEXT,
            category TEXT,
            tipo TEXT,
            quantity INTEGER DEFAULT 1,
            status TEXT NOT NULL,
            pecas_faltando TEXT,
            volumes_esperados INTEGER,
            volumes_faltando TEXT
        )
    """)
    # Tabela de histórico de movimentação
    c.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER,
            status TEXT,
            date TEXT,
            note TEXT,
            FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ==========================================
# DICIONÁRIOS E CONSTANTES
# ==========================================
STATUS_CONFIG = {
    "A conferir": {"color": "#6b7280"},
    "Disponível": {"color": "#3fa34d"},
    "Em separação": {"color": "#3b82c4"},
    "Em falta": {"color": "#d64545"},
    "Sobrando": {"color": "#a855f7"},
    "Incompleto": {"color": "#c99a1e"},
    "Avariado": {"color": "#e0793c"},
    "Assistência técnica": {"color": "#2aa7a0"}
}

STATUS_LIST = list(STATUS_CONFIG.keys())
TIPOS_LIST = ["Eletro", "Móvel", "Outro"]

# ==========================================
# FUNÇÕES DE BANCO DE DADOS (CRUD E TRIAGEM)
# ==========================================
def get_items_df():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM items ORDER BY id DESC", conn)
    conn.close()
    return df

def get_history(item_id):
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT status, date, note FROM history WHERE item_id = ? ORDER BY id DESC", conn, params=(item_id,))
    conn.close()
    return df

def add_item(name, sku, category, tipo, quantity, status, pecas_faltando, volumes_esperados, volumes_faltando, note):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO items (name, sku, category, tipo, quantity, status, pecas_faltando, volumes_esperados, volumes_faltando)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, sku, category, tipo, quantity, status, pecas_faltando, volumes_esperados, volumes_faltando))
    item_id = c.lastrowid
    
    date_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    note_final = note if note.strip() else "Item cadastrado"
    c.execute("INSERT INTO history (item_id, status, date, note) VALUES (?, ?, ?, ?)",
              (item_id, status, date_str, note_final))
    conn.commit()
    conn.close()
    return item_id

def update_item_status(item_id, new_status, note="Alteração rápida de status"):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE items SET status = ? WHERE id = ?", (new_status, item_id))
    date_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    c.execute("INSERT INTO history (item_id, status, date, note) VALUES (?, ?, ?, ?)",
              (item_id, new_status, date_str, note))
    conn.commit()
    conn.close()

def split_item(original_id, split_qty, new_status, new_tipo, pecas_faltando, volumes_esperados, volumes_faltando, note):
    """
    Função de Triagem: Desmembra uma quantidade específica de um lote existente
    e gera um novo registro com o novo status e especificações.
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Pega os dados do item original
    c.execute("SELECT name, sku, category, quantity, status FROM items WHERE id = ?", (original_id,))
    orig = c.fetchone()
    if not orig:
        conn.close()
        return
    
    orig_name, orig_sku, orig_category, orig_qty, orig_status = orig
    date_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    
    # Se a quantidade a desmembrar for igual ao total do lote, apenas atualiza
    if split_qty >= orig_qty:
        c.execute("""
            UPDATE items 
            SET status = ?, tipo = ?, pecas_faltando = ?, volumes_esperados = ?, volumes_faltando = ?
            WHERE id = ?
        """, (new_status, new_tipo, pecas_faltando, volumes_esperados, volumes_faltando, original_id))
        
        hist_note = f"Triagem completa do lote ({split_qty} un.): {note}" if note else f"Triagem do lote ({split_qty} un.)"
        c.execute("INSERT INTO history (item_id, status, date, note) VALUES (?, ?, ?, ?)",
                  (original_id, new_status, date_str, hist_note))
    else:
        # 2. Subtrai a quantidade do item de origem
        new_orig_qty = orig_qty - split_qty
        c.execute("UPDATE items SET quantity = ? WHERE id = ?", (new_orig_qty, original_id))
        c.execute("INSERT INTO history (item_id, status, date, note) VALUES (?, ?, ?, ?)",
                  (original_id, orig_status, date_str, f"Triagem: {split_qty} un. separada(s) para '{new_status}'"))
        
        # 3. Cria a nova entrada com a quantidade triada
        c.execute("""
            INSERT INTO items (name, sku, category, tipo, quantity, status, pecas_faltando, volumes_esperados, volumes_faltando)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (orig_name, orig_sku, orig_category, new_tipo, split_qty, new_status, pecas_faltando, volumes_esperados, volumes_faltando))
        new_item_id = c.lastrowid
        
        hist_note = f"Desmembrado de lote de {orig_qty} un. | {note}" if note else f"Desmembrado de lote de {orig_qty} un."
        c.execute("INSERT INTO history (item_id, status, date, note) VALUES (?, ?, ?, ?)",
                  (new_item_id, new_status, date_str, hist_note))
    
    conn.commit()
    conn.close()

def delete_item(item_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM history WHERE item_id = ?", (item_id,))
    c.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

# ==========================================
# INTERFACE DO USUÁRIO
# ==========================================
st.title("📦 Controle de Estoque — Assistência Técnica")
st.caption("Visibilidade real e conferência física: disponível · em separação · em falta · sobrando · incompleto · avariado · assistência técnica")

# Carrega os dados
df_items = get_items_df()

# --- BARRA SUPERIOR DE MÉTRICAS ---
st.markdown("### Resumo por Status")
cols = st.columns(len(STATUS_LIST))
for idx, st_name in enumerate(STATUS_LIST):
    if not df_items.empty:
        count_itens = len(df_items[df_items["status"] == st_name])
        soma_unidades = int(df_items[df_items["status"] == st_name]["quantity"].sum())
    else:
        count_itens, soma_unidades = 0, 0
    with cols[idx]:
        st.metric(label=st_name, value=f"{soma_unidades} un.", delta=f"{count_itens} reg." if count_itens > 0 else None)

st.divider()

# --- SIDEBAR: CADASTRO E IMPORTAÇÃO ---
with st.sidebar:
    st.header("⚙️ Operações")
    
    with st.expander("➕ Novo Item Manual", expanded=False):
        with st.form("form_novo_item", clear_on_submit=True):
            name = st.text_input("Nome do Produto *")
            sku = st.text_input("SKU / Código")
            category = st.text_input("Categoria")
            tipo = st.selectbox("Tipo de Item", TIPOS_LIST)
            quantity = st.number_input("Quantidade", min_value=1, value=1, step=1)
            status = st.selectbox("Status Inicial", STATUS_LIST, index=0)
            
            pecas_faltando = ""
            volumes_esperados = None
            volumes_faltando = ""
            
            if tipo == "Eletro":
                pecas_faltando = st.text_input("Peças/Acessórios Faltando", placeholder="Ex: falta controle, cabo HDMI")
            elif tipo == "Móvel":
                volumes_esperados = st.number_input("Volumes Esperados", min_value=1, value=1, step=1)
                volumes_faltando = st.text_input("Volumes Faltando", placeholder="Ex: 3, 7")
            
            note = st.text_input("Observação Inicial", placeholder="Ex: Recebido do Auditor")
            submit = st.form_submit_button("Cadastrar Item")
            
            if submit:
                if name.strip():
                    add_item(name.strip(), sku.strip(), category.strip(), tipo, quantity, status,
                             pecas_faltando.strip(), volumes_esperados, volumes_faltando.strip(), note)
                    st.success("Item cadastrado com sucesso!")
                    st.rerun()
                else:
                    st.error("O campo Nome é obrigatório.")

    # Importação / Exportação CSV
    st.subheader("Arquivo CSV")
    uploaded_file = st.file_uploader("Importar CSV do Auditor", type=["csv"])
    individualize_on_import = st.checkbox("Desmembrar em 1 por 1 na importação", value=False,
                                          help="Se marcado, um lote com 6 unidades criará 6 registros individuais de 1 unidade para facilitar a triagem unitária.")
    
    if uploaded_file is not None:
        if st.button("Processar Importação"):
            try:
                bytes_data = uploaded_file.getvalue()
                try:
                    text_data = bytes_data.decode("utf-8-sig")
                except UnicodeDecodeError:
                    text_data = bytes_data.decode("latin-1")

                first_line = text_data.splitlines()[0] if text_data.splitlines() else ""
                delimiter = ";" if ";" in first_line else ","

                imported_df = pd.read_csv(io.StringIO(text_data), sep=delimiter)
                imported_df.columns = [str(c).replace("\ufeff", "").strip().lower() for c in imported_df.columns]
                
                col_name = next((c for c in imported_df.columns if c in ["produto", "nome", "descricao", "descrição", "item"]), None)
                col_sku = next((c for c in imported_df.columns if c in ["sku", "codigo", "código", "cod", "cód"]), None)
                col_cat = next((c for c in imported_df.columns if c in ["categoria", "grupo", "familia", "família", "setor"]), None)
                col_qty = next((c for c in imported_df.columns if c in ["quantidade", "qtd", "qtde", "estoque", "saldo"]), None)
                col_tipo = next((c for c in imported_df.columns if c in ["tipo"]), None)
                
                if col_name:
                    count_imp = 0
                    for _, row in imported_df.iterrows():
                        p_name = str(row[col_name]).strip()
                        if p_name and p_name != "nan":
                            p_sku = str(row[col_sku]).strip() if col_sku and pd.notna(row[col_sku]) else ""
                            p_cat = str(row[col_cat]).strip() if col_cat and pd.notna(row[col_cat]) else ""
                            
                            # Inferência básica de tipo caso exista
                            p_tipo = "Outro"
                            if col_tipo and pd.notna(row[col_tipo]):
                                t_val = str(row[col_tipo]).capitalize()
                                if t_val in TIPOS_LIST:
                                    p_tipo = t_val
                            elif any(k in p_name.lower() for k in ["fogão", "geladeira", "tv", "micro", "ar-condicionado", "notebook", "smartphone", "ventilador"]):
                                p_tipo = "Eletro"
                            elif any(k in p_name.lower() for k in ["guarda-roupa", "mesa", "sofá", "cama", "estante", "cômoda", "rack"]):
                                p_tipo = "Móvel"

                            try:
                                p_qty = int(float(str(row[col_qty]).replace(",", "."))) if col_qty and pd.notna(row[col_qty]) else 1
                            except (ValueError, TypeError):
                                p_qty = 1
                            
                            if individualize_on_import and p_qty > 1:
                                for _ in range(p_qty):
                                    add_item(p_name, p_sku, p_cat, p_tipo, 1, "A conferir", "", None, "", "Importado de planilha CSV (Unitário)")
                                    count_imp += 1
                            else:
                                add_item(p_name, p_sku, p_cat, p_tipo, p_qty, "A conferir", "", None, "", "Importado de planilha CSV")
                                count_imp += 1

                    st.success(f"{count_imp} registro(s) importado(s) com sucesso como 'A conferir'!")
                    st.rerun()
                else:
                    st.error("Coluna de nome do produto não identificada no arquivo CSV.")
            except Exception as e:
                st.error(f"Erro ao processar CSV: {e}")

    if not df_items.empty:
        csv_data = df_items.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="⬇️ Exportar Base Completa (CSV)",
            data=csv_data,
            file_name=f"estoque_at_{datetime.date.today()}.csv",
            mime="text/csv"
        )

# --- ÁREA DE CONSULTA E LISTAGEM ---
col_busca, col_filtro = st.columns([2, 1])
with col_busca:
    query = st.text_input("🔍 Buscar por nome, SKU ou categoria", placeholder="Digite para filtrar...")
with col_filtro:
    filtro_status = st.selectbox("Filtrar por Status", ["Todos"] + STATUS_LIST)

# Aplica filtros
df_view = df_items.copy()
if not df_view.empty:
    if filtro_status != "Todos":
        df_view = df_view[df_view["status"] == filtro_status]
    if query.strip():
        q = query.lower().strip()
        df_view = df_view[
            df_view["name"].str.lower().str.contains(q, na=False) |
            df_view["sku"].str.lower().str.contains(q, na=False) |
            df_view["category"].str.lower().str.contains(q, na=False)
        ]

st.markdown(f"**Exibindo {len(df_view)} registro(s)**")

if df_view.empty:
    st.info("Nenhum item encontrado com os filtros selecionados.")
else:
    for _, row in df_view.iterrows():
        with st.container():
            c1, c2, c3, c4 = st.columns([4, 2, 2, 1])
            with c1:
                st.subheader(row["name"])
                detalhes = f"**SKU:** {row['sku'] or 'S/N'} | **Categoria:** {row['category'] or 'Geral'} | **Tipo:** {row['tipo']}"
                st.write(detalhes)
                
                # Exibição de pendências de volumes/peças
                if row["tipo"] == "Eletro" and row["pecas_faltando"]:
                    st.warning(f"⚠️ **Peças Faltando:** {row['pecas_faltando']}")
                elif row["tipo"] == "Móvel" and (row["volumes_faltando"] or row["volumes_esperados"]):
                    st.warning(f"⚠️ **Volumes:** Esperados: {row['volumes_esperados'] or '-'} | Faltando: {row['volumes_faltando'] or 'Nenhum'}")

            with c2:
                st.metric(label="Saldo do Lote", value=f"{row['quantity']} un.")

            with c3:
                # Alteração de status direta do lote
                current_idx = STATUS_LIST.index(row["status"]) if row["status"] in STATUS_LIST else 0
                novo_st = st.selectbox(
                    "Status Atual",
                    STATUS_LIST,
                    index=current_idx,
                    key=f"status_select_{row['id']}"
                )
                if novo_st != row["status"]:
                    update_item_status(row["id"], novo_st, note=f"Status alterado no painel para {novo_st}")
                    st.rerun()

            with c4:
                st.write("")
                st.write("")
                if st.button("🗑️ Excluir", key=f"del_{row['id']}"):
                    delete_item(row["id"])
                    st.rerun()

            # --- SEÇÃO DE TRIAGEM / DESMEMBRAMENTO DE LOTES ---
            if row["quantity"] > 1:
                with st.expander(f"🧩 Triar / Desmembrar Lote ({row['quantity']} unidades disponíveis)"):
                    st.markdown(
                        "Use esta ferramenta para separar parte do lote que esteja em estado diferente "
                        "(ex: mandar 1 para avaria ou assistência técnica e manter o restante)."
                    )
                    with st.form(key=f"form_split_{row['id']}"):
                        f_col1, f_col2, f_col3 = st.columns([1, 1, 1])
                        with f_col1:
                            split_qtd = st.number_input(
                                "Quantidade a Destinar",
                                min_value=1,
                                max_value=int(row["quantity"]),
                                value=1,
                                step=1,
                                key=f"split_q_{row['id']}"
                            )
                        with f_col2:
                            split_status = st.selectbox(
                                "Novo Status para essa(s) unidade(s)",
                                STATUS_LIST,
                                index=1,
                                key=f"split_st_{row['id']}"
                            )
                        with f_col3:
                            tipo_item = st.selectbox(
                                "Tipo",
                                TIPOS_LIST,
                                index=TIPOS_LIST.index(row["tipo"]) if row["tipo"] in TIPOS_LIST else 0,
                                key=f"split_tipo_{row['id']}"
                            )

                        # Campos específicos de acordo com o tipo
                        p_faltando = ""
                        v_esperados = None
                        v_faltando = ""
                        
                        if tipo_item == "Eletro":
                            p_faltando = st.text_input("Peças/Acessórios Faltando (se houver)", key=f"split_pf_{row['id']}")
                        elif tipo_item == "Móvel":
                            m_col1, m_col2 = st.columns(2)
                            with m_col1:
                                v_esperados = st.number_input("Volumes Esperados", min_value=1, value=int(row["volumes_esperados"] or 1), key=f"split_ve_{row['id']}")
                            with m_col2:
                                v_faltando = st.text_input("Volumes Faltando (ex: 2, 5)", value=str(row["volumes_faltando"] or ""), key=f"split_vf_{row['id']}")

                        split_obs = st.text_input("Motivo / Observação da Triagem", placeholder="Ex: 1 un. identificada com avaria na lateral durante conferência", key=f"split_obs_{row['id']}")
                        
                        btn_confirmar_triagem = st.form_submit_button("✅ Confirmar Triagem e Desmembrar")
                        if btn_confirmar_triagem:
                            split_item(
                                original_id=row["id"],
                                split_qty=split_qtd,
                                new_status=split_status,
                                new_tipo=tipo_item,
                                pecas_faltando=p_faltando.strip(),
                                volumes_esperados=v_esperados,
                                volumes_faltando=v_faltando.strip(),
                                note=split_obs.strip()
                            )
                            st.success(f"{split_qtd} unidade(s) triada(s) com sucesso para '{split_status}'!")
                            st.rerun()

            # Expander de Histórico
            with st.expander("📜 Ver Histórico de Movimentações"):
                hist_df = get_history(row["id"])
                if not hist_df.empty:
                    for _, h in hist_df.iterrows():
                        st.markdown(f"- **{h['date']}** | `{h['status']}` — {h['note']}")
                else:
                    st.caption("Sem histórico registrado.")
            
            st.divider()
