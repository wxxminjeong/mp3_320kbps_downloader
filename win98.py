"""Windows 98 look-alike widgets for Tkinter.

Bevels, check marks, icons and progress blocks are all drawn by hand, so the
app keeps its Windows 98 look on Windows 10/11, macOS and Linux instead of
picking up the platform's modern native theme.
"""

import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

# -- "Windows Standard" colour scheme ------------------------------------------------

FACE = "#C0C0C0"
LIGHT = "#DFDFDF"
HILIGHT = "#FFFFFF"
SHADOW = "#808080"
DKSHADOW = "#000000"
WINDOW = "#FFFFFF"
TEXT = "#000000"
GRAYTEXT = "#808080"
SELECT = "#000080"
SELECT_TEXT = "#FFFFFF"

# A bevel is a list of 1-pixel rings, outermost first: (top/left, bottom/right).
RAISED = ((HILIGHT, DKSHADOW), (LIGHT, SHADOW))
PRESSED = ((DKSHADOW, HILIGHT), (SHADOW, LIGHT))
DEFAULT = ((DKSHADOW, DKSHADOW), (HILIGHT, DKSHADOW), (LIGHT, SHADOW))
DEFAULT_PRESSED = ((DKSHADOW, DKSHADOW), (SHADOW, SHADOW))
SUNKEN = ((SHADOW, HILIGHT), (DKSHADOW, LIGHT))
THIN_SUNKEN = ((SHADOW, HILIGHT),)
THIN_RAISED = ((HILIGHT, SHADOW),)
ETCHED = ((SHADOW, HILIGHT), (HILIGHT, SHADOW))

# -- 16-colour pixel art ('.' is transparent) ------------------------------------------

PALETTE = {
    "k": "#000000", "w": "#FFFFFF", "s": "#C0C0C0", "d": "#808080",
    "n": "#000080", "b": "#0000FF", "c": "#00FFFF", "G": "#008000",
    "y": "#FFFF00", "o": "#808000", "r": "#FF0000",
}

CD = (
    "......kkkk......",
    "....kksssskk....",
    "...kssssssssk...",
    "..kwwssssssssk..",
    ".kswwwssssssssk.",
    ".ksswwwsssssssk.",
    "ksssswddddsssssk",
    "ksssssd..dsssssk",
    "ksssssd..dyssssk",
    "ksssssddddcysssk",
    ".kssssssycccysk.",
    ".ksssssssycccyk.",
    "..ksssssssycck..",
    "...ksssssssyk...",
    "....kksssskk....",
    "......kkkk......",
)

NOTE = (
    "...kkkkkk",
    "...kkkkkk",
    "...k....k",
    "...k....k",
    "...k....k",
    "...k....k",
    ".kkk..kkk",
    "kkkk.kkkk",
    "kkkk.kkkk",
    ".kk...kk.",
)

GLOBE = (
    ".....kkkkkk.....",
    "...kkbbGGbbkk...",
    "..kbbGGGGbbbbk..",
    ".kbcGGGGGbbbbbk.",
    ".kbbGGGbbbGGbbk.",
    "kbbbbGGbbGGGGbbk",
    "kbbbbbGbbGGGGbbk",
    "kbbbbbbbbbGGGbbk",
    "kbbbbbbbbbGGbbbk",
    "kbbGGbbbbbbbbbbk",
    "kbGGGGGbbbbbbbbk",
    ".kbGGGGbbbbbbbk.",
    ".kbbGGGbbbbbbbk.",
    "..kbbbGbbbbbbk..",
    "...kkbbbbbbkk...",
    ".....kkkkkk.....",
)

FOLDER = (
    "................",
    "................",
    "..kkkk..........",
    ".kwyyyk.........",
    "kwyyyyykkkkkkkk.",
    "kwwwwwwwwwwwwwok",
    "kwyyyyyyyyyyyyok",
    "kwyyyyyyyyyyyyok",
    "kwyyyyyyyyyyyyok",
    "kwyyyyyyyyyyyyok",
    "kwyyyyyyyyyyyyok",
    "kwyyyyyyyyyyyyok",
    "kwyyyyyyyyyyyyok",
    "kooooooooooooook",
    "kkkkkkkkkkkkkkkk",
    "................",
)

CHECK_MARK = (
    "......k",
    ".....kk",
    "k...kkk",
    "kk.kkk.",
    "kkkkk..",
    ".kkk...",
    "..k....",
)

ARROW_UP = ("...k...", "..kkk..", ".kkkkk.", "kkkkkkk")
ARROW_DOWN = ARROW_UP[::-1]

