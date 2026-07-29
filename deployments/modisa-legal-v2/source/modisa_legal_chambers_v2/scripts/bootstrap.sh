#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v uv >/dev/null 2>&1 || { echo "uv is required" >&2; exit 1; }
[[ -f .env.local ]] || python scripts/init_secrets.py --target .env.local
uv sync --extra dev
uv run pytest -q
printf '%s\n' "Offline controls verified. Add OPENAI_API_KEY securely, then run PORT=8421 uv run python main.py"
