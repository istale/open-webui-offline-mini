# 代理開發 (open-webui-offline-mini) - Git 歷史與程式碼改動概要

## 專案簡介
**代理開發** (open-webui-offline-mini) 是一個離線部署的 Open WebUI 風格 Web App，使用 FastAPI + SQLite，後端透過 OpenAI-compatible API 對接 vLLM/Ollama。

本文檔總結了 **istale** 貢獻的所有 commit 和程式碼改動。

---

## Commit 歷史 (由新到舊)

### 1. `7c485d2` - feat(kls): force wrong answer for verification (Feb 17, 03:03)
**功能**：允許強制指定錯誤答案進行 KB 更新驗證

```python
# 新增環境變數 KLS_FORCE_WRONG_QID
force_wrong_qid = os.environ.get("KLS_FORCE_WRONG_QID", "").strip()
if force_wrong_qid and force_wrong_qid == q_id:
    student_answer = "A" if correct_answer != "A" else "B"
```

---

### 2. `0142ce9` - fix(kls): make feedback cumulative from checkpoint (Feb 17, 01:46)
**功能**：Checkpoint 紀錄合併，使回饋具有累積性

**改動**：
- 加載現有的 checkpoint 紀錄
- 新問題 + 已處理問題合併去重

```python
# Load existing checkpoint records so feedback can be cumulative.
prior_by_qid: dict[str, dict] = {}
# ... load checkpoint ...
combined = dict(prior_by_qid)
for rec in feedback_records:
    combined[rec.get("question_id")] = rec
```

---

### 3. `04c3a44` - fix(kls): separate checkpoint vs trace files (Feb 17, 01:45)
**功能**：分離 checkpoint 和 trace 檔案，避免覆蓋

```bash
checkpoint_path = TRACES_DIR / "exam_runs" / f"{run_id}.checkpoint.jsonl"
trace_path = TRACES_DIR / "exam_runs" / f"{run_id}.trace.jsonl"
```

---

### 4. `76269f2` - fix(kls): batch exam loop with --max-new (Feb 16, 16:47)
**功能**：讓 exam loop 可分批處理 (每次 2 題)

```python
# 新增參數 --max-new
parser.add_argument(
    "--max-new",
    type=int,
    default=None,
    help="Process at most N not-yet-done questions this run (for batching/resume).",
)

# 處理 N 題後停止
if max_new_questions is not None and processed_new >= max_new_questions:
    break
```

**使用方式**：
```bash
# 分 5 批處理，每批 2 題
for i in 1 2 3 4 5; do
  timeout 600 python -m kls.exam --exam demo_ml_exam --run-id demo_exam --max-new 2
done
```

---

### 5. `2be336e` - fix(kls): checkpoint exam + reduce grading calls (Feb 16, 14:35)
**功能**：Checkpoint 考試 + 減少 LLM 評分呼叫

**改動**：
- 延長 demo timeout 從 180s → 1800s (本地模型慢)
- 加入 checkpoint 機制
- 減少 grading calls：

```python
# 快速評分：直接比對答案
if correct_answer:
    # Fast grading: match answer key
    result = "correct" if ca_u in sa_u else "incorrect"
else:
    # Only use LLM grading when not correct
    feedback = grade_answer(...)
```

---

### 6. `f8e0c5a` - fix(kls): do not read PNG as text (Feb 16, 14:34)
**功能**：修正 PNG 圖檔不當讀為文字

```python
# Prefer sidecar .txt for question text; do NOT try to read the PNG bytes as text.
question_text = read_optional_txt(q_path.with_suffix(".txt"))

if not question_text:
    question_text = f"[Image-only question: {q_id}]"
```

---

### 7. `b606d45` - fix(kls): make exam loop resumable (Feb 16, 10:46)
**功能**：Exam loop 支援中斷/恢復

**主要改動**：

1. **增加 retry 機制**：
```python
def call_llm_with_retry(prompt: str, env: dict, attempts=3) -> str:
    """Retry wrapper for slow local backends."""
    last = ""
    for i in range(attempts):
        last = call_llm(prompt, env)
        if not (isinstance(last, str) and last.startswith("ERROR:")):
            return last
    return last
```

2. **延長 timeout**：60s → 180s (本地模型慢)

