"""Coordinates the diagram's services and owns the final inspection decision."""
import threading
import time

from .picture_controller import PictureController
from .picture_inspector import PictureInspector
from .picture_saver import PictureSaver


class InspectionError(RuntimeError):
    def __init__(self, message, inspection_id=None):
        super().__init__(message)
        self.inspection_id = inspection_id


class MainController:
    def __init__(self, settings, picture_controller=None, saver=None, inspector=None):
        self.settings = settings
        self.picture_controller = picture_controller or PictureController(settings)
        self.saver = saver or PictureSaver(settings)
        self.inspector = inspector or PictureInspector(settings)
        self._lock = threading.Lock()

    @staticmethod
    def decide(checks):
        states = [c["state"] for c in checks]
        if "ERROR" in states:
            return "ERROR", "; ".join(c["message"] for c in checks if c["state"] == "ERROR")
        if "FAIL" in states:
            return "REJECT", "; ".join(c["message"] for c in checks if c["state"] == "FAIL")
        if len(checks) != 4 or any(state != "PASS" for state in states):
            return "INCOMPLETE", "; ".join(c["message"] for c in checks if c["state"] != "PASS")
        return "PASS", "All configured checks passed."

    def inspect(self, path=None, scenario="clean", progress=None, requires_operator_review=False):
        if not self._lock.acquire(False):
            raise InspectionError("An inspection is already running.")
        try:
            if requires_operator_review:
                pending = self.pending_review()
                if pending is not None:
                    raise InspectionError("Choose Pass or Reject for inspection #%d before starting the next protector." % pending["id"])
            return self._inspect(path, scenario, progress or (lambda message: None), requires_operator_review)
        finally:
            self._lock.release()

    def _inspect(self, path, scenario, progress, requires_operator_review=False):
        started = time.monotonic()
        inspection_id = None
        try:
            progress("Taking picture..." if path is None else "Loading image...")
            packet = self.picture_controller.acquire(path)
            packet["requires_operator_review"] = bool(requires_operator_review)
            scenario = packet.get("test_scenario", scenario)
            progress("Saving image...")
            inspection_id = self.saver.save_picture(packet, scenario)
        except Exception as exc:
            raise InspectionError("Acquisition or initial storage failed: %s" % exc)
        try:
            progress("Analyzing screen protector...")
            analysis = self.inspector.inspect(packet, inspection_id, scenario)
            if analysis.get("inspection_id") != inspection_id:
                raise RuntimeError("Inspector returned a different inspection ID.")
            decision, reason = self.decide(analysis["checks"])
        except Exception as exc:
            decision, reason = "ERROR", str(exc)
            analysis = {"checks": [], "measurements": {}, "detections": [], "annotated": packet["original"]}
        elapsed_ms = (time.monotonic() - started) * 1000
        try:
            progress("Saving result...")
            self.saver.save_result(inspection_id, decision, reason, analysis, elapsed_ms)
        except Exception as exc:
            raise InspectionError("Result was not confirmed saved for inspection #%d: %s. No final decision is confirmed; record remains PENDING." % (inspection_id, exc), inspection_id)
        return {"id": inspection_id, "decision": decision, "reason": reason,
                "is_demo": self.settings.data["demo"], "elapsed_ms": elapsed_ms,
                "acquired_at": packet["acquired_at"], "captured_at": packet["captured_at"],
                "checks": analysis["checks"], "measurements": analysis["measurements"],
                "detections": analysis["detections"], "annotated": analysis["annotated"]}

    def history(self):
        return self.saver.database.history(self.settings.data["demo"])

    def pending_review(self):
        return self.saver.database.pending_review(self.settings.data["demo"])

    def record_operator_decision(self, inspection_id, decision):
        if not self._lock.acquire(False):
            raise InspectionError("An inspection is already running.")
        try:
            self.saver.save_operator_decision(inspection_id, decision)
            return self.get(inspection_id)
        finally:
            self._lock.release()

    def get(self, inspection_id):
        return self.saver.database.get(inspection_id)

    def image(self, inspection_id, kind="annotated"):
        return self.saver.database.image(inspection_id, kind)

    def statistics(self):
        return self.saver.database.statistics(self.settings.data["demo"])

    def export(self, path, rejects_only=False):
        return self.saver.database.export(path, self.settings.data["demo"], rejects_only)
