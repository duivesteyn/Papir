#!/usr/bin/env python3
# coding: utf-8
#
# duivesteyn // Python // papir
# https://github.com/duivesteyn/papir
#
# Beam reading material to your e-reader via API, with correct Author + Title.
# Unofficial. Not affiliated with Amazon / Kindle.
#
# # bmd 2026

"""Papir RSA request signing. Stdlib only — no extra deps.

Scheme is PKCS#1 v1.5 over a BARE SHA-256 digest (no ASN.1 DigestInfo prefix).
Using a standard SHA256-with-DigestInfo signer gives an opaque 403 from Amazon.
"""

import base64
import binascii
import datetime
import hashlib


def signing_date_now():
    """UTC signing date like 2026-10-06T10:00:00Z."""
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def make_digest_data(method, path, signing_date, post_data, adp_token):
    """Join the five signed fields with newlines, as bytes."""
    return "\n".join([method, path, signing_date, post_data, adp_token]).encode("utf-8")


def _der_read_length(buf, pos):
    first = buf[pos]
    pos += 1
    if first & 0x80 == 0:
        return first, pos
    nbytes = first & 0x7F
    length = int.from_bytes(buf[pos:pos + nbytes], "big")
    return length, pos + nbytes


def _der_read_tlv(buf, pos):
    tag = buf[pos]
    pos += 1
    length, pos = _der_read_length(buf, pos)
    val = buf[pos:pos + length]
    return tag, val, pos + length


def _parse_pkcs1_integers(der):
    """Parse PKCS#1 RSAPrivateKey DER into (n, e, d)."""
    tag, seq, _ = _der_read_tlv(der, 0)
    if tag != 0x30:
        raise ValueError("not a PKCS#1 SEQUENCE")
    pos = 0
    ints = []
    while pos < len(seq):
        t, v, pos = _der_read_tlv(seq, pos)
        if t != 0x02:
            raise ValueError("expected INTEGER in private key")
        ints.append(int.from_bytes(v, "big", signed=False))
        # DER pads positive ints with a leading 0x00 when the high bit is set;
        # unsigned parse keeps the numeric value correct.
    if len(ints) < 4:
        raise ValueError("truncated PKCS#1 key")
    _, n, e, d = ints[0], ints[1], ints[2], ints[3]
    return n, e, d


def load_rsa_private_numbers(pem_text):
    """Extract (n, d) from PEM. Accepts PKCS#1 and PKCS#8. Stdlib only."""
    lines = [l.strip() for l in pem_text.strip().splitlines() if "-----" not in l]
    der = base64.b64decode("".join(lines))
    # PKCS#8 wraps PKCS#1 in an OCTET STRING: find inner SEQUENCE starting with version 0
    if "PRIVATE KEY" in pem_text and der[1:2] != b"":
        try:
            return _parse_pkcs1_integers(der)
        except ValueError:
            pass
        # walk outer: SEQUENCE { version, alg SEQ, octetString }
        _, outer, _ = _der_read_tlv(der, 0)
        pos = 0
        parts = []
        while pos < len(outer):
            t, v, pos = _der_read_tlv(outer, pos)
            parts.append((t, v))
        for t, v in parts:
            if t == 0x04:  # OCTET STRING -> inner PKCS#1
                return _parse_pkcs1_integers(v)
        raise ValueError("could not find inner PKCS#1 in PKCS#8")
    return _parse_pkcs1_integers(der)


def digest_header_for_request(pem_private_key, adp_token, method, path, post_data, signing_date=None):
    """Build X-ADP-Request-Digest value: base64(sig) + ':' + date."""
    if signing_date is None:
        signing_date = signing_date_now()
    sig_data = make_digest_data(method, path, signing_date, post_data, adp_token)
    digest = hashlib.sha256(sig_data).digest()
    n, _, d = load_rsa_private_numbers(pem_private_key)
    k = (n.bit_length() + 7) // 8  # 256 for 2048-bit keys
    # EM = 00 01 FF..FF 00 || digest  (bare digest, no DigestInfo)
    ps_len = k - 3 - len(digest)
    em = b"\x00\x01" + b"\xff" * ps_len + b"\x00" + digest
    sig_int = pow(int.from_bytes(em, "big"), d, n)
    sig_bytes = sig_int.to_bytes(k, "big")
    return base64.b64encode(sig_bytes).decode("utf-8") + ":" + signing_date


if __name__ == "__main__":
    """Localhost Testing Functionality."""
    print(signing_date_now())
