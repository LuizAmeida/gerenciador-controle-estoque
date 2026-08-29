import streamlit as st
import pandas as pd
import sqlite3
import datetime
import io

# ==========================================
# CONFIGURAÇÃO DA PÁGINA E ESTILIZAÇÃO CSS
# ==========================================
st.set_page_config(
    page_title="Controle de Estoque - AT",
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
    margin-bottom: 18px;
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    flex-wrap: wrap;
    gap: 10px;
}
.header-title {
    font-family: 'Segoe UI', Arial, sans-serif;
    text-transform: uppercase;
    font-size: 24px;
    font-weight: 700;
    letter-spacing: .03em;
    margin: 0;
    color: #edeeee;
}
.header-sub {
    color: #9aa0a6;
    font-size: 11px;
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
    grid-template-columns: repeat(8, minmax(80px, 1fr));
    gap: 6px;
    margin-bottom: 20px;
}
@media (max-width: 900px) {
    .stats-grid {
        grid-template-columns: repeat(4, 1fr);
    }
}
.stat-tile {
    background: #24282c;
    border: 1px solid #3a3f45;
    border-radius: 4px;
    padding: 8px 10px;
    text-align: left;
}
.stat-count {
    display: block;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 20px;
    font-weight: 700;
    line-height: 1;
    color: #edeeee;
}
.stat-label {
    display: block;
    font-size: 9px;
    color: #9aa0a6;
    margin-top: 4px;
    text-transform: uppercase;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.unit-title {
    font-size: 16px;
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
# BANCO DE DADOS (SIMPLIFICADO POR PRODUTO)
# ==========================================
DB_NAME = "estoque_at_direto.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            brand TEXT,
            sku TEXT UNIQUE,
            category TEXT,
            tipo TEXT,
            status TEXT NOT NULL,
            volumes_total INTEGER DEFAULT 1,
            volumes_faltando TEXT,
            volumes_avariados TEXT,
            volumes_sobrando TEXT,
            pecas_faltando TEXT
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

def upsert_item(name, brand, sku, category, tipo, status, volumes_total, volumes_faltando, volumes_avariados, volumes_sobrando, pecas_faltando, note):
    """Insere ou atualiza o item caso o SKU já exista, evitando duplicatas."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    sku_val = sku.strip() if sku.strip() else f"GEN-{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    
    c.execute("SELECT id FROM items WHERE sku = ?", (sku_val,))
    existing = c.fetchone()
    date_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    
    if existing:
        item_id = existing[0]
        c.execute("""
            UPDATE items 
            SET name = ?, brand = ?, category = ?, tipo = ?, status = ?,
                volumes_total = ?, volumes_faltando = ?, volumes_avariados = ?,
                volumes_sobrando = ?, pecas_faltando = ?
            WHERE id = ?
        """, (name, brand, category, tipo, status, volumes_total, volumes_faltando, volumes_avariados, volumes_sobrando, pecas_faltando, item_id))
        
        c.execute("INSERT INTO history (item_id, status, date, note) VALUES (?, ?, ?, ?)",
                  (item_id, status, date_str, note or "Item atualizado"))
    else:
        c.execute("""
            INSERT INTO items (name, brand, sku, category, tipo, status, volumes_total, volumes_faltando, volumes_avariados, volumes_sobrando, pecas_faltando)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, brand, sku_val, category, tipo, status, volumes_total, volumes_faltando, volumes_avariados, volumes_sobrando, pecas_faltando))
        item_id = c.lastrowid
        c.execute("INSERT INTO history (item_id, status, date, note) VALUES (?, ?, ?, ?)",
                  (item_id, status, date_str, note or "Item cadastrado"))
        
    conn.commit()
    conn.close()
    return item_id

def update_status_quick(item_id, new_status):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE items SET status = ? WHERE id = ?", (new_status, item_id))
    date_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    c.execute("INSERT INTO history (item_id, status, date, note) VALUES (?, ?, ?, ?)",
              (item_id, new_status, date_str, f"Status alterado para {new_status}"))
    conn.commit()
    conn.close()

