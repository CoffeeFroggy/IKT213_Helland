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
    assert app.current_page == "welcome"
    app.start_button.invoke()
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
    assert app.controller.statistics()["operator_pass_rate"] == 0.5
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
        assert restored.current_page == "welcome"
        restored.start_button.invoke()
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


def test_welcome_menu_and_placeholder_destinations(gui):
    root, app, errors = gui
    app.home_button.invoke()
    root.update()
    assert app.current_page == "welcome"
    assert app.welcome_title.cget("text") == "Welcome To VDI - Visual Defect Inspector"
    app.stats_button.invoke()
    root.update()
    assert app.current_page == "statistics"
    assert app.pages["statistics"].winfo_ismapped()
    app.home_button.invoke()
    app.guide_button.invoke()
    root.update()
    assert app.current_page == "guide"
    assert app.pages["guide"].winfo_ismapped()
    app.home_button.invoke()
    app.start_button.invoke()
    root.update()
    assert app.current_page == "inspection"
    assert app.instruction_label.cget("text") == "When the protector is placed in the Black Box run the analysis."
    assert app.capture_button.cget("text") == "Run analysis"
    assert errors == []


def test_history_button_and_navigation_preserve_an_unfinished_review(gui):
    root, app, errors = gui
    app.capture_button.invoke()
    pump(root, lambda: not app.busy)
    app.home_button.invoke()
    app.stats_button.invoke()
    app.home_button.invoke()
    app.start_button.invoke()
    assert app.awaiting_review == app.current_id == 1
    assert enabled(app.pass_button) and not enabled(app.capture_button)
    app.reject_button.invoke()
    pump(root, lambda: not app.busy)
    app.history_button.invoke()
    root.update()
    assert app.current_page == "history"
    row = app.history.item("1", "values")
    assert row[1:4] == ("PASS", "REJECT", "No defect detected")
    app.history.selection_set("1")
    app.select_history(None)
    root.update()
    assert app.current_page == "inspection"
    assert app.current_image is not None and not enabled(app.pass_button)
    assert app.verdict_title.cget("text") == "PASS"
    assert errors == []


def test_rounded_buttons_respond_to_mouse_and_keyboard(gui):
    root, app, errors = gui
    app.home_button.invoke()
    root.update()
    button = app.start_button
    button.event_generate("<Button-1>", x=50, y=30)
    button.event_generate("<ButtonRelease-1>", x=50, y=30)
    root.update()
    assert app.current_page == "inspection"
    app.capture_button.focus_force()
    root.update()
    app.capture_button.event_generate("<Return>")
    pump(root, lambda: not app.busy)
    assert app.current_id == 1
    app.capture_button.event_generate("<Return>")
    root.update()
    assert len(app.controller.history()) == 1
    assert errors == []



def test_inspection_has_no_scrollable_boxes_and_keeps_all_results_visible(gui):
    import tkinter as tk
    root, app, errors = gui
    root.geometry("1080x688")
    root.update()
    app.controller.picture_controller.camera.index = 2
    app.capture_button.invoke()
    pump(root, lambda: not app.busy)
    def children(widget):
        for child in widget.winfo_children():
            yield child
            yield from children(child)
    assert not any(isinstance(w, (tk.Text, tk.Scrollbar)) or w.winfo_class() == "TScrollbar"
                   for w in children(app.pages["inspection"]))
    assert app.result_title.cget("text") == "TEST: Crack"
    assert "Confidence:" in app.details.cget("text")
    for widget in (app.check_table, app.verdict_title, app.result_title, app.details,
                   app.pass_button, app.reject_button, app.capture_button):
        assert widget.winfo_ismapped()
        assert widget.winfo_rooty()+widget.winfo_height() <= root.winfo_rooty()+root.winfo_height()
    assert app.details.winfo_reqheight() <= app.details.winfo_height()
    assert app.details.winfo_rooty()+app.details.winfo_height() <= app.classification_card.winfo_rooty()+app.classification_card.winfo_height()
    position = app.verdict_card.winfo_rooty()
    app.check_table.event_generate("<MouseWheel>", delta=-120)
    app.details.event_generate("<MouseWheel>", delta=-120)
    root.update()
    assert app.verdict_card.winfo_rooty() == position
    assert errors == []


