"""Fixed comparison grid and paginated history with readable, aligned columns."""
import math
import tkinter as tk
from PIL import Image, ImageDraw, ImageTk
from .ui_typography import font, text_width, wrap_text


class DataTable(tk.Canvas):
    def __init__(self, parent, columns, weights, paginated=False, height=226, on_page=None):
        super().__init__(parent, bg="#10273b", bd=0, highlightthickness=0,
                         height=height, width=300, takefocus=int(paginated))
        self.columns = columns
        self.weights = weights
        self.paginated = paginated
        self.rows = {}
        self.headers = dict((c, c) for c in columns)
        self.selected = None
        self.page_index = 0
        self.page_size = 10
        self.on_page = on_page
        self.cell_bounds = []
        self.header_height = 34
        self.row_height = 32
        self.bind("<Configure>", self.draw)
        self.bind("<Button-1>", self.clicked)
        self.bind("<Up>", lambda event: self.move_selection(-1))
        self.bind("<Down>", lambda event: self.move_selection(1))
        for event in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind(event, lambda event: "break")

    @property
    def page_count(self):
        return max(1, int(math.ceil(len(self.rows)/float(self.page_size))))

    def heading(self, column, text):
        self.headers[column] = text

    def insert(self, parent, index, iid=None, values=(), tags=()):
        key = str(iid) if iid is not None else "row%d" % (len(self.rows)+1)
        self.rows[key] = {"values": tuple(values), "tags": tags}
        self.draw()
        return key

    def replace_rows(self, rows):
        self.rows = {str(key): {"values": tuple(values), "tags": tags} for key, values, tags in rows}
        if self.selected not in self.rows:
            self.selected = None
        self.draw()

    def get_children(self):
        return tuple(self.rows)

    def delete(self, key):
        self.rows.pop(str(key), None)
        if self.selected == str(key):
            self.selected = None
        self.draw()

    def item(self, key, option=None):
        record = self.rows[str(key)]
        return record[option] if option else record

    def selection(self):
        return (self.selected,) if self.selected in self.rows else ()

    def selection_set(self, key):
        key = str(key)
        if key in self.rows:
            self.selected = key
            self.page_index = list(self.rows).index(key)//self.page_size if self.paginated else 0
        self.draw()

    def change_page(self, step):
        self.page_index = max(0, min(self.page_count-1, self.page_index+step))
        self.draw()

    def move_selection(self, step):
        if not self.paginated or not self.rows:
            return "break"
        keys = list(self.rows)
        current = keys.index(self.selected) if self.selected in keys else 0
        self.selection_set(keys[max(0, min(len(keys)-1, current+step))])
        return "break"

    def clicked(self, event):
        if not self.paginated:
            return
        self.focus_set()
        index = int((event.y-self.header_height)//self.row_height)
        if event.y >= self.header_height and 0 <= index < self.page_size:
            keys = list(self.rows)
            position = self.page_index*self.page_size+index
            if position < len(keys):
                self.selection_set(keys[position])

    def draw(self, event=None):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 40 or h < 20:
            return
        size = 20 if w >= 980 else 18 if w >= 700 else 16
        face, bold = font(size), font(size, True)
        if self.paginated:
            self.header_height, self.row_height = 44, 44
            self.page_size = max(1, int((h-self.header_height)//self.row_height))
        else:
            self.header_height = 34
            self.row_height = max(28, int((h-self.header_height)/6))
        self.page_index = min(self.page_index, self.page_count-1)
        total = float(sum(self.weights))
        minimums = [80, 165, 135, 175, 125, 125, 190] if self.paginated else []
        use_minimums = self.paginated and len(self.columns) == 7 and w >= sum(minimums)
        boundaries = [0]
        for index, weight in enumerate(self.weights):
            width = minimums[index]+(w-sum(minimums))*weight/total if use_minimums else w*weight/total
            boundaries.append(boundaries[-1]+width)
        self.cell_bounds = boundaries
        bitmap = Image.new("RGB", (w, h), "#10273b")
        draw = ImageDraw.Draw(bitmap)
        draw.rectangle((0, 0, w-1, self.header_height), fill="#1b405c")
        header_size = min(size, 18) if self.paginated else size
        header_font = font(header_size, True)
        for i, key in enumerate(self.columns):
            lines = wrap_text(self.headers[key], header_font, boundaries[i+1]-boundaries[i]-24)
            for index, line in enumerate(lines):
                draw.text((boundaries[i]+12, 3+index*(header_size+2)), line, font=header_font, fill="#edf5ff")
        items = list(self.rows.items())
        start = self.page_index*self.page_size if self.paginated else 0
        count = self.page_size if self.paginated else len(items)
        status_text = {"NOT_READY": "SETUP", "SKIPPED": "NOT RUN", "UNCERTAIN": "REVIEW"}
        for index, (key, row) in enumerate(items[start:start+count]):
            top = self.header_height+index*self.row_height
            fill = "#245a76" if key == self.selected else ("#17344a" if index % 2 else "#10273b")
            draw.rectangle((0, top, w-1, top+self.row_height), fill=fill)
            for i, value in enumerate(row["values"]):
                value = str(value)
                status = (i == len(self.columns)-1 and not self.paginated) or (self.paginated and i in (1, 2))
                color = "#6ce6b0" if status and value == "PASS" else "#ff949e" if status and value in ("REJECT", "FAIL", "ERROR") else "#f4cf85" if status and value in ("NOT_READY", "UNCERTAIN") else "#e5eff9"
                text = status_text.get(value, value) if status else value
                available = max(20, boundaries[i+1]-boundaries[i]-24)
                lines = wrap_text(text, face, available)
                for line_index, line in enumerate(lines):
                    draw.text((boundaries[i]+12, top+max(2,(self.row_height-len(lines)*(size+2))/2)+line_index*(size+2)),
                              line, font=face, fill=color)
            draw.line((0, top+self.row_height, w-1, top+self.row_height), fill="#35566e", width=1)
        for boundary in boundaries:
            x = max(0, min(w-1, int(boundary)))
            draw.line((x, 0, x, h-1), fill="#41667e", width=1)
        draw.rectangle((0, 0, w-1, h-1), outline="#41667e", width=1)
        self._photo = ImageTk.PhotoImage(bitmap, master=self)
        self.delete_image()
        self.create_image(0, 0, anchor="nw", image=self._photo, tags="table_image")
        if self.on_page:
            self.on_page(self.page_index+1, self.page_count)

    def delete_image(self):
        super().delete("table_image")
