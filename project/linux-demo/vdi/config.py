"""Configuration paths are relative to the project, never the shell directory."""
import copy
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ConfigurationError(ValueError):
    pass


def number(value, name, minimum=0, allow_zero=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigurationError("%s must be a number." % name)
    if not math.isfinite(value) or value < minimum or (not allow_zero and value == minimum):
        raise ConfigurationError("%s is outside the allowed range." % name)
    return value


class Settings:
    def __init__(self, data, path=None):
        self.data = copy.deepcopy(data)
        self.path = Path(path).resolve() if path else None
        self.validate()

    def resolve(self, value):
        p = Path(value).expanduser()
        return p.resolve() if p.is_absolute() else (ROOT / p).resolve()

    def validate(self):
        d = self.data
        try:
            if not isinstance(d["demo"], bool):
                raise ConfigurationError("demo must be true or false.")
            if d["model"]["backend"] not in ("placeholder", "ultralytics"):
                raise ConfigurationError("model.backend must be placeholder or ultralytics.")
            number(d["model"]["confidence"], "model.confidence")
            number(d["model"]["iou"], "model.iou")
            if d["model"]["confidence"] > 1 or d["model"]["iou"] > 1:
                raise ConfigurationError("Model thresholds must be at most 1.")
            if not isinstance(d["model"]["image_size"], int) or d["model"]["image_size"] <= 0:
                raise ConfigurationError("model.image_size must be a positive integer.")
            if d["model"]["input"] != "original_bgr":
                raise ConfigurationError("Only original_bgr is supported until training preprocessing is confirmed.")
            s = d["segmentation"]
            roi = s["roi"]
            if len(roi) != 4 or not (0 <= roi[0] < roi[2] <= 1 and 0 <= roi[1] < roi[3] <= 1):
                raise ConfigurationError("roi must be normalized [left, top, right, bottom].")
            if s["method"] not in ("laplacian", "brightness"):
                raise ConfigurationError("segmentation.method must be laplacian or brightness.")
            for key in ("gaussian_kernel", "close_kernel"):
                k = s[key]
                if not isinstance(k, int) or isinstance(k, bool) or k < 1 or k % 2 == 0:
                    raise ConfigurationError("%s must be a positive odd integer." % key)
            number(s["threshold"], "segmentation.threshold", allow_zero=True)
            if s["threshold"] > 255:
                raise ConfigurationError("threshold must be at most 255.")
            number(s["min_area_fraction"], "min_area_fraction")
            number(s["max_area_fraction"], "max_area_fraction")
            if not s["min_area_fraction"] < s["max_area_fraction"] < 1:
                raise ConfigurationError("Area fractions must satisfy 0 < min < max < 1.")
            number(s["second_object_ratio"], "second_object_ratio")
            if s["second_object_ratio"] > 1:
                raise ConfigurationError("second_object_ratio must be <= 1.")
            g = d["geometry"]
            for key in ("max_shape_distance", "max_fill_difference", "max_aspect_relative_difference"):
                number(g[key], "geometry." + key)
            for key in ("mm_per_pixel", "nominal_width_mm", "nominal_height_mm"):
                if g[key] is not None:
                    number(g[key], "geometry." + key)
            for key in ("width_tolerance_mm", "height_tolerance_mm"):
                if g[key] is not None:
                    number(g[key], "geometry." + key, allow_zero=True)
            if g["nominal_width_mm"] and g["nominal_height_mm"] and g["nominal_width_mm"] >= g["nominal_height_mm"]:
                raise ConfigurationError("Width is the shorter side; nominal width must be below height.")
            size = g["calibration_image_size"]
            if size is not None and (len(size) != 2 or any(not isinstance(x, int) or x <= 0 for x in size)):
                raise ConfigurationError("calibration_image_size must be [width_px, height_px].")
            for key in ("width", "height", "warmup_frames", "flush_frames"):
                if not isinstance(d["camera"][key], int) or d["camera"][key] <= 0:
                    raise ConfigurationError("camera.%s must be a positive integer." % key)
            if not isinstance(d["camera"]["controls"], dict):
                raise ConfigurationError("camera.controls must be a mapping.")
            if any(not isinstance(v, int) or isinstance(v, bool) for v in d["camera"]["controls"].values()):
                raise ConfigurationError("Camera control values must be integers.")
            number(d["camera"]["settle_seconds"], "camera.settle_seconds", allow_zero=True)
            if not d["database"]:
                raise ConfigurationError("database path is required.")
        except (KeyError, TypeError) as exc:
            raise ConfigurationError("Missing or invalid configuration field: %s" % exc)


def load_settings(path=None):
    p = Path(path).expanduser().resolve() if path else ROOT / "config/demo.json"
    try:
        with p.open(encoding="utf-8") as f:
            return Settings(json.load(f), p)
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError("Cannot read configuration %s: %s" % (p, exc))
