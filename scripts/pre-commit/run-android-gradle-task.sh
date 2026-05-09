#!/usr/bin/env bash
set -euo pipefail

task="${1:?Gradle task required}"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if [[ "$task" == ":app:detekt" ]]; then
    java_version="$(java -version 2>&1 | awk -F '"' '/version/ { print $2; exit }')"
    java_major="${java_version%%.*}"

    if [[ "$java_major" == "1" ]]; then
        java_major="$(printf '%s' "$java_version" | awk -F '.' '{ print $2 }')"
    fi

    if [[ "$java_major" =~ ^[0-9]+$ ]] && ((java_major > 22)); then
        echo "detekt 1.23.8 does not run on JDK $java_version."
        echo "Use JDK 17 or 21 for pre-commit, then rerun this hook."
        exit 1
    fi
fi

cd "$repo_root/android-app"
exec ./gradlew --quiet "$task"
