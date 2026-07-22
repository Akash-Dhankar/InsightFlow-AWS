"""
app.py – InsightFlow: AI-Powered Data Analyst Agent

Main entry point for the Streamlit dashboard.
Run with: streamlit run app.py
"""

import html
from datetime import datetime

import pandas as pd
import streamlit as st

from prompts import (
    INSIGHT_PROMPT_TEMPLATE,
    QA_PROMPT_TEMPLATE,
    RAG_QA_PROMPT_TEMPLATE,
    SYSTEM_PROMPT,
)
from utils.analyzer import get_data_quality, get_overview, get_statistics, load_csv
from utils.charts import plot_bar_charts, plot_correlation_heatmap, plot_histograms
from utils.llm import generate_response, is_ollama_running
from utils.pdf_report import generate_pdf_report
from utils.rag import build_embeddings, retrieve_relevant_rows

st.set_page_config(
    page_title="InsightFlow - AI Data Analyst",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
        --bg: #0b1020;
        --panel: rgba(17, 24, 39, 0.72);
        --card: rgba(255, 255, 255, 0.035);
        --border: rgba(255, 255, 255, 0.08);
        --text: #f8fafc;
        --muted: #94a3b8;
        --radius: 18px;
        --shadow: 0 12px 32px rgba(0,0,0,0.22);
        --shadow-soft: 0 8px 18px rgba(0,0,0,0.14);
    }

    html, body, [class*="css"] {
        background: var(--bg);
        color: var(--text);
    }

    #MainMenu, footer, header[data-testid="stHeader"] {
        visibility: hidden;
    }

    [data-testid="stAppViewContainer"] {
        background:
            radial-gradient(circle at top left, rgba(99,102,241,0.16), transparent 26%),
            radial-gradient(circle at top right, rgba(14,165,233,0.10), transparent 24%),
            var(--bg);
    }

    [data-testid="stToolbar"] {
        display: none !important;
    }

    .main .block-container {
        padding-top: 2rem !important;
        padding-left: 1.8rem !important;
        padding-right: 1.8rem !important;
        padding-bottom: 2rem !important;
        max-width: 1440px;
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0a1020 0%, #0f172a 100%) !important;
        border-right: 1px solid rgba(255,255,255,0.06) !important;
    }

    section[data-testid="stSidebar"] .block-container {
        padding: 1.15rem 0.95rem !important;
    }

    [data-testid="stVerticalBlock"] {
        gap: 0.85rem;
    }

    .stButton > button {
        border-radius: 14px !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        background: rgba(255,255,255,0.05) !important;
        color: var(--text) !important;
        box-shadow: none !important;
        transition: all 0.18s ease !important;
        padding: 0.58rem 1rem !important;
    }

    .stButton > button:hover {
        transform: translateY(-1px);
        border-color: rgba(99,102,241,0.35) !important;
        background: rgba(99,102,241,0.12) !important;
    }

    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%) !important;
        color: white !important;
        border: 0 !important;
    }

    .stButton > button[kind="primary"]:hover {
        filter: brightness(1.05);
    }

    [data-testid="stFileUploader"] {
        width: 100%;
    }

    [data-testid="stFileUploader"] section {
        background: rgba(255,255,255,0.03);
        border: 1px dashed rgba(255,255,255,0.12);
        border-radius: 18px;
        padding: 1rem;
    }

    [data-testid="stFileUploader"] section:hover {
        border-color: rgba(99,102,241,0.28);
        background: rgba(99,102,241,0.05);
    }

    [data-testid="stFileUploader"] button {
        border-radius: 12px !important;
        padding: 0.5rem 0.95rem !important;
    }

    [data-testid="stDataFrame"] {
        border-radius: var(--radius);
        overflow: hidden;
        border: 1px solid var(--border);
        box-shadow: var(--shadow-soft);
    }

    [data-testid="stExpander"] {
        border-radius: var(--radius);
        border: 1px solid var(--border);
        background: rgba(255,255,255,0.02);
    }

    [data-baseweb="tab-list"] {
        gap: 0.35rem;
        background: rgba(255,255,255,0.03);
        padding: 0.45rem;
        border: 1px solid var(--border);
        border-radius: 18px;
    }

    [data-baseweb="tab"] {
        border-radius: 14px !important;
        color: var(--muted) !important;
        padding: 0.75rem 1rem !important;
        font-weight: 600 !important;
    }

    [data-baseweb="tab"][aria-selected="true"] {
        background: rgba(99,102,241,0.16) !important;
        color: var(--text) !important;
        border: 1px solid rgba(99,102,241,0.28) !important;
    }

    .hero {
        background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.03));
        border: 1px solid var(--border);
        border-radius: 24px;
        padding: 1.7rem 1.8rem;
        box-shadow: var(--shadow);
    }

    .hero-title {
        font-size: 2rem;
        line-height: 1.15;
        margin: 0 0 0.45rem 0;
        color: var(--text);
        font-weight: 800;
        letter-spacing: -0.03em;
    }

    .hero-subtitle {
        color: var(--muted);
        margin: 0;
        font-size: 1rem;
        line-height: 1.6;
        max-width: 980px;
    }

    .section-card {
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 20px;
        box-shadow: var(--shadow-soft);
        padding: 1.15rem 1.15rem 1rem 1.15rem;
        margin-bottom: 0.9rem;
    }

    .section-title {
        font-size: 1.05rem;
        font-weight: 800;
        color: var(--text);
        margin-bottom: 0.85rem;
        letter-spacing: -0.01em;
    }

    .metric-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.9rem;
        margin: 0.9rem 0 1rem 0;
    }

    .kpi-card {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 1rem;
        box-shadow: var(--shadow-soft);
    }

    .kpi-label {
        color: var(--muted);
        font-size: 0.82rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }

    .kpi-value {
        color: var(--text);
        font-size: 1.75rem;
        font-weight: 800;
        margin-top: 0.35rem;
        letter-spacing: -0.04em;
    }

    .ai-card {
        background: rgba(255,255,255,0.03);
        border: 1px solid var(--border);
        border-radius: 18px;
        padding: 1rem;
        box-shadow: var(--shadow-soft);
    }

    .ai-tag {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        color: #c7d2fe;
        background: rgba(99,102,241,0.12);
        border: 1px solid rgba(99,102,241,0.18);
        border-radius: 999px;
        padding: 0.35rem 0.65rem;
        font-size: 0.75rem;
        font-weight: 700;
        margin-bottom: 0.75rem;
    }

    .chat-wrap {
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 22px;
        box-shadow: var(--shadow-soft);
        padding: 1rem;
    }

    .chat-scroll {
        max-height: 600px;
        overflow-y: auto;
        padding-right: 0.25rem;
    }

    .chat-row {
        display: flex;
        margin: 0.8rem 0;
    }

    .chat-row.user {
        justify-content: flex-end;
    }

    .chat-row.ai {
        justify-content: flex-start;
    }

    .chat-bubble {
        max-width: min(78%, 920px);
        border-radius: 18px;
        padding: 0.95rem 1rem;
        line-height: 1.55;
        font-size: 0.95rem;
        white-space: pre-wrap;
    }

    .chat-row.user .chat-bubble {
        background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
        color: white;
        border-bottom-right-radius: 6px;
    }

    .chat-row.ai .chat-bubble {
        background: rgba(255,255,255,0.04);
        border: 1px solid var(--border);
        color: var(--text);
        border-bottom-left-radius: 6px;
    }

    .chat-meta {
        font-size: 0.72rem;
        color: var(--muted);
        margin-top: 0.35rem;
    }

    .quality-wrap {
        display: grid;
        grid-template-columns: minmax(180px, 220px) 1fr;
        gap: 1.5rem;
        align-items: center;
        margin-bottom: 1rem;
    }

    .score-ring {
        width: 170px;
        height: 170px;
        border-radius: 50%;
        display: grid;
        place-items: center;
        margin: 0 auto;
        box-shadow: inset 0 0 0 12px rgba(255,255,255,0.03);
    }

    .quality-summary-panel {
        display: flex;
        flex-direction: column;
        gap: 0.85rem;
    }

    .quality-metric-row {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        padding: 0.55rem 0;
        border-bottom: 1px solid rgba(255,255,255,0.05);
        color: var(--muted);
        font-size: 0.92rem;
    }

    .quality-metric-row:last-child {
        border-bottom: none;
        padding-bottom: 0;
    }

    .quality-metric-row b {
        color: var(--text);
    }

    .quality-alert {
        border-radius: 14px;
        padding: 0.85rem 1rem;
        margin-top: 0.75rem;
        font-size: 0.92rem;
        line-height: 1.5;
    }

    .quality-alert.warning {
        background: rgba(245, 158, 11, 0.1);
        border: 1px solid rgba(245, 158, 11, 0.28);
        color: #fcd34d;
    }

    .quality-alert.danger {
        background: rgba(239, 68, 68, 0.1);
        border: 1px solid rgba(239, 68, 68, 0.28);
        color: #fca5a5;
    }

    .quality-alert.success {
        background: rgba(34, 197, 94, 0.1);
        border: 1px solid rgba(34, 197, 94, 0.28);
        color: #86efac;
    }

    .score-inner {
        width: 126px;
        height: 126px;
        border-radius: 50%;
        background: #0d1428;
        border: 1px solid var(--border);
        display: grid;
        place-items: center;
        text-align: center;
    }

    .score-number {
        font-size: 2rem;
        font-weight: 800;
        color: var(--text);
        line-height: 1;
    }

    .score-label {
        font-size: 0.8rem;
        color: var(--muted);
        margin-top: 0.3rem;
        font-weight: 600;
    }

    .sidebar-shell {
        display: flex;
        flex-direction: column;
        gap: 0.95rem;
        color: var(--text);
    }

    .sidebar-brand {
        display: flex;
        align-items: center;
        gap: 0.8rem;
        padding: 0.25rem 0.1rem 0.9rem 0.1rem;
        border-bottom: 1px solid rgba(255,255,255,0.06);
    }

    .sidebar-logo {
        width: 44px;
        height: 44px;
        border-radius: 14px;
        display: grid;
        place-items: center;
        font-weight: 800;
        color: #e0e7ff;
        background: linear-gradient(135deg, rgba(99,102,241,0.24), rgba(14,165,233,0.12));
        border: 1px solid rgba(129,140,248,0.22);
        box-shadow: 0 10px 20px rgba(0,0,0,0.22);
    }

    .sidebar-title {
        font-size: 1rem;
        font-weight: 800;
        letter-spacing: -0.02em;
    }

    .sidebar-subtitle {
        color: var(--muted);
        font-size: 0.78rem;
        margin-top: 0.1rem;
    }

    .sidebar-section {
        display: flex;
        flex-direction: column;
        gap: 0.55rem;
    }

    .sidebar-label {
        color: #64748b;
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        font-weight: 700;
    }

    .sidebar-chip {
        display: inline-flex;
        align-items: center;
        gap: 0.55rem;
        width: fit-content;
        padding: 0.55rem 0.75rem;
        color: #cbd5e1;
        font-size: 0.86rem;
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 16px;
        box-shadow: 0 8px 22px rgba(0,0,0,0.14);
    }

    .sidebar-dot {
        width: 9px;
        height: 9px;
        border-radius: 50%;
        background: #22c55e;
        box-shadow: 0 0 10px rgba(34,197,94,0.45);
    }

    @media (max-width: 1100px) {
        .metric-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .quality-wrap {
            grid-template-columns: 1fr;
        }
    }

    @media (max-width: 760px) {
        .main .block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
        .metric-grid {
            grid-template-columns: 1fr;
        }
        .hero {
            padding: 1.3rem;
        }
        .hero-title {
            font-size: 1.65rem;
        }
        .chat-bubble {
            max-width: 92%;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _render_chart_image(img_bytes, caption: str) -> None:
    """Render a PNG chart using Streamlit 1.32-compatible image API."""
    img_bytes.seek(0)
    st.image(img_bytes, caption=caption, use_column_width=True)


def _show_chart_warnings(warnings: list[str]) -> None:
    for message in warnings:
        st.warning(message)


def _quality_ring_style(score: float) -> str:
    """
    Build inline CSS for the quality donut ring.
    Maps score (0-100) to a conic-gradient fill angle (0-360deg).
    """
    score = max(0.0, min(100.0, float(score)))
    track_color = "rgba(255,255,255,0.08)"

    if score >= 80:
        fill_color = "#22c55e"
    elif score >= 60:
        fill_color = "#f59e0b"
    else:
        fill_color = "#ef4444"

    if score >= 100.0:
        return f"background: {fill_color};"

    if score <= 0.0:
        return f"background: conic-gradient({track_color} 0deg, {track_color} 360deg);"

    fill_deg = round(score * 3.6, 2)
    return (
        f"background: conic-gradient("
        f"{fill_color} 0deg, {fill_color} {fill_deg}deg, "
        f"{track_color} {fill_deg}deg, {track_color} 360deg"
        f");"
    )


def _quality_label(score: float) -> str:
    if score >= 100:
        return "Excellent Quality"
    if score >= 80:
        return "Good Quality"
    if score >= 60:
        return "Moderate Quality"
    return "Poor Quality"


def _build_context(df: pd.DataFrame) -> dict:
    overview = get_overview(df)
    quality = get_data_quality(df)
    stats = get_statistics(df)
    return {
        "rows": overview["rows"],
        "cols": overview["columns"],
        "dtypes": overview["dtypes"],
        "missing": quality["missing_values"],
        "duplicates": quality["duplicate_rows"],
        "statistics": stats["text_summary"],
    }


ollama_ok = is_ollama_running()

with st.sidebar:
    st.markdown(
        f"""
        <div class="sidebar-shell">
            <div class="sidebar-brand">
                <div class="sidebar-logo">IF</div>
                <div>
                    <div class="sidebar-title">InsightFlow</div>
                    <div class="sidebar-subtitle">AI Data Analyst</div>
                </div>
            </div>
            <div class="sidebar-section">
                <div class="sidebar-label">Connection</div>
                <div class="sidebar-chip">
                    <span class="sidebar-dot" style="background:{'#22c55e' if ollama_ok else '#ef4444'}"></span>
                    <span>{'Ollama Live' if ollama_ok else 'Ollama Offline'}</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
    selected_tab = st.radio(
        "Navigation",
        ["Overview", "Data Quality", "Statistics", "Visualizations", "AI Insights", "Ask Questions"],
        label_visibility="collapsed",
    )

st.markdown(
    """
    <div class="hero">
        <div class="hero-title">AI-Powered Data Analyst Agent</div>
        <div class="hero-subtitle">
            Upload a dataset, generate insights, visualize trends, and interact with your data using natural language.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="section-card">
        <div class="section-title">Upload Dataset</div>
    </div>
    """,
    unsafe_allow_html=True,
)

uploaded_file = st.file_uploader(
    "Upload CSV",
    type=["csv"],
    label_visibility="collapsed",
    help="Upload a CSV file to begin",
)

if uploaded_file is None:
    st.info("Upload a CSV file to begin.")
    st.stop()

with st.spinner("Loading and validating CSV..."):
    try:
        df = load_csv(uploaded_file)
    except ValueError as exc:
        st.error(f"Could not load CSV: {exc}")
        st.stop()

st.session_state["df"] = df
st.success(f"Loaded **{df.shape[0]:,} rows** and **{df.shape[1]} columns**.")

with st.spinner("Preparing TF-IDF context for Q&A..."):
    rag_state = build_embeddings(df)
    st.session_state["rag_available"] = rag_state["available"]
    st.session_state["rag_vectors"] = rag_state["vectors"]
    st.session_state["rag_docs"] = rag_state["docs"]
    st.session_state["rag_vectorizer"] = rag_state["vectorizer"]
    st.session_state["rag_fallback"] = rag_state["fallback_context"]

if not rag_state["available"]:
    st.info(
        "Row-level TF-IDF indexing is unavailable for this dataset. "
        "Q&A will use dataset summary and sample rows instead."
    )

overview = get_overview(df)
quality = get_data_quality(df)
stats = get_statistics(df)

missing_count = 0
if quality["missing_values"] != "None":
    missing_count = sum(quality["missing_values"].values())

st.markdown(
    f"""
    <div class="metric-grid">
        <div class="kpi-card"><div class="kpi-label">Rows</div><div class="kpi-value">{overview["rows"]}</div></div>
        <div class="kpi-card"><div class="kpi-label">Columns</div><div class="kpi-value">{overview["columns"]}</div></div>
        <div class="kpi-card"><div class="kpi-label">Missing Values</div><div class="kpi-value">{missing_count}</div></div>
        <div class="kpi-card"><div class="kpi-label">Duplicate Rows</div><div class="kpi-value">{quality["duplicate_rows"]}</div></div>
    </div>
    """,
    unsafe_allow_html=True,
)

if "pdf_buffer" not in st.session_state:
    st.session_state["pdf_buffer"] = None

col_pdf_space, col_pdf = st.columns([4, 1])
with col_pdf:
    if st.button("Generate PDF Report", type="primary", use_container_width=True):
        with st.spinner("Generating PDF report..."):
            try:
                ov = get_overview(st.session_state["df"])
                ql = get_data_quality(st.session_state["df"])
                sts = get_statistics(st.session_state["df"])
                insights = st.session_state.get("last_insights", "")
                st.session_state["pdf_buffer"] = generate_pdf_report(ov, ql, sts, insights)
                st.success("PDF report is ready to download.")
            except Exception as exc:
                st.error(f"PDF generation failed: {exc}")

    if st.session_state["pdf_buffer"] is not None:
        st.download_button(
            label="Save PDF",
            data=st.session_state["pdf_buffer"],
            file_name="insightflow_report.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

with st.expander("Preview dataset"):
    st.dataframe(df.head(), use_container_width=True)

if selected_tab == "Overview":
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Dataset Overview</div>', unsafe_allow_html=True)
    st.dataframe(
        pd.DataFrame(
            {
                "Column": list(overview["dtypes"].keys()),
                "Data Type": list(overview["dtypes"].values()),
            }
        ),
        use_container_width=True,
    )
    with st.expander("Dataset preview"):
        st.dataframe(df.head(10), use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

elif selected_tab == "Data Quality":
    total_cells = df.shape[0] * df.shape[1]
    missing_cells = missing_count
    duplicate_rows = quality["duplicate_rows"]
    duplicate_pct = quality["summary"]["duplicate_percentage"]
    quality_pct = ((total_cells - missing_cells) / total_cells) * 100 if total_cells else 100
    score = round(quality_pct, 1)
    label = _quality_label(score)
    ring_style = _quality_ring_style(score)
    has_missing = missing_cells > 0
    has_duplicates = duplicate_rows > 0

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Data Quality Assessment</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="quality-wrap">
            <div class="score-ring" style="{ring_style}">
                <div class="score-inner">
                    <div>
                        <div class="score-number">{score}%</div>
                        <div class="score-label">{label}</div>
                    </div>
                </div>
            </div>
            <div class="quality-summary-panel">
                <div class="ai-card">
                    <div class="ai-tag">Quality Summary</div>
                    <div class="quality-metric-row">
                        <span>Total cells</span>
                        <b>{total_cells:,}</b>
                    </div>
                    <div class="quality-metric-row">
                        <span>Missing cells</span>
                        <b>{missing_cells:,} ({quality["summary"]["missing_percentage"]}%)</b>
                    </div>
                    <div class="quality-metric-row">
                        <span>Duplicate rows</span>
                        <b>{duplicate_rows:,} ({duplicate_pct}%)</b>
                    </div>
                    <div class="quality-metric-row">
                        <span>Completeness score</span>
                        <b>{score}%</b>
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not has_missing and not has_duplicates:
        st.markdown(
            '<div class="quality-alert success">'
            "Dataset looks clean: no missing values or duplicate rows detected."
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        if has_missing:
            st.markdown(
                f'<div class="quality-alert warning">'
                f"<b>Missing values detected:</b> {missing_cells:,} cell(s) are empty across "
                f"{len(quality['missing_values']) if quality['missing_values'] != 'None' else 0} column(s). "
                f"Review the table below and consider imputation or removal."
                f"</div>",
                unsafe_allow_html=True,
            )
        if has_duplicates:
            alert_class = "danger" if duplicate_pct >= 10 else "warning"
            st.markdown(
                f'<div class="quality-alert {alert_class}">'
                f"<b>Duplicate rows detected:</b> {duplicate_rows:,} duplicate row(s) "
                f"({duplicate_pct}% of the dataset). Consider deduplication before analysis."
                f"</div>",
                unsafe_allow_html=True,
            )

    if quality["missing_values"] == "None":
        st.success("No missing values found in any column.")
    else:
        st.markdown("#### Missing Values by Column")
        missing_df = pd.DataFrame(
            list(quality["missing_values"].items()),
            columns=["Column", "Missing Count"],
        )
        missing_df["Missing %"] = round((missing_df["Missing Count"] / df.shape[0]) * 100, 2)
        st.dataframe(missing_df, use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)

elif selected_tab == "Statistics":
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Statistical Summarisation</div>', unsafe_allow_html=True)
    st.dataframe(stats["describe"], use_container_width=True)

    if stats["num_cols"]:
        with st.expander("Numerical columns"):
            st.text(stats["text_summary"])

    if stats["cat_cols"]:
        cat_info = pd.DataFrame(
            {
                "Column": stats["cat_cols"],
                "Unique Values": [df[col].fillna("Missing").astype(str).nunique() for col in stats["cat_cols"]],
                "Most Frequent": [
                    df[col].fillna("Missing").astype(str).value_counts().index[0]
                    if len(df[col]) > 0
                    else None
                    for col in stats["cat_cols"]
                ],
            }
        )
        with st.expander("Categorical columns"):
            st.dataframe(cat_info, use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)

elif selected_tab == "Visualizations":
    num_cols = stats["num_cols"]
    cat_cols = stats["cat_cols"]

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Auto-Generated Visualisations</div>', unsafe_allow_html=True)

    if num_cols:
        st.markdown("#### Histograms")
        with st.spinner("Generating histograms..."):
            histograms, hist_warnings = plot_histograms(df, num_cols)
        _show_chart_warnings(hist_warnings)
        if histograms:
            for col_name, img_bytes in histograms:
                st.markdown(f"**Histogram: {col_name}**")
                _render_chart_image(img_bytes, caption=f"Distribution of {col_name}")
        elif not hist_warnings:
            st.info("No histograms could be generated for the available numeric columns.")
    else:
        st.info("No numerical columns found - skipping histograms.")

    st.markdown("---")

    if cat_cols:
        st.markdown("#### Bar Charts")
        with st.spinner("Generating bar charts..."):
            bar_charts, bar_warnings = plot_bar_charts(df, cat_cols)
        _show_chart_warnings(bar_warnings)
        if bar_charts:
            for col_name, img_bytes in bar_charts:
                st.markdown(f"**Bar chart: {col_name}**")
                _render_chart_image(img_bytes, caption=f"Top values in {col_name}")
        elif not bar_warnings:
            st.info("No bar charts could be generated for the available categorical columns.")
    else:
        st.info("No categorical columns found - skipping bar charts.")

    st.markdown("---")

    if len(num_cols) >= 2:
        st.markdown("#### Correlation Heatmap")
        with st.spinner("Generating correlation heatmap..."):
            heatmap_bytes, heatmap_warnings = plot_correlation_heatmap(df, num_cols)
        _show_chart_warnings(heatmap_warnings)
        if heatmap_bytes:
            _render_chart_image(heatmap_bytes, caption="Correlation between numerical columns")
        else:
            st.info("Correlation heatmap could not be generated for this dataset.")
    else:
        st.info("Need at least 2 numerical columns for a correlation heatmap.")

    st.markdown("</div>", unsafe_allow_html=True)

elif selected_tab == "AI Insights":
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">AI-Generated Insights</div>', unsafe_allow_html=True)

    if not ollama_ok:
        st.warning(
            "Ollama is not running. Start it with `ollama serve`, ensure `qwen2.5:3b` "
            "is available, then refresh the page."
        )
    else:
        if st.button("Generate Insights", type="primary"):
            context = _build_context(df)
            user_prompt = INSIGHT_PROMPT_TEMPLATE.format(**context)
            with st.spinner("Generating insights with qwen2.5:3b..."):
                response = generate_response(SYSTEM_PROMPT, user_prompt)
            st.session_state["last_insights"] = response

            if response.startswith("**Ollama is not running.**") or response.startswith("Error communicating"):
                st.warning(response)
            else:
                parts = [part.strip() for part in response.split("\n\n") if part.strip()]
                if not parts:
                    parts = [response]

                tags = ["Trends", "Risks", "Recommendations", "Insights"]
                for index, part in enumerate(parts[:4]):
                    st.markdown(
                        f"""
                        <div class="ai-card" style="margin-bottom:0.9rem;">
                            <div class="ai-tag">{tags[index % len(tags)]}</div>
                            <div>{html.escape(part)}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                st.download_button(
                    label="Download Insights",
                    data=response,
                    file_name="insightflow_insights.md",
                    mime="text/markdown",
                )

    st.markdown("</div>", unsafe_allow_html=True)

elif selected_tab == "Ask Questions":
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Ask Questions About Your Data</div>', unsafe_allow_html=True)

    if not ollama_ok:
        st.warning(
            "Ollama is not running. Start it with `ollama serve`, ensure `qwen2.5:3b` "
            "is available, then refresh the page."
        )
    else:
        st.markdown('<div class="chat-wrap"><div class="chat-scroll">', unsafe_allow_html=True)

        for entry in st.session_state["chat_history"]:
            question = html.escape(entry.get("question", ""))
            answer = html.escape(entry.get("answer", ""))
            timestamp = html.escape(entry.get("timestamp", ""))
            st.markdown(
                f"""
                <div class="chat-row user">
                    <div>
                        <div class="chat-bubble">{question}</div>
                        <div class="chat-meta">{timestamp}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown(
                f"""
                <div class="chat-row ai">
                    <div>
                        <div class="chat-bubble">{answer}</div>
                        <div class="chat-meta">{timestamp}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("</div></div>", unsafe_allow_html=True)

        user_question = st.text_input(
            "Ask a question",
            placeholder="e.g. Which columns have the most missing values?",
            label_visibility="collapsed",
        )

        col_send, col_clear = st.columns([1, 1])
        with col_send:
            send = st.button("Send", type="primary", use_container_width=True)
        with col_clear:
            clear = st.button("Clear conversation", use_container_width=True)

        if clear:
            st.session_state["chat_history"] = []
            st.rerun()

        if send and user_question.strip():
            context = _build_context(df)
            rag_available = st.session_state.get("rag_available", False)

            if rag_available:
                relevant = retrieve_relevant_rows(
                    user_question,
                    st.session_state["rag_vectors"],
                    st.session_state["rag_docs"],
                    st.session_state["rag_vectorizer"],
                    k=5,
                    fallback_context=st.session_state.get("rag_fallback", ""),
                )
                user_prompt = RAG_QA_PROMPT_TEMPLATE.format(
                    **context, relevant_rows=relevant, question=user_question
                )
            else:
                sample_text = st.session_state.get(
                    "rag_fallback", df.head(5).to_string(index=False)
                )
                user_prompt = QA_PROMPT_TEMPLATE.format(
                    **context, sample=sample_text, question=user_question
                )

            with st.spinner("Thinking with qwen2.5:3b..."):
                response = generate_response(SYSTEM_PROMPT, user_prompt)

            now = datetime.now().strftime("%H:%M")
            st.session_state["chat_history"].append(
                {"question": user_question, "answer": response, "timestamp": now}
            )
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
