"""Visual Defect Inspector, IKT213 Group 2."""

import os
import platform

# Cover direct Python/PyCharm entry points as well as shell launchers.
# This must run before any package module imports cv2 or NumPy.
if platform.machine().lower() in ("aarch64", "arm64"):
    os.environ["OPENBLAS_CORETYPE"] = "ARMV8"

__version__ = "0.4.0"
