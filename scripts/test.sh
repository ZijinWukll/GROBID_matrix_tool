#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd -- "$script_dir/.." && pwd)"
python_bin="${MATRIX_PYTHON:-python}"

cd "$project_root"
exec "$python_bin" -m pytest -q
