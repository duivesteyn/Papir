#!/usr/bin/env python3
"""Offline tests for the local intake receiver."""

import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from unittest import mock

from http.server import ThreadingHTTPServer

from papir import intake


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(os.environ.pop, "PAPIR_CLIENT", None)
        os.environ["PAPIR_CLIENT"] = os.path.join(self.tmp.name, "client.json")

    # -- request building -------------------------------------------------
    def start(self, opener=None):
        token = intake.load_token()
        handler = type("T", (intake.Handler,), {"token": token, "opener": staticmethod(opener or (lambda link: True))})
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        return f"http://127.0.0.1:{httpd.server_address[1]}", token

    def post(self, base, token, payload):
        data = json.dumps(payload).encode()
        request = urllib.request.Request(base + "/send", data=data, method="POST",
                                         headers={"Content-Type": "application/json",
                                                  "Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(request, timeout=5) as reply:
                return reply.status, json.loads(reply.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    # -- token ------------------------------------------------------------
    def test_token_is_created_private(self):
        token = intake.load_token()
        self.assertEqual(len(token), 64)
        path = intake.token_path()
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(intake.load_token(), token)

    def test_token_is_stable(self):
        first = intake.load_token()
        second = intake.load_token()
        self.assertEqual(first, second)

    # -- validation -------------------------------------------------------
    def test_validate_accepts_https(self):
        self.assertEqual(intake.validate("https://example.com/a.pdf"), "https://example.com/a.pdf")

    def test_validate_rejects_other_schemes(self):
        for bad in ["file:///etc/passwd", "javascript:alert(1)", "ftp://x/y", "", None, "https://"]:
            with self.assertRaises(ValueError):
                intake.validate(bad)

    def test_app_link_escapes(self):
        link = intake.app_link("https://example.com/a b.pdf?x=1&y=2", "A & B")
        self.assertTrue(link.startswith("papir://intake?"))
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(link).query)
        self.assertEqual(query["url"][0], "https://example.com/a b.pdf?x=1&y=2")
        self.assertEqual(query["title"][0], "A & B")

    # -- http -------------------------------------------------------------
    def test_health_requires_token(self):
        base, _ = self.start()
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(base + "/health", timeout=5)
        self.assertEqual(caught.exception.code, 401)

    def test_health_with_token(self):
        base, token = self.start()
        request = urllib.request.Request(base + "/health", headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(request, timeout=5) as reply:
            self.assertEqual(reply.status, 200)
            self.assertTrue(json.loads(reply.read())["ok"])

    def test_send_without_token(self):
        base, _ = self.start()
        status, body = self.post(base, "nope", {"url": "https://example.com/a.pdf"})
        self.assertEqual(status, 401)
        self.assertFalse(body["ok"])

    def test_send_forwards_to_app(self):
        seen = []
        base, token = self.start(opener=lambda link: seen.append(link) or True)
        status, body = self.post(base, token, {"url": "https://example.com/a.pdf", "title": "October"})
        self.assertEqual(status, 202)
        self.assertTrue(body["ok"])
        self.assertEqual(len(seen), 1)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(seen[0]).query)
        self.assertEqual(query["url"][0], "https://example.com/a.pdf")
        self.assertEqual(query["title"][0], "October")

    def test_send_rejects_bad_url(self):
        base, token = self.start()
        status, body = self.post(base, token, {"url": "file:///etc/passwd"})
        self.assertEqual(status, 400)
        self.assertFalse(body["ok"])

    def test_send_refuses_when_app_disabled(self):
        base, token = self.start()
        with mock.patch.object(intake, "intake_enabled", return_value=False):
            status, body = self.post(base, token, {"url": "https://example.com/a.pdf"})
        self.assertEqual(status, 409)
        self.assertIn("Settings", body["error"])

    def test_send_reports_missing_app(self):
        base, token = self.start(opener=lambda link: False)
        status, body = self.post(base, token, {"url": "https://example.com/a.pdf"})
        self.assertEqual(status, 503)
        self.assertFalse(body["ok"])


if __name__ == "__main__":
    unittest.main()
