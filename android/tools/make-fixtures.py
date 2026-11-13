#!/usr/bin/env python3
"""Regenerate the Kotlin signer test fixture from the Python implementation.

The Android port must sign byte-for-byte what the CLI signs. Rather than
trusting a hand-copied expectation, this script asks `papir/signer.py` for the
digest and writes it into `app/src/test/.../Fixtures.kt`, where `SignerTest`
compares against the Kotlin result.

    python3 android/tools/make-fixtures.py

Requires `openssl` on PATH. Changes nothing else in the repository.
"""

from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from papir import papir, signer  # noqa: E402

TOOLS = ROOT / "android/tools"
FIXTURES = TOOLS / "fixtures"
KEY = FIXTURES / "signer-test-key.pem"
OUT = ROOT / "android/app/src/test/java/com/duivesteyn/papir/core/Fixtures.kt"

DATE = "2026-01-02T03:04:05Z"
ADP_TOKEN = "AMP-test-adp-token"
PATH = "/GetUploadUrl"
METHOD = "POST"
BODY = (
    '{"ClientInfo":{"appName":"ShellExtension","appVersion":"1.1.1.253",'
    '"os":"MacOSX_10.14.6_x64","osArchitecture":"x64"},"fileSize":123456}'
)
VERIFIER = "test-verifier-1234567890abcdefghijklmnopqrstuvwxyz"
TITLE_CASES = [
    "Light_and_Wonder_LNW_Investment_Report_v1.2_2026-10-06",
    "report",
    "2026-10-06",
    "Quarterly Report 2026-03-31",
    "Design Systems v2.1",
    "budget_final_v3",
    "a b  c",
    "paper",
]


def keys(directory: Path) -> tuple[str, str]:
    """A fixed, throwaway test key keeps regeneration from churning the repo."""
    FIXTURES.mkdir(parents=True, exist_ok=True)
    if not KEY.exists():
        subprocess.run(
            ["openssl", "genrsa", "-out", str(KEY), "2048"],
            check=True,
            capture_output=True,
        )
        print(f"created {KEY.relative_to(ROOT)} (test key, safe to commit)")

    pkcs8 = directory / "pkcs8.pem"
    subprocess.run(
        ["openssl", "pkcs8", "-topk8", "-nocrypt", "-in", str(KEY), "-out", str(pkcs8)],
        check=True,
        capture_output=True,
    )
    return KEY.read_text(), pkcs8.read_text()


def kotlin_raw_string(value: str) -> str:
    assert '"""' not in value and "$" not in value
    return '"""' + value.rstrip("\n") + '"""'


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        pkcs1, pkcs8 = keys(Path(tmp))

    digest = signer.digest_header_for_request(
        pkcs1, ADP_TOKEN, METHOD, PATH, BODY, signing_date=DATE
    )
    assert digest == signer.digest_header_for_request(
        pkcs8, ADP_TOKEN, METHOD, PATH, BODY, signing_date=DATE
    ), "PKCS#1 and PKCS#8 keys must sign identically"

    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    titles = {stem: papir.clean_title(stem) for stem in TITLE_CASES}
    title_lines = "\n".join(f'        "{k}" to "{v}",' for k, v in titles.items())

    source = f'''package com.duivesteyn.papir.core

/**
 * Values produced by the Python reference implementation
 * (`papir/signer.py`, `papir/papir.py`). Do not hand-edit: regenerate with
 * `python3 android/tools/make-fixtures.py`.
 */
object Fixtures {{
    const val ADP_TOKEN = "{ADP_TOKEN}"
    const val DATE = "{DATE}"
    const val PATH = "{PATH}"
    const val METHOD = "{METHOD}"
    const val BODY = {kotlin_raw_string(BODY)}

    const val EXPECTED_DIGEST = "{digest}"

    const val VERIFIER = "{VERIFIER}"
    const val EXPECTED_CHALLENGE = "{challenge}"

    val PKCS1_KEY: String = {kotlin_raw_string(pkcs1)}
    val PKCS8_KEY: String = {kotlin_raw_string(pkcs8)}

    val TITLES: Map<String, String> = mapOf(
{title_lines}
    )
}}
'''
    OUT.write_text(source)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(source)} bytes)")


if __name__ == "__main__":
    main()
