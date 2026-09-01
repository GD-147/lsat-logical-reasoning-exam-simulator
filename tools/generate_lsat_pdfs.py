#!/usr/bin/env python3

from pathlib import Path
import json
import re
import shutil
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    KeepTogether,
)

ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = ROOT / "packs" / "lsat" / "data"
PDF_DIR = ROOT / "packs" / "lsat" / "pdf"
CONFIG_PATH = ROOT / "packs" / "lsat" / "config.json"

STAGE_DIR = ROOT / "packs" / "lsat" / "pdf.__generation_stage__"

LR_RE = re.compile(
    r"^lsat_logical_reasoning_(1|2)_exam_(\d{2})\.json$"
)



# ============================================================
# TEXT HELPERS
# ============================================================

def safe_text(value):
    """
    Convert normal Unicode punctuation to PDF-safe punctuation.
    This avoids broken glyphs with standard ReportLab fonts.
    """
    if value is None:
        return ""

    text = str(value)

    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2026": "...",
        "\u00a0": " ",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


def esc(text):
    """
    Escape text for ReportLab Paragraph XML.
    """
    text = safe_text(text)

    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )


def split_prompt(prompt):
    """
    Split the canonical LSAT prompt into:
      source material / passage / stimulus
      question stem

    Expected canonical separator:
      \\n\\nQuestion:\\n
    """

    prompt = safe_text(prompt)

    marker = "\n\nQuestion:\n"

    if marker in prompt:
        body, question = prompt.rsplit(marker, 1)
        return body.strip(), question.strip()

    return prompt.strip(), ""


# ============================================================
# STYLES
# ============================================================

styles = getSampleStyleSheet()

TITLE = ParagraphStyle(
    "LSATTitle",
    parent=styles["Title"],
    fontName="Helvetica-Bold",
    fontSize=18,
    leading=22,
    alignment=TA_CENTER,
    spaceAfter=14,
)

SUBTITLE = ParagraphStyle(
    "LSATSubtitle",
    parent=styles["Normal"],
    fontName="Helvetica",
    fontSize=9.5,
    leading=13,
    alignment=TA_CENTER,
    textColor=colors.HexColor("#444444"),
    spaceAfter=16,
)

SECTION_HEADING = ParagraphStyle(
    "LSATSectionHeading",
    parent=styles["Heading2"],
    fontName="Helvetica-Bold",
    fontSize=13,
    leading=16,
    spaceBefore=9,
    spaceAfter=8,
)

PASSAGE_STYLE = ParagraphStyle(
    "LSATPassage",
    parent=styles["BodyText"],
    fontName="Helvetica",
    fontSize=10,
    leading=14,
    spaceAfter=12,
)

QUESTION_STYLE = ParagraphStyle(
    "LSATQuestion",
    parent=styles["BodyText"],
    fontName="Helvetica-Bold",
    fontSize=10,
    leading=14,
    spaceBefore=5,
    spaceAfter=7,
)

CHOICE_STYLE = ParagraphStyle(
    "LSATChoice",
    parent=styles["BodyText"],
    fontName="Helvetica",
    fontSize=9.7,
    leading=13,
    leftIndent=14,
    firstLineIndent=-14,
    spaceAfter=4,
)

ANSWER_STYLE = ParagraphStyle(
    "LSATAnswer",
    parent=styles["BodyText"],
    fontName="Helvetica",
    fontSize=9.5,
    leading=13,
    spaceAfter=6,
)

EXPLANATION_STYLE = ParagraphStyle(
    "LSATExplanation",
    parent=styles["BodyText"],
    fontName="Helvetica",
    fontSize=9.3,
    leading=13,
    leftIndent=12,
    spaceAfter=13,
)



# ============================================================
# PAGE FOOTER
# ============================================================

def page_footer(canvas, doc):
    canvas.saveState()

    width, _ = letter

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#666666"))

    canvas.drawCentredString(
        width / 2,
        0.42 * inch,
        f"LSAT Logical Reasoning Exam Simulator - Page {doc.page}"
    )

    canvas.restoreState()


# ============================================================
# DOCUMENT
# ============================================================

def create_doc(path, title):
    return SimpleDocTemplate(
        str(path),
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
        title=title,
        author="LSAT Logical Reasoning Exam Simulator",
    )


def add_mcq_header(story, title, section_name, question_count):
    story.append(
        Paragraph(
            esc(title),
            TITLE,
        )
    )

    story.append(
        Paragraph(
            esc(
                f"{section_name} - {question_count} questions"
            ),
            SUBTITLE,
        )
    )

    story.append(
        Paragraph(
            esc(
                "Choose the best answer for each question. "
                "The answer key and detailed explanations "
                "begin after the question section."
            ),
            PASSAGE_STYLE,
        )
    )

    story.append(Spacer(1, 7))


