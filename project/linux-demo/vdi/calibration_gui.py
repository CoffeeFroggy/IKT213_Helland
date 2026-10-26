"""A two-point calibration tool with a visible, reviewable reference contour."""
import json
import math
import hashlib
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import cv2
from PIL import Image, ImageTk

from .config import ROOT, Settings
from .geometry import find_protector
from .image_processing import prepare, read_image


class CalibrationWindow:
    def __init__(self, parent, settings):
        self.settings = settings
        self.data = json.loads(json.dumps(settings.data))
        self.image = None
        self.points = []
        self.contour = None
        self.window = tk.Toplevel(parent)
        self.window.title("Calibration - fixed camera and product plane")
        self.window.geometry("1080x810")
        self.window.transient(parent)
        self.window.grab_set()
        ttk.Label(self.window, text="1. Load a full-resolution good reference.  2. Check the green outline.\n"
                  "3. Click two points a known distance apart, at the glass plane.  4. Enter the actual values.",
                  padding=10).pack(anchor="w")
        row = ttk.Frame(self.window, padding=8)
        row.pack(fill="x")
        ttk.Button(row, text="Load reference image", command=self.load).pack(side="left")
        ttk.Button(row, text="Reset points", command=self.reset).pack(side="left", padx=8)
        self.info = tk.StringVar(value="Use the same camera, focus, resolution, ROI and glass position as inspection.")
        ttk.Label(row, textvariable=self.info).pack(side="left", padx=8)
        tuning = ttk.Frame(self.window, padding=(10, 0, 10, 8))
        tuning.pack(fill="x")
        ttk.Label(tuning, text="Outline filter:").pack(side="left")
        s = self.data["segmentation"]
        self.method = tk.StringVar(value=s["method"])
        ttk.Combobox(tuning, textvariable=self.method, values=["laplacian", "brightness"], state="readonly", width=12).pack(side="left", padx=6)
        ttk.Label(tuning, text="Threshold:").pack(side="left")
        self.threshold = tk.StringVar(value=str(s["threshold"]))
        ttk.Entry(tuning, textvariable=self.threshold, width=5).pack(side="left", padx=6)
        ttk.Label(tuning, text="Close kernel:").pack(side="left")
        self.kernel = tk.StringVar(value=str(s["close_kernel"]))
        ttk.Entry(tuning, textvariable=self.kernel, width=4).pack(side="left", padx=6)
        ttk.Label(tuning, text="ROI l,t,r,b (0-1):").pack(side="left")
        self.roi = tk.StringVar(value=",".join(str(x) for x in s["roi"]))
        ttk.Entry(tuning, textvariable=self.roi, width=18).pack(side="left", padx=6)
        ttk.Button(tuning, text="Update outline", command=self.update_outline).pack(side="left")
        bottom = ttk.Frame(self.window)
        bottom.pack(side="bottom", fill="x")
        self.canvas = tk.Canvas(self.window, width=980, height=480, background="#17232c", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=10)
        self.canvas.bind("<Button-1>", self.click)
        self.canvas.bind("<Configure>", lambda event: self.draw())
        fields = ttk.Frame(bottom, padding=10)
        fields.pack(fill="x")
        self.values = {}
        g = settings.data["geometry"]
        for i, (key, label) in enumerate([
                ("reference_length_mm", "Distance between clicks (mm)"),
                ("nominal_width_mm", "Expected width, short side (mm)"),
                ("nominal_height_mm", "Expected height, long side (mm)"),
                ("width_tolerance_mm", "Width tolerance +/- (mm)"),
                ("height_tolerance_mm", "Height tolerance +/- (mm)")]):
            ttk.Label(fields, text=label).grid(row=i // 3 * 2, column=i % 3, sticky="w", padx=8)
            var = tk.StringVar(value="" if g.get(key) is None else str(g[key]))
            self.values[key] = var
            ttk.Entry(fields, textvariable=var, width=28).grid(row=i // 3 * 2 + 1, column=i % 3, sticky="w", padx=8, pady=(0, 8))
        self.reviewed = tk.BooleanVar(value=False)
        ttk.Checkbutton(bottom, variable=self.reviewed,
                        text="I checked that the green contour follows the complete, correct glass outline.").pack(anchor="w", padx=16)
        ttk.Button(bottom, text="Save calibration", command=self.save).pack(anchor="e", padx=16, pady=12)

    def load(self):
        path = filedialog.askopenfilename(parent=self.window, title="Known good reference image",
                                          filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff")])
        if not path:
            return
        try:
            image = read_image(path)
            self.image = image
            self.points = []
            self.reviewed.set(False)
            self.update_outline()
        except Exception as exc:
            messagebox.showerror("Reference image", str(exc), parent=self.window)

    def update_outline(self):
        if self.image is None:
            return
        try:
            data = json.loads(json.dumps(self.data))
            data["segmentation"].update({"method": self.method.get(), "threshold": float(self.threshold.get()),
                                         "close_kernel": int(self.kernel.get()),
                                         "roi": [float(x.strip()) for x in self.roi.get().split(",")]})
            Settings(data)
            self.data = data
            packet = prepare(self.image, data["segmentation"])
            self.contour, reason, _ = find_protector(packet, data["segmentation"])
            self.reviewed.set(False)
            self.info.set(reason if reason else "Check green outline; click known distance endpoints.")
            self.draw()
        except Exception as exc:
            messagebox.showerror("Outline settings", str(exc), parent=self.window)

    def reset(self):
        self.points = []
        self.info.set("Click two endpoints again.")
        self.draw()

    def draw(self):
        if self.image is None:
            return
        display = self.image.copy()
        if self.contour is not None:
            cv2.drawContours(display, [self.contour], -1, (30, 255, 30), 2)
        h, w = display.shape[:2]
        x1, y1, x2, y2 = self.data["segmentation"]["roi"]
        cv2.rectangle(display, (int(x1 * w), int(y1 * h)), (int(x2 * w) - 1, int(y2 * h) - 1), (255, 180, 0), 1)
        for point in self.points:
            cv2.circle(display, tuple(int(round(x)) for x in point), 6, (0, 0, 255), -1)
        if len(self.points) == 2:
            cv2.line(display, tuple(map(int, self.points[0])), tuple(map(int, self.points[1])), (0, 0, 255), 2)
        h, w = display.shape[:2]
        self.scale = min(max(1, self.canvas.winfo_width() - 8) / w,
                         max(1, self.canvas.winfo_height() - 8) / h)
        size = (max(1, int(w * self.scale)), max(1, int(h * self.scale)))
        pil = Image.fromarray(cv2.cvtColor(display, cv2.COLOR_BGR2RGB)).resize(size)
        self.photo = ImageTk.PhotoImage(pil)
        self.canvas.delete("all")
        self.canvas.create_image(4, 4, anchor="nw", image=self.photo)

    def click(self, event):
        if self.image is None or len(self.points) == 2:
            return
        x, y = (event.x - 4) / self.scale, (event.y - 4) / self.scale
        if not (0 <= x < self.image.shape[1] and 0 <= y < self.image.shape[0]):
            return
        self.points.append((x, y))
        self.draw()
        if len(self.points) == 2:
            a, b = self.points
            self.info.set("Reference distance: %.2f pixels" % math.hypot(b[0] - a[0], b[1] - a[1]))

    def save(self):
        try:
            if self.image is None or self.contour is None or len(self.points) != 2 or not self.reviewed.get():
                raise ValueError("Load the reference, choose two points, and confirm the contour first.")
            a, b = self.points
            distance = math.hypot(b[0] - a[0], b[1] - a[1])
            if distance < 20:
                raise ValueError("Choose reference points at least 20 pixels apart for more reliable calibration.")
            values = {key: float(var.get().replace(",", ".")) for key, var in self.values.items()}
            if not math.isfinite(values["reference_length_mm"]) or values["reference_length_mm"] <= 0:
                raise ValueError("Reference distance in millimeters must be positive.")
            # Require Update outline if the user changed filter fields since detection.
            s = self.data["segmentation"]
            if (self.method.get() != s["method"] or float(self.threshold.get()) != s["threshold"] or
                    int(self.kernel.get()) != s["close_kernel"] or [float(x) for x in self.roi.get().split(",")] != s["roi"]):
                raise ValueError("Click Update outline and review the contour after changing filter settings.")
            data = json.loads(json.dumps(self.data))
            data["geometry"].update({key: value for key, value in values.items() if key != "reference_length_mm"})
            data["geometry"]["mm_per_pixel"] = values["reference_length_mm"] / distance
            data["geometry"]["calibration_image_size"] = [self.image.shape[1], self.image.shape[0]]
            from .image_processing import encode_png
            encoded = encode_png(self.image)
            relative_reference = "assets/references/" + hashlib.sha256(encoded).hexdigest() + ".png"
            data["geometry"]["reference_image"] = relative_reference
            Settings(data)  # Validate all entered fields before writing either file.
            reference = ROOT / relative_reference
            reference.parent.mkdir(parents=True, exist_ok=True)
            target = self.settings.path or ROOT / "config/inspection.json"
            # Keep any previous profile for recovery; no automatically accepted reference.
            if target.exists():
                target.with_suffix(target.suffix + ".bak").write_bytes(target.read_bytes())
            reference.write_bytes(encoded)
            temporary = target.with_suffix(target.suffix + ".tmp")
            temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            temporary.replace(target)
            messagebox.showinfo("Calibration saved", "Calibration saved. Close and restart the inspection application to use it.\n"
                                "Validate measurements and shape thresholds on additional good and bad examples.", parent=self.window)
            self.window.destroy()
        except Exception as exc:
            messagebox.showerror("Calibration", str(exc), parent=self.window)
