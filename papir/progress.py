#!/usr/bin/env python3
# coding: utf-8
#
# duivesteyn // Python // papir
# https://github.com/duivesteyn/papir
#
# Tiny stderr progress bar with emoji. Stdlib only.
#
# # bmd 2026

"""Upload progress bar. Writes to stderr so stdout stays script-friendly (sku only)."""

import sys
import time

WIDTH = 24


def human_size(n):
    """1.6 MB, 680 KB, 512 B."""
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


class SendBar:
    """Callable progress sink: bar(sent, total). Falls back to plain lines off-tty."""

    def __init__(self, label, total, out=None):
        self.label = label
        self.total = max(int(total), 1)
        self.out = out if out is not None else sys.stderr
        self.tty = self.out.isatty() if hasattr(self.out, "isatty") else False
        self.start = time.time()
        self.last_draw = 0.0
        self.sent = 0
        self.closed = False
        self.write(f"\U0001F4E4 Sending {label} ({human_size(total)}) …\n")

    def write(self, s):
        self.out.write(s)
        try:
            self.out.flush()
        except (OSError, ValueError):
            pass

    def _draw(self, sent):
        pct = min(sent / self.total, 1.0)
        filled = int(pct * WIDTH)
        bar = "\u2588" * filled + "\u2591" * (WIDTH - filled)
        elapsed = max(time.time() - self.start, 0.001)
        rate = human_size(sent / elapsed) + "/s"
        self.write(
            f"\r\U0001F4E4 {self.label} [{bar}] {pct * 100:3.0f}% "
            f"{human_size(sent)}/{human_size(self.total)} {rate}\x1b[K"
        )

    def __call__(self, sent, total):
        self.sent = sent
        if sent >= self.total:
            if self.tty:
                self._draw(self.total)  # full 100% frame first — never skip it
            self.done()  # completion always reported, tty or not
            return
        now = time.time()
        if now - self.last_draw < 0.1:
            return  # throttle redraws
        self.last_draw = now
        if not self.tty:
            return  # start/done lines only in logs
        self._draw(sent)

    def done(self, message=None):
        if self.closed:
            return
        self.closed = True
        elapsed = time.time() - self.start
        if self.tty:
            self.write("\n")
        self.write(message or f"\u2705 Uploaded {human_size(self.sent)} in {elapsed:.1f}s — converting & delivering …\n")


if __name__ == "__main__":
    """Localhost Testing Functionality."""
    bar = SendBar('"Demo" by bmd', 1_600_000)
    for i in range(0, 1_600_001, 80_000):
        bar(i, 1_600_000)
        time.sleep(0.05)
    bar.done()
