"""Verify capture-to-review persistence and upgrades independently of the GUI."""
import csv
import io
import json
import sqlite3
import subprocess
import sys
import zipfile

import pytest

from vdi.application import create_controller
from vdi.camera import Camera
from vdi.config import ROOT, ConfigurationError, Settings
from vdi.database import Database
from vdi.demo import TestCamera as SimulatedCamera
from vdi.main_controller import InspectionError, MainController
from vdi.picture_controller import PictureController


def test_test_camera_advances_all_cases_without_manual_input(profile):
    controller = create_controller(profile, test_camera=True)
    expected = ["PASS", "REJECT", "REJECT", "REJECT", "REJECT", "REJECT",
                "REJECT", "REJECT", "PASS", "ERROR", "PASS"]
    for index, decision in enumerate(expected, 1):
        progress = []
        result = controller.inspect(progress=progress.append, requires_operator_review=True)
        assert result["decision"] == decision
        record = controller.get(result["id"])
        assert record["source"]["kind"] == "test_camera"
        assert record["source"]["camera"]["sequence_number"] == index
        assert record["captured_at"] and record["requires_operator_review"]
        assert record["operator_decision"] is None
        assert progress == ["Taking picture...", "Saving image...",
                            "Analyzing screen protector...", "Saving result..."]
        with pytest.raises(InspectionError, match="Choose Pass or Reject"):
            controller.inspect(requires_operator_review=True)
        assert controller.picture_controller.camera.index == index
        final = controller.record_operator_decision(result["id"], "REJECT")
        assert final["decision"] == decision  # The automatic result never changes.
        assert final["operator_decision"] == "REJECT"
    assert len(controller.history()) == 11


def test_default_controller_uses_physical_camera(profile):
    controller = create_controller(profile)
    assert isinstance(controller.picture_controller.camera, Camera)


@pytest.mark.parametrize("change", ["real", "real_model"])
def test_simulated_camera_cannot_be_used_as_a_real_inspection(profile, change):
    if change == "real":
        profile.data["demo"] = False
    else:
        profile.data["model"]["backend"] = "ultralytics"
    with pytest.raises(ConfigurationError, match="test profile"):
        create_controller(profile, test_camera=True)
    controller = MainController(profile, picture_controller=PictureController(profile, SimulatedCamera()))
    with pytest.raises(InspectionError, match="Simulated camera"):
        controller.inspect(requires_operator_review=True)
    assert controller.history() == []


def test_operator_choice_is_final_validated_and_mode_scoped(profile):
    controller = create_controller(profile, test_camera=True)
    result = controller.inspect(requires_operator_review=True)
    with pytest.raises(ValueError, match="Choose PASS or REJECT"):
        controller.record_operator_decision(result["id"], "maybe")
    assert controller.pending_review()["id"] == result["id"]
    other_settings = Settings(profile.data)
    other_settings.data["demo"] = False
    other = MainController(other_settings)
    with pytest.raises(ValueError, match="not awaiting"):
        other.record_operator_decision(result["id"], "REJECT")
    assert other.pending_review() is None
    final = controller.record_operator_decision(result["id"], "PASS")
    assert final["operator_decision"] == "PASS"
    with pytest.raises(ValueError, match="already saved"):
        controller.record_operator_decision(result["id"], "REJECT")
    assert controller.get(result["id"])["operator_decision"] == "PASS"
    assert controller.pending_review() is None


def test_operator_statistics_and_exports_follow_the_operator_choice(profile, tmp_path):
    controller = create_controller(profile, test_camera=True)
    first = controller.inspect(requires_operator_review=True)  # Automatic PASS.
    controller.record_operator_decision(first["id"], "REJECT")
    second = controller.inspect(requires_operator_review=True)  # Automatic REJECT.
    controller.record_operator_decision(second["id"], "PASS")
    third = controller.inspect(requires_operator_review=True)  # Still awaiting choice.
    stats = controller.statistics()
    assert stats["operator_counts"] == {"PASS": 1, "REJECT": 1, "AWAITING": 1}
    assert stats["operator_pass_rate"] == 0.5
    assert stats["counts"]["PASS"] == 1 and stats["counts"]["REJECT"] == 2
    target = tmp_path / "rejected.zip"
    assert controller.export(target, rejects_only=True) == 1
    with zipfile.ZipFile(str(target)) as archive:
        records = json.loads(archive.read("records.json"))
        assert [r["id"] for r in records] == [first["id"]]
        rows = list(csv.DictReader(io.StringIO(archive.read("results.csv").decode("utf-8-sig"))))
        assert rows[0]["automatic_result"] == "PASS"
        assert rows[0]["operator_decision"] == "REJECT"
        assert "rejected/%06d_original.png" % first["id"] in archive.namelist()
        assert "rejected/%06d_original.png" % second["id"] not in archive.namelist()
        assert "rejected/%06d_original.png" % third["id"] not in archive.namelist()


def test_schema_one_upgrades_without_losing_images_ids_or_results(profile):
    # Keep the test self-contained in the distributed project too: schema v1
    # is precisely the base columns before the three ALTER TABLE additions.
    controller = MainController(profile)
    result = controller.inspect(ROOT / "assets/demo/scratch.png", "scratch")
    before = controller.get(result["id"])
    image = controller.image(result["id"], "original")
    with sqlite3.connect(str(controller.saver.database.path)) as connection:
        for column in ("requires_operator_review", "operator_decision", "operator_decided_at"):
            connection.execute("ALTER TABLE inspections DROP COLUMN " + column)
        connection.execute("PRAGMA user_version=1")
    migrated = Database(controller.saver.database.path)
    after = migrated.get(result["id"])
    assert after["id"] == before["id"]
    for field in ("decision", "checks", "detections", "measurements", "source", "config"):
        assert after[field] == before[field]
    assert migrated.image(result["id"], "original") == image
    assert after["requires_operator_review"] is False
    assert after["operator_decision"] is None
    assert migrated.pending_review(True) is None
    with migrated.connection() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
    # Re-opening is idempotent and AUTOINCREMENT continues after existing IDs.
    reopened = create_controller(profile, test_camera=True)
    assert reopened.inspect(requires_operator_review=True)["id"] > result["id"]


def test_pc_launcher_runs_headless_from_another_directory(tmp_path):
    completed = subprocess.run([sys.executable, str(ROOT / "test_on_pc.py"), "--capture",
                                "--db", str(tmp_path / "launcher.sqlite3")],
                               cwd=str(tmp_path), capture_output=True, text=True, timeout=20)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["is_demo"] is True and result["decision"] == "PASS"
