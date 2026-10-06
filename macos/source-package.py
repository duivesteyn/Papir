"""Create a source ZIP from an explicit allowlist, excluding local documents/state."""
from pathlib import Path
import sys
import zipfile

project = Path(__file__).resolve().parent.parent
files = ["CONTRIBUTING.md", "SECURITY.md", "README.md", "LICENSE", "setup.py", "requirements.txt", "main.py", "test.py", ".gitignore"]
files += [str(p.relative_to(project)) for p in (project / "papir").glob("*.py")]
files += [str(p.relative_to(project)) for p in (project / "macos").iterdir() if p.is_file() and p.suffix in {".py", ".sh", ".md", ".txt", ".plist"}]
for directory in ("macos/Sources", "art", "planning", ".github", "macos/tests", "_screenshots"):
    files += [str(p.relative_to(project)) for p in (project / directory).rglob("*") if p.is_file() and "__pycache__" not in p.parts]
with zipfile.ZipFile(sys.argv[1], "w", compression=zipfile.ZIP_DEFLATED) as output:
    for relative in sorted(set(files)):
        output.write(project / relative, "Papir/" + relative)
