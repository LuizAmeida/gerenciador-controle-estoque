import streamlit as st
import pandas as pd
import sqlite3
import datetime
import io

# ==========================================
# CONFIGURAÇÃO DA PÁGINA E BANCO DE DADOS
# ==========================================
st.set_page_config(
    page_title="Controle de Estoque Unitário - AT",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_NAME = "estoque_unitario_at.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Tabela 100% unitária: Cada registro é EXATAMENTE 1 unidade física
    c.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sku TEXT,
            category TEXT,
            tipo TEXT,
            unit_label TEXT,
            status TEXT NOT NULL,
            pecas_faltando TEXT,
            volumes_esperados INTEGER,
            volumes_faltando TEXT
        )
    """)
    # Tabela de histórico por unidade
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
# CONSTANTES E ESTILOS
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
# FUNÇÕES DE BANCO DE DADOS (100% UNITÁRIO)
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

def add_single_unit(name, sku, category, tipo, unit_label, status, pecas_faltando, volumes_esperados, volumes_faltando, note):
    """Insere rigorosamente 1 unidade física no banco de dados."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO items (name, sku, category, tipo, unit_label, status, pecas_faltando, volumes_esperados, volumes_faltando)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, sku, category, tipo, unit_label, status, pecas_faltando, volumes_esperados, volumes_faltando))
    item_id = c.lastrowid
    
    date_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    note_final = note if note.strip() else "Unidade cadastrada"
    c.execute("INSERT INTO history (item_id, status, date, note) VALUES (?, ?, ?, ?)",
              (item_id, status, date_str, note_final))
    conn.commit()
    conn.close()
    return item_id

