# main.py
import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from setup_helper import full_setup
# import cc_download.main as cc

full_setup()  # Ensure environment is ready

from yt_dlp import YoutubeDL
from datetime import datetime
import logging


DEFAULT_DOWNLOAD_DIR = "YouTube_Downloads"
AUDIO_COPY_DIR = os.path.join(DEFAULT_DOWNLOAD_DIR, "audio_only")
LOG_FILE = "youtube_downloader.log"
ARCHIVE_FILE = os.path.join(DEFAULT_DOWNLOAD_DIR, 'downloaded_videos.txt')

os.makedirs(DEFAULT_DOWNLOAD_DIR, exist_ok=True)
os.makedirs(AUDIO_COPY_DIR, exist_ok=True)

# --- Logging Setup ---
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- UI Setup ---
root = tk.Tk()
root.title("YouTube Playlist Downloader")
root.geometry("650x500")
root.resizable(False, False)

playlist_entries = []

# --- Functions ---
def fetch_videos():
    global playlist_entries
    playlist_entries = []
    video_listbox.delete(0, tk.END)
    url = url_entry.get().strip()

    if not url:
        print(url)
        messagebox.showwarning("Input Error", "Please enter a playlist URL.")
        return

    ydl_opts = {
        'extract_flat': True,
        'force_generic_extractor': True,
        'quiet': True,
        'skip_download': True,
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            # Detect if it's a playlist
            if 'entries' in info:
                entries = info['entries']
                for i, entry in enumerate(entries):
                    title = entry.get('title', 'Unknown Title')
                    playlist_entries.append(entry)
                    video_listbox.insert(tk.END, f"{i+1:03d}. {title}")
                if not entries:
                    messagebox.showerror("Playlist Error", "No videos found in playlist.")
            else:
                # Single video
                title = info.get('title', 'Unknown Title')
                playlist_entries.append(info)
                video_listbox.insert(tk.END, f"001. {title}")
    except Exception as e:
        messagebox.showerror("Error", f"Could not fetch playlist info:\n{e}")


def update_quality_options(*args):
    q_combo['values'] = video_qualities if type_var.get() == 'Video' else audio_qualities
    q_combo.current(0)


def download_selected():
    selected = video_listbox.curselection()
    if not selected:
        messagebox.showwarning("Selection Error", "Please select at least one video.")
        return

    url = url_entry.get().strip()
    video_type = type_var.get()
    quality = q_combo.get()
    selected_items = ','.join(str(i + 1) for i in selected)

    progress_label.config(text="Starting download...")

    def progress_hook(d):
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '').strip()
            progress_label.config(text=f"Downloading: {percent}")
            progress_bar.step(1)
        elif d['status'] == 'finished':
            progress_label.config(text=f"Finished: {d.get('filename')}")
            progress_bar['value'] = 100

    ydl_opts = {
        'format': quality,
        'outtmpl': os.path.join(DEFAULT_DOWNLOAD_DIR, '%(playlist)s/%(playlist_index)s - %(title)s.%(ext)s'),
        'ignoreerrors': True,
        'download_archive': ARCHIVE_FILE,
        'progress_hooks': [progress_hook],
        'playlist_items': selected_items,
    }

    if video_type == 'Audio':
        ydl_opts['extractaudio'] = True
        ydl_opts['postprocessors'] = [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }
        ]
    else:
        ydl_opts['postprocessors'] = [
            {
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mkv'
            }
        ]
        # ydl_opts['format'] = 'bestvideo+bestaudio/best'

    def run_download():
        try:
            with YoutubeDL(ydl_opts) as ydl:
                result = ydl.download([url])
            messagebox.showinfo("Success", "Download completed!")
        except Exception as e:
            logging.error(f"Download failed: {e}")
            messagebox.showerror("Error", f"Download failed:\n{e}")

    threading.Thread(target=run_download, daemon=True).start()

# --- GUI Layout ---
tk.Label(root, text="YouTube Playlist URL:").pack(pady=(10, 0))
url_entry = tk.Entry(root, width=80)
url_entry.pack()

fetch_btn = tk.Button(root, text="Fetch Playlist", command=fetch_videos)
fetch_btn.pack(pady=(5, 10))

frame = tk.Frame(root)
frame.pack()
type_var = tk.StringVar(value="Video")
tk.Label(frame, text="Download Type:").grid(row=0, column=0)
tk.Radiobutton(frame, text="Video", variable=type_var, value="Video", command=update_quality_options).grid(row=0, column=1)
tk.Radiobutton(frame, text="Audio", variable=type_var, value="Audio", command=update_quality_options).grid(row=0, column=2)
# new added for captions
# tk.Radiobutton(frame, text="Transcript", variable=type_var,value="Captions[CC]").grid(row=0, column=3)

video_qualities = ['best', 'bestvideo[height<=1080]+bestaudio', 'bestvideo[height<=720]+bestaudio', 'worst']
audio_qualities = ['bestaudio', 'bestaudio[ext=mp3]', 'bestaudio/best']

q_combo = ttk.Combobox(root, values=video_qualities, state="readonly", width=60)
q_combo.current(0)
q_combo.pack(pady=(5, 10))

video_listbox = tk.Listbox(root, selectmode=tk.MULTIPLE, width=80, height=10)
video_listbox.pack()

scrollbar = tk.Scrollbar(root, orient="vertical", command=video_listbox.yview)
video_listbox.config(yscrollcommand=scrollbar.set)
scrollbar.place(x=605, y=220, height=165)

progress_label = tk.Label(root, text="")
progress_label.pack(pady=(5, 0))

progress_bar = ttk.Progressbar(root, length=400, mode='determinate')
progress_bar.pack(pady=(2, 10))

start_btn = tk.Button(root, text="Start Download", command=download_selected, bg="green", fg="white")
start_btn.pack(pady=(5, 10))

root.mainloop()