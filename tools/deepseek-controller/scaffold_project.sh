#!/usr/bin/env bash
# Thin scaffold wrapper: plan JSON → project dir (Swiss full glue; other styles stub).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec python3 "$ROOT/tools/deepseek-controller/scaffold.py" "$@"
