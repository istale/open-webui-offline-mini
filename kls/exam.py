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
    }

    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=60.0)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"ERROR: {e}"


def generate_answer(question_text: str, env: dict) -> str:
    prompt = f"""Answer the following question concisely:

Question: {question_text}

Provide a brief answer:"""

    return call_llm(prompt, env)


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

    response = call_llm(prompt, env)

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


def process_exam(exam_path: Path, run_id: str, env: dict) -> dict:
    exam_set_id = exam_path.name
    questions_dir = exam_path / "questions"
    answers_dir = exam_path / "answers"

    if not questions_dir.exists():
        raise ValueError(f"No questions directory found: {questions_dir}")

    question_files = list_png_files(questions_dir)
    if not question_files:
        raise ValueError(f"No question images found in: {questions_dir}")

    answer_key_path = answers_dir / "answer_key.json"
    answer_key = read_json(answer_key_path) or {}

    feedback_records = []
    results_summary = []

    for q_path in question_files:
        q_id = q_path.stem
        question_text = read_optional_txt(q_path)

        if not question_text:
            question_text = f"[Image: {q_id}]"

        answer_entry = answer_key.get(q_id, {})
        correct_answer = (
            answer_entry.get("answer", "")
            if isinstance(answer_entry, dict)
            else str(answer_entry)
        )

        student_answer = generate_answer(question_text, env)

        if correct_answer:
            feedback = grade_answer(question_text, student_answer, correct_answer, env)
        else:
            feedback = {
                "result": "unknown",
                "rationale": "No answer key available for grading",
                "gaps": [],
                "study_actions": [],
            }

        feedback_record = {
            "question_id": q_id,
            "result": feedback["result"],
            "rationale": feedback["rationale"],
            "gaps": feedback["gaps"],
            "study_actions": feedback["study_actions"],
        }
        feedback_records.append(feedback_record)

        results_summary.append(
            {
                "question_id": q_id,
                "result": feedback["result"],
            }
        )

    feedback_output = {
        "run_id": run_id,
        "exam_set_id": exam_set_id,
        "timestamp": now_iso(),
        "questions": feedback_records,
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
        result = process_exam(exam_path, run_id, env)
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
        trace_path = TRACES_DIR / "exam_runs" / f"{run_id}.jsonl"
        write_jsonl(trace_path, trace_records)


if __name__ == "__main__":
    main()
