#!/usr/bin/env python3
# coding: utf-8
#
# duivesteyn // Python // papir
# https://github.com/duivesteyn/papir
#
# Core: one function to beam a file, plus login/devices/logout helpers.
# Unofficial. Not affiliated with Amazon / Kindle.
#
# # bmd 2026

"""Papir core — papirSend() plus credential helpers."""

import base64
import json
import logging
import os
import re
import secrets
import socket
from pathlib import Path

from papir import api

SUPPORTED = {
    "pdf": "PDF", "epub": "EPUB", "doc": "DOC", "docx": "DOCX",
    "rtf": "RTF", "txt": "TXT", "htm": "HTM", "html": "HTML",
    "mobi": "MOBI", "azw": "AZW",
    "jpg": "JPEG", "jpeg": "JPEG", "gif": "GIF", "png": "PNG", "bmp": "BMP",
}

DEFAULT_CLIENT = os.path.join("~", ".config", "papir", "client.json")


def client_path(path=None):
    """Resolve credential path. Env PAPIR_CLIENT wins."""
    p = Path(os.environ.get("PAPIR_CLIENT", path or DEFAULT_CLIENT)).expanduser()
    return p


def new_verifier():
    """PKCE code verifier."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()


def new_serial():
    """Per-install random device serial: 32 upper-hex chars (like cyrgim/stk)."""
    return secrets.token_hex(16).upper()


def default_device_name():
    """Hostname as device_model, fallback 'papir'."""
    try:
        h = socket.gethostname()
        return h if h else "papir"
    except OSError:
        return "papir"


_KEEP = object()  # sentinel: leave the stored default untouched


def save_client(device_info, path=None, default_target=_KEEP, default_author=_KEEP):
    """Write client.json with mode 600. Stored defaults are preserved unless
    explicitly given (pass None to clear one)."""
    p = client_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    old = {}
    if p.exists():
        try:
            old = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            old = {}
    if default_target is _KEEP:
        default_target = old.get("default_target")
    if default_author is _KEEP:
        default_author = old.get("default_author")
    p.write_text(json.dumps(
        {"version": 1, "device_info": device_info,
         "default_target": default_target, "default_author": default_author},
        indent=2), encoding="utf-8")
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    return p


def load_client(path=None):
    """Load client.json. Raises FileNotFoundError with a hint."""
    p = client_path(path)
    if not p.exists():
        raise FileNotFoundError(f"no client at {p} — run `papir login` first")
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("version") != 1:
        raise ValueError(f"unsupported client version in {p}")
    return data["device_info"], p


def get_default_target(path=None):
    """Stored default device serial (or None = fall back to all)."""
    p = client_path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("default_target")
    except (OSError, ValueError):
        return None


def set_default_target(serial, path=None):
    """Persist the default device serial. Pass None to clear (back to all)."""
    info, _ = load_client(path)
    return save_client(info, path, default_target=serial)


def get_default_author(path=None):
    """Stored default author (or None)."""
    p = client_path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("default_author")
    except (OSError, ValueError):
        return None


def set_default_author(name, path=None):
    """Persist the default author. Pass None/'' to clear."""
    info, _ = load_client(path)
    return save_client(info, path, default_author=name or None)


def resolve_author(author, path=None):
    """Explicit flag wins, then stored default, then the Amazon account name."""
    if author:
        return author
    stored = get_default_author(path)
    if stored:
        return stored
    try:
        info, _ = load_client(path)
        return info.get("account_name") or ""
    except (FileNotFoundError, ValueError):
        return ""


def clean_title(stem):
    """Turn a filename stem into a display title.

    Light_and_Wonder_LNW_Investment_Report_v1.2_2026-10-06
    -> Light and Wonder LNW Investment Report
    """
    t = stem.replace("_", " ")
    t = re.sub(r"\s+\d{4}[-_ ]\d{2}[-_ ]\d{2}\s*$", "", t)          # trailing _2026-10-06
    t = re.sub(r"\s+v\d+(\.\d+)*\s*$", "", t, flags=re.IGNORECASE)  # trailing _v1.2
    t = re.sub(r"\s+", " ", t).strip()
    return t or stem


def resolve_title(title, file_path):
    """Explicit flag wins, else a cleaned-up filename stem."""
    if title:
        return title
    return clean_title(Path(file_path).stem)


def resolve_target(info, target, path=None):
    """Turn a --to value into a serial list. None/'default' uses the stored default, else all."""
    if target is None or target == "default":
        stored = get_default_target(path)
        target = stored or "all"
    if isinstance(target, str):
        if target == "all":
            serials = [d["deviceSerialNumber"] for d in api.get_owned_devices(info)]
            if not serials:
                raise ValueError("account has no devices — use target='library' for cloud-only")
            return serials
        if target == "library":
            return []
        return [target]
    return list(target)


def papirLogin(redirect_url=None, verifier=None, serial=None, device_name=None, path=None):
    """Complete OAuth login. If redirect_url is None, prints sign-in URL + verifier for the CLI to drive."""
    verifier = verifier or new_verifier()
    if redirect_url is None:
        return api.get_signin_url(verifier), verifier
    code = api.parse_authorization_code(redirect_url)
    token = api.token_exchange(code, verifier)
    serial = serial or new_serial()
    device_name = device_name or default_device_name()
    info = api.register_device_with_token(token, serial, device_name)
    p = save_client(info, path)
    logging.info(f"registered {device_name} ({serial}), saved to {p}")
    return info


def papirDevices(path=None):
    """List e-reader targets. Returns list of dicts."""
    info, _ = load_client(path)
    return api.get_owned_devices(info)


def papirLogout(path=None):
    """Disown server-side + delete local client.json."""
    info, p = load_client(path)
    api.logout(info)
    try:
        p.unlink()
    except OSError:
        pass


def _format_for(path, override="auto"):
    if override and override.lower() != "auto":
        return override.upper()
    ext = Path(path).suffix.lower().lstrip(".")
    if ext not in SUPPORTED:
        raise ValueError(f"unsupported type (.{ext}): {path}")
    return SUPPORTED[ext]


def papirSend(file_path, author=None, title=None, target=None, fmt="auto", archive=True, path=None,
            on_progress=None, convert=False):
    """Beam one file to your e-reader. Returns the sku Amazon assigns.

    author (optional): author tag shown on the device; falls back to the
    stored default author, then the Amazon account name.
    title (optional): falls back to the cleaned filename.
    target: None/'default' (stored default, else all), a serial string,
    a list of serials, "all", or [] / "library" for cloud-library-only.
    on_progress(sent, total): optional upload progress callback.
    convert: True = Amazon's "convert PDF to Kindle format" (forceConvert).
    False (default) keeps the native PDF.
    """
    info, _ = load_client(path)
    fp = Path(file_path).expanduser()
    if not fp.is_file():
        raise FileNotFoundError(f"not found: {file_path}")
    size = fp.stat().st_size
    if size <= 0:
        raise ValueError(f"empty file: {file_path}")
    fmt = _format_for(fp, fmt)
    author = resolve_author(author, path)
    title = resolve_title(title, fp)

    target = resolve_target(info, target, path)
    logging.info(f"uploading {fp.name} ({size} bytes, {fmt}) author={author!r} title={title!r} -> {len(target)} target(s)")

    upload_url, stk_token = api.get_upload_url(info, size)
    with open(fp, "rb") as f:
        api.upload_file(upload_url, size, f, on_progress=on_progress)
    sku = api.send_to_kindle(info, stk_token, target, author=author, title=title,
                             fmt=fmt, archive=archive, force_convert=convert)
    logging.info(f"sent sku={sku}")
    return sku


if __name__ == "__main__":
    """Localhost Testing Functionality."""
    print("papir core — see main.py for example usage")
