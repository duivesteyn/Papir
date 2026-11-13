#!/usr/bin/env python3
# coding: utf-8
#
# duivesteyn // Python // papir
# https://github.com/duivesteyn/papir
#
# Local intake: a browser button or Shortcut posts a document link, Papir opens
# it for review. Off unless you run `papir serve`. Loopback only, token-gated.
#
# # bmd 2026

"""Local HTTP intake for Papir.

The browser cannot open a `papir://` URL on its own, so this listens on
127.0.0.1, checks a bearer token, and forwards the link to the app. It never
downloads or sends anything itself: the app shows the normal review step.
"""

import json
import os
import secrets
import subprocess
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from papir.papir import client_path

DEFAULT_PORT = 47821
APP_INTAKE = Path.home() / "Library" / "Application Support" / "Papir" / "intake.json"
MAX_BODY = 16 * 1024
APP_BUNDLE = "com.bmd.papir"


def token_path():
    """Kept beside client.json so PAPIR_CLIENT redirects it in tests."""
    return client_path().parent / "serve.json"


def app_token():
    """The app owns the token when it has one. Tests stay isolated via PAPIR_CLIENT."""
    if os.environ.get("PAPIR_CLIENT"):
        return ""
    try:
        return json.loads(APP_INTAKE.read_text(encoding="utf-8")).get("token", "") or ""
    except (OSError, ValueError):
        return ""


def load_token(create=True):
    token = app_token()
    if token:
        return token
    path = token_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        token = data.get("token", "")
        if token:
            return token
    except (OSError, ValueError):
        pass
    if not create:
        return ""
    token = secrets.token_hex(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 1, "token": token}, indent=2), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return token


def intake_enabled():
    """None when the app has no opinion (CLI-only), else the app's switch."""
    path = (Path.home() / "Library" / "Application Support" / "Papir" / "intake.json")
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("enabled") is True
    except (OSError, ValueError):
        return None


def validate(url):
    """Only http(s) with a host. Returns the URL or raises ValueError."""
    if not isinstance(url, str) or not url.strip():
        raise ValueError("Missing url.")
    parsed = urllib.parse.urlsplit(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http and https links can be sent.")
    if not parsed.netloc:
        raise ValueError("That link has no host.")
    return url.strip()


def describe(url):
    """A short, human line for the terminal: host and the file name."""
    parts = urllib.parse.urlsplit(url)
    name = parts.path.rsplit("/", 1)[-1]
    name = urllib.parse.unquote(name)
    if len(name) > 60:
        name = name[:57] + "…"
    return f"{parts.netloc}/{name}" if name else parts.netloc


def app_link(url, title=None):
    params = {"url": url}
    if title:
        params["title"] = title
    return "papir://intake?" + urllib.parse.urlencode(params)


def open_in_app(link):
    """Ask LaunchServices to hand the link to Papir.app."""
    methods = [["-b", APP_BUNDLE, link], [link]]
    for args in methods:
        try:
            result = subprocess.run(["open", *args], capture_output=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0:
            return True
    return False


class Handler(BaseHTTPRequestHandler):
    server_version = "PapirIntake/1"
    protocol_version = "HTTP/1.1"
    token = ""
    opener = staticmethod(open_in_app)
    quiet = False

    def log_message(self, fmt, *args):
        # Never log the body or the token; the request line is enough here.
        if not getattr(self, "quiet", False):
            sys.stderr.write("papir serve: %s\n" % (fmt % args))

    def note(self, message):
        if not getattr(self, "quiet", False):
            sys.stderr.write("papir serve: %s\n" % message)

    # -- plumbing ---------------------------------------------------------
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "authorization, content-type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _authorised(self):
        header = self.headers.get("Authorization", "")
        scheme, _, value = header.partition(" ")
        if scheme.lower() != "bearer" or not value:
            return False
        return secrets.compare_digest(value.strip(), self.token)

    # -- routes -----------------------------------------------------------
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path.split("?")[0] != "/health":
            return self._json(404, {"ok": False, "error": "Unknown path."})
        if not self._authorised():
            return self._json(401, {"ok": False, "error": "Bad or missing token."})
        self._json(200, {"ok": True, "service": "papir", "intake_enabled": intake_enabled()})

    def do_POST(self):
        if self.path.split("?")[0] != "/send":
            return self._json(404, {"ok": False, "error": "Unknown path."})
        if not self._authorised():
            return self._json(401, {"ok": False, "error": "Bad or missing token."})
        length = self.headers.get("Content-Length")
        try:
            length = int(length or 0)
        except ValueError:
            return self._json(400, {"ok": False, "error": "Bad length."})
        if length <= 0 or length > MAX_BODY:
            return self._json(413, {"ok": False, "error": "Body too large."})
        try:
            request = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self._json(400, {"ok": False, "error": "Expected JSON."})

        try:
            url = validate(request.get("url"))
        except ValueError as error:
            return self._json(400, {"ok": False, "error": str(error)})

        if intake_enabled() is False:
            return self._json(409, {"ok": False,
                                     "error": "papir:// links are off in Papir Settings, under Advanced."})

        title = request.get("title")
        title = title.strip()[:200] if isinstance(title, str) else None
        if not self.opener(app_link(url, title)):
            self.note(f"✗ could not open Papir for {describe(url)}")
            return self._json(503, {"ok": False, "error": "Papir is not installed or could not be opened."})
        self.note(f"→ Papir: {describe(url)}" + (f'  “{title}”' if title else ""))
        self._json(202, {"ok": True, "handed_to": "Papir"})


def serve(host="127.0.0.1", port=DEFAULT_PORT, quiet=False):
    token = load_token()
    handler = type("BoundHandler", (Handler,), {"token": token, "quiet": quiet})
    try:
        httpd = ThreadingHTTPServer((host, port), handler)
    except OSError as error:
        if getattr(error, "errno", None) in (48, 98):
            print(f"papir: port {port} is already in use — Papir.app is probably listening, which is fine.",
                  file=sys.stderr)
            raise SystemExit(1)
        raise
    if not quiet:
        print(f"Papir intake listening on http://{host}:{port}", file=sys.stderr)
        state = intake_enabled()
        print("papir:// links: " + {True: "on", False: "off (Settings ▸ Advanced)", None: "unknown (app not set up)"}[state], file=sys.stderr)
        print(f"Token (stored in {token_path()}):", file=sys.stderr)
        print(f"  {token}", file=sys.stderr)
        if intake_enabled() is False:
            print("Note: papir:// links are off in Papir Settings, under Advanced.", file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("", file=sys.stderr)
    finally:
        httpd.server_close()
