#!/usr/bin/env bash
set -euo pipefail

tool="${1:?Backend tool required}"
shift

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
backend_root="$repo_root/backend"

files=()
for path in "$@"; do
  case "$path" in
    backend/*) files+=("${path#backend/}") ;;
    *) files+=("$path") ;;
  esac
done

if [[ "${#files[@]}" -eq 0 ]]; then
  exit 0
fi

cd "$backend_root"

case "$tool" in
  black)
    exec .venv/bin/black "${files[@]}"
    ;;
  ruff)
    exec .venv/bin/ruff check --fix "${files[@]}"
    ;;
  *)
    echo "Unsupported backend tool: $tool" >&2
    exit 2
    ;;
esac
