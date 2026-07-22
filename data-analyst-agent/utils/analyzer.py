"""
analyzer.py

Handles all data-analysis logic:
- Loading & validating CSV files
- Computing dataset overview (rows, columns, dtypes)
- Data quality assessment (missing values, duplicates)
- Statistical summarisation (describe + numeric stats)
- Separating numerical / categorical columns
"""

import csv
import pandas as pd
import numpy as np
from io import StringIO, BytesIO


def _read_raw_bytes(uploaded_file) -> bytes:
    """Read bytes from a Streamlit UploadedFile or path-like object."""
    if hasattr(uploaded_file, "read"):
        uploaded_file.seek(0)
        raw = uploaded_file.read()
        if isinstance(raw, str):
            return raw.encode("utf-8")
        return raw
    if isinstance(uploaded_file, (bytes, bytearray)):
        return bytes(uploaded_file)
    if isinstance(uploaded_file, str):
        with open(uploaded_file, "rb") as handle:
            return handle.read()
    raise ValueError("Unsupported file input type.")


def _decode_csv_text(raw: bytes) -> str:
    """Try common encodings used by CSV exports."""
    if not raw or not raw.strip():
        raise ValueError("The CSV file is empty.")

    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise ValueError(
        "Could not decode the CSV file. Supported encodings: UTF-8, UTF-8 BOM, Latin-1."
    )


def _detect_delimiter(text: str) -> str:
    """Sniff comma, semicolon, or tab delimiters."""
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        return dialect.delimiter
    except csv.Error:
        first_line = sample.splitlines()[0] if sample.splitlines() else ""
        if first_line.count("\t") > first_line.count(",") and first_line.count("\t") > 0:
            return "\t"
        if first_line.count(";") > first_line.count(",") and first_line.count(";") > 0:
            return ";"
        return ","


def load_csv(uploaded_file) -> pd.DataFrame:
    """
    Read an uploaded CSV file into a pandas DataFrame.
    Supports UTF-8, UTF-8 BOM, Latin-1, and comma/semicolon/tab delimiters.
    Raises ValueError with a clear message when parsing fails.
    """
    try:
        raw = _read_raw_bytes(uploaded_file)
        text = _decode_csv_text(raw)
        delimiter = _detect_delimiter(text)

        df = pd.read_csv(StringIO(text), sep=delimiter)

        if df.shape[1] == 0:
            raise ValueError("The CSV file has no columns.")

        if df.shape[0] == 0:
            raise ValueError(
                "The CSV file contains headers but no data rows. "
                "Please upload a file with at least one data row."
            )

        return df
    except ValueError:
        raise
    except pd.errors.EmptyDataError:
        raise ValueError("The CSV file is empty or corrupted.")
    except pd.errors.ParserError as exc:
        raise ValueError(f"Could not parse CSV file: {exc}")
    except Exception as exc:
        raise ValueError(f"Invalid CSV file: {exc}")


def get_overview(df: pd.DataFrame) -> dict:
    """Return basic metadata about the dataset."""
    return {
        "rows": df.shape[0],
        "columns": df.shape[1],
        "column_names": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
    }


def get_data_quality(df: pd.DataFrame) -> dict:
    """Assess data quality: missing values, duplicates, and a quality summary."""
    missing = df.isnull().sum()
    missing = missing[missing > 0]

    duplicates = df.duplicated().sum()
    total_cells = df.size
    missing_cells = int(df.isnull().sum().sum())
    missing_pct = round((missing_cells / total_cells) * 100, 2) if total_cells else 0

    return {
        "missing_values": missing.to_dict() if not missing.empty else "None",
        "duplicate_rows": int(duplicates),
        "summary": {
            "total_cells": int(total_cells),
            "missing_cells": missing_cells,
            "missing_percentage": missing_pct,
            "duplicate_percentage": round(
                (duplicates / df.shape[0]) * 100, 2
            )
            if df.shape[0]
            else 0,
        },
    }


def get_statistics(df: pd.DataFrame) -> dict:
    """Return pandas describe() output and a simplified summary for the LLM."""
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    cat_cols = df.select_dtypes(exclude=[np.number]).columns.tolist()

    describe_df = df.describe(include="all").round(2)

    summary_lines = []
    if num_cols:
        summary_lines.append("Numerical columns:")
        for col in num_cols:
            series = pd.to_numeric(df[col], errors="coerce").dropna()
            if series.empty:
                summary_lines.append(f"  - {col}: no valid numeric values")
                continue
            s = series.describe()
            std_str = f"{s['std']:.2f}" if pd.notna(s["std"]) else "N/A"
            summary_lines.append(
                f"  - {col}: mean={s['mean']:.2f}, std={std_str}, "
                f"min={s['min']:.2f}, 25%={s['25%']:.2f}, 50%={s['50%']:.2f}, "
                f"75%={s['75%']:.2f}, max={s['max']:.2f}"
            )

    if cat_cols:
        summary_lines.append("\nCategorical columns (top value & count):")
        for col in cat_cols:
            cleaned = df[col].fillna("Missing").astype(str)
            top = cleaned.value_counts().head(1)
            if not top.empty:
                summary_lines.append(
                    f"  - {col}: most common = '{top.index[0]}' "
                    f"(appears {top.values[0]} times)"
                )

    return {
        "describe": describe_df,
        "text_summary": "\n".join(summary_lines) if summary_lines else "No summary available.",
        "num_cols": num_cols,
        "cat_cols": cat_cols,
    }


def get_numeric_categorical(df: pd.DataFrame) -> tuple:
    """Convenience helper – returns (num_cols, cat_cols)."""
    num = df.select_dtypes(include=[np.number]).columns.tolist()
    cat = df.select_dtypes(exclude=[np.number]).columns.tolist()
    return num, cat
