import streamlit as st
import pandas as pd
import sqlite3
import datetime
import io

# ==========================================
# CONFIGURAÇÃO DA PÁGINA E ESTILIZAÇÃO CSS
# ==========================================
st.set_page_config(
    page_title="Controle de Estoque Unitário - AT",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""<style>
.stApp {
    background-color: #1c1f22;
    color: #edeeee;
    font-family: 'Consolas', 'Courier New', monospace;
}
.header-box {
    border-bottom: 3px solid #f5b400;
    padding-bottom: 14px;
    margin-bottom: 20px;
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    flex-wrap: wrap;
    gap: 10px;
}
.header-title {
    font-family: 'Segoe UI', 'Arial Narrow', Arial, sans-serif;
    text-transform: uppercase;
    font-size: 26px;
    font-weight: 700;
    letter-spacing: .03em;
    margin: 0;
    color: #edeeee;
}
.header-sub {
    color: #9aa0a6;
    font-size: 12px;
    margin-top: 4px;
}
.header-badge {
    background: #f5b400;
    color: #1c1f22;
    font-family: 'Segoe UI', sans-serif;
    font-weight: 700;
    font-size: 11px;
    text-transform: uppercase;
    padding: 4px 10px;
    border-radius: 3px;
}
.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(115px, 1fr));
    gap: 8px;
    margin-bottom: 22px;
}
.stat-tile {
    background: #24282c;
    border: 1px solid #3a3f45;
    border-radius: 4px;
    padding: 10px 12px;
    text-align: left;
}
.stat-count {
    display: block;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 22px;
    font-weight: 700;
    line-height: 1;
    color: #edeeee;
}
.stat-label {
    display: block;
    font-size: 10px;
    color: #9aa0a6;
    margin-top: 5px;
    text-transform: uppercase;
    font-weight: 600;
}
.unit-title {
    font-size: 15px;
    font-weight: 600;
    color: #edeeee;
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
}
.badge-brand {
    background: #1c1f22;
    border: 1px solid #3a3f45;
    color: #f5b400;
    font-size: 11px;
    padding: 2px 7px;
    border-radius: 3px;
    font-weight: 700;
}
.badge-type {
    background: #2b2f34;
    border: 1px solid #3a3f45;
    color: #9aa0a6;
    font-size: 11px;
    padding: 2px 7px;
    border-radius: 3px;
}
[data-testid="stSidebar"] {
    background-color: #24282c;
    border-right: 1px solid #3a3f45;
}
</style>""", unsafe_allow_html=True)

# ==========================================
# BANCO DE DADOS (100% UNITÁRIO)
# ==========================================
DB_NAME = "estoque_unitario_at.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            brand TEXT,
            sku TEXT,
            category TEXT,
            tipo TEXT,
            status TEXT NOT NULL,
            pecas_faltando TEXT,
            volumes_esperados INTEGER,
            volumes_faltando TEXT
        )
    """)
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
# CONSTANTES DE STATUS E CORES
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
# OPERAÇÕES CRUD
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

def add_single_unit(name, brand, sku, category, tipo, status, pecas_faltando, volumes_esperados, volumes_faltando, note):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO items (name, brand, sku, category, tipo, status, pecas_faltando, volumes_esperados, volumes_faltando)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, brand, sku, category, tipo, status, pecas_faltando, volumes_esperados, volumes_faltando))
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
# INTERFACE PRINCIPAL
# ==========================================
header_html = (
    '<div class="header-box">'
    '<div>'
    '<h1 class="header-title">Controle de Estoque — Assistência Técnica</h1>'
    '<div class="header-sub">disponível · em separação · em falta · sobrando · incompleto · avariado · assistência técnica</div>'
    '</div>'
    '<span class="header-badge">Gestão Unitária · Físico Real</span>'
    '</div>'
)
st.markdown(header_html, unsafe_allow_html=True)

df_items = get_items_df()

# Grid de Métricas
tiles = []
for st_name, meta in STATUS_CONFIG.items():
    count = len(df_items[df_items["status"] == st_name]) if not df_items.empty else 0
    tile = (
        f'<div class="stat-tile" style="border-left: 4px solid {meta["color"]};">'
        f'<span class="stat-count">{count}</span>'
        f'<span class="stat-label">{st_name}</span>'
        f'</div>'
    )
    tiles.append(tile)

