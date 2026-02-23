# Commit 7acb4f2 - MVP auth/chat/RAG + selftest 詳細說明

## 基本資訊

| 項目 | 內容 |
|------|------|
| **Commit** | `7acb4f21098bf0201845140c3c3d6a6e25190901` |
| **日期** | 2026-02-11 00:55:38 UTC |
| **作者** | istale <iscarryon@gmail.com> |
| **訊息** | feat: MVP auth/chat/RAG + selftest |

## 變更統計

| 檔案 | 新增 | 刪除 | 變更 |
|------|------|------|------|
| `.gitignore` | +17 | - | 新檔案 |
| `app.py` | +125 | -21 | 修改 |
| `docs/PLAN_MVP.md` | +138 | - | 新檔案 |
| `requirements.txt` | +4 | - | 修改 |
| `scripts/selftest.py` | +271 | - | 新檔案 |
| `scripts/selftest.sh` | +16 | - | 新檔案 |
| **總計** | **+550** | **-21** | **6 files** |

---

## 主要功能

這個 commit 實現了 MVP 的三個核心功能：

### 1. Auth（認證系統）

#### 新增端點

| 端點 | 方法 | 功能 |
|------|------|------|
| `/api/register` | POST | 使用者註冊 |
| `/api/login` | POST | 使用者登入 |
| `/api/auth/logout` | POST | 使用者登出 |
| `/api/me` | GET | 取得當前用戶資訊 |

#### 密碼處理

```python
def _hash_password(password: str) -> str:
    # bcrypt 有 72-byte 限制；超過則截斷
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    return pwd_context.hash(password_bytes)


def _verify_password(password: str, hash: str) -> bool:
    # 同樣處理 bcrypt 72-byte 限制
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    return pwd_context.verify(password_bytes, hash)
```

#### JWT Token 機制

```python
@dataclass
class Token:
    user_id: int
    email: str
    exp: int


def sign_token(user_id: int, email: str, ttl_s: int = 7 * 24 * 3600) -> str:
    payload = {
        "uid": int(user_id),
        "email": str(email),
        "exp": int(time.time()) + int(ttl_s)
    }
    raw = json.dumps(payload, ...).encode("utf-8")
    sig = hmac.new(APP_SECRET.encode("utf-8"), raw, hashlib.sha256).digest()
    return _b64url(raw) + "." + _b64url(sig)


def verify_token(token: str) -> Token:
    # 解析並驗證 JWT
    ...
```