ICON_WAITING = (
    "kkkkkkkkk",
    ".kwwwwwk.",
    "..kwwwk..",
    "...kyk...",
    "....k....",
    "...kwk...",
    "..kwywk..",
    ".kyyyyyk.",
    "kkkkkkkkk",
)
ICON_ACTIVE = (
    "...nnn...",
    "...nnn...",
    "...nnn...",
    "...nnn...",
    "nnnnnnnnn",
    ".nnnnnnn.",
    "..nnnnn..",
    "...nnn...",
    "....n....",
)
ICON_DONE = (
    "........G",
    ".......GG",
    "......GGG",
    "G....GGG.",
    "GG..GGG..",
    "GGGGGG...",
    ".GGGG....",
    "..GG.....",
    ".........",
)
ICON_ERROR = (
    "rr.....rr",
    "rrr...rrr",
    ".rrr.rrr.",
    "..rrrrr..",
    "...rrr...",
    "..rrrrr..",
    ".rrr.rrr.",
    "rrr...rrr",
    "rr.....rr",
)
ICON_CANCELLED = tuple(row.replace("r", "d") for row in ICON_ERROR)


# -- theme state and scaling ---------------------------------------------------------

class _Theme:
    scale = 1.0   # 1.0 at 96 DPI
    unit = 1      # device pixels per "Windows 98 pixel"
    font = bold = title = glyph = None
    images = {}   # keeps ttk element images alive


theme = _Theme()


def px(value):
    """Scale a size given in 96-DPI pixels to this screen."""
    return int(round(value * theme.scale))


def enable_dpi_awareness():
    """Sharp text on high-DPI Windows screens. Call before creating Tk()."""
    if sys.platform != "win32":
        return
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def set_app_id(app_id):
    """Group the app under its own taskbar icon instead of python.exe's."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:
            pass


def init(root):
    """Set up fonts, scaling and ttk styles. Call once, right after Tk()."""
    # Windows scales in 25 % steps; rounding also absorbs DPI values like 143.9.
    theme.scale = max(1.0, round(root.winfo_fpixels("1i") / 96.0 * 4) / 4)
    theme.unit = max(1, int(theme.scale + 0.5))

    families = set(tkfont.families(root))
    candidates = ["Microsoft Sans Serif", "Tahoma", "Arial", "Liberation Sans", "Helvetica", "DejaVu Sans"]
    if theme.scale == 1.0:
        candidates.insert(0, "MS Sans Serif")  # the real bitmap font, crisp only at 100%
    family = next((f for f in candidates if f in families), None)
    family = family or tkfont.nametofont("TkDefaultFont").actual("family")
    serif = next((f for f in ("Times New Roman", "Liberation Serif", "Times") if f in families), family)

    theme.font = tkfont.Font(root, family=family, size=-px(11))
    theme.bold = tkfont.Font(root, family=family, size=-px(11), weight="bold")
    theme.title = tkfont.Font(root, family=family, size=-px(15), weight="bold")
    theme.glyph = tkfont.Font(root, family=serif, size=-px(22), weight="bold")
    root.option_add("*Font", theme.font)
    root.configure(bg=FACE)
    _setup_ttk(root)


def style_window(window):
    """Windows 11: navy title bar with white text and square corners."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        window.update_idletasks()
        hwnd = int(window.wm_frame(), 16)

        def set_attribute(attribute, value):
            value = ctypes.c_int(value)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value))

        set_attribute(33, 1)         # DWMWA_WINDOW_CORNER_PREFERENCE = do not round
        set_attribute(34, 0xC0C0C0)  # DWMWA_BORDER_COLOR (colours are 0x00BBGGRR)
        set_attribute(35, 0x800000)  # DWMWA_CAPTION_COLOR = navy
        set_attribute(36, 0xFFFFFF)  # DWMWA_TEXT_COLOR = white
    except Exception:
        pass  # older Windows keeps its normal title bar


# -- drawing helpers ---------------------------------------------------------------

def _size(widget):
    """Current size of a widget, or its requested size before it is shown."""
    width, height = widget.winfo_width(), widget.winfo_height()
    if width <= 1 or height <= 1:
        width, height = int(widget.cget("width")), int(widget.cget("height"))
    return width, height


def _bevel_rects(x0, y0, x1, y1, rings):
    u = theme.unit
    for light, dark in rings:
        yield dark, (x0, y1 - u, x1, y1)
        yield dark, (x1 - u, y0, x1, y1)
        yield light, (x0, y0, x1 - u, y0 + u)
        yield light, (x0, y0, x0 + u, y1 - u)
        x0, y0, x1, y1 = x0 + u, y0 + u, x1 - u, y1 - u


def draw_bevel(canvas, x0, y0, x1, y1, rings):
    """Draw a bevel on a canvas and return the rectangle inside it."""
    for color, rect in _bevel_rects(x0, y0, x1, y1, rings):
        canvas.create_rectangle(*rect, fill=color, outline="")
    t = len(rings) * theme.unit
    return x0 + t, y0 + t, x1 - t, y1 - t


def bevel_image(width, height, rings, fill=FACE):
    image = tk.PhotoImage(width=width, height=height)
    image.put(fill, to=(0, 0, width, height))
    for color, rect in _bevel_rects(0, 0, width, height, rings):
        image.put(color, to=rect)
    return image