def delete_item(item_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM history WHERE item_id = ?", (item_id,))
    c.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

def clear_all_data():
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
    '<span class="header-badge">Gestão de Estoque Físico</span>'
    '</div>'
)
st.markdown(header_html, unsafe_allow_html=True)

df_items = get_items_df()

# Grid de Métricas (8 status)
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
    
    with st.expander("➕ Cadastrar Novo Item", expanded=False):
        with st.form("form_novo_item", clear_on_submit=True):
            name = st.text_input("Nome do Produto *", placeholder="Ex: Guarda-roupa 6 Portas Munique")
            brand = st.text_input("Marca", placeholder="Ex: Madesa, Samsung, Brastemp")
            sku = st.text_input("SKU / Código *", placeholder="Ex: AT-0033")
            category = st.text_input("Categoria", placeholder="Ex: Móveis")
            tipo = st.selectbox("Tipo de Item", TIPOS_LIST, index=1)
            status = st.selectbox("Status Inicial", STATUS_LIST, index=0)
            
            v_total = 1
            v_falt = ""
            v_avar = ""
            v_sobr = ""
            p_falt = ""
            
            if tipo == "Móvel":
                st.caption("📦 Configuração de Volumes do Móvel:")
                v_total = st.number_input("Total de Volumes de Fábrica", min_value=1, value=6, step=1)
                v_falt = st.text_input("Volumes Faltando", placeholder="Ex: Vol 3, Vol 6")
                v_avar = st.text_input("Volumes Avariados", placeholder="Ex: Vol 2")
                v_sobr = st.text_input("Volumes Sobrando", placeholder="Ex: Vol 1")
            elif tipo == "Eletro":
                st.caption("⚡ Eletros possuem 1 volume de fábrica:")
                p_falt = st.text_input("Peças / Acessórios com problema", placeholder="Ex: Falta controle e cabo de força")
            
            note = st.text_input("Observação Inicial", placeholder="Ex: Recebido da conferência")
            submit = st.form_submit_button("Cadastrar Produto")
            
            if submit:
                if name.strip():
                    upsert_item(
                        name=name.strip(),
                        brand=brand.strip(),
                        sku=sku.strip(),
                        category=category.strip(),
                        tipo=tipo,
                        status=status,
                        volumes_total=v_total if tipo == "Móvel" else 1,
                        volumes_faltando=v_falt.strip(),
                        volumes_avariados=v_avar.strip(),
                        volumes_sobrando=v_sobr.strip(),
                        pecas_faltando=p_falt.strip() if tipo == "Eletro" else "",
                        note=note.strip()
                    )
                    st.success("Item cadastrado com sucesso!")
                    st.rerun()
                else:
                    st.error("O campo Nome do Produto é obrigatório.")

    st.markdown("### 📥 Importação de Planilha")
    uploaded_file = st.file_uploader("Subir CSV do Auditor", type=["csv"])
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        btn_importar = st.button("Processar CSV")
    with col_btn2:
        substituir_tudo = st.checkbox("Substituir base atual", value=False, help="Se marcado, limpa o estoque antes de importar")
    
    if uploaded_file is not None and btn_importar:
        try:
            bytes_data = uploaded_file.getvalue()
            try:
                text_data = bytes_data.decode("utf-8-sig")
            except UnicodeDecodeError:
                text_data = bytes_data.decode("latin-1")

            lines = [l.strip() for l in text_data.splitlines() if l.strip()]
            
            if len(lines) < 2:
                st.error("O arquivo CSV precisa ter cabeçalho e dados.")
            else:
                if substituir_tudo:
                    clear_all_data()

                delimiter = ';' if ';' in lines[0] else (',' if ',' in lines[0] else '\t')
                
                count_importados = 0
                for line in lines[1:]:
                    parts = [p.strip().replace('"', '') for p in line.split(delimiter)]
                    if not parts or not parts[0]:
                        continue
                    
                    p_name = parts[0]
                    p_brand = parts[1] if len(parts) > 1 else ""
                    p_sku = parts[2] if len(parts) > 2 else f"AT-{count_importados+1:04d}"
                    p_cat = parts[3] if len(parts) > 3 else ""
                    
                    # Tipo
                    p_tipo_raw = parts[4].capitalize() if len(parts) > 4 and parts[4] else ""
                    if p_tipo_raw in TIPOS_LIST:
                        p_tipo = p_tipo_raw
                    elif any(k in p_name.lower() for k in ["fogão", "geladeira", "tv", "micro", "ar-condicionado", "notebook", "smartphone", "ventilador", "air fryer", "cafeteira", "aspirador", "liquidificador", "batedeira", "purificador", "som", "lava"]):
                        p_tipo = "Eletro"
                    else:
                        p_tipo = "Móvel"

                    # Volumes
                    if p_tipo == "Eletro":
                        v_tot = 1
                    else:
                        try:
                            v_tot = int(float(parts[5])) if len(parts) > 5 and parts[5] else 6
                        except:
                            v_tot = 6

                    p_falt = parts[6] if len(parts) > 6 else ""
                    v_falt = parts[7] if len(parts) > 7 else ""

                    # REGRA: Toda importação do Auditor entra estritamente como "A conferir"
                    upsert_item(
                        name=p_name,
                        brand=p_brand,
                        sku=p_sku,
                        category=p_cat,
                        tipo=p_tipo,
                        status="A conferir",
                        volumes_total=v_tot,
                        volumes_faltando=v_falt if p_tipo == "Móvel" else "",
                        volumes_avariados="",
                        volumes_sobrando="",
                        pecas_faltando=p_falt if p_tipo == "Eletro" else "",
                        note="Importado da planilha do Auditor — aguardando conferência física"
                    )
                    count_importados += 1

                st.success(f"{count_importados} produtos processados como 'A conferir' sem duplicatas!")
                st.rerun()

        except Exception as e:
            st.error(f"Erro ao processar: {e}")

    if not df_items.empty:
        csv_data = df_items.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="⬇️ Exportar Base Completa (CSV)",
            data=csv_data,
            file_name=f"estoque_at_{datetime.date.today()}.csv",
            mime="text/csv"
        )
        st.divider()
        if st.button("🚨 Limpar Todo o Banco de Dados"):
            clear_all_data()
            st.rerun()

