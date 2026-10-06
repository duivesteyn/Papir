#!/usr/bin/env python3
# coding: utf-8
#
# duivesteyn // Python // papir
# https://github.com/duivesteyn/papir
#
# Simple Example!
#

from papir import papirSend

def main():
    """Send a PDF with correct Author + Title."""

    sku = papirSend(
        "report.pdf",
        author="deCapital",
        title="Imperial Investment Case",
        target="all",
    )
    print(f"Sent sku={sku}")

if __name__ == "__main__":
    main()
