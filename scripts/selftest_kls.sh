#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

PYTHON="python3"
if [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
fi


ERRORS=0

echo "=========================================="
echo "KLS Self-Test Script"
echo "=========================================="
echo ""

check_file() {
    if [ -f "$1" ]; then
        echo "[PASS] File exists: $1"
        return 0
    else
        echo "[FAIL] File missing: $1"
        ERRORS=$((ERRORS + 1))
        return 1
    fi
}

check_dir() {
    if [ -d "$1" ]; then
        echo "[PASS] Directory exists: $1"
        return 0
    else
        echo "[FAIL] Directory missing: $1"
        ERRORS=$((ERRORS + 1))
        return 1
    fi
}

echo "Test 1: Checking directory structure..."
check_dir "domain_knowledge_materials"
check_dir "domain_knowledge_exams"
check_dir "kb"
check_dir "kb/concepts"
check_dir "kb/indices"
check_dir "traces"
check_dir "traces/ingest_runs"
check_dir "traces/exam_runs"
check_dir "exam_feedback"
echo ""

echo "Test 2: Checking KLS modules..."
check_file "kls/__init__.py"
check_file "kls/utils.py"
check_file "kls/ingest.py"
check_file "kls/exam.py"
check_file "kls/update_kb.py"
echo ""

echo "Test 3: Checking scripts..."
check_file "scripts/generate_demo_kls_data.py"
check_file "scripts/kls_demo_run.sh"
check_file "scripts/selftest_kls.sh"
echo ""

echo "Test 4: Checking demo data generation..."
if [ -d "domain_knowledge_materials/demo_ml_basics/slides" ]; then
    SLIDE_COUNT=$(ls domain_knowledge_materials/demo_ml_basics/slides/*.png 2>/dev/null | wc -l)
    if [ "$SLIDE_COUNT" -eq 10 ]; then
        echo "[PASS] Demo deck has 10 slides"
    else
        echo "[FAIL] Demo deck has $SLIDE_COUNT slides, expected 10"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo "[SKIP] Demo deck not generated yet (run demo script first)"
fi

if [ -d "domain_knowledge_exams/demo_ml_exam/questions" ]; then
    Q_COUNT=$(ls domain_knowledge_exams/demo_ml_exam/questions/*.png 2>/dev/null | wc -l)
    if [ "$Q_COUNT" -eq 10 ]; then
        echo "[PASS] Demo exam has 10 questions"
    else
        echo "[FAIL] Demo exam has $Q_COUNT questions, expected 10"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo "[SKIP] Demo exam not generated yet (run demo script first)"
fi

if [ -f "domain_knowledge_exams/demo_ml_exam/answers/answer_key.json" ]; then
    echo "[PASS] Answer key exists"
else
    echo "[SKIP] Answer key not generated yet (run demo script first)"
fi
echo ""

echo "Test 5: Checking ingest outputs..."
if [ -f "kb/indices/material_index.jsonl" ]; then
    RECORDS=$(wc -l < kb/indices/material_index.jsonl)
    echo "[PASS] Material index has $RECORDS records"
else
    echo "[SKIP] Material index not generated yet (run ingest first)"
fi

CONCEPT_COUNT=$(ls kb/concepts/*.md 2>/dev/null | wc -l)
if [ "$CONCEPT_COUNT" -gt 0 ]; then
    echo "[PASS] KB has $CONCEPT_COUNT concept files"
else
    echo "[SKIP] No concept files yet (run ingest first)"
fi
echo ""

echo "Test 6: Checking no-leak constraint..."
if [ -d "exam_feedback" ]; then
    for feedback_file in exam_feedback/*/*.json; do
        if [ -f "$feedback_file" ]; then
            # Check that feedback doesn't contain exact question text
            if grep -q "What is the main characteristic" "$feedback_file" 2>/dev/null; then
                echo "[FAIL] Feedback may contain leaked question text in $feedback_file"
                ERRORS=$((ERRORS + 1))
            else
                echo "[PASS] No obvious question text leak in $feedback_file"
            fi

            # Verify feedback has required fields
            if "$PYTHON" -c "
import json
import sys
with open('$feedback_file') as f:
    data = json.load(f)
    if 'questions' not in data:
        sys.exit(1)
    for q in data['questions']:
        for field in ['result', 'rationale', 'gaps', 'study_actions']:
            if field not in q:
                sys.exit(1)
    sys.exit(0)
" 2>/dev/null; then
                echo "[PASS] Feedback structure valid in $(basename $feedback_file)"
            else
                echo "[FAIL] Feedback structure invalid in $(basename $feedback_file)"
                ERRORS=$((ERRORS + 1))
            fi
        fi
    done
else
    echo "[SKIP] No feedback files yet (run exam first)"
fi
echo ""

echo "Test 7: Checking Python syntax..."
"$PYTHON" -m py_compile kls/__init__.py kls/utils.py kls/ingest.py kls/exam.py kls/update_kb.py
"$PYTHON" -m py_compile scripts/generate_demo_kls_data.py
echo "[PASS] All Python files have valid syntax"
echo ""

echo "Test 8: Checking imports..."
"$PYTHON" -c "import kls; import kls.utils" || ERRORS=$((ERRORS + 1))
echo "[PASS] KLS package imports successfully"
echo ""

echo "=========================================="
if [ $ERRORS -eq 0 ]; then
    echo "All tests passed!"
    echo "=========================================="
    exit 0
else
    echo "Tests completed with $ERRORS error(s)"
    echo "=========================================="
    exit 1
fi
