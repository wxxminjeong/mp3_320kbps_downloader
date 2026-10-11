"""The main window: link box, progress panel and download list."""

import json
import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from dataclasses import dataclass, field
from tkinter import filedialog, ttk

import downloader
import updater
import win98
from win98 import FACE, WINDOW, TEXT, px

APP_NAME = "MP3 320kbps Downloader"
APP_VERSION = "2.0"


# -- settings ----------------------------------------------------------------------------

def _settings_path():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "MP3_320kbps_Downloader", "settings.json")


def _default_folder():
    folder = os.path.join(os.path.expanduser("~"), "Downloads")
    return folder if os.path.isdir(folder) else os.path.expanduser("~")


def load_settings():
    settings = {"folder": _default_folder(), "playlist": False, "square_cover": True, "skipped_version": ""}
    try:
        with open(_settings_path(), encoding="utf-8") as f:
            saved = json.load(f)
        settings.update({k: v for k, v in saved.items() if k in settings and type(v) is type(settings[k])})
    except (OSError, ValueError):
        pass
    return settings


def save_settings(settings):
    path = _settings_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except OSError:
        pass


# -- helpers -----------------------------------------------------------------------------

def parse_links(text):
    """Every http(s) link in the text; bare 'youtube.com/...' / 'youtu.be/...' get https://."""
    links = []
    for word in text.split():
        if re.match(r"(?:www\.|m\.|music\.)?(?:youtube\.com|youtu\.be)/", word, re.I):
            word = "https://" + word
        if re.match(r"https?://[^/\s]+\.[^/\s]+", word, re.I) and word not in links:
            links.append(word)
    return links


def format_size(n):
    if n is None:
        return "?"
    for unit in ("bytes", "KB", "MB"):
        if n < 1024 or unit == "MB":
            return f"{n:.0f} {unit}" if unit == "bytes" else f"{n:.1f} {unit}"
        n /= 1024


def format_time(seconds):
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds} sec"
    if seconds < 3600:
        return f"{seconds // 60} min {seconds % 60} sec"
    return f"{seconds // 3600} hr {seconds % 3600 // 60} min"


