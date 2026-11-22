#!/usr/bin/env python3
"""Run the chatbot locally without the Vercel CLI.

    python dev_server.py            # http://localhost:8000
    AI_GATEWAY_API_KEY=... python dev_server.py   # with Claude answers

Serves the static page and the same /api/chat handler that Vercel runs.
"""

import os
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "api"))

import chat  # noqa: E402


class DevHandler(chat.handler, SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] == "/api/chat":
            return chat.handler.do_GET(self)
        return SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        if self.path.split("?")[0] == "/api/chat":
            return chat.handler.do_POST(self)
        self.send_error(404)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) > 1 else 8000))
    server = ThreadingHTTPServer(("0.0.0.0", port), partial(DevHandler, directory=ROOT))
    print(f"Smart farm chatbot on http://localhost:{port}  (LLM: {'on' if chat._llm.available() else 'off, rules only'})")
    server.serve_forever()
