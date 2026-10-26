"""Trained shape gate, real detector and unchanged persistence contract."""
import json
from pathlib import Path
import pytest

from vdi.config import ROOT, load_settings
from vdi.defect_model import filter_scratch_duplicates
from vdi.main_controller import MainController
from vdi.picture_inspector import PictureInspector


def settings_for_model_test(tmp_path):
    settings = load_settings(ROOT / "config/inspection.json")
    settings.data["database"] = str(tmp_path / "models.sqlite3")
    return settings


class ShapeResult:
    def __init__(self, status):
        self.status = status

    def classify(self, image):
        return {"status": self.status, "reason": "fixture", "confidence": .99,
                "predicted_class": self.status, "probabilities": {}, "margin": .98,
                "thresholds": {"correct_shape": .9, "shape_defect": .85, "no_protector": .9},
                "required_margin": .2}


class ObservedDetector:
    name = "observed real-model interface"
    is_placeholder = False

    def __init__(self):
        self.calls = 0

    def predict(self, image, scenario=None):
        self.calls += 1
        return []


@pytest.mark.parametrize("status,decision,detector_calls", [("correct_shape", "INCOMPLETE", 1),
    ("shape_defect", "REJECT", 0), ("no_protector", "REJECT", 0),
    ("uncertain", "INCOMPLETE", 0), ("unavailable", "ERROR", 0)])
def test_learned_shape_gate_and_uncalibrated_size(tmp_path, status, decision, detector_calls):
    settings = settings_for_model_test(tmp_path)
    detector = ObservedDetector()
    inspector = PictureInspector(settings, detector, ShapeResult(status))
    controller = MainController(settings, inspector=inspector)
    result = controller.inspect(ROOT / "assets/demo/clean.png")
    assert result["decision"] == decision
    assert detector.calls == detector_calls
    assert controller.get(result["id"])["measurements"]["shape_classification"]["status"] == status
    dimensions = next(c for c in result["checks"] if c["name"] == "dimensions")
    assert dimensions["state"] != "PASS"
    defects = next(c for c in result["checks"] if c["name"] == "defects")
    assert defects["state"] == ("PASS" if detector_calls else "SKIPPED")


def test_scratch_duplicate_filter_preserves_crack_boxes():
    def item(label, confidence):
        return {"label": label, "confidence": confidence, "xyxy": [0, 0, 100, 100]}
    rows = [item("scratch", .95), item("scratch", .90), item("crack", .85)]
    filtered = filter_scratch_duplicates(rows, .7)
    assert [(d["label"], d["confidence"]) for d in filtered] == [("scratch", .95), ("crack", .85)]
    assert len(rows) == 3


def test_actual_trained_models_match_the_supplied_examples(tmp_path):
    pytest.importorskip("torch")
    pytest.importorskip("ultralytics")
    controller = MainController(settings_for_model_test(tmp_path))
    for case in json.loads((ROOT / "assets/model_checks/expected.json").read_text()):
        result = controller.inspect(ROOT / "assets/model_checks" / case["file"])
        record = controller.get(result["id"])
        assert result["is_demo"] is False
        assert record["measurements"]["shape_classification"]["status"] == case["shape"]
        assert sorted(d["label"] for d in result["detections"]) == case["labels"]
        check = next(c for c in result["checks"] if c["name"] == "defects")
        assert check["state"] != "ERROR"
        if case["defect_status"] == "not_performed":
            assert check["state"] == "SKIPPED"
        elif not case["labels"]:
            assert result["decision"] == "INCOMPLETE"  # Uncalibrated size cannot pass.
        else:
            assert result["decision"] == "REJECT"
        assert len(record["measurements"]["shape_classification"]["model_sha256"]) == 64


def test_shape_preprocessing_refuses_untrained_frame_aspect_ratio():
    from PIL import Image
    from vdi.shape_classifier import prepare_pil, PREPROCESS
    with pytest.raises(ValueError, match="sideforhold"):
        prepare_pil(Image.new("RGB", (800, 800)), PREPROCESS)
    assert prepare_pil(Image.new("RGB", (1920, 1080)), PREPROCESS).size == (448, 448)
