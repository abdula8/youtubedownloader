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
import re
import requests
# import re


from pathlib import Path
file_path = Path(__file__).resolve()
directory = os.path.dirname(file_path)

def check_os(name):
    import sys
    if sys.platform == "linux":
        # print("This is a Linux system.")
        return f"{directory}/{name}"
    elif sys.platform == "win32":
        # print("This is a Windows system.")
        return f"{directory}\\{name}"
    else:
        print(f"This is an unsupported operating system: {sys.platform}")

DEFAULT_DOWNLOAD_DIR = check_os("YouTube_Downloads")
# Mutable download directory (can be changed via UI)
DOWNLOAD_DIR = DEFAULT_DOWNLOAD_DIR
AUDIO_COPY_DIR = os.path.join(DOWNLOAD_DIR, "audio_only")
LOG_FILE = check_os("youtube_downloader.log")
ARCHIVE_FILE = os.path.join(DOWNLOAD_DIR, 'downloaded_videos.txt')

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
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
root.resizable(True, True)

playlist_entries = []
current_formats = []  # populated by Load Formats per selected item
cookies_path = None   # optional cookies file for sites like Facebook

def resolve_final_url(input_url: str) -> str:
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
        }
        resp = requests.get(input_url, headers=headers, allow_redirects=True, timeout=15)
        if resp.url:
            return resp.url
        return input_url
    except Exception:
        return input_url
success_count = 0
failure_count = 0

# --- Functions ---
def fetch_videos():
    global playlist_entries
    playlist_entries = []
    video_listbox.delete(0, tk.END)
    url = url_entry.get().strip()
    # Resolve share/redirected URLs (e.g., Facebook share links)
    url = resolve_final_url(url)

    if not url:
        print(url)
        messagebox.showwarning("Input Error", "Please enter a playlist URL.")
        return

    ydl_opts = {
        'extract_flat': True,
        'quiet': True,
        'skip_download': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
            'Referer': url,
        },
    }
    if cookies_path:
        ydl_opts['cookiefile'] = cookies_path
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            # Handle playlists and generic post pages with multiple entries
            if isinstance(info, dict) and 'entries' in info and info['entries'] is not None:
                entries = info['entries']
                for i, entry in enumerate(entries):
                    if not isinstance(entry, dict):
                        continue
                    title = entry.get('title') or entry.get('id', 'Unknown')
                    playlist_entries.append(entry)
                    video_listbox.insert(tk.END, f"{i+1:03d}. {title}")
                if not entries:
                    messagebox.showerror("No Media", "No videos found at the provided URL.")
            elif isinstance(info, dict):
                # Single media item
                title = info.get('title') or info.get('id', 'Unknown')
                playlist_entries.append(info)
                video_listbox.insert(tk.END, f"001. {title}")
            else:
                messagebox.showerror("No Media", "No downloadable media found at the provided URL.")
    except Exception as e:
        messagebox.showerror("Error", f"Could not fetch info from URL. If this is Facebook, try loading cookies.txt and retry.\n\n{e}")


def update_quality_options(*args):
    q_combo['values'] = video_qualities if type_var.get() == 'Video' else audio_qualities
    q_combo.current(0)


