# KLS Loop v1 — MVP CHECKLIST

## MVP 目標
在離線 Linux 上跑通：
1) ingest 一個教材 deck（PNG slides）
2) 產出可追溯的 KB（concept files + embedding index）
3) ingest 一個考題 exam_set（PNG questions）
4) Exam Bot 回傳不洩題的 gaps/rationale
5) KLS 依 gaps 更新 KB（閉環一次）

## 驗收條件
- [x] `domain_knowledge_materials/<deck>/slides/*.png` 可被偵測
- [x] 產生 `kb/concepts/*.md` 且每個 concept 有來源引用 `<deck_id>/slide_####`
- [x] embeddings index 生成成功（格式先簡單，後續可換 sqlite）
- [x] `domain_knowledge_exams/<exam_set>/questions/*.png` 可被偵測
- [x] Exam Bot 回饋不含題幹/選項/數字（符合 SAFETY a）
- [x] traces 記錄 ingest/exam run（可統計）

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run full demo (generates data + runs pipeline)
```bash
bash scripts/kls_demo_run.sh
```

This script:
- Generates 10 demo slides + 10 demo questions
- Runs ingest pipeline
- Runs exam loop (requires OPENAI_BASE_URL for LLM calls)
- Updates KB from exam feedback
- Prints output locations

### 3. Run self-tests
```bash
bash scripts/selftest_kls.sh
```

Tests include:
- Directory structure validation
- File existence checks
- Demo data count validation (10 slides, 10 questions)
- No-leak constraint verification (feedback must not contain exact question text)
- Feedback JSON structure validation
- Python syntax checks

### 4. Manual module usage

Generate demo data only:
```bash
python3 scripts/generate_demo_kls_data.py
```

Run ingest only:
```bash
python3 -m kls.ingest --deck demo_ml_basics --run-id my_run
```

Run exam only:
```bash
export OPENAI_BASE_URL=http://127.0.0.1:8000/v1
python3 -m kls.exam --exam demo_ml_exam --run-id my_exam
```

Update KB from feedback:
```bash
python3 -m kls.update_kb --feedback exam_feedback/demo_ml_exam/<run_id>.json --run-id update_1
```

## Output Locations

After running demo:
- Demo deck: `domain_knowledge_materials/demo_ml_basics/`
- Demo exam: `domain_knowledge_exams/demo_ml_exam/`
- KB concepts: `kb/concepts/*.md`
- Material index: `kb/indices/material_index.jsonl`
- Ingest traces: `traces/ingest_runs/*.jsonl`
- Exam traces: `traces/exam_runs/*.jsonl`
- Exam feedback: `exam_feedback/<exam_set>/<run_id>.json`

## 先行假資料
- deck: 10 張 slides (demo_ml_basics)
- exam_set: 10 題 questions (demo_ml_exam)

## Not in MVP
- UI 完整化（先能跑通流程）
- 進階概念圖譜/依賴圖
- 多使用者/權限細節
