#!/bin/bash
set -euo pipefail
PAPIR_MAC_ROOT="$(cd "$(dirname "$0")" && pwd)"
PAPIR_APP="$PAPIR_MAC_ROOT/build/Papir.app"
if [ ! -x "$PAPIR_APP/Contents/Helpers/papir-engine" ]; then
    printf '%s\n' 'Run bash macos/build.sh first.' >&2
    exit 1
fi
codesign --verify --deep --strict "$PAPIR_APP"
PAPIR_VERSION=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$PAPIR_APP/Contents/Info.plist")
PAPIR_ARCH="$(uname -m)"
PAPIR_RELEASE="$PAPIR_MAC_ROOT/releases"
PAPIR_ZIP="$PAPIR_RELEASE/Papir-$PAPIR_VERSION-macos-$PAPIR_ARCH.zip"
mkdir -p "$PAPIR_RELEASE"
ditto -c -k --sequesterRsrc --keepParent "$PAPIR_APP" "$PAPIR_ZIP"
cp "$PAPIR_MAC_ROOT/INSTALL.md" "$PAPIR_RELEASE/INSTALL.md"
python3 "$PAPIR_MAC_ROOT/source-package.py" "$PAPIR_RELEASE/Papir-$PAPIR_VERSION-source.zip"
(cd "$PAPIR_RELEASE" && shasum -a 256 "$(basename "$PAPIR_ZIP")" "Papir-$PAPIR_VERSION-source.zip" > SHA256SUMS.txt)
printf '%s\n' "$PAPIR_ZIP"
