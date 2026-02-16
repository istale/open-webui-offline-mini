import argparse
import json
import re
import uuid
from pathlib import Path

from kls.utils import (
    compute_sha256,
    ensure_dir,
    list_png_files,
    now_iso,
    read_optional_txt,
    write_jsonl,
)


MATERIALS_DIR = Path("domain_knowledge_materials")
KB_DIR = Path("kb")
TRACES_DIR = Path("traces")


def extract_concepts(text: str) -> list:
    concepts = []
    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("- ") or line.startswith("* "):
            concepts.append(line[2:].strip())
        elif line.startswith("Concept: "):
            concepts.append(line[9:].strip())
        elif ":" in line and len(line) < 100:
            parts = line.split(":", 1)
            if parts[0].strip() and parts[1].strip():
                concepts.append(parts[0].strip())
    return concepts if concepts else ["General content"]


def process_slide(slide_path: Path, deck_id: str) -> dict:
    text = read_optional_txt(slide_path)
    sha256 = compute_sha256(slide_path)
    slide_id = slide_path.stem

    try:
        rel_path = str(slide_path.relative_to(Path.cwd()))
    except ValueError:
        rel_path = str(slide_path)

    record = {
        "deck_id": deck_id,
        "slide_id": slide_id,
        "text": text,
        "sha256": sha256,
        "path": rel_path,
    }

    return record


def generate_concept_md(concepts: list, deck_id: str, slide_refs: list) -> str:
    lines = []
    for concept in concepts:
        lines.append(f"## {concept}")
        lines.append(
            f"Source: {deck_id}/slide_{slide_refs[0] if slide_refs else 'unknown'}"
        )
        lines.append("")
    return "\n".join(lines)


def ingest_deck(deck_path: Path, run_id: str) -> dict:
    deck_id = deck_path.name
    slides_dir = deck_path / "slides"

    if not slides_dir.exists():
        raise ValueError(f"No slides directory found: {slides_dir}")

    slide_files = list_png_files(slides_dir)
    if not slide_files:
        raise ValueError(f"No slide images found in: {slides_dir}")

    all_records = []
    all_concepts = []

    for slide_path in slide_files:
        record = process_slide(slide_path, deck_id)
        all_records.append(record)

        if record["text"]:
            concepts = extract_concepts(record["text"])
            all_concepts.extend(concepts)

    index_path = KB_DIR / "indices" / "material_index.jsonl"
    write_jsonl(index_path, all_records)

    concepts_dir = KB_DIR / "concepts"
    ensure_dir(concepts_dir)

    unique_concepts = list(set(all_concepts))
    for concept in unique_concepts:
        safe_name = (
            re.sub(r"[^\w\s-]", "", concept).strip().replace(" ", "_").lower()[:50]
        )
        if not safe_name:
            safe_name = "concept"

        concept_path = concepts_dir / f"{safe_name}.md"
        slide_ids = [r["slide_id"] for r in all_records if r["text"]]

        if concept_path.exists():
            content = concept_path.read_text(encoding="utf-8")
        else:
            content = f"# {concept}\n\n"

        new_content = generate_concept_md([concept], deck_id, slide_ids[:1])
        content += "\n" + new_content
        concept_path.write_text(content, encoding="utf-8")

    return {
        "run_id": run_id,
        "deck_id": deck_id,
        "processed_slides": len(all_records),
        "concepts_extracted": len(unique_concepts),
        "timestamp": now_iso(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--deck",
        required=True,
        help="Deck directory name under domain_knowledge_materials/",
    )
    parser.add_argument("--run-id", default=None, help="Optional run ID")
    args = parser.parse_args()

    run_id = args.run_id or str(uuid.uuid4())[:8]
    deck_path = MATERIALS_DIR / args.deck

    if not deck_path.exists():
        print(f"ERROR: Deck not found: {deck_path}")
        exit(1)

    trace_records = []
    trace_records.append(
        {
            "event": "ingest_start",
            "run_id": run_id,
            "deck": args.deck,
            "timestamp": now_iso(),
        }
    )

    try:
        result = ingest_deck(deck_path, run_id)
        trace_records.append(
            {
                "event": "ingest_complete",
                "run_id": run_id,
                "result": result,
                "timestamp": now_iso(),
            }
        )
        print(
            f"Ingest complete: {result['processed_slides']} slides, {result['concepts_extracted']} concepts"
        )
    except Exception as e:
        trace_records.append(
            {
                "event": "ingest_error",
                "run_id": run_id,
                "error": str(e),
                "timestamp": now_iso(),
            }
        )
        print(f"ERROR: {e}")
        exit(1)
    finally:
        trace_path = TRACES_DIR / "ingest_runs" / f"{run_id}.jsonl"
        write_jsonl(trace_path, trace_records)


if __name__ == "__main__":
    main()
