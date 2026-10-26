import sys
import types

import numpy as np
import pytest

from vdi.camera import Camera, CameraError
from vdi.config import ROOT
from vdi.defect_model import UltralyticsModel
from vdi.image_processing import read_image


def install_fake_ultralytics(monkeypatch, profile, tmp_path, names=None, boxes=None, task="detect"):
    weights = tmp_path / "best.pt"
    weights.write_bytes(b"fake weights for adapter contract tests")
    profile.data["model"]["weights"] = str(weights)
    calls = []

    class FakeBoxes:
        xyxy = np.array([[300, 250, 400, 350], [200, 200, 250, 250]], dtype=float)
        conf = np.array([0.9, 0.1])
        cls = np.array([1, 0], dtype=float)

        def cpu(self):
            return self

        def numpy(self):
            return self

    class FakeYOLO:
        def __init__(self, path, **kwargs):
            self.task = task
            self.names = names if names is not None else {0: "scratch", 1: "crack"}
            calls.append((path, kwargs))

        def predict(self, **kwargs):
            calls.append(kwargs)
            return [types.SimpleNamespace(boxes=boxes if boxes is not None else FakeBoxes())]

    monkeypatch.setitem(sys.modules, "ultralytics", types.SimpleNamespace(YOLO=FakeYOLO))
    return UltralyticsModel(profile), calls


def test_yolo_adapter_maps_boxes_and_uses_configured_arguments(monkeypatch, profile, tmp_path):
    model, calls = install_fake_ultralytics(monkeypatch, profile, tmp_path)
    image = read_image(ROOT / "assets/demo/clean.png")
    detections = model.predict(image)
    assert len(detections) == 1  # Low-confidence detection is filtered.
    assert detections[0]["label"] == "crack"
    assert detections[0]["xyxy"] == [300, 250, 400, 350]
    assert detections[0]["simulated"] is False
    assert calls[1]["source"] is image
    assert calls[1]["conf"] == 0.25 and calls[1]["iou"] == 0.45
    assert calls[1]["imgsz"] == 1024 and calls[1]["device"] == "cpu"
    assert calls[1]["save"] is False
    assert len(model.sha256) == 64


@pytest.mark.parametrize("names", [{0: "crack", 1: "scratch"}, {0: "scratch"}, {0: "scratch", 1: "crack", 2: "good"}])
def test_yolo_adapter_refuses_wrong_class_map(monkeypatch, profile, tmp_path, names):
    model, _ = install_fake_ultralytics(monkeypatch, profile, tmp_path, names=names)
    with pytest.raises(RuntimeError, match="classes differ"):
        model.predict(read_image(ROOT / "assets/demo/clean.png"))


def test_yolo_adapter_refuses_image_classification_task(monkeypatch, profile, tmp_path):
    model, _ = install_fake_ultralytics(monkeypatch, profile, tmp_path, task="classify")
    with pytest.raises(RuntimeError, match="object detection"):
        model.predict(read_image(ROOT / "assets/demo/clean.png"))


def test_yolo_adapter_refuses_invalid_detections(monkeypatch, profile, tmp_path):
    class InvalidBoxes:
        xyxy = np.array([[float("nan"), 0, 200, 200]])
        conf = np.array([0.9])
        cls = np.array([0])

        def cpu(self):
            return self

        def numpy(self):
            return self

    model, _ = install_fake_ultralytics(monkeypatch, profile, tmp_path, boxes=InvalidBoxes())
    with pytest.raises(RuntimeError, match="invalid detection"):
        model.predict(read_image(ROOT / "assets/demo/clean.png"))


def test_camera_missing_device_is_specific_error(profile):
    profile.data["camera"]["device"] = "/dev/not-a-real-vdi-camera"
    with pytest.raises(CameraError, match="not found"):
        Camera(profile.data["camera"]).capture()


def configure_fake_camera(monkeypatch, profile, tmp_path, shape=(1080, 1920, 3)):
    import vdi.camera as module
    device = tmp_path / "camera"
    device.touch()
    config = dict(profile.data["camera"], device=str(device), settle_seconds=0)

    class FakeCapture:
        released = False

        def isOpened(self):
            return True

        def set(self, prop, value):
            return True

        def get(self, prop):
            return module.cv2.VideoWriter_fourcc(*"YUYV")

        def read(self):
            return True, np.zeros(shape, np.uint8)

        def release(self):
            self.released = True

    capture = FakeCapture()
    monkeypatch.setattr(module.cv2, "VideoCapture", lambda *args: capture)
    camera = Camera(config)
    monkeypatch.setattr(camera, "_controls", lambda: {"focus_absolute": 157})
    return camera, capture


def test_camera_releases_device_on_success(monkeypatch, profile, tmp_path):
    camera, capture = configure_fake_camera(monkeypatch, profile, tmp_path)
    image, timestamp, metadata = camera.capture()
    assert image.shape == (1080, 1920, 3)
    assert timestamp.endswith("+00:00")
    assert metadata["controls"]["focus_absolute"] == 157
    assert capture.released


def test_camera_releases_device_on_wrong_resolution(monkeypatch, profile, tmp_path):
    camera, capture = configure_fake_camera(monkeypatch, profile, tmp_path, shape=(480, 640, 3))
    with pytest.raises(CameraError, match="wrong resolution"):
        camera.capture()
    assert capture.released


def test_camera_never_ignores_failed_fixed_controls(monkeypatch, profile):
    import vdi.camera as module
    monkeypatch.setattr(module.shutil, "which", lambda command: "/usr/bin/v4l2-ctl")

    def fail_setting(args, **kwargs):
        if "--list-ctrls" in args:
            return types.SimpleNamespace(returncode=0, stdout="exposure_auto 0x1 (menu)\n", stderr="")
        return types.SimpleNamespace(returncode=1, stdout="", stderr="invalid control")

    monkeypatch.setattr(module.subprocess, "run", fail_setting)
    with pytest.raises(CameraError, match="rejected exposure_auto"):
        Camera(profile.data["camera"])._controls()
