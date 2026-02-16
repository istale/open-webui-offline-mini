# KLS Loop v1 — DEV

## 0) 分支
- `feature/kls-loop-v1`

## 1) 依賴
- 離線 Linux
- 本機 OpenAI-compatible API（由 nanobot / vLLM / Ollama 提供）

必要 endpoint：
- `GET /v1/models`
- `POST /v1/chat/completions`
- `POST /v1/embeddings`

## 2) 環境變數（延續既有）
- `OPENAI_BASE_URL`：例如 `http://127.0.0.1:8000/v1`
- `OPENAI_API_KEY`：本機可用 `EMPTY`
- `APP_SECRET`

## 3) 資料夾準備
建立資料夾：
- `domain_knowledge_materials/`
- `domain_knowledge_exams/`

資料夾格式見：`DATA_CONTRACT.md`

## 4) 開發/測試建議
- 先用既有 `scripts/selftest.sh` 確認主系統還能跑
- KLS v1 會新增新的自測腳本（待加）：
  - ingest smoke（讀一個 deck → 產出 KB 檔）
  - exam feedback smoke（讀一個 exam_set → 產出 gaps JSON）

## 5) nanobot 協作註記
- nanobot 目標是「通用 agent」；是否開分支 TBD。
- 本 repo 的 spec 會先把協作介面固定成「輸入資料夾 + JSON 回饋」。
