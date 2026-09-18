"""Local preview server for the static site + Python API functions.

Vercel runs `public/` as static assets and `api/*.py` as serverless functions.
There is no Node dev server for this project, so v0's preview (which auto-detects
an open port) has nothing to attach to. This script fills that gap for LOCAL
PREVIEW ONLY: it serves the files in `public/` and delegates `/api/analyze` and
`/api/live` to the exact same `handler` classes used in production, so the
preview behaves identically to the deployed app.

It is not used by Vercel in production (vercel.json drives that) and is safe to
ignore when deploying.

Run:  python3 scripts/dev_server.py [port]
"""
import importlib.util
import mimetypes
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC = os.path.join(ROOT, "public")
sys.path.insert(0, ROOT)


def _load(module_name, filename):
    path = os.path.join(ROOT, "api", filename)
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.handler


ANALYZE_HANDLER = _load("api_analyze", "analyze.py")
LIVE_HANDLER = _load("api_live", "live.py")

API_ROUTES = (
    ("/api/analyze", ANALYZE_HANDLER),
    ("/api/live", LIVE_HANDLER),
)


class Router(BaseHTTPRequestHandler):
    # HTTP/1.0 so each response closes its connection. The delegated API
    # handlers do not send Content-Length, so the browser relies on the
    # connection closing to know the response body has ended.
    protocol_version = "HTTP/1.0"

    def _match(self):
        path = self.path.split("?", 1)[0]
        for prefix, target in API_ROUTES:
            if path == prefix or path.startswith(prefix + "/"):
                return target
        return None

    def _delegate(self, target_cls):
        # Reuse the production handler by binding it to this live connection.
        proxy = target_cls.__new__(target_cls)
        for attr in (
            "rfile", "wfile", "headers", "command", "path", "request_version",
            "client_address", "server", "connection", "requestline",
        ):
            setattr(proxy, attr, getattr(self, attr))
        proxy.close_connection = True
        method = getattr(proxy, "do_" + self.command, None)
        if method is None:
            self.send_error(405, "Method Not Allowed")
            return
        method()

    def _serve_static(self):
        path = self.path.split("?", 1)[0]
        if path in ("", "/"):
            path = "/index.html"
        full = os.path.normpath(os.path.join(PUBLIC, path.lstrip("/")))
        if not full.startswith(PUBLIC):
            self.send_error(403, "Forbidden")
            return
        if os.path.isdir(full):
            full = os.path.join(full, "index.html")
        if not os.path.isfile(full):
            self.send_error(404, "Not Found")
            return
        with open(full, "rb") as handle:
            data = handle.read()
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        target = self._match()
        if target:
            self._delegate(target)
        else:
            self._serve_static()

    def do_POST(self):
        target = self._match()
        if target:
            self._delegate(target)
        else:
            self.send_error(404, "Not Found")

    def do_OPTIONS(self):
        target = self._match()
        if target:
            self._delegate(target)
        else:
            self.send_error(404, "Not Found")

    def log_message(self, fmt, *args):
        sys.stderr.write("[dev] %s - %s\n" % (self.command, self.path))


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("DEV_PORT", "3000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Router)
    sys.stderr.write("[dev] serving %s and /api/* on http://0.0.0.0:%d\n" % (PUBLIC, port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
