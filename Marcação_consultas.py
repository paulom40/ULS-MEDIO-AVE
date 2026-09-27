"""
ULS Médio Ave — Painel de Agenda Cirúrgica (Hospital Surgery Schedule)
========================================================================
Streamlit dashboard that reads surgery-schedule data live from a Google
Sheet and lets the user filter by Data (Date), Mês (Month), Processo
(Process), Médico (Doctor) and Bloco (Operating block/room).

HOW TO RUN
----------
1. pip install -r requirements.txt
2. streamlit run app.py

DATA SOURCE
-----------
The app reads the Google Sheet below as a live CSV export. For this to
work, the sheet must be shared as "Anyone with the link -> Viewer".
If your data lives on a specific tab (not the first one), set GID below
to that tab's gid (found in the sheet's URL after "gid=").
"""

import calendar as pycal
import html as html_lib
import io
import re
from datetime import datetime

import pandas as pd
import streamlit as st

# --------------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------------
SHEET_ID = "1tt7-2kCdeJmUbtYaKVkNnZ0EptzcHj-aNhQWF_CIF40"
GID = "0"  # change if your data is on another tab
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

LOGO_PATH = "https://raw.githubusercontent.com/paulom40/ULS-MEDIO-AVE/main/Logo_5.-ULS-MEDIO-AVE.png"

# Column names expected in the sheet — edit here if your headers differ.
COL_DATA = "Data"
COL_MES = "Mês"
COL_PROCESSO = "Processo"
COL_MEDICO = "Médico"
COL_BLOCO = "Bloco"
COL_HORA = "Hora"
COL_ESPECIALIDADE = "Especialidade"
COL_INTERVENCAO = "Intervenção"

MESES_PT = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]

# --------------------------------------------------------------------------
# PAGE SETUP + HOSPITAL COLOR PALETTE
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="ULS Médio Ave | Agenda Cirúrgica",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

PRIMARY = "#0277BD"      # hospital blue
PRIMARY_DARK = "#01579B"
ACCENT = "#00897B"       # clinical teal accent
BG = "#FFFFFF"           # clean white background
SIDEBAR_BG = "#F2F7FA"   # very light blue-gray
CARD_BG = "#FFFFFF"
TEXT = "#1C2B2D"
WARN = "#D84315"         # soft alert red-orange
GRID = "#DCE7ED"

