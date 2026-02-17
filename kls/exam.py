import argparse
import json
import os
import uuid
from pathlib import Path

import httpx

from kls.utils import (
    ensure_dir,
    get_env,
    list_png_files,
    now_iso,
    read_json,
    read_optional_txt,
    write_json,
    write_jsonl,
)


EXAMS_DIR = Path("domain_knowledge_exams")
TRACES_DIR = Path("traces")
FEEDBACK_DIR = Path("exam_feedback")


def call_llm(prompt: str, env: dict) -> str:
    base_url = env["OPENAI_BASE_URL"].rstrip("/")
    api_key = env["OPENAI_API_KEY"]

    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": os.environ.get("DEFAULT_CHAT_MODEL", "gpt-3.5-turbo"),
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 500,
        "stream": False,
    }

    # NOTE: local models can be slow (first-token latency). Use a longer timeout.
    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=180.0)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"ERROR: {e}"


def generate_answer(question_text: str, env: dict) -> str:
    prompt = f"""Answer the following question concisely:

Question: {question_text}

Provide a brief answer:"""

    return call_llm_with_retry(prompt, env)


def call_llm_with_retry(prompt: str, env: dict, attempts: int = 3) -> str:
    """Retry wrapper for slow local backends."""
    last = ""
    for i in range(attempts):
        last = call_llm(prompt, env)
        if not (isinstance(last, str) and last.startswith("ERROR:")):
            return last
    return last


def grade_answer(
    question_text: str, student_answer: str, correct_answer: str, env: dict
) -> dict:
    prompt = f"""You are grading a student's answer. DO NOT include the question text, numbers, or specific details in your response.

Compare the student's answer to the correct answer conceptually.

Student Answer: {student_answer}

Correct Answer: {correct_answer}

Respond in this JSON format (no markdown code blocks, just raw JSON):
{{
  "result": "correct" or "incorrect" or "partial",
  "rationale": "2-6 sentences explaining conceptually why the answer is correct or incorrect. Avoid quoting the question.",
  "gaps": ["conceptual gap 1", "conceptual gap 2"],
  "study_actions": ["action to study concept 1", "action to study concept 2"]
}}"""

    response = call_llm_with_retry(prompt, env)

    try:
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            json_str = response[start:end]
            result = json.loads(json_str)
        else:
            result = json.loads(response)

        for key in ["result", "rationale", "gaps", "study_actions"]:
            if key not in result:
                result[key] = [] if key in ["gaps", "study_actions"] else "unknown"

        return result
    except json.JSONDecodeError:
        return {
            "result": "unknown",
            "rationale": "Failed to parse LLM response",
            "gaps": ["Parsing error"],
            "study_actions": ["Review manually"],
        }


