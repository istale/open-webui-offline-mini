#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "=========================================="
echo "KLS Demo Run Script"
echo "=========================================="
echo ""

echo "Step 1: Preparing Python environment..."
PYTHON="python3"
PIP="pip"

if [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
  PIP=".venv/bin/pip"
else
  echo "  WARN: .venv not found; will try system python (may fail on PEP 668)."
fi

# Best-effort install if we have a writable venv
if [ -x "$PIP" ]; then
  echo "  Installing dependencies into venv (best-effort)..."
  "$PIP" install -q -r requirements.txt || true
fi

echo "  Using PYTHON=$PYTHON"
echo ""

echo "Step 2: Generating demo data..."
"$PYTHON" scripts/generate_demo_kls_data.py
echo ""

echo "Step 3: Running ingest pipeline..."
"$PYTHON" -m kls.ingest --deck demo_ml_basics --run-id demo_ingest
echo ""

echo "Step 4: Checking ingest outputs..."
echo "  KB concepts directory:"
ls -la kb/concepts/ | head -5
echo "  Material index:"
head -3 kb/indices/material_index.jsonl
echo ""

echo "Step 5: Running exam loop..."
if [ -z "${OPENAI_BASE_URL:-}" ]; then
  echo "  SKIP: OPENAI_BASE_URL not set. (Exam loop requires local OpenAI-compatible backend)"
else
  # Best-effort health check (models endpoint)
  if command -v curl >/dev/null 2>&1; then
    curl -sS -m 2 "${OPENAI_BASE_URL%/}/models" >/dev/null 2>&1 || echo "  WARN: OPENAI_BASE_URL not reachable; exam may fail"
  fi
  timeout 180 "$PYTHON" -m kls.exam --exam demo_ml_exam --run-id demo_exam || echo "  (Exam loop failed or timed out)"
fi
echo ""

echo "Step 6: Checking exam outputs..."
if [ -d "exam_feedback/demo_ml_exam" ]; then
    echo "  Feedback files:"
    ls -la exam_feedback/demo_ml_exam/
    
    # Find the latest feedback file
    FEEDBACK_FILE=$(ls -t exam_feedback/demo_ml_exam/*.json | head -1)
    if [ -n "$FEEDBACK_FILE" ]; then
        echo "  Sample feedback (first 500 chars):"
        head -c 500 "$FEEDBACK_FILE"
        echo ""
        
        echo ""
        echo "Step 7: Updating KB from feedback..."
        "$PYTHON" -m kls.update_kb --feedback "$FEEDBACK_FILE" --run-id demo_update
        echo ""
        
        echo "Step 8: Checking updated KB..."
        echo "  Updated concepts:"
        ls -la kb/concepts/ | head -10
    fi
else
    echo "  No feedback directory found."
fi

echo ""
echo "=========================================="
echo "Demo Run Complete!"
echo "=========================================="
echo ""
echo "Output locations:"
echo "  - Demo data:     domain_knowledge_materials/demo_ml_basics/"
echo "  - Exam data:     domain_knowledge_exams/demo_ml_exam/"
echo "  - KB concepts:   kb/concepts/"
echo "  - Material index: kb/indices/material_index.jsonl"
echo "  - Traces:        traces/"
echo "  - Feedback:      exam_feedback/"
echo ""
echo "To run selftests: bash scripts/selftest_kls.sh"
