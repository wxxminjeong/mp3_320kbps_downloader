"""Download engine: YouTube link -> 320 kbps MP3 with tags and cover art.

yt-dlp runs on one background thread and everything it does is reported as
plain dict events (see DownloadManager), so this module knows nothing about
the user interface.
"""

import collections
import itertools
import os
import re
import shutil
import sys
import threading
from dataclasses import dataclass

import yt_dlp
from yt_dlp.postprocessor import FFmpegThumbnailsConvertorPP
from yt_dlp.utils import DownloadCancelled, replace_extension


@dataclass(frozen=True)
class Options:
    folder: str
    playlist: bool = False
    square_cover: bool = True


@dataclass
class Job:
    id: int
    url: str
    options: Options


class SquareCoverPP(FFmpegThumbnailsConvertorPP):
    """Centre-crops the downloaded thumbnail to a square JPEG, like real album art.

    yt-dlp's own converter skips thumbnails that are already JPEG, so the crop
    is done here for every one of them.
    """

    CROP = "crop='min(iw,ih)':'min(iw,ih)'"

    def run(self, info):
        files_to_delete = []
        for idx, thumbnail in enumerate(info.get("thumbnails") or []):
            if not thumbnail.get("filepath"):
                continue
            self.fixup_webp(info, idx)  # YouTube sometimes sends WebP named .jpg
            source = thumbnail["filepath"]
            target = replace_extension(source, "cover.jpg")
            self.real_run_ffmpeg(
                [(source, ["-f", "image2", "-pattern_type", "none"])],
                [(target, ["-vf", self.CROP, "-q:v", "2", "-update", "1"])])
            thumbnail["filepath"] = target
            files_to_delete.append(source)
            moves = info.get("__files_to_move") or {}
            if source in moves:
                moves[target] = replace_extension(moves[source], "cover.jpg")
        return files_to_delete, info


# -- external tools --------------------------------------------------------------

def _program_folders():
    """Folders that may hold tools shipped together with the program."""
    folders = []
    if hasattr(sys, "_MEIPASS"):  # inside a PyInstaller bundle
        folders.append(sys._MEIPASS)
    if getattr(sys, "frozen", False):
        folders.append(os.path.dirname(sys.executable))
    folders.append(os.path.dirname(os.path.abspath(__file__)))
    return folders


def _find_tool(name):
    exe = name + ".exe" if os.name == "nt" else name
    for folder in _program_folders():
        path = os.path.join(folder, exe)
        if os.path.isfile(path):
            return path
    return shutil.which(name)


def find_ffmpeg():
    """Path of the ffmpeg binary, or None if there is none.

    Checks next to the program, then PATH, then the copy that comes with the
    imageio-ffmpeg package (installed through requirements.txt).
    """
    path = _find_tool("ffmpeg")
    if path:
        return path
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # package missing or no binary for this platform
        return None


def find_deno():
    """Path of the Deno JavaScript runtime, or None if there is none.

    Recent YouTube pages can only be read properly with a JS runtime; the
    `deno` package from requirements.txt ships one.
    """
    path = _find_tool("deno")
    if path:
        return path
    try:
        import deno
        path = deno.find_deno_bin()
        return path if os.path.isfile(path) else None
    except Exception:
        return None


def ytdlp_version():
    return yt_dlp.version.__version__


# -- error messages ----------------------------------------------------------------

_ANSI = re.compile(r"\x1b\[[0-9;]*m")

# (pattern found in yt-dlp's message, what we tell the user)
_FRIENDLY_ERRORS = [
    ("is not a valid url", "That doesn't look like a valid link."),
    ("unsupported url", "This link is not supported."),
    ("private video", "This video is private."),
    ("video unavailable", "This video is unavailable."),
    ("sign in to confirm your age", "This video is age-restricted and can't be downloaded without signing in."),
    ("confirm you're not a bot", "YouTube blocked the request (bot check). Try again later."),
    ("http error 403", "YouTube refused the download (HTTP 403). Try again, or update yt-dlp."),
    ("http error 404", "Nothing was found at that link (HTTP 404)."),
    ("ffprobe and ffmpeg not found", "FFmpeg was not found, so the MP3 could not be made."),
    ("unable to download webpage", "Network error. Check your internet connection."),
    ("getaddrinfo failed", "Network error. Check your internet connection."),
    ("name or service not known", "Network error. Check your internet connection."),
    ("timed out", "The connection timed out. Check your internet connection."),
    ("no space left", "The disk is full."),
    ("permission denied", "Windows denied access to the download folder."),
]


def friendly_error(message):
    """Turn a raw yt-dlp error into one short sentence for the user."""
    text = _ANSI.sub("", str(message)).strip()
    text = re.sub(r"^ERROR:\s*", "", text)
    text = re.sub(r"^\[[^\]]+\]\s*(?:[\w-]+:\s*)?", "", text)  # "[youtube] abc123: ..."
    text = text.splitlines()[0].strip() if text else ""
    lowered = text.lower()
    for needle, friendly in _FRIENDLY_ERRORS:
        if needle in lowered:
            return friendly
    return text or "Unknown error."


class _Logger:
    """Collects yt-dlp's error messages instead of printing them."""

    def __init__(self):
        self.errors = []

    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        self.errors.append(msg)


# -- the queue -----------------------------------------------------------------------

