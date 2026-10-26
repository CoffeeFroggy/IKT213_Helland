"""VDI desktop pages: welcome, inspection, history and future destinations."""
import queue
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from tkinter import filedialog, messagebox, ttk

import cv2
from PIL import Image, ImageTk

from .application import create_controller
from .calibration_gui import CalibrationWindow
from .image_processing import decode_png
from .ui_typography import SmoothLabel, text_bitmap
from .ui_table import DataTable
from .ui_widgets import BG, PANEL, BORDER, TEAL, TEXT, MUTED, GREEN, RED, RoundedButton

CAPTURE_LABEL = "Run analysis"
INSTRUCTION = "When the protector is placed in the Black Box run the analysis."


def model_classification(record):
    shape = record["measurements"].get("shape_classification", {})
    names = {"shape_defect": "Wrong shape", "no_protector": "No protector", "uncertain": "Shape uncertain", "unavailable": "Shape unavailable"}
    if shape.get("status") in names:
        return names[shape["status"]]
    labels = {d["label"] for d in record["detections"]}
    if labels:
        return " + ".join(label.capitalize() for label in ("scratch", "crack") if label in labels)
    check = next((c for c in record["checks"] if c["name"] == "defects"), None)
    if check and check["state"] == "PASS":
        return "No defect detected"
    if check and check["state"] == "SKIPPED":
        return "Not run"
    return "Unavailable"


def comparison_rows(record):
    """Use each record's saved configuration, including when viewing history."""
    checks = {c["name"]: c for c in record["checks"]}
    values = record["measurements"]
    geometry = record["config"]["geometry"]
    presence = checks.get("presence", {}).get("state", "SKIPPED")
    shape = checks.get("shape", {}).get("state", "SKIPPED")
    dimensions = checks.get("dimensions", {}).get("state", "SKIPPED")
    rows = [("Presence", "Present", "Detected" if presence == "PASS" else "Not reliable" if presence == "FAIL" else "-", presence)]
    for title, key, limit in [("Shape score", "shape_distance", "max_shape_distance"),
                              ("Fill diff.", "fill_difference", "max_fill_difference"),
                              ("Aspect diff.", "aspect_relative_difference", "max_aspect_relative_difference")]:
        actual, expected = values.get(key), geometry.get(limit)
        state = ("PASS" if actual <= expected else "FAIL") if actual is not None and expected is not None else shape
        rows.append((title, "<= %.4f" % expected if expected is not None else "Not configured",
                     "%.4f" % actual if actual is not None else "-", state))
    for title, key, nominal, tolerance in [("Width", "width_mm", "nominal_width_mm", "width_tolerance_mm"),
                                           ("Height", "height_mm", "nominal_height_mm", "height_tolerance_mm")]:
        actual, expected, margin = values.get(key), geometry.get(nominal), geometry.get(tolerance)
        configured = expected is not None and margin is not None
        state = ("PASS" if abs(actual-expected) <= margin+1e-9 else "FAIL") if actual is not None and configured else dimensions
        rows.append((title, "%.2f +/- %.2f mm" % (expected, margin) if configured else "Not configured",
                     "%.2f mm" % actual if actual is not None else "-", state))
    prediction = values.get("shape_classification")
    if prediction:
        labels = {"correct_shape": "Correct", "shape_defect": "Wrong shape", "no_protector": "No protector", "uncertain": "Uncertain", "unavailable": "Unavailable"}
        status = prediction["status"]
        confidence = prediction.get("confidence")
        margin = prediction.get("margin")
        target = prediction.get("predicted_class")
        minimum = prediction.get("thresholds", {}).get(target)
        margin_limit = prediction.get("required_margin", .20)
        confidence_state = "PASS" if confidence is not None and minimum is not None and confidence >= minimum else "UNCERTAIN"
        margin_state = "PASS" if margin is not None and margin >= margin_limit else "UNCERTAIN"
        rows = [rows[0], ("Shape class", "Correct", labels.get(status, status), shape),
                ("Confidence", ">= %.0f%%" % (minimum*100) if minimum is not None else "-",
                 "%.1f%%" % (confidence*100) if confidence is not None else "-", confidence_state),
                ("Class margin", ">= %.2f" % margin_limit, "%.3f" % margin if margin is not None else "-", margin_state),
                rows[-2], rows[-1]]
    return rows


