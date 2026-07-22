"""
pdf_report.py – PDF Report Generation using ReportLab

Generates a downloadable PDF report containing:
  - Dataset Overview
  - Data Quality Summary
  - Statistical Summary
  - AI Insights (if available)
"""

from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak,
)
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER


def generate_pdf_report(
    overview: dict,
    quality: dict,
    stats: dict,
    insights: str = "",
) -> BytesIO:
    """
    Build a PDF report and return it as a BytesIO stream.
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        title="InsightFlow – Data Report",
        author="InsightFlow",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle", parent=styles["Title"], spaceAfter=0.5 * inch
    )
    heading_style = ParagraphStyle(
        "CustomHeading", parent=styles["Heading2"], spaceBefore=0.3 * inch,
        spaceAfter=0.15 * inch,
    )
    body_style = styles["Normal"]

    elements = []

    elements.append(Paragraph("InsightFlow – Data Report", title_style))
    elements.append(Spacer(1, 0.2 * inch))

    elements.append(Paragraph("1. Dataset Overview", heading_style))
    overview_data = [
        ["Rows", str(overview["rows"])],
        ["Columns", str(overview["columns"])],
    ]
    for col, dtype in overview["dtypes"].items():
        overview_data.append([f"Column: {col}", dtype])
    t = Table(overview_data, colWidths=[2.5 * inch, 3.5 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E8E8E8")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.2 * inch))

    elements.append(Paragraph("2. Data Quality Summary", heading_style))
    quality_data = [
        ["Duplicate Rows", str(quality["duplicate_rows"])],
        [
            "Duplicate %",
            f"{quality['summary']['duplicate_percentage']}%",
        ],
        [
            "Missing Cells",
            f"{quality['summary']['missing_cells']} "
            f"({quality['summary']['missing_percentage']}%)",
        ],
    ]
    t2 = Table(quality_data, colWidths=[2.5 * inch, 3.5 * inch])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E8E8E8")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    elements.append(t2)
    elements.append(Spacer(1, 0.2 * inch))

    elements.append(Paragraph("3. Statistical Summary", heading_style))
    for line in stats["text_summary"].split("\n"):
        if line.strip():
            elements.append(Paragraph(line, body_style))
    elements.append(Spacer(1, 0.2 * inch))

    elements.append(Paragraph("4. AI Insights", heading_style))
    if insights:
        for line in insights.split("\n"):
            if line.strip():
                elements.append(Paragraph(line, body_style))
    else:
        elements.append(
            Paragraph(
                "No AI insights were generated. "
                "Use the 'Generate Insights' button in the dashboard.",
                body_style,
            )
        )

    doc.build(elements)
    buf.seek(0)
    return buf