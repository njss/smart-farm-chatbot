"""Vercel Python Function: POST /api/chat

Request JSON:
    {"message": "Should I irrigate today?", "lang": "en" | "sw", "crop": "maize",
     "reading": {...latest telemetry...}, "history": [{"role": "user", "content": "..."}, ...]}

Response JSON:
    {"reply": "...", "mode": "llm" | "rules", "model": "...", "findings": [...], "note": "..."}

GET /api/chat returns a small health object, used by the page to show which mode is active.
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _advisor  # noqa: E402
import _llm  # noqa: E402

MAX_BODY = 64 * 1024


def answer(payload: dict, request_headers=None) -> dict:
    message = str(payload.get("message") or "").strip()
    lang = "sw" if payload.get("lang") == "sw" else "en"
    crop = payload.get("crop") if payload.get("crop") in _advisor.CROPS else "maize"
    reading = payload.get("reading") if isinstance(payload.get("reading"), dict) else None
    history = payload.get("history") if isinstance(payload.get("history"), list) else []

    findings = _advisor.assess(reading, crop)
    result = {"findings": findings, "crop": crop, "lang": lang}

    if message and _llm.available(request_headers):
        try:
            result.update(reply=_llm.ask(message, reading, findings, crop, lang, history, request_headers),
                          mode="llm", model=_llm.DEFAULT_MODEL)
            return result
        except RuntimeError as exc:
            result["note"] = f"LLM unavailable, used rules instead ({exc})"[:300]

    result.update(reply=_advisor.rules_reply(findings, lang, message), mode="rules", model=None)
    return result


class handler(BaseHTTPRequestHandler):
    def _send(self, status: int, obj: dict) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send(200, {"ok": True, "llm": _llm.available(self.headers),
                         "model": _llm.DEFAULT_MODEL if _llm.available(self.headers) else None,
                         "crops": list(_advisor.CROPS)})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            return self._send(400, {"error": "send a JSON body under 64 KB"})
        try:
            payload = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            return self._send(400, {"error": "invalid JSON"})
        if not isinstance(payload, dict):
            return self._send(400, {"error": "JSON object expected"})
        self._send(200, answer(payload, self.headers))
