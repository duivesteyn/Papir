#!/usr/bin/env python3
# coding: utf-8
#
# duivesteyn // Python // papir
# https://github.com/duivesteyn/papir
#
# CLI: papir login | devices | send | logout | doctor
#
# # bmd 2026

"""Papir command line interface."""

import argparse
import json
import os
import sys

# readline raises the terminal's 1024-char paste limit — without this,
# pasting the ~1500-char Amazon redirect URL truncates mid-code and login
# silently hangs/fails. (Same fix as stkclient.)
try:
    import readline  # noqa: F401
except ImportError:
    pass

from papir import api
from papir import pick
from papir import progress
from papir.papir import (
    client_path,
    get_default_author,
    get_default_target,
    load_client,
    new_serial,
    new_verifier,
    papirDevices,
    papirLogout,
    papirLogin,
    papirSend,
    resolve_author,
    resolve_target,
    resolve_title,
    save_client,
    set_default_author,
    set_default_target,
)


def pick_default_device(devices, path):
    """Interactive picker. Returns serial, 'ALL' (send to all), or None (cancelled)."""
    labels = [f"{d.get('deviceName')} ({d.get('deviceSerialNumber')})" for d in devices]
    labels.append("All devices")
    hint = "arrows+j/k+Enter" if pick._can_arrow() else "number/serial+q"
    res = pick.choose(f"Default Kindle [{hint}]:", labels)
    if res is None:
        return None
    if res == pick.ALL:
        set_default_target(None, path)
        return "ALL"
    if isinstance(res, str):  # serial pasted into the numbered fallback
        if not any(d.get("deviceSerialNumber") == res for d in devices):
            print(f"Warning: {res} not in device list — storing anyway.", file=sys.stderr)
        set_default_target(res, path)
        return res
    serial = devices[res]["deviceSerialNumber"]
    set_default_target(serial, path)
    return serial


def hyperlink(url, text):
    """Wrap url in an OSC 8 hyperlink when stdout is a tty, else plain text."""
    if sys.stdout.isatty():
        return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"
    return f"{text}: {url}"


def cmd_login(args):
    p = client_path(args.client)
    if p.exists() and not args.force:
        print(f"{p} already exists (use --force to overwrite)", file=sys.stderr)
        raise SystemExit(1)
    verifier = args.verifier or new_verifier()
    if args.code and not args.url:
        # bare-code fast path: no browser round-trip needed in this invocation
        # (verifier MUST be the one printed by the earlier `papir login` run —
        # pass it back via --verifier, else the token exchange will fail)
        redirect = args.code
    elif args.url:
        redirect = args.url
    else:
        signin = api.get_signin_url(verifier)
        print(hyperlink(signin, "Sign in with Amazon (click to open)"))
        print(signin)
        print(f"\n[verifier for this run — save it if your paste gets cut off:]\n{verifier}\n")
        print("Sign in in your browser, then paste the final URL you land on.")
        print("Tip: if the paste truncates, just paste the code value of")
        print("openid.oa2.authorization_code instead (or re-run with --url / --code).")
        try:
            redirect = input("Redirect URL (or bare code): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.", file=sys.stderr)
            raise SystemExit(1)
        if not redirect:
            # piped stdin (pbpaste / cat file) arrives as empty input() on some
            # terminals — fall back to reading all of stdin
            if not sys.stdin.isatty():
                redirect = sys.stdin.read().strip()
    try:
        info = papirLogin(redirect, verifier, device_name=args.name, path=args.client)
    except api.APIError as e:
        print(f"\nAmazon rejected the login: {e}", file=sys.stderr)
        print("The code may have expired (single-use) — run `papir login` fresh.", file=sys.stderr)
        raise SystemExit(1)
    except ValueError as e:
        print(f"\nLogin failed: {e}", file=sys.stderr)
        print("The pasted URL was probably truncated (macOS cuts pastes ~1024 chars", file=sys.stderr)
        print("without readline). Look for openid.oa2.authorization_code=... in the", file=sys.stderr)
        print("browser address bar and re-run as:", file=sys.stderr)
        print(f"  papir login --code THE_CODE --verifier {verifier}", file=sys.stderr)
        raise SystemExit(1)
    print(f"Registered as {info.get('device_name')} — saved to {p}")
    # setup step: default author
    account = info.get("account_name") or ""
    try:
        default_author = input(f"Default author [{account}]: ").strip() or account
    except (EOFError, KeyboardInterrupt):
        print()
        default_author = account
    if default_author:
        set_default_author(default_author, args.client)
        print(f'Default author: "{default_author}". (Override per-send with --author.)')
    # setup step: pick the default Kindle to always send to
    try:
        devices = papirDevices(args.client)
    except Exception as e:  # noqa: BLE001 — device list flaked 503 upstream; don't fail login
        print(f"\nCould not list devices ({e}) — default stays 'all'.", file=sys.stderr)
        print("Run `papir set-default` later to pick one.", file=sys.stderr)
        return
    if not devices:
        print("\nNo devices found — default stays 'all'.")
        return
    print("\nWhich Kindle should papir send to by default?")
    serial = pick_default_device(devices, args.client)
    if serial is None:
        print("No default set — will send to all devices. (Change with `papir set-default`.)")
    elif serial == "ALL":
        print("Default: all devices. (Change anytime with `papir set-default`.)")
    else:
        name = next((d.get("deviceName") for d in devices if d.get("deviceSerialNumber") == serial), serial)
        print(f"Default: {name}. (`papir send` uses it; override with --to, change with `papir set-default`.)")


