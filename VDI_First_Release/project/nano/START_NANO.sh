#!/usr/bin/env bash
set -euo pipefail
case "$(uname -m)" in
    aarch64|arm64) export OPENBLAS_CORETYPE=ARMV8 ;;
esac
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=2
vdi_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -x "$vdi_dir/.nano-venv/bin/python" || ! -f "$vdi_dir/.nano-venv/.vdi-ready" ]]; then
    bash "$vdi_dir/SETUP_NANO.sh"
fi
if [[ -z "${DISPLAY:-}" ]]; then
    printf 'Open this terminal on the Nano desktop, with its monitor connected. The GUI needs a display.\n' >&2
    printf 'For a headless model check: .nano-venv/bin/python tools/check_models.py\n' >&2
    exit 1
fi
export YOLO_AUTOINSTALL=False
printf 'Starting the Nano camera GUI with the supplied trained models.\n'
exec "$vdi_dir/.nano-venv/bin/python" "$vdi_dir/START_GUI.py" "$@"
