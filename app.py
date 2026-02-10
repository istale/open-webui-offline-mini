#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline Mini WebUI (FastAPI).

Features (minimal):
- Local auth (SQLite) with password hashing
- Chat sessions + message history (SQLite)
- File upload -> chunk -> embeddings via OpenAI-compatible API -> store vectors
- RAG retrieval (simple cosine similarity)
- Chat streaming: proxy to OpenAI-compatible /v1/chat/completions (stream)

Deployment target: offline machine (no Internet). Only needs Python + pip packages.

Env:
- APP_SECRET: used to sign tokens (simple HMAC token)
- OPENAI_BASE_URL: e.g. http://127.0.0.1:8000/v1
- OPENAI_API_KEY: e.g. EMPTY
- DEFAULT_CHAT_MODEL
- DEFAULT_EMBED_MODEL
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from passlib.context import CryptContext
from pydantic import BaseModel

APP_SECRET = os.environ.get("APP_SECRET", "dev-secret")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:8000/v1").rstrip("/")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "EMPTY")
DEFAULT_CHAT_MODEL = os.environ.get("DEFAULT_CHAT_MODEL", "")
DEFAULT_EMBED_MODEL = os.environ.get("DEFAULT_EMBED_MODEL", "")

DATA_DIR = Path(os.environ.get("DATA_DIR", "./data"))
DB_PATH = Path(os.environ.get("DB_PATH", str(DATA_DIR / "app.db")))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI(title="offline-mini-webui")


# --------------------------- DB ---------------------------

def db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = db()
    cur = conn.cursor()
    cur.executescript(
        """
        PRAGMA journal_mode=WAL;

        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          email TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL,
          created_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chats (
          id TEXT PRIMARY KEY,
          user_id INTEGER NOT NULL,
          title TEXT NOT NULL,
          created_at INTEGER NOT NULL,
          updated_at INTEGER NOT NULL,
          FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS messages (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          chat_id TEXT NOT NULL,
          role TEXT NOT NULL,
          content TEXT NOT NULL,
          created_at INTEGER NOT NULL,
          FOREIGN KEY(chat_id) REFERENCES chats(id)
        );

        CREATE TABLE IF NOT EXISTS rag_chunks (
          id TEXT PRIMARY KEY,
          user_id INTEGER NOT NULL,
          chat_id TEXT NOT NULL,
          source_name TEXT NOT NULL,
          chunk_index INTEGER NOT NULL,
          content TEXT NOT NULL,
          embedding_json TEXT NOT NULL,
          created_at INTEGER NOT NULL,
          FOREIGN KEY(user_id) REFERENCES users(id),
          FOREIGN KEY(chat_id) REFERENCES chats(id)
        );
        """
    )
    conn.commit()
    conn.close()


init_db()


# --------------------------- Auth token ---------------------------

@dataclass
class Token:
    user_id: int
    email: str
    exp: int


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("utf-8").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def sign_token(user_id: int, email: str, ttl_s: int = 7 * 24 * 3600) -> str:
    payload = {"uid": int(user_id), "email": str(email), "exp": int(time.time()) + int(ttl_s)}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(APP_SECRET.encode("utf-8"), raw, hashlib.sha256).digest()
    return _b64url(raw) + "." + _b64url(sig)


