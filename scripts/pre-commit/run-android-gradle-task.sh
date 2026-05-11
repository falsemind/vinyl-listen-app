#!/usr/bin/env bash
set -euo pipefail

task="${1:?Gradle task required}"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

android_studio_jbr="/Applications/Android Studio.app/Contents/jbr/Contents/Home"
if [[ -n "${ANDROID_GRADLE_JAVA_HOME:-}" ]]; then
  export JAVA_HOME="$ANDROID_GRADLE_JAVA_HOME"
elif [[ -x "$android_studio_jbr/bin/java" ]]; then
  export JAVA_HOME="$android_studio_jbr"
fi

cd "$repo_root/android-app"
exec ./gradlew --quiet "$task"
