#!/usr/bin/env python3

from pathlib import Path
import json
import re
import shutil
import sys
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]

SOURCE_ROOT = ROOT / "imports" / "lsat_exams" / "json"
DATA_DIR = ROOT / "packs" / "lsat" / "data"
CONFIG_PATH = ROOT / "packs" / "lsat" / "config.json"

VALID_SECTIONS = {
    "logical_reasoning_1": {
        "folder": "logical_reasoning",
        "prefix": "LR1",
        "filename": re.compile(
            r"^lsat_logical_reasoning_1_exam_(\d{2})\.json$"
        ),
        "min_questions": 25,
        "max_questions": 26,
        "type": "mcq",
        "label": "Internal Logical Reasoning Source 1",
    },
    "logical_reasoning_2": {
        "folder": "logical_reasoning",
        "prefix": "LR2",
        "filename": re.compile(
            r"^lsat_logical_reasoning_2_exam_(\d{2})\.json$"
        ),
        "min_questions": 25,
        "max_questions": 26,
        "type": "mcq",
        "label": "Internal Logical Reasoning Source 2",
    },
}

ID_RE = re.compile(
    r"^LSAT-(LR1|LR2)-(\d{2})-(\d{3})$"
)

CHOICE_KEYS = {"A", "B", "C", "D", "E"}


def fail(errors):
    print()
    print("==================================================")
    print("IMPORT FAILED")
    print("==================================================")

    for error in errors:
        print("ERROR:", error)

    print()
    print(
        "No JSON files were copied to packs/lsat/data "
        "and config.json was not changed."
    )
    sys.exit(1)


def load_json(path, errors):
    try:
        return json.loads(
            path.read_text(encoding="utf-8-sig")
        )
    except Exception as exc:
        errors.append(
            f"{path.relative_to(ROOT)}: invalid JSON: {exc}"
        )
        return None


