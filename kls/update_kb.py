import argparse
import re
from datetime import datetime, timezone
from pathlib import Path

from kls.utils import read_json, write_jsonl


KB_DIR = Path("kb")
FEEDBACK_DIR = Path("exam_feedback")
TRACES_DIR = Path("traces")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def sanitize_filename(text: str) -> str:
    safe = re.sub(r"[^\w\s-]", "", text).strip().replace(" ", "_").lower()[:50]
    return safe if safe else "gap"


def update_kb_from_feedback(feedback_path: Path, run_id: str) -> dict:
    feedback = read_json(feedback_path)
    if not feedback:
        raise ValueError(f"Could not read feedback: {feedback_path}")

    exam_set_id = feedback.get("exam_set_id", "unknown")
    questions = feedback.get("questions", [])

    concepts_dir = KB_DIR / "concepts"
    concepts_dir.mkdir(parents=True, exist_ok=True)

    gaps_added = 0
    concepts_updated = []

    for q in questions:
        gaps = q.get("gaps", [])
        study_actions = q.get("study_actions", [])

        for gap in gaps:
            if not gap or not isinstance(gap, str):
                continue

            safe_name = sanitize_filename(gap)
            concept_path = concepts_dir / f"{safe_name}.md"

            timestamp = now_iso()

            if concept_path.exists():
                content = concept_path.read_text(encoding="utf-8")
            else:
                content = f"# {gap}\n\n"

            content += f"\n## Gaps from exams\n"
            content += f"- **Exam**: {exam_set_id}\n"
            content += f"- **Question**: {q.get('question_id', 'unknown')}\n"
            content += f"- **Timestamp**: {timestamp}\n"
            content += f"- **Gap identified**: {gap}\n"

            if study_actions:
                content += "- **Study actions**:\n"
                for action in study_actions:
                    if action:
                        content += f"  - {action}\n"

            content += f"- **Rationale**: {q.get('rationale', 'N/A')[:200]}...\n"

            concept_path.write_text(content, encoding="utf-8")

            gaps_added += 1
            if safe_name not in concepts_updated:
                concepts_updated.append(safe_name)

    trace_record = {
        "event": "kb_update",
        "run_id": run_id,
        "feedback_path": str(feedback_path),
        "exam_set_id": exam_set_id,
        "gaps_added": gaps_added,
        "concepts_updated": concepts_updated,
        "timestamp": now_iso(),
    }

    trace_path = TRACES_DIR / "ingest_runs" / f"{run_id}_kb_update.jsonl"
    write_jsonl(trace_path, [trace_record])

    return {
        "run_id": run_id,
        "exam_set_id": exam_set_id,
        "gaps_added": gaps_added,
        "concepts_updated": concepts_updated,
        "timestamp": now_iso(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--feedback", required=True, help="Path to feedback JSON file")
    parser.add_argument("--run-id", default=None, help="Optional run ID")
    args = parser.parse_args()

    run_id = args.run_id or f"kb_{int(datetime.now().timestamp())}"
    feedback_path = Path(args.feedback)

    if not feedback_path.exists():
        print(f"ERROR: Feedback file not found: {feedback_path}")
        exit(1)

    try:
        result = update_kb_from_feedback(feedback_path, run_id)
        print(f"KB update complete: {result['gaps_added']} gaps added")
        print(f"Concepts updated: {', '.join(result['concepts_updated'])}")
    except Exception as e:
        print(f"ERROR: {e}")
        exit(1)


if __name__ == "__main__":
    main()
