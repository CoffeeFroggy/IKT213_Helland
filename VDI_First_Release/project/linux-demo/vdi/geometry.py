"""Presence, reference shape and calibrated dimensions, independent of YOLO."""
import hashlib

import cv2
import numpy as np

from .image_processing import prepare, read_image


def check(name, state, message, value=None):
    result = {"name": name, "state": state, "message": message}
    if value is not None:
        result["value"] = value
    return result


def find_protector(packet, config):
    """Return an outer contour in ORIGINAL pixel coordinates, or a specific reason."""
    gray = packet["gray"]
    h, w = gray.shape
    x1, y1, x2, y2 = config["roi"]
    left, top = int(x1 * w), int(y1 * h)
    right, bottom = int(x2 * w), int(y2 * h)
    if right - left < 10 or bottom - top < 10:
        return None, "ROI is too small for contour detection.", None
    source = packet["laplacian"] if config["method"] == "laplacian" else gray
    crop = source[top:bottom, left:right]
    mask = (crop > config["threshold"]).astype(np.uint8) * 255
    k = config["close_kernel"]
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
    contours = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2]
    area = mask.size
    candidates = sorted([c for c in contours if cv2.contourArea(c) >= area * config["min_area_fraction"]],
                        key=cv2.contourArea, reverse=True)
    if not candidates:
        return None, "No reliable protector outline found. Check placement, ROI and lighting.", mask
    c = candidates[0]
    if cv2.contourArea(c) > area * config["max_area_fraction"]:
        return None, "Detected region occupies too much of the ROI; outline is unreliable.", mask
    if len(candidates) > 1 and cv2.contourArea(candidates[1]) >= cv2.contourArea(c) * config["second_object_ratio"]:
        return None, "Multiple large outlines found. Place one protector in the ROI.", mask
    x, y, cw, ch = cv2.boundingRect(c)
    if x <= 1 or y <= 1 or x + cw >= mask.shape[1] - 1 or y + ch >= mask.shape[0] - 1:
        return None, "Outline touches the ROI boundary. Move the protector or enlarge the ROI.", mask
    return c + np.array([[[left, top]]], dtype=np.int32), None, mask


def dimensions(contour):
    rect = cv2.minAreaRect(contour.astype(np.float32))
    short, long = sorted(float(x) for x in rect[1])
    if short <= 0 or long <= 0:
        raise ValueError("Degenerate protector contour.")
    return {"width_px": short, "height_px": long,
            "aspect_ratio": short / long,
            "fill_ratio": float(cv2.contourArea(contour)) / (short * long)}, rect


class GeometryInspector:
    def __init__(self, settings):
        self.settings = settings

    def inspect(self, packet):
        settings = self.settings
        g = settings.data["geometry"]
        contour, reason, _ = find_protector(packet, settings.data["segmentation"])
        checks = []
        values = {}
        if contour is None:
            checks.append(check("presence", "FAIL", reason))
            for name in ("shape", "dimensions"):
                checks.append(check(name, "SKIPPED", "Requires a reliable protector outline."))
            return checks, values, None
        checks.append(check("presence", "PASS", "One complete outer outline detected."))
        measured, _ = dimensions(contour)
        values.update(measured)
        reference_name = g["reference_image"]
        if not reference_name:
            checks.append(check("shape", "NOT_READY", "Choose a known good reference image in Calibration."))
        else:
            reference = settings.resolve(reference_name)
            if not reference.is_file():
                raise ValueError("Reference image not found: %s" % reference)
            ref_packet = prepare(read_image(reference), settings.data["segmentation"])
            ref_c, ref_reason, _ = find_protector(ref_packet, settings.data["segmentation"])
            if ref_c is None:
                raise ValueError("Reference outline is unusable: %s" % ref_reason)
            ref_dims, _ = dimensions(ref_c)
            distance = float(cv2.matchShapes(contour, ref_c, cv2.CONTOURS_MATCH_I1, 0))
            fill_delta = abs(measured["fill_ratio"] - ref_dims["fill_ratio"])
            aspect_delta = abs(measured["aspect_ratio"] / ref_dims["aspect_ratio"] - 1)
            values.update({"shape_distance": distance, "fill_difference": fill_delta,
                           "aspect_relative_difference": aspect_delta,
                           "reference_sha256": hashlib.sha256(reference.read_bytes()).hexdigest()})
            shape_ok = (distance <= g["max_shape_distance"] and
                        fill_delta <= g["max_fill_difference"] and
                        aspect_delta <= g["max_aspect_relative_difference"])
            checks.append(check("shape", "PASS" if shape_ok else "FAIL",
                                "Shape matches reference." if shape_ok else "Shape differs from the expected protector.",
                                {"hu_distance": distance, "fill_difference": fill_delta,
                                 "aspect_relative_difference": aspect_delta}))
        required = ("mm_per_pixel", "nominal_width_mm", "nominal_height_mm",
                    "width_tolerance_mm", "height_tolerance_mm", "calibration_image_size")
        missing = [key for key in required if g[key] is None]
        if missing:
            checks.append(check("dimensions", "NOT_READY", "Calibration is missing: " + ", ".join(missing)))
        elif [packet["gray"].shape[1], packet["gray"].shape[0]] != g["calibration_image_size"]:
            checks.append(check("dimensions", "NOT_READY", "Image resolution differs from the calibration. Recalibrate."))
        else:
            width = measured["width_px"] * g["mm_per_pixel"]
            height = measured["height_px"] * g["mm_per_pixel"]
            values.update({"width_mm": width, "height_mm": height})
            # Tiny floating-point errors must not reject values exactly on a boundary.
            width_ok = abs(width - g["nominal_width_mm"]) <= g["width_tolerance_mm"] + 1e-9
            height_ok = abs(height - g["nominal_height_mm"]) <= g["height_tolerance_mm"] + 1e-9
            checks.append(check("dimensions", "PASS" if width_ok and height_ok else "FAIL",
                                "Dimensions are within tolerance." if width_ok and height_ok else "Width or height is outside tolerance.",
                                {"width_mm": width, "height_mm": height,
                                 "width_ok": width_ok, "height_ok": height_ok}))
        return checks, values, contour
