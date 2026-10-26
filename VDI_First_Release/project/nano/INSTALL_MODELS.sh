#!/usr/bin/env bash
set -euo pipefail
vdi_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$vdi_dir/SETUP_NANO.sh" "$@"
