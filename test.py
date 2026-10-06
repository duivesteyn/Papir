#!/usr/bin/env python3
# coding: utf-8
#
# duivesteyn // Python // papir
# https://github.com/duivesteyn/papir
#
# Smoke tests: offline always, live only with PAPIR_LIVE=1.
#

import base64
import os
import sys

from papir import signer
from papir.pick import interpret_numbered_input
from papir.progress import SendBar, human_size
from papir.papir import (
    _format_for,
    clean_title,
    get_default_author,
    get_default_target,
    new_serial,
    resolve_author,
    resolve_target,
    resolve_title,
    save_client,
    set_default_author,
)


def test_format_map():
    assert _format_for("a.pdf") == "PDF"
    assert _format_for("a.EPUB") == "EPUB"
    assert _format_for("a.jpg") == "JPEG"
    try:
        _format_for("a.zip")
        raise AssertionError("should have raised for .zip")
    except ValueError:
        pass
    print("format map OK")


def test_serial():
    s1, s2 = new_serial(), new_serial()
    assert len(s1) == 32 and s1 == s1.upper()
    assert s1 != s2
    print(f"serial OK ({s1[:8]}…)")


def test_signer_bare_digest():
    """Signer must produce a 2048-bit RSA sig over bare SHA-256, verifiable by hand."""
    # Generate a throwaway key with openssl (present on macOS) — no extra pip deps.
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        key = os.path.join(d, "k.pem")
        subprocess.run(["openssl", "genrsa", "-out", key, "2048"],
                       check=True, capture_output=True)
        pem = open(key).read()
    n, _, dd = signer.load_rsa_private_numbers(pem)
    n, e, _d = signer.load_rsa_private_numbers(pem)
    assert n.bit_length() in (2047, 2048)
    hdr = signer.digest_header_for_request(pem, "ADP", "POST", "/SendToKindle", "{}", "2026-01-01T00:00:00Z")
    sig_b64, date = hdr.split(":", 1)  # date itself contains colons
    assert date == "2026-01-01T00:00:00Z"
    sig = base64.b64decode(sig_b64)
    assert len(sig) == (n.bit_length() + 7) // 8
    # verify: decrypt and check EM structure 00 01 FF..FF 00 || sha256
    import hashlib
    m = pow(int.from_bytes(sig, "big"), e, n)
    em = m.to_bytes((n.bit_length() + 7) // 8, "big")
    assert em[:2] == b"\x00\x01" and em[-33:-32] == b"\x00"
    expect = hashlib.sha256(b"POST\n/SendToKindle\n2026-01-01T00:00:00Z\n{}\nADP").digest()
    assert em[-32:] == expect, "digest mismatch — not a bare SHA-256 signature"
    print("signer bare-digest structure OK")


def test_picker_input():
    assert interpret_numbered_input("1", 3) == ("index", 0)
    assert interpret_numbered_input("3", 3) == ("index", 2)
    assert interpret_numbered_input("4", 3) == ("all",)      # trailing 'All devices'
    assert interpret_numbered_input("9", 3) == ("invalid",)
    assert interpret_numbered_input("", 3) == ("cancel",)
    assert interpret_numbered_input("q", 3) == ("cancel",)
    assert interpret_numbered_input("G093UV07444301RP", 3) == ("serial", "G093UV07444301RP")
    print("picker input OK")


def test_progress():
    import io
    assert human_size(512) == "512 B"
    assert human_size(1_600_000) == "1.5 MB"
    out = io.StringIO()
    seen = []
    bar = SendBar('"Demo"', 1_000, out=out)
    bar(500, 1_000)
    bar(1_000, 1_000)
    text = out.getvalue()
    assert "\U0001F4E4 Sending" in text and "\u2705 Uploaded" in text
    # on a tty the full 100% frame must render BEFORE the Uploaded line
    class FakeTty(io.StringIO):
        def isatty(self):
            return True
    tty_out = FakeTty()
    bar2 = SendBar('"Demo"', 1_000, out=tty_out)
    bar2(999, 1_000)
    bar2(1_000, 1_000)
    tty_text = tty_out.getvalue()
    assert "100%" in tty_text, "100% frame never rendered"
    assert tty_text.index("100%") < tty_text.index("\u2705 Uploaded")
    # reader wrapper counts bytes and forwards them untouched
    from papir.api import _ProgressReader
    raw = io.BytesIO(b"x" * 10_000)
    r = _ProgressReader(raw, 10_000, lambda s, t: seen.append((s, t)))
    assert len(r) == 10_000
    assert r.read(4096) == b"x" * 4096 and seen[-1] == (4096, 10_000)
    assert r.read() == b"x" * 5904 and seen[-1] == (10_000, 10_000)
    print("progress OK")


def test_send_body_stays_pdf():
    from papir.api import build_send_body
    body = build_send_body("tok", ["AAA"], author="deCapital", title="Report", fmt="PDF")
    # the backend converts when it sees outputFormat=MOBI (stkclient's invention —
    # the official app never sends outputFormat/deliveryMechanism at all)
    assert "outputFormat" not in body and "deliveryMechanism" not in body
    assert body["forceConvert"] is False
    assert body["DocumentMetadata"] == {
        "author": "deCapital", "crc32": 0, "inputFormat": "PDF", "title": "Report"}
    assert body["stkToken"] == "tok" and body["targetDevices"] == ["AAA"]
    assert build_send_body("t", [], author="a", title="t", fmt="PDF", force_convert=True)["forceConvert"] is True
    print("send body (native PDF) OK")


def test_title_and_author():
    assert clean_title("Light_and_Wonder_LNW_Investment_Report_v1.2_2026-10-06") == \
        "Light and Wonder LNW Investment Report"
    assert clean_title("Design Systems") == "Design Systems"
    assert clean_title("notes") == "notes"
    assert resolve_title(None, "report_v2.pdf") == "report"
    assert resolve_title(None, "my_notes.pdf") == "my notes"
    assert resolve_title("Given", "whatever_v9.pdf") == "Given"

    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        p = str(Path(d) / "client.json")
        info = {"device_private_key": "x", "adp_token": "y", "account_name": "Benjamin"}
        save_client(info, p)
        assert get_default_author(p) is None
        assert resolve_author(None, p) == "Benjamin"   # account fallback
        assert resolve_author("X", p) == "X"           # explicit wins
        set_default_author("deCapital", p)
        assert resolve_author(None, p) == "deCapital"  # stored wins over account
        set_default_author(None, p)
        assert get_default_author(p) is None           # cleared
        # clearing the author must not clobber the stored device default
        save_client(info, p, default_target="AAA")
        set_default_author("Z", p)
        assert get_default_target(p) == "AAA"
    print("title + author defaults OK")


def test_default_target():
    import json
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        p = str(Path(d) / "client.json")
        info = {"device_private_key": "x", "adp_token": "y"}
        save_client(info, p)                       # no default yet
        assert get_default_target(p) is None
        save_client(info, p, default_target="ABC123")
        assert get_default_target(p) == "ABC123"
        # resolve uses the stored default without touching the network
        assert resolve_target(info, None, p) == ["ABC123"]
        assert resolve_target(info, "default", p) == ["ABC123"]
        assert resolve_target(info, "library", p) == []
        assert resolve_target(info, "ZZZ", p) == ["ZZZ"]
        # re-saving without a default preserves the stored one
        save_client(info, p)
        assert get_default_target(p) == "ABC123"
    print("default target OK")


def test_live():
    if os.environ.get("PAPIR_LIVE") != "1":
        print("live skipped (PAPIR_LIVE!=1)")
        return
    from papir.papir import papirDevices
    devs = papirDevices()
    print(f"live devices OK ({len(devs)} found)")


if __name__ == "__main__":
    test_format_map()
    test_serial()
    test_picker_input()
    test_progress()
    test_send_body_stays_pdf()
    test_title_and_author()
    test_default_target()
    try:
        test_signer_bare_digest()
    except Exception as e:
        print(f"signer test FAILED: {e}", file=sys.stderr)
        raise SystemExit(1)
    test_live()
    print("all offline tests passed")