class InspectorGUI:
    def __init__(self, root, settings, controller=None):
        self.root, self.settings = root, settings
        self.controller = controller or create_controller(settings)
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.events = queue.Queue()
        self.busy = False
        self.operation = None
        self.awaiting_review = None
        self.current_id = None
        self.current_image = None
        self.actions = []
        self.pages = {}
        self.current_page = None
        root.title("Visual Defect Inspector - IKT213 Group 2")
        root.configure(bg=BG)
        width = max(640, root.winfo_screenwidth()-40)
        height = max(480, root.winfo_screenheight()-80)
        root.geometry("%dx%d" % (width, height))
        root.minsize(min(1080, width), min(688, height))
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.compact_mode = height <= 760
        self.theme()
        self.menu = None
        if not settings.data["demo"]:
            self.menu = tk.Menu(root)
            setup = tk.Menu(self.menu, tearoff=False)
            setup.add_command(label="Calibration...", command=self.calibrate)
            self.menu.add_cascade(label="Setup", menu=setup)
            root.configure(menu=self.menu)
        header = tk.Frame(root, bg=BG, padx=22, pady=8)
        header.pack(fill="x")
        self.label(header, "VDI", font=("DejaVu Sans", 17, "bold"), fg=TEAL).pack(side="left")
        self.label(header, "  /  Visual Defect Inspector", fg=MUTED).pack(side="left")
        self.home_button = self.button(header, "Home", lambda: self.show_page("welcome"), height=34, width=95)
        self.home_button.pack(side="right", padx=(14, 0))
        self.label(header, "PC TEST MODE" if settings.data["demo"] else "INSPECTION STATION",
                   fg="#ffcf79" if settings.data["demo"] else TEAL, font=("DejaVu Sans", 9, "bold")).pack(side="right")
        footer = tk.Frame(root, bg=BG, padx=22, pady=8)
        footer.pack(side="bottom", fill="x")
        self.status = tk.StringVar(value="Welcome. Choose an option to get started.")
        self.label(footer, textvariable=self.status, fg=MUTED, font=("DejaVu Sans", 9)).pack(side="left")
        self.progress = ttk.Progressbar(footer, mode="indeterminate", length=110)
        self.progress.pack(side="right")
        self.page_container = tk.Frame(root, bg=BG)
        self.page_container.pack(fill="both", expand=True, padx=22, pady=(4, 0))
        self.page_container.rowconfigure(0, weight=1)
        self.page_container.columnconfigure(0, weight=1)
        self.build_welcome()
        self.build_inspection()
        self.build_history()
        self.build_placeholder("statistics", "Review statistics")
        self.build_placeholder("guide", "VDI user guide")
        self.refresh()
        pending = self.controller.pending_review()
        if pending is not None:
            self.awaiting_review = pending["id"]
            self.show_record(pending)
            self.status.set("Inspection #%d awaits your choice. Open Start inspection protocol to continue." % pending["id"])
        self.show_page("welcome")
        self.update_controls()
        self.poll_token = root.after(80, self.poll)
        root.bind("<Configure>", self.resize)

    def theme(self):
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                        borderwidth=0, bordercolor=BORDER, lightcolor=PANEL, darkcolor=PANEL,
                        rowheight=23, font=("DejaVu Sans", 9))
        style.configure("Treeview.Heading", background="#1b3a52", foreground=TEXT,
                        relief="flat", font=("DejaVu Sans", 9, "bold"))
        style.map("Treeview", background=[("selected", "#23526a")], foreground=[("selected", TEXT)])
        style.configure("TProgressbar", troughcolor=PANEL, background=TEAL, borderwidth=0)

    def label(self, parent, text=None, **kwargs):
        kwargs.setdefault("bg", parent.cget("bg"))
        kwargs.setdefault("fg", TEXT)
        kwargs.setdefault("font", ("DejaVu Sans", 11))
        return SmoothLabel(parent, text=text, **kwargs)

    def button(self, parent, text, command, **kwargs):
        button = RoundedButton(parent, text, command, **kwargs)
        self.actions.append(button)
        return button

    def page(self, name):
        frame = tk.Frame(self.page_container, bg=BG)
        frame.grid(row=0, column=0, sticky="nsew")
        self.pages[name] = frame
        return frame

    def show_page(self, name):
        if self.busy:
            return False
        self.pages[name].tkraise()
        self.current_page = name
        if name == "inspection":
            self.draw()
        return True

    def card(self, parent):
        return tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=2, padx=12, pady=9)

    def page_heading(self, parent, title):
        self.label(parent, title, font=("DejaVu Sans", 22, "bold")).pack(anchor="w", pady=(5, 12))

    def build_welcome(self):
        page = self.page("welcome")
        decoration = tk.Canvas(page, bg=BG, highlightthickness=0)
        decoration.place(relwidth=1, relheight=1)
        content = tk.Frame(page, bg=BG)
        content.place(relx=.5, rely=.49, anchor="center", relwidth=.94)
        self.welcome_title = self.label(page, "Welcome To VDI - Visual Defect Inspector",
                                       font=("DejaVu Sans", 24, "bold"), fg=TEXT)
        self.welcome_title.pack(pady=(36, 0))
        self.label(content, "Choose your workspace", fg=MUTED).pack(pady=(0, 12))
        self.start_button = self.button(content, "Start inspection protocol", lambda: self.show_page("inspection"),
                                        width=580, height=70, font_size=15, color="#087e92")
        self.stats_button = self.button(content, "Review statistics", lambda: self.show_page("statistics"),
                                        width=580, height=70, font_size=15)
        self.guide_button = self.button(content, "VDI user guide", lambda: self.show_page("guide"),
                                        width=580, height=70, font_size=15)
        for button in (self.start_button, self.stats_button, self.guide_button):
            button.pack(pady=8)
        if self.settings.data["demo"]:
            self.label(content, "PC test: simulated camera, calibration and model", fg="#ffcf79",
                       font=("VDI Sans", 10)).pack(pady=(10, 0))
        def decorate(event):
            decoration.delete("all")
            w, h = event.width, event.height
            for x, y, dx, dy in [(10, 10, 1, 1), (w-10, 10, -1, 1),
                                  (10, h-10, 1, -1), (w-10, h-10, -1, -1)]:
                decoration.create_line(x, y+dy*26, x, y, x+dx*26, y, fill=TEAL, width=2)
            for offset in (0, 15, 30):
                decoration.create_line(0, h-90-offset, 90+offset, h, fill=BORDER, width=1)
                decoration.create_line(w-90-offset, h, w, h-90-offset, fill=BORDER, width=1)
            self.welcome_title.configure(wraplength=max(400, w-90))
        decoration.bind("<Configure>", decorate)

    def resize(self, event):
        if event.widget != self.root:
            return
        compact = event.height <= 760
        if compact != self.compact_mode:
            self.compact_mode = compact
            self.check_table.configure(height=212 if compact else 260)
        self.instruction_label.configure(wraplength=max(400, event.width-400))

    def build_inspection(self):
        page = self.page("inspection")
        heading = tk.Frame(page, bg=BG)
        heading.pack(fill="x", pady=(0, 10))
        self.capture_button = self.button(heading, CAPTURE_LABEL, self.capture, color="#087e92", height=56, width=270, font_size=16)
        self.capture_button.pack(side="right", padx=(18, 0))
        title = tk.Frame(heading, bg=BG)
        title.pack(side="left", fill="x", expand=True)
        self.label(title, "Inspection protocol", font=("VDI Sans", 21, "bold")).pack(anchor="w")
        self.instruction_label = self.label(title, INSTRUCTION, fg=MUTED, wraplength=700, justify="left")
        self.instruction_label.pack(anchor="w", pady=(2, 0))
        body = tk.Frame(page, bg=BG)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=40, uniform="workspace")
        body.columnconfigure(1, weight=60, uniform="workspace")
        body.rowconfigure(0, weight=1)
        left = tk.Frame(body, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        self.history_button = self.button(left, "Inspection results history", lambda: self.show_page("history"), height=46, font_size=13)
        self.history_button.pack(side="bottom", fill="x", pady=(8, 0))
        preview = tk.Frame(left, bg=PANEL, highlightbackground=BORDER, highlightthickness=3, padx=9, pady=8)
        preview.pack(fill="both", expand=True)
        self.label(preview, "Screen protector image", font=("VDI Sans", 13, "bold")).pack(anchor="w", pady=(0, 7))
        self.canvas = tk.Canvas(preview, bg="#06111c", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda event: self.draw())
        self.right_panel = tk.Frame(body, bg=BG)
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        right = self.right_panel
        decisions = tk.Frame(right, bg=BG)
        decisions.pack(side="bottom", fill="x", pady=(6, 0))
        self.operator_status = tk.StringVar(value="Choose Pass or Reject after analysis.")
        self.label(decisions, textvariable=self.operator_status, fg=MUTED, font=("VDI Sans", 11),
                   anchor="w", justify="left", wraplength=900).pack(fill="x", pady=(0, 5))
        buttons = tk.Frame(decisions, bg=BG)
        buttons.pack(fill="x")
        buttons.columnconfigure(0, weight=1, uniform="decisions")
        buttons.columnconfigure(1, weight=1, uniform="decisions")
        self.pass_button = self.button(buttons, "Pass", lambda: self.choose("PASS"), color="#147a52", height=48, font_size=15)
        self.reject_button = self.button(buttons, "Reject", lambda: self.choose("REJECT"), color="#a83c50", height=48, font_size=15)
        self.pass_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.reject_button.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        self.verdict_card = self.card(right)
        self.verdict_card.pack(fill="x", pady=(0, 8))
        row = tk.Frame(self.verdict_card, bg=PANEL)
        row.pack(fill="x", pady=(0, 6))
        self.label(row, "SYSTEM VERDICT", font=("VDI Sans", 13, "bold")).pack(side="left")
        self.verdict_title = self.label(row, "Awaiting analysis", font=("VDI Sans", 22, "bold"), fg=TEAL)
        self.verdict_title.pack(side="right")
        self.automatic_result = tk.StringVar(value="Automatic inspection: waiting for capture")
        self.check_table = DataTable(self.verdict_card, ("check", "expected", "actual", "result"),
                                    (.25, .35, .23, .17), height=212 if self.compact_mode else 260)
        for key, title in [("check", "Check"), ("expected", "Expected"), ("actual", "Measured"), ("result", "Result")]:
            self.check_table.heading(key, title)
        self.check_table.pack(fill="x")
        self.reset_checks()
        self.classification_card = self.card(right)
        self.classification_card.pack(fill="both", expand=True)
        classification = self.classification_card
        self.label(classification, "MODEL CLASSIFICATION", font=("VDI Sans", 12, "bold"), fg=MUTED).pack(anchor="w")
        self.result_title = self.label(classification, "Ready", font=("VDI Sans", 19, "bold"), fg=TEAL,
                                      wraplength=700, justify="left")
        self.result_title.pack(anchor="w", pady=(2, 3))
        self.details = self.label(classification, "Run analysis to see the verdict, measurements and model classification.",
                                  fg=MUTED, font=("VDI Sans", 12), wraplength=700, justify="left", anchor="w")
        self.details.pack(anchor="w", fill="x")
        classification.bind("<Configure>", lambda event: self.details.configure(wraplength=max(240, event.width-36)))

    def reset_checks(self):
        self.check_table.replace_rows([(str(i), (title, "-", "-", "Waiting"), ()) for i, title in enumerate(
            ("Presence", "Shape score", "Fill diff.", "Aspect diff.", "Width", "Height"))])

    def build_placeholder(self, name, title):
        page = self.page(name)
        self.page_heading(page, title)
        card = self.card(page)
        card.place(relx=.5, rely=.46, anchor="center", relwidth=.7)
        self.label(card, title, font=("DejaVu Sans", 23, "bold"), fg=TEAL).pack(pady=(24, 12))
        self.label(card, "This page is reserved for the next design stage.", fg=MUTED).pack(pady=(0, 22))
        self.button(card, "Back to welcome", lambda: self.show_page("welcome")).pack(pady=(0, 24))

    def build_history(self):
        page = self.page("history")
        self.page_heading(page, "Inspection results history")
        bar = tk.Frame(page, bg=BG)
        bar.pack(side="bottom", fill="x", pady=10)
        self.button(bar, "Back to inspection", lambda: self.show_page("inspection"), height=44, width=225).pack(side="left")
        self.button(bar, "View selected inspection", lambda: self.select_history(None), height=44, width=270).pack(side="left", padx=8)
        self.button(bar, "Export results CSV", lambda: self.export(False), height=44, width=205).pack(side="right")
        pager = tk.Frame(page, bg=BG)
        pager.pack(side="bottom", fill="x", pady=(4, 0))
        self.history_page_text = tk.StringVar(value="Page 1 of 1")
        self.button(pager, "Previous", lambda: self.history.change_page(-1), height=40, width=125).pack(side="left")
        self.label(pager, textvariable=self.history_page_text, fg=MUTED).pack(side="left", padx=15)
        self.button(pager, "Next", lambda: self.history.change_page(1), height=40, width=125).pack(side="left")
        self.label(page, "Select a record, then open it to see its picture and saved results.", fg=MUTED).pack(anchor="w", pady=(0, 10))
        columns = ("id", "automatic", "operator", "model", "width", "height", "time")
        self.history = DataTable(page, columns, (.05, .12, .12, .22, .10, .10, .19), paginated=True,
                                 on_page=lambda page, total: self.history_page_text.set("Page %d of %d" % (page, total)))
        for key, title in zip(columns, ("ID", "Verdict", "Operator", "Model output", "Width (mm)", "Height (mm)", "Acquired (UTC)")):
            self.history.heading(key, title)
        self.history.pack(fill="both", expand=True)
        self.history.bind("<Double-1>", self.select_history)
        self.history.bind("<Return>", self.select_history)

    @staticmethod
    def set_text(widget, text):
        widget.configure(text=text)

    def update_controls(self):
        for button in self.actions:
            button.configure(state="disabled" if self.busy else "normal")
        self.capture_button.configure(state="disabled" if self.busy or self.awaiting_review is not None else "normal")
        review = not self.busy and self.awaiting_review is not None and self.current_id == self.awaiting_review
        for button in (self.pass_button, self.reject_button):
            button.configure(state="normal" if review else "disabled")
        if self.menu is not None:
            self.menu.entryconfigure("Setup", state="disabled" if self.busy or self.awaiting_review is not None else "normal")

    def capture(self):
        if self.busy or self.awaiting_review is not None:
            return
        self.show_page("inspection")
        self.busy = True
        self.operation = "inspection"
        self.current_id = None
        self.current_image = None
        self.result_title.configure(text="Loading...", foreground=TEAL)
        self.automatic_result.set("Automatic inspection in progress")
        self.verdict_title.configure(text="Loading...", fg=TEAL)
        self.reset_checks()
        self.operator_status.set("Please wait for analysis to finish.")
        self.set_text(self.details, "Taking a picture and analyzing the screen protector...")
        self.status.set("Taking picture...")
        self.draw()
        self.update_controls()
        self.progress.start(12)

        def work():
            try:
                result = self.controller.inspect(progress=lambda msg: self.events.put(("progress", msg)),
                                                 requires_operator_review=True)
                self.events.put(("result", result))
            except Exception as exc:
                self.events.put(("error", str(exc)))
        self.executor.submit(work)

    def choose(self, decision):
        if self.busy or self.awaiting_review is None or self.current_id != self.awaiting_review:
            return
        inspection_id = self.awaiting_review
        self.busy = True
        self.operation = "operator"
        self.status.set("Saving your %s choice..." % decision)
        self.update_controls()
        self.progress.start(12)

        def work():
            try:
                record = self.controller.record_operator_decision(inspection_id, decision)
                self.events.put(("operator_result", record))
            except Exception as exc:
                self.events.put(("error", str(exc)))
        self.executor.submit(work)

    def poll(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "progress":
                    self.status.set(payload)
                    continue
                self.busy = False
                self.progress.stop()
                if kind == "result":
                    self.current_id = self.awaiting_review = payload["id"]
                    self.show_record(self.controller.get(self.current_id))
                    self.show_page("inspection")
                    self.status.set("Analysis complete. Choose Pass or Reject for inspection #%d" % self.current_id)
                elif kind == "operator_result":
                    self.awaiting_review = None
                    self.show_record(payload)
                    self.status.set("Your %s choice is saved. Ready for the next screen protector." % payload["operator_decision"])
                else:
                    self.show_error(payload)
                self.refresh()
                self.update_controls()
        except queue.Empty:
            pass
        except Exception as exc:
            self.show_error(str(exc))
            self.update_controls()
        finally:
            self.poll_token = self.root.after(80, self.poll)

    def show_error(self, message):
        self.busy = False
        self.progress.stop()
        if self.operation == "operator":
            self.status.set("Your choice was not saved. Try Pass or Reject again.")
        else:
            self.result_title.configure(text="ERROR", foreground="#af2932")
            self.automatic_result.set("Inspection could not be completed")
            self.verdict_title.configure(text="ERROR", fg=RED)
            self.operator_status.set("No new inspection result is confirmed.")
            self.set_text(self.details, message)
            self.status.set("Capture or storage failed. See the error message.")
        messagebox.showerror("Inspection error", message, parent=self.root)

    def show_record(self, record):
        self.current_id = record["id"]
        prefix = "TEST: " if record["is_demo"] else ""
        colors = {"PASS": GREEN, "REJECT": RED, "ERROR": RED}
        self.result_title.configure(text=prefix + model_classification(record),
                                    foreground=colors.get(record["decision"], "#ffcf79"))
        self.automatic_result.set("Automatic inspection: " + record["decision"])
        self.verdict_title.configure(text=record["decision"], fg=colors.get(record["decision"], "#ffcf79"))
        self.check_table.replace_rows([(str(i), row, (row[3],)) for i, row in enumerate(comparison_rows(record))])
        choice = record["operator_decision"]
        if choice:
            self.operator_status.set("Your decision: %s (saved)" % choice)
        elif record["requires_operator_review"]:
            self.operator_status.set("Your decision: choose Pass or Reject below.")
        else:
            self.operator_status.set("No operator decision was requested for this stored test.")
        lines = []
        if record["detections"]:
            maxima = {}
            for detection in record["detections"]:
                maxima[detection["label"]] = max(maxima.get(detection["label"], 0), detection["confidence"])
            confidence = ", ".join("%s %.0f%%" % (name.capitalize(), score*100) for name, score in maxima.items())
            lines.append("Confidence: " + confidence + (" (simulated)" if record["is_demo"] else ""))
        else:
            lines.append(("Shape is uncertain; automatic approval is blocked." if record["measurements"].get("shape_classification", {}).get("status") == "uncertain" else "Calibration or model setup is incomplete.") if record["decision"] == "INCOMPLETE" else record["reason"])
        if record["decision"] in ("ERROR", "INCOMPLETE"):
            lines.append("Your choice is a manual disposition. Automatic result retained.")
        elif choice and choice != record["decision"]:
            lines.append("Your choice differs from the system verdict. Both are saved.")
        shape = record["measurements"].get("shape_classification")
        if shape:
            label = {"correct_shape": "Correct", "shape_defect": "Wrong shape", "no_protector": "No protector", "uncertain": "Uncertain"}.get(shape["status"], "Unavailable")
            lines.append("Inspection #%d | Shape: %s" % (record["id"], label))
        else:
            lines.append("Inspection #%d" % record["id"])
        self.set_text(self.details, "\n".join(lines))
        image = decode_png(self.controller.image(self.current_id))
        self.current_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB) if image.ndim == 3 else image)
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        for x, y, dx, dy in [(12, 12, 1, 1), (w-12, 12, -1, 1),
                              (12, h-12, 1, -1), (w-12, h-12, -1, -1)]:
            self.canvas.create_line(x, y+dy*24, x, y, x+dx*24, y, fill=TEAL, width=2)
        if self.current_image is None:
            text = "Taking picture and analyzing..." if self.busy else "Screen protector image\n\nThe processed picture appears here after analysis."
            bitmap = text_bitmap(text, 18, False, MUTED, "#06111c", max(150, w-70), "center")
            self.placeholder_photo = ImageTk.PhotoImage(bitmap, master=self.canvas)
            self.canvas.create_image(w/2, h/2, image=self.placeholder_photo)
            return
        image = self.current_image.copy()
        image.thumbnail((max(1, w-48), max(1, h-48)), getattr(Image, "Resampling", Image).LANCZOS)
        self.photo = ImageTk.PhotoImage(image)
        self.canvas.create_image(w/2, h/2, image=self.photo, anchor="center")

    def refresh(self):
        rows = []
        for record in self.controller.history():
            choice = record["operator_decision"] or ("Awaiting" if record["requires_operator_review"] and record["decision"] != "PENDING" else "-")
            dimensions = record["measurements"]
            mm = lambda key: "%.2f" % dimensions[key] if key in dimensions else "-"
            values = (record["id"], record["decision"], choice, model_classification(record),
                      mm("width_mm"), mm("height_mm"), record["acquired_at"][:16].replace("T", " "))
            rows.append((str(record["id"]), values, ()))
        self.history.replace_rows(rows)

    def select_history(self, event):
        if self.busy:
            return
        selection = self.history.selection()
        if not selection:
            return
        selected = int(selection[0])
        if self.awaiting_review is not None and selected != self.awaiting_review:
            self.status.set("Finish the Pass or Reject choice for inspection #%d first" % self.awaiting_review)
            return
        self.show_record(self.controller.get(selected))
        self.show_page("inspection")
        self.update_controls()

    def export(self, rejects):
        ext = ".zip" if rejects else ".csv"
        path = filedialog.asksaveasfilename(defaultextension=ext, initialfile=("test_" if self.settings.data["demo"] else "") + ("rejected_images.zip" if rejects else "inspection_results.csv"), filetypes=[("ZIP" if rejects else "CSV", "*" + ext)])
        if path:
            try:
                count = self.controller.export(path, rejects)
                self.status.set("Exported %d records" % count)
            except Exception as exc:
                messagebox.showerror("Export", str(exc), parent=self.root)

    def calibrate(self):
        if not self.busy and self.awaiting_review is None:
            CalibrationWindow(self.root, self.settings)

    def close(self):
        if self.busy:
            messagebox.showinfo("Inspection running", "Wait for the current operation to finish before closing.", parent=self.root)
            return
        self.root.after_cancel(self.poll_token)
        self.executor.shutdown(wait=False)
        self.root.destroy()


def launch(settings, controller=None):
    root = tk.Tk()
    InspectorGUI(root, settings, controller=controller)
    root.mainloop()
