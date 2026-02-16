# KLS Loop v1 — SPEC

> Repo: open-webui-offline-mini（代理開發）
> Branch: feature/kls-loop-v1
> Status: draft

## 0. 目標與範圍

本分支新增一個「知識學習系統」（KLS, Knowledge Learning System）閉環：

1) 使用者上傳（其實是把 Windows 端轉檔後的資料夾上傳到 Linux）
2) 系統主動整理教材/報告，透過少量對話補齊關鍵缺口
3) 形成可檢索 + 可追溯的知識庫（結構化筆記 + 向量索引）
4) 交給「評量 chatbot」（Exam Bot）對考題資料夾進行作答與評語
5) Exam Bot 回傳「對/錯理由與知識缺口」（不可洩題）給 KLS
6) KLS 依缺口回補知識庫，形成學習/評量循環

### 非目標（v1 不做）
- 不在 Linux 端處理 PPT/PPTX 轉檔（由 Windows 端完成後再上傳）
- 不做雲端模型（全本機）
- 不把考題內容直接顯示在回饋中（不可洩題）

## 1. 名詞
- KLS：知識學習系統（本 repo 主要承載 UI + 工作流中樞）
- Exam Bot：評量 chatbot（由 nanobot 提供通用 agent 能力；分支策略 TBD）
- Knowledge Base（KB）：結構化筆記 + 向量索引 + 來源追溯

## 2. 資料夾入口（硬性契約）
見 `DATA_CONTRACT.md`。

## 3. 本機模型/後端依賴

KLS 後端只透過 OpenAI-compatible API 存取本機模型能力：
- OPENAI_BASE_URL（例如 http://127.0.0.1:8000/v1）
- 需求：/v1/models, /v1/chat/completions, /v1/embeddings

## 4. 工作流（高層狀態機）

### 4.1 Ingest（教材整理）
輸入：`domain_knowledge_materials/<deck>/slides/*.png`

步驟：
1) OCR（本機）→ 每張 slide 產出可搜尋文字（若 OCR 不可用則退化為純視覺摘要）
2) Slide 摘要：每張 slide 產出 3-8 行摘要 + 概念候選（concept candidates）
3) Chunk + Embedding：以 slide 為最小引用單位，產生 embedding index
4) 結構化 KB：產生/更新 `kb/concepts/*.md`（每個概念一檔，附來源 slide refs）

### 4.2 少量對話補齊
對話目標：以最少問題補齊高價值缺口（例如名詞對應、內部叫法、重要例外）。

輸出：KB 更新（概念定義/前提/例外/常見錯誤）。

### 4.3 評量回圈
輸入：`domain_knowledge_exams/<exam_set>/...`

流程：
1) KLS 觸發 Exam Bot（以“考題資料夾 + 不洩題規則”為上下文）
2) Exam Bot 作答 + 產生「對/錯理由」與「知識缺口清單」
3) KLS 依缺口定位到教材來源（RAG）→ 更新 KB

## 5. 不洩題（a）
詳見 `SAFETY.md`。

## 6. nanobot 合作介面（註記）
- 目前需求是「nanobot 需要提供通用 Exam Bot 能力」
- 是否為 nanobot 開分支：**TBD**（使用者直覺是不用；待介面穩定後再檢討）

## 7. 驗收
- 見 `MVP_CHECKLIST.md`
