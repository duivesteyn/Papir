#!/bin/bash
set -euo pipefail
PAPIR_MAC_ROOT="$(cd "$(dirname "$0")" && pwd)"
PAPIR_PROJECT_ROOT="$(cd "$PAPIR_MAC_ROOT/.." && pwd)"
PAPIR_APP="$PAPIR_MAC_ROOT/build/Papir.app"
PAPIR_BUILD_PYTHON="${PAPIR_BUILD_PYTHON:-$PAPIR_MAC_ROOT/build-tools/bin/python}"
if [ ! -x "$PAPIR_BUILD_PYTHON" ]; then
    python3 -m venv "$PAPIR_MAC_ROOT/build-tools"
fi
if ! "$PAPIR_BUILD_PYTHON" -c "import PyInstaller, requests" 2>/dev/null; then
    "$PAPIR_BUILD_PYTHON" -m pip install --disable-pip-version-check -r "$PAPIR_MAC_ROOT/build-requirements.txt"
fi
PYINSTALLER_CONFIG_DIR="$PAPIR_MAC_ROOT/build/pyinstaller-cache" "$PAPIR_BUILD_PYTHON" -m PyInstaller --noconfirm --onefile --name papir-engine \
    --paths "$PAPIR_PROJECT_ROOT" --distpath "$PAPIR_MAC_ROOT/build/engine-dist" \
    --workpath "$PAPIR_MAC_ROOT/build/engine-work" --specpath "$PAPIR_MAC_ROOT/build" \
    "$PAPIR_MAC_ROOT/engine.py"
mkdir -p "$PAPIR_APP/Contents/MacOS" "$PAPIR_APP/Contents/Resources" "$PAPIR_APP/Contents/Helpers"
xcrun swiftc -module-cache-path "$PAPIR_MAC_ROOT/build/ModuleCache" -parse-as-library -swift-version 5 \
    -target "$(uname -m)-apple-macosx14.0" "$PAPIR_MAC_ROOT/Sources/PapirApp.swift" -o "$PAPIR_APP/Contents/MacOS/Papir"
# Replace only generated runtime output; never include credentials or project data.
if [ -d "$PAPIR_APP/Contents/Helpers/papir-engine" ]; then
    rm -rf "$PAPIR_APP/Contents/Helpers/papir-engine"
fi
cp "$PAPIR_MAC_ROOT/build/engine-dist/papir-engine" "$PAPIR_APP/Contents/Helpers/papir-engine"
cp "$PAPIR_MAC_ROOT/Info.plist" "$PAPIR_APP/Contents/Info.plist"
cp "$PAPIR_PROJECT_ROOT/art/Iconi/Papir.icns" "$PAPIR_APP/Contents/Resources/Papir.icns"
cp "$PAPIR_PROJECT_ROOT/LICENSE" "$PAPIR_APP/Contents/Resources/LICENSE.txt"
"$PAPIR_BUILD_PYTHON" "$PAPIR_MAC_ROOT/collect-licenses.py" "$PAPIR_APP/Contents/Resources/ThirdPartyLicenses.txt"
codesign --force --deep --sign - "$PAPIR_APP"
codesign --verify --deep --strict "$PAPIR_APP"
printf '%s\n' "$PAPIR_APP"
