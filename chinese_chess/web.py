from __future__ import annotations

import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Type

from .api import Application


STATIC_ROOT = Path(__file__).resolve().parent.parent / "web"


class RequestHandler(BaseHTTPRequestHandler):
    application: Application

    def do_GET(self) -> None:
        if self.path.startswith("/api/"):
            self._send_json(*self.application.handle("GET", self.path, None))
        else:
            self._serve_static()

    def do_POST(self) -> None:
        self._handle_with_body("POST")

    def do_PUT(self) -> None:
        self._handle_with_body("PUT")

    def _handle_with_body(self, method: str) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 65536:
                self._send_json(413, {"error": "request body is too large"})
                return
            raw = self.rfile.read(length)
            payload: Optional[Dict[str, Any]] = json.loads(raw) if raw else None
            if not isinstance(payload, dict):
                raise ValueError("JSON body must be an object")
        except (ValueError, json.JSONDecodeError) as error:
            self._send_json(400, {"error": str(error)})
            return
        self._send_json(*self.application.handle(method, self.path, payload))

    def _send_json(self, status: int, body: Dict[str, Any]) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def _serve_static(self) -> None:
        relative = "index.html" if self.path in ("/", "/index.html") else self.path.lstrip("/")
        path = (STATIC_ROOT / relative).resolve()
        if STATIC_ROOT.resolve() not in path.parents or not path.is_file():
            self._send_json(404, {"error": "file not found"})
            return
        content = path.read_bytes()
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type + ("; charset=utf-8" if content_type.startswith("text/") else ""))
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format_string: str, *args: object) -> None:
        return


def make_handler(application: Application) -> Type[RequestHandler]:
    class BoundRequestHandler(RequestHandler):
        pass

    BoundRequestHandler.application = application
    return BoundRequestHandler


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Chinese chess web application")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args(argv)
    application = Application()
    config = application.config.get()
    host = args.host or config.host
    port = args.port or config.port
    server = ThreadingHTTPServer((host, port), make_handler(application))
    print("Chinese chess is available at http://%s:%d" % (host, port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
