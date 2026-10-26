"""Verify model hashes and run the supplied real-image regression examples."""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    from vdi.config import load_settings
    from vdi.main_controller import MainController
    expected_hashes = json.loads((ROOT / "models/checksums.json").read_text())
    for name, expected in expected_hashes.items():
        path = ROOT / "models" / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError("Model checksum does not match the supplied model: " + name)
    profile = load_settings(ROOT / "config/inspection.json")
    with tempfile.TemporaryDirectory(prefix="vdi-model-check-") as directory:
        profile.data["database"] = str(Path(directory) / "checks.sqlite3")
        controller = MainController(profile)
        for item in json.loads((ROOT / "assets/model_checks/expected.json").read_text()):
            result = controller.inspect(ROOT / "assets/model_checks" / item["file"])
            shape = result["measurements"]["shape_classification"]
            if shape["status"] != item["shape"]:
                raise RuntimeError("Shape regression mismatch: %s: %s" % (item["file"], shape))
            defects = next(c for c in result["checks"] if c["name"] == "defects")
            expected_labels = item["labels"]
            actual_labels = sorted(d["label"] for d in result["detections"])
            if defects["state"] == "ERROR" or actual_labels != expected_labels:
                raise RuntimeError("Defect regression mismatch: %s: %s" % (item["file"], defects))
            if item["defect_status"] == "not_performed" and defects["state"] != "SKIPPED":
                raise RuntimeError("Defect model should have been skipped: " + item["file"])
            print("OK: %s | shape=%s | defects=%s | system=%s" % (item["file"], shape["status"], ",".join(actual_labels) or defects["state"], result["decision"]))
    print("Both trained models verified on the four supplied examples. This is not a camera or accuracy benchmark.")
    print("Width/height remain uncalibrated until real geometry calibration is completed.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("Model setup check failed: %s" % exc, file=sys.stderr)
        sys.exit(1)
