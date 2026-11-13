#!/usr/bin/env bash
# Shared environment for the Papir Android build.
#
# This project builds without Gradle: the toolchain lives in .tooling/ and is
# driven directly through aapt2, kotlinc, d8 and apksigner. Everything is
# reproducible from a plain macOS checkout with a JDK.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ANDROID="$ROOT/android"
SDK="${ANDROID_SDK_ROOT:-$ROOT/.tooling/sdk}"
BUILD_TOOLS="${BUILD_TOOLS:-$SDK/build-tools/35.0.0}"
PLATFORM="${PLATFORM:-$SDK/platforms/android-35/android.jar}"
KOTLIN_LIBS="$ROOT/.tooling/kotlinc"
TEST_LIBS="$ROOT/.tooling/testlib"
BUILD="$ANDROID/build"

VERSION_NAME="0.1.2"
VERSION_CODE="3"
MIN_SDK=26
TARGET_SDK=34

KOTLIN_STDLIB="$KOTLIN_LIBS/kotlin-stdlib-2.0.21.jar"
KOTLIN_COMPILER_CP="$KOTLIN_LIBS/kotlin-compiler-embeddable-2.0.21.jar"
KOTLIN_COMPILER_CP="$KOTLIN_COMPILER_CP:$KOTLIN_LIBS/kotlin-stdlib-2.0.21.jar"
KOTLIN_COMPILER_CP="$KOTLIN_COMPILER_CP:$KOTLIN_LIBS/kotlin-script-runtime-2.0.21.jar"
KOTLIN_COMPILER_CP="$KOTLIN_COMPILER_CP:$KOTLIN_LIBS/kotlin-reflect-2.0.21.jar"
KOTLIN_COMPILER_CP="$KOTLIN_COMPILER_CP:$KOTLIN_LIBS/kotlin-daemon-embeddable-2.0.21.jar"
KOTLIN_COMPILER_CP="$KOTLIN_COMPILER_CP:$KOTLIN_LIBS/trove4j-1.0.20200330.jar"
KOTLIN_COMPILER_CP="$KOTLIN_COMPILER_CP:$KOTLIN_LIBS/annotations-13.0.jar"
KOTLIN_COMPILER_CP="$KOTLIN_COMPILER_CP:$KOTLIN_LIBS/kotlinx-coroutines-core-jvm-1.8.1.jar"

kotlinc() {
    java -Xmx2g -cp "$KOTLIN_COMPILER_CP" \
        org.jetbrains.kotlin.cli.jvm.K2JVMCompiler "$@"
}

require_toolchain() {
    for required in "$PLATFORM" "$BUILD_TOOLS/aapt2" "$KOTLIN_STDLIB" "$BUILD_TOOLS/apksigner"; do
        if [ ! -e "$required" ]; then
            echo "missing $required" >&2
            echo "see android/README.md for the one-time toolchain setup" >&2
            exit 1
        fi
    done
}

kt_sources() {
    find "$ANDROID/app/src/main/java" -name '*.kt' | sort
}
