"""Short PDF report for the user, one per session.

Layout: title (the user's main question) → results table → critical issues (only if any)
→ conclusion → recommendations → chart → seasonality (≥ 24 months: month × year table and
peaks per season) → follow-ups (question, short answer; for a follow-up that fetched new data
also its results table, data problems and chart). A short report fits one A4 page; long text
flows onto further pages.
Numbers come from analysis-N.json; conclusion, recommendations and answers are written by the agent.
"""

import statistics
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .i18n import lang_name, month_name, period_label, t

FONT = "DejaVuSans"
FONT_BOLD = "DejaVuSans-Bold"

ACCENT = colors.HexColor("#1f4e79")
HEADER_BG = colors.HexColor("#dce6f0")
GOOD = colors.HexColor("#2e7d32")
BAD = colors.HexColor("#c62828")
WARN_BG = colors.HexColor("#fff4e5")
MUTED = colors.HexColor("#666666")

PAGE_W, PAGE_H = A4
MARGIN = 1.6 * cm


def _register_fonts() -> None:
    """Unicode font for Cyrillic etc. DejaVu Sans ships with matplotlib, so no font files in the skill."""
    if FONT in pdfmetrics.getRegisteredFontNames():
        return
    fonts_dir = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    pdfmetrics.registerFont(TTFont(FONT, str(fonts_dir / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, str(fonts_dir / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFontFamily(FONT, normal=FONT, bold=FONT_BOLD, italic=FONT, boldItalic=FONT_BOLD)


def _pct(value: float | None, lang: str) -> str:
    return f"{value:+.0f}%" if value is not None else t("na", lang)


def _int(value: float) -> str:
    return f"{round(value):,}".replace(",", " ")


def _direction(data: dict) -> str:
    """growing / declining / flat: significant Mann-Kendall AND 95% CI excluding zero."""
    ci, p = data.get("ci95"), data.get("mann_kendall_p")
    if ci and p is not None and p < 0.05:
        if ci[0] > 0:
            return "growing"
        if ci[1] < 0:
            return "declining"
    return "flat"


def _median(data: dict) -> float:
    values = list((data.get("monthly") or {}).values())
    return statistics.median(values) if values else 0


def auto_problems(analysis: dict, missing: list[str], lang: str, no_views: list[str] | None = None) -> list[str]:
    """Data problems the user must know about, derived from the analysis.

    missing: languages without an article; no_views: languages with an article but no
    views (or no complete month since its creation) in the period.
    """
    out = [t("missing_lang", lang, name=lang_name(code, lang)) for code in missing]
    out += [t("no_views_lang", lang, name=lang_name(code, lang)) for code in no_views or []]
    for code, d in analysis.items():
        name = _cap(lang_name(code, lang))
        for caveat in d.get("caveats") or []:
            if caveat in ("low_volume", "short_history"):
                out.append(t(caveat, lang, name=name, median=_int(_median(d))))
    return out


def _cap(s: str) -> str:
    """Upper-case the first letter only ("JavaScript" stays "JavaScript")."""
    return s[:1].upper() + s[1:]


def _results_table(analysis: dict, lang: str) -> Table:
    rows = [[t(k, lang) for k in ("col_lang", "col_direction", "col_yoy", "col_site", "col_views", "col_conf")]]
    style = []
    for i, (code, d) in enumerate(analysis.items(), start=1):
        direction = _direction(d)
        style.append(("TEXTCOLOR", (1, i), (1, i),
                      {"growing": GOOD, "declining": BAD}.get(direction, MUTED)))
        rows.append([
            _cap(lang_name(code, lang)),
            t(direction, lang),
            _pct(d.get("yoy_change_pct"), lang),
            _pct((d.get("baseline") or {}).get("yoy_change_pct"), lang),
            _int(_median(d)),
            t(f"conf_{d.get('confidence', 'low')}", lang),
        ])
    table = Table(rows, colWidths=[3.2 * cm, 3.4 * cm, 2.4 * cm, 3.2 * cm, 2.6 * cm, 3 * cm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTNAME", (1, 1), (1, -1), FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, ACCENT),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (2, 0), (4, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        *style,
    ]))
    return table


def _issues_box(issues: list[str], body: ParagraphStyle) -> Table:
    box = Table([[Paragraph("• " + escape(i), body)] for i in issues], colWidths=[PAGE_W - 2 * MARGIN])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), WARN_BG),
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, colors.HexColor("#e65100")),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return box