def cmd_devices(args):
    default = get_default_target(args.client)
    devices = papirDevices(args.client)
    if getattr(args, "json", False):
        print(json.dumps({"default_target": default, "devices": [
            {"serial": d.get("deviceSerialNumber"), "name": d.get("deviceName")}
            for d in devices
        ]}))
        return
    for d in devices:
        mark = "  * default" if d.get("deviceSerialNumber") == default else ""
        print(f"{d.get('deviceSerialNumber')}: {d.get('deviceName')}{mark}")


def cmd_set_default(args):
    if args.author is not None:
        if args.author:
            set_default_author(args.author, args.client)
            print(f'Default author: "{args.author}".')
        else:
            set_default_author(None, args.client)
            print("Default author cleared.")
        if not args.serial:
            return
    devices = papirDevices(args.client)
    if not devices:
        print("No devices found.", file=sys.stderr)
        raise SystemExit(1)
    if args.serial:
        serial = args.serial
        if serial != "all" and not any(d.get("deviceSerialNumber") == serial for d in devices):
            print(f"Warning: {serial} not in device list — storing anyway.", file=sys.stderr)
        set_default_target(None if serial == "all" else serial, args.client)
        print(f"Default: {'all devices' if serial == 'all' else serial}.")
        return
    print("Which Kindle should papir send to by default?")
    serial = pick_default_device(devices, args.client)
    if serial is None:
        print("Unchanged.")
    elif serial == "ALL":
        print("Default: all devices.")
    else:
        print(f"Default: {serial}.")


def cmd_send(args):
    # `papir <file>` shorthand arrives here with target default None
    author = resolve_author(args.author, args.client)
    title = resolve_title(args.title, args.file)
    if not args.author or not args.title:
        print(f'Title:  "{title}"\nAuthor: "{author}"', file=sys.stderr)
    expanded = os.path.expanduser(args.file)
    if not os.path.isfile(expanded):
        raise FileNotFoundError(f"not found: {args.file}")
    size = os.path.getsize(expanded)
    label = f'"{title}"' + (f" by {author}" if author else "")
    bar = progress.SendBar(label, size)
    sku = papirSend(
        args.file,
        author=author,
        title=title,
        target=args.to,
        fmt=args.format,
        archive=not args.no_archive,
        path=args.client,
        on_progress=bar,
        convert=args.convert,
    )
    print(f"\u2705 Sent {label}.", file=sys.stderr)
    print(sku)


def cmd_logout(args):
    papirLogout(args.client)
    print("Signed out.")


def cmd_doctor(args):
    """Offline checks (auth file present, signer works) + optional live probe."""
    ok = True
    try:
        info, p = load_client(args.client)
        print(f"client: {p} OK (serial {info.get('device_serial_number')})")
    except (FileNotFoundError, ValueError) as e:
        print(f"client: FAIL — {e}")
        ok = False
    try:
        from papir import signer
        sig = signer.digest_header_for_request.__name__
        print(f"signer: {sig} OK")
    except Exception as e:  # noqa: BLE001
        print(f"signer: FAIL — {e}")
        ok = False
    if args.live:
        try:
            n = len(papirDevices(args.client))
            print(f"live: devices reachable ({n} found) OK")
        except Exception as e:  # noqa: BLE001
            print(f"live: FAIL — {e}")
            ok = False
    raise SystemExit(0 if ok else 1)


