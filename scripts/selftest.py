#!/usr/bin/env python3
"""
Self-test script for open-webui-offline-mini MVP.

Prerequisites:
- Python dependencies installed (pip install -r requirements.txt)
- Optional: OpenAI-compatible server running at OPENAI_BASE_URL for full tests

Usage:
    python scripts/selftest.py

Environment variables:
    APP_SECRET          - JWT secret (default: test-secret)
    OPENAI_BASE_URL     - OpenAI-compatible API base URL (default: http://127.0.0.1:8000/v1)
    OPENAI_API_KEY      - API key (default: EMPTY)
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# Test configuration
TEST_PORT = 18080
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "testpassword123"

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def log(msg, level="info"):
    color = {"info": "", "ok": GREEN, "error": RED, "warn": YELLOW}.get(level, "")
    print(f"{color}{msg}{RESET}")


def http_request(path, method="GET", data=None, headers=None):
    """Make HTTP request and return (status, body)."""
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, method=method)

    if headers:
        for k, v in headers.items():
            req.add_header(k, v)

    if data and method in ("POST", "PUT", "PATCH"):
        if isinstance(data, dict):
            req.add_header("Content-Type", "application/json")
            data = json.dumps(data).encode("utf-8")
        req.data = data

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")
    except Exception as e:
        return -1, str(e)


def check(condition, msg):
    """Check condition and log result."""
    if condition:
        log(f"  ✓ {msg}", "ok")
        return True
    else:
        log(f"  ✗ {msg}", "error")
        return False


def wait_for_server(timeout=30):
    """Wait for server to be ready."""
    log("Waiting for server to start...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            status, _ = http_request("/")
            if status == 200:
                log("  ✓ Server is ready", "ok")
                return True
        except:
            pass
        time.sleep(0.5)
    log("  ✗ Server failed to start", "error")
    return False


def main():
    log("=" * 60)
    log("open-webui-offline-mini MVP Self-Test")
    log("=" * 60)

    # Set environment variables for the test
    env = os.environ.copy()
    env["APP_SECRET"] = env.get("APP_SECRET", "test-secret-for-selftest")
    env["OPENAI_BASE_URL"] = env.get("OPENAI_BASE_URL", "http://127.0.0.1:8000/v1")
    env["OPENAI_API_KEY"] = env.get("OPENAI_API_KEY", "EMPTY")
    env["DEFAULT_CHAT_MODEL"] = env.get("DEFAULT_CHAT_MODEL", "")
    env["DEFAULT_EMBED_MODEL"] = env.get("DEFAULT_EMBED_MODEL", "")

    server_process = None
    all_passed = True

    try:
        # Start server
        log("\n[1/8] Starting uvicorn server...")
        server_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(TEST_PORT),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(Path(__file__).parent.parent),
            env=env,
        )

        if not wait_for_server():
            all_passed = False
            return all_passed

        # Test 2: Register
        log("\n[2/8] Testing user registration...")
        status, body = http_request(
            "/api/register", "POST", {"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        if status == 200:
            all_passed &= check(True, f"Registered user {TEST_EMAIL}")
        elif status == 409:
            all_passed &= check(True, f"User {TEST_EMAIL} already exists (ok)")
        else:
            all_passed &= check(False, f"Registration failed: HTTP {status}, {body}")

        # Test 3: Login
        log("\n[3/8] Testing login...")
        status, body = http_request(
            "/api/login", "POST", {"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        if status == 200:
            resp = json.loads(body)
            token = resp.get("token")
            all_passed &= check(token is not None, "Received JWT token")
        else:
            log(f"  Response: {body}", "error")
            all_passed &= check(False, f"Login failed: HTTP {status}")
            token = None

        if not token:
            log("\nCannot continue without authentication", "error")
            return False

        auth_headers = {"Authorization": f"Bearer {token}"}

        # Test 4: /api/me
        log("\n[4/8] Testing /api/me...")
        status, body = http_request("/api/me", headers=auth_headers)
        if status == 200:
            resp = json.loads(body)
            all_passed &= check(
                resp.get("email") == TEST_EMAIL,
                f"Got correct email: {resp.get('email')}",
            )
            all_passed &= check(resp.get("id") is not None, "Got user id")
        else:
            all_passed &= check(False, f"/api/me failed: HTTP {status}")

        # Test 5: /api/models (requires OpenAI-compatible server)
        log("\n[5/8] Testing /api/models...")
        status, body = http_request("/api/models", headers=auth_headers)
        if status == 200:
            resp = json.loads(body)
            models = resp.get("models", [])
            all_passed &= check(
                isinstance(models, list), f"Got models list ({len(models)} models)"
            )
            log(f"    Models: {[m.get('id') for m in models[:5]]}...", "info")
        else:
            all_passed &= check(
                False,
                f"/api/models failed: HTTP {status} (OpenAI server may be unavailable)",
            )

        # Test 6: Create chat
        log("\n[6/8] Testing chat creation...")
        status, body = http_request(
            "/api/chats",
            "POST",
            {"title": "Test Chat", "model": "test-model"},
            auth_headers,
        )
        if status == 200:
            resp = json.loads(body)
            chat = resp.get("chat", {})
            chat_id = chat.get("id")
            all_passed &= check(chat_id is not None, f"Created chat with id: {chat_id}")
            all_passed &= check(chat.get("title") == "Test Chat", "Chat title correct")
            all_passed &= check(chat.get("model") == "test-model", "Chat model stored")
        else:
            all_passed &= check(False, f"Chat creation failed: HTTP {status}")
            chat_id = None

        # Test 7: List chats
        if chat_id:
            log("\n[7/8] Testing list chats...")
            status, body = http_request("/api/chats", headers=auth_headers)
            if status == 200:
                resp = json.loads(body)
                chats = resp.get("chats", [])
                all_passed &= check(
                    isinstance(chats, list), f"Got chats list ({len(chats)} chats)"
                )
                all_passed &= check(
                    any(c.get("id") == chat_id for c in chats),
                    "Created chat is in list",
                )
            else:
                all_passed &= check(False, f"List chats failed: HTTP {status}")

        # Test 8: Logout
        log("\n[8/8] Testing logout...")
        status, body = http_request("/api/auth/logout", "POST", {}, auth_headers)
        if status == 200:
            all_passed &= check(True, "Logout successful")
        else:
            all_passed &= check(False, f"Logout failed: HTTP {status}")

        # Additional: Test static files
        log("\n[Extra] Testing static files...")
        for path in ["/", "/app.js", "/style.css"]:
            status, _ = http_request(path)
            all_passed &= check(status == 200, f"GET {path} -> HTTP {status}")

    finally:
        # Cleanup
        if server_process:
            log("\nStopping server...")
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_process.kill()
            log("  ✓ Server stopped", "ok")

    # Summary
    log("\n" + "=" * 60)
    if all_passed:
        log("ALL TESTS PASSED ✓", "ok")
        log("=" * 60)
        return 0
    else:
        log("SOME TESTS FAILED ✗", "error")
        log("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
