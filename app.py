import streamlit as st
import pandas as pd
import sqlite3
import datetime

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
# FUNÇÕES DE BANCO DE DADOS (CRUD)
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

def update_item_status(item_id, new_status, note="Alteração rápida de status"):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE items SET status = ? WHERE id = ?", (new_status, item_id))
    date_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    c.execute("INSERT INTO history (item_id, status, date, note) VALUES (?, ?, ?, ?)",
              (item_id, new_status, date_str, note))
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
    count = len(df_items[df_items["status"] == st_name]) if not df_items.empty else 0
    with cols[idx]:
        st.metric(label=st_name, value=count)

st.divider()

# --- SIDEBAR: CADASTRO E IMPORTAÇÃO ---
with st.sidebar:
    st.header("⚙️ Operações")
    
    with st.expander("➕ Novo Item", expanded=False):
        with st.form("form_novo_item", clear_on_submit=True):
            name = st.text_input("Nome do Produto *")
            sku = st.text_input("SKU / Código")
            category = st.text_input("Categoria")
            tipo = st.selectbox("Tipo de Item", TIPOS_LIST)
            quantity = st.number_input("Quantidade", min_value=1, value=1, step=1)
            status = st.selectbox("Status Inicial", STATUS_LIST, index=1)
            
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
    if uploaded_file is not None:
        if st.button("Processar Importação"):
            try:
                imported_df = pd.read_csv(uploaded_file, sep=None, engine='python')
                imported_df.columns = [c.lower().strip() for c in imported_df.columns]
                
                # Mapeamento dinâmico de colunas
                col_name = next((c for c in imported_df.columns if c in ["produto", "nome", "descricao", "descrição", "item"]), None)
                col_sku = next((c for c in imported_df.columns if c in ["sku", "codigo", "código", "cod"]), None)
                col_cat = next((c for c in imported_df.columns if c in ["categoria", "grupo", "setor"]), None)
                col_qty = next((c for c in imported_df.columns if c in ["quantidade", "qtd", "estoque"]), None)
                
                if col_name:
                    count_imp = 0
                    for _, row in imported_df.iterrows():
                        p_name = str(row[col_name]).strip()
                        if p_name and p_name != "nan":
                            p_sku = str(row[col_sku]).strip() if col_sku and pd.notna(row[col_sku]) else ""
                            p_cat = str(row[col_cat]).strip() if col_cat and pd.notna(row[col_cat]) else ""
                            p_qty = int(row[col_qty]) if col_qty and pd.notna(row[col_qty]) else 1
                            add_item(p_name, p_sku, p_cat, "Outro", p_qty, "A conferir", "", None, "", "Importado de planilha CSV")
                            count_imp += 1
                    st.success(f"{count_imp} itens importados como 'A conferir'!")
                    st.rerun()
                else:
                    st.error("Coluna de nome do produto não identificada no CSV.")
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

st.markdown(f"**Exibindo {len(df_view)} item(ns)**")

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
                st.metric(label="Quantidade", value=f"{row['quantity']} un.")

            with c3:
                # Alteração rápida de status
                current_idx = STATUS_LIST.index(row["status"]) if row["status"] in STATUS_LIST else 0
                novo_st = st.selectbox(
                    "Status Atual",
                    STATUS_LIST,
                    index=current_idx,
                    key=f"status_select_{row['id']}"
                )
                if novo_st != row["status"]:
                    update_item_status(row["id"], novo_st, note="Status alterado no painel")
                    st.rerun()

            with c4:
                st.write("")
                st.write("")
                if st.button("🗑️ Excluir", key=f"del_{row['id']}"):
                    delete_item(row["id"])
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
