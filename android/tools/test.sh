#!/usr/bin/env bash
# JVM tests for the pure Kotlin core (signer, PKCE, title handling).
# The signer fixture is generated from the Python implementation, so this is a
# cross-language parity check, not a self-fulfilling test.

set -euo pipefail
source "$(dirname "$0")/env.sh"

mkdir -p "$BUILD/test-classes"
rm -rf "$BUILD/test-classes"
mkdir -p "$BUILD/test-classes"

CORE=()
for file in Signer Pkce Documents DeviceKind; do
    CORE+=("$ANDROID/app/src/main/java/com/duivesteyn/papir/core/$file.kt")
done
TESTS=()
while IFS= read -r file; do TESTS+=("$file"); done < <(find "$ANDROID/app/src/test/java" -name '*.kt' | sort)

echo "  compile tests"
kotlinc -no-stdlib -jvm-target 1.8 \
    -classpath "$TEST_LIBS/junit-4.13.2.jar:$KOTLIN_STDLIB" \
    -d "$BUILD/test-classes" \
    "${CORE[@]}" "${TESTS[@]}"

echo "  run"
java -Dpapir.android="$ANDROID" \
    -cp "$KOTLIN_STDLIB:$TEST_LIBS/junit-4.13.2.jar:$TEST_LIBS/hamcrest-core-1.3.jar:$BUILD/test-classes" \
    org.junit.runner.JUnitCore \
    com.duivesteyn.papir.core.SignerTest \
    com.duivesteyn.papir.core.PkceTest \
    com.duivesteyn.papir.core.DocumentsTest \
    com.duivesteyn.papir.core.DeviceKindTest \
    com.duivesteyn.papir.core.ManifestTest
