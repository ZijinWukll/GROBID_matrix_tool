#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd -- "$script_dir/.." && pwd)"
python_bin="${MATRIX_PYTHON:-python}"

exec "$python_bin" "$project_root/matrix_tool.py" "$@"
