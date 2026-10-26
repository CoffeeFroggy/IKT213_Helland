"""Exercise actual Tk windows and the operator's complete pipeline."""
import os
import threading
import time
import types

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk tests need a display")


def pump(root, until=None, timeout=10):
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        root.update()
        if until is None or until():
            return
        time.sleep(0.01)
    raise AssertionError("GUI did not finish in time")


def enabled(button):
    return not button.instate(["disabled"])


@pytest.fixture
def gui(profile, monkeypatch):
    import tkinter as tk
    import vdi.gui as module
    from vdi.application import create_controller
    errors = []
    monkeypatch.setattr(module.messagebox, "showerror", lambda title, message, **kwargs: errors.append(message))
    root = tk.Tk()
    callback_errors = []
    root.report_callback_exception = lambda typ, value, tb: callback_errors.append(str(value))
    app = module.InspectorGUI(root, profile, create_controller(profile, test_camera=True))
    root.update()
    yield root, app, errors
    if app.busy:
        pump(root, lambda: not app.busy)
    try:
        exists = root.winfo_exists()
    except tk.TclError:
        exists = False
    if exists:
        app.close()
    assert callback_errors == []


def test_one_button_loading_result_manual_choice_and_next_protector(gui, monkeypatch):
    root, app, errors = gui
    assert enabled(app.capture_button)
    assert not enabled(app.pass_button) and not enabled(app.reject_button)
    camera = app.controller.picture_controller.camera
    capture = camera.capture
    release = threading.Event()

    def delayed_capture():
        assert release.wait(4)
        return capture()

    monkeypatch.setattr(camera, "capture", delayed_capture)
    try:
        app.capture_button.invoke()
        root.update()
        assert app.busy
        assert app.result_title.cget("text") == "Loading..."
        assert str(app.progress.cget("mode")) == "indeterminate"
        assert not enabled(app.capture_button)
        assert not enabled(app.pass_button) and not enabled(app.reject_button)
        app.capture()  # A second request during loading does not queue another picture.
    finally:
        release.set()
    pump(root, lambda: not app.busy)
    assert app.result_title.cget("text") == "TEST: No defect detected"
    assert app.automatic_result.get() == "Automatic inspection: PASS"
    assert app.current_image is not None
    assert len(app.history.get_children()) == 1
    assert not enabled(app.capture_button)
    assert enabled(app.pass_button) and enabled(app.reject_button)
    assert app.controller.get(1)["operator_decision"] is None
    app.capture()  # Cannot skip the current operator decision.
    assert len(app.history.get_children()) == 1
    app.reject_button.invoke()  # Operator may override a model/automatic pass.
    assert not enabled(app.pass_button) and not enabled(app.reject_button)
    pump(root, lambda: not app.busy)
    record = app.controller.get(1)
    assert record["decision"] == "PASS"
    assert record["operator_decision"] == "REJECT"
    assert record["operator_decided_at"]
    assert "differs" in app.details.get("1.0", "end")
    assert enabled(app.capture_button)
    assert not enabled(app.pass_button)
    app.capture_button.invoke()
    pump(root, lambda: not app.busy)
    assert app.result_title.cget("text") == "TEST: Scratch"
    assert app.current_image is not None
    app.pass_button.invoke()
    pump(root, lambda: not app.busy)
    assert app.controller.get(2)["decision"] == "REJECT"
    assert app.controller.get(2)["operator_decision"] == "PASS"
    assert "Pass rate: 50.0%" in app.stats_text.get("1.0", "end")
    app.history.selection_set("1")
    app.select_history(None)
    assert app.current_id == 1
    assert not enabled(app.pass_button) and not enabled(app.reject_button)
    assert errors == []


def test_no_file_or_test_case_selection_is_requested(gui, monkeypatch):
    import vdi.gui as module
    root, app, errors = gui

    def forbidden(*args, **kwargs):
        pytest.fail("The operator must never be asked to select an input image")

    monkeypatch.setattr(module.filedialog, "askopenfilename", forbidden)
    app.capture_button.invoke()
    pump(root, lambda: not app.busy)
    assert not hasattr(app, "demo_case")
    assert not hasattr(app, "open_file")
    assert app.current_image is not None
    assert errors == []


def test_camera_error_allows_retry_without_operator_buttons(gui, monkeypatch):
    root, app, errors = gui
    camera = app.controller.picture_controller.camera
    capture = camera.capture

    def broken():
        raise OSError("Camera disconnected")

    monkeypatch.setattr(camera, "capture", broken)
    app.capture_button.invoke()
    pump(root, lambda: not app.busy)
    assert app.result_title.cget("text") == "ERROR"
    assert len(errors) == 1 and "Camera disconnected" in errors[0]
    assert app.current_id is None and app.current_image is None
    assert not app.history.get_children()
    assert enabled(app.capture_button)
    assert not enabled(app.pass_button) and not enabled(app.reject_button)
    monkeypatch.setattr(camera, "capture", capture)
    app.capture_button.invoke()
    pump(root, lambda: not app.busy)
    assert app.current_id == 1 and enabled(app.pass_button)


