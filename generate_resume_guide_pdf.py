"""Render Resume_Project_Interview_Guide.md as a print-friendly PDF.

Requires ReportLab:  python -m pip install reportlab
"""

from __future__ import annotations

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "Resume_Project_Interview_Guide.md"
OUTPUT = ROOT / "Resume_Project_Interview_Guide.pdf"
TITLE = "Resume Project Interview Guide"
PAGE_WIDTH, PAGE_HEIGHT = letter


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "GuideTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=27,
            textColor=colors.HexColor("#17365D"),
            alignment=TA_CENTER,
            spaceAfter=16,
        ),
        "subtitle": ParagraphStyle(
            "GuideSubtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#455A64"),
            spaceAfter=20,
        ),
        "h1": ParagraphStyle(
            "GuideH1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#17365D"),
            spaceBefore=14,
            spaceAfter=8,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "GuideH2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12.5,
            leading=16,
            textColor=colors.HexColor("#285B8F"),
            spaceBefore=12,
            spaceAfter=6,
            keepWithNext=True,
        ),
        "h3": ParagraphStyle(
            "GuideH3",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=14,
            textColor=colors.HexColor("#1F4E79"),
            spaceBefore=9,
            spaceAfter=4,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "GuideBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.2,
            leading=13,
            spaceAfter=5,
        ),
        "bullet": ParagraphStyle(
            "GuideBullet",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.2,
            leading=12.5,
            leftIndent=15,
            firstLineIndent=-8,
            spaceAfter=3,
        ),
        "code": ParagraphStyle(
            "GuideCode",
            parent=base["Code"],
            fontName="Courier",
            fontSize=7.6,
            leading=9.8,
            backColor=colors.HexColor("#F3F6F8"),
            borderColor=colors.HexColor("#D2DCE5"),
            borderWidth=0.5,
            borderPadding=5,
            spaceBefore=5,
            spaceAfter=7,
        ),
        "table": ParagraphStyle(
            "GuideTable",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.2,
            leading=9,
        ),
        "table_header": ParagraphStyle(
            "GuideTableHeader",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.2,
            leading=9,
            textColor=colors.white,
        ),
    }


def inline_markdown(text: str) -> str:
    """Escape text and restore a compact Markdown subset used in the guide."""
    rendered = []
    for segment in re.split(r"(`[^`]+`)", text):
        if segment.startswith("`") and segment.endswith("`"):
            rendered.append(f'<font name="Courier">{html.escape(segment[1:-1])}</font>')
            continue
        value = html.escape(segment)
        value = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", value)
        value = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", value)
        rendered.append(value)
    return "".join(rendered)


def table_flowable(lines: list[str], s: dict[str, ParagraphStyle]) -> Table:
    rows = []
    for row_index, line in enumerate(lines):
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        rows.append(
            [
                Paragraph(inline_markdown(cell), s["table_header" if row_index == 0 else "table"])
                for cell in cells
            ]
        )
    column_count = max(len(row) for row in rows)
    for row in rows:
        row.extend([Paragraph("", s["table"])] * (column_count - len(row)))
    available = PAGE_WIDTH - 1.1 * inch
    widths = [available / column_count] * column_count
    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#285B8F")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5DF")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F7F9FB")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F7FA")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def parse_markdown(markdown: str, s: dict[str, ParagraphStyle]) -> list:
    story = []
    lines = markdown.splitlines()
    index = 0
    first_title = True

    while index < len(lines):
        line = lines[index]
        if line.startswith("```"):
            code_lines = []
            index += 1
            while index < len(lines) and not lines[index].startswith("```"):
                code_lines.append(lines[index])
                index += 1
            story.append(Preformatted("\n".join(code_lines), s["code"]))
        elif line.startswith("|") and index + 1 < len(lines) and re.match(
            r"^\|?[\s:|-]+\|", lines[index + 1]
        ):
            table_lines = [line]
            index += 2  # Skip Markdown divider.
            while index < len(lines) and lines[index].startswith("|"):
                table_lines.append(lines[index])
                index += 1
            story.append(Spacer(1, 3))
            story.append(table_flowable(table_lines, s))
            story.append(Spacer(1, 7))
            continue
        elif line == "---":
            story.append(Spacer(1, 8))
            story.append(
                Table(
                    [[""]],
                    colWidths=[PAGE_WIDTH - 1.1 * inch],
                    rowHeights=[0.5],
                    style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#9FB3C8"))]),
                )
            )
            story.append(Spacer(1, 8))
        elif line.startswith("# "):
            if first_title:
                story.append(Spacer(1, 0.65 * inch))
                story.append(Paragraph(inline_markdown(line[2:]), s["title"]))
                first_title = False
            else:
                story.append(PageBreak())
                story.append(Paragraph(inline_markdown(line[2:]), s["h1"]))
        elif line.startswith("## "):
            story.append(Paragraph(inline_markdown(line[3:]), s["h2"]))
        elif line.startswith("### "):
            story.append(Paragraph(inline_markdown(line[4:]), s["h3"]))
        elif line.startswith("* ") or line.startswith("- "):
            story.append(Paragraph("• " + inline_markdown(line[2:]), s["bullet"]))
        elif re.match(r"^\d+\.\s", line):
            story.append(Paragraph(inline_markdown(line), s["bullet"]))
        elif line.strip():
            if first_title:
                story.append(Paragraph(inline_markdown(line), s["subtitle"]))
            else:
                story.append(Paragraph(inline_markdown(line), s["body"]))
        else:
            story.append(Spacer(1, 3))
        index += 1
    return story


def page_header_footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#CBD5DF"))
    canvas.line(0.55 * inch, PAGE_HEIGHT - 0.44 * inch, PAGE_WIDTH - 0.55 * inch, PAGE_HEIGHT - 0.44 * inch)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#52616B"))
    canvas.drawString(0.55 * inch, PAGE_HEIGHT - 0.34 * inch, TITLE)
    canvas.drawRightString(PAGE_WIDTH - 0.55 * inch, 0.34 * inch, f"Page {doc.page}")
    canvas.drawString(0.55 * inch, 0.34 * inch, "Code-grounded study material · verify current code before interview use")
    canvas.restoreState()


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(f"Missing source document: {SOURCE}")
    document = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=letter,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.62 * inch,
        bottomMargin=0.58 * inch,
        title=TITLE,
        author="Sheel Patel",
        subject="Technical interview preparation for personal projects",
    )
    document.build(parse_markdown(SOURCE.read_text(encoding="utf-8"), styles()), onFirstPage=page_header_footer, onLaterPages=page_header_footer)
    print(f"Created {OUTPUT}")


if __name__ == "__main__":
    main()
