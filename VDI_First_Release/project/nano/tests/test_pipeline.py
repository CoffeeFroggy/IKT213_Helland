import json
import sqlite3
import zipfile
from pathlib import Path

import cv2
import numpy as np
import pytest

from vdi.config import ROOT, Settings, ConfigurationError, load_settings
from vdi.database import Database
from vdi.geometry import find_protector
from vdi.image_processing import decode_png, encode_png, prepare, read_image
from vdi.main_controller import MainController, InspectionError
from vdi.picture_controller import PictureController
from vdi.picture_inspector import PictureInspector
from vdi.picture_saver import PictureSaver


@pytest.mark.parametrize("asset,scenario,decision,failed", [
    ("clean", "clean", "PASS", None),
    ("scratch", "scratch", "REJECT", "defects"),
    ("crack", "crack", "REJECT", "defects"),
    ("both", "both", "REJECT", "defects"),
    ("empty", "clean", "REJECT", "presence"),
    ("wrong_shape", "clean", "REJECT", "shape"),
    ("missing_piece", "clean", "REJECT", "shape"),
    ("wrong_size", "clean", "REJECT", "dimensions"),
    ("rotated", "clean", "PASS", None),
    ("clean", "model_error", "ERROR", "defects"),
])
def test_end_to_end(profile, asset, scenario, decision, failed):
    c = MainController(profile)
    result = c.inspect(ROOT / "assets/demo" / (asset + ".png"), scenario)
    record = c.get(result["id"])
    assert result["decision"] == decision == record["decision"]
    assert record["is_demo"] is True
    assert record["captured_at"] is None
    assert record["completed_at"]
    assert record["config"]["model"]["backend"] == "placeholder"
    if failed:
        assert any(check["name"] == failed and check["state"] in ("FAIL", "ERROR") for check in record["checks"])
    original = read_image(ROOT / "assets/demo" / (asset + ".png"))
    np.testing.assert_array_equal(decode_png(c.image(record["id"], "original")), original)
    if asset == "clean" and decision == "PASS":
        assert record["measurements"]["width_mm"] == pytest.approx(70)
        assert record["measurements"]["height_mm"] == pytest.approx(150)


def test_image_and_id_exist_before_inspection(profile):
    saver = PictureSaver(profile)
    real_inspector = PictureInspector(profile)

    class ObservedInspector:
        def inspect(self, packet, inspection_id, scenario):
            rows = saver.database.history(True)
            assert len(rows) == 1 and rows[0]["decision"] == "PENDING"
            np.testing.assert_array_equal(decode_png(saver.database.image(rows[0]["id"], "original")), packet["original"])
            assert inspection_id == rows[0]["id"]
            return real_inspector.inspect(packet, inspection_id, scenario)

    result = MainController(profile, saver=saver, inspector=ObservedInspector()).inspect(ROOT / "assets/demo/clean.png")
    assert result["id"] == 1
    assert saver.database.get(1)["decision"] == "PASS"


def test_missing_calibration_never_passes(profile):
    profile.data["geometry"]["mm_per_pixel"] = None
    c = MainController(profile)
    result = c.inspect(ROOT / "assets/demo/clean.png")
    assert result["decision"] == "INCOMPLETE"
    assert result["checks"][-1]["state"] == "SKIPPED"


def test_resolution_change_invalidates_calibration(profile, tmp_path):
    profile.data["geometry"]["calibration_image_size"] = [1920, 1080]
    result = MainController(profile).inspect(ROOT / "assets/demo/clean.png")
    assert result["decision"] == "INCOMPLETE"
    assert "resolution" in result["reason"]


def test_non_demo_placeholder_cannot_pass(profile):
    profile.data["demo"] = False
    c = MainController(profile)
    result = c.inspect(ROOT / "assets/demo/clean.png")
    assert result["decision"] == "INCOMPLETE"
    assert result["is_demo"] is False
    assert "placeholder" in result["reason"]


def test_missing_model_is_saved_error_not_empty_detections_pass(profile):
    profile.data["demo"] = False
    profile.data["model"]["backend"] = "ultralytics"
    profile.data["model"]["weights"] = "models/no_such_model.pt"
    c = MainController(profile)
    result = c.inspect(ROOT / "assets/demo/clean.png")
    assert result["decision"] == "ERROR"
    assert c.get(result["id"])["checks"][-1]["state"] == "ERROR"
    assert result["measurements"]["width_mm"] == pytest.approx(70)