def draw_focus(canvas, x0, y0, x1, y1):
    """The dotted focus rectangle."""
    u = theme.unit
    for x in range(x0, x1, 2 * u):
        canvas.create_rectangle(x, y0, x + u, y0 + u, fill=TEXT, outline="")
        canvas.create_rectangle(x, y1 - u, x + u, y1, fill=TEXT, outline="")
    for y in range(y0 + 2 * u, y1 - u, 2 * u):
        canvas.create_rectangle(x0, y, x0 + u, y + u, fill=TEXT, outline="")
        canvas.create_rectangle(x1 - u, y, x1, y + u, fill=TEXT, outline="")


def draw_text(canvas, x, y, text, underline=-1, enabled=True, anchor="center"):
    """Text with an optional mnemonic underline; disabled text is embossed."""
    font = theme.font
    width, height = font.measure(text), font.metrics("linespace")
    if anchor == "center":
        x -= width // 2
    y -= height // 2
    u = theme.unit
    for offset, color in ([(0, TEXT)] if enabled else [(u, HILIGHT), (0, GRAYTEXT)]):
        tx, ty = x + offset, y + offset
        canvas.create_text(tx, ty, text=text, font=font, fill=color, anchor="nw")
        if 0 <= underline < len(text):
            ux = tx + font.measure(text[:underline])
            uy = ty + font.metrics("ascent") + u
            canvas.create_rectangle(ux, uy, ux + font.measure(text[underline]), uy + u, fill=color, outline="")
    return x, y, width, height


def _pixel_runs(rows):
    """(x, y, end_x, colour) for every horizontal run of one colour."""
    for y, row in enumerate(rows):
        x = 0
        while x < len(row):
            end = x
            while end < len(row) and row[end] == row[x]:
                end += 1
            if row[x] != ".":
                yield x, y, end, PALETTE[row[x]]
            x = end


def paint(image, rows, zoom=1, dx=0, dy=0):
    """Paint pixel art onto a PhotoImage; (dx, dy) are in art pixels."""
    for x, y, end, color in _pixel_runs(rows):
        image.put(color, to=((dx + x) * zoom, (dy + y) * zoom, (dx + end) * zoom, (dy + y + 1) * zoom))
    return image


def pixel_image(rows, zoom=1, width=None, height=None, dx=0, dy=0):
    width = width or len(rows[0])
    height = height or len(rows)
    return paint(tk.PhotoImage(width=width * zoom, height=height * zoom), rows, zoom, dx, dy)


def draw_pixels(canvas, rows, x0, y0, zoom):
    for x, y, end, color in _pixel_runs(rows):
        canvas.create_rectangle(x0 + x * zoom, y0 + y * zoom, x0 + end * zoom, y0 + (y + 1) * zoom,
                                fill=color, outline="")


def app_icon(zoom=1):
    """The program icon: a CD."""
    return pixel_image(CD, zoom)


# -- keyboard mnemonics --------------------------------------------------------------

def split_mnemonic(text):
    """'&Download' -> ('Download', 0): the letter after & is underlined."""
    index = text.find("&")
    if index < 0:
        return text, -1
    return text[:index] + text[index + 1:], index


def bind_mnemonic(widget, letter, action):
    """Alt+letter anywhere in the widget's window runs `action`.

    Not on a Mac: Option+letter types special characters there and
    Command+letter is taken by copy/paste and friends.
    """
    if sys.platform == "darwin":
        return

    def handler(event):
        if widget.winfo_viewable():
            action()
        return "break"

    top = widget.winfo_toplevel()
    for key in {letter.lower(), letter.upper()}:
        top.bind(f"<Alt-KeyPress-{key}>", handler)


def bind_context_menu(widget, handler):
    """Right-click opens a context menu (on a Mac also Control-click)."""
    widget.bind("<Button-3>", handler)
    if sys.platform == "darwin":
        widget.bind("<Button-2>", handler)  # Tk 8.6 on macOS numbers the right button 2
        widget.bind("<Control-Button-1>", handler)


# -- ttk (list view and scroll bar) ---------------------------------------------------