def verify_token(token: str) -> Token:
    try:
        raw_b64, sig_b64 = token.split(".", 1)
        raw = _b64url_decode(raw_b64)
        sig = _b64url_decode(sig_b64)
        expect = hmac.new(APP_SECRET.encode("utf-8"), raw, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expect):
            raise ValueError("bad signature")
        payload = json.loads(raw.decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("expired")
        return Token(user_id=int(payload["uid"]), email=str(payload["email"]), exp=int(payload["exp"]))
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


def require_user(request: Request) -> Token:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    return verify_token(auth[len("Bearer ") :].strip())


# --------------------------- Models ---------------------------

class RegisterIn(BaseModel):
    email: str
    password: str


class LoginIn(BaseModel):
    email: str
    password: str


class ChatCreateIn(BaseModel):
    title: str = ""


class StreamIn(BaseModel):
    model: str
    prompt: str
    rag_top_k: int = 5


# --------------------------- OpenAI-compatible client ---------------------------

def _openai_headers() -> Dict[str, str]:
    return {"Authorization": f"Bearer {OPENAI_API_KEY}"}


def openai_list_models() -> List[Dict[str, Any]]:
    r = requests.get(f"{OPENAI_BASE_URL}/models", headers=_openai_headers(), timeout=15)
    r.raise_for_status()
    return r.json().get("data", [])


def openai_embeddings(model: str, texts: List[str]) -> List[List[float]]:
    r = requests.post(
        f"{OPENAI_BASE_URL}/embeddings",
        headers={"Content-Type": "application/json", **_openai_headers()},
        json={"model": model, "input": texts},
        timeout=60,
    )
    r.raise_for_status()
    data = r.json().get("data", [])
    # preserve order by index
    data = sorted(data, key=lambda x: x.get("index", 0))
    return [d["embedding"] for d in data]


# --------------------------- Utils: RAG ---------------------------

def chunk_text(text: str, max_chars: int = 1200, overlap: int = 150) -> List[str]:
    text = text.replace("\r\n", "\n")
    if not text.strip():
        return []
    chunks = []
    i = 0
    while i < len(text):
        j = min(len(text), i + max_chars)
        chunks.append(text[i:j])
        if j >= len(text):
            break
        i = max(0, j - overlap)
    return chunks


def cosine(a: List[float], b: List[float]) -> float:
    # no numpy dependency
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / ((na ** 0.5) * (nb ** 0.5))


def rag_retrieve(user_id: int, chat_id: str, query: str, top_k: int, embed_model: str) -> List[Dict[str, Any]]:
    if not embed_model:
        return []
    qvec = openai_embeddings(embed_model, [query])[0]
    conn = db()
    rows = conn.execute(
        "SELECT id, source_name, chunk_index, content, embedding_json FROM rag_chunks WHERE user_id=? AND chat_id=?",
        (user_id, chat_id),
    ).fetchall()
    conn.close()

    scored = []
    for r in rows:
        try:
            vec = json.loads(r["embedding_json"])
            scored.append((cosine(qvec, vec), dict(r)))
        except Exception:
            continue
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for s, rr in scored[: max(1, int(top_k))]:
        out.append({"score": float(s), "source": rr["source_name"], "chunk_index": rr["chunk_index"], "content": rr["content"]})
    return out


# --------------------------- Static ---------------------------

ROOT = Path(__file__).resolve().parent


@app.get("/", response_class=HTMLResponse)
def root() -> Any:
    return FileResponse(ROOT / "index.html")


@app.get("/app.js")
def app_js() -> Any:
    return FileResponse(ROOT / "app.js")


@app.get("/style.css")
def style_css() -> Any:
    return FileResponse(ROOT / "style.css")


# --------------------------- Auth endpoints ---------------------------

@app.post("/api/register")
def register(inp: RegisterIn) -> Any:
    email = inp.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(400, "Invalid email")
    if len(inp.password) < 6:
        raise HTTPException(400, "Password too short")

    ph = pwd_context.hash(inp.password)
    conn = db()
    try:
        conn.execute(
            "INSERT INTO users(email,password_hash,created_at) VALUES (?,?,?)",
            (email, ph, int(time.time())),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(409, "User already exists")
    finally:
        conn.close()
    return {"ok": True}


@app.post("/api/login")
def login(inp: LoginIn) -> Any:
    email = inp.email.strip().lower()
    conn = db()
    row = conn.execute("SELECT id,email,password_hash FROM users WHERE email=?", (email,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(401, "Bad credentials")
    if not pwd_context.verify(inp.password, row["password_hash"]):
        raise HTTPException(401, "Bad credentials")
    token = sign_token(int(row["id"]), str(row["email"]))
    return {"token": token}


@app.get("/api/me")
def me(t: Token = Depends(require_user)) -> Any:
    return {"id": t.user_id, "email": t.email, "exp": t.exp}


# --------------------------- Models endpoint ---------------------------

@app.get("/api/models")
def models(t: Token = Depends(require_user)) -> Any:
    data = openai_list_models()
    ids = [m.get("id") for m in data if m.get("id")]
    return {
        "models": [{"id": mid} for mid in ids],
        "default_chat_model": DEFAULT_CHAT_MODEL or (ids[0] if ids else ""),
        "default_embed_model": DEFAULT_EMBED_MODEL or "",
    }


# --------------------------- Chat endpoints ---------------------------

def _chat_ensure_owned(chat_id: str, user_id: int) -> sqlite3.Row:
    conn = db()
    row = conn.execute("SELECT * FROM chats WHERE id=? AND user_id=?", (chat_id, user_id)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Chat not found")
    return row


@app.get("/api/chats")
def list_chats(t: Token = Depends(require_user)) -> Any:
    conn = db()
    rows = conn.execute(
        "SELECT id,title,created_at,updated_at FROM chats WHERE user_id=? ORDER BY updated_at DESC",
        (t.user_id,),
    ).fetchall()
    conn.close()
    return {"chats": [dict(r) for r in rows]}


@app.post("/api/chats")
def create_chat(inp: ChatCreateIn, t: Token = Depends(require_user)) -> Any:
    chat_id = "C" + secrets.token_hex(8)
    now = int(time.time())
    title = (inp.title or "").strip()
    conn = db()
    conn.execute(
        "INSERT INTO chats(id,user_id,title,created_at,updated_at) VALUES (?,?,?,?,?)",
        (chat_id, t.user_id, title, now, now),
    )
    conn.commit()
    conn.close()
    return {"chat": {"id": chat_id, "title": title, "created_at": now, "updated_at": now}}


@app.get("/api/chats/{chat_id}/messages")
def list_messages(chat_id: str, t: Token = Depends(require_user)) -> Any:
    _chat_ensure_owned(chat_id, t.user_id)
    conn = db()
    rows = conn.execute(
        "SELECT role,content,created_at FROM messages WHERE chat_id=? ORDER BY id ASC",
        (chat_id,),
    ).fetchall()
    conn.close()
    return {"messages": [dict(r) for r in rows]}


def _store_message(chat_id: str, role: str, content: str) -> None:
    conn = db()
    conn.execute(
        "INSERT INTO messages(chat_id,role,content,created_at) VALUES (?,?,?,?)",
        (chat_id, role, content, int(time.time())),
    )
    conn.execute("UPDATE chats SET updated_at=? WHERE id=?", (int(time.time()), chat_id))
    conn.commit()
    conn.close()


@app.post("/api/upload")
async def upload(
    t: Token = Depends(require_user),
    file: UploadFile = File(...),
    chat_id: str = Form(...),
    top_k: int = Form(5),
) -> Any:
    _chat_ensure_owned(chat_id, t.user_id)

    raw = await file.read()
    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception:
        raise HTTPException(400, "Unable to decode file as UTF-8")

    chunks = chunk_text(text)
    if not chunks:
        return {"ok": True, "chunks": 0}

    embed_model = DEFAULT_EMBED_MODEL
    if not embed_model:
        raise HTTPException(400, "DEFAULT_EMBED_MODEL not set (needed for RAG)")

    vecs = openai_embeddings(embed_model, chunks)

    conn = db()
    now = int(time.time())
    source = file.filename or "upload"
    for i, (ch, v) in enumerate(zip(chunks, vecs)):
        rid = "R" + secrets.token_hex(10)
        conn.execute(
            "INSERT INTO rag_chunks(id,user_id,chat_id,source_name,chunk_index,content,embedding_json,created_at) VALUES (?,?,?,?,?,?,?,?)",
            (rid, t.user_id, chat_id, source, i, ch, json.dumps(v), now),
        )
    conn.commit()
    conn.close()
    return {"ok": True, "chunks": len(chunks)}


@app.post("/api/chats/{chat_id}/stream")
def stream_chat(chat_id: str, inp: StreamIn, t: Token = Depends(require_user)) -> Any:
    _chat_ensure_owned(chat_id, t.user_id)

    model = inp.model or DEFAULT_CHAT_MODEL
    if not model:
        raise HTTPException(400, "No model selected")

    prompt = (inp.prompt or "").strip()
    if not prompt:
        raise HTTPException(400, "Empty prompt")

    # store user message first
    _store_message(chat_id, "user", prompt)

    # RAG context (optional)
    rag_ctx = ""
    if inp.rag_top_k and DEFAULT_EMBED_MODEL:
        hits = rag_retrieve(t.user_id, chat_id, prompt, inp.rag_top_k, DEFAULT_EMBED_MODEL)
        if hits:
            parts = ["[RAG Context] 以下為檢索到的片段："]
            for h in hits:
                parts.append(f"- ({h['score']:.3f}) {h['source']}#{h['chunk_index']}: {h['content']}")
            rag_ctx = "\n".join(parts)

    # build messages from history (simple)
    conn = db()
    rows = conn.execute(
        "SELECT role,content FROM messages WHERE chat_id=? ORDER BY id ASC LIMIT 200",
        (chat_id,),
    ).fetchall()
    conn.close()

    msgs = []
    if rag_ctx:
        msgs.append({"role": "system", "content": rag_ctx})
    for r in rows:
        msgs.append({"role": r["role"], "content": r["content"]})

    def gen() -> Iterable[bytes]:
        # proxy streaming from OpenAI-compatible
        payload = {
            "model": model,
            "messages": msgs,
            "stream": True,
            "temperature": 0.2,
        }

        try:
            with requests.post(
                f"{OPENAI_BASE_URL}/chat/completions",
                headers={"Content-Type": "application/json", **_openai_headers()},
                data=json.dumps(payload),
                stream=True,
                timeout=300,
            ) as r:
                r.raise_for_status()

                acc = ""
                for line in r.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    if not line.startswith("data:"):
                        continue
                    data = line[len("data:") :].strip()
                    if data == "[DONE]":
                        break
                    try:
                        ev = json.loads(data)
                        delta = ev.get("choices", [{}])[0].get("delta", {}).get("content")
                        if delta:
                            acc += delta
                            out = json.dumps({"delta": delta}, ensure_ascii=False)
                            yield ("data: " + out + "\n\n").encode("utf-8")
                    except Exception:
                        continue

                # store assistant
                _store_message(chat_id, "assistant", acc)
                yield b"data: [DONE]\n\n"
        except Exception as e:
            err = json.dumps({"error": str(e)}, ensure_ascii=False)
            yield ("data: " + err + "\n\n").encode("utf-8")

    return StreamingResponse(gen(), media_type="text/event-stream")
