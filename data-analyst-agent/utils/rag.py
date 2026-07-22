"""
rag.py – Simple RAG (Retrieval-Augmented Generation) using TF-IDF

Converts each CSV row into a text document, builds TF-IDF vectors with
scikit-learn's TfidfVectorizer, and stores vectors in memory. For each user
question, the top-5 most relevant rows are retrieved via cosine similarity
and sent to the LLM as context.

No sentence-transformers, no transformers, no PyTorch – just scikit-learn.
"""

import logging

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


def _rows_to_documents(df: pd.DataFrame) -> list[str]:
    """Turn each CSV row into a plain-English text description."""
    docs = []
    for _, row in df.iterrows():
        parts = []
        for col in df.columns:
            val = row[col]
            if pd.isna(val):
                continue
            parts.append(f"{col} is {val}")
        docs.append(" | ".join(parts) if parts else "empty row")
    return docs


def build_fallback_context(df: pd.DataFrame, stats_text: str = "", max_rows: int = 5) -> str:
    """Fallback context when TF-IDF indexing is unavailable."""
    lines = [
        "DATASET SUMMARY (RAG fallback)",
        f"Rows: {df.shape[0]}",
        f"Columns: {', '.join(str(c) for c in df.columns)}",
    ]
    if stats_text:
        lines.append("")
        lines.append(stats_text)

    sample = df.head(max_rows)
    if not sample.empty:
        lines.append("")
        lines.append(f"SAMPLE ROWS (first {len(sample)})")
        lines.append(sample.to_string(index=False))

    return "\n".join(lines)


def build_embeddings(df: pd.DataFrame) -> dict:
    """
    Build TF-IDF vectors for every row in the DataFrame.

    Returns a dict:
      - available: bool
      - vectors, docs, vectorizer: set when available is True
      - fallback_context: summary text used when TF-IDF is unavailable
    """
    docs = _rows_to_documents(df)
    fallback_context = build_fallback_context(df)

    if not docs or all(not doc.strip() or doc == "empty row" for doc in docs):
        return {
            "available": False,
            "vectors": None,
            "docs": None,
            "vectorizer": None,
            "fallback_context": fallback_context,
        }

    try:
        vectorizer = TfidfVectorizer(stop_words="english", min_df=1)
        vectors = vectorizer.fit_transform(docs)
        if vectors.shape[1] == 0:
            raise ValueError("TF-IDF produced an empty vocabulary.")

        return {
            "available": True,
            "vectors": vectors,
            "docs": docs,
            "vectorizer": vectorizer,
            "fallback_context": fallback_context,
        }
    except Exception as exc:
        logger.warning("TF-IDF indexing unavailable: %s", exc)
        return {
            "available": False,
            "vectors": None,
            "docs": None,
            "vectorizer": None,
            "fallback_context": fallback_context,
        }


def retrieve_relevant_rows(
    question: str,
    vectors,
    docs: list[str],
    vectorizer,
    k: int = 5,
    fallback_context: str = "",
) -> str:
    """
    Return the top-k most relevant rows for a question.
    Falls back to dataset summary text when TF-IDF is unavailable.
    """
    if vectors is None or vectorizer is None or not docs:
        return fallback_context or "No row-level context available."

    try:
        q_vec = vectorizer.transform([question])
        sims = cosine_similarity(q_vec, vectors)[0]
        top_k_indices = np.argsort(sims)[::-1][:k]

        lines = []
        for idx in top_k_indices:
            if idx < len(docs):
                lines.append(
                    f"  Row #{idx} (similarity={sims[idx]:.3f}): {docs[idx]}"
                )

        if lines:
            return "\n".join(lines)
        return fallback_context or "No relevant rows found."
    except Exception as exc:
        logger.warning("Row retrieval failed, using fallback context: %s", exc)
        return fallback_context or "No row-level context available."
