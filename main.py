"""MP3 320kbps Downloader: YouTube links to 320 kbps MP3 files, Windows 98 style."""

import os
import subprocess
import sys
import tempfile
import time
import tkinter as tk
import traceback

import win98
from app import App


def self_test(report_path):
    """Check that a packed exe works: `--self-test report.txt`. Used by the release workflow."""
    lines, ok = [], True
    try:
        import downloader
        import updater
        lines.append(f"version: {updater.current_version()}")
        lines.append(f"yt-dlp: {downloader.ytdlp_version()}")
        ffmpeg, deno = downloader.find_ffmpeg(), downloader.find_deno()
        quiet = {"capture_output": True, "text": True, "stdin": subprocess.DEVNULL, "timeout": 120}
        lines.append(f"ffmpeg: {ffmpeg}: {subprocess.run([ffmpeg, '-version'], **quiet).stdout.splitlines()[0]}")
        lines.append(f"deno: {deno}: {subprocess.run([deno, '--version'], **quiet).stdout.splitlines()[0]}")

        mp3 = os.path.join(tempfile.mkdtemp(), "tone.mp3")
        subprocess.run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "sine=duration=1", "-b:a", "320k", mp3],
                       check=True, **quiet)
        lines.append(f"mp3 encode: {os.path.getsize(mp3)} bytes")
        try:  # informational only: a GitHub hiccup shouldn't fail the build
            lines.append(f"update check: {updater.check()}")
        except Exception as e:
            lines.append(f"update check: failed ({e})")

        root = tk.Tk()
        App(root)
        for _ in range(10):  # let the startup callbacks run
            root.update()
            time.sleep(0.05)
        root.destroy()
        lines.append("window: ok")
    except Exception:
        ok = False
        lines.append(traceback.format_exc())
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines + ["PASS" if ok else "FAIL"]) + "\n")
    return 0 if ok else 1


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        sys.exit(self_test(sys.argv[2]))
    win98.enable_dpi_awareness()
    win98.set_app_id("wxxmin.mp3_320kbps_downloader")
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