def _setup_ttk(root):
    style = ttk.Style(root)
    if "win98" in style.theme_names():
        style.theme_use("win98")
        return
    style.theme_create("win98", parent="clam")
    style.theme_use("win98")

    u = theme.unit
    size = 16 * u
    images = theme.images
    images["trough"] = trough = tk.PhotoImage(width=2 * u, height=2 * u)  # the dithered track
    trough.put(FACE, to=(0, 0, 2 * u, 2 * u))
    trough.put(HILIGHT, to=(0, 0, u, u))
    trough.put(HILIGHT, to=(u, u, 2 * u, 2 * u))
    images["raised"] = bevel_image(size, size, RAISED)
    images["pressed"] = bevel_image(size, size, PRESSED)
    images["up"] = paint(bevel_image(size, size, RAISED), ARROW_UP, u, dx=4, dy=6)
    images["down"] = paint(bevel_image(size, size, RAISED), ARROW_DOWN, u, dx=4, dy=6)
    images["up_pressed"] = paint(bevel_image(size, size, PRESSED), ARROW_UP, u, dx=5, dy=7)
    images["down_pressed"] = paint(bevel_image(size, size, PRESSED), ARROW_DOWN, u, dx=5, dy=7)

    style.element_create("Vertical.Scrollbar.trough", "image", trough, sticky="nsew")
    style.element_create("Vertical.Scrollbar.thumb", "image", images["raised"], border=2 * u, sticky="nsew")
    style.element_create("Vertical.Scrollbar.uparrow", "image", images["up"],
                         ("pressed", images["up_pressed"]), sticky="")
    style.element_create("Vertical.Scrollbar.downarrow", "image", images["down"],
                         ("pressed", images["down_pressed"]), sticky="")
    style.layout("Vertical.TScrollbar", [
        ("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
            ("Vertical.Scrollbar.uparrow", {"side": "top", "sticky": ""}),
            ("Vertical.Scrollbar.downarrow", {"side": "bottom", "sticky": ""}),
            ("Vertical.Scrollbar.thumb", {"sticky": "nswe", "unit": "1"}),
        ]}),
    ])

    style.element_create("Treeheading.cell", "image", images["raised"],
                         ("pressed", images["pressed"]), border=2 * u, sticky="nsew")
    style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    style.layout("Treeview.Heading", [
        ("Treeheading.cell", {"sticky": "nswe"}),
        ("Treeheading.padding", {"sticky": "nswe", "children": [
            ("Treeheading.image", {"side": "right", "sticky": ""}),
            ("Treeheading.text", {"sticky": "we"}),
        ]}),
    ])
    style.layout("Treeview.Item", [  # no expand/collapse indicator: the list is flat
        ("Treeitem.padding", {"sticky": "nswe", "children": [
            ("Treeitem.image", {"side": "left", "sticky": ""}),
            ("Treeitem.focus", {"side": "left", "sticky": "", "children": [
                ("Treeitem.text", {"side": "left", "sticky": ""}),
            ]}),
        ]}),
    ])

    style.configure(".", background=FACE, foreground=TEXT, font=theme.font)
    style.configure("Treeview", background=WINDOW, fieldbackground=WINDOW, foreground=TEXT,
                    font=theme.font, borderwidth=0,
                    rowheight=max(theme.font.metrics("linespace") + px(4), 11 * u))
    style.map("Treeview", background=[("selected", SELECT)], foreground=[("selected", SELECT_TEXT)])
    style.configure("Treeview.Heading", font=theme.font, padding=(px(5), px(2)))


# -- containers -------------------------------------------------------------------------

class Bevel(tk.Frame):
    """A frame with a bevel border. Put its content in `.inner`."""

    def __init__(self, master, rings=SUNKEN, bg=WINDOW):
        super().__init__(master, bg=FACE)
        self.rings = rings
        self._canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self._canvas.place(x=0, y=0, relwidth=1, relheight=1)
        border = len(rings) * theme.unit
        self.inner = tk.Frame(self, bg=bg)
        self.inner.pack(fill="both", expand=True, padx=border, pady=border)
        self._canvas.bind("<Configure>", self._draw)

    def _draw(self, event=None):
        self._canvas.delete("all")
        draw_bevel(self._canvas, 0, 0, self._canvas.winfo_width(), self._canvas.winfo_height(), self.rings)