stats_html = '<div class="stats-grid">' + ''.join(tiles) + '</div>'
st.markdown(stats_html, unsafe_allow_html=True)

# --- SIDEBAR: OPERAÇÕES ---
with st.sidebar:
    st.markdown("### ⚙️ Painel de Operações")
    
    with st.expander("➕ Cadastrar Unidade Manual", expanded=False):
        with st.form("form_novo_item", clear_on_submit=True):
            name = st.text_input("Nome do Produto *", placeholder="Ex: Ventilador de Coluna 6 Pas Mondial Turbo")
            brand = st.text_input("Marca", placeholder="Ex: Mondial, Samsung, Brastemp")
            sku = st.text_input("SKU / Código", placeholder="Ex: AT-0019")
            category = st.text_input("Categoria", placeholder="Ex: Eletrodomésticos")
            tipo = st.selectbox("Tipo de Item", TIPOS_LIST)
            status = st.selectbox("Status Inicial", STATUS_LIST, index=0)
            
            pecas_faltando = ""
            volumes_esperados = None
            volumes_faltando = ""
            
            if tipo == "Eletro":
                pecas_faltando = st.text_input("Peças/Acessórios Faltando", placeholder="Ex: falta cabo de força / controle")
            elif tipo == "Móvel":
                volumes_esperados = st.number_input("Volumes Esperados de Fábrica", min_value=1, value=4, step=1)
                volumes_faltando = st.text_input("Volumes Faltando (ex: 2, 4)", placeholder="Ex: 2, 4")
            
            note = st.text_input("Observação Inicial", placeholder="Ex: Recebido da conferência física")
            submit = st.form_submit_button("Cadastrar no Estoque")
            
            if submit:
                if name.strip():
                    add_single_unit(
                        name=name.strip(),
                        brand=brand.strip(),
                        sku=sku.strip(),
                        category=category.strip(),
                        tipo=tipo,
                        status=status,
                        pecas_faltando=pecas_faltando.strip(),
                        volumes_esperados=volumes_esperados,
                        volumes_faltando=volumes_faltando.strip(),
                        note=note
                    )
                    st.success("Unidade cadastrada com sucesso!")
                    st.rerun()
                else:
                    st.error("O campo Nome é obrigatório.")

    st.markdown("### 📥 Importação de Planilha")
    uploaded_file = st.file_uploader("Subir CSV do Auditor", type=["csv"])
    if uploaded_file is not None:
        if st.button("Processar Carga do Arquivo"):
            try:
                bytes_data = uploaded_file.getvalue()
                try:
                    text_data = bytes_data.decode("utf-8-sig")
                except UnicodeDecodeError:
                    text_data = bytes_data.decode("latin-1")

                # Detecta delimitador da primeira linha de forma determinística
                first_line = text_data.strip().splitlines()[0] if text_data.strip().splitlines() else ""
                sep = ';' if ';' in first_line else (',' if ',' in first_line else '\t')

                imported_df = pd.read_csv(io.StringIO(text_data), sep=sep, dtype=str)
                imported_df.columns = [str(c).replace("\ufeff", "").strip().lower() for c in imported_df.columns]

                # Mapeamento exato de colunas
                def get_val(row, *col_names):
                    for name in col_names:
                        if name in row and pd.notna(row[name]):
                            val = str(row[name]).strip()
                            if val.lower() != "nan":
                                return val
                    return ""

                if "produto" in imported_df.columns or "nome" in imported_df.columns:
                    total_units_created = 0
                    for _, row in imported_df.iterrows():
                        p_name = get_val(row, "produto", "nome", "descricao", "item")
                        if not p_name:
                            continue

                        p_brand = get_val(row, "marca", "fabricante", "brand")
                        p_sku = get_val(row, "sku", "codigo", "código", "cod")
                        p_cat = get_val(row, "categoria", "grupo", "setor")
                        
                        # Tipo
                        p_tipo_raw = get_val(row, "tipo").capitalize()
                        if p_tipo_raw in TIPOS_LIST:
                            p_tipo = p_tipo_raw
                        elif any(k in p_name.lower() for k in ["fogão", "geladeira", "tv", "micro", "ar-condicionado", "notebook", "smartphone", "ventilador", "air fryer", "cafeteira", "aspirador", "liquidificador", "batedeira", "purificador", "som", "lava"]):
                            p_tipo = "Eletro"
                        else:
                            p_tipo = "Móvel"

                        # Volumes esperados
                        v_esp_raw = get_val(row, "volumes_esperados", "volumes", "vol_esp")
                        if p_tipo == "Eletro":
                            v_esp = 1
                        else:
                            try:
                                v_esp = int(float(v_esp_raw)) if v_esp_raw else 4
                            except:
                                v_esp = 4

                        p_falt = get_val(row, "pecas_faltando", "peças_faltando", "pecas", "acessorios")
                        v_falt = get_val(row, "volumes_faltando", "vol_faltando")

                        # Status inicial
                        if p_falt or v_falt:
                            init_status = "Incompleto"
                        else:
                            init_status = "A conferir"

                        add_single_unit(
                            name=p_name,
                            brand=p_brand,
                            sku=p_sku,
                            category=p_cat,
                            tipo=p_tipo,
                            status=init_status,
                            pecas_faltando=p_falt if p_tipo == "Eletro" else "",
                            volumes_esperados=v_esp,
                            volumes_faltando=v_falt if p_tipo == "Móvel" else "",
                            note="Importado da planilha do Auditor"
                        )
                        total_units_created += 1

                    st.success(f"{total_units_created} unidades importadas com sucesso!")
                    st.rerun()
                else:
                    st.error("Coluna 'produto' não encontrada no arquivo CSV.")
            except Exception as e:
                st.error(f"Erro ao processar CSV: {e}")

    if not df_items.empty:
        csv_data = df_items.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="⬇️ Exportar Base Completa (CSV)",
            data=csv_data,
            file_name=f"estoque_unitario_{datetime.date.today()}.csv",
            mime="text/csv"
        )
        st.divider()
        if st.button("🚨 Limpar Todo o Banco de Dados"):
            clear_all_units()
            st.rerun()

