"""Architecture steps 3-7: acquisition, capture metadata and preprocessing."""
from pathlib import Path

from .camera import Camera
from .image_processing import prepare, read_image, utc_now


class PictureController:
    def __init__(self, settings, camera=None):
        self.settings = settings
        self.camera = camera or Camera(settings.data["camera"])

    def acquire(self, path=None):
        if path is None:
            image, captured_at, camera_info = self.camera.capture()
            simulated = camera_info.get("simulated", False)
            if simulated and (not self.settings.data["demo"] or self.settings.data["model"]["backend"] != "placeholder"):
                raise ValueError("Simulated camera frames cannot be used as real inspections.")
            source = {"kind": "test_camera" if simulated else "camera",
                      "name": camera_info["device"], "camera": camera_info}
        else:
            image = read_image(path)
            captured_at = None  # An import time must not be presented as an original capture time.
            source = {"kind": "file", "name": str(Path(path).resolve())}
        packet = prepare(image, self.settings.data["segmentation"])
        packet.update({"captured_at": captured_at, "acquired_at": utc_now(), "source": source})
        if source["kind"] == "test_camera":
            packet["test_scenario"] = source["camera"]["test_scenario"]
        return packet
