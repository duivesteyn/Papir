#!/usr/bin/env bash
# One-time toolchain setup for the Papir Android build.
#
#   bash android/tools/bootstrap.sh
#
# Everything lands in .tooling/ (gitignored): the Android SDK packages and the
# Kotlin compiler. No Gradle, no Android Studio, no system-wide changes.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TOOLING="$ROOT/.tooling"
SDK="$TOOLING/sdk"
KOTLIN="$TOOLING/kotlinc"
TESTLIB="$TOOLING/testlib"
DL="$TOOLING/dl"
HOME_OVERRIDE="-Duser.home=$TOOLING/home"

CMDLINE_URL="https://dl.google.com/android/repository/commandlinetools-mac-13114758_latest.zip"
KOTLIN_VERSION="2.0.21"
MAVEN="https://repo1.maven.org/maven2"

mkdir -p "$TOOLING/home" "$DL" "$KOTLIN" "$TESTLIB"

if [ ! -x "$SDK/cmdline-tools/latest/bin/sdkmanager" ]; then
    echo "→ Android command-line tools"
    curl -sSL -o "$DL/cmdline-tools.zip" "$CMDLINE_URL"
    rm -rf "$SDK/cmdline-tools" /tmp/papir-cmdline-tools
    mkdir -p "$SDK/cmdline-tools"
    unzip -q "$DL/cmdline-tools.zip" -d /tmp/papir-cmdline-tools
    mv /tmp/papir-cmdline-tools/cmdline-tools "$SDK/cmdline-tools/latest"
    rm -rf /tmp/papir-cmdline-tools
fi

echo "→ SDK packages"
export JAVA_OPTS="$HOME_OVERRIDE"
printf 'y\n%.0s' {1..40} | "$SDK/cmdline-tools/latest/bin/sdkmanager" --sdk_root="$SDK" --licenses >/dev/null 2>&1 || true
"$SDK/cmdline-tools/latest/bin/sdkmanager" --sdk_root="$SDK" \
    "platform-tools" "platforms;android-35" "build-tools;35.0.0"

echo "→ Kotlin compiler $KOTLIN_VERSION"
fetch() {
    local relative="$1" destination="$2"
    if [ ! -s "$destination" ]; then
        curl -sSL -o "$destination" "$MAVEN/$relative"
    fi
}
fetch "org/jetbrains/kotlin/kotlin-compiler-embeddable/$KOTLIN_VERSION/kotlin-compiler-embeddable-$KOTLIN_VERSION.jar" "$KOTLIN/kotlin-compiler-embeddable-$KOTLIN_VERSION.jar"
fetch "org/jetbrains/kotlin/kotlin-stdlib/$KOTLIN_VERSION/kotlin-stdlib-$KOTLIN_VERSION.jar" "$KOTLIN/kotlin-stdlib-$KOTLIN_VERSION.jar"
fetch "org/jetbrains/kotlin/kotlin-script-runtime/$KOTLIN_VERSION/kotlin-script-runtime-$KOTLIN_VERSION.jar" "$KOTLIN/kotlin-script-runtime-$KOTLIN_VERSION.jar"
fetch "org/jetbrains/kotlin/kotlin-reflect/$KOTLIN_VERSION/kotlin-reflect-$KOTLIN_VERSION.jar" "$KOTLIN/kotlin-reflect-$KOTLIN_VERSION.jar"
fetch "org/jetbrains/kotlin/kotlin-daemon-embeddable/$KOTLIN_VERSION/kotlin-daemon-embeddable-$KOTLIN_VERSION.jar" "$KOTLIN/kotlin-daemon-embeddable-$KOTLIN_VERSION.jar"
fetch "org/jetbrains/intellij/deps/trove4j/1.0.20200330/trove4j-1.0.20200330.jar" "$KOTLIN/trove4j-1.0.20200330.jar"
fetch "org/jetbrains/annotations/13.0/annotations-13.0.jar" "$KOTLIN/annotations-13.0.jar"
fetch "org/jetbrains/kotlinx/kotlinx-coroutines-core-jvm/1.8.1/kotlinx-coroutines-core-jvm-1.8.1.jar" "$KOTLIN/kotlinx-coroutines-core-jvm-1.8.1.jar"

echo "→ test dependencies"
fetch "junit/junit/4.13.2/junit-4.13.2.jar" "$TESTLIB/junit-4.13.2.jar"
fetch "org/hamcrest/hamcrest-core/1.3/hamcrest-core-1.3.jar" "$TESTLIB/hamcrest-core-1.3.jar"

echo
echo "ready: bash android/tools/build.sh"