# ============================================================
# LOGICAL REASONING PDF
# ============================================================

def generate_lr(data, output_path, display_title):
    questions = data["questions"]

    story = []

    add_mcq_header(
        story,
        display_title,
        "Logical Reasoning",
        len(questions),
    )

    story.append(
        Paragraph(
            "QUESTIONS",
            SECTION_HEADING,
        )
    )

    for number, q in enumerate(questions, 1):
        stimulus, stem = split_prompt(q["prompt"])

        block = []

        if stimulus:
            block.append(
                Paragraph(
                    esc(stimulus),
                    PASSAGE_STYLE,
                )
            )

        if stem:
            block.append(
                Paragraph(
                    f"<b>{number}.</b> {esc(stem)}",
                    QUESTION_STYLE,
                )
            )
        else:
            block.append(
                Paragraph(
                    f"<b>{number}.</b>",
                    QUESTION_STYLE,
                )
            )

        choices = q["choices"]

        for letter in ("A", "B", "C", "D", "E"):
            block.append(
                Paragraph(
                    f"<b>{letter}.</b> {esc(choices[letter])}",
                    CHOICE_STYLE,
                )
            )

        block.append(Spacer(1, 9))

        story.append(
            KeepTogether(block)
        )

    add_answer_section(story, questions)

    doc = create_doc(output_path, display_title)

    doc.build(
        story,
        onFirstPage=page_footer,
        onLaterPages=page_footer,
    )


# ============================================================
# ANSWER KEY AND EXPLANATIONS
# ============================================================

def add_answer_section(story, questions):
    story.append(PageBreak())

    story.append(
        Paragraph(
            "ANSWER KEY + DETAILED EXPLANATIONS",
            TITLE,
        )
    )

    # Compact answer key first.
    answer_lines = []

    for number, q in enumerate(questions, 1):
        answer_lines.append(
            f"{number}. {q['correct']}"
        )

    # Split answer key into manageable rows.
    chunk = 9

    for i in range(0, len(answer_lines), chunk):
        story.append(
            Paragraph(
                " &nbsp;&nbsp;&nbsp; ".join(
                    answer_lines[i:i + chunk]
                ),
                ANSWER_STYLE,
            )
        )

    story.append(Spacer(1, 12))

    for number, q in enumerate(questions, 1):
        correct = q["correct"]
        correct_text = q["correctAnswerText"]
        explanation = q["explanation"]

        story.append(
            Paragraph(
                f"<b>{number}. Correct: {esc(correct)}</b>",
                QUESTION_STYLE,
            )
        )

        story.append(
            Paragraph(
                f"<b>Correct Answer:</b> {esc(correct_text)}",
                ANSWER_STYLE,
            )
        )

        story.append(
            Paragraph(
                f"<b>Explanation:</b> {esc(explanation)}",
                EXPLANATION_STYLE,
            )
        )


# ============================================================
# WRITING PDF
# ============================================================
# MAIN GENERATION
# ============================================================

