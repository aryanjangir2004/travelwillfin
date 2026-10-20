"""Tiny save API for the Finndex editor.

Runs behind nginx, which handles the logins (HTTP basic auth) and passes the
signed-in username in X-Remote-User. Listens on localhost only.

    GET  /api/countries        -> {"user": ..., "countries": {key: row}, "meta": {key: {...}}}
    PUT  /api/countries/<key>  -> body {"score": int, "reason": str}; returns the saved row

Every save rewrites data.json atomically and keeps a timestamped backup.
Only standard-library Python, so nothing extra to install on the server.

Dev mode (local testing): python3 server/finndex_api.py --data /tmp/data.json --static site --user tester
"""
import argparse
import json
import os
import re
import shutil
import tempfile
import threading
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

MAX_REASON = 500
MAX_SCORE = 100
KEEP_BACKUPS = 200

lock = threading.Lock()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, data_path, state_dir):
        self.data_path = Path(data_path)
        self.meta_path = Path(state_dir) / "meta.json"
        self.backup_dir = Path(state_dir) / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def load(self):
        data = json.loads(self.data_path.read_text(encoding="utf-8"))
        meta = json.loads(self.meta_path.read_text(encoding="utf-8")) if self.meta_path.exists() else {}
        return data, meta

    def _write(self, path, obj):
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        os.chmod(tmp, 0o644)  # nginx serves data.json publicly
        os.replace(tmp, path)

    def save(self, key, score, reason, user):
        with lock:
            data, meta = self.load()
            if key not in data:
                raise KeyError(key)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            shutil.copy2(self.data_path, self.backup_dir / f"data-{stamp}.json")
            for old in sorted(self.backup_dir.glob("data-*.json"))[:-KEEP_BACKUPS]:
                old.unlink()
            data[key]["score"] = score
            data[key]["reason"] = reason
            meta[key] = {"by": user, "at": now()}
            self._write(self.data_path, data)
            self._write(self.meta_path, meta)
            return data[key], meta[key]


class Handler(SimpleHTTPRequestHandler):
    store = None
    dev_user = None
    static_dir = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=self.static_dir or os.devnull, **kwargs)

    # Quieter logs: method, path, status only.
    def log_request(self, code="-", size="-"):
        self.log_message('"%s %s" %s', self.command, urlparse(self.path).path, code)

    def user(self):
        return self.headers.get("X-Remote-User") or self.dev_user

    def send_json(self, status, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/countries":
            if not self.user():
                return self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "Not signed in"})
            data, meta = self.store.load()
            return self.send_json(HTTPStatus.OK, {"user": self.user(), "countries": data, "meta": meta})
        if self.static_dir and not path.startswith("/api/"):
            if path == "/data.json":  # dev: serve the store's data like nginx does
                return self.send_json(HTTPStatus.OK, self.store.load()[0])
            return super().do_GET()
        self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_PUT(self):
        m = re.fullmatch(r"/api/countries/([^/]+)", urlparse(self.path).path)
        if not m:
            return self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
        user = self.user()
        if not user:
            return self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "Not signed in"})
        # JSON-only + custom header: blocks cross-site form posts riding on a saved login.
        if not self.headers.get("Content-Type", "").startswith("application/json") or \
                self.headers.get("X-Finndex") != "1":
            return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Bad request"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 8192:
                return self.send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "Too large"})
            body = json.loads(self.rfile.read(length) or b"{}")
            score = body.get("score")
            reason = body.get("reason")
            if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= MAX_SCORE:
                return self.send_json(HTTPStatus.BAD_REQUEST, {"error": f"Score must be a whole number from 0 to {MAX_SCORE}"})
            if not isinstance(reason, str) or len(reason.strip()) > MAX_REASON:
                return self.send_json(HTTPStatus.BAD_REQUEST, {"error": f"Reason must be at most {MAX_REASON} characters"})
            row, meta = self.store.save(unquote(m.group(1)), score, reason.strip(), user)
        except KeyError:
            return self.send_json(HTTPStatus.NOT_FOUND, {"error": "Unknown country"})
        except (ValueError, json.JSONDecodeError):
            return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Bad request"})
        self.log_message("saved %s by %s", m.group(1), user)
        self.send_json(HTTPStatus.OK, {"country": row, "meta": meta})


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="/var/lib/finndex/data.json")
    p.add_argument("--state", help="folder for meta.json and backups (default: next to --data)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8090)
    p.add_argument("--static", help="dev only: also serve this folder")
    p.add_argument("--user", help="dev only: pretend this user is signed in")
    a = p.parse_args()

    Handler.store = Store(a.data, a.state or Path(a.data).parent)
    Handler.static_dir = a.static
    Handler.dev_user = a.user
    server = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f"finndex api on http://{a.host}:{a.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
