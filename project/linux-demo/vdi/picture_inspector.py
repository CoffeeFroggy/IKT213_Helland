"""Architecture steps 12-14. Returns evidence; MainController decides PASS/REJECT."""
import cv2
import numpy as np

from .defect_model import make_model
from .geometry import GeometryInspector, check


class PictureInspector:
    def __init__(self, settings, model=None):
        self.settings = settings
        self.geometry = GeometryInspector(settings)
        self.model = model or make_model(settings)

    def inspect(self, packet, inspection_id, scenario="clean"):
        checks, measurements, contour = self.geometry.inspect(packet)
        detections = []
        geometry_passed = all(c["state"] == "PASS" for c in checks)
        if not geometry_passed:
            checks.append(check("defects", "SKIPPED", "Requires completed presence, shape and dimension checks."))
        elif self.model.is_placeholder and not self.settings.data["demo"]:
            checks.append(check("defects", "NOT_READY", "A placeholder cannot approve real protectors. Add the trained model."))
        else:
            try:
                detections = self.model.predict(packet["original"], scenario)
                checks.append(check("defects", "FAIL" if detections else "PASS",
                                    "Detected: " + ", ".join(sorted({d["label"] for d in detections}))
                                    if detections else "No defects above the configured confidence threshold.",
                                    {"model": self.model.name, "simulated": self.model.is_placeholder,
                                     "model_sha256": getattr(self.model, "sha256", None)}))
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