@pytest.mark.parametrize("name,content", [("bad.jpg", b"not a jpeg"), ("empty.png", b""), ("bad.txt", b"text")])
def test_invalid_import_makes_no_database_record(profile, tmp_path, name, content):
    path = tmp_path / name
    path.write_bytes(content)
    c = MainController(profile)
    with pytest.raises(InspectionError, match="Acquisition"):
        c.inspect(path)
    assert c.history() == []


def test_failed_initial_storage_stops_analysis(profile):
    class BrokenSaver:
        def save_picture(self, packet, scenario):
            raise OSError("disk full")

    class MustNotRun:
        def inspect(self, packet, inspection_id, scenario):
            pytest.fail("Inference must not run before persistent image storage")

    with pytest.raises(InspectionError, match="disk full"):
        MainController(profile, saver=BrokenSaver(), inspector=MustNotRun()).inspect(ROOT / "assets/demo/clean.png")


def test_failed_result_storage_leaves_pending_and_no_confirmed_pass(profile):
    class BrokenResultSaver(PictureSaver):
        def save_result(self, *args):
            raise OSError("read-only filesystem")

    saver = BrokenResultSaver(profile)
    c = MainController(profile, saver=saver)
    with pytest.raises(InspectionError, match="not confirmed saved") as exc:
        c.inspect(ROOT / "assets/demo/clean.png")
    assert exc.value.inspection_id == 1
    assert saver.database.get(1)["decision"] == "PENDING"


def test_ids_unique_even_when_importing_same_file(profile):
    c = MainController(profile)
    a = c.inspect(ROOT / "assets/demo/clean.png")
    b = c.inspect(ROOT / "assets/demo/clean.png")
    assert a["id"] != b["id"]
    assert len(c.history()) == 2


def test_capture_records_capture_time_and_metadata(profile):
    class FakeCamera:
        def capture(self):
            return read_image(ROOT / "assets/demo/clean.png"), "2026-10-25T10:00:00+00:00", {"device": "fake", "controls": {"focus_absolute": 157}}

    pc = PictureController(profile, FakeCamera())
    c = MainController(profile, picture_controller=pc)
    result = c.inspect()
    record = c.get(result["id"])
    assert record["captured_at"] == "2026-10-25T10:00:00+00:00"
    assert record["source"]["camera"]["controls"]["focus_absolute"] == 157


def test_geometry_failure_prevents_model_execution(profile):
    class NeverModel:
        name = "test"
        is_placeholder = False

        def predict(self, image, scenario):
            pytest.fail("A missing protector must not reach the model")

    c = MainController(profile, inspector=PictureInspector(profile, NeverModel()))
    result = c.inspect(ROOT / "assets/demo/empty.png")
    assert result["decision"] == "REJECT"
    assert result["checks"][-1]["state"] == "SKIPPED"


def test_model_receives_original_bgr_unmodified(profile):
    expected = read_image(ROOT / "assets/demo/clean.png")

    class ObserveModel:
        name = "test detector"
        is_placeholder = False

        def predict(self, image, scenario):
            np.testing.assert_array_equal(image, expected)
            return []

    c = MainController(profile, inspector=PictureInspector(profile, ObserveModel()))
    assert c.inspect(ROOT / "assets/demo/clean.png")["decision"] == "PASS"


def test_statistics_and_exports_keep_modes_separate(profile, tmp_path):
    c = MainController(profile)
    a = c.inspect(ROOT / "assets/demo/clean.png")
    b = c.inspect(ROOT / "assets/demo/both.png", "both")
    c.inspect(ROOT / "assets/demo/clean.png", "model_error")
    other = Settings(profile.data)
    other.data["demo"] = False
    MainController(other).inspect(ROOT / "assets/demo/clean.png")
    stats = c.statistics()
    assert stats["total"] == 3
    assert stats["pass_rate"] == 0.5
    assert stats["categories"]["scratch"] == stats["categories"]["crack"] == 1
    out = tmp_path / "rejects.zip"
    assert c.export(out, rejects_only=True) == 1
    with zipfile.ZipFile(out) as z:
        records = json.loads(z.read("records.json"))
        assert len(records) == 1 and records[0]["id"] == b["id"]
        assert "rejected/%06d_original.png" % b["id"] in z.namelist()
        assert "rejected/%06d_original.png" % a["id"] not in z.namelist()
    csv = tmp_path / "all.csv"
    assert c.export(csv) == 3
    assert "scratch" in csv.read_text(encoding="utf-8-sig")