def test_buttons_have_filled_surfaces_and_one_outline_color(gui):
    from vdi.ui_widgets import BUTTON_BORDER, BG
    root, app, errors = gui
    root.update()
    for button in app.actions:
        polygons = [i for i in button.find_all() if button.type(i) == "polygon"]
        assert polygons, button.cget("text")
        assert button.itemcget(polygons[0], "outline") == BUTTON_BORDER
        assert button.itemcget(polygons[0], "fill") != BG
        button.set_hover(True)
        assert button.itemcget(button.find_all()[0], "outline") == BUTTON_BORDER
        button.set_hover(False)


def test_history_uses_pages_instead_of_scrolling(gui):
    root, app, errors = gui
    app.history_button.invoke()
    root.update()
    rows = [(str(i), (i, "PASS", "PASS", "No defect detected", "70.00", "150.00", "2026-10-26 07:00"), ())
            for i in range(1, 31)]
    app.history.replace_rows(rows)
    root.update()
    assert app.history.page_count > 1
    next_button = next(b for b in app.actions if b.cget("text") == "Next")
    next_button.invoke()
    root.update()
    assert app.history.page_index == 1
    assert app.history_page_text.get().startswith("Page 2 of")
    app.history.selection_set("30")
    root.update()
    assert app.history.page_index == app.history.page_count-1


@pytest.mark.parametrize("case", [4, 5, 7, 9, "missing_calibration"])
def test_all_failure_summaries_fit_without_scrolling_on_small_screen(gui, case):
    root, app, errors = gui
    root.geometry("1080x688")
    root.update()
    if case == "missing_calibration":
        for key in ("mm_per_pixel", "nominal_width_mm", "nominal_height_mm", "width_tolerance_mm", "height_tolerance_mm"):
            app.settings.data["geometry"][key] = None
    else:
        app.controller.picture_controller.camera.index = case
    app.capture_button.invoke()
    pump(root, lambda: not app.busy)
    assert app.details.winfo_reqheight() <= app.details.winfo_height()
    assert app.details.winfo_rooty()+app.details.winfo_height() <= app.classification_card.winfo_rooty()+app.classification_card.winfo_height()
    assert app.check_table.header_height+6*app.check_table.row_height <= app.check_table.winfo_height()


def test_real_models_run_from_capture_button_and_preserve_operator_review(tmp_path, monkeypatch):
    import tkinter as tk
    pytest.importorskip("torch")
    pytest.importorskip("ultralytics")
    from vdi.config import ROOT, load_settings
    from vdi.image_processing import read_image, utc_now
    from vdi.picture_controller import PictureController
    from vdi.main_controller import MainController
    from vdi.gui import InspectorGUI
    import vdi.gui as gui_module
    errors = []
    monkeypatch.setattr(gui_module.messagebox, "showerror", lambda title, message, **kwargs: errors.append(message))
    settings = load_settings(ROOT / "config/inspection.json")
    settings.data["database"] = str(tmp_path / "real-gui.sqlite3")
    sample = ROOT / "assets/model_checks/20261026_113813_103483_e148a2ca.jpg"
    class CapturedRealImage:
        def capture(self):
            return read_image(sample), utc_now(), {"device": "rig-interface-test", "simulated": False}
    controller = MainController(settings, picture_controller=PictureController(settings, CapturedRealImage()))
    root = tk.Tk()
    app = InspectorGUI(root, settings, controller)
    try:
        root.update()
        assert app.current_page == "welcome"
        app.start_button.invoke()
        app.capture_button.invoke()
        pump(root, lambda: not app.busy, timeout=20)
        assert app.result_title.cget("text") == "No defect detected"
        assert app.verdict_title.cget("text") == "INCOMPLETE"
        values = [app.check_table.item(key, "values") for key in app.check_table.get_children()]
        assert values[1][0] == "Shape class" and values[1][2] == "Correct"
        assert values[-1][-1] == "NOT_READY"
        assert controller.get(1)["source"]["kind"] == "camera"
        assert controller.get(1)["is_demo"] is False
        app.reject_button.invoke()
        pump(root, lambda: not app.busy)
        assert controller.get(1)["operator_decision"] == "REJECT"
        assert controller.get(1)["decision"] == "INCOMPLETE"
        assert errors == []
    finally:
        if app.busy:
            pump(root, lambda: not app.busy, timeout=20)
        app.close()
