import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def get_env():
    return {
        "OPENAI_BASE_URL": os.environ.get(
            "OPENAI_BASE_URL", "http://127.0.0.1:8000/v1"
        ),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", "EMPTY"),
        "APP_SECRET": os.environ.get("APP_SECRET", "change-me"),
    }


def compute_sha256(filepath: Path) -> str:
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def write_jsonl(filepath: Path, records: list) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_jsonl(filepath: Path) -> list:
    if not filepath.exists():
        return []
    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def write_json(filepath: Path, data: Any) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_json(filepath: Path) -> Any:
    if not filepath.exists():
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_txt_path(png_path: Path) -> Path:
    return png_path.with_suffix(".txt")


def read_optional_txt(png_path: Path) -> str:
    txt_path = get_txt_path(png_path)
    if txt_path.exists():
        return txt_path.read_text(encoding="utf-8")
    return ""


def list_png_files(directory: Path) -> list:
    if not directory.exists():
        return []
    return sorted(directory.glob("*.png"))