class DownloadManager:
    """Downloads queued links one after another on a background thread.

    `emit` is called from that thread with dicts that all carry "kind" and
    (except "idle") "job":

        started     the job left the queue
        progress    title, playlist, index, count, downloaded, total, speed, eta
        converting  title (download done, ffmpeg is making the MP3)
        saved       path of a finished MP3
        finished    files (list of paths), failed (playlist entries that failed)
        failed      message
        cancelled
        idle        the queue is empty again
    """

    def __init__(self, emit, ffmpeg=None, deno=None):
        self._emit = emit
        self.ffmpeg = ffmpeg
        self.deno = deno
        self._pending = collections.deque()
        self._lock = threading.Condition()
        self._cancel = threading.Event()
        self._ids = itertools.count(1)
        self._current = None
        threading.Thread(target=self._worker, name="downloader", daemon=True).start()

    def add(self, url, options):
        with self._lock:
            job = Job(next(self._ids), url, options)
            self._pending.append(job)
            self._lock.notify()
        return job

    def remove(self, job_id):
        """Drop a job that has not started yet. Returns False if it had."""
        with self._lock:
            for job in self._pending:
                if job.id == job_id:
                    self._pending.remove(job)
                    return True
        return False

    def cancel(self):
        """Stop the job that is running right now."""
        with self._lock:
            if self._current is not None:
                self._cancel.set()

    @property
    def busy(self):
        with self._lock:
            return self._current is not None or bool(self._pending)

    @property
    def pending(self):
        with self._lock:
            return len(self._pending)

    def _worker(self):
        while True:
            with self._lock:
                while not self._pending:
                    self._lock.wait()
                job = self._current = self._pending.popleft()
                self._cancel.clear()
            try:
                self._run(job)
            except Exception as e:  # never let one bad job kill the worker
                self._emit({"kind": "failed", "job": job.id, "message": friendly_error(e)})
            with self._lock:
                self._current = None
                idle = not self._pending
            if idle:
                self._emit({"kind": "idle"})

    def ydl_options(self, options, progress_hook=None, postprocessor_hook=None, logger=None):
        postprocessors = [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"},
            {"key": "FFmpegMetadata", "add_metadata": True},  # title / artist / date tags
            {"key": "EmbedThumbnail"},
        ]
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(options.folder, "%(title)s.%(ext)s"),
            "noplaylist": not options.playlist,
            # In a playlist, skip broken entries instead of stopping at the first one.
            "ignoreerrors": "only_download" if options.playlist else False,
            "writethumbnail": True,
            "postprocessors": postprocessors,
            "progress_hooks": [progress_hook] if progress_hook else [],
            "postprocessor_hooks": [postprocessor_hook] if postprocessor_hook else [],
            "logger": logger,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            # yt-dlp uses the first runtime it finds; Node.js and Bun work too if installed.
            "js_runtimes": {"deno": {"path": self.deno} if self.deno else {}, "node": {}, "bun": {}},
        }
        if self.ffmpeg:
            ydl_opts["ffmpeg_location"] = self.ffmpeg
        return ydl_opts

    def _run(self, job):
        def emit(kind, **data):
            self._emit({"kind": kind, "job": job.id, **data})

        logger = _Logger()
        files = []
        leftovers = set()  # partial downloads and thumbnails to delete on cancel

        def check_cancel():
            if self._cancel.is_set():
                raise DownloadCancelled("Cancelled by user")

        def on_progress(d):
            check_cancel()
            info = d.get("info_dict") or {}
            leftovers.update(p for p in (d.get("tmpfilename"), d.get("filename")) if p)
            leftovers.update(t["filepath"] for t in info.get("thumbnails") or () if t.get("filepath"))
            if d["status"] == "downloading":
                emit(
                    "progress",
                    title=info.get("title") or "",
                    playlist=info.get("playlist_title") or info.get("playlist") or "",
                    index=info.get("playlist_index"),
                    count=info.get("n_entries") or info.get("playlist_count"),
                    downloaded=d.get("downloaded_bytes") or 0,
                    total=d.get("total_bytes") or d.get("total_bytes_estimate"),
                    speed=d.get("speed"),
                    eta=d.get("eta"),
                )

        def on_postprocess(d):
            check_cancel()
            info = d.get("info_dict") or {}
            if d["postprocessor"] == "ExtractAudio" and d["status"] == "started":
                emit("converting", title=info.get("title") or "")
            elif d["postprocessor"] == "MoveFiles" and d["status"] == "finished":
                path = info.get("filepath")
                if path:
                    files.append(path)
                    emit("saved", path=path)

        emit("started")
        try:
            with yt_dlp.YoutubeDL(self.ydl_options(job.options, on_progress, on_postprocess, logger)) as ydl:
                if job.options.square_cover:
                    ydl.add_post_processor(SquareCoverPP(ydl), when="before_dl")
                ydl.download([job.url])
        except DownloadCancelled:
            for path in leftovers | {p + ".ytdl" for p in leftovers}:
                if not path.endswith(".mp3"):  # keep MP3s that were already finished
                    try:
                        os.remove(path)
                    except OSError:
                        pass
            emit("cancelled")
            return
        except Exception as e:
            emit("failed", message=friendly_error(logger.errors[-1] if logger.errors else e))
            return

        if files:
            emit("finished", files=files, failed=len(logger.errors))
        else:
            emit("failed", message=friendly_error(logger.errors[-1]) if logger.errors else "Nothing was downloaded.")
