"""One capture requested by the GUI. No terminal input and no image saving here."""
import shutil
import subprocess
import time
from pathlib import Path

import cv2

from .image_processing import utc_now


class CameraError(RuntimeError):
    pass


class Camera:
    def __init__(self, config):
        self.config = config

    def _controls(self):
        if not shutil.which("v4l2-ctl"):
            raise CameraError("v4l2-ctl is missing. Install Ubuntu package v4l-utils.")
        device = self.config["device"]
        # Modern kernels sometimes use new names for the same UVC controls.
        aliases = {"exposure_auto": "auto_exposure", "focus_auto": "focus_automatic_continuous",
                   "white_balance_temperature_auto": "white_balance_automatic"}
        listing = subprocess.run(["v4l2-ctl", "-d", device, "--list-ctrls"],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 universal_newlines=True, timeout=5)
        if listing.returncode:
            raise CameraError("Cannot query camera controls: " + listing.stderr.strip())
        available = {line.split()[0] for line in listing.stdout.splitlines() if line.split()}
        actual = {}
        for name, value in self.config["controls"].items():
            control = name if name in available else aliases.get(name, name)
            setting = "%s=%d" % (control, value)
            done = subprocess.run(["v4l2-ctl", "-d", device, "-c", setting],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  universal_newlines=True, timeout=5)
            if done.returncode:
                raise CameraError("Camera rejected %s: %s" % (setting, done.stderr.strip()))
            check = subprocess.run(["v4l2-ctl", "-d", device, "--get-ctrl", control],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   universal_newlines=True, timeout=5)
            try:
                readback = int(check.stdout.strip().split(":")[-1].strip())
            except ValueError:
                readback = None
            if check.returncode or readback != value:
                raise CameraError("Camera did not retain setting %s." % setting)
            actual[control] = readback
        return actual

    def capture(self):
        c = self.config
        if not Path(c["device"]).exists():
            raise CameraError("Camera not found: " + c["device"])
        cap = cv2.VideoCapture(c["device"], cv2.CAP_V4L2)
        try:
            if not cap.isOpened():
                raise CameraError("Could not open camera. Close other camera applications.")
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"YUYV"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, c["width"])
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, c["height"])
            controls = self._controls()
            for _ in range(c["warmup_frames"]):
                if not cap.read()[0]:
                    raise CameraError("Camera failed during warm-up.")
            time.sleep(c["settle_seconds"])
            # Controls remain locked while older buffered frames are discarded.
            for _ in range(c["flush_frames"]):
                if not cap.read()[0]:
                    raise CameraError("Camera failed while flushing frames.")
            ok, frame = cap.read()
            captured_at = utc_now()
            if not ok or frame is None:
                raise CameraError("Camera returned no image.")
            if frame.shape[:2] != (c["height"], c["width"]):
                raise CameraError("Camera returned the wrong resolution; calibration would be invalid.")
            fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
            if fourcc != cv2.VideoWriter_fourcc(*"YUYV"):
                raise CameraError("Camera did not select YUYV. Check supported camera formats.")
            return frame, captured_at, {"device": c["device"], "controls": controls,
                                        "format": "YUYV", "width": c["width"], "height": c["height"]}
        finally:
            cap.release()
