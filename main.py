"""MP3 320kbps Downloader: YouTube links to 320 kbps MP3 files, Windows 98 style."""

import tkinter as tk

import win98
from app import App


def main():
    win98.enable_dpi_awareness()
    win98.set_app_id("wxxmin.mp3_320kbps_downloader")
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
