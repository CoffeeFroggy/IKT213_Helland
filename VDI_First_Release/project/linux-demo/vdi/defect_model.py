"""Replaceable defect detector. No model dependency is needed for the demo."""
import hashlib
import math
import os


class PlaceholderModel:
    name = "placeholder"
    is_placeholder = True

    def predict(self, image, scenario="clean"):
        if scenario == "model_error":
            raise RuntimeError("Simulated model failure for integration testing.")
        h, w = image.shape[:2]
        labels = {"clean": [], "scratch": ["scratch"], "crack": ["crack"],
                  "both": ["scratch", "crack"]}
        if scenario not in labels:
            raise ValueError("Unknown placeholder scenario: %s" % scenario)
        result = []
        for i, label in enumerate(labels[scenario]):
            result.append({"class_id": 0 if label == "scratch" else 1, "label": label,
                           "confidence": 1.0, "xyxy": [0.42 * w, (0.35 + i * 0.2) * h,
                                                      0.58 * w, (0.45 + i * 0.2) * h],
                           "simulated": True})
        return result


class UltralyticsModel:
    is_placeholder = False

    def __init__(self, settings):
        self.settings = settings
        self._model = None
        self.name = "ultralytics: " + settings.data["model"]["weights"]
        self.sha256 = None

    def _load(self):
        if self._model is not None:
            return
        path = self.settings.resolve(self.settings.data["model"]["weights"])
        if not path.is_file():
            raise RuntimeError("Model file is missing: %s. Add your group's trained weights." % path)
        os.environ["YOLO_AUTOINSTALL"] = "False"
        try:
            from ultralytics import YOLO
        except ImportError:
            raise RuntimeError("Ultralytics is not installed. Follow docs/MODEL_AND_JETSON.md.")
        model = YOLO(str(path), task="detect")
        if getattr(model, "task", None) != "detect":
            raise RuntimeError("Expected an object detection model, not a classification model.")
        names = model.names
        actual = {i: str(names[i]).strip().lower() for i in range(len(names))}
        if actual != {0: "scratch", 1: "crack"}:
            raise RuntimeError("Model classes differ from the report: %s. Expected 0=scratch, 1=crack." % actual)
        self.sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        self._model = model

    def predict(self, image, scenario=None):
        self._load()
        c = self.settings.data["model"]
        predictions = self._model.predict(source=image, conf=c["confidence"], iou=c["iou"],
                                          imgsz=c["image_size"], device=c["device"],
                                          verbose=False, save=False, stream=False)
        if len(predictions) != 1 or predictions[0].boxes is None:
            raise RuntimeError("Model did not return one valid detection result.")
        boxes = predictions[0].boxes.cpu().numpy()
        detections = []
        h, w = image.shape[:2]
        for xyxy, conf, cls in zip(boxes.xyxy, boxes.conf, boxes.cls):
            values = [float(v) for v in xyxy]
            confidence = float(conf)
            class_number = float(cls)
            if (not all(math.isfinite(v) for v in values + [confidence, class_number]) or
                    class_number not in (0.0, 1.0) or not 0 <= confidence <= 1):
                raise RuntimeError("Model returned an invalid detection.")
            if confidence < c["confidence"]:
                continue
            x1, y1, x2, y2 = values
            x1, x2 = max(0., min(w, x1)), max(0., min(w, x2))
            y1, y2 = max(0., min(h, y1)), max(0., min(h, y2))
            if x2 <= x1 or y2 <= y1:
                raise RuntimeError("Model returned an empty defect box.")
            class_id = int(class_number)
            detections.append({"class_id": class_id, "label": ("scratch", "crack")[class_id],
                               "confidence": confidence, "xyxy": [x1, y1, x2, y2],
                               "simulated": False})
        return detections


def make_model(settings):
    return PlaceholderModel() if settings.data["model"]["backend"] == "placeholder" else UltralyticsModel(settings)
