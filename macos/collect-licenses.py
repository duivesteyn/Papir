"""Retain notices for the Python runtime and frozen runtime dependencies."""
from importlib.metadata import distribution
from pathlib import Path
import sys

parts = ["Papir bundled runtime: third-party licences\n"]
# Python's interpreter licence is exposed by the interpreter itself.
python_license = __import__('builtins').license
python_license._Printer__setup()
parts.append("Python\n" + "\n".join(python_license._Printer__lines))
for name in ("requests", "urllib3", "certifi", "charset-normalizer", "idna", "pyinstaller"):
    dist = distribution(name)
    parts.append(f"\n{name} {dist.version}\n")
    for file in dist.files or []:
        if any(term in file.name.lower() for term in ("license", "copying", "notice")):
            path = Path(dist.locate_file(file))
            if path.is_file():
                parts.append(path.read_text(errors="replace"))
Path(sys.argv[1]).write_text("\n\n".join(parts))