def load_formats_for_selection():
    selected = video_listbox.curselection()
    if not selected:
        messagebox.showwarning("Selection Error", "Please select a video to load formats.")
        return
    # Use the first selected index to discover formats
    idx = selected[0]
    url = url_entry.get().strip()
    url = resolve_final_url(url)
    if not url:
        messagebox.showwarning("Input Error", "Please enter a URL first.")
        return

    progress_label.config(text="Loading formats...")
    def _load():
        global current_formats
        try:
            base_opts = {
                'quiet': True,
                'playlist_items': str(idx + 1),
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
                    'Referer': url,
                }
            }
            if cookies_path:
                base_opts['cookiefile'] = cookies_path
            with YoutubeDL(base_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            logging.error(f"Format load failed: {e}")
            messagebox.showerror("Error", f"Failed to load formats:\n{e}")
            return

        # info may be playlist entry or a single video dict
        # Ensure we have a dict with 'formats'
        if isinstance(info, dict) and 'formats' in info:
            formats = info['formats']
        elif isinstance(info, list) and info:
            candidate = info[0]
            formats = candidate.get('formats', [])
        else:
            formats = []

        # Build human-friendly choices, focusing on video heights
        heights = []
        for f in formats:
            vcodec = f.get('vcodec')
            height = f.get('height')
            if vcodec and vcodec != 'none' and height:
                heights.append(height)
        heights = sorted(set(h for h in heights if isinstance(h, int)), reverse=True)

        choices = []
        choices.append(('best', 'best (auto)'))
        for h in heights:
            selector = f"bestvideo[height<={h}]+bestaudio/best"
            label = f"<= {h}p (video+bestaudio)"
            choices.append((selector, label))

        # Fallback if no heights found
        if len(choices) == 1:
            choices.extend([
                ('best', 'best'),
                ('worst', 'worst')
            ])

        current_formats = choices
        # Update combobox with human labels but keep mapping
        q_combo['values'] = [label for _, label in choices]
        q_combo.current(0)
        progress_label.config(text="Formats loaded.")

    threading.Thread(target=_load, daemon=True).start()


def download_selected():
    selected = video_listbox.curselection()
    if not selected:
        messagebox.showwarning("Selection Error", "Please select at least one video.")
        return

    url = url_entry.get().strip()
    video_type = type_var.get()
    # Resolve selected quality: if user used Load Formats, map label->selector
    selected_label = q_combo.get()
    quality = None
    for selector, label in current_formats:
        if label == selected_label:
            quality = selector
            break
    if not quality:
        quality = selected_label
    selected_indices = [i for i in selected]

    progress_label.config(text="Starting download...")

    def progress_hook(d):
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '').strip()
            progress_label.config(text=f"Downloading: {percent}")
            progress_bar.step(1)
        elif d['status'] == 'finished':
            progress_label.config(text=f"Finished: {d.get('filename')}")
            progress_bar['value'] = 100

    def is_in_archive(video_id: str) -> bool:
        try:
            if not os.path.exists(ARCHIVE_FILE):
                return False
            with open(ARCHIVE_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                return video_id in content
        except Exception:
            return False
        # ydl_opts['format'] = 'bestvideo+bestaudio/best'

    def run_download():
        global success_count, failure_count, DOWNLOAD_DIR, AUDIO_COPY_DIR, ARCHIVE_FILE
        success_count = 0
        failure_count = 0
        total_items = len(selected_indices)
        counts_label.config(text=f"Downloaded: {success_count}/{total_items} | Errors: {failure_count}")

        for offset, idx in enumerate(selected_indices, start=1):
            try:
                entry = playlist_entries[idx]
            except Exception:
                failure_count += 1
                counts_label.config(text=f"Downloaded: {success_count}/{total_items} | Errors: {failure_count}")
                continue

            title = entry.get('title', 'Unknown Title')
            video_id = entry.get('id') or ''

            # Duplicate confirmation using archive
            use_archive = True
            if video_id and is_in_archive(video_id):
                resp = messagebox.askyesno("Already downloaded", f"'{title}' seems already downloaded. Download again?")
                if not resp:
                    counts_label.config(text=f"Downloaded: {success_count}/{total_items} | Errors: {failure_count}")
                    continue
                use_archive = False

            # Build per-item options and ensure target subfolder exists (for non-playlist posts too)
            raw_subdir = entry.get('playlist') or 'NA'
            safe_subdir = re.sub(r'[\\/:*?"<>|]+', '_', str(raw_subdir)).strip() or 'NA'
            target_dir = os.path.join(DOWNLOAD_DIR, safe_subdir)
            os.makedirs(target_dir, exist_ok=True)

            ydl_opts_item = {
                'format': quality,
                'outtmpl': '%(playlist_index|NA)s - %(title)s.%(ext)s',
                'paths': {
                    'home': target_dir,
                    'temp': target_dir,
                },
                'ignoreerrors': False,
                'progress_hooks': [progress_hook],
                'playlist_items': str(idx + 1),
                'retries': 10,
                'fragment_retries': 10,
                'concurrent_fragment_downloads': 3,
                'windowsfilenames': True,
                'restrictfilenames': True,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
                    'Referer': url,
                }
            }
            if cookies_path:
                ydl_opts_item['cookiefile'] = cookies_path
            if use_archive:
                ydl_opts_item['download_archive'] = ARCHIVE_FILE

            if video_type == 'Audio':
                ydl_opts_item['extractaudio'] = True
                ydl_opts_item['postprocessors'] = [
                    {
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }
                ]
            else:
                ydl_opts_item['postprocessors'] = [
                    {
                        'key': 'FFmpegVideoRemuxer',
                        'preferedformat': 'mkv'
                    }
                ]

            attempts = 0
            local_max = 5
            while True:
                try:
                    progress_bar['value'] = 0
                    progress_label.config(text=f"Starting: {title} ({offset}/{total_items})")
                    with YoutubeDL(ydl_opts_item) as ydl:
                        ydl.download([url])
                    success_count += 1
                    counts_label.config(text=f"Downloaded: {success_count}/{total_items} | Errors: {failure_count}")
                    break
                except Exception as e:
                    attempts += 1
                    logging.error(f"Download failed for '{title}' attempt {attempts}: {e}")
                    progress_label.config(text=f"Error: {title} (attempt {attempts}/{local_max})")
                    if attempts >= local_max:
                        retry_more = messagebox.askyesno(
                            "Retry more?",
                            f"'{title}' failed {local_max} times. Try {local_max} more attempts?"
                        )
                        if retry_more:
                            attempts = 0
                            continue
                        else:
                            failure_count += 1
                            counts_label.config(text=f"Downloaded: {success_count}/{total_items} | Errors: {failure_count}")
                            break

        if failure_count == 0:
            messagebox.showinfo("Done", f"All {success_count} items downloaded successfully.")
        else:
            messagebox.showwarning("Done with errors", f"Downloaded {success_count} items with {failure_count} error(s). Check logs.")

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