def _grid_style(font_size: float) -> list:
    return [
        ("FONTNAME", (0, 0), (-1, -1), FONT),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, ACCENT),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]


def _seasonality_block(code: str, seas: dict, lang: str, body: ParagraphStyle) -> list:
    """Month × year table, one row per season (peak / low vs its mean), and a one-line summary."""
    peaks = {s["peak_month"] for s in seas["seasons"]}
    lows = {s["low_month"] for s in seas["seasons"]}
    years = sorted({y for per_year in seas["by_month"].values() for y in per_year})

    grid = [[t("col_year", lang)] + [month_name(f"{m:02d}", lang) for m in range(1, 13)]]
    style = _grid_style(7.5) + [("ALIGN", (1, 0), (-1, -1), "RIGHT")]
    for r, year in enumerate(years, start=1):
        row = [year]
        for c, month in enumerate((f"{m:02d}" for m in range(1, 13)), start=1):
            value = seas["by_month"].get(month, {}).get(year)
            row.append(_int(value) if value is not None else "—")
            key = f"{year}-{month}"
            if key in peaks or key in lows:
                style += [("TEXTCOLOR", (c, r), (c, r), GOOD if key in peaks else BAD),
                          ("FONTNAME", (c, r), (c, r), FONT_BOLD)]
        grid.append(row)
    width = PAGE_W - 2 * MARGIN
    month_table = Table(grid, colWidths=[1.4 * cm] + [(width - 1.4 * cm) / 12] * 12)
    month_table.setStyle(TableStyle(style))

    def point(month: str, views: int, pct: float | None) -> str:
        return f"{month_name(month[5:], lang)} {month[:4]}: {_int(views)} ({_pct(pct, lang)})"

    rows = [[t(k, lang) for k in ("col_season", "col_season_mean", "col_peak", "col_low")]]
    for s in seas["seasons"]:
        rows.append([
            period_label(s["start"], s["end"], lang),
            _int(s["mean"]),
            point(s["peak_month"], s["peak_views"], s["peak_vs_mean_pct"]),
            point(s["low_month"], s["low_views"], s["low_vs_mean_pct"]),
        ])
    season_table = Table(rows, colWidths=[4.2 * cm, 2.6 * cm, 5.5 * cm, 5.5 * cm])
    season_table.setStyle(TableStyle(_grid_style(8.5) + [
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TEXTCOLOR", (2, 1), (2, -1), GOOD),
        ("TEXTCOLOR", (3, 1), (3, -1), BAD),
    ]))

    def months(key: str) -> str:
        distinct = dict.fromkeys(s[key][5:] for s in seas["seasons"])  # keeps first-seen order
        return ", ".join(month_name(m, lang, full=True) for m in distinct)

    lines = [
        t("peak_repeats", lang, month=month_name(seas["peak_calendar_month"], lang, full=True))
        if seas["peak_repeats"] else t("peak_varies", lang, months=months("peak_month")),
        t("low_repeats", lang, month=month_name(seas["low_calendar_month"], lang, full=True))
        if seas["low_repeats"] else t("low_varies", lang, months=months("low_month")),
    ]
    lines += [t("peak_is_trend", lang, season=period_label(s["start"], s["end"], lang))
              for s in seas["seasons"] if s["peak_above_neighbours"] is False]

    return [
        Paragraph(f"<b>{escape(_cap(lang_name(code, lang)))}</b>. " + escape(" ".join(lines)), body),
        Spacer(1, 0.1 * cm),
        month_table,
        Spacer(1, 0.15 * cm),
        season_table,
        Spacer(1, 0.2 * cm),
    ]