def update_unit_details(item_id, new_status, new_tipo, pecas_faltando, volumes_esperados, volumes_faltando, note):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        UPDATE items 
        SET status = ?, tipo = ?, pecas_faltando = ?, volumes_esperados = ?, volumes_faltando = ?
        WHERE id = ?
    """, (new_status, new_tipo, pecas_faltando, volumes_esperados, volumes_faltando, item_id))
    
    date_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    note_final = note.strip() if note.strip() else f"Status atualizado para '{new_status}'"
    c.execute("INSERT INTO history (item_id, status, date, note) VALUES (?, ?, ?, ?)",
              (item_id, new_status, date_str, note_final))
    conn.commit()
    conn.close()

def delete_unit(item_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM history WHERE item_id = ?", (item_id,))
    c.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

def clear_all_units():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM history")
    c.execute("DELETE FROM items")
    conn.commit()
    conn.close()

# ==========================================
# INTERFACE DO USUÁRIO
# ==========================================
st.title("📦 Controle de Estoque Unitário — Assistência Técnica")
st.caption("Controle estrito por unidade física: disponível · em separação · em falta · sobrando · incompleto · avariado · assistência técnica")

# Carrega todos os itens unitários
df_items = get_items_df()

# --- BARRA SUPERIOR DE MÉTRICAS (CONTAGEM DE PEÇAS) ---
st.markdown("### Contagem por Status (Unidades Físicas)")
cols = st.columns(len(STATUS_LIST))
for idx, st_name in enumerate(STATUS_LIST):
    count = len(df_items[df_items["status"] == st_name]) if not df_items.empty else 0
    with cols[idx]:
        st.metric(label=st_name, value=f"{count} un.")

st.divider()

# --- SIDEBAR: CADASTRO E IMPORTAÇÃO ---
with st.sidebar:
    st.header("⚙️ Operações de Entrada")
    
    with st.expander("➕ Cadastrar Unidade(s) Manualmente", expanded=False):
        with st.form("form_novo_item", clear_on_submit=True):
            name = st.text_input("Nome do Produto *")
            sku = st.text_input("SKU / Código")
            category = st.text_input("Categoria")
            tipo = st.selectbox("Tipo de Item", TIPOS_LIST)
            qty_input = st.number_input("Quantas unidades físicas deseja gerar?", min_value=1, value=1, step=1)
            status = st.selectbox("Status Inicial", STATUS_LIST, index=0)
            
            pecas_faltando = ""
            volumes_esperados = None
            volumes_faltando = ""
            
            if tipo == "Eletro":
                pecas_faltando = st.text_input("Peças/Acessórios Faltando", placeholder="Ex: falta controle, cabo HDMI")
            elif tipo == "Móvel":
                volumes_esperados = st.number_input("Volumes Esperados", min_value=1, value=1, step=1)
                volumes_faltando = st.text_input("Volumes Faltando", placeholder="Ex: 3, 7")
            
            note = st.text_input("Observação Inicial", placeholder="Ex: Recebido da conferência física")
            submit = st.form_submit_button("Gerar Unidade(s)")
            
            if submit:
                if name.strip():
                    for i in range(1, int(qty_input) + 1):
                        label = f"Unidade {i}/{qty_input}" if qty_input > 1 else "Unidade 1/1"
                        add_single_unit(
                            name=name.strip(),
                            sku=sku.strip(),
                            category=category.strip(),
                            tipo=tipo,
                            unit_label=label,
                            status=status,
                            pecas_faltando=pecas_faltando.strip(),
                            volumes_esperados=volumes_esperados,
                            volumes_faltando=volumes_faltando.strip(),
                            note=note
                        )
                    st.success(f"{qty_input} unidade(s) gerada(s) individualmente!")
                    st.rerun()
                else:
                    st.error("O campo Nome é obrigatório.")

    # Importação do CSV
    st.subheader("Importar CSV do Auditor")
    uploaded_file = st.file_uploader("Selecione o arquivo .csv", type=["csv"])
    if uploaded_file is not None:
        if st.button("Processar Importação Unitária"):
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
                    total_units_created = 0
                    for _, row in imported_df.iterrows():
                        p_name = str(row[col_name]).strip()
                        if p_name and p_name != "nan":
                            p_sku = str(row[col_sku]).strip() if col_sku and pd.notna(row[col_sku]) else ""
                            p_cat = str(row[col_cat]).strip() if col_cat and pd.notna(row[col_cat]) else ""
                            
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
                            
                            # Criação rigorosa de 1 registro por unidade física
                            for u_idx in range(1, max(1, p_qty) + 1):
                                u_label = f"Unidade {u_idx}/{p_qty}" if p_qty > 1 else "Unidade 1/1"
                                add_single_unit(
                                    name=p_name,
                                    sku=p_sku,
                                    category=p_cat,
                                    tipo=p_tipo,
                                    unit_label=u_label,
                                    status="A conferir",
                                    pecas_faltando="",
                                    volumes_esperados=None,
                                    volumes_faltando="",
                                    note="Importado da planilha do Auditor — aguardando triagem unitária"
                                )
                                total_units_created += 1

                    st.success(f"{total_units_created} unidades individuais geradas para conferência!")
                    st.rerun()
                else:
                    st.error("Coluna de nome do produto não identificada no arquivo CSV.")
            except Exception as e:
                st.error(f"Erro ao processar CSV: {e}")

    # Exportação e limpeza
    if not df_items.empty:
        csv_data = df_items.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="⬇️ Exportar Todas as Unidades (CSV)",
            data=csv_data,
            file_name=f"estoque_unitario_{datetime.date.today()}.csv",
            mime="text/csv"
        )
        st.divider()
        if st.button("🚨 Limpar Todo o Banco de Dados"):
            clear_all_units()
            st.rerun()

# --- ÁREA DE CONSULTA E LISTAGEM UNITÁRIA ---
col_busca, col_filtro = st.columns([2, 1])
with col_busca:
    query = st.text_input("🔍 Buscar por nome, SKU, categoria ou identificador", placeholder="Digite para buscar...")
with col_filtro:
    filtro_status = st.selectbox("Filtrar por Status", ["Todos"] + STATUS_LIST)

df_view = df_items.copy()
if not df_view.empty:
    if filtro_status != "Todos":
        df_view = df_view[df_view["status"] == filtro_status]
    if query.strip():
        q = query.lower().strip()
        df_view = df_view[
            df_view["name"].str.lower().str.contains(q, na=False) |
            df_view["sku"].str.lower().str.contains(q, na=False) |
            df_view["category"].str.lower().str.contains(q, na=False) |
            df_view["unit_label"].str.lower().str.contains(q, na=False)
        ]

st.markdown(f"**Exibindo {len(df_view)} unidade(s) física(s)**")

if df_view.empty:
    st.info("Nenhuma unidade física encontrada com os filtros atuais.")
else:
    for _, row in df_view.iterrows():
        with st.container():
            c1, c2, c3 = st.columns([5, 3, 1])
            with c1:
                st.markdown(f"### {row['name']} &nbsp; <span style='font-size: 13px; color: #888; background: #2b2f34; padding: 2px 8px; border-radius: 4px;'>{row['unit_label'] or 'Unidade Física'}</span>", unsafe_allow_html=True)
                detalhes = f"**ID Unitário:** `#{row['id']}` | **SKU:** {row['sku'] or 'S/N'} | **Categoria:** {row['category'] or 'Geral'} | **Tipo:** {row['tipo']}"
                st.write(detalhes)
                
                # Alertas de pendências específicas desta peça
                if row["tipo"] == "Eletro" and row["pecas_faltando"]:
                    st.warning(f"⚠️ **Peças/Acessórios Faltando:** {row['pecas_faltando']}")
                elif row["tipo"] == "Móvel" and (row["volumes_faltando"] or row["volumes_esperados"]):
                    st.warning(f"⚠️ **Volumes:** Esperados: {row['volumes_esperados'] or '-'} | Faltando: {row['volumes_faltando'] or 'Nenhum'}")

            with c2:
                # Triagem individual direta
                current_idx = STATUS_LIST.index(row["status"]) if row["status"] in STATUS_LIST else 0
                novo_st = st.selectbox(
                    "Status desta Unidade",
                    STATUS_LIST,
                    index=current_idx,
                    key=f"status_unit_{row['id']}"
                )
                if novo_st != row["status"]:
                    update_unit_details(
                        item_id=row["id"],
                        new_status=novo_st,
                        new_tipo=row["tipo"],
                        pecas_faltando=row["pecas_faltando"] or "",
                        volumes_esperados=row["volumes_esperados"],
                        volumes_faltando=row["volumes_faltando"] or "",
                        note=f"Status alterado na triagem para {novo_st}"
                    )
                    st.rerun()

            with c3:
                st.write("")
                st.write("")
                if st.button("🗑️ Excluir", key=f"del_unit_{row['id']}"):
                    delete_unit(row["id"])
                    st.rerun()

            # Expander de Edição Detalhada desta Unidade
            with st.expander("🛠️ Editar Detalhes / Registrar Avaria ou Peças Desta Peça"):
                with st.form(key=f"form_edit_unit_{row['id']}"):
                    e_col1, e_col2 = st.columns(2)
                    with e_col1:
                        e_tipo = st.selectbox(
                            "Tipo de Item",
                            TIPOS_LIST,
                            index=TIPOS_LIST.index(row["tipo"]) if row["tipo"] in TIPOS_LIST else 0,
                            key=f"e_tipo_{row['id']}"
                        )
                    with e_col2:
                        e_status = st.selectbox(
                            "Status",
                            STATUS_LIST,
                            index=STATUS_LIST.index(row["status"]) if row["status"] in STATUS_LIST else 0,
                            key=f"e_st_{row['id']}"
                        )

                    e_pf = ""
                    e_ve = None
                    e_vf = ""
                    if e_tipo == "Eletro":
                        e_pf = st.text_input("Peças / Acessórios Faltando", value=str(row["pecas_faltando"] or ""), key=f"e_pf_{row['id']}")
                    elif e_tipo == "Móvel":
                        m1, m2 = st.columns(2)
                        with m1:
                            e_ve = st.number_input("Volumes Esperados", min_value=1, value=int(row["volumes_esperados"] or 1), key=f"e_ve_{row['id']}")
                        with m2:
                            e_vf = st.text_input("Volumes Faltando (ex: 2, 4)", value=str(row["volumes_faltando"] or ""), key=f"e_vf_{row['id']}")

                    e_note = st.text_input("Observação / Motivo da alteração", placeholder="Ex: Riscos na porta lateral, enviado para reparo", key=f"e_note_{row['id']}")
                    
                    if st.form_submit_button("Salvar Detalhes da Unidade"):
                        update_unit_details(
                            item_id=row["id"],
                            new_status=e_status,
                            new_tipo=e_tipo,
                            pecas_faltando=e_pf.strip(),
                            volumes_esperados=e_ve,
                            volumes_faltando=e_vf.strip(),
                            note=e_note.strip()
                        )
                        st.success("Unidade atualizada com sucesso!")
                        st.rerun()

            # Expander de Histórico da Unidade
            with st.expander("📜 Histórico de Movimentações Desta Unidade"):
                hist_df = get_history(row["id"])
                if not hist_df.empty:
                    for _, h in hist_df.iterrows():
                        st.markdown(f"- **{h['date']}** | `{h['status']}` — {h['note']}")
                else:
                    st.caption("Sem movimentações registradas.")

            st.divider()
