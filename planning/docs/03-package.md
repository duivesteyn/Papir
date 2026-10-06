> Early package design retained for context. Some proposed flags/features are
> not implemented; current CLI help and source are authoritative.

# 03 — `papir` Package Design (duivesteyn style)

Match your existing repos (`bmdOilPriceFetch`, `piOilPriceDisplay`): flat layout,
header comments, `main.py` example, `test.py`, `setup.py`, screenshot, changelog.

## Repo layout (real repo, not this plan folder)

```
papir/
  README.md
  LICENSE                    # MIT
  setup.py                   # setuptools, like bmdOilPriceFetch (keep pyproject.toml minimal shim later)
  requirements.txt           # requests only at first; stdlib otherwise
  main.py                    # example usage, copy-paste runnable
  test.py                    # smoke test: login fixture → devices → 28-byte send
  papir/
    __init__.py              # from papir.papir import papirSend
    papir.py                 # core single function + DeviceInfo dataclass
    api.py                   # token_exchange, register, get_upload_url, upload_file, send_to_kindle, devices, logout
    signer.py                # ADP RSA bare-digest signer (vendored, no `rsa` dep if possible)
    cli.py                   # argparse: login/devices/send/logout/doctor
  _screenshots/
    cli-send.png
    mac-app.png (later)
```

## Header style (copy yours)

```python
#!/usr/bin/env python3
# coding: utf-8
#
# duivesteyn // Python // papir
# https://github.com/duivesteyn/papir
#
# Beam reading material to your e-reader via API, with correct Author + Title.
#
# # bmd 2026
```

## Public API (v1 — keep tiny like `bmdPriceFetch()`)

```python
from papir import papirSend

sku = papirSend(
    "report.pdf",                 # path
    author="deCapital",           # → DocumentMetadata.author
    title="Imperial Investment Case",
    target="all",                 # serial | "all" | [...] | [] (library-only)
)
```

Plus thin wrappers for power users: `papirLogin()`, `papirDevices()`, `papirLogout()`.
`Client` object pattern from `stkclient` is fine internally, but export function-first
facade so README example is 5 lines.

## CLI (v1) — binary is `papir`

```
papir login [--client ~/.config/papir/client.json --force]
papir devices [--client ...]                 # SERIAL: Name
papir send FILE --author A --title T [--format auto] [--to SERIAL|all|library] [--no-archive]
papir document.pdf --title "Design Systems" --author "deCapital"   # shorthand: papir <file> == papir send <file>
papir logout
papir doctor                                 # auth? devices? 28-byte probe send? versions?
```

- `--format auto` = uppercased suffix; validate against supported set.
- `--to library` = `targetDevices: []`.
- Credential default: `~/.config/papir/client.json`, mode 600. Env override `PAPIR_CLIENT`.
- Truncate author/title like the old app (log a warning when truncating); exact limits TBD by probe (see roadmap).
- Exit codes: 0 ok, 1 Amazon error (print `sku`/message), 2 usage error.

## Deps (deliberately boring)

- `requests` only (matches your `bmdOilPriceFetch` which uses `requests`).
- RSA signing: prefer stdlib (`hashlib` + `pow()` manual PKCS#1 v1.5 bare pad) to avoid `rsa`/`pyasn1` deps.
  Fallback: vendor the 10-line pad from `stkclient/signer.py:54-60`.
- XML: stdlib `xml.etree`. No `defusedxml` required for this fixed schema (still cap parse size).

## Config / state

- No QSettings/plist. One JSON credential file: `{version:1, device_info:{...}}`.
- Per-send: no local DB needed for v1 (old `stk.db` metrics were telemetry, not required).
  Optional later: `~/.config/papir/history.jsonl` for dedup (your `send_to_kindle.py` 24h guard was app-specific; keep CLI stateless, document `--force` pattern instead).

## Testing

- `test.py`: unit (signer vector vs known-good digest, truncation, format map) + live opt-in (`PAPIR_LIVE=1` does real 28-byte send to library).
- CI: `python -m py_compile`, `pip install .`, `papir --help`, `papir doctor --offline`.

## README skeleton (your format)

`Example Usage` (main.py 5-liner) → `Example Output Data` (sku JSON) → `Changelog` (v0.1/v0.2/...) → `Notes for uploading to pypi` → `Credits (bmd + stkclient lineage)`.