def generate_report(
    topic: str,
    analysis: dict,
    chart_file: str,
    conclusion: str = "",
    output_file: str | None = None,
    meta: dict | None = None,
    recommendations: list[str] | None = None,
    problems: list[str] | None = None,
    lang: str = "en",
    followups: list[dict] | None = None,
) -> bytes | None:
    """Build the PDF.

    Args:
        topic: the user's main question / topic, used in the title
        analysis: {lang: analysis_result} of the main step
        chart_file: PNG from plot_trends (in the same `lang`)
        conclusion: agent's answer to the main question, in the user's language
        output_file: PDF path, or None to return bytes
        meta: the main step from session.json (period, langs_missing)
        recommendations: agent's recommendations, one per item
        problems: extra critical issues from the agent (added to the automatic ones)
        lang: language of the labels ("uk", "en")
        followups: [{"question", "answer", "chart_file" or None}] in conversation order
    """
    _register_fonts()
    meta = meta or {}

    body = ParagraphStyle("body", fontName=FONT, fontSize=9.5, leading=13)
    h2 = ParagraphStyle("h2", fontName=FONT_BOLD, fontSize=11.5, leading=14, textColor=ACCENT,
                        spaceBefore=9, spaceAfter=4)
    title = ParagraphStyle("title", fontName=FONT_BOLD, fontSize=16, leading=20, textColor=ACCENT)
    small = ParagraphStyle("small", fontName=FONT, fontSize=8, leading=10, textColor=MUTED)

    period = meta.get("period")
    story = [
        Paragraph(escape(t("title", lang, topic=topic or "—")), title),
        Paragraph(escape(t(
            "subtitle", lang,
            period=period_label(*period, lang) if period else t("na", lang),
            date=datetime.now(UTC).date().isoformat(),
        )), small),
        Spacer(1, 0.2 * cm),
    ]

    if analysis:
        story += [Paragraph(t("results", lang), h2), _results_table(analysis, lang)]

    issues = auto_problems(
        analysis, meta.get("langs_missing") or [], lang, meta.get("langs_no_views") or []
    ) + list(problems or [])
    if issues:
        story += [Paragraph(t("problems", lang), h2), _issues_box(issues, body)]

    if conclusion:
        story += [Paragraph(t("conclusion", lang), h2),
                  Paragraph(escape(conclusion).replace("\n", "<br/>"), body)]

    if recommendations:
        story.append(Paragraph(t("recommendations", lang), h2))
        story += [Paragraph(f"{n}. {escape(r)}", body) for n, r in enumerate(recommendations, start=1)]

    if Path(chart_file).exists():
        # Heading and chart move to the next page together if they don't fit.
        story.append(KeepTogether([
            Paragraph(t("chart", lang), h2),
            Image(chart_file, width=PAGE_W - 2 * MARGIN, height=7 * cm, kind="proportional"),
        ]))

    seasonal = {code: d["seasonality"] for code, d in analysis.items() if d.get("seasonality")}
    if seasonal:
        blocks = [_seasonality_block(code, s, lang, body) for code, s in seasonal.items()]
        story.append(KeepTogether([Paragraph(t("seasonality", lang), h2), *blocks[0]]))
        story += [KeepTogether(b) for b in blocks[1:]]
        story.append(Paragraph(t("season_note", lang), small))

    for f in followups or []:
        block = [Paragraph(escape(t("followup", lang, question=f["question"])), h2)]
        if f.get("answer"):
            block.append(Paragraph(escape(f["answer"]).replace("\n", "<br/>"), body))
        if f.get("analysis"):
            block += [Spacer(1, 0.15 * cm), _results_table(f["analysis"], lang)]
        step_issues = auto_problems(
            f.get("analysis") or {}, f.get("langs_missing") or [], lang, f.get("langs_no_views") or []
        )
        if step_issues:
            block += [Spacer(1, 0.15 * cm), _issues_box(step_issues, body)]
        if f.get("chart_file") and Path(f["chart_file"]).exists():
            block.append(Image(f["chart_file"], width=PAGE_W - 2 * MARGIN, height=6 * cm, kind="proportional"))
        story.append(KeepTogether(block))

    story += [Spacer(1, 0.2 * cm), Paragraph(t("footer", lang), small)]

    target = str(output_file) if output_file else BytesIO()
    if output_file:
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        target, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN,
        bottomMargin=MARGIN, title=t("title", lang, topic=topic), author="wiki-interest skill",
    )
    # A short report fits one page; longer text simply flows onto the next page.
    doc.build(story, onFirstPage=_page_number, onLaterPages=_page_number)
    return None if output_file else target.getvalue()


def _page_number(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont(FONT, 7)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(PAGE_W - MARGIN, MARGIN / 2, str(doc.page))
    canvas.restoreState()