st.markdown(
    f"""
    <style>
        .stApp {{
            background-color: {BG};
            color: {TEXT};
        }}

        /* Hide Streamlit's own top header (menu / GitHub icon) and footer */
        header {{
            visibility: hidden;
            height: 0;
        }}
        footer {{
            visibility: hidden;
            height: 0;
        }}

        section[data-testid="stSidebar"] {{
            background-color: {SIDEBAR_BG};
            border-right: 1px solid {GRID};
        }}
        section[data-testid="stSidebar"] * {{
            color: {TEXT};
        }}
        h1, h2, h3 {{
            color: {PRIMARY_DARK};
            font-family: 'Segoe UI', sans-serif;
        }}

        /* --- Fix dark/black input widgets so they match the light theme --- */
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        div[data-baseweb="base-input"],
        div[data-baseweb="calendar"],
        div[data-baseweb="popover"] div[data-baseweb="calendar"],
        .stDateInput input,
        .stTextInput input,
        input[type="text"],
        input[type="password"],
        textarea {{
            background-color: #FFFFFF !important;
            color: {TEXT} !important;
            border: 1px solid {GRID} !important;
            border-radius: 6px !important;
        }}
        /* Password show/hide eye icon button */
        div[data-baseweb="input"] button {{
            background-color: transparent !important;
        }}

        /* Sidebar multiselect / date-input controls — target Streamlit's
           official stable widget wrapper classes and force every descendant
           to white, since the internal component structure isn't a reliable
           thing to guess at. */
        [data-testid="stDateInput"] *,
        [data-testid="stMultiSelect"] *,
        [data-testid="stSelectbox"] * {{
            background-color: #FFFFFF !important;
            color: {TEXT} !important;
        }}
        /* Icons (dropdown chevron, calendar glyph, clear "x") use nested
           SVG shapes where some parts must stay transparent — forcing fill
           on every part turns them into solid black squares, so only the
           outer svg gets a color and inner shapes inherit it naturally. */
        [data-testid="stDateInput"] svg,
        [data-testid="stMultiSelect"] svg,
        [data-testid="stSelectbox"] svg {{
            fill: {TEXT} !important;
            background-color: transparent !important;
        }}
        [data-testid="stDateInput"] > div,
        [data-testid="stMultiSelect"] > div,
        [data-testid="stSelectbox"] > div {{
            border: 1px solid {GRID} !important;
            border-radius: 6px !important;
        }}
        /* Restore the colored "chip" look for selected multiselect values
           (must come after the wildcard rule above, and be at least as
           specific, so it wins) */
        [data-testid="stMultiSelect"] span[data-baseweb="tag"],
        [data-testid="stMultiSelect"] div[data-baseweb="tag"] {{
            background-color: {PRIMARY} !important;
        }}
        [data-testid="stMultiSelect"] span[data-baseweb="tag"] *,
        [data-testid="stMultiSelect"] div[data-baseweb="tag"] * {{
            color: #FFFFFF !important;
            fill: #FFFFFF !important;
        }}
        /* The dropdown menu that opens on click (portalled, may render
           outside the sidebar in the DOM, so it's targeted separately) */
        div[data-baseweb="popover"] * {{
            background-color: #FFFFFF !important;
            color: {TEXT} !important;
        }}

        /* Tabs (Dashboard / Calendário) — the inactive tab's text was
           invisible (white on white); force both states to be legible */
        button[data-baseweb="tab"] {{
            color: {TEXT} !important;
            background-color: transparent !important;
        }}
        button[data-baseweb="tab"] p {{
            color: {TEXT} !important;
        }}
        button[data-baseweb="tab"][aria-selected="true"],
        button[data-baseweb="tab"][aria-selected="true"] p {{
            color: {PRIMARY} !important;
        }}
        [data-baseweb="tab-highlight"] {{
            background-color: {PRIMARY} !important;
        }}
        [data-baseweb="tab-border"] {{
            background-color: {GRID} !important;
        }}
        [data-baseweb="tab-list"] {{
            background-color: transparent !important;
        }}
        /* Form submit buttons (e.g. the login "Entrar" button) */
        div[data-testid="stFormSubmitButton"] button {{
            background-color: {PRIMARY} !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 6px !important;
        }}
        div[data-testid="stFormSubmitButton"] button:hover {{
            background-color: {PRIMARY_DARK} !important;
            color: #FFFFFF !important;
        }}
        /* Hide any GitHub / Streamlit badge links injected by the hosting platform */
        a[href*="github.com"],
        a[href*="streamlit.io"] {{
            display: none !important;
        }}
        [data-testid="stStatusWidget"] {{
            visibility: hidden !important;
        }}
        div[data-baseweb="select"] span,
        div[data-baseweb="tag"] {{
            color: {TEXT} !important;
        }}
        div[data-baseweb="tag"] {{
            background-color: {PRIMARY} !important;
        }}
        div[data-baseweb="tag"] span {{
            color: #FFFFFF !important;
        }}
        ul[data-baseweb="menu"] {{
            background-color: #FFFFFF !important;
            color: {TEXT} !important;
        }}
        ul[data-baseweb="menu"] li:hover {{
            background-color: {SIDEBAR_BG} !important;
        }}

        div[data-testid="stMetric"] {{
            background-color: {CARD_BG};
            border: 1px solid {GRID};
            border-left: 6px solid {PRIMARY};
            border-radius: 10px;
            padding: 14px 16px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.05);
        }}
        div[data-testid="stMetricLabel"] {{
            color: {PRIMARY_DARK};
            font-weight: 600;
        }}
        div[data-testid="stMetricValue"] {{
            color: {TEXT};
        }}
        .stDataFrame {{
            border: 1px solid {GRID};
            border-radius: 8px;
        }}
        .block-container {{
            padding-top: 1.5rem;
        }}
        hr {{
            border-top: 1px solid {GRID};
        }}
        .stButton button, .stDownloadButton button {{
            background-color: {PRIMARY};
            color: #FFFFFF;
            border: none;
            border-radius: 6px;
        }}
        .stButton button:hover, .stDownloadButton button:hover {{
            background-color: {PRIMARY_DARK};
            color: #FFFFFF;
        }}
        .top-banner {{
            background: linear-gradient(90deg, {PRIMARY_DARK} 0%, {PRIMARY} 55%, {ACCENT} 100%);
            padding: 14px 22px;
            border-radius: 10px;
            color: white;
            margin-bottom: 18px;
        }}
        .top-banner h1 {{
            color: white !important;
            margin: 0;
            font-size: 1.6rem;
        }}
        .top-banner p {{
            margin: 0;
            opacity: 0.9;
            font-size: 0.9rem;
        }}

        /* --- Calendar tab --- */
        .cal-grid {{
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            gap: 6px;
            margin-top: 8px;
        }}
        .cal-dow {{
            text-align: center;
            font-weight: 600;
            color: {PRIMARY_DARK};
            padding: 4px 0;
            font-size: 0.85rem;
        }}
        .cal-cell {{
            background-color: {CARD_BG};
            border: 1px solid {GRID};
            border-radius: 8px;
            min-height: 220px;
            padding: 8px;
            display: flex;
            flex-direction: column;
        }}
        .cal-cell.empty {{
            background-color: {SIDEBAR_BG};
            border: 1px dashed {GRID};
            min-height: 60px;
        }}
        .cal-cell.today {{
            border: 2px solid {ACCENT};
        }}
        .cal-daynum {{
            font-weight: 700;
            color: {PRIMARY_DARK};
            font-size: 1rem;
            margin-bottom: 6px;
            flex: 0 0 auto;
        }}
        .cal-events {{
            overflow-y: auto;
            max-height: 260px;
            display: flex;
            flex-direction: column;
            gap: 4px;
            scrollbar-width: thin;
        }}
        .cal-event {{
            flex: 0 0 auto;
            background-color: {PRIMARY};
            color: #FFFFFF;
            font-size: 0.82rem;
            line-height: 1.5;
            padding: 4px 7px;
            border-radius: 4px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            cursor: default;
        }}
        .cal-event:nth-child(odd) {{
            background-color: {ACCENT};
        }}
        .cal-event:hover {{
            filter: brightness(1.15);
        }}
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------
# LOGIN GATE
# --------------------------------------------------------------------------
VALID_USER = "0000"
VALID_PASSWORD = "0000"

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    col_a, col_b, col_c = st.columns([1, 1.2, 1])
    with col_b:
        try:
            st.image(LOGO_PATH, use_container_width=True)
        except Exception:
            pass
        st.markdown(
            f"""
            <div style="text-align:center; margin-bottom: 10px;">
                <h2 style="color:{PRIMARY_DARK}; margin-bottom:0;">Agenda Cirúrgica</h2>
                <p style="color:{TEXT}; opacity:0.75;">Inicie sessão para aceder ao painel</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("login_form"):
            user_input = st.text_input("Utilizador")
            pass_input = st.text_input("Palavra-passe", type="password")
            submitted = st.form_submit_button("Entrar", use_container_width=True)
            if submitted:
                if user_input == VALID_USER and pass_input == VALID_PASSWORD:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Utilizador ou palavra-passe incorretos.")
    st.stop()

# --------------------------------------------------------------------------
# HEADER — logo top-left + title banner
# --------------------------------------------------------------------------
col_logo, col_title = st.columns([1, 5], vertical_alignment="center")
with col_logo:
    try:
        st.image(LOGO_PATH, use_container_width=True)
    except Exception:
        st.write("🏥")
with col_title:
    st.markdown(
        """
        <div class="top-banner">
            <h1>Agenda Cirúrgica — ULS Médio Ave</h1>
            <p>Painel de gestão e acompanhamento das cirurgias agendadas</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

# --------------------------------------------------------------------------
# DATA LOADING
# --------------------------------------------------------------------------
@st.cache_data(ttl=300, show_spinner="A carregar dados da folha de cálculo...")
def load_data(url: str) -> pd.DataFrame:
    df = pd.read_csv(url)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def normalize_month_pt(series: pd.Series) -> pd.Series:
    """Map month numbers/names to standard Portuguese month names."""
    def to_month_name(val):
        if pd.isna(val):
            return None
        s = str(val).strip()
        if s.isdigit():
            idx = int(s)
            if 1 <= idx <= 12:
                return MESES_PT[idx - 1]
        s_norm = s.lower()
        for m in MESES_PT:
            if m.lower().startswith(s_norm[:3]):
                return m
        return s
    return series.apply(to_month_name)


try:
    raw_df = load_data(CSV_URL)
except Exception as e:
    st.error(
        "Não foi possível carregar os dados da Google Sheet.\n\n"
        "Verifique se a folha está partilhada como **\"Qualquer pessoa com "
        "o link -> Leitor\"** e se o `GID` no topo do script corresponde "
        "ao separador correto.\n\n"
        f"Detalhe técnico: {e}"
    )
    st.stop()

df = raw_df.copy()

# Parse date column
if COL_DATA in df.columns:
    df[COL_DATA] = pd.to_datetime(df[COL_DATA], errors="coerce", dayfirst=True)
else:
    st.warning(f"Coluna '{COL_DATA}' não encontrada na folha. Ajuste COL_DATA no script.")

# Derive/normalize Mês column
if COL_MES in df.columns:
    df[COL_MES] = normalize_month_pt(df[COL_MES])
elif COL_DATA in df.columns:
    df[COL_MES] = df[COL_DATA].dt.month.apply(
        lambda m: MESES_PT[int(m) - 1] if pd.notna(m) else None
    )

# --------------------------------------------------------------------------
# SIDEBAR FILTERS
# --------------------------------------------------------------------------
try:
    st.sidebar.image(LOGO_PATH, use_container_width=True)
except Exception:
    pass
st.sidebar.markdown("## 🔍 Filtros")
st.sidebar.markdown("---")

filtered = df.copy()

# Data (date range) filter
if COL_DATA in df.columns and df[COL_DATA].notna().any():
    min_date = df[COL_DATA].min().date()
    max_date = df[COL_DATA].max().date()
    st.sidebar.markdown("**📅 Data**")
    date_range = st.sidebar.date_input(
        "Intervalo de datas",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        label_visibility="collapsed",
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start, end = date_range
        filtered = filtered[
            (filtered[COL_DATA].dt.date >= start) & (filtered[COL_DATA].dt.date <= end)
        ]

# Mês filter
if COL_MES in df.columns:
    st.sidebar.markdown("**🗓️ Mês**")
    meses_disponiveis = [m for m in MESES_PT if m in df[COL_MES].dropna().unique()]
    outros = sorted(set(df[COL_MES].dropna().unique()) - set(meses_disponiveis))
    opcoes_mes = meses_disponiveis + outros
    sel_mes = st.sidebar.multiselect("Selecionar mês(es)", opcoes_mes, default=[], label_visibility="collapsed")
    if sel_mes:
        filtered = filtered[filtered[COL_MES].isin(sel_mes)]

# Processo filter
if COL_PROCESSO in df.columns:
    st.sidebar.markdown("**🧾 Processo**")
    proc_opts = sorted(df[COL_PROCESSO].dropna().astype(str).unique())
    sel_proc = st.sidebar.multiselect("Selecionar processo(s)", proc_opts, default=[], label_visibility="collapsed")
    if sel_proc:
        filtered = filtered[filtered[COL_PROCESSO].astype(str).isin(sel_proc)]

# Médico filter
if COL_MEDICO in df.columns:
    st.sidebar.markdown("**👨‍⚕️ Médico**")
    med_opts = sorted(df[COL_MEDICO].dropna().astype(str).unique())
    sel_med = st.sidebar.multiselect("Selecionar médico(s)", med_opts, default=[], label_visibility="collapsed")
    if sel_med:
        filtered = filtered[filtered[COL_MEDICO].astype(str).isin(sel_med)]

# Bloco filter
if COL_BLOCO in df.columns:
    st.sidebar.markdown("**🚪 Bloco**")
    bloco_opts = sorted(df[COL_BLOCO].dropna().astype(str).unique())
    sel_bloco = st.sidebar.multiselect("Selecionar bloco(s)", bloco_opts, default=[], label_visibility="collapsed")
    if sel_bloco:
        filtered = filtered[filtered[COL_BLOCO].astype(str).isin(sel_bloco)]

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Atualizar dados"):
    st.cache_data.clear()
    st.rerun()
if st.sidebar.button("🚪 Terminar sessão"):
    st.session_state.authenticated = False
    st.rerun()

def to_excel_bytes(data: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        data.to_excel(writer, index=False, sheet_name="Agenda Cirurgica")
    return buffer.getvalue()


def safe(row, col):
    """Return a clean string for a field, or '—' if missing/empty."""
    if col not in row.index:
        return "—"
    val = row[col]
    if pd.isna(val) or str(val).strip() == "":
        return "—"
    return str(val).strip()


tab_dashboard, tab_calendar = st.tabs(["📊 Dashboard", "📅 Calendário"])

# ==========================================================================
# TAB 1 — DASHBOARD
# ==========================================================================
with tab_dashboard:
    # ---------------- KPI METRICS ----------------
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total de Cirurgias", len(filtered))
    k2.metric("Médicos Distintos", filtered[COL_MEDICO].nunique() if COL_MEDICO in filtered.columns else "—")
    k3.metric("Blocos em Uso", filtered[COL_BLOCO].nunique() if COL_BLOCO in filtered.columns else "—")
    k4.metric("Processos", filtered[COL_PROCESSO].nunique() if COL_PROCESSO in filtered.columns else "—")

    st.markdown("---")

    # ---------------- DATA TABLE ----------------
    # st.dataframe renders on an HTML canvas, so plain CSS can't recolor its
    # cells — we style the data itself via a pandas Styler instead.
    st.markdown("### 📋 Lista de Cirurgias (filtradas)")
    table_style = filtered.style.set_properties(**{
        "background-color": "#FFFFFF",
        "color": TEXT,
    })
    st.dataframe(table_style, use_container_width=True, hide_index=True)

    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        st.download_button(
            "⬇️ Descarregar CSV",
            data=filtered.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"agenda_cirurgica_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with dl_col2:
        st.download_button(
            "⬇️ Descarregar Excel",
            data=to_excel_bytes(filtered),
            file_name=f"agenda_cirurgica_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    st.caption("Fonte: Google Sheets (ULS Médio Ave) · Atualizado automaticamente a cada 5 minutos.")

# ==========================================================================
# TAB 2 — CALENDÁRIO (Google Calendar-style month view)
# ==========================================================================
with tab_calendar:
    st.markdown("### 📅 Calendário de Cirurgias")
    st.caption("Uma linha por cirurgia (Hora · Processo · Especialidade). Passe o rato por cima para ver todos os detalhes.")

    if COL_DATA not in filtered.columns or filtered[COL_DATA].dropna().empty:
        st.info("Sem datas disponíveis para mostrar no calendário com os filtros atuais.")
    else:
        cal_df = filtered.dropna(subset=[COL_DATA]).copy()
        cal_df["_year"] = cal_df[COL_DATA].dt.year
        cal_df["_month"] = cal_df[COL_DATA].dt.month

        year_months = sorted(
            {(int(y), int(m)) for y, m in zip(cal_df["_year"], cal_df["_month"])}
        )

        if not year_months:
            st.info("Sem datas disponíveis para mostrar no calendário com os filtros atuais.")
        else:
            option_labels = [f"{MESES_PT[m - 1]} {y}" for y, m in year_months]

            today = datetime.now()
            default_idx = 0
            for i, (y, m) in enumerate(year_months):
                if (y, m) <= (today.year, today.month):
                    default_idx = i

            sel_label = st.selectbox("Mês a visualizar", option_labels, index=default_idx)
            sel_year, sel_month = year_months[option_labels.index(sel_label)]

            month_events = cal_df[(cal_df["_year"] == sel_year) & (cal_df["_month"] == sel_month)]

            # Sort each day's surgeries by Hora when available
            if COL_HORA in month_events.columns:
                month_events = month_events.sort_values(by=[COL_DATA, COL_HORA])
            else:
                month_events = month_events.sort_values(by=[COL_DATA])

            events_by_day = {}
            for _, row in month_events.iterrows():
                day = row[COL_DATA].day
                events_by_day.setdefault(day, []).append(row)

            pycal.setfirstweekday(pycal.MONDAY)
            weeks = pycal.monthcalendar(sel_year, sel_month)
            dow_labels = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

            html_parts = ['<div class="cal-grid">']
            for lbl in dow_labels:
                html_parts.append(f'<div class="cal-dow">{lbl}</div>')

            is_current_month = (sel_year == today.year and sel_month == today.month)

            for week in weeks:
                for day in week:
                    if day == 0:
                        html_parts.append('<div class="cal-cell empty"></div>')
                        continue

                    is_today = is_current_month and day == today.day
                    cell_classes = "cal-cell" + (" today" if is_today else "")

                    events_html = ""
                    for row in events_by_day.get(day, []):
                        hora = safe(row, COL_HORA)
                        processo = safe(row, COL_PROCESSO)
                        especialidade = safe(row, COL_ESPECIALIDADE)
                        intervencao = safe(row, COL_INTERVENCAO)
                        medico = safe(row, COL_MEDICO)
                        bloco = safe(row, COL_BLOCO)

                        one_line = html_lib.escape(f"{hora} · {processo} · {especialidade}")
                        full_detail = html_lib.escape(
                            f"Hora: {hora}\n"
                            f"Processo: {processo}\n"
                            f"Especialidade: {especialidade}\n"
                            f"Intervenção: {intervencao}\n"
                            f"Médico: {medico}\n"
                            f"Bloco: {bloco}"
                        )
                        events_html += f'<div class="cal-event" title="{full_detail}">{one_line}</div>'

                    html_parts.append(
                        f'<div class="{cell_classes}">'
                        f'<div class="cal-daynum">{day}</div>'
                        f'<div class="cal-events">{events_html}</div>'
                        f'</div>'
                    )
            html_parts.append('</div>')

            st.markdown("".join(html_parts), unsafe_allow_html=True)

            st.markdown("")
            month_export = month_events.drop(columns=["_year", "_month"], errors="ignore")
            st.download_button(
                f"⬇️ Descarregar Excel — {sel_label}",
                data=to_excel_bytes(month_export),
                file_name=f"agenda_cirurgica_{sel_year}_{sel_month:02d}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
