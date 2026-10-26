"""Bundled, antialiased UI text: independent of the platform's Tk font backend."""
from functools import lru_cache
from pathlib import Path
import tkinter as tk

from PIL import Image, ImageDraw, ImageFont, ImageTk

FONT_DIRECTORY = Path(__file__).resolve().parent.parent / "assets/fonts"


@lru_cache(maxsize=96)
def font(size=18, bold=False):
    filename = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(str(FONT_DIRECTORY / filename), max(10, int(size)))


def text_width(text, face):
    bounds = face.getbbox(str(text)) if hasattr(face, "getbbox") else (0, 0, *face.getsize(str(text)))
    return bounds[2]-bounds[0]


def wrap_text(text, face, width):
    lines = []
    for paragraph in str(text).split("\n"):
        line = ""
        for word in paragraph.split(" "):
            candidate = (line+" "+word).strip()
            if line and width and text_width(candidate, face) > width:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
    return lines or [""]


def text_bitmap(text, size=18, bold=False, foreground="#ecf4fc", background="#091624", wrap=0, align="left"):
    face = font(size, bold)
    lines = wrap_text(text, face, wrap)
    line_height = int(size*1.35)
    width = max(1, max(text_width(line, face) for line in lines)+2)
    height = max(line_height, len(lines)*line_height)
    bitmap = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(bitmap)
    for index, line in enumerate(lines):
        x = (width-text_width(line, face))/2 if align == "center" else 0
        draw.text((x, index*line_height), line, font=face, fill=foreground)
    return bitmap


class SmoothLabel(tk.Label):
    """A label rendered with the bundled TrueType face, not a Tk bitmap fallback."""
    def __init__(self, parent, text=None, **kwargs):
        self._text = text or ""
        self._font = kwargs.pop("font", ("VDI Sans", 12))
        self._wrap = kwargs.pop("wraplength", 0)
        self._align = kwargs.get("justify", "left")
        variable = kwargs.pop("textvariable", None)
        self._variable = variable
        self._trace = None
        super().__init__(parent, text="", **kwargs)
        if variable is not None:
            self._trace = variable.trace_add("write", self._changed)
        self.bind("<Destroy>", self._remove_trace)
        self._render()

    def _changed(self, *args):
        self._render()

    def _remove_trace(self, event):
        if event.widget == self and self._variable is not None and self._trace is not None:
            try:
                self._variable.trace_remove("write", self._trace)
            except tk.TclError:
                pass
            self._trace = None

    def _render(self):
        text = self._variable.get() if self._variable is not None else self._text
        size = max(14, int(abs(self._font[1])*1.35))
        bold = "bold" in self._font[2:]
        bitmap = text_bitmap(text, size, bold, super().cget("fg"), super().cget("bg"), self._wrap, self._align)
        self._photo = ImageTk.PhotoImage(bitmap, master=self)
        super().configure(image=self._photo)

    def configure(self, cnf=None, **kwargs):
        if cnf:
            kwargs.update(cnf)
        if "text" in kwargs:
            self._text = str(kwargs.pop("text"))
        if "font" in kwargs:
            self._font = kwargs.pop("font")
        if "wraplength" in kwargs:
            self._wrap = kwargs.pop("wraplength")
        if "justify" in kwargs:
            self._align = kwargs["justify"]
        if kwargs:
            super().configure(**kwargs)
        if hasattr(self, "_photo"):
            self._render()
    config = configure

    def cget(self, key):
        if key == "text":
            return self._variable.get() if self._variable is not None else self._text
        if key == "font":
            return self._font
        if key == "wraplength":
            return self._wrap
        return super().cget(key)

    def get(self, *args):
        return self.cget("text")