def process_exam(exam_path: Path, run_id: str, env: dict, max_new_questions: int | None = None) -> dict:
    print(f"[kls.exam] run_id={run_id} exam_set={exam_path.name}")
    exam_set_id = exam_path.name
    questions_dir = exam_path / "questions"
    answers_dir = exam_path / "answers"

    # Checkpoint file for resumable runs (per-question records)
    ensure_dir(TRACES_DIR / "exam_runs")
    checkpoint_path = TRACES_DIR / "exam_runs" / f"{run_id}.checkpoint.jsonl"

    if not questions_dir.exists():
        raise ValueError(f"No questions directory found: {questions_dir}")

    question_files = list_png_files(questions_dir)
    if not question_files:
        raise ValueError(f"No question images found in: {questions_dir}")

    answer_key_path = answers_dir / "answer_key.json"
    answer_key = read_json(answer_key_path) or {}

    # Load existing checkpoint records so feedback can be cumulative.
    prior_by_qid: dict[str, dict] = {}

    # Resume support: skip questions already processed
    done = set()
    if checkpoint_path.exists():
        try:
            for line in checkpoint_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                qid = rec.get("question_id")
                if qid:
                    done.add(qid)
                    prior_by_qid[qid] = rec
        except Exception:
            pass

    feedback_records: list[dict] = []

    print(f"[kls.exam] questions={len(question_files)} done={len(done)}")
    results_summary = []

    processed_new = 0

    for idx, q_path in enumerate(question_files, start=1):
        qid = q_path.stem  # e.g. q_0001
        if qid in done:
            print(f"[kls.exam] Q{idx}/{len(question_files)} {qid} (skip; already done)", flush=True)
            continue
        print(f"[kls.exam] Q{idx}/{len(question_files)} {qid} file={q_path.name}", flush=True)
        q_id = q_path.stem
        # Prefer sidecar .txt for question text; do NOT try to read the PNG bytes as text.
        question_text = read_optional_txt(q_path.with_suffix(".txt"))

        if not question_text:
            question_text = f"[Image-only question: {q_id}]"

        answer_entry = answer_key.get(q_id, {})
        correct_answer = (
            answer_entry.get("answer", "")
            if isinstance(answer_entry, dict)
            else str(answer_entry)
        )

        student_answer = generate_answer(question_text, env)

        # Fast grading to reduce LLM calls: determine correctness by matching answer key.
        result = "unknown"
        if correct_answer:
            sa_u = str(student_answer).strip().upper()
            ca_u = str(correct_answer).strip().upper()
            if ca_u and ca_u in sa_u:
                result = "correct"
            elif ca_u:
                result = "incorrect"

        # Only use LLM grading feedback when not correct (reduce total calls)
        if not correct_answer:
            feedback = {
                "result": "unknown",
                "rationale": "No answer key available for grading",
                "gaps": [],
                "study_actions": [],
            }
        elif result == "correct":
            feedback = {
                "result": "correct",
                "rationale": "",
                "gaps": [],
                "study_actions": [],
            }
        else:
            feedback = grade_answer(question_text, student_answer, correct_answer, env)
            if result in ("incorrect", "correct"):
                feedback["result"] = result

        feedback_record = {
            "question_id": q_id,
            "question_path": str(q_path),
            "student_answer": student_answer,
            "correct_answer": correct_answer,
            "result": feedback["result"],
            "rationale": feedback["rationale"],
            "gaps": feedback["gaps"],
            "study_actions": feedback["study_actions"],
        }

        # Checkpoint per-question for resumability
        with checkpoint_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(feedback_record, ensure_ascii=False) + "\n")

        feedback_records.append(feedback_record)

        results_summary.append({"question_id": q_id, "result": feedback["result"]})

        processed_new += 1
        if max_new_questions is not None and processed_new >= max_new_questions:
            print(f"[kls.exam] Reached max_new_questions={max_new_questions}; stopping early", flush=True)
            break

    # Cumulative feedback = prior checkpoint records + newly processed records (dedup by question_id)
    combined = dict(prior_by_qid)
    for rec in feedback_records:
        qid = rec.get("question_id")
        if qid:
            combined[qid] = rec
    feedback_output = {
        "run_id": run_id,
        "exam_set_id": exam_set_id,
        "timestamp": now_iso(),
        "questions": [combined[k] for k in sorted(combined.keys())],
    }

    feedback_dir = FEEDBACK_DIR / exam_set_id
    ensure_dir(feedback_dir)
    feedback_path = feedback_dir / f"{run_id}.json"
    write_json(feedback_path, feedback_output)

    correct_count = sum(1 for r in results_summary if r["result"] == "correct")
    incorrect_count = sum(1 for r in results_summary if r["result"] == "incorrect")

    return {
        "run_id": run_id,
        "exam_set_id": exam_set_id,
        "total_questions": len(question_files),
        "correct": correct_count,
        "incorrect": incorrect_count,
        "unknown": len(question_files) - correct_count - incorrect_count,
        "feedback_path": str(feedback_path),
        "timestamp": now_iso(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--exam",
        required=True,
        help="Exam set directory name under domain_knowledge_exams/",
    )
    parser.add_argument("--run-id", default=None, help="Optional run ID")
    parser.add_argument(
        "--max-new",
        type=int,
        default=None,
        help="Process at most N not-yet-done questions this run (for batching/resume).",
    )
    args = parser.parse_args()

    run_id = args.run_id or str(uuid.uuid4())[:8]
    exam_path = EXAMS_DIR / args.exam

    if not exam_path.exists():
        print(f"ERROR: Exam not found: {exam_path}")
        exit(1)

    env = get_env()

    trace_records = []
    trace_records.append(
        {
            "event": "exam_start",
            "run_id": run_id,
            "exam": args.exam,
            "timestamp": now_iso(),
        }
    )

    try:
        result = process_exam(exam_path, run_id, env, max_new_questions=args.max_new)
        trace_records.append(
            {
                "event": "exam_complete",
                "run_id": run_id,
                "result": result,
                "timestamp": now_iso(),
            }
        )
        print(f"Exam complete: {result['correct']}/{result['total_questions']} correct")
        print(f"Feedback saved to: {result['feedback_path']}")
    except Exception as e:
        trace_records.append(
            {
                "event": "exam_error",
                "run_id": run_id,
                "error": str(e),
                "timestamp": now_iso(),
            }
        )
        print(f"ERROR: {e}")
        exit(1)
    finally:
        trace_path = TRACES_DIR / "exam_runs" / f"{run_id}.trace.jsonl"
        write_jsonl(trace_path, trace_records)


if __name__ == "__main__":
    main()