#### SQLite Schema

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE chats (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    model TEXT,  -- 新增：儲存對話使用的模型
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
```

---

### 2. Chat（聊天功能）

#### 端點

| 端點 | 方法 | 功能 |
|------|------|------|
| `/api/chats` | GET | 列出所有對話 |
| `/api/chats` | POST | 建立新對話 |
| `/api/chats/{chat_id}/messages` | GET | 取得對話訊息 |
| `/api/chats/{chat_id}/stream` | POST | 傳送訊息並串流回應 |

#### 建立對話

```python
@app.post("/api/chats")
def create_chat(inp: ChatCreateIn, t: Token = Depends(require_user)) -> Any:
    chat_id = "C" + secrets.token_hex(8)
    now = int(time.time())
    title = (inp.title or "").strip()
    model = (inp.model or "").strip()  # 新增：儲存模型
    
    conn = db()
    conn.execute(
        "INSERT INTO chats(id,user_id,title,model,created_at,updated_at) VALUES (?,?,?,?,?,?)",
        (chat_id, t.user_id, title, model, now, now),
    )
    conn.commit()
    conn.close()
    
    return {"chat": {"id": chat_id, "title": title, "model": model, ...}}
```

#### 串流回應

```python
@app.post("/api/chats/{chat_id}/stream")
def stream_chat(chat_id: str, inp: StreamIn, t: Token = Depends(require_user)) -> Any:
    # 1. 取得 RAG context（可選）
    if inp.rag_top_k and DEFAULT_EMBED_MODEL:
        hits = rag_retrieve(t.user_id, prompt, inp.rag_top_k, DEFAULT_EMBED_MODEL)
        # 加入 RAG context 到 prompt
    
    # 2. 建立訊息歷史
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    # ... 加入歷史訊息 ...
    messages.append({"role": "user", "content": prompt})
    
    # 3. 串流呼叫 OpenAI-compatible API
    r = httpx.post(
        f"{OPENAI_BASE_URL}/chat/completions",
        json={"model": ..., "messages": messages, "stream": True},
        headers=_openai_headers(),
        timeout=120.0
    )
    
    # 4. 逐步回傳 SSE
    for line in r.iter_lines():
        if line.startswith("data: "):
            data = line[6:]
            if data == "[DONE]":
                break
            # 解析並回傳 delta
            yield f"data: {json.dumps({'delta': delta})}\n\n"
```

---

### 3. RAG（檢索增強生成）

#### 端點

| 端點 | 方法 | 功能 |
|------|------|------|
| `/api/upload` | POST | 上傳檔案並產生 embeddings |
| `/api/rag/search` | POST | 搜尋 RAG chunks |

#### 上傳流程

```python
@app.post("/api/upload")
async def upload(file: UploadFile, t: Token = Depends(require_user)) -> Any:
    # 1. 讀取檔案內容
    content = await file.read()
    
    # 2. 文字 chunking
    chunks = chunk_text(text, max_chars=1200, overlap=150)
    
    # 3. 產生 embeddings
    embeddings = openai_embeddings(DEFAULT_EMBED_MODEL, chunks)
    
    # 4. 存入資料庫
    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        conn.execute(
            "INSERT INTO rag_chunks(user_id,chat_id,source_name,chunk_index,content,embedding_json) VALUES (?,?,?,?,?,?)",
            (t.user_id, chat_id, filename, i, chunk, json.dumps(emb))
        )
    
    return {"ok": True, "chunks": len(chunks)}
```

#### RAG 搜尋

```python
class RAGSearchIn(BaseModel):
    query: str
    chat_id: str
    top_k: int = 5


@app.post("/api/rag/search")
def rag_search(inp: RAGSearchIn, t: Token = Depends(require_user)) -> Any:
    _chat_ensure_owned(inp.chat_id, t.user_id)
    
    # 1. 產生 query embedding
    qvec = openai_embeddings(DEFAULT_EMBED_MODEL, [inp.query])[0]
    
    # 2. 取得用戶所有 chunks（改為 user-level 共享）
    rows = conn.execute(
        "SELECT ... FROM rag_chunks WHERE user_id=?",
        (t.user_id,)
    ).fetchall()
    
    # 3. Cosine similarity 計算
    scored = []
    for row in rows:
        chunk_emb = json.loads(row["embedding_json"])
        score = cosine(qvec, chunk_emb)
        scored.append((score, row))
    
    # 4. 回傳 top-k
    scored.sort(key=lambda x: x[0], reverse=True)
    return {"results": [h for s, h in scored[:inp.top_k]]}
```

#### RAG 整合到 Chat

```python
# 在 stream_chat 中
if inp.rag_top_k and DEFAULT_EMBED_MODEL:
    hits = rag_retrieve(t.user_id, prompt, inp.rag_top_k, DEFAULT_EMBED_MODEL)
    if hits:
        parts = ["[RAG Context] 以下為檢索到的片段："]
        for h in hits:
            parts.append(f"- ({h['score']:.3f}) {h['source']}#{h['chunk_index']}: {h['content']}")
        rag_ctx = "\n".join(parts)
```

---

### 4. Models Proxy（模型代理）

```python
@app.get("/api/models")
def models(t: Token = Depends(require_user)) -> Any:
    # 代理到上游 OpenAI-compatible server
    data = openai_list_models()
    return data
```

---

### 5. Self-Test（自我測試）

#### scripts/selftest.py (271 行)

完整的自動化測試腳本，測試項目：

| 測試 | 項目 |
|------|------|
| [1/8] | 啟動 uvicorn server |
| [2/8] | 使用者註冊 (`/api/register`) |
| [3/8] | 使用者登入 (`/api/login`) |
| [4/8] | 取得用戶資訊 (`/api/me`) |
| [5/8] | 取得模型列表 (`/api/models`) |
| [6/8] | 建立對話 (`/api/chats`) |
| [7/8] | 列出對話 (`/api/chats`) |
| [8/8] | 登出 (`/api/auth/logout`) |
| [Extra] | 靜態檔案 (`/`, `/app.js`, `/style.css`) |

#### 使用方式

```bash
# 方式 1：直接執行
python scripts/selftest.py

# 方式 2：使用 wrapper
bash scripts/selftest.sh

# 方式 3：使用 venv
.venv/bin/python scripts/selftest.py
```

---

## 新的依賴套件

```txt
# 新增
passlib==1.7.4      # 密碼雜湊
bcrypt==4.0.1       # bcrypt 後端
httpx==0.27.2       # HTTP client（用於串流）
```

---

## API 總覽

```
Auth:
  POST /api/register        # 註冊
  POST /api/login           # 登入
  POST /api/auth/logout     # 登出
  GET  /api/me              # 取得當前用戶

Models:
  GET  /api/models          # 取得可用模型列表

Chat:
  GET  /api/chats                           # 列出對話
  POST /api/chats                           # 建立對話
  GET  /api/chats/{chat_id}/messages        # 取得訊息
  POST /api/chats/{chat_id}/stream          # 傳送訊息（串流）

RAG:
  POST /api/upload              # 上傳檔案
  POST /api/rag/search          # 搜尋 chunks
```

---

## 環境變數

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `APP_SECRET` | `dev-secret` | JWT 簽章密鑰 |
| `OPENAI_BASE_URL` | `http://127.0.0.1:8000/v1` | OpenAI-compatible API |
| `OPENAI_API_KEY` | `EMPTY` | API Key |
| `DEFAULT_CHAT_MODEL` | - | 預設聊天模型 |
| `DEFAULT_EMBED_MODEL` | - | 預設 embedding 模型 |

---

## 總結

這個 commit 實現了 **MVP 的核心功能**：

1. ✅ **Auth** - 註冊/登入/登出 + JWT token
2. ✅ **Chat** - 對話 CRUD + 串流回應
3. ✅ **RAG** - 檔案上傳 + embeddings + 向量搜尋
4. ✅ **Models Proxy** - 代理上游模型列表
5. ✅ **Self-Test** - 完整自動化測試

目標是讓專案可以在**單機離線環境**下運行，後端對接 OpenAI-compatible server（vLLM/Ollama）。
