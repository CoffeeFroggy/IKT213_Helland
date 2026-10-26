"""Full-resolution images for measurement; Laplace contrast is display-only."""
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def read_image(path):
    p = Path(path)
    if p.suffix.lower() not in (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"):
        raise ValueError("Unsupported image extension. Choose PNG, JPEG, BMP or TIFF.")
    try:
        data = np.frombuffer(p.read_bytes(), dtype=np.uint8)
        image = cv2.imdecode(data, cv2.IMREAD_COLOR) if data.size else None
    except OSError as exc:
        raise ValueError("Cannot read image: %s" % exc)
    if image is None or not image.size:
        raise ValueError("The file is not a readable image: %s" % p.name)
    return image


def encode_png(image):
    ok, data = cv2.imencode(".png", image)
    if not ok:
        raise ValueError("Could not encode image for storage.")
    return data.tobytes()


def decode_png(data):
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError("Stored image could not be decoded.")
    return image


def prepare(image, segmentation):
    if image is None or image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Expected a non-empty uint8 BGR image.")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    k = segmentation["gaussian_kernel"]
    blur = cv2.GaussianBlur(gray, (k, k), 0)
    lap = cv2.Laplacian(blur, cv2.CV_32F, ksize=1)
    absolute = np.abs(lap)
    top = float(np.percentile(absolute, 99.5))
    display = np.zeros_like(gray)
    if top > 0:
        display = (np.clip(absolute / top, 0, 1) ** 0.6 * 255).astype(np.uint8)
    return {"original": image.copy(), "gray": gray, "laplacian": absolute,
            "laplace_preview": display,
            "quality": {"brightness_mean": float(gray.mean()),
                        "brightness_std": float(gray.std()),
                        "laplacian_variance": float(cv2.Laplacian(gray, cv2.CV_64F).var())}}
