"""Small Tk widgets for the desktop theme; no extra GUI dependency."""
import math
import tkinter as tk
from PIL import ImageTk
from .ui_typography import text_bitmap

BG = "#091624"
PANEL = "#10273b"
BORDER = "#315b76"
BUTTON_BORDER = "#79cbe4"
BUTTON_FILL = "#175f95"
TEAL = "#16c9cf"
TEXT = "#ecf4fc"
MUTED = "#a4b8cb"
GREEN = "#58dc9b"
RED = "#ff8c96"


class RoundedButton(tk.Canvas):
    """Rounded, keyboard-accessible button with explicit disabled semantics."""
    def __init__(self, parent, text, command, color=BUTTON_FILL, foreground=TEXT,
                 height=48, width=250, font_size=12):
        super().__init__(parent, width=width, height=height, bg=parent.cget("bg"),
                         highlightthickness=0, bd=0, takefocus=1, cursor="hand2")
        self.label = text
        self.command = command
        self.color = color
        self.foreground = foreground
        self.font_size = font_size
        self.disabled = False
        self.hover = False
        self.bind("<Configure>", self.draw)
        self.bind("<Enter>", lambda event: self.set_hover(True))
        self.bind("<Leave>", lambda event: self.set_hover(False))
        self.bind("<Button-1>", lambda event: self.focus_set())
        self.bind("<ButtonRelease-1>", self.clicked)
        self.bind("<Return>", lambda event: self.invoke())
        self.bind("<space>", lambda event: self.invoke())
        self.bind("<FocusIn>", self.draw)
        self.bind("<FocusOut>", self.draw)

    def set_hover(self, value):
        self.hover = value
        self.draw()

    def clicked(self, event):
        if 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height():
            self.invoke()

    def invoke(self):
        if not self.disabled:
            return self.command()

    def instate(self, states):
        return all(self.disabled if s == "disabled" else not self.disabled if s == "!disabled" else False for s in states)

    def configure(self, cnf=None, **kwargs):
        if cnf:
            kwargs.update(cnf)
        if "state" in kwargs:
            self.disabled = kwargs.pop("state") == "disabled"
        if "text" in kwargs:
            self.label = kwargs.pop("text")
        if kwargs:
            super().configure(**kwargs)
        if hasattr(self, "label"):
            self.draw()
    config = configure

    def cget(self, key):
        if key == "text":
            return self.label
        if key == "state":
            return "disabled" if self.disabled else "normal"
        return super().cget(key)

    def draw(self, event=None):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 5 or h < 5:
            return
        r = min(20, (h-4)/2, (w-4)/2)
        points = []
        for x, y, start in [(w-2-r, 2+r, -90), (w-2-r, h-2-r, 0),
                             (2+r, h-2-r, 90), (2+r, 2+r, 180)]:
            for degrees in range(start, start+91, 10):
                angle = math.radians(degrees)
                points.extend([x+r*math.cos(angle), y+r*math.sin(angle)])
        fill = self.color
        if self.disabled:
            channels = [int(self.color[i:i+2], 16) for i in (1, 3, 5)]
            fill = "#"+"".join("%02x" % int(c*.65) for c in channels)
        self.create_polygon(points, fill=fill, outline=BUTTON_BORDER, width=2)
        if self.focus_get() == self:
            self.create_line(20, h-6, w-20, h-6, fill=BUTTON_BORDER, width=2)
        bitmap = text_bitmap(self.label, max(18, int(self.font_size*1.3)), True,
                             "#bacddd" if self.disabled else self.foreground, fill, max(30, w-32), "center")
        self._text_photo = ImageTk.PhotoImage(bitmap, master=self)
        self.create_image(w/2, h/2, image=self._text_photo)
