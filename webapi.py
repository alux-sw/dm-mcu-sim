import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

kCorsHeaders = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


# streams: 경로 → fn(handler, query) — 응답을 직접 길게 써 내려가는 GET (영상 등)
def serve(port, routes, html_path=None, streams=None):
    class Handler(BaseHTTPRequestHandler):
        def send(self, code, payload, content_type):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            for k, v in kCorsHeaders.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(payload)

        def send_json(self, obj):
            self.send(200, json.dumps(obj).encode(), "application/json")

        def do_OPTIONS(self):
            self.send(204, b"", "text/plain")

        def do_GET(self):
            parts = urlsplit(self.path)
            stream = (streams or {}).get(parts.path)
            if stream is not None:
                stream(self, parse_qs(parts.query))
                return
            is_root = parts.path == "/"
            if is_root and html_path is not None:
                with open(html_path, "rb") as f:
                    self.send(200, f.read(), "text/html; charset=utf-8")
                return
            fn = routes.get(("GET", self.path))
            if fn is None:
                self.send(404, b"not found", "text/plain")
                return
            self.send_json(fn(None))

        def do_POST(self):
            fn = routes.get(("POST", self.path))
            if fn is None:
                self.send(404, b"not found", "text/plain")
                return
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            self.send_json(fn(body))

        def log_message(self, fmt, *args):
            pass

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