def validate_file(path, errors, all_ids):
    rel = path.relative_to(ROOT)

    data = load_json(path, errors)

    if data is None:
        return None

    if not isinstance(data, dict):
        errors.append(
            f"{rel}: root must be an object"
        )
        return None

    title = data.get("title")
    section = data.get("section")
    questions = data.get("questions")

    if not isinstance(title, str) or not title.strip():
        errors.append(
            f"{rel}: missing or invalid title"
        )

    if section not in VALID_SECTIONS:
        errors.append(
            f"{rel}: unsupported section {section!r}; "
            "this portal accepts only logical_reasoning_1 "
            "or logical_reasoning_2"
        )
        return None

    spec = VALID_SECTIONS[section]

    if path.parent.name != spec["folder"]:
        errors.append(
            f"{rel}: file is in folder "
            f"{path.parent.name!r}, "
            f"expected {spec['folder']!r}"
        )

    match = spec["filename"].fullmatch(path.name)

    if not match:
        errors.append(
            f"{rel}: filename does not match expected "
            f"{section} convention"
        )
        return None

    exam_no = match.group(1)

    if not isinstance(questions, list):
        errors.append(
            f"{rel}: questions must be an array"
        )
        return None

    count = len(questions)

    if not (
        spec["min_questions"]
        <= count
        <= spec["max_questions"]
    ):
        errors.append(
            f"{rel}: expected "
            f"{spec['min_questions']}-{spec['max_questions']} "
            f"questions, found {count}"
        )

    expected_ids = [
        f"LSAT-{spec['prefix']}-{exam_no}-{i:03d}"
        for i in range(1, count + 1)
    ]

    actual_ids = []

    for index, q in enumerate(questions, 1):

        if not isinstance(q, dict):
            errors.append(
                f"{rel}: question #{index} is not an object"
            )
            continue

        qid = q.get("id")

        if not isinstance(qid, str):
            errors.append(
                f"{rel}: question #{index} missing valid id"
            )
            continue

        actual_ids.append(qid)
        all_ids.append(qid)

        match_id = ID_RE.fullmatch(qid)

        if not match_id:
            errors.append(
                f"{rel}: invalid ID {qid!r}"
            )
        else:
            prefix, id_exam, id_question = (
                match_id.groups()
            )

            if prefix != spec["prefix"]:
                errors.append(
                    f"{rel}: {qid} has wrong section prefix"
                )

            if id_exam != exam_no:
                errors.append(
                    f"{rel}: {qid} exam number does not "
                    f"match filename {exam_no}"
                )

            expected_question_no = f"{index:03d}"

            if id_question != expected_question_no:
                errors.append(
                    f"{rel}: {qid} question number does not "
                    f"match position {expected_question_no}"
                )

        if q.get("type") != "mcq":
            errors.append(
                f"{rel}: {qid} expected type 'mcq'"
            )

        if q.get("itemType") != "mcq":
            errors.append(
                f"{rel}: {qid} expected itemType 'mcq'"
            )

        if (
            not isinstance(q.get("section"), str)
            or not q["section"].strip()
        ):
            errors.append(
                f"{rel}: {qid} missing question section"
            )

        for field in ("focus", "category"):
            if field not in q:
                errors.append(
                    f"{rel}: {qid} missing {field}"
                )
            elif not isinstance(q[field], str):
                errors.append(
                    f"{rel}: {qid} {field} must be string"
                )

        if (
            not isinstance(q.get("prompt"), str)
            or not q["prompt"].strip()
        ):
            errors.append(
                f"{rel}: {qid} missing prompt"
            )

        if q.get("credits") != 1:
            errors.append(
                f"{rel}: {qid} credits must equal 1"
            )

        choices = q.get("choices")

        if not isinstance(choices, dict):
            errors.append(
                f"{rel}: {qid} choices must be object"
            )
            continue

        if set(choices.keys()) != CHOICE_KEYS:
            errors.append(
                f"{rel}: {qid} choices must be "
                "exactly A, B, C, D, E"
            )

        for letter in CHOICE_KEYS:
            if (
                letter not in choices
                or not isinstance(choices[letter], str)
                or not choices[letter].strip()
            ):
                errors.append(
                    f"{rel}: {qid} invalid/empty choice "
                    f"{letter}"
                )

        correct = q.get("correct")

        if correct not in CHOICE_KEYS:
            errors.append(
                f"{rel}: {qid} invalid correct answer "
                f"{correct!r}"
            )

        elif correct in choices:

            correct_text = q.get("correctAnswerText")

            if not isinstance(correct_text, str):
                errors.append(
                    f"{rel}: {qid} missing "
                    "correctAnswerText"
                )

            elif (
                correct_text.strip()
                != choices[correct].strip()
            ):
                errors.append(
                    f"{rel}: {qid} correctAnswerText "
                    f"does not match choice {correct}"
                )

        if (
            not isinstance(q.get("explanation"), str)
            or not q["explanation"].strip()
        ):
            errors.append(
                f"{rel}: {qid} missing explanation"
            )

    if actual_ids != expected_ids:
        errors.append(
            f"{rel}: IDs are not the exact consecutive "
            f"sequence expected for Exam {exam_no}"
        )

    return {
        "path": path,
        "section": section,
        "exam_no": exam_no,
        "questions": count,
    }


