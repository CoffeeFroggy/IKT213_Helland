"""Read-only checks; does not install packages or access a camera."""
import importlib
import os
import platform
import sys

if platform.machine().lower() in ("aarch64", "arm64"):
    os.environ["OPENBLAS_CORETYPE"] = "ARMV8"

print("Python:", sys.version.split()[0])
print("Interpreter:", sys.executable)
print("Platform:", platform.platform())
missing = []
for name in ("numpy", "cv2", "PIL", "tkinter", "sqlite3"):
    try:
        module = importlib.import_module(name)
        print("OK %-9s %s" % (name, getattr(module, "__version__", "built in / available")))
    except Exception as exc:
        missing.append(name)
        print("MISSING %s: %s" % (name, exc))
if sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
    print("No desktop display detected. The GUI needs a desktop session; headless tests still work.")
if missing:
    print("See README.md for installation in your existing environment.")
    sys.exit(1)
print("Core imports are ready. Start with: python START_GUI.py")
