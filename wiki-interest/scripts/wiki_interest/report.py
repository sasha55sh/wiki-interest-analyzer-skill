"""Generate PDF report from analysis results."""

from datetime import date
from pathlib import Path

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        Image,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
except ImportError:
    raise ImportError("reportlab required: pip install reportlab")


def generate_report(
    run_id: str,
    analysis: dict,
    chart_file: str,
    user_summary: str = "",
    output_file: str | None = None,
) -> bytes:
    """Generate a one-page PDF report.

    Args:
        run_id: Run identifier
        analysis: Dict of {lang: analysis_result} from analyze()
        chart_file: Path to PNG chart
        user_summary: User's conclusion (≤120 words)
        output_file: PDF file path, or None to return bytes
    """
    from io import BytesIO

    if output_file:
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        doc = SimpleDocTemplate(str(output_file), pagesize=A4, topMargin=0.5 * inch)
    else:
        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=0.5 * inch)

    story = []
    styles = getSampleStyleSheet()

    # Title
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=14,
        textColor=colors.HexColor("#1f77b4"),
        spaceAfter=6,
    )
    story.append(Paragraph("Wikipedia Pageview Trend Analysis", title_style))

    meta_text = f"<b>Run ID:</b> {run_id} | <b>Date:</b> {date.today().isoformat()}"
    story.append(Paragraph(meta_text, styles["Normal"]))
    story.append(Spacer(1, 0.15 * inch))

    if user_summary:
        conclusion_style = ParagraphStyle(
            "Conclusion", parent=styles["BodyText"], fontSize=10, leading=12, spaceAfter=8
        )
        story.append(Paragraph("<b>Summary:</b>", styles["Heading3"]))
        text = user_summary[:400]
        story.append(Paragraph(text, conclusion_style))
        story.append(Spacer(1, 0.1 * inch))

    if Path(chart_file).exists():
        story.append(Paragraph("<b>Trend Chart:</b>", styles["Heading3"]))
        try:
            img = Image(chart_file, width=5.5 * inch, height=2.5 * inch)
            story.append(img)
            story.append(Spacer(1, 0.1 * inch))
        except Exception:
            story.append(Paragraph("[Chart unavailable]", styles["Normal"]))

    story.append(Paragraph("<b>Metrics:</b>", styles["Heading3"]))
    table_data = [["Language", "Confidence", "YoY Change %", "Caveats"]]
    for lang, data in sorted(analysis.items()):
        caveats = ", ".join(data.get("caveats", [])[:2])
        table_data.append(
            [
                lang.upper(),
                data.get("confidence", "?"),
                f"{data.get('yoy_change_pct', 0):+.1f}%",
                caveats or "—",
            ]
        )

    table = Table(table_data, colWidths=[1 * inch, 1.2 * inch, 1.2 * inch, 1.6 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 0.1 * inch))

    footer_style = ParagraphStyle(
        "Footer", parent=styles["Normal"], fontSize=7, textColor=colors.grey
    )
    footer = f"<i>Wikimedia Pageviews API | {date.today().isoformat()}</i>"
    story.append(Paragraph(footer, footer_style))

    doc.build(story)

    if output_file is None:
        buf.seek(0)
        return buf.read()
    return None