def build_parser():
    ap = argparse.ArgumentParser(prog="papir", description="Beam reading material to your e-reader via API.")
    ap.add_argument("--client", default=None, help="path to client.json (default ~/.config/papir/client.json)")
    ap.add_argument("--set-default", action="store_true",
                    help="choose the default Kindle (same as `papir set-default`)")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("login", help="register a new device via browser sign-in")
    p.add_argument("--force", action="store_true")
    p.add_argument("--name", default=None, help="device model name (default: hostname)")
    p.add_argument("--url", default=None, help="final redirect URL (avoids interactive paste)")
    p.add_argument("--code", default=None, help="bare openid.oa2.authorization_code value")
    p.add_argument("--verifier", default=None, help="PKCE verifier from the matching login run")
    p.set_defaults(func=cmd_login)

    p = sub.add_parser("devices", help="list e-reader targets (* marks the default)")
    p.add_argument("--json", action="store_true", help="machine-readable devices and default destination")
    p.set_defaults(func=cmd_devices)

    p = sub.add_parser("set-default", help="choose the default Kindle to always send to")
    p.add_argument("serial", nargs="?", default=None, help="serial, or 'all' to clear")
    p.add_argument("--author", default=None, help="set the default author instead ('' to clear)")
    p.set_defaults(func=cmd_set_default)

    p = sub.add_parser("send", help="send a file (author/title default from setup + filename)")
    p.add_argument("file")
    p.add_argument("--author", default=None, help="defaults to your stored author")
    p.add_argument("--title", default=None, help="defaults to the cleaned-up filename")
    p.add_argument("--format", default="auto")
    p.add_argument("--to", default=None, help="serial, 'all', 'library', or omit for the default")
    p.add_argument("--no-archive", action="store_true")
    p.add_argument("--convert", action="store_true",
                   help="convert PDF to Kindle format (default keeps the native PDF)")
    p.set_defaults(func=cmd_send)

    p = sub.add_parser("logout", help="disown device + delete local creds")
    p.set_defaults(func=cmd_logout)

    p = sub.add_parser("doctor", help="self-test")
    p.add_argument("--live", action="store_true", help="also hit Amazon APIs")
    p.add_argument("--offline", action="store_true")
    p.set_defaults(func=cmd_doctor)
    return ap


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    # shorthand: `papir document.pdf --title X --author Y` == `papir send document.pdf ...`
    # (must rewrite BEFORE parse_args, or argparse rejects the filename as a bad subcommand)
    cmds = {"login", "devices", "set-default", "send", "logout", "doctor"}
    if "--set-default" not in argv and not any(t in cmds for t in argv):
        # pull out a global --client VALUE so flag order never breaks the rewrite
        client_val = None
        scan = list(argv)
        cleaned = []
        i = 0
        while i < len(scan):
            if scan[i] == "--client" and i + 1 < len(scan):
                client_val = scan[i + 1]
                i += 2
                continue
            cleaned.append(scan[i])
            i += 1
        found_file = any(
            not t.startswith("-") and os.path.exists(os.path.expanduser(t)) for t in cleaned
        )
        if found_file:
            argv = (["--client", client_val] if client_val else []) + ["send"] + cleaned
    args = build_parser().parse_args(argv)
    if getattr(args, "set_default", False):
        if args.cmd is not None:
            build_parser().error("--set-default takes no subcommand (did you mean `papir set-default`?)")
        args.cmd, args.serial, args.author, args.func = "set-default", None, None, cmd_set_default
        try:
            args.func(args)
        except api.APIError as e:
            _amazon_error(e)
        return
    if args.cmd is None:
        build_parser().print_help()
        raise SystemExit(1)
    try:
        args.func(args)
    except api.APIError as e:
        _amazon_error(e)


def _amazon_error(e):
    print(f"\nAmazon error: {e}", file=sys.stderr)
    print("Their Send-to-Kindle backend flaps (HTTP 500/503s come and go) — wait a bit and retry.", file=sys.stderr)
    print("Skip the device list meanwhile: `papir set-default SERIAL` or `papir send --to <serial|library>`.", file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