3. **Checkpoint 機制**：
```python
checkpoint_path = TRACES_DIR / "exam_runs" / f"{run_id}.jsonl"
# Skip already processed questions
done = set()
if checkpoint_path.exists():
    for line in checkpoint_path.read_text().splitlines():
        rec = json.loads(line)
        if rec.get("question_id"):
            done.add(rec["question_id"])
```

4. **Per-question checkpoint**：
```python
# Checkpoint per-question for resumability
with checkpoint_path.open("a", encoding="utf-8") as f:
    f.write(json.dumps(feedback_record, ensure_ascii=False) + "\n")
```

---

### 8. `76aecb9` - chore(kls): make demo/selftest use venv (Feb 16, 08:59)
**功能**：讓 demo/selftest 使用 venv，避免系統 Python 問題

```bash
PYTHON="python3"
PIP="pip"

if [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
  PIP=".venv/bin/pip"
fi

# Best-effort install if we have a writable venv
"$PIP" install -q -r requirements.txt || true

# Skip exam when OPENAI_BASE_URL unset
if [ -z "${OPENAI_BASE_URL:-}" ]; then
  echo "  SKIP: OPENAI_BASE_URL not set."
else
  timeout 180 "$PYTHON" -m kls.exam ...
fi
```

---

### 9. `0e602f3` - feat(kls): add ingest+exam loop MVP (Feb 16, 07:45)
**功能**：新增完整的 KLS (Knowledge Learning System) MVP

**新增檔案**：
```
kls/__init__.py           # Package init
kls/exam.py               # Exam loop with grading
kls/ingest.py             # Ingest pipeline (slides → concepts)
kls/update_kb.py          # Update KB from feedback
kls/utils.py              # Utility functions

scripts/generate_demo_kls_data.py  # Generate demo data
scripts/kls_demo_run.sh            # Run full pipeline
scripts/selftest_kls.sh            # Self-test suite

docs/kls/MVP_CHECKLIST.md          # MVP checklist
docs/kls/SPEC.md                   # Specification
docs/kls/DATA_CONTRACT.md          # Data contract
docs/kls/SAFETY.md                 # Safety guidelines
docs/kls/DEV.md                    # Developer guide
```

**主要功能**：
1. **Ingest Pipeline**： slides → concepts → embeddings
2. **Exam Loop**： questions + grading + feedback
3. **KB Update**：根據 feedback 更新知識庫

---

### 10. `d54a4c9` - docs(kls): add spec + safety + dev docs (Feb 16, 06:13)
**功能**：新增 KLS 相關文檔

**新增檔案**：
- `docs/kls/SPEC.md` - Specification (69 lines)
- `docs/kls/DATA_CONTRACT.md` - Data contract (77 lines)
- `docs/kls/SAFETY.md` - Safety guidelines (24 lines)
- `docs/kls/DEV.md` - Developer guide (35 lines)

---

### 11. `7acb4f2` - feat: MVP auth/chat/RAG + selftest (Feb 11, 00:55)
**功能**：新增 MVP 功能 + 自動測試

**改動**：
- `.gitignore` - 新增 17 行
- `app.py` - 增加 125 行 (主要功能)
- `docs/PLAN_MVP.md` - 新增 138 行
- `requirements.txt` - 修改依賴
- `scripts/selftest.py` - 新增 271 行
- `scripts/selftest.sh` - 新增 16 行

**功能**：
1. **Auth**：SQLite users + login/logout
2. **Chat**：OpenAI-compatible /v1/chat/completions
3. **RAG**：Upload + embeddings + vector search

---

### 12. `531f82f` - Initial offline mini webui skeleton (Feb 10, 20:33)
**功能**：初始版本

**新增檔案**：
```
README.md        # 52 lines
app.js           # 310 lines (frontend)
app.py           # 530 lines (FastAPI backend)
index.html       # 94 lines
requirements.txt # 6 lines
style.css        # 34 lines (frontend)
```

**功能**：
- FastAPI backend
- OpenAI-compatible API
- SQLite database
- Minimal UI

---

## 完整 Commit 總表

