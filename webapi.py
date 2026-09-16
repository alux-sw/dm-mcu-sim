"""JSON GET/POST 라우팅만 있는 최소 HTTP 서버"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

kCorsHeaders = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def serve(port, routes, html_path=None):
    """routes = {("GET", "/api/x"): fn(body) -> obj}. html_path 는 '/' 에 그대로 내보낸다"""

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
            is_root = self.path == "/"
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