# --- FILTROS E PESQUISA ---
f_col1, f_col2 = st.columns([2.5, 1.5])
with f_col1:
    query = st.text_input("🔍 Buscar por nome, marca, SKU ou categoria", placeholder="Ex: Mondial, Madesa, AT-0033, Geladeira...")
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

st.caption(f"Exibindo {len(df_view)} produto(s)")

# --- LISTAGEM DOS PRODUTOS ---
if df_view.empty:
    st.info("Nenhum item cadastrado ou encontrado. Utilize a barra lateral para importar ou cadastrar.")
else:
    for _, row in df_view.iterrows():
        with st.container():
            c1, c2, c3 = st.columns([5, 3, 1])
            with c1:
                brand_badge = f'<span class="badge-brand">{row["brand"]}</span>' if row["brand"] else ""
                
                if row["tipo"] == "Eletro":
                    type_badge = '<span class="badge-type">⚡ Eletro (1 Volume)</span>'
                else:
                    type_badge = f'<span class="badge-type">📦 Móvel ({row["volumes_total"]} Volumes)</span>'

                card_title_html = (
                    f'<div class="unit-title">'
                    f'{row["name"]}'
                    f'{brand_badge}'
                    f'{type_badge}'
                    f'</div>'
                )
                st.markdown(card_title_html, unsafe_allow_html=True)
                
                detalhes = f"**SKU:** `{row['sku']}` | **Categoria:** {row['category'] or 'Geral'}"
                st.write(detalhes)
                
                # Exibição de pendências e apontamentos
                if row["tipo"] == "Eletro" and row["pecas_faltando"]:
                    st.warning(f"⚠️ **Peças/Acessórios:** {row['pecas_faltando']}")
                elif row["tipo"] == "Móvel":
                    avisos = []
                    if row["volumes_faltando"]:
                        avisos.append(f"❌ **Faltando:** {row['volumes_faltando']}")
                    if row["volumes_avariados"]:
                        avisos.append(f"💥 **Avariado(s):** {row['volumes_avariados']}")
                    if row["volumes_sobrando"]:
                        avisos.append(f"➕ **Sobrando:** {row['volumes_sobrando']}")
                    
                    if avisos:
                        st.warning(f"📦 **Apontamento de Volumes (Total: {row['volumes_total']}):** " + " | ".join(avisos))

            with c2:
                current_idx = STATUS_LIST.index(row["status"]) if row["status"] in STATUS_LIST else 0
                novo_st = st.selectbox(
                    "Status do Produto",
                    STATUS_LIST,
                    index=current_idx,
                    key=f"status_select_{row['id']}"
                )
                if novo_st != row["status"]:
                    update_status_quick(row["id"], novo_st)
                    st.rerun()

            with c3:
                st.write("")
                st.write("")
                if st.button("🗑️ Excluir", key=f"del_btn_{row['id']}"):
                    delete_item(row["id"])
                    st.rerun()

            # Painel expansível de Apontamento de Volumes e Detalhes
            with st.expander("🛠️ Apontar Volumes (Faltando/Avariado/Sobrando) ou Peças"):
                with st.form(key=f"form_unit_{row['id']}"):
                    e1, e2 = st.columns(2)
                    with e1:
                        e_tipo = st.selectbox("Tipo de Item", TIPOS_LIST, index=TIPOS_LIST.index(row["tipo"]) if row["tipo"] in TIPOS_LIST else 0, key=f"et_{row['id']}")
                    with e2:
                        e_st = st.selectbox("Status", STATUS_LIST, index=STATUS_LIST.index(row["status"]) if row["status"] in STATUS_LIST else 0, key=f"es_{row['id']}")

                    e_vtot = row["volumes_total"] or 1
                    e_vfalt = row["volumes_faltando"] or ""
                    e_vavar = row["volumes_avariados"] or ""
                    e_vsobr = row["volumes_sobrando"] or ""
                    e_pfalt = row["pecas_faltando"] or ""

                    if e_tipo == "Móvel":
                        st.markdown("##### 📦 Controle de Volumes do Móvel")
                        e_vtot = st.number_input("Quantidade Total de Volumes de Fábrica", min_value=1, value=int(row["volumes_total"] or 6), key=f"vt_{row['id']}")
                        
                        col_m1, col_m2, col_m3 = st.columns(3)
                        with col_m1:
                            e_vfalt = st.text_input("Volumes Faltando", value=str(row["volumes_faltando"] or ""), placeholder="Ex: Vol 3, Vol 6", key=f"vf_{row['id']}")
                        with col_m2:
                            e_vavar = st.text_input("Volumes Avariados", value=str(row["volumes_avariados"] or ""), placeholder="Ex: Vol 2", key=f"va_{row['id']}")
                        with col_m3:
                            e_vsobr = st.text_input("Volumes Sobrando", value=str(row["volumes_sobrando"] or ""), placeholder="Ex: Vol 1", key=f"vs_{row['id']}")
                    elif e_tipo == "Eletro":
                        st.markdown("##### ⚡ Controle de Eletro (1 Volume)")
                        e_vtot = 1
                        e_pfalt = st.text_input("Peças / Acessórios com problema", value=str(row["pecas_faltando"] or ""), placeholder="Ex: Falta controle remoto / cabo", key=f"pf_{row['id']}")

                    e_note = st.text_input("Observação da Conferência", placeholder="Ex: Caixa do espelho (Vol 3) avariada na descarga", key=f"enote_{row['id']}")
                    
                    if st.form_submit_button("Salvar Apontamentos"):
                        upsert_item(
                            name=row["name"],
                            brand=row["brand"],
                            sku=row["sku"],
                            category=row["category"],
                            tipo=e_tipo,
                            status=e_st,
                            volumes_total=e_vtot,
                            volumes_faltando=e_vfalt.strip(),
                            volumes_avariados=e_vavar.strip(),
                            volumes_sobrando=e_vsobr.strip(),
                            pecas_faltando=e_pfalt.strip(),
                            note=e_note.strip()
                        )
                        st.success("Apontamentos salvos com sucesso!")
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
