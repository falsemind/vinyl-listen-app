#!/usr/bin/env bash
set -euo pipefail

task="${1:?Gradle task required}"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

cd "$repo_root/android-app"
exec ./gradlew --quiet "$task"