def test_reference_missing_is_error(profile):
    profile.data["geometry"]["reference_image"] = "assets/does-not-exist.png"
    result = MainController(profile).inspect(ROOT / "assets/demo/clean.png")
    assert result["decision"] == "ERROR"


def test_boundary_contour_rejected(profile):
    image = np.full((800, 800, 3), 12, np.uint8)
    cv2.rectangle(image, (0, 100), (300, 700), (110, 110, 110), -1)
    packet = prepare(image, profile.data["segmentation"])
    contour, reason, _ = find_protector(packet, profile.data["segmentation"])
    assert contour is None and "boundary" in reason


def test_multiple_protectors_rejected(profile):
    image = np.full((800, 800, 3), 12, np.uint8)
    cv2.rectangle(image, (50, 100), (300, 700), (110, 110, 110), -1)
    cv2.rectangle(image, (450, 100), (700, 700), (110, 110, 110), -1)
    contour, reason, _ = find_protector(prepare(image, profile.data["segmentation"]), profile.data["segmentation"])
    assert contour is None and "Multiple" in reason


def test_dimension_tolerance_boundary_is_inclusive(profile):
    profile.data["geometry"]["nominal_width_mm"] = 72
    profile.data["geometry"]["nominal_height_mm"] = 152
    assert MainController(profile).inspect(ROOT / "assets/demo/clean.png")["decision"] == "PASS"


def test_invalid_state_transition_cannot_overwrite_result(profile):
    c = MainController(profile)
    result = c.inspect(ROOT / "assets/demo/clean.png")
    analysis = {"checks": [], "measurements": {}, "detections": []}
    with pytest.raises(RuntimeError, match="already been completed"):
        c.saver.database.complete(result["id"], "REJECT", "overwrite", analysis, 1)
    assert c.get(result["id"])["decision"] == "PASS"


def test_incompatible_database_is_not_modified(tmp_path):
    path = tmp_path / "future.sqlite3"
    with sqlite3.connect(str(path)) as con:
        con.execute("PRAGMA user_version=999")
    with pytest.raises(RuntimeError, match="Unsupported"):
        Database(path)


@pytest.mark.parametrize("field,value", [("mm_per_pixel", 0), ("nominal_width_mm", -1), ("width_tolerance_mm", -1), ("mm_per_pixel", float("nan"))])
def test_invalid_geometry_settings(profile, field, value):
    profile.data["geometry"][field] = value
    with pytest.raises(ConfigurationError):
        Settings(profile.data)


def test_laplacian_pipeline_preserves_faint_outline(profile):
    image = np.full((800, 800, 3), 12, np.uint8)
    cv2.rectangle(image, (260, 100), (540, 700), (100, 100, 100), 3)
    s = dict(profile.data["segmentation"], method="laplacian", threshold=2)
    packet = prepare(image, s)
    contour, reason, _ = find_protector(packet, s)
    assert contour is not None, reason


def test_controller_rejects_concurrent_work(profile):
    c = MainController(profile)
    c._lock.acquire()
    try:
        with pytest.raises(InspectionError, match="already running"):
            c.inspect(ROOT / "assets/demo/clean.png")
    finally:
        c._lock.release()


def test_inspector_cannot_change_database_identity(profile):
    class WrongIDInspector:
        def inspect(self, packet, inspection_id, scenario):
            return {"inspection_id": inspection_id + 1}
    c = MainController(profile, inspector=WrongIDInspector())
    result = c.inspect(ROOT / "assets/demo/clean.png")
    assert result["id"] == 1 and result["decision"] == "ERROR"
    assert "different inspection ID" in result["reason"]
