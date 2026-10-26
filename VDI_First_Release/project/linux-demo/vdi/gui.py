"""One-button acquisition and analysis, followed by an explicit operator disposition."""
import queue
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from tkinter import filedialog, messagebox, ttk

import cv2
from PIL import Image, ImageTk

from .application import create_controller
from .calibration_gui import CalibrationWindow
from .image_processing import decode_png

CAPTURE_LABEL = "Take picture and analyze next screen protector"


def model_classification(record):
    labels = {d["label"] for d in record["detections"]}
    if labels:
        return " + ".join(label.capitalize() for label in ("scratch", "crack") if label in labels)
    defect_check = next((c for c in record["checks"] if c["name"] == "defects"), None)
    if defect_check and defect_check["state"] == "PASS":
        return "No defect detected"
    if defect_check and defect_check["state"] == "SKIPPED":
        return "Not run"
    return "Unavailable"


class InspectorGUI:
    def __init__(self, root, settings, controller=None):
        self.root = root
        self.settings = settings
        self.controller = controller or create_controller(settings)
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.events = queue.Queue()
        self.busy = False
        self.operation = None
        self.awaiting_review = None
        self.current_id = None
        self.current_image = None
        self.actions = []
        root.title("Visual Defect Inspector - IKT213 Group 2")
        width = min(1280, max(640, root.winfo_screenwidth() - 40))
        height = min(850, max(480, root.winfo_screenheight() - 80))
        root.geometry("%dx%d" % (width, height))
        root.minsize(min(1080, width), min(720, height))
        root.protocol("WM_DELETE_WINDOW", self.close)
        style = ttk.Style(root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Title.TLabel", font=("DejaVu Sans", 21, "bold"))
        style.configure("Result.TLabel", font=("DejaVu Sans", 21, "bold"))
        style.configure("Capture.TButton", font=("DejaVu Sans", 13, "bold"), padding=(14, 12))
        style.configure("Pass.TButton", font=("DejaVu Sans", 11, "bold"), padding=(8, 10), foreground="#12633b")
        style.configure("Reject.TButton", font=("DejaVu Sans", 11, "bold"), padding=(8, 10), foreground="#a02730")
        self.menu = None
        if not settings.data["demo"]:
            self.menu = tk.Menu(root)
            setup = tk.Menu(self.menu, tearoff=False)
            setup.add_command(label="Calibration...", command=self.calibrate)
            self.menu.add_cascade(label="Setup", menu=setup)
            root.configure(menu=self.menu)
        header = ttk.Frame(root, padding=(18, 14))
        header.pack(fill="x")
        ttk.Label(header, text="Visual Defect Inspector", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="IKT213  |  Group 2").pack(side="right")
        if settings.data["demo"]:
            tk.Label(root, text="TEST MODE - simulated camera, artificial calibration and placeholder model. Results are software tests.",
                     bg="#ffe5a3", fg="#25323a", anchor="w", padx=18, pady=10).pack(fill="x")
        bar = ttk.Frame(root, padding=(18, 8, 18, 12))
        bar.pack(fill="x")
        self.capture_button = self.button(bar, CAPTURE_LABEL, self.capture, "Capture.TButton")
        self.capture_button.pack(anchor="w")
        ttk.Label(bar, text="Place one protector in the tray. Capture, analysis and result storage run automatically.").pack(anchor="w", pady=(8, 0))
        footer = ttk.Frame(root, padding=(18, 4, 18, 12))
        footer.pack(side="bottom", fill="x")
        self.status = tk.StringVar(value="Ready for the next screen protector")
        ttk.Label(footer, textvariable=self.status).pack(side="left")
        self.progress = ttk.Progressbar(footer, mode="indeterminate", length=150)
        self.progress.pack(side="right")
        body = ttk.Panedwindow(root, orient="horizontal")
        body.pack(fill="both", expand=True, padx=18, pady=(0, 8))
        preview = ttk.Frame(body)
        body.add(preview, weight=3)
        ttk.Label(preview, text="Inspection picture", padding=(0, 0, 0, 6)).pack(anchor="w")
        self.canvas = tk.Canvas(preview, background="#14232d", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda event: self.draw())
        self.notebook = ttk.Notebook(body, width=510)
        body.add(self.notebook, weight=2)
        self.result_tab = ttk.Frame(self.notebook, padding=14)
        history_tab = ttk.Frame(self.notebook, padding=10)
        stats_tab = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(self.result_tab, text="Inspection result")
        self.notebook.add(history_tab, text="History")
        self.notebook.add(stats_tab, text="Statistics")
        ttk.Label(self.result_tab, text="MODEL CLASSIFICATION").pack(anchor="w")
        self.result_title = ttk.Label(self.result_tab, text="Ready", style="Result.TLabel", wraplength=475)
        self.result_title.pack(anchor="w", pady=(5, 10))
        self.automatic_result = tk.StringVar(value="Automatic inspection: waiting for capture")
        ttk.Label(self.result_tab, textvariable=self.automatic_result, wraplength=475).pack(anchor="w", pady=(0, 8))
        decisions = ttk.Frame(self.result_tab)
        decisions.pack(side="bottom", fill="x", pady=(12, 0))
        self.operator_status = tk.StringVar(value="Pass and Reject become available after analysis.")
        ttk.Label(decisions, textvariable=self.operator_status, wraplength=475).pack(anchor="w", pady=(0, 8))
        buttons = ttk.Frame(decisions)
        buttons.pack(fill="x")
        self.pass_button = self.button(buttons, "Pass screen protector", lambda: self.choose("PASS"), "Pass.TButton")
        self.reject_button = self.button(buttons, "Reject screen protector", lambda: self.choose("REJECT"), "Reject.TButton")
        self.pass_button.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.reject_button.pack(side="left", fill="x", expand=True, padx=(6, 0))
        self.details = tk.Text(self.result_tab, wrap="word", relief="flat", background="#f2f5f7",
                               font=("DejaVu Sans", 11), padx=10, pady=10, height=12)
        self.details.pack(fill="both", expand=True)
        self.set_text(self.details, "Press the capture button once.\n\nThe result and picture appear here automatically.\n\nThen choose Pass or Reject for this protector.")
        self.history = ttk.Treeview(history_tab, columns=("id", "automatic", "operator", "time"), show="headings", selectmode="browse")
        for column, title, width in [("id", "ID", 45), ("automatic", "Automatic", 90),
                                     ("operator", "Your choice", 95), ("time", "Acquired (UTC)", 170)]:
            self.history.heading(column, text=title)
            self.history.column(column, width=width, stretch=column == "time")
        scrollbar = ttk.Scrollbar(history_tab, orient="vertical", command=self.history.yview)
        self.history.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.history.pack(fill="both", expand=True)
        self.history.bind("<<TreeviewSelect>>", self.select_history)
        ttk.Label(history_tab, text="Latest 500 records; exports include all.").pack(anchor="w", pady=8)
        self.stats_text = tk.Text(stats_tab, wrap="word", relief="flat", background="#f2f5f7",
                                 font=("DejaVu Sans", 11), padx=10, pady=10)
        export_bar = ttk.Frame(stats_tab)
        export_bar.pack(side="bottom", fill="x", pady=(12, 0))
        self.button(export_bar, "Export results CSV", lambda: self.export(False)).pack(fill="x", pady=(0, 6))
        self.button(export_bar, "Export rejected images ZIP", lambda: self.export(True)).pack(fill="x")
        self.stats_text.pack(fill="both", expand=True)
        self.refresh()
        pending = self.controller.pending_review()
        if pending is not None:
            self.awaiting_review = pending["id"]
            self.show_record(pending)
            self.status.set("Inspection #%d is awaiting your Pass or Reject choice" % pending["id"])
        self.update_controls()
        self.draw()
        self.poll_token = root.after(80, self.poll)

    def button(self, parent, text, command, style=None):
        kwargs = {"style": style} if style else {}
        button = ttk.Button(parent, text=text, command=command, **kwargs)
        self.actions.append(button)
        return button

    @staticmethod
    def set_text(widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

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
        self.busy = True
        self.operation = "inspection"
        self.current_id = None
        self.current_image = None
        self.notebook.select(self.result_tab)
        self.result_title.configure(text="Loading...", foreground="#294858")
        self.automatic_result.set("Automatic inspection in progress")
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
                    self.notebook.select(self.result_tab)
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
            self.operator_status.set("No new inspection result is confirmed.")
            self.set_text(self.details, message)
            self.status.set("Capture or storage failed. See the error message.")
        messagebox.showerror("Inspection error", message, parent=self.root)

    def show_record(self, record):
        self.current_id = record["id"]
        prefix = "TEST: " if record["is_demo"] else ""
        colors = {"PASS": "#137a4a", "REJECT": "#ad3333", "ERROR": "#ad3333"}
        self.result_title.configure(text=prefix + model_classification(record),
                                    foreground=colors.get(record["decision"], "#946716"))
        self.automatic_result.set("Automatic inspection: " + record["decision"])
        choice = record["operator_decision"]
        if choice:
            self.operator_status.set("Your decision: %s (saved)" % choice)
        elif record["requires_operator_review"]:
            self.operator_status.set("Your decision: choose Pass or Reject below.")
        else:
            self.operator_status.set("No operator decision was requested for this stored test.")
        lines = ["Inspection #%d" % record["id"], record["reason"], ""]
        names = {"presence": "Protector presence", "shape": "Shape", "dimensions": "Dimensions", "defects": "Defect detection"}
        states = {"PASS": "Passed", "FAIL": "Failed", "NOT_READY": "Setup needed", "SKIPPED": "Not run", "ERROR": "Error"}
        for c in record["checks"]:
            lines.append("%s: %s" % (names.get(c["name"], c["name"]), states.get(c["state"], c["state"])))
        m = record["measurements"]
        if "width_mm" in m and "height_mm" in m:
            lines.extend(["", "Width: %.2f mm" % m["width_mm"], "Height: %.2f mm" % m["height_mm"]])
        if record["detections"]:
            lines.append("")
            for d in record["detections"]:
                lines.append("%s confidence: %.0f%%" % (d["label"].capitalize(), d["confidence"] * 100))
        if record["decision"] in ("ERROR", "INCOMPLETE"):
            lines.extend(["", "Automatic inspection is incomplete or failed. Your choice is a manual disposition; the automatic result stays recorded."])
        if choice and choice != record["decision"]:
            lines.extend(["", "Your decision differs from the automatic result. Both are stored."])
        lines.extend(["", "Acquired (UTC): " + record["acquired_at"]])
        if record["is_demo"]:
            lines.extend(["", "TEST: artificial measurements and simulated defect outputs."])
        self.set_text(self.details, "\n".join(lines))
        image = decode_png(self.controller.image(self.current_id))
        self.current_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB) if image.ndim == 3 else image)
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        if self.current_image is None:
            self.canvas.create_text(self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2,
                                    text="Taking picture and analyzing..." if self.busy else "The captured picture appears here after analysis.",
                                    fill="#d3e2e8", width=max(200, self.canvas.winfo_width() - 50), font=("DejaVu Sans", 13))
            return
        image = self.current_image.copy()
        size = (max(1, self.canvas.winfo_width() - 16), max(1, self.canvas.winfo_height() - 16))
        resampling = getattr(Image, "Resampling", Image)
        image.thumbnail(size, resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(image)
        self.canvas.create_image(self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2, image=self.photo, anchor="center")

    def refresh(self):
        for item in self.history.get_children():
            self.history.delete(item)
        for r in self.controller.history():
            choice = r["operator_decision"] or ("Awaiting" if r["requires_operator_review"] and r["decision"] != "PENDING" else "-")
            self.history.insert("", "end", iid=str(r["id"]), values=(r["id"], r["decision"], choice, r["acquired_at"][:19].replace("T", " ")))
        stats = self.controller.statistics()
        rate = lambda value: "No decisions yet" if value is None else "%.1f%%" % (value * 100)
        lines = ["TEST INSPECTIONS" if self.settings.data["demo"] else "REAL INSPECTIONS", "",
                 "Your final decisions:", "Pass rate: " + rate(stats["operator_pass_rate"])]
        lines.extend("%s: %d" % (name, value) for name, value in stats["operator_counts"].items())
        lines.extend(["", "Automatic inspection results:", "Automatic pass rate: " + rate(stats["pass_rate"])])
        lines.extend("%s: %d" % (name, value) for name, value in stats["counts"].items())
        lines.extend(["", "Detected defect / failed check categories:"])
        lines.extend("%s: %d" % (name, value) for name, value in stats["categories"].items())
        lines.extend(["", "Your decisions and automatic results are counted separately.", "Test and real records are kept separate."])
        self.set_text(self.stats_text, "\n".join(lines))

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
