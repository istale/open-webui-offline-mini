# open-webui-offline-mini

一個「可離線部署」的極簡 Open WebUI 風格 Web App（單機部署、Python server），後端透過 **OpenAI-compatible API** 對接：
- vLLM（OpenAI API server）
- Ollama（OpenAI-compatible endpoint）

目標：用盡量少的檔案數（~3–7）提供：
- 單聊天室 + 多聊天歷史
- RAG（上傳文件 → embedding → 簡單向量檢索）
- 模型管理（列出/選擇 model；只針對 OpenAI-compatible）
- 使用者登入與權限（本機 SQLite）

> 注意：這不是 fork open-webui 的大改版；而是 **重寫最小可用版本**，upstream 僅作參考。

## 快速開始

### 1) 安裝
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) 設定（環境變數）
```bash
export APP_SECRET='change-me'
export OPENAI_BASE_URL='http://127.0.0.1:8000/v1'
export OPENAI_API_KEY='EMPTY'
# 預設模型（可在 UI 切換）
export DEFAULT_CHAT_MODEL='your-chat-model'
export DEFAULT_EMBED_MODEL='your-embed-model'
```

### 3) 啟動
```bash
uvicorn app:app --host 0.0.0.0 --port 8080
```

打開：<http://127.0.0.1:8080>

## OpenAI-compatible API 需求
- `GET /v1/models`
- `POST /v1/chat/completions`（支援 stream）
- `POST /v1/embeddings`（RAG 用）

## DB
- 預設 SQLite 檔：`./data/app.db`

## 進度
- [ ] UI：登入/登出、聊天列表、聊天視窗、上傳文件
- [ ] Backend：auth、chat、models proxy、upload、embedding、檢索
- [ ] 最小測試/自我檢查腳本