def reveal(path):
    """Open the folder in the file manager, with the file selected where possible."""
    folder = path if os.path.isdir(path) else os.path.dirname(path)
    try:
        if sys.platform == "win32":
            if os.path.isfile(path):
                subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
            else:
                os.startfile(folder)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path] if os.path.isfile(path) else ["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])
    except OSError:
        pass


@dataclass
class Row:
    """One line of the download list."""
    url: str
    options: downloader.Options
    title: str = ""
    state: str = "waiting"  # waiting / running / done / error / cancelled
    message: str = ""
    files: list = field(default_factory=list)


# -- the window --------------------------------------------------------------------------

class App:
    def __init__(self, root):
        self.root = root
        root.title(APP_NAME)
        win98.init(root)

        self.settings = load_settings()
        self.url_var = tk.StringVar()
        self.folder_var = tk.StringVar(value=self.settings["folder"])
        self.playlist_var = tk.BooleanVar(value=self.settings["playlist"])
        self.square_var = tk.BooleanVar(value=self.settings["square_cover"])
        for var in (self.playlist_var, self.square_var):
            var.trace_add("write", lambda *args: self._save_settings())

        self.events = queue.Queue()
        self.manager = downloader.DownloadManager(
            self.events.put, ffmpeg=downloader.find_ffmpeg(), deno=downloader.find_deno())
        self.rows = {}
        self.current = None  # id of the job that is running
        self.saved_count = 0
        self.last_error = None
        self.pending_update = None  # found while downloading; offered once idle
        self.updating = False
        self.closed = False

        self.icons = {
            "waiting": win98.ICON_WAITING, "running": win98.ICON_ACTIVE, "done": win98.ICON_DONE,
            "error": win98.ICON_ERROR, "cancelled": win98.ICON_CANCELLED,
        }
        self.icons = {state: win98.pixel_image(art, win98.theme.unit, width=12, dx=1)
                      for state, art in self.icons.items()}
        self.app_icons = (win98.app_icon(2 * win98.theme.unit), win98.app_icon(win98.theme.unit))
        root.iconphoto(True, *self.app_icons)

        self._build()
        self._set_idle()
        self._update_queue_pane()
        if not self.manager.ffmpeg:
            self.status.set("FFmpeg was not found. Downloads can't be converted to MP3.")
        elif not self.manager.deno:
            self.status.set("Ready. (No JavaScript runtime found: some YouTube videos may fail.)")

        root.update_idletasks()
        root.minsize(root.winfo_reqwidth(), root.winfo_reqheight())
        root.protocol("WM_DELETE_WINDOW", self.quit)
        if sys.platform == "darwin":  # Command+Q and the app menu's About item
            root.createcommand("::tk::mac::Quit", self.quit)
            root.createcommand("tkAboutDialog", self.show_about)
        root.after(10, win98.style_window, root)
        root.after(60, self._poll)
        if not self.manager.ffmpeg:
            root.after(300, self._warn_no_ffmpeg)
        if updater.current_version():
            root.after(3000, self.check_for_updates, False)
            root.after(5000, updater.cleanup)
        self.url_entry.focus_set()

    # -- layout -------------------------------------------------------------------------

    def _build(self):
        root = self.root
        self._build_menus()
        self._build_header()
        win98.Separator(root).pack(fill="x")

        status = win98.StatusBar(root)
        status.pack(side="bottom", fill="x")
        self.status = status.add_pane(expand=True)
        self.queue_pane = status.add_pane(width=13)
        status.add_pane("MP3 · 320 kbps", width=15)

        body = tk.Frame(root, bg=FACE)
        body.pack(fill="both", expand=True, padx=px(10), pady=(px(8), px(2)))
        self._build_source(body)
        self._build_progress(body)
        self._build_list(body)
        self._build_buttons(body)

    def _build_menus(self):
        bar = win98.MenuBar(self.root)
        bar.pack(fill="x")

        file_menu = win98.make_menu(self.root)
        file_menu.add_command(label="Paste Link", underline=0, accelerator="Alt+P", command=self.paste)
        file_menu.add_command(label="Open Download Folder", underline=0, command=self.open_folder)
        file_menu.add_command(label="Clear Finished", underline=6, command=self.clear_finished)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", underline=1, command=self.quit)
        bar.add_menu("&File", file_menu)

        options_menu = win98.make_menu(self.root)
        options_menu.add_checkbutton(label="Download Whole Playlists", underline=15, variable=self.playlist_var)
        options_menu.add_checkbutton(label="Square Cover Art", underline=0, variable=self.square_var)
        options_menu.add_separator()
        options_menu.add_command(label="Change Download Folder...", underline=0, command=self.browse)
        bar.add_menu("&Options", options_menu)

        help_menu = win98.make_menu(self.root)
        help_menu.add_command(label="How to Use", underline=0, command=self.show_help)
        help_menu.add_command(label="Check for Updates...", underline=10, command=self.check_for_updates)
        help_menu.add_separator()
        help_menu.add_command(label=f"About {APP_NAME}", underline=0, command=self.show_about)
        bar.add_menu("&Help", help_menu)

    def _build_header(self):
        header = tk.Frame(self.root, bg=WINDOW)
        header.pack(fill="x")
        tk.Label(header, image=self.app_icons[0], bg=WINDOW).pack(side="right", padx=px(14), pady=px(8))
        text = tk.Frame(header, bg=WINDOW)
        text.pack(side="left", fill="x", padx=px(16), pady=px(8))
        tk.Label(text, text=APP_NAME, font=win98.theme.title, bg=WINDOW, fg=TEXT, anchor="w").pack(fill="x")
        tk.Label(text, text="Paste a YouTube link and get a 320 kbps MP3 with cover art and tags.",
                 bg=WINDOW, fg=TEXT, anchor="w").pack(fill="x", padx=(px(14), 0), pady=(px(3), 0))

    def _build_source(self, parent):
        group = win98.GroupBox(parent, "Download")
        group.pack(fill="x")
        g = group.body
        g.columnconfigure(1, weight=1)

        self.url_entry = win98.Entry(g, self.url_var, width=44)
        self.url_entry.entry.bind("<Return>", lambda e: self.download())
        win98.label(g, "&URL:", buddy=self.url_entry).grid(row=0, column=0, sticky="w", padx=(0, px(8)))
        self.url_entry.grid(row=0, column=1, sticky="we")
        win98.Button(g, "&Paste", command=self.paste).grid(row=0, column=2, padx=(px(6), 0))

        self.folder_entry = win98.Entry(g, self.folder_var)
        win98.label(g, "&Save in:", buddy=self.folder_entry).grid(row=1, column=0, sticky="w", pady=(px(6), 0))
        self.folder_entry.grid(row=1, column=1, sticky="we", pady=(px(6), 0))
        win98.Button(g, "&Browse...", command=self.browse).grid(row=1, column=2, padx=(px(6), 0), pady=(px(6), 0))

        checks = tk.Frame(g, bg=FACE)
        checks.grid(row=2, column=1, columnspan=2, sticky="w", pady=(px(6), 0))
        win98.Checkbox(checks, "Whole p&laylist", self.playlist_var).pack(side="left")
        win98.Checkbox(checks, "S&quare cover art", self.square_var).pack(side="left", padx=(px(16), 0))

    def _build_progress(self, parent):
        group = win98.GroupBox(parent, "Progress")
        group.pack(fill="x", pady=(px(8), 0))
        g = group.body
        self.animation = win98.TransferAnimation(g)
        self.animation.pack(fill="x")
        self.caption = win98.EllipsisLabel(g)
        self.caption.pack(fill="x", pady=(px(4), px(4)))
        self.bar = win98.ProgressBar(g)
        self.bar.pack(fill="x")

        info = tk.Frame(g, bg=FACE)
        info.pack(fill="x", pady=(px(6), 0))
        info.columnconfigure(1, weight=1)
        tk.Label(info, text="Time left:", bg=FACE, fg=TEXT).grid(row=0, column=0, sticky="w")
        tk.Label(info, text="Transfer rate:", bg=FACE, fg=TEXT).grid(row=1, column=0, sticky="w")
        self.time_left = win98.EllipsisLabel(info)
        self.time_left.grid(row=0, column=1, sticky="we", padx=(px(10), 0))
        self.rate = win98.EllipsisLabel(info)
        self.rate.grid(row=1, column=1, sticky="we", padx=(px(10), 0))

    def _build_list(self, parent):
        group = win98.GroupBox(parent, "Download list")
        group.pack(fill="both", expand=True, pady=(px(8), 0))
        frame = win98.Bevel(group.body)
        frame.pack(fill="both", expand=True)

        tree = self.tree = ttk.Treeview(frame.inner, columns=("status",), height=5, selectmode="browse")
        tree.heading("#0", text="Name", anchor="w")
        tree.heading("status", text="Status", anchor="w")
        tree.column("#0", width=px(270), minwidth=px(80), stretch=True)
        tree.column("status", width=px(130), minwidth=px(60), stretch=False)
        scrollbar = ttk.Scrollbar(frame.inner, orient="vertical", command=tree.yview)

        def set_scroll(first, last):  # only show the scroll bar when it is needed
            if float(first) <= 0 and float(last) >= 1:
                scrollbar.pack_forget()
            elif not scrollbar.winfo_ismapped():
                scrollbar.pack(side="right", fill="y", before=tree)
            scrollbar.set(first, last)

        tree.configure(yscrollcommand=set_scroll)
        tree.pack(side="left", fill="both", expand=True)
        tree.bind("<Double-1>", self._on_row_double_click)
        tree.bind("<Return>", self._on_row_double_click)
        tree.bind("<Delete>", lambda e: self.remove_selected())
        win98.bind_context_menu(tree, self._on_row_menu)

    def _build_buttons(self, parent):
        row = tk.Frame(parent, bg=FACE)
        row.pack(fill="x", pady=(px(10), px(6)))
        win98.Button(row, "Ope&n Folder", command=self.open_folder).pack(side="left")
        self.cancel_button = win98.Button(row, "&Cancel", command=self.cancel)
        self.cancel_button.pack(side="right")
        win98.Button(row, "&Download", command=self.download, default=True).pack(side="right", padx=(0, px(6)))

    # -- actions ------------------------------------------------------------------------

    def download(self):
        if self.updating:
            win98.show_message(self.root, APP_NAME, "An update is being installed. Please wait a moment.")
            return
        text = self.url_var.get().strip()
        links = parse_links(text)
        if not links:
            message = ("Paste a YouTube link first." if not text else
                       "That doesn't look like a link.\n\nIt should start with https:// "
                       "(for example https://youtu.be/...).")
            win98.show_message(self.root, APP_NAME, message, "warning")
            self.url_entry.focus_set()
            return
        if not self.manager.ffmpeg:
            self._warn_no_ffmpeg()
            return
        folder = self._ensure_folder()
        if not folder:
            return

        options = downloader.Options(folder, self.playlist_var.get(), self.square_var.get())
        for link in links:
            self._add(link, options)
        self.url_var.set("")
        self._update_queue_pane()

    def _add(self, url, options):
        job = self.manager.add(url, options)
        self.rows[job.id] = Row(url, options)
        self.tree.insert("", "end", iid=str(job.id), text=url, image=self.icons["waiting"], values=("Waiting",))
        self.tree.see(str(job.id))

    def _ensure_folder(self):
        folder = os.path.abspath(os.path.expanduser(self.folder_var.get().strip() or _default_folder()))
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as e:
            win98.show_message(self.root, APP_NAME, f"Can't use this folder:\n{folder}\n\n{e.strerror}", "error")
            return None
        self.folder_var.set(folder)
        self._save_settings()
        return folder

    def paste(self):
        try:
            text = self.root.clipboard_get().strip()
        except tk.TclError:
            text = ""
        if not text:
            self.root.bell()
            return
        self.url_var.set(text)
        self.url_entry.entry.icursor("end")
        self.url_entry.entry.focus_set()

    def browse(self):
        folder = filedialog.askdirectory(parent=self.root, initialdir=self.folder_var.get(),
                                         title="Choose a folder for your MP3s")
        if folder:
            self.folder_var.set(os.path.normpath(folder))
            self._save_settings()

    def open_folder(self):
        folder = self._ensure_folder()
        if folder:
            reveal(folder)

    def cancel(self):
        if self.current is not None:
            self.manager.cancel()
            self.caption.set("Cancelling...")

    def clear_finished(self):
        for job_id, row in list(self.rows.items()):
            if row.state in ("done", "error", "cancelled"):
                self.tree.delete(str(job_id))
                del self.rows[job_id]

    def remove_selected(self):
        for item in self.tree.selection():
            job_id = int(item)
            row = self.rows[job_id]
            if row.state == "running":
                self.root.bell()
                continue
            if row.state == "waiting":
                self.manager.remove(job_id)
            self.tree.delete(item)
            del self.rows[job_id]
        self._update_queue_pane()

    def retry(self, job_id):
        row = self.rows.pop(job_id)
        self.tree.delete(str(job_id))
        self._add(row.url, row.options)
        self._update_queue_pane()

    def copy_link(self, job_id):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.rows[job_id].url)

    def show_help(self):
        win98.show_message(self.root, "How to Use", (
            "1.  Copy a link from YouTube (a video, or a playlist).\n"
            "2.  Click Paste, or press Ctrl+V in the URL box.\n"
            "3.  Click Download (or press Enter).\n\n"
            "You can keep adding links while a download is running; they wait in the "
            "download list and start one after another.\n\n"
            "Double-click a finished item to show the MP3 in its folder. "
            "Right-click an item for more options."))

    def show_about(self):
        ffmpeg = self.manager.ffmpeg or "not found"
        deno = self.manager.deno or "not found"
        win98.show_message(self.root, f"About {APP_NAME}", (
            f"{APP_NAME}\nVersion {updater.current_version() or APP_VERSION + ' (source)'}\n\n"
            "Turns YouTube links into 320 kbps MP3 files with cover art and tags.\n\n"
            f"yt-dlp {downloader.ytdlp_version()}\n"
            f"FFmpeg: {ffmpeg}\n"
            f"Deno: {deno}"))

    def quit(self):
        if self.manager.busy and not win98.ask_yes_no(
                self.root, APP_NAME, "A download is still running.\n\nDo you want to quit anyway?", "warning"):
            return
        self.manager.cancel()
        self._save_settings()
        self.closed = True
        self.animation.stop()
        self.root.destroy()

    def _warn_no_ffmpeg(self):
        win98.show_message(self.root, APP_NAME, (
            "FFmpeg was not found, so videos can't be turned into MP3 files.\n\n"
            "Install the requirements again (pip install -r requirements.txt), "
            "or put ffmpeg.exe in the same folder as this program."), "error")

    def _save_settings(self):
        self.settings.update(folder=self.folder_var.get().strip() or _default_folder(),
                             playlist=self.playlist_var.get(), square_cover=self.square_var.get())
        save_settings(self.settings)

    # -- list interaction ---------------------------------------------------------------

    def _on_row_double_click(self, event):
        item = self.tree.focus()
        if not item:
            return
        row = self.rows[int(item)]
        if row.state == "done":
            reveal(row.files[-1] if row.files else row.options.folder)
        elif row.state == "error":
            win98.show_message(self.root, APP_NAME, f"{row.title or row.url}\n\n{row.message}", "error")

    def _on_row_menu(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        self.tree.selection_set(item)
        self.tree.focus(item)
        job_id = int(item)
        row = self.rows[job_id]
        menu = win98.make_menu(self.root)
        if row.state == "done":
            menu.add_command(label="Show in Folder", underline=0,
                             command=lambda: reveal(row.files[-1] if row.files else row.options.folder))
        if row.state in ("error", "cancelled"):
            menu.add_command(label="Retry", underline=0, command=lambda: self.retry(job_id))
        if row.state == "error":
            menu.add_command(label="Error Details...", underline=0,
                             command=lambda: self._on_row_double_click(None))
        menu.add_command(label="Copy Link", underline=0, command=lambda: self.copy_link(job_id))
        menu.add_separator()
        menu.add_command(label="Remove from List", underline=0, command=self.remove_selected,
                         state="disabled" if row.state == "running" else "normal")
        menu.tk_popup(event.x_root, event.y_root)

    # -- events from the download thread ------------------------------------------------

    def _poll(self):
        try:
            while not self.closed:
                self._handle(self.events.get_nowait())
        except queue.Empty:
            pass
        if not self.closed:
            self.root.after(60, self._poll)

    def _set_row(self, job_id, state=None, status=None, title=None):
        row = self.rows.get(job_id)
        if row is None:  # removed from the list meanwhile
            return
        item = str(job_id)
        if state:
            row.state = state
            self.tree.item(item, image=self.icons[state])
        if title:
            row.title = title
            self.tree.item(item, text=title)
        if status:
            self.tree.set(item, "status", status)

    def _handle(self, event):
        kind, job_id = event["kind"], event.get("job")
        if kind.startswith("update"):
            self._handle_update(event)
            return
        row = self.rows.get(job_id)

        if kind == "started":
            self.current = job_id
            self.last_error = None
            self._set_row(job_id, "running", "Connecting...")
            self.caption.set("Getting file information...")
            self.bar.set(0)
            self.time_left.set("")
            self.rate.set("")
            self.animation.start()
            self.cancel_button.set_enabled(True)
            self.status.set(f"Opening {row.url if row else ''}")

        elif kind == "progress":
            name = event["title"]
            position = f" ({event['index']} of {event['count']})" if event["index"] and event["count"] else ""
            self._set_row(job_id, title=event["playlist"] or name)
            fraction = event["downloaded"] / event["total"] if event["total"] else 0
            self.bar.set(fraction)
            self.caption.set(f"Saving{position}:  {name}.mp3")
            status = f"{fraction:.0%}" if event["total"] else format_size(event["downloaded"])
            self._set_row(job_id, status=f"{event['index']}/{event['count']} · {status}" if position else status)
            copied = f"({format_size(event['downloaded'])} of {format_size(event['total'])} copied)"
            eta = event["eta"]
            self.time_left.set(f"{format_time(eta)} {copied}" if eta is not None else copied)
            self.rate.set(f"{format_size(event['speed'])}/Sec" if event["speed"] else "")
            self.status.set(f"Downloading {name}")

        elif kind == "converting":
            self.bar.set(1)
            self.caption.set(f"Converting to MP3 (320 kbps):  {event['title']}")
            self.time_left.set("Almost done...")
            self.rate.set("")
            self._set_row(job_id, status="Converting...")

        elif kind == "saved":
            if row:
                row.files.append(event["path"])
            self.saved_count += 1
            self.status.set(f"Saved {os.path.basename(event['path'])}")

        elif kind == "finished":
            files, failed = event["files"], event["failed"]
            status = "Done" if len(files) == 1 else f"Done ({len(files)} files)"
            if failed:
                status += f", {failed} failed"
            if not (row and row.title):
                self._set_row(job_id, title=os.path.splitext(os.path.basename(files[0]))[0])
            self._set_row(job_id, "done", status)
            self.current = None

        elif kind == "failed":
            if row:
                row.message = event["message"]
            self._set_row(job_id, "error", "Error")
            self.status.set(event["message"])
            self.last_error = (row.title or row.url, event["message"]) if row else None
            self.current = None

        elif kind == "cancelled":
            self._set_row(job_id, "cancelled", "Cancelled")
            self.status.set("Download cancelled.")
            self.current = None

        elif kind == "idle":
            saved = self.saved_count
            self._set_idle()
            if self.last_error:
                name, message = self.last_error
                self.last_error = None
                self.status.set(message)
                self.root.after_idle(lambda: win98.show_message(
                    self.root, APP_NAME, f"Could not download:\n{name}\n\n{message}", "error"))
            else:
                if saved:
                    self.root.bell()
                if self.pending_update:  # one dialog at a time: not after an error message
                    self.root.after_idle(self._offer_update, self.pending_update)
                    self.pending_update = None

        self._update_queue_pane()

    # -- updates --------------------------------------------------------------------------

    def check_for_updates(self, asked=True):
        """Look for a newer exe on GitHub in the background. `asked`: from the Help menu."""
        if not updater.current_version():
            if asked:
                win98.show_message(self.root, "Check for Updates", (
                    "You are running the program from source, so it can't update itself.\n\n"
                    "To update, run:\n    git pull\n    pip install -U -r requirements.txt"))
            return

        def work():
            try:
                event = {"kind": "update_check", "update": updater.check(), "asked": asked}
            except Exception as e:
                event = {"kind": "update_check", "error": str(e), "asked": asked}
            self.events.put(event)

        threading.Thread(target=work, name="update-check", daemon=True).start()

    def _handle_update(self, event):
        kind = event["kind"]
        if kind == "update_check":
            update, asked = event.get("update"), event["asked"]
            if event.get("error"):
                if asked:
                    self.root.after_idle(lambda: win98.show_message(
                        self.root, "Check for Updates", f"Couldn't check for updates.\n\n{event['error']}", "warning"))
            elif not update:
                if asked:
                    self.root.after_idle(lambda: win98.show_message(
                        self.root, "Check for Updates", f"You have the newest version ({updater.current_version()})."))
            elif asked or update.version != self.settings["skipped_version"]:
                if self.manager.busy:
                    self.pending_update = update
                else:
                    self.root.after_idle(self._offer_update, update)

        elif kind == "update_progress":
            done, total = event["done"], event["total"]
            self.bar.set(done / total if total else 0)
            self.time_left.set(f"({format_size(done)} of {format_size(total)} copied)")

        elif kind == "update_ready":
            try:
                updater.install_and_restart(event["path"])
            except OSError as e:
                self._update_failed(f"Couldn't replace the program file.\n{e}")
                return
            self._save_settings()
            self.closed = True
            self.animation.stop()
            self.root.destroy()

        elif kind == "update_failed":
            self._update_failed(event["message"])

    def _offer_update(self, update):
        if self.updating or self.manager.busy:
            return
        if not win98.ask_yes_no(self.root, "Update Available", (
                f"A new version of {APP_NAME} is available.\n\n"
                f"Your version:   {updater.current_version()}\n"
                f"New version:    {update.version}\n\n"
                "New versions come with the newest yt-dlp, which keeps YouTube downloads working.\n\n"
                "Update now? The program will restart by itself."), "info"):
            self.settings["skipped_version"] = update.version  # don't ask again for this one
            self._save_settings()
            return

        self.updating = True
        self.animation.start()
        self.bar.set(0)
        self.caption.set(f"Downloading version {update.version}...")
        self.rate.set("")
        self.status.set("Downloading update...")

        def progress(done, total):
            self.events.put({"kind": "update_progress", "done": done, "total": total})

        def work():
            try:
                self.events.put({"kind": "update_ready", "path": updater.download(update, progress)})
            except Exception as e:
                self.events.put({"kind": "update_failed", "message": str(e)})

        threading.Thread(target=work, name="update-download", daemon=True).start()

    def _update_failed(self, message):
        self.updating = False
        self._set_idle()
        self.root.after_idle(lambda: win98.ask_yes_no(
            self.root, "Update Failed",
            f"The update didn't work:\n{message}\n\nOpen the download page to get the new version yourself?",
            "error") and webbrowser.open(updater.RELEASES_PAGE))

    def _set_idle(self):
        self.current = None
        self.animation.stop()
        self.cancel_button.set_enabled(False)
        self.time_left.set("")
        self.rate.set("")
        if self.saved_count:
            self.bar.set(1)
            plural = "s" if self.saved_count != 1 else ""
            self.caption.set(f"Finished. {self.saved_count} MP3{plural} saved to {self.folder_var.get()}")
            self.status.set("Done.")
        else:
            self.bar.set(0)
            self.caption.set("Waiting for a link.")
            self.status.set("Ready.")
        self.saved_count = 0

    def _update_queue_pane(self):
        waiting = sum(1 for row in self.rows.values() if row.state == "waiting")
        self.queue_pane.set(f"{waiting} waiting" if waiting else "Queue empty")
