"""Architecture steps 12-14. Returns evidence; MainController decides PASS/REJECT."""
import cv2
import numpy as np

from .defect_model import make_model
from .geometry import GeometryInspector, check, find_protector, dimensions


class PictureInspector:
    def __init__(self, settings, model=None, shape_engine=None):
        self.settings = settings
        self.geometry = GeometryInspector(settings)
        self.model = model or make_model(settings)
        self.shape_engine = shape_engine
        if shape_engine is None and settings.data.get("shape", {}).get("backend") in ("mobilenet", "onnx"):
            config = settings.data["shape"]
            if config["backend"] == "onnx":
                from .onnx_models import OnnxShapeClassifier as ShapeClassifier
            else:
                from .shape_classifier import ShapeClassifier
            self.shape_engine = ShapeClassifier(settings.resolve(config["weights"]), config.get("device", "cpu"))

    def inspect(self, packet, inspection_id, scenario="clean"):
        if self.shape_engine is not None:
            checks, measurements, contour = self.learned_checks(packet)
            geometry_passed = measurements["shape_classification"]["status"] == "correct_shape"
        else:
            checks, measurements, contour = self.geometry.inspect(packet)
            geometry_passed = all(c["state"] == "PASS" for c in checks)
        detections = []
        if not geometry_passed:
            checks.append(check("defects", "SKIPPED", "Requires a confident correct-shape result." if self.shape_engine is not None else "Requires completed presence, shape and dimension checks."))
        elif self.model.is_placeholder and not self.settings.data["demo"]:
            checks.append(check("defects", "NOT_READY", "A placeholder cannot approve real protectors. Add the trained model."))
        else:
            try:
                detections = self.model.predict(packet["original"], scenario)
                checks.append(check("defects", "FAIL" if detections else "PASS",
                                    "Detected: " + ", ".join(sorted({d["label"] for d in detections}))
                                    if detections else "No defects above the configured confidence threshold.",
                                    {"model": self.model.name, "simulated": self.model.is_placeholder,
                                     "model_sha256": getattr(self.model, "sha256", None),
                                     "raw_detections": getattr(self.model, "last_raw_detections", None)}))
            except Exception as exc:
                checks.append(check("defects", "ERROR", "Defect model failed: %s" % exc))
        annotated = packet["original"].copy()
        if contour is not None:
            cv2.drawContours(annotated, [contour], -1, (0, 220, 70), 2)
            box = cv2.boxPoints(cv2.minAreaRect(contour)).astype(np.int32)
            cv2.polylines(annotated, [box], True, (0, 210, 255), 2)
        for d in detections:
            x1, y1, x2, y2 = [int(round(x)) for x in d["xyxy"]]
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (30, 30, 240), 2)
            text = ("DEMO " if d["simulated"] else "") + "%s %.2f" % (d["label"], d["confidence"])
            cv2.putText(annotated, text, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (30, 30, 240), 2)
        return {"inspection_id": inspection_id, "checks": checks, "measurements": measurements,
                "detections": detections, "annotated": annotated}


    def learned_checks(self, packet):
        result = self.shape_engine.classify(packet["original"])
        status = result["status"]
        values = {"shape_classification": result}
        contour = None
        if status == "correct_shape":
            checks = [check("presence", "PASS", "Screen protector detected by the trained model."),
                      check("shape", "PASS", "Trained model classified the correct shape.", result)]
        elif status == "shape_defect":
            checks = [check("presence", "PASS", "Screen protector detected by the trained model."),
                      check("shape", "FAIL", "Trained model detected an incorrect or incomplete shape.", result)]
        elif status == "no_protector":
            checks = [check("presence", "FAIL", "Trained model detected no screen protector.", result),
                      check("shape", "SKIPPED", "No screen protector.")]
        else:
            error = status == "unavailable" or result.get("reason") == "shape_analysis_error"
            state = "ERROR" if error else "UNCERTAIN"
            message = "Shape model: " + str(result.get("detail") or result.get("reason") or status)
            checks = [check("presence", state, message), check("shape", state, message, result)]
        if status != "correct_shape":
            checks.append(check("dimensions", "SKIPPED", "Requires a confident correct-shape result."))
            return checks, values, contour
        config = self.settings.data["geometry"]
        required = ("mm_per_pixel", "nominal_width_mm", "nominal_height_mm", "width_tolerance_mm",
                    "height_tolerance_mm", "calibration_image_size")
        if any(config[key] is None for key in required):
            checks.append(check("dimensions", "NOT_READY", "Width/height are not calibrated; millimetre dimensions were not checked."))
        elif list(reversed(packet["gray"].shape)) != config["calibration_image_size"]:
            checks.append(check("dimensions", "NOT_READY", "Image resolution differs from calibration."))
        else:
            contour, reason, _ = find_protector(packet, self.settings.data["segmentation"])
            if contour is None:
                checks.append(check("dimensions", "NOT_READY", "No reliable measurement contour: " + reason))
            else:
                measured, _ = dimensions(contour)
                values.update(measured)
                width = measured["width_px"]*config["mm_per_pixel"]
                height = measured["height_px"]*config["mm_per_pixel"]
                values.update(width_mm=width, height_mm=height)
                width_ok = abs(width-config["nominal_width_mm"]) <= config["width_tolerance_mm"]+1e-9
                height_ok = abs(height-config["nominal_height_mm"]) <= config["height_tolerance_mm"]+1e-9
                checks.append(check("dimensions", "PASS" if width_ok and height_ok else "FAIL",
                                    "Dimensions are within tolerance." if width_ok and height_ok else "Width or height is outside tolerance.",
                                    {"width_mm": width, "height_mm": height, "width_ok": width_ok, "height_ok": height_ok}))
        # Missing size calibration never suppresses the real shape/surface test,
        # but it continues to prevent an overall automatic PASS in MainController.
        return checks, values, contour
