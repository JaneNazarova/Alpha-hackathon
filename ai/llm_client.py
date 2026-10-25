import csv
import hashlib
import json
import os
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("LLM_API_KEY")
BASE_URL = os.getenv("LLM_BASE_URL")
CACHE_DIR = Path("cache/llm")
LOG_PATH = Path("llm_log.csv")
LOG_HEADER = ["date", "model", "prompt_tokens", "completion_tokens", "status", "finish_reason", "note"]


class LLMConfigurationError(RuntimeError):
    """Raised when the AI provider cannot be called because settings are missing."""


def _cache_key(model, messages, max_tokens):
    raw = json.dumps({"m": model, "msg": messages, "t": max_tokens}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _log(model, usage, status, finish_reason, note=""):
    is_new = not LOG_PATH.exists()
    with LOG_PATH.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if is_new:
            w.writerow(LOG_HEADER)
        w.writerow([date.today().isoformat(), model, usage.get("prompt_tokens"),
                    usage.get("completion_tokens"), status, finish_reason, note])


def chat(model, messages, max_tokens=3000, use_cache=True, note=""):
    """Возвращает dict: content, finish_reason, usage. Успешные ответы с finish_reason=stop кэшируются."""
    if not API_KEY or not BASE_URL:
        raise LLMConfigurationError("LLM_API_KEY and LLM_BASE_URL must be configured")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{_cache_key(model, messages, max_tokens)}.json"
    if use_cache and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    r = requests.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={"model": model, "messages": messages, "max_tokens": max_tokens},
        timeout=180,
    )
    if r.status_code != 200:
        _log(model, {}, r.status_code, None, note)
        raise RuntimeError(f"API error {r.status_code}")

    data = r.json()
    choice = data["choices"][0]
    usage = data.get("usage", {})
    result = {
        "content": choice["message"].get("content") or "",
        "finish_reason": choice.get("finish_reason"),
        "usage": usage,
    }
    _log(model, usage, 200, result["finish_reason"], note)
    if result["finish_reason"] == "stop":
        path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return result