class GroupBox(tk.Frame):
    """Etched frame with a caption. Put its content in `.body`."""

    def __init__(self, master, text):
        super().__init__(master, bg=FACE)
        self.text = text
        self._canvas = tk.Canvas(self, bg=FACE, highlightthickness=0, bd=0)
        self._canvas.place(x=0, y=0, relwidth=1, relheight=1)
        line = theme.font.metrics("linespace")
        self.body = tk.Frame(self, bg=FACE)
        self.body.pack(fill="both", expand=True, padx=px(10), pady=(line + px(4), px(10)))
        self._canvas.bind("<Configure>", self._draw)

    def _draw(self, event=None):
        c = self._canvas
        c.delete("all")
        line = theme.font.metrics("linespace")
        draw_bevel(c, 0, line // 2, c.winfo_width(), c.winfo_height(), ETCHED)
        x = px(8)
        c.create_rectangle(x - px(2), 0, x + theme.font.measure(self.text) + px(2), line, fill=FACE, outline="")
        c.create_text(x, 0, text=self.text, anchor="nw", font=theme.font, fill=TEXT)


class Separator(tk.Frame):
    """Etched horizontal line."""

    def __init__(self, master):
        super().__init__(master, bg=HILIGHT, height=2 * theme.unit)
        self.pack_propagate(False)
        tk.Frame(self, bg=SHADOW, height=theme.unit).pack(fill="x", side="top")


# -- controls ---------------------------------------------------------------------------

def label(master, text, buddy=None, **options):
    """A label; with `buddy`, Alt+underlined letter focuses that widget."""
    text, underline = split_mnemonic(text)
    widget = tk.Label(master, text=text, underline=underline, bg=options.pop("bg", FACE), fg=TEXT,
                      font=options.pop("font", theme.font), **options)
    if buddy is not None and underline >= 0:
        bind_mnemonic(widget, text[underline], buddy.focus_set)
    return widget


class EllipsisLabel(tk.Label):
    """Label that cuts long text short with '...' instead of widening the window."""

    def __init__(self, master, text="", width=1, **options):
        options.setdefault("bg", FACE)
        options.setdefault("fg", TEXT)
        super().__init__(master, width=width, anchor="w", font=theme.font, **options)
        self._text = ""
        self.bind("<Configure>", lambda e: self._fit())
        self.set(text)

    def set(self, text):
        self._text = text
        self._fit()

    def get(self):
        return self._text

    def _fit(self):
        text, font = self._text, theme.font
        pad = self.winfo_pixels(self.cget("padx")) + self.winfo_pixels(self.cget("bd"))
        room = self.winfo_width() - 2 * pad - 2
        if self.winfo_width() > 1 and font.measure(text) > room:
            low, high = 0, len(text)
            while low < high:
                mid = (low + high + 1) // 2
                if font.measure(text[:mid] + "...") <= room:
                    low = mid
                else:
                    high = mid - 1
            text = text[:low].rstrip() + "..."
        self.configure(text=text)


class Button(tk.Canvas):
    """Push button with a 3D bevel, mnemonic underline and dotted focus."""

    def __init__(self, master, text, command=None, default=False, width=75):
        self.text, self.underline = split_mnemonic(text)
        font = theme.font
        super().__init__(master, bg=FACE, highlightthickness=0, bd=0, takefocus=1,
                         width=max(px(width), font.measure(self.text) + px(16)),
                         height=max(px(23), font.metrics("linespace") + px(10)))
        self.command = command
        self.default = default
        self.enabled = True
        self._armed = False      # mouse button went down on us
        self._inside = False
        self._key_down = False   # space bar held
        self._focused = False
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", lambda e: self._on_hover(True))
        self.bind("<Leave>", lambda e: self._on_hover(False))
        self.bind("<FocusIn>", lambda e: self._on_focus(True))
        self.bind("<FocusOut>", lambda e: self._on_focus(False))
        self.bind("<KeyPress-space>", self._on_space_down)
        self.bind("<KeyRelease-space>", self._on_space_up)
        self.bind("<Return>", self._on_return)
        self.bind("<Configure>", lambda e: self._draw())
        if self.underline >= 0:
            bind_mnemonic(self, self.text[self.underline], self.invoke)
        self._draw()

    def set_enabled(self, enabled):
        if enabled != self.enabled:
            self.enabled = enabled
            self._armed = self._key_down = False
            self.configure(takefocus=1 if enabled else 0)
            self._draw()

    def invoke(self):
        if self.enabled and self.command:
            self.command()

    def _on_press(self, event):
        if self.enabled:
            self.focus_set()
            self._armed = self._inside = True
            self._draw()

    def _on_release(self, event):
        if self._armed:
            self._armed = False
            self._draw()
            if self._inside:
                self.invoke()

    def _on_hover(self, inside):
        self._inside = inside
        if self._armed:
            self._draw()

    def _on_focus(self, focused):
        self._focused = focused
        self._draw()

    def _on_space_down(self, event):
        if self.enabled and not self._key_down:
            self._key_down = True
            self._draw()
        return "break"

    def _on_space_up(self, event):
        if self._key_down:
            self._key_down = False
            self._draw()
            self.invoke()
        return "break"

    def _on_return(self, event):
        self.invoke()
        return "break"

    def _draw(self):
        self.delete("all")
        w, h = _size(self)
        down = (self._armed and self._inside) or self._key_down
        if self.default and self.enabled:
            rings = DEFAULT_PRESSED if down else DEFAULT
        else:
            rings = PRESSED if down else RAISED
        draw_bevel(self, 0, 0, w, h, rings)
        shift = theme.unit if down else 0
        draw_text(self, w // 2 + shift, h // 2 + shift, self.text, self.underline, self.enabled)
        if self._focused and self.enabled:
            inset = px(4)
            draw_focus(self, inset, inset, w - inset, h - inset)


class Checkbox(tk.Canvas):
    """Check box bound to a BooleanVar."""

    def __init__(self, master, text, variable, command=None):
        self.text, self.underline = split_mnemonic(text)
        self.variable = variable
        self.command = command
        font = theme.font
        self._box = 13 * theme.unit
        self._gap = px(5)
        super().__init__(master, bg=FACE, highlightthickness=0, bd=0, takefocus=1,
                         width=self._box + self._gap + font.measure(self.text) + px(3),
                         height=max(self._box, font.metrics("linespace")) + px(2))
        self._armed = self._inside = self._focused = False
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", lambda e: self._on_hover(True))
        self.bind("<Leave>", lambda e: self._on_hover(False))
        self.bind("<FocusIn>", lambda e: self._on_focus(True))
        self.bind("<FocusOut>", lambda e: self._on_focus(False))
        self.bind("<KeyPress-space>", lambda e: (self.toggle(), "break")[1])
        self.bind("<Configure>", lambda e: self._draw())
        trace = variable.trace_add("write", lambda *args: self._draw())
        self.bind("<Destroy>", lambda e: variable.trace_remove("write", trace))
        if self.underline >= 0:
            bind_mnemonic(self, self.text[self.underline], lambda: (self.focus_set(), self.toggle()))
        self._draw()

    def toggle(self):
        self.variable.set(not self.variable.get())
        if self.command:
            self.command()

    def _on_press(self, event):
        self.focus_set()
        self._armed = self._inside = True
        self._draw()

    def _on_release(self, event):
        if self._armed:
            self._armed = False
            if self._inside:
                self.toggle()
            self._draw()

    def _on_hover(self, inside):
        self._inside = inside
        if self._armed:
            self._draw()

    def _on_focus(self, focused):
        self._focused = focused
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = _size(self)
        u = theme.unit
        top = (h - self._box) // 2
        x0, y0, x1, y1 = draw_bevel(self, 0, top, self._box, top + self._box, SUNKEN)
        self.create_rectangle(x0, y0, x1, y1, fill=FACE if self._armed and self._inside else WINDOW, outline="")
        if self.variable.get():
            draw_pixels(self, CHECK_MARK, x0 + u, y0 + u, u)
        x, y, tw, th = draw_text(self, self._box + self._gap, h // 2, self.text, self.underline, anchor="w")
        if self._focused:
            draw_focus(self, x - u, max(0, y - u), min(w, x + tw + 2 * u), min(h, y + th + u))


class Entry(Bevel):
    """Sunken one-line text field; the tk.Entry itself is `.entry`."""

    def __init__(self, master, textvariable=None, width=30):
        super().__init__(master, SUNKEN, WINDOW)
        self.entry = tk.Entry(
            self.inner, textvariable=textvariable, width=width, relief="flat", bd=0,
            highlightthickness=0, bg=WINDOW, fg=TEXT, font=theme.font,
            disabledbackground=FACE, readonlybackground=FACE,
            insertbackground=TEXT, insertwidth=theme.unit,
            selectbackground=SELECT, selectforeground=SELECT_TEXT, selectborderwidth=0)
        self.entry.pack(fill="both", expand=True, padx=px(2), pady=px(2))
        bind_context_menu(self.entry, self._context_menu)
        self.entry.bind("<Control-a>", self._select_all)
        self.entry.bind("<Control-A>", self._select_all)

    def focus_set(self):
        self.entry.focus_set()
        self._select_all()

    def _select_all(self, event=None):
        self.entry.select_range(0, "end")
        self.entry.icursor("end")
        return "break"

    def _context_menu(self, event):
        entry = self.entry
        selected = "normal" if entry.selection_present() else "disabled"
        try:
            entry.clipboard_get()
            can_paste = "normal"
        except tk.TclError:
            can_paste = "disabled"
        menu = make_menu(entry)
        menu.add_command(label="Cut", underline=2, state=selected, command=lambda: entry.event_generate("<<Cut>>"))
        menu.add_command(label="Copy", underline=0, state=selected, command=lambda: entry.event_generate("<<Copy>>"))
        menu.add_command(label="Paste", underline=0, state=can_paste,
                         command=lambda: entry.event_generate("<<Paste>>"))
        menu.add_command(label="Delete", underline=0, state=selected,
                         command=lambda: entry.event_generate("<<Clear>>"))
        menu.add_separator()
        menu.add_command(label="Select All", underline=7, command=self._select_all)
        entry.focus_set()
        menu.tk_popup(event.x_root, event.y_root)


class ProgressBar(tk.Canvas):
    """Sunken bar filled with navy blocks."""

    def __init__(self, master):
        super().__init__(master, bg=FACE, highlightthickness=0, bd=0, width=px(200), height=px(18))
        self._value = 0.0
        self.bind("<Configure>", lambda e: self._draw())

    def set(self, fraction):
        fraction = min(1.0, max(0.0, fraction or 0.0))
        if fraction != self._value:
            self._value = fraction
            self._draw()

    def _draw(self):
        self.delete("all")
        w, h = _size(self)
        u = theme.unit
        x0, y0, x1, y1 = draw_bevel(self, 0, 0, w, h, THIN_SUNKEN)
        x0, y0, x1, y1 = x0 + u, y0 + u, x1 - u, y1 - u
        block, gap = px(8), px(2)
        capacity = max(1, (x1 - x0 + gap) // (block + gap))
        for i in range(int(capacity * self._value + 1e-9)):  # whole blocks only, like the original
            bx = x0 + i * (block + gap)
            self.create_rectangle(bx, y0, bx + block, y1, fill=SELECT, outline="")


class TransferAnimation(tk.Canvas):
    """Internet Explorer's download animation: a note flies from a globe to a folder."""

    FRAMES = 22
    STAGE = 280  # widest distance between the two icons, in 96-DPI pixels

    def __init__(self, master):
        zoom = 2 * theme.unit
        self._globe_image = pixel_image(GLOBE, zoom)
        self._folder_image = pixel_image(FOLDER, zoom)
        self._note_image = pixel_image(NOTE, zoom)
        self._icon = 16 * zoom
        super().__init__(master, bg=FACE, highlightthickness=0, bd=0,
                         width=px(200), height=self._icon + px(14))
        self._globe = self.create_image(0, 0, image=self._globe_image, anchor="nw")
        self._folder = self.create_image(0, 0, image=self._folder_image, anchor="nw")
        self._note = self.create_image(0, 0, image=self._note_image, anchor="nw", state="hidden")
        self._frame = 0
        self._job = None
        self.bind("<Configure>", lambda e: self._layout())

    @property
    def running(self):
        return self._job is not None

    def start(self):
        if self._job is None:
            self.itemconfigure(self._note, state="normal")
            self._tick()

    def stop(self):
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None
        self.itemconfigure(self._note, state="hidden")

    def _layout(self):
        w, h = _size(self)
        stage = min(w, px(self.STAGE))
        left = (w - stage) // 2
        top = h - self._icon - px(2)
        self.coords(self._globe, left, top)
        self.coords(self._folder, left + stage - self._icon, top)
        self._place_note()

    def _tick(self):
        self._frame = (self._frame + 1) % self.FRAMES
        self._place_note()
        self._job = self.after(60, self._tick)

    def _place_note(self):
        w, h = _size(self)
        stage = min(w, px(self.STAGE))
        left = (w - stage) // 2
        note_w, note_h = self._note_image.width(), self._note_image.height()
        start, end = left + self._icon, left + stage - self._icon - note_w
        t = self._frame / (self.FRAMES - 1)
        base = h - px(2) - self._icon // 2 - note_h // 2
        x = start + (end - start) * t
        y = base - px(10) * 4 * t * (1 - t)
        step = 2 * theme.unit  # move in whole "pixels" for a chunky look
        self.coords(self._note, int(x) // step * step, int(y) // step * step)


# -- menus ------------------------------------------------------------------------------

def make_menu(master):
    return tk.Menu(master, tearoff=0, bg=FACE, fg=TEXT, activebackground=SELECT,
                   activeforeground=SELECT_TEXT, disabledforeground=GRAYTEXT, selectcolor=TEXT,
                   font=theme.font, relief="raised", bd=2 * theme.unit, activeborderwidth=0)


class MenuBar(tk.Frame):
    """Classic menu bar drawn in the window (the native one can't be recoloured)."""

    def __init__(self, master):
        super().__init__(master, bg=FACE)

    def add_menu(self, text, menu):
        item = _MenuBarItem(self, text, menu)
        item.pack(side="left")
        return item


class _MenuBarItem(tk.Canvas):
    def __init__(self, bar, text, menu):
        self.text, self.underline = split_mnemonic(text)
        self.menu = menu
        font = theme.font
        super().__init__(bar, bg=FACE, highlightthickness=0, bd=0,
                         width=font.measure(self.text) + px(12), height=font.metrics("linespace") + px(6))
        self._state = "normal"  # "hot" under the mouse, "open" while its menu shows
        self.bind("<Enter>", lambda e: self._state == "normal" and self._set("hot"))
        self.bind("<Leave>", lambda e: self._state == "hot" and self._set("normal"))
        self.bind("<ButtonPress-1>", lambda e: self.open())
        self.bind("<Configure>", lambda e: self._draw())
        if self.underline >= 0:
            bind_mnemonic(self, self.text[self.underline], self.open)
        self._draw()

    def open(self):
        self._set("open")
        self.menu.tk_popup(self.winfo_rootx(), self.winfo_rooty() + self.winfo_height())
        self.after(150, self._wait_until_closed)  # tk_popup blocks on Windows, not on X11

    def _wait_until_closed(self):
        if self.menu.winfo_ismapped():
            self.after(150, self._wait_until_closed)
        else:
            self._set("normal")

    def _set(self, state):
        self._state = state
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = _size(self)
        shift = 0
        if self._state == "hot":
            draw_bevel(self, 0, 0, w, h, THIN_RAISED)
        elif self._state == "open":
            draw_bevel(self, 0, 0, w, h, THIN_SUNKEN)
            shift = theme.unit
        draw_text(self, w // 2 + shift, h // 2 + shift, self.text, self.underline)


# -- status bar -------------------------------------------------------------------------

class SizeGrip(tk.Canvas):
    """The ridged corner that resizes the window."""

    def __init__(self, master):
        u, n = theme.unit, 12
        cursor = "size_nw_se" if sys.platform == "win32" else "bottom_right_corner"
        super().__init__(master, bg=FACE, highlightthickness=0, bd=0, width=n * u, height=n * u, cursor=cursor)
        ridges = {11: HILIGHT, 10: SHADOW, 9: SHADOW, 7: HILIGHT, 6: SHADOW, 5: SHADOW,
                  3: HILIGHT, 2: SHADOW, 1: SHADOW}
        for row in range(n):
            for col in range(n):
                color = ridges.get((n - 1 - row) + (n - 1 - col))
                if color:
                    self.create_rectangle(col * u, row * u, (col + 1) * u, (row + 1) * u, fill=color, outline="")
        self.bind("<ButtonPress-1>", self._start)
        self.bind("<B1-Motion>", self._drag)

    def _start(self, event):
        top = self.winfo_toplevel()
        self._origin = (event.x_root, event.y_root, top.winfo_width(), top.winfo_height())

    def _drag(self, event):
        x, y, width, height = self._origin
        self.winfo_toplevel().geometry(f"{max(1, width + event.x_root - x)}x{max(1, height + event.y_root - y)}")


class StatusBar(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=FACE)
        SizeGrip(self).pack(side="right", anchor="se")

    def add_pane(self, text="", width=1, expand=False):
        """Add a sunken pane; returns its EllipsisLabel (use .set() to change it)."""
        pane = Bevel(self, THIN_SUNKEN, FACE)
        text_label = EllipsisLabel(pane.inner, text, width=width, padx=px(2))
        text_label.pack(fill="both", expand=True)
        pane.pack(side="left", fill="both", expand=expand, padx=(px(2), 0), pady=(px(2), 0))
        return text_label


# -- message boxes ----------------------------------------------------------------------

def _draw_dialog_icon(canvas, kind):
    u, s = theme.unit, px(32)
    if kind == "error":  # red circle with a white cross
        canvas.create_oval(2 * u, 2 * u, s, s, fill=SHADOW, outline="")
        canvas.create_oval(0, 0, s - 2 * u, s - 2 * u, fill="#FF0000", outline="#800000", width=u)
        a, b = px(9), s - 2 * u - px(9)
        canvas.create_line(a, a, b, b, fill=HILIGHT, width=px(3))
        canvas.create_line(a, b, b, a, fill=HILIGHT, width=px(3))
    elif kind == "warning":  # yellow triangle with "!"
        triangle = (s // 2 - u, 0, s - 2 * u, s - 3 * u, 0, s - 3 * u)
        canvas.create_polygon([v + 2 * u for v in triangle], fill=SHADOW, outline="")
        canvas.create_polygon(triangle, fill="#FFFF00", outline=TEXT, width=u)
        canvas.create_text(s // 2 - u, s * 0.58, text="!", font=theme.glyph, fill=TEXT)
    else:  # "info" / "question": speech balloon
        bw, bh = s - 2 * u, int(s * 0.78)
        canvas.create_oval(2 * u, 2 * u, bw + 2 * u, bh + 2 * u, fill=SHADOW, outline="")
        canvas.create_polygon(px(7), bh - px(6), px(5), s - u, px(15), bh - px(3),
                              fill=WINDOW, outline=TEXT, width=u)
        canvas.create_oval(0, 0, bw, bh, fill=WINDOW, outline=TEXT, width=u)
        canvas.create_rectangle(px(8), bh - px(7), px(14), bh - px(2), fill=WINDOW, outline="")
        canvas.create_text(bw // 2, bh // 2, text="i" if kind == "info" else "?", font=theme.glyph, fill="#0000FF")


class MessageDialog(tk.Toplevel):
    """Modal message box. After it closes, `.result` is the index of the button pressed."""

    def __init__(self, parent, title, message, icon="info", buttons=("OK",), default=0, cancel=0):
        super().__init__(parent, bg=FACE)
        self.withdraw()
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.result = cancel

        body = tk.Frame(self, bg=FACE)
        body.pack(fill="both", padx=px(12), pady=px(12))
        art = tk.Canvas(body, width=px(34), height=px(34), bg=FACE, highlightthickness=0, bd=0)
        _draw_dialog_icon(art, icon)
        art.grid(row=0, column=0, sticky="n", padx=(0, px(14)))
        tk.Label(body, text=message, justify="left", anchor="w", wraplength=px(330),
                 bg=FACE, fg=TEXT, font=theme.font).grid(row=0, column=1, sticky="w")

        row = tk.Frame(self, bg=FACE)
        row.pack(pady=(0, px(12)))
        buttons = [Button(row, text, command=lambda i=i: self.close(i), default=i == default)
                   for i, text in enumerate(buttons)]
        for button in buttons:
            button.pack(side="left", padx=px(3))
        self.bind("<Escape>", lambda e: self.close(cancel))
        self.protocol("WM_DELETE_WINDOW", lambda: self.close(cancel))

        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_reqwidth()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_reqheight()) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.deiconify()
        style_window(self)
        self.wait_visibility()
        self.grab_set()
        buttons[default].focus_set()
        if icon in ("error", "warning"):
            self.bell()
        self.wait_window()

    def close(self, result):
        self.result = result
        self.destroy()


def show_message(parent, title, message, icon="info"):
    MessageDialog(parent, title, message, icon)


def ask_yes_no(parent, title, message, icon="question"):
    return MessageDialog(parent, title, message, icon, ("&Yes", "&No"), default=0, cancel=1).result == 0
