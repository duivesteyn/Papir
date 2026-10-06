#!/usr/bin/env python3
# coding: utf-8
#
# duivesteyn // Python // papir
# https://github.com/duivesteyn/papir
#
# Arrow-key menu with numbered-prompt fallback. Stdlib only.
#
# # bmd 2026

"""Interactive option picker: up/down arrows on a tty, numbered input otherwise."""

import os
import sys

ALL = "ALL"  # sentinel meaning "all devices" (maps to stored default None)


def interpret_numbered_input(text, n_devices):
    """Map one line of fallback input to ('index', i) | ('all',) | ('cancel',) | ('serial', s) | ('invalid',).

    Pure function — unit-testable. n_devices excludes the trailing 'All devices' entry.
    """
    t = text.strip()
    if t == "" or t.lower() in ("q", "quit", "exit"):
        return ("cancel",)
    if t.isdigit():
        i = int(t)
        if 1 <= i <= n_devices:
            return ("index", i - 1)
        if i == n_devices + 1:
            return ("all",)
        return ("invalid",)
    return ("serial", t)


def _can_arrow():
    return (
        sys.stdin.isatty()
        and sys.stdout.isatty()
        and os.name != "nt"
        and os.environ.get("TERM", "") != "dumb"
    )


def choose(prompt, labels):
    """Pick one of labels. Returns 0-based index, ALL (last entry), or None on cancel.

    labels should already include 'All devices' as the final entry.
    """
    if _can_arrow():
        try:
            return _choose_arrow(prompt, labels)
        except Exception:  # noqa: BLE001 — broken terminfo etc: fall back to numbers
            pass
    return _choose_numbered(prompt, labels)


def _choose_numbered(prompt, labels):
    n_devices = len(labels) - 1
    print(prompt)
    for i, label in enumerate(labels, 1):
        print(f"  {i}. {label}")
    while True:
        try:
            text = input(f"[1-{len(labels)}, serial, q=cancel]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        kind, *rest = interpret_numbered_input(text, n_devices)
        if kind == "index":
            return rest[0]
        if kind == "all":
            return ALL
        if kind == "cancel":
            return None
        if kind == "serial":
            return rest[0]  # raw serial pasted — caller validates loosely
        print(f"Enter 1-{len(labels)}, a serial, or q.")


def _choose_arrow(prompt, labels):
    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    idx = 0
    n = len(labels)
    try:
        tty.setraw(fd)
        out = sys.stdout
        out.write("\x1b[?25l")  # hide cursor while navigating
        out.write(prompt + "\r\n")
        for _ in labels:
            out.write("\r\n")
        out.flush()

        def render():
            out.write(f"\x1b[{n}A")  # back up to first option
            for i, label in enumerate(labels):
                marker = "\u276f" if i == idx else " "
                line = f"{marker} {label}"
                if i == idx:
                    line = f"\x1b[7m{line}\x1b[0m"
                out.write(f"\r\x1b[K{line}\r\n")
            out.flush()

        def read_bytes(n, timeout):
            """Read up to n raw bytes, waiting at most timeout total. No stdio buffering."""
            out_b = b""
            while len(out_b) < n:
                r, _, _ = select.select([fd], [], [], timeout)
                if not r:
                    break
                chunk = os.read(fd, n - len(out_b))
                if not chunk:
                    break
                out_b += chunk
            return out_b

        def read_key():
            b = read_bytes(1, None)  # block for the first byte
            if not b:
                return "esc"  # EOF (Ctrl-D in raw mode)
            if b == b"\x1b":
                # Arrows arrive as ESC [ A/B (normal) or ESC O A/B (tmux/app mode).
                # A lone Esc means cancel — wait briefly to tell them apart.
                rest = read_bytes(2, 0.15)
                if rest == b"":
                    return "esc"
                if rest[:1] in (b"[", b"O") and len(rest) >= 2:
                    return {"A": "up", "B": "down", "H": "home", "F": "end"}.get(
                        rest[1:2].decode("ascii", "replace"), None)
                return None  # unknown escape (e.g. mouse, focus events) — ignore
            if b in (b"\r", b"\n"):
                return "enter"
            if b == b"\x03":  # Ctrl-C in raw mode arrives as a byte, not a signal
                return "esc"
            if b == b"\x7f":
                return "esc"
            try:
                ch = b.decode("utf-8")
            except UnicodeDecodeError:
                return None
            return ch

        render()
        while True:
            key = read_key()
            if key == "up" or key == "k":
                idx = (idx - 1) % n
                render()
            elif key == "down" or key == "j":
                idx = (idx + 1) % n
                render()
            elif key == "home":
                idx = 0
                render()
            elif key == "end":
                idx = n - 1
                render()
            elif key == "enter":
                out.write(f"\r\x1b[K\u2713 {labels[idx]}\r\n")
                out.flush()
                return ALL if idx == n - 1 else idx
            elif key == "esc" or key == "q":
                out.write("\r\x1b[K(cancelled)\r\n")
                out.flush()
                return None
            elif isinstance(key, str) and key.isdigit():
                num = int(key)
                if 1 <= num <= n:
                    idx = num - 1
                    render()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write("\x1b[?25h")
        sys.stdout.flush()


if __name__ == "__main__":
    """Localhost Testing Functionality."""
    r = choose("Pick one:", ["Scribe", "Pixel", "All devices"])
    print(f"chose: {r!r}")
