"""
charts.py

Generates all visualisations using Matplotlib & Seaborn:
- Histograms for numerical columns
- Bar charts for categorical columns
- Correlation heatmap when 2+ numerical columns exist
"""

import logging
import warnings

import matplotlib

matplotlib.use("Agg")  # non-interactive backend – safe for Streamlit

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from io import BytesIO

logger = logging.getLogger(__name__)


def _fig_to_bytes(fig) -> BytesIO:
    """Convert a Matplotlib figure to a BytesIO object for Streamlit."""
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf


def _truncate_label(value, max_len: int = 40) -> str:
    text = str(value)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def plot_histograms(df: pd.DataFrame, num_cols: list) -> tuple[list, list[str]]:
    """
    Generate one histogram per numerical column.
    Returns (successful_charts, warnings).
    """
    results = []
    chart_warnings = []

    for col in num_cols:
        try:
            series = pd.to_numeric(df[col], errors="coerce").replace(
                [np.inf, -np.inf], np.nan
            ).dropna()

            if series.empty:
                chart_warnings.append(
                    f"Skipped histogram for '{col}': no valid numeric values."
                )
                continue

            values = series.astype(np.float64).values
            bin_count = min(20, max(1, len(np.unique(values))))

            fig, ax = plt.subplots(figsize=(6, 3.5))
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                ax.hist(values, bins=bin_count, color="#4C72B0", edgecolor="white")
            ax.set_title(f"Distribution of {col}", fontsize=13, fontweight="bold")
            ax.set_xlabel(col)
            ax.set_ylabel("Frequency")
            ax.grid(axis="y", alpha=0.3)
            fig.tight_layout()
            results.append((col, _fig_to_bytes(fig)))
        except Exception as exc:
            logger.exception("Histogram failed for column '%s'", col)
            chart_warnings.append(
                f"Could not render histogram for '{col}': {exc}"
            )

    return results, chart_warnings


def plot_bar_charts(
    df: pd.DataFrame, cat_cols: list, top_n: int = 10
) -> tuple[list, list[str]]:
    """
    Generate one bar chart per categorical column (showing top_n values).
    Returns (successful_charts, warnings).
    """
    results = []
    chart_warnings = []

    for col in cat_cols:
        try:
            series = df[col].fillna("Missing").astype(str).str.strip()
            series = series.replace("", "Missing")

            counts = series.value_counts().head(top_n)
            if counts.empty:
                chart_warnings.append(
                    f"Skipped bar chart for '{col}': no values to plot."
                )
                continue

            labels = [_truncate_label(label) for label in counts.index]

            fig, ax = plt.subplots(figsize=(max(6, len(counts) * 0.6), 3.8))
            ax.bar(
                range(len(counts)),
                counts.values,
                color="#DD8452",
                edgecolor="white",
            )
            ax.set_xticks(range(len(counts)))
            ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
            ax.set_title(f"Top values in {col}", fontsize=13, fontweight="bold")
            ax.set_xlabel(col)
            ax.set_ylabel("Count")
            ax.grid(axis="y", alpha=0.3)
            fig.tight_layout()
            results.append((col, _fig_to_bytes(fig)))
        except Exception as exc:
            logger.exception("Bar chart failed for column '%s'", col)
            chart_warnings.append(
                f"Could not render bar chart for '{col}': {exc}"
            )

    return results, chart_warnings


def plot_correlation_heatmap(
    df: pd.DataFrame, num_cols: list
) -> tuple[BytesIO | None, list[str]]:
    """
    Generate a correlation heatmap for numerical columns.
    Returns (heatmap_bytes_or_none, warnings).
    """
    chart_warnings = []

    if len(num_cols) < 2:
        return None, chart_warnings

    try:
        numeric_df = df[num_cols].apply(pd.to_numeric, errors="coerce")
        numeric_df = numeric_df.replace([np.inf, -np.inf], np.nan)

        if numeric_df.dropna(how="all").shape[1] < 2:
            chart_warnings.append(
                "Skipped correlation heatmap: fewer than 2 usable numeric columns."
            )
            return None, chart_warnings

        corr = numeric_df.corr(numeric_only=True).fillna(0)

        fig, ax = plt.subplots(
            figsize=(
                max(6, len(num_cols) * 0.8),
                max(5, len(num_cols) * 0.7),
            )
        )
        sns.heatmap(
            corr,
            annot=True,
            fmt=".2f",
            cmap="coolwarm",
            center=0,
            square=True,
            linewidths=0.5,
            ax=ax,
        )
        ax.set_title("Correlation Heatmap", fontsize=14, fontweight="bold")
        fig.tight_layout()
        return _fig_to_bytes(fig), chart_warnings
    except Exception as exc:
        logger.exception("Correlation heatmap failed")
        chart_warnings.append(f"Could not render correlation heatmap: {exc}")
        return None, chart_warnings