# Button to load formats for arbitrary sites (Instagram, TikTok, Twitter, LinkedIn, etc.)
fmt_btn = tk.Button(root, text="Load Formats", command=load_formats_for_selection)
fmt_btn.pack(pady=(0, 5))

video_listbox = tk.Listbox(root, selectmode=tk.MULTIPLE, width=80, height=10)
video_listbox.pack()

scrollbar = tk.Scrollbar(root, orient="vertical", command=video_listbox.yview)
video_listbox.config(yscrollcommand=scrollbar.set)
scrollbar.place(x=605, y=220, height=165)

progress_label = tk.Label(root, text="")
progress_label.pack(pady=(5, 0))

progress_bar = ttk.Progressbar(root, length=400, mode='determinate')
progress_bar.pack(pady=(2, 10))

# Download directory chooser and counters
def choose_folder():
    global DOWNLOAD_DIR, AUDIO_COPY_DIR, ARCHIVE_FILE
    chosen = filedialog.askdirectory(initialdir=DOWNLOAD_DIR, title="Choose download folder")
    if chosen:
        DOWNLOAD_DIR = chosen
        AUDIO_COPY_DIR = os.path.join(DOWNLOAD_DIR, "audio_only")
        ARCHIVE_FILE = os.path.join(DOWNLOAD_DIR, 'downloaded_videos.txt')
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        os.makedirs(AUDIO_COPY_DIR, exist_ok=True)
        folder_label.config(text=f"Folder: {DOWNLOAD_DIR}")

folder_frame = tk.Frame(root)
folder_frame.pack(pady=(0, 5))
tk.Button(folder_frame, text="Choose Folder", command=choose_folder).grid(row=0, column=0, padx=(0, 10))
folder_label = tk.Label(folder_frame, text=f"Folder: {DOWNLOAD_DIR}")
folder_label.grid(row=0, column=1)

counts_label = tk.Label(root, text="Downloaded: 0/0 | Errors: 0")
counts_label.pack(pady=(0, 5))

start_btn = tk.Button(root, text="Start Download", command=download_selected, bg="green", fg="white")
start_btn.pack(pady=(5, 10))

# Cookies loader to support sites requiring auth/headers (e.g., Facebook)
def load_cookies():
    global cookies_path
    path = filedialog.askopenfilename(title="Select cookies.txt",
                                      filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
    if path:
        cookies_path = path
        messagebox.showinfo("Cookies Loaded", f"Using cookies from:\n{cookies_path}")

cookies_btn = tk.Button(root, text="Load Cookies.txt (optional)", command=load_cookies)
cookies_btn.pack(pady=(0, 5))

root.mainloop()