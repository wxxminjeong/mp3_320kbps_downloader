import os
import threading
import customtkinter as ctk
from tkinter import filedialog
import yt_dlp

# --- Theme & Color Settings ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
ACCENT_COLOR = "#1DB954"
HOVER_COLOR = "#1AA34A"

app = ctk.CTk()
app.title("MP3_320kbps Downloader")
app.geometry("450x330")
app.resizable(False, False)

# Default download path (OS Downloads folder)
default_path = os.path.expanduser('~/Downloads')
save_dir = ctk.StringVar(value=default_path)

def select_folder():
    folder = filedialog.askdirectory(initialdir=save_dir.get(), title="Select Download Folder")
    if folder:
        save_dir.set(folder)

def progress_hook(d):
    """ Update status text (Thread-safe UI update via lambda) """
    if d['status'] == 'downloading':
        app.after(0, lambda: status_label.configure(text="Downloading...", text_color="#FFCC00"))
    elif d['status'] == 'finished':
        app.after(0, lambda: status_label.configure(text="Converting & Adding Cover...", text_color="#00FFCC"))

def download_mp3():
    url = url_entry.get().strip()
    if not url:
        status_label.configure(text="Please enter a valid YouTube URL!", text_color="#FF3333")
        return

    status_label.configure(text="Starting...", text_color="#FFCC00")
    download_btn.configure(state="disabled")

    ydl_opts = {
        'format': 'bestaudio/best',
        'writethumbnail': True, # Download YouTube thumbnail
        'postprocessors': [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            },
            {
                'key': 'EmbedThumbnail', # Embed thumbnail into MP3 metadata
            }
        ],
        'outtmpl': os.path.join(save_dir.get(), '%(title)s.%(ext)s'),
        'progress_hooks': [progress_hook],
        'quiet': True
    }

    def run_download():
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            app.after(0, lambda: status_label.configure(text="Complete!", text_color=ACCENT_COLOR))
            app.after(0, lambda: url_entry.delete(0, 'end'))
        except Exception as e:
            app.after(0, lambda: status_label.configure(text="Error! Check URL or Network.", text_color="#FF3333"))
            print(e) # Print error to terminal for debugging
        finally:
            app.after(0, lambda: download_btn.configure(state="normal"))

    threading.Thread(target=run_download, daemon=True).start()

# --- UI Layout ---

title_label = ctk.CTkLabel(app, text="MP3_320kbps Downloader", font=ctk.CTkFont(size=24, weight="bold"))
title_label.pack(pady=(25, 20))

url_frame = ctk.CTkFrame(app, fg_color="transparent")
url_frame.pack(fill="x", padx=35, pady=(0, 15))
url_entry = ctk.CTkEntry(url_frame, placeholder_text="Paste YouTube URL here...", height=40)
url_entry.pack(fill="x")

folder_frame = ctk.CTkFrame(app, fg_color="transparent")
folder_frame.pack(fill="x", padx=35, pady=(0, 15))

folder_entry = ctk.CTkEntry(folder_frame, textvariable=save_dir, state="readonly", height=35)
folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

folder_btn = ctk.CTkButton(folder_frame, text="Browse", width=70, height=35, 
                           command=select_folder, fg_color="#4A4A4A", hover_color="#333333")
folder_btn.pack(side="right")

status_label = ctk.CTkLabel(app, text="Ready", font=ctk.CTkFont(size=14, weight="bold"))
status_label.pack(pady=(10, 15))

download_btn = ctk.CTkButton(app, text="DOWNLOAD 320KBPS MP3", height=50, 
                             font=ctk.CTkFont(size=15, weight="bold"), 
                             command=download_mp3, fg_color=ACCENT_COLOR, hover_color=HOVER_COLOR)
download_btn.pack(fill="x", padx=35)

app.mainloop()