"""Read-only deployment information; run on the Jetson before selecting model packages."""
import importlib
import platform
import sys
from pathlib import Path

print("Python:", sys.version)
print("Architecture:", platform.machine())
for file in ("/etc/nv_tegra_release", "/etc/os-release", "/proc/device-tree/model"):
    p = Path(file)
    if p.exists():
        print(file, p.read_text(errors="replace").replace("\x00", "").strip())
for name in ("cv2", "numpy", "PIL", "tkinter", "torch", "torchvision", "tensorrt", "ultralytics"):
    try:
        module = importlib.import_module(name)
        print(name, getattr(module, "__version__", "available"))
        if name == "torch":
            print("CUDA available:", module.cuda.is_available())
    except Exception as exc:
        print(name, "unavailable:", str(exc))
