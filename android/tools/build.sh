#!/usr/bin/env bash
# Build the Papir Android APK without Gradle.
#
#   android/tools/build.sh
#
# Output: android/build/papir-<version>.apk (signed with the local dev key).

set -euo pipefail
source "$(dirname "$0")/env.sh"
require_toolchain

echo "Papir Android $VERSION_NAME"
rm -rf "$BUILD"
mkdir -p "$BUILD/gen" "$BUILD/classes" "$BUILD/dex"

echo "  resources"
"$BUILD_TOOLS/aapt2" compile --dir "$ANDROID/app/src/main/res" -o "$BUILD/res.zip"

echo "  link"
"$BUILD_TOOLS/aapt2" link \
    -I "$PLATFORM" \
    --manifest "$ANDROID/app/src/main/AndroidManifest.xml" \
    -R "$BUILD/res.zip" \
    --java "$BUILD/gen" \
    --min-sdk-version "$MIN_SDK" \
    --target-sdk-version "$TARGET_SDK" \
    --version-code "$VERSION_CODE" \
    --version-name "$VERSION_NAME" \
    --auto-add-overlay \
    -o "$BUILD/base.apk"

echo "  R.java"
find "$BUILD/gen" -name '*.java' -print0 |
    xargs -0 javac -encoding UTF-8 --release 8 -nowarn -classpath "$PLATFORM" -d "$BUILD/classes"

echo "  kotlin"
SOURCES=()
while IFS= read -r file; do SOURCES+=("$file"); done < <(kt_sources)
kotlinc -no-stdlib -jvm-target 1.8 \
    -classpath "$PLATFORM:$BUILD/classes:$KOTLIN_STDLIB" \
    -d "$BUILD/classes" \
    "${SOURCES[@]}"

echo "  dex"
CLASSES=()
while IFS= read -r file; do CLASSES+=("$file"); done < <(find "$BUILD/classes" -name '*.class' | sort)
"$BUILD_TOOLS/d8" --release --min-api "$MIN_SDK" --lib "$PLATFORM" \
    --output "$BUILD/dex" \
    "${CLASSES[@]}" "$KOTLIN_STDLIB"

echo "  package"
cp "$BUILD/base.apk" "$BUILD/unsigned.apk"
(cd "$BUILD/dex" && zip -q -X "$BUILD/unsigned.apk" classes.dex)

echo "  align"
"$BUILD_TOOLS/zipalign" -f -p 4 "$BUILD/unsigned.apk" "$BUILD/aligned.apk"

echo "  sign"
KEYSTORE="$ROOT/.tooling/papir-dev.keystore"
if [ ! -f "$KEYSTORE" ]; then
    mkdir -p "$(dirname "$KEYSTORE")"
    keytool -genkeypair -keystore "$KEYSTORE" -storepass papir-dev -keypass papir-dev \
        -alias papir -keyalg RSA -keysize 2048 -validity 10000 \
        -dname "CN=Papir Dev, O=Papir, C=AU" >/dev/null
    echo "    created local signing key at $KEYSTORE"
fi
APK="$BUILD/papir-$VERSION_NAME.apk"
"$BUILD_TOOLS/apksigner" sign \
    --ks "$KEYSTORE" --ks-pass pass:papir-dev --key-pass pass:papir-dev \
    --out "$APK" "$BUILD/aligned.apk"
"$BUILD_TOOLS/apksigner" verify "$APK"

echo
ls -lh "$APK"
"$BUILD_TOOLS/aapt2" dump badging "$APK" | grep -E "package:|application-label:|sdkVersion|targetSdkVersion" | head -5
