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

import re
from datetime import datetime

import pandas as pd
import plotly.express as px
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
        div[data-baseweb="calendar"],
        div[data-baseweb="popover"] div[data-baseweb="calendar"],
        .stDateInput input {{
            background-color: #FFFFFF !important;
            color: {TEXT} !important;
            border: 1px solid {GRID} !important;
            border-radius: 6px !important;
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
            padding-top: 1.2rem;
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
    </style>
    """,
    unsafe_allow_html=True,
)

HOSPITAL_PALETTE = [PRIMARY, ACCENT, PRIMARY_DARK, "#4FC3F7", "#26A69A", "#78909C", WARN]

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

# --------------------------------------------------------------------------
# KPI METRICS
# --------------------------------------------------------------------------
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total de Cirurgias", len(filtered))
k2.metric("Médicos Distintos", filtered[COL_MEDICO].nunique() if COL_MEDICO in filtered.columns else "—")
k3.metric("Blocos em Uso", filtered[COL_BLOCO].nunique() if COL_BLOCO in filtered.columns else "—")
k4.metric("Processos", filtered[COL_PROCESSO].nunique() if COL_PROCESSO in filtered.columns else "—")

st.markdown("---")

# --------------------------------------------------------------------------
# CHARTS
# --------------------------------------------------------------------------
c1, c2 = st.columns(2)

with c1:
    if COL_MEDICO in filtered.columns and not filtered.empty:
        by_med = filtered[COL_MEDICO].value_counts().reset_index()
        by_med.columns = [COL_MEDICO, "Cirurgias"]
        fig = px.bar(
            by_med, x="Cirurgias", y=COL_MEDICO, orientation="h",
            title="Cirurgias por Médico",
            color_discrete_sequence=[PRIMARY],
        )
        fig.update_layout(
            plot_bgcolor=CARD_BG, paper_bgcolor=CARD_BG,
            font_color=TEXT, yaxis=dict(categoryorder="total ascending"),
        )
        st.plotly_chart(fig, use_container_width=True)

with c2:
    if COL_BLOCO in filtered.columns and not filtered.empty:
        by_bloco = filtered[COL_BLOCO].value_counts().reset_index()
        by_bloco.columns = [COL_BLOCO, "Cirurgias"]
        fig2 = px.pie(
            by_bloco, names=COL_BLOCO, values="Cirurgias",
            title="Distribuição por Bloco",
            color_discrete_sequence=HOSPITAL_PALETTE,
            hole=0.45,
        )
        fig2.update_layout(paper_bgcolor=CARD_BG, font_color=TEXT)
        st.plotly_chart(fig2, use_container_width=True)

if COL_DATA in filtered.columns and filtered[COL_DATA].notna().any():
    by_day = filtered.dropna(subset=[COL_DATA]).groupby(filtered[COL_DATA].dt.date).size().reset_index()
    by_day.columns = ["Data", "Cirurgias"]
    fig3 = px.line(
        by_day, x="Data", y="Cirurgias", markers=True,
        title="Cirurgias ao Longo do Tempo",
        color_discrete_sequence=[ACCENT],
    )
    fig3.update_layout(plot_bgcolor=CARD_BG, paper_bgcolor=CARD_BG, font_color=TEXT)
    st.plotly_chart(fig3, use_container_width=True)

st.markdown("---")

# --------------------------------------------------------------------------
# DATA TABLE
# --------------------------------------------------------------------------
st.markdown("### 📋 Lista de Cirurgias (filtradas)")
st.dataframe(filtered, use_container_width=True, hide_index=True)

st.download_button(
    "⬇️ Descarregar dados filtrados (CSV)",
    data=filtered.to_csv(index=False).encode("utf-8-sig"),
    file_name=f"agenda_cirurgica_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
    mime="text/csv",
)

st.caption("Fonte: Google Sheets (ULS Médio Ave) · Atualizado automaticamente a cada 5 minutos.")
