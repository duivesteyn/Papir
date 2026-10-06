"""Frozen entry point: normal CLI plus private desktop JSON bridge."""
import sys
from papir.cli import main as cli_main
from papir.desktop import main as desktop_main

if __name__ == "__main__":
    if sys.argv[1:] == ["--desktop"]:
        raise SystemExit(desktop_main())
    cli_main()
