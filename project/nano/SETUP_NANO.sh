#!/usr/bin/env bash
set -euo pipefail
# NumPy 1.19.5's bundled OpenBLAS can SIGILL on the Nano during import.
# Set this before the first Python process, including the cv2 probe below.
case "$(uname -m)" in
    aarch64|arm64) export OPENBLAS_CORETYPE=ARMV8 ;;
esac
export OMP_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=2
vdi_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ -n "${VDI_PYTHON:-}" ]]; then
    vdi_python="$VDI_PYTHON"
elif [[ -x /usr/bin/python3.6 ]]; then
    vdi_python=/usr/bin/python3.6
else
    vdi_python=/usr/bin/python3
fi
vdi_version="$($vdi_python -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
vdi_arch="$(uname -m)"
vdi_packages=()
"$vdi_python" -c 'import cv2' 2>/dev/null || vdi_packages+=(python3-opencv)
"$vdi_python" -c 'import tkinter' 2>/dev/null || vdi_packages+=(python3-tk)
"$vdi_python" -c 'import ensurepip' 2>/dev/null || vdi_packages+=(python3-venv)
command -v v4l2-ctl >/dev/null 2>&1 || vdi_packages+=(v4l-utils)
if ((${#vdi_packages[@]})); then
    printf 'Installing Nano system packages: %s\n' "${vdi_packages[*]}"
    if ((EUID == 0)); then
        apt-get update
        apt-get install -y "${vdi_packages[@]}"
    else
        sudo apt-get update
        sudo apt-get install -y "${vdi_packages[@]}"
    fi
fi
if [[ ! -x "$vdi_dir/.nano-venv/bin/python" ]]; then
    "$vdi_python" -m venv --system-site-packages "$vdi_dir/.nano-venv"
fi
vdi_env="$vdi_dir/.nano-venv/bin/python"
if [[ "$vdi_version" == 3.6 ]]; then
    if [[ "$vdi_arch" != aarch64 && "$vdi_arch" != arm64 ]]; then
        printf 'The included Python 3.6 wheels are for ARM64 Jetson Nano.\n' >&2
        exit 1
    fi
    vdi_wheels="$vdi_dir/wheels/python36_aarch64"
    "$vdi_env" -m pip install --no-index --find-links "$vdi_wheels" pip==21.3.1 setuptools==59.6.0 wheel==0.37.1
    "$vdi_env" -m pip install --no-index --find-links "$vdi_wheels" -r "$vdi_dir/requirements-nano36.txt"
elif [[ "$vdi_version" == 3.8 ]]; then
    "$vdi_env" -m pip install 'pip<25.1'
    "$vdi_env" -m pip install numpy==1.24.4 Pillow==9.5.0 onnxruntime==1.16.3
else
    "$vdi_env" -c 'import sys; assert (3,9) <= sys.version_info[:2] <= (3,12), "Use Nano system Python 3.6, or Python 3.8-3.12."'
    "$vdi_env" -m pip install numpy==1.26.4 Pillow==10.4.0 onnxruntime==1.20.1
fi
"$vdi_env" -u -c 'import importlib; names=("numpy", "cv2", "PIL", "onnxruntime", "tkinter"); [(print("Checking " + name + "...", flush=True), importlib.import_module(name), print("OK " + name, flush=True)) for name in names]'
"$vdi_env" "$vdi_dir/tools/check_models.py"
touch "$vdi_dir/.nano-venv/.vdi-ready"
printf '\nSetup passed. Start the camera GUI: bash START_NANO.sh\n'