# --- FILTROS E PESQUISA ---
f_col1, f_col2 = st.columns([2.5, 1.5])
with f_col1:
    query = st.text_input("🔍 Buscar por nome, marca, SKU ou categoria", placeholder="Ex: Mondial, Samsung, AT-0019, Geladeira...")
with f_col2:
    filtro_status = st.selectbox("Filtrar por Status", ["Todos"] + STATUS_LIST)

df_view = df_items.copy()
if not df_view.empty:
    if filtro_status != "Todos":
        df_view = df_view[df_view["status"] == filtro_status]
    if query.strip():
        q = query.lower().strip()
        df_view = df_view[
            df_view["name"].str.lower().str.contains(q, na=False) |
            df_view["brand"].fillna("").str.lower().str.contains(q, na=False) |
            df_view["sku"].fillna("").str.lower().str.contains(q, na=False) |
            df_view["category"].fillna("").str.lower().str.contains(q, na=False)
        ]

st.caption(f"Exibindo {len(df_view)} unidade(s) física(s)")

# --- CARDS UNITÁRIOS ---
if df_view.empty:
    st.info("Nenhuma unidade física cadastrada. Utilize o menu lateral para cadastrar ou importar.")
else:
    for _, row in df_view.iterrows():
        with st.container():
            c1, c2, c3 = st.columns([5, 3, 1])
            with c1:
                brand_badge = f'<span class="badge-brand">{row["brand"]}</span>' if row["brand"] else ""
                
                if row["tipo"] == "Eletro":
                    type_badge = '<span class="badge-type">Eletro (1 Vol.)</span>'
                else:
                    v_count = row["volumes_esperados"] if row["volumes_esperados"] else 1
                    type_badge = f'<span class="badge-type">{row["tipo"]} ({v_count} Vols)</span>'

                card_title_html = (
                    f'<div class="unit-title">'
                    f'{row["name"]}'
                    f'{brand_badge}'
                    f'{type_badge}'
                    f'</div>'
                )
                st.markdown(card_title_html, unsafe_allow_html=True)
                
                detalhes = f"**ID:** `#{row['id']}` | **SKU:** {row['sku'] or 'S/N'} | **Categoria:** {row['category'] or 'Geral'}"
                st.write(detalhes)
                
                if row["tipo"] == "Eletro" and row["pecas_faltando"]:
                    st.warning(f"⚠️ **Peças/Acessórios Faltando:** {row['pecas_faltando']}")
                elif row["tipo"] == "Móvel" and (row["volumes_faltando"] or (row["volumes_esperados"] and row["volumes_esperados"] > 1)):
                    msg = f"⚠️ **Volumes do Móvel/Base:** {row['volumes_esperados']} volumes de fábrica"
                    if row["volumes_faltando"]:
                        msg += f" · **Faltando:** {row['volumes_faltando']}"
                    st.warning(msg)

            with c2:
                current_idx = STATUS_LIST.index(row["status"]) if row["status"] in STATUS_LIST else 0
                novo_st = st.selectbox(
                    "Status da Peça",
                    STATUS_LIST,
                    index=current_idx,
                    key=f"status_select_{row['id']}"
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
                if st.button("🗑️ Excluir", key=f"del_btn_{row['id']}"):
                    delete_unit(row["id"])
                    st.rerun()

            # Painel expansível de Edição
            with st.expander("🛠️ Registrar Avaria, Peças/Volumes ou Detalhes"):
                with st.form(key=f"form_unit_{row['id']}"):
                    e1, e2 = st.columns(2)
                    with e1:
                        e_tipo = st.selectbox("Tipo de Item", TIPOS_LIST, index=TIPOS_LIST.index(row["tipo"]) if row["tipo"] in TIPOS_LIST else 0, key=f"et_{row['id']}")
                    with e2:
                        e_st = st.selectbox("Status", STATUS_LIST, index=STATUS_LIST.index(row["status"]) if row["status"] in STATUS_LIST else 0, key=f"es_{row['id']}")

                    e_pf = ""
                    e_ve = None
                    e_vf = ""
                    if e_tipo == "Eletro":
                        st.caption("ℹ️ Eletro possui 1 único volume. Indique se falta algum acessório/peça:")
                        e_pf = st.text_input("Peças / Acessórios Faltando", value=str(row["pecas_faltando"] or ""), key=f"epf_{row['id']}", placeholder="Ex: falta controle remoto e cabo de força")
                    elif e_tipo == "Móvel":
                        st.caption("ℹ️ Móveis e Bases/Colchões possuem múltiplos volumes de fábrica:")
                        m1, m2 = st.columns(2)
                        with m1:
                            e_ve = st.number_input("Volumes Esperados", min_value=1, value=int(row["volumes_esperados"] or 4), key=f"eve_{row['id']}")
                        with m2:
                            e_vf = st.text_input("Volumes Faltando (ex: 2, 4)", value=str(row["volumes_faltando"] or ""), key=f"evf_{row['id']}")

                    e_note = st.text_input("Observação / Motivo da Triagem", placeholder="Ex: Identificada avaria na lateral durante conferência", key=f"enote_{row['id']}")
                    
                    if st.form_submit_button("Salvar Alterações Desta Peça"):
                        update_unit_details(
                            item_id=row["id"],
                            new_status=e_st,
                            new_tipo=e_tipo,
                            pecas_faltando=e_pf.strip(),
                            volumes_esperados=e_ve,
                            volumes_faltando=e_vf.strip(),
                            note=e_note.strip()
                        )
                        st.success("Peça física atualizada com sucesso!")
                        st.rerun()

            # Histórico
            with st.expander("📜 Histórico de Movimentações"):
                hist_df = get_history(row["id"])
                if not hist_df.empty:
                    for _, h in hist_df.iterrows():
                        st.markdown(f"- **{h['date']}** | `{h['status']}` — {h['note']}")
                else:
                    st.caption("Sem movimentações registradas.")

            st.divider()
