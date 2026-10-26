"""Synthetic fixtures for software integration, not evidence of model accuracy."""
from pathlib import Path

import cv2
import numpy as np

from .config import ROOT
from .image_processing import encode_png, read_image, utc_now

CASES = [
    ("Clean protector", "clean", "clean"),
    ("Scratch", "scratch", "scratch"),
    ("Crack", "crack", "crack"),
    ("Scratch and crack", "both", "both"),
    ("No protector", "empty", "clean"),
    ("Wrong shape", "wrong_shape", "clean"),
    ("Missing piece", "missing_piece", "clean"),
    ("Wrong dimensions", "wrong_size", "clean"),
    ("Rotated protector", "rotated", "clean"),
    ("Model failure", "clean", "model_error"),
]


class TestCamera:
    """Advance automatically on each capture request; never ask an operator for a file.

    The image and the simulated model scenario travel together through acquisition.
    A new test session starts at the first sample, then repeats after the last one.
    """
    is_simulated = True

    def __init__(self):
        self.directory = generate_demo_assets()
        self.index = 0

    def capture(self):
        label, asset, scenario = CASES[self.index % len(CASES)]
        image = read_image(self.directory / (asset + ".png"))
        self.index += 1
        return image, utc_now(), {"device": "simulated-test-camera", "simulated": True,
                                   "test_case": label, "test_scenario": scenario,
                                   "sequence_number": self.index}


def generate_demo_assets(directory=None):
    directory = Path(directory) if directory else ROOT / "assets/demo"
    directory.mkdir(parents=True, exist_ok=True)
    background = np.full((800, 800, 3), 12, np.uint8)
    clean = background.copy()
    cv2.rectangle(clean, (260, 120), (540, 680), (115, 110, 100), -1)
    cv2.rectangle(clean, (280, 100), (520, 700), (115, 110, 100), -1)
    for point in [(280, 120), (520, 120), (280, 680), (520, 680)]:
        cv2.circle(clean, point, 20, (115, 110, 100), -1)
    images = {"clean": clean, "empty": background}
    for name in ("scratch", "crack", "both"):
        image = clean.copy()
        if name in ("scratch", "both"):
            cv2.line(image, (350, 300), (460, 340), (240, 240, 240), 2)
        if name in ("crack", "both"):
            cv2.polylines(image, [np.array([(350, 470), (410, 490), (385, 520), (450, 550)])], False, (240, 240, 240), 2)
        images[name] = image
    wrong = background.copy()
    cv2.rectangle(wrong, (240, 150), (560, 650), (115, 110, 100), -1)
    images["wrong_shape"] = wrong
    missing = clean.copy()
    cv2.rectangle(missing, (460, 340), (560, 490), (12, 12, 12), -1)
    images["missing_piece"] = missing
    transform = cv2.getRotationMatrix2D((400, 400), 0, 1.10)
    images["wrong_size"] = cv2.warpAffine(clean, transform, (800, 800), borderValue=(12, 12, 12))
    transform = cv2.getRotationMatrix2D((400, 400), 23, 1)
    images["rotated"] = cv2.warpAffine(clean, transform, (800, 800), borderValue=(12, 12, 12))
    for name, image in images.items():
        target = directory / (name + ".png")
        if not target.exists():
            target.write_bytes(encode_png(image))
    return directory