def main():

    errors = []
    all_ids = []
    validated = []

    files = sorted(
        SOURCE_ROOT.rglob("*.json")
    )

    if not files:
        fail([
            "No JSON files found in "
            "imports/lsat_exams/json/"
        ])

    print("==================================================")
    print("LSAT LOGICAL REASONING JSON VALIDATION")
    print("==================================================")

    for path in files:
        result = validate_file(
            path,
            errors,
            all_ids,
        )

        if result:
            validated.append(result)

    duplicate_counts = Counter(all_ids)

    for qid, occurrences in sorted(
        duplicate_counts.items()
    ):
        if occurrences > 1:
            errors.append(
                f"duplicate global ID {qid}: "
                f"{occurrences} occurrences"
            )

    seen_exam = {}

    for item in validated:
        key = (
            item["section"],
            item["exam_no"],
        )

        if key in seen_exam:
            errors.append(
                "duplicate exam number: "
                f"{item['section']} Exam "
                f"{item['exam_no']}"
            )

        seen_exam[key] = item["path"]

    if errors:
        fail(errors)

    counts = Counter(
        item["section"]
        for item in validated
    )

    print()
    print("VALIDATION CLEAN")
    print(f"Files: {len(validated)}")
    print(f"Questions: {len(all_ids)}")
    print(
        "logical_reasoning_1:",
        counts.get("logical_reasoning_1", 0),
        "file(s)"
    )
    print(
        "logical_reasoning_2:",
        counts.get("logical_reasoning_2", 0),
        "file(s)"
    )

    # --------------------------------------------------
    # Prepare config IN MEMORY before touching live data.
    # --------------------------------------------------

    try:
        cfg = json.loads(
            CONFIG_PATH.read_text(
                encoding="utf-8"
            )
        )
    except Exception as exc:
        fail([
            f"Cannot read config.json: {exc}"
        ])

    sections = {
        section.get("id"): section
        for section in cfg.get("sections", [])
        if isinstance(section, dict)
    }

    public = sections.get(
        "logical_reasoning"
    )

    if not public:
        fail([
            "config.json missing public "
            "logical_reasoning section"
        ])

    files_by_section = {
        "logical_reasoning_1": [],
        "logical_reasoning_2": [],
    }

    for item in sorted(
        validated,
        key=lambda x: (
            x["section"],
            x["exam_no"],
        ),
    ):
        files_by_section[
            item["section"]
        ].append(
            item["path"].name
        )

    available_sources = []

    new_sections = [public]

    for section_id in (
        "logical_reasoning_1",
        "logical_reasoning_2",
    ):
        exam_files = files_by_section[
            section_id
        ]

        if not exam_files:
            continue

        source = sections.get(section_id)

        if source is None:
            spec = VALID_SECTIONS[
                section_id
            ]

            source = {
                "id": section_id,
                "label": spec["label"],
                "timeMin": 35,
                "examQuestions": 26,
                "type": "mcq",
                "examFiles": [],
                "hidden": True,
            }

        source["label"] = (
            VALID_SECTIONS[
                section_id
            ]["label"]
        )
        source["timeMin"] = 35
        source["examQuestions"] = 26
        source["type"] = "mcq"
        source["examFiles"] = exam_files
        source["hidden"] = True
        source.pop(
            "sourceSections",
            None
        )

        new_sections.append(source)
        available_sources.append(
            section_id
        )

    if not available_sources:
        fail([
            "No validated Logical Reasoning "
            "source pool was found."
        ])

    public["label"] = (
        "LSAT Logical Reasoning"
    )
    public["timeMin"] = 35
    public["examQuestions"] = 26
    public["type"] = "mcq"
    public["examFiles"] = []
    public["sourceSections"] = (
        available_sources
    )
    public.pop("hidden", None)

    cfg["sections"] = new_sections

    # --------------------------------------------------
    # Stage output before replacing live data.
    # --------------------------------------------------

    stage_dir = (
        DATA_DIR.parent
        / "data.__json_import_stage__"
    )

    if stage_dir.exists():
        shutil.rmtree(stage_dir)

    stage_dir.mkdir(
        parents=True
    )

    for item in validated:
        shutil.copy2(
            item["path"],
            stage_dir
            / item["path"].name,
        )

    config_stage = (
        CONFIG_PATH.parent
        / "config.json.__stage__"
    )

    config_stage.write_text(
        json.dumps(
            cfg,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    # --------------------------------------------------
    # Transactional commit.
    # --------------------------------------------------

    backup_dir = (
        DATA_DIR.parent
        / "data.__before_json_import__"
    )

    if backup_dir.exists():
        shutil.rmtree(
            backup_dir
        )

    if DATA_DIR.exists():
        DATA_DIR.rename(
            backup_dir
        )

    try:
        stage_dir.rename(
            DATA_DIR
        )

        config_stage.replace(
            CONFIG_PATH
        )

    except Exception:

        if DATA_DIR.exists():
            shutil.rmtree(
                DATA_DIR
            )

        if backup_dir.exists():
            backup_dir.rename(
                DATA_DIR
            )

        if stage_dir.exists():
            shutil.rmtree(
                stage_dir
            )

        if config_stage.exists():
            config_stage.unlink()

        raise

    if backup_dir.exists():
        shutil.rmtree(
            backup_dir
        )

    print()
    print("==================================================")
    print("IMPORT OK")
    print("==================================================")
    print(
        f"Imported {len(validated)} Logical Reasoning "
        f"JSON files into "
        f"{DATA_DIR.relative_to(ROOT)}"
    )
    print(
        "Active source pools:",
        ", ".join(available_sources)
    )
    print(
        "config.json updated successfully."
    )


if __name__ == "__main__":
    main()
