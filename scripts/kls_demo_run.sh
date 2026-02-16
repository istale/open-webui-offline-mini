#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "=========================================="
echo "KLS Demo Run Script"
echo "=========================================="
echo ""

echo "Step 1: Installing dependencies..."
pip install -q -r requirements.txt
echo "  Dependencies installed."
echo ""

echo "Step 2: Generating demo data..."
python3 scripts/generate_demo_kls_data.py
echo ""

echo "Step 3: Running ingest pipeline..."
python3 -m kls.ingest --deck demo_ml_basics --run-id demo_ingest
echo ""

echo "Step 4: Checking ingest outputs..."
echo "  KB concepts directory:"
ls -la kb/concepts/ | head -5
echo "  Material index:"
head -3 kb/indices/material_index.jsonl
echo ""

echo "Step 5: Running exam loop..."
python3 -m kls.exam --exam demo_ml_exam --run-id demo_exam || echo "  (Exam loop may need OPENAI_BASE_URL configured)"
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
        python3 -m kls.update_kb --feedback "$FEEDBACK_FILE" --run-id demo_update
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