def main():

    if not DATA_DIR.exists():
        print("ERROR: packs/lsat/data does not exist.")
        sys.exit(1)

    files = sorted(DATA_DIR.glob("*.json"))

    if not files:
        print("ERROR: no validated Logical Reasoning JSON files found.")
        sys.exit(1)

    tasks = []
    errors = []

    # --------------------------------------------------------
    # Accept only validated LR1/LR2 JSON filenames.
    # --------------------------------------------------------

    for json_path in files:

        match = LR_RE.fullmatch(json_path.name)

        if not match:
            errors.append(
                f"unsupported JSON in LR portal: {json_path.name}"
            )
            continue

        source_no = int(match.group(1))
        exam_no = int(match.group(2))

        try:
            data = json.loads(
                json_path.read_text(
                    encoding="utf-8-sig"
                )
            )
        except Exception as exc:
            errors.append(
                f"{json_path.name}: invalid JSON: {exc}"
            )
            continue

        expected_section = (
            f"logical_reasoning_{source_no}"
        )

        if data.get("section") != expected_section:
            errors.append(
                f"{json_path.name}: section "
                f"{data.get('section')!r} does not match "
                f"{expected_section!r}"
            )
            continue

        questions = data.get("questions")

        if not isinstance(questions, list):
            errors.append(
                f"{json_path.name}: questions must be an array"
            )
            continue

        if not 25 <= len(questions) <= 26:
            errors.append(
                f"{json_path.name}: expected 25-26 questions, "
                f"found {len(questions)}"
            )
            continue

        # Preserve the mother portal's existing LR1 filenames:
        # Exam 01 -> PDF 01
        # Exam 02 -> PDF 04
        # Exam 03 -> PDF 07
        # ...
        #
        # If a genuine LR2 pool is ever added, it can use the
        # old second slot (02, 05, 08, ...) without collisions.
        legacy_slot = 1 if source_no == 1 else 2

        file_sequence = (
            (exam_no - 1) * 3
            + legacy_slot
        )

        tasks.append(
            {
                "json_path": json_path,
                "data": data,
                "source_no": source_no,
                "exam_no": exam_no,
                "file_sequence": file_sequence,
            }
        )

    if errors:
        print()
        print("PDF GENERATION FAILED")
        for error in errors:
            print("ERROR:", error)
        sys.exit(1)

    if not tasks:
        print("ERROR: no Logical Reasoning PDFs to generate.")
        sys.exit(1)

    tasks.sort(
        key=lambda item: (
            item["exam_no"],
            item["source_no"],
        )
    )

    if STAGE_DIR.exists():
        shutil.rmtree(STAGE_DIR)

    STAGE_DIR.mkdir(parents=True)

    generated = []

    print("==================================================")
    print("LSAT LOGICAL REASONING PRINTABLE PDF GENERATOR")
    print("==================================================")

    # --------------------------------------------------------
    # Generate PDFs.
    # --------------------------------------------------------

    for display_no, task in enumerate(
        tasks,
        1,
    ):
        pdf_name = (
            f"lsat_practice_exam_"
            f"{task['file_sequence']:02d}_"
            f"logical_reasoning.pdf"
        )

        label = (
            "LSAT Logical Reasoning Practice Exam "
            f"{display_no:02d}"
        )

        generate_lr(
            task["data"],
            STAGE_DIR / pdf_name,
            label,
        )

        generated.append(
            {
                "label": label,
                "file": pdf_name,
                "sequence": display_no,
            }
        )

        print(
            f"GENERATED: {pdf_name} "
            f"| {label}"
        )

    # --------------------------------------------------------
    # Validate generated PDFs.
    # --------------------------------------------------------

    validation_errors = []

    for item in generated:

        pdf = STAGE_DIR / item["file"]

        if not pdf.exists():
            validation_errors.append(
                f"missing generated PDF: {item['file']}"
            )
            continue

        size = pdf.stat().st_size

        if size < 1000:
            validation_errors.append(
                f"generated PDF suspiciously small: "
                f"{item['file']} ({size} bytes)"
            )

        with pdf.open("rb") as fh:
            signature = fh.read(5)

        if signature != b"%PDF-":
            validation_errors.append(
                f"invalid PDF signature: {item['file']}"
            )

    if validation_errors:

        print()
        print("PDF GENERATION FAILED")

        for error in validation_errors:
            print("ERROR:", error)

        shutil.rmtree(STAGE_DIR)
        sys.exit(1)

    # --------------------------------------------------------
    # Prepare config in memory.
    # --------------------------------------------------------

    try:
        cfg = json.loads(
            CONFIG_PATH.read_text(
                encoding="utf-8"
            )
        )
    except Exception as exc:
        shutil.rmtree(STAGE_DIR)

        print(
            f"ERROR: cannot read config.json: {exc}"
        )
        sys.exit(1)

    cfg["printables"] = [
        {
            "label": item["label"],
            "file": item["file"],
        }
        for item in generated
    ]

    config_stage = CONFIG_PATH.with_name(
        "config.json.__pdf_stage__"
    )

    config_stage.write_text(
        json.dumps(
            cfg,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # Transactional commit.
    # --------------------------------------------------------

    backup = (
        PDF_DIR.parent
        / "pdf.__before_generation__"
    )

    if backup.exists():
        shutil.rmtree(backup)

    if PDF_DIR.exists():
        PDF_DIR.rename(backup)

    try:
        STAGE_DIR.rename(PDF_DIR)
        config_stage.replace(CONFIG_PATH)

    except Exception:

        if PDF_DIR.exists():
            shutil.rmtree(PDF_DIR)

        if backup.exists():
            backup.rename(PDF_DIR)

        if STAGE_DIR.exists():
            shutil.rmtree(STAGE_DIR)

        if config_stage.exists():
            config_stage.unlink()

        raise

    if backup.exists():
        shutil.rmtree(backup)

    print()
    print("==================================================")
    print("PDF GENERATION OK")
    print("==================================================")
    print(
        f"Generated Logical Reasoning PDFs: "
        f"{len(generated)}"
    )
    print(
        "config.json printables updated successfully."
    )


if __name__ == "__main__":
    main()
