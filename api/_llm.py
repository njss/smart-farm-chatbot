"""Optional LLM layer: Claude through the Vercel AI Gateway (OpenAI-compatible API).

Uses only the Python standard library, so there is nothing to install.

Authentication, first match wins:
  1. AI_GATEWAY_API_KEY environment variable (create a key in the Vercel dashboard, AI Gateway tab)
  2. the OIDC token Vercel gives every deployment (x-vercel-oidc-token header / VERCEL_OIDC_TOKEN)
If neither exists, the chatbot silently uses the rule-based advisor only.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

GATEWAY_URL = os.environ.get("AI_GATEWAY_URL", "https://ai-gateway.vercel.sh/v1/chat/completions")
DEFAULT_MODEL = os.environ.get("CHAT_MODEL", "anthropic/claude-haiku-5.5")
TIMEOUT_S = float(os.environ.get("CHAT_TIMEOUT_S", "25"))

SYSTEM_PROMPT = """You are "Shamba Smart", a friendly agricultural extension assistant for smallholder farmers in Tanzania.
You advise on one farm plot using live readings from its environmental sensors.

Rules:
- Base every statement about the farm on the SENSOR READING and RULE FINDINGS provided. Never invent sensor values.
- Answer in {language}. Use simple words a farmer understands. No markdown headings, no tables.
- Keep answers short: at most 5 sentences or 5 bullet points, unless the farmer asks for more detail.
- Give one clear action first, with a quantity and a time of day when possible (for example litres per square metre).
- If the data cannot answer the question (pests, prices, seed varieties, chemicals), say so honestly and suggest asking the local extension officer (afisa ugani).
- Never recommend a specific pesticide or dose.
- If readings look impossible or old, say the sensor may need checking.
"""


def _token(request_headers=None) -> str | None:
    if os.environ.get("AI_GATEWAY_API_KEY"):
        return os.environ["AI_GATEWAY_API_KEY"]
    if request_headers is not None:
        tok = request_headers.get("x-vercel-oidc-token")
        if tok:
            return tok
    return os.environ.get("VERCEL_OIDC_TOKEN")


def available(request_headers=None) -> bool:
    return bool(_token(request_headers)) and os.environ.get("CHAT_DISABLE_LLM") != "1"


def ask(message: str, reading: dict | None, findings: list[dict], crop: str, lang: str,
        history: list[dict] | None = None, request_headers=None, model: str | None = None) -> str:
    """Return the model's answer. Raises RuntimeError on any failure (caller falls back to rules)."""
    token = _token(request_headers)
    if not token:
        raise RuntimeError("no AI Gateway credentials")

    language = "Swahili (Kiswahili)" if lang == "sw" else "English"
    context = (
        f"CROP: {crop}\n"
        f"SENSOR READING (JSON): {json.dumps(reading, ensure_ascii=False) if reading else 'none available'}\n"
        "RULE FINDINGS (from the agronomy rules, already checked):\n"
        + "\n".join(f"- [{f['level']}] {f['en']}" for f in findings)
    )
    messages = [{"role": "system", "content": SYSTEM_PROMPT.format(language=language)}]
    for turn in (history or [])[-6:]:
        if turn.get("role") in ("user", "assistant") and isinstance(turn.get("content"), str):
            messages.append({"role": turn["role"], "content": turn["content"][:2000]})
    messages.append({"role": "user", "content": f"{context}\n\nFARMER'S QUESTION: {message[:2000]}"})

    body = json.dumps({"model": model or DEFAULT_MODEL, "messages": messages,
                       "max_tokens": 400, "temperature": 0.3}).encode()
    req = urllib.request.Request(GATEWAY_URL, data=body, method="POST", headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"gateway HTTP {exc.code}: {exc.read()[:200]!r}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"gateway error: {exc}") from exc
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, AttributeError) as exc:
        raise RuntimeError(f"unexpected gateway response: {str(data)[:200]}") from exc
