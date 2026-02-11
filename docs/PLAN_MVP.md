# open-webui-offline-mini — MVP Plan (auth/chat/models proxy/upload/embeddings)

> Goal: make the project runnable end-to-end on a single machine, offline, with a minimal UI + FastAPI backend.
> Backend proxies to an OpenAI-compatible server (vLLM/Ollama) for:
> - GET /v1/models
> - POST /v1/chat/completions (stream)
> - POST /v1/embeddings

## Scope (IN)
1) **Auth**
- Local SQLite users table
- Register + login + logout
- Session via signed cookie (or JWT in httpOnly cookie) — pick one and implement consistently

2) **Chat**
- Create chat, list chats, load messages
- Send message -> server calls OpenAI-compatible `chat/completions` (stream)
- Persist user messages + assistant messages

3) **Models proxy**
- Backend endpoint to fetch models from `OPENAI_BASE_URL` and expose to UI
- UI model picker (store selection per user or per chat)

4) **Upload + RAG (minimal)**
- Upload text-like files (txt/md/pdf optional)
- Store file metadata + raw text in DB (or filesystem + DB pointer)
- Chunking + embeddings (call `OPENAI_BASE_URL/v1/embeddings`)
- Naive vector search (cosine similarity) on query embeddings
- Inject top-k chunks into chat prompt (system or user prefix)

5) **Minimal self-test script**
- A script that boots the server and runs a handful of HTTP checks (register/login/models/chat/embeddings)

## Scope (OUT)
- Multi-user admin UI
- Advanced permissions/roles
- Full Open WebUI parity
- Fancy document parsers, OCR, complex chunkers

## Existing files
- `app.py` (FastAPI backend)
- `index.html` + `style.css` (UI)
- `app.js` (frontend logic)
- `requirements.txt`

## Implementation tasks (do in this order)

### T1. Backend config + OpenAI client wrapper
- Ensure env vars are supported:
  - `APP_SECRET`
  - `OPENAI_BASE_URL`
  - `OPENAI_API_KEY`
  - `DEFAULT_CHAT_MODEL`
  - `DEFAULT_EMBED_MODEL`
- Create a small wrapper for calling OpenAI-compatible endpoints with timeouts + error propagation.

**Verify**:
- `GET /api/models` returns same list as upstream `/v1/models` (shape normalized for UI)

### T2. SQLite schema + init
Tables (minimal):
- users(id, email unique, password_hash, created_at)
- sessions(id, user_id, created_at, expires_at) OR cookie-only session if chosen
- chats(id, user_id, title, model, created_at, updated_at)
- messages(id, chat_id, role, content, created_at)
- documents(id, user_id, filename, mime, created_at)
- doc_chunks(id, document_id, chunk_index, text, embedding_json)

**Verify**:
- Fresh run creates `./data/app.db`

### T3. Auth endpoints
- `POST /api/auth/register` (email+password)
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/me` (whoami)

**Verify**:
- Register then login produces authenticated session cookie
- `GET /api/me` works only when logged in

### T4. Chat CRUD endpoints
- `GET /api/chats`
- `POST /api/chats` (create)
- `GET /api/chats/{id}` (messages)
- `POST /api/chats/{id}/messages` (send user message; server streams assistant reply)

Streaming:
- Use SSE or fetch streaming that `app.js` can consume.

**Verify**:
- Can create chat, send message, receive streamed assistant text, persist messages

### T5. Upload + embeddings + search
- `POST /api/upload` (multipart)
- Extract text (start with plain text; optionally add pdf via pypdf if already present)
- Chunk (e.g. ~800 chars with overlap)
- Call embeddings endpoint and store vectors
- `POST /api/rag/search` (query -> top-k chunks)
- In chat send, if RAG enabled and docs exist, prepend retrieved chunks

**Verify**:
- Upload a txt file
- Search returns chunks
- Chat response changes when RAG context included

### T6. UI wiring
- Login page/modal
- Chat list + chat window
- Upload button
- Model dropdown (from /api/models)

**Verify**:
- Manual smoke: login -> create chat -> send -> stream -> upload -> ask doc question

### T7. Minimal self-test script
Create `scripts/selftest.sh` (or `python scripts/selftest.py`) that:
1. Starts uvicorn (background) on a test port
2. Registers a user
3. Logs in (stores cookie)
4. Calls /api/models
5. Creates chat
6. Sends a non-stream chat (or stream but collect output)
7. Calls embeddings endpoint via our backend (or direct) to ensure connectivity
8. Stops server

**Verify**:
- `./scripts/selftest.sh` exits 0

## Acceptance criteria (definition of done)
- `uvicorn app:app --host 0.0.0.0 --port 8080` runs
- UI usable for: register/login, pick model, create chat, stream reply
- Upload a txt file -> RAG search returns results -> chat can include context
- `./scripts/selftest.sh` passes on a machine with reachable OpenAI-compatible server

## Notes
- Keep dependencies minimal; add only if required for PDF parsing.
- Prefer deterministic, small code changes; avoid refactors unrelated to MVP.