def test_failed_choice_storage_keeps_picture_and_allows_retry(gui, monkeypatch):
    root, app, errors = gui
    app.capture_button.invoke()
    pump(root, lambda: not app.busy)
    save = app.controller.saver.save_operator_decision

    def broken(*args):
        raise OSError("Disk is read only")

    monkeypatch.setattr(app.controller.saver, "save_operator_decision", broken)
    app.pass_button.invoke()
    pump(root, lambda: not app.busy)
    assert errors and "Disk is read only" in errors[-1]
    assert "not saved" in app.status.get()
    assert app.current_image is not None and app.awaiting_review == 1
    assert app.controller.get(1)["operator_decision"] is None
    assert not enabled(app.capture_button)
    assert enabled(app.pass_button) and enabled(app.reject_button)
    monkeypatch.setattr(app.controller.saver, "save_operator_decision", save)
    app.reject_button.invoke()
    pump(root, lambda: not app.busy)
    assert app.controller.get(1)["operator_decision"] == "REJECT"
    assert enabled(app.capture_button)


def test_model_failure_stays_visible_when_operator_disposes_protector(gui):
    root, app, errors = gui
    app.controller.picture_controller.camera.index = 9
    app.capture_button.invoke()
    pump(root, lambda: not app.busy)
    assert app.result_title.cget("text") == "TEST: Unavailable"
    assert app.automatic_result.get() == "Automatic inspection: ERROR"
    assert "manual disposition" in app.details.get("1.0", "end")
    assert app.current_image is not None and enabled(app.reject_button)
    app.reject_button.invoke()
    pump(root, lambda: not app.busy)
    assert app.controller.get(1)["decision"] == "ERROR"
    assert app.controller.get(1)["operator_decision"] == "REJECT"
    assert errors == []


def test_result_buttons_fit_a_small_desktop_window(gui):
    root, app, errors = gui
    root.geometry("1080x688")
    root.minsize(1080, 688)
    root.update()
    for button in (app.capture_button, app.pass_button, app.reject_button):
        assert button.winfo_height() >= 24
        assert button.winfo_rooty() + button.winfo_height() <= root.winfo_rooty() + root.winfo_height()
        assert button.winfo_rootx() + button.winfo_width() <= root.winfo_rootx() + root.winfo_width()


def test_restart_restores_image_and_pending_choice(gui, profile):
    import tkinter as tk
    from vdi.application import create_controller
    from vdi.gui import InspectorGUI
    root, app, errors = gui
    app.capture_button.invoke()
    pump(root, lambda: not app.busy)
    app.close()
    root2 = tk.Tk()
    restored = InspectorGUI(root2, profile, create_controller(profile, test_camera=True))
    try:
        root2.update()
        assert restored.current_id == restored.awaiting_review == 1
        assert restored.current_image is not None
        assert not enabled(restored.capture_button)
        assert enabled(restored.pass_button) and enabled(restored.reject_button)
        restored.pass_button.invoke()
        pump(root2, lambda: not restored.busy)
        assert enabled(restored.capture_button)
        assert restored.controller.get(1)["operator_decision"] == "PASS"
    finally:
        restored.close()


def test_calibration_gui_saves_the_reviewed_scale(gui, tmp_path, monkeypatch):
    import vdi.calibration_gui as module
    from vdi.config import ROOT, Settings, load_settings
    root, app, errors = gui
    profile = Settings(app.settings.data, path=tmp_path / "inspection.json")
    profile.data["demo"] = False
    selected = ROOT / "assets/demo/clean.png"
    monkeypatch.setattr(module.filedialog, "askopenfilename", lambda **kwargs: str(selected))
    messages = []
    monkeypatch.setattr(module.messagebox, "showinfo", lambda title, message, **kwargs: messages.append(message))
    window = module.CalibrationWindow(root, profile)
    root.update()
    save_button = next(child for frame in window.window.winfo_children() for child in frame.winfo_children()
                       if child.winfo_class() == "TButton" and child.cget("text") == "Save calibration")
    assert save_button.winfo_height() >= 20
    assert save_button.winfo_rooty() + save_button.winfo_height() <= window.window.winfo_rooty() + window.window.winfo_height()
    window.load()
    root.update()
    assert window.contour is not None
    for x, y in [(280, 200), (280, 600)]:
        window.click(types.SimpleNamespace(x=4 + x * window.scale, y=4 + y * window.scale))
    assert len(window.points) == 2
    window.values["reference_length_mm"].set("100")
    window.values["nominal_width_mm"].set("70")
    window.values["nominal_height_mm"].set("150")
    window.values["width_tolerance_mm"].set("2")
    window.values["height_tolerance_mm"].set("2")
    window.reviewed.set(True)
    window.save()
    root.update()
    saved = load_settings(profile.path)
    assert saved.data["geometry"]["mm_per_pixel"] == pytest.approx(0.25)
    assert saved.data["geometry"]["calibration_image_size"] == [800, 800]
    assert saved.resolve(saved.data["geometry"]["reference_image"]).exists()
    assert len(messages) == 1
    assert errors == []