| # | Commit | Date | 功能 |
|---|--------|------|------|
| 1 | `7c485d2` | Feb 17, 03:03 | force wrong answer for KLS verification |
| 2 | `0142ce9` | Feb 17, 01:46 | cumulative feedback from checkpoint |
| 3 | `04c3a44` | Feb 17, 01:45 | separate checkpoint vs trace files |
| 4 | `76269f2` | Feb 16, 16:47 | batch exam loop with --max-new |
| 5 | `2be336e` | Feb 16, 14:35 | checkpoint + reduce grading calls |
| 6 | `f8e0c5a` | Feb 16, 14:34 | do not read PNG as text |
| 7 | `b606d45` | Feb 16, 10:46 | resumable exam loop |
| 8 | `76aecb9` | Feb 16, 08:59 | use venv for demo/selftest |
| 9 | `0e602f3` | Feb 16, 07:45 | add KLS ingest+exam MVP |
| 10 | `d54a4c9` | Feb 16, 06:13 | add KLS docs |
| 11 | `7acb4f2` | Feb 11, 00:55 | MVP auth/chat/RAG + selftest |
| 12 | `531f82f` | Feb 10, 20:33 | initial skeleton |

---

## 程式碼統計

| 類型 | 檔案數 | 行數 |
|------|--------|------|
| Python (kls/) | 5 | ~800+ |
| Scripts | 3 | ~450+ |
| Docs (kls/) | 6 | ~380+ |
| Frontend | 2 | ~440+ |
| Backend (app.py) | 1 | ~650+ |

**總計**：約 **2700+ 行**

---

## 標題 (istale 的貢獻重點)

### 1. KLS (Knowledge Learning System)
- Ingest pipeline：slides → concepts → embeddings
- Exam loop：questions + grading + feedback
- KB update：根據 feedback 更新知識庫

### 2. Resumability (中斷/恢復)
- Checkpoint 機制
- Batch processing (--max-new)
- Cumulative feedback

### 3. Robustness (強健性)
- Retry mechanism for slow local models
- Timeout adjustments (60s → 180s)
- PNG file handling fix

### 4. Developer Experience
- Virtual environment support
- Self-test suite
- Demo scripts

---

## 相關檔案結構

```
open-webui-offline-mini/
├── app.py                    # FastAPI backend (initial)
├── app.js                    # Frontend
├── index.html                # HTML
├── style.css                 # CSS
├── requirements.txt          # Python dependencies
├── README.md                 # Project readme
│
├── kls/                      # Knowledge Learning System
│   ├── __init__.py           # Package init
│   ├── exam.py               # Exam loop + grading
│   ├── ingest.py             # Ingest pipeline
│   ├── update_kb.py          # KB update from feedback
│   └── utils.py              # Utility functions
│
├── scripts/
│   ├── kls_demo_run.sh       # Run full pipeline
│   ├── selftest_kls.sh       # Self-test suite
│   └── generate_demo_kls_data.py  # Generate demo data
│
├── docs/
│   └── kls/                  # KLS documentation
│       ├── SPEC.md           # Specification
│       ├── DATA_CONTRACT.md  # Data contract
│       ├── SAFETY.md         # Safety guidelines
│       ├── DEV.md            # Developer guide
│       └── MVP_CHECKLIST.md  # MVP checklist
│
├── domain_knowledge_materials/  # Slide decks
├── domain_knowledge_exams/      # Exam sets
├── kb/                          # Knowledge base
│   ├── concepts/                # Concept markdown files
│   └── indices/                 # Embeddings index
├── traces/                      # Ingest/exam run traces
│   └── exam_runs/
└── exam_feedback/               # Exam feedback records
```

---

## 功能发展历程

```
531f82f (Initial)
    ↓
7acb4f2 (MVP auth/chat/RAG + selftest)
    ↓
d54a4c9 (KLS docs)
    ↓
0e602f3 (KLS MVP: ingest + exam loop)
    ↓
76aecb9 (venv support)
    ↓
b606d45 (resumable exam loop + retry)
    ↓
f8e0c5a (PNG fix)
    ↓
2be336e (checkpoint + reduce grading)
    ↓
76269f2 (batch exam loop --max-new)
    ↓
04c3a44 (separate checkpoint vs trace)
    ↓
0142ce9 (cumulative feedback)
    ↓
7c485d2 (force wrong answer for verification)
```

---

## 總結

istale 的貢獻集中在 **KLS (Knowledge Learning System)** 功能，包括：

1. ✅ 完整的 Ingest pipeline (slides → concepts)
2. ✅ Exam loop with grading
3. ✅ KB update from feedback
4. ✅ Resumability (checkpoint + batch processing)
5. ✅ Robustness (retry, timeout, PNG fix)
6. ✅ Developer experience (venv, self-test, demo)

所有功能都圍繞著 **"本地化 + 開源"** 的目標，避免依賴外部 API。
