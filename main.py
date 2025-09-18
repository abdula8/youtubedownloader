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
import subprocess
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
root.geometry("750x600")
root.resizable(True, True)

# Make the UI scrollable
container = tk.Frame(root)
container.pack(fill='both', expand=True)

canvas = tk.Canvas(container)
scrollbar = tk.Scrollbar(container, orient='vertical', command=canvas.yview)
scrollbar.pack(side='right', fill='y')
canvas.pack(side='left', fill='both', expand=True)
canvas.configure(yscrollcommand=scrollbar.set)

content = tk.Frame(canvas)
content.bind(
    '<Configure>',
    lambda e: canvas.configure(scrollregion=canvas.bbox('all'))
)
canvas.create_window((0, 0), window=content, anchor='nw')

# Mouse wheel scrolling bindings (Windows/Linux)
def _on_mousewheel(event):
    try:
        delta = int(-1*(event.delta/120))
        canvas.yview_scroll(delta, 'units')
    except Exception:
        pass

def _on_mousewheel_linux_up(event):
    canvas.yview_scroll(-1, 'units')

def _on_mousewheel_linux_down(event):
    canvas.yview_scroll(1, 'units')

canvas.bind_all('<MouseWheel>', _on_mousewheel)
canvas.bind_all('<Button-4>', _on_mousewheel_linux_up)
canvas.bind_all('<Button-5>', _on_mousewheel_linux_down)

playlist_entries = []
current_formats = []  # populated by Load Formats per selected item
cookies_path = None   # optional cookies file for sites like Facebook
convert_selected_btn = None
convert_all_btn = None

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

# Utility: scan for video files (used by Scan Folder)
def find_video_files(folder_path: str):
    video_extensions = ['.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm']
    matches = []
    for dirpath, dirnames, filenames in os.walk(folder_path):
        for filename in filenames:
            if any(filename.lower().endswith(ext) for ext in video_extensions):
                matches.append(os.path.join(dirpath, filename))
    return matches

# Utility: convert a single file to MP4 via ffmpeg (stream copy)
def convert_to_mp4(input_file: str):
    base, ext = os.path.splitext(input_file)
    output_file = f"{base}.mp4"
    if os.path.normpath(input_file).lower() == os.path.normpath(output_file).lower():
        return True, "Already MP4"
    cmd = ['ffmpeg', '-y', '-i', input_file, '-c:v', 'copy', '-c:a', 'copy', output_file]
    try:
        proc = subprocess.run(cmd, check=True, text=True, capture_output=True, encoding='utf-8')
        return True, output_file
    except FileNotFoundError:
        return False, "FFmpeg not found. Install and add to PATH."
    except subprocess.CalledProcessError as e:
        return False, e.stderr or str(e)
    except Exception as e:
        return False, str(e)
success_count = 0
failure_count = 0

# --- Functions ---
def fetch_videos():
    global playlist_entries
    playlist_entries = []
    video_listbox.delete(0, tk.END)
    # Reset action buttons to download mode
    try:
        start_btn.pack(pady=(5, 10))
        convert_selected_btn.pack_forget()
        convert_all_btn.pack_forget()
    except Exception:
        pass
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
    mode = type_var.get()
    if mode == 'Video':
        q_combo['values'] = video_qualities
        q_combo.current(0)
        q_combo.pack_configure(pady=(5, 10))
        fmt_btn.pack_configure(pady=(0, 5))
        captions_lang_combo_inline.grid_remove()
    elif mode == 'Audio':
        q_combo['values'] = audio_qualities
        q_combo.current(0)
        q_combo.pack_configure(pady=(5, 10))
        fmt_btn.pack_configure(pady=(0, 5))
        captions_lang_combo_inline.grid_remove()
    else:
        # Captions mode
        q_combo['values'] = []
        try:
            q_combo.set('')
        except Exception:
            pass
        q_combo.pack_forget()
        fmt_btn.pack_forget()
        captions_lang_combo_inline.grid()


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
    mode = type_var.get()
    # Resolve selected quality when in Video/Audio mode
    selected_label = q_combo.get()
    quality = None
    if mode in ('Video', 'Audio'):
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

        # Captions mode: use a streamlined captions flow
        if mode == 'Captions':
            lang = captions_lang_var.get().strip() or 'en'
            target_dir = os.path.join(DOWNLOAD_DIR, 'captions')
            os.makedirs(target_dir, exist_ok=True)
            try:
                opts = {
                    'skip_download': True,
                    'writeautomaticsub': True,
                    'writesubtitles': True,
                    'subtitleslangs': [lang],
                    'outtmpl': os.path.join(target_dir, '%(title)s.%(ext)s'),
                    'subtitle_format': 'vtt',
                    'quiet': False,
                    'ignoreerrors': True,
                }
                with YoutubeDL(opts) as ydl:
                    ydl.download([url])
                messagebox.showinfo("Captions", f"Captions downloaded to:\n{target_dir}")
            except Exception as e:
                logging.error(f"Captions download failed: {e}")
                messagebox.showerror("Captions Error", f"Failed to download captions:\n{e}")
            return

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

            if mode == 'Audio':
                ydl_opts_item['extractaudio'] = True
                ydl_opts_item['postprocessors'] = [
                    {
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }
                ]
            else:  # Video
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
tk.Label(content, text="Media URL:").pack(pady=(10, 0))
url_entry = tk.Entry(content, width=80)
url_entry.pack()

fetch_btn = tk.Button(content, text="Fetch Playlist", command=fetch_videos)
fetch_btn.pack(pady=(5, 10))

frame = tk.Frame(content)
frame.pack()
type_var = tk.StringVar(value="Video")
tk.Label(frame, text="Type:").grid(row=0, column=0)
tk.Radiobutton(frame, text="Video", variable=type_var, value="Video", command=update_quality_options).grid(row=0, column=1)
tk.Radiobutton(frame, text="Audio", variable=type_var, value="Audio", command=update_quality_options).grid(row=0, column=2)
tk.Radiobutton(frame, text="Captions", variable=type_var, value="Captions", command=update_quality_options).grid(row=0, column=3)

video_qualities = ['best', 'bestvideo[height<=1080]+bestaudio', 'bestvideo[height<=720]+bestaudio', 'worst']
audio_qualities = ['bestaudio', 'bestaudio[ext=mp3]', 'bestaudio/best']

q_combo = ttk.Combobox(content, values=video_qualities, state="readonly", width=60)
q_combo.current(0)
q_combo.pack(pady=(5, 10))

formats_frame = tk.Frame(content)
formats_frame.pack()
q_combo.pack_forget()
q_combo = ttk.Combobox(formats_frame, values=video_qualities, state="readonly", width=60)
q_combo.current(0)
q_combo.pack(side='left', pady=(5, 10))

# Button to load formats for arbitrary sites (Instagram, TikTok, Twitter, LinkedIn, etc.)
fmt_btn = tk.Button(formats_frame, text="Load Formats", command=load_formats_for_selection)
fmt_btn.pack(side='left', padx=(8, 0), pady=(5, 10))

# Captions language dropdown (shown only when Captions is selected)
captions_lang_var = tk.StringVar(value='en')
captions_lang_combo_inline = ttk.Combobox(frame, values=["en", "ar"], state="readonly", width=8, textvariable=captions_lang_var)
captions_lang_combo_inline.grid(row=0, column=4, padx=(10,0))
captions_lang_combo_inline.grid_remove()

video_listbox = tk.Listbox(content, selectmode=tk.MULTIPLE, width=80, height=12)
video_listbox.pack()

# Internal list scroll for the listbox
list_scrollbar = tk.Scrollbar(content, orient="vertical", command=video_listbox.yview)
video_listbox.config(yscrollcommand=list_scrollbar.set)
list_scrollbar.pack(fill='y')

progress_label = tk.Label(content, text="")
progress_label.pack(pady=(5, 0))

progress_bar = ttk.Progressbar(content, length=500, mode='determinate')
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

folder_frame = tk.Frame(content)
folder_frame.pack(pady=(0, 5))
tk.Button(folder_frame, text="Choose Folder", command=choose_folder).grid(row=0, column=0, padx=(0, 10))
folder_label = tk.Label(folder_frame, text=f"Folder: {DOWNLOAD_DIR}")
folder_label.grid(row=0, column=1)

counts_label = tk.Label(content, text="Downloaded: 0/0 | Errors: 0")
counts_label.pack(pady=(0, 5))

start_btn = tk.Button(content, text="Start Download", command=download_selected, bg="green", fg="white")
start_btn.pack(pady=(5, 10))

# Cookies loader to support sites requiring auth/headers (e.g., Facebook)
def load_cookies():
    global cookies_path
    path = filedialog.askopenfilename(title="Select cookies.txt",
                                      filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
    if path:
        cookies_path = path
        messagebox.showinfo("Cookies Loaded", f"Using cookies from:\n{cookies_path}")

cookies_btn = tk.Button(content, text="Load Cookies.txt (optional)", command=load_cookies)
cookies_btn.pack(pady=(0, 5))

# Inline buttons on the right of type options: Convert MKV to MP4 and Scan Folder
def convert_mkv_button():
    paths = filedialog.askopenfilenames(title="Choose MKV/Video files",
                                        filetypes=[("Video Files", "*.mkv;*.mp4;*.avi;*.mov;*.wmv;*.flv;*.webm"), ("All Files", "*.*")])
    if not paths:
        return
    def _run():
        ok, fail = 0, 0
        for f in paths:
            success, msg = convert_to_mp4(f)
            if success:
                ok += 1
            else:
                fail += 1
                logging.error(f"Convert failed for {f}: {msg}")
        message = f"Converted: {ok}, Failed: {fail}"
        if fail:
            message += "\nCheck log for details."
        messagebox.showinfo("Convert", message)
    threading.Thread(target=_run, daemon=True).start()

def scan_folder_button():
    path = filedialog.askdirectory(initialdir=DOWNLOAD_DIR, title="Choose folder to scan for videos")
    if not path:
        return
    video_listbox.delete(0, tk.END)
    def _scan():
        files = find_video_files(path)
        for p in files:
            video_listbox.insert(tk.END, p)
        if not files:
            messagebox.showinfo("Scan", "No videos found in the selected folder.")
    def _post():
        try:
            start_btn.pack_forget()
            convert_selected_btn.pack(pady=(5, 0))
            convert_all_btn.pack(pady=(5, 10))
        except Exception:
            pass
    def _run():
        _scan()
        root.after(0, _post)
    threading.Thread(target=_run, daemon=True).start()

tk.Button(frame, text="Convert MKV to MP4", command=convert_mkv_button).grid(row=0, column=5, padx=(10,0))
tk.Button(frame, text="Scan Folder\nfor mkv", command=scan_folder_button).grid(row=0, column=6, padx=(6,0))

# Inline convert action buttons (hidden by default, appear after Scan Folder)
convert_selected_btn = tk.Button(content, text="Convert Selected", command=lambda: convert_selected_action_inline())
convert_all_btn = tk.Button(content, text="Convert All", command=lambda: convert_all_action_inline())
convert_selected_btn.pack_forget()
convert_all_btn.pack_forget()

def convert_selected_action_inline():
    sel = video_listbox.curselection()
    if not sel:
        messagebox.showwarning("Convert", "Select one or more files to convert.")
        return
    files = [video_listbox.get(i) for i in sel]
    def _run():
        ok, fail = 0, 0
        for f in files:
            success, msg = convert_to_mp4(f)
            if success:
                ok += 1
            else:
                fail += 1
                logging.error(f"Convert failed for {f}: {msg}")
        message = f"Converted: {ok}, Failed: {fail}"
        if fail:
            message += "\nCheck log for details."
        messagebox.showinfo("Convert Selected", message)
    threading.Thread(target=_run, daemon=True).start()

def convert_all_action_inline():
    count = video_listbox.size()
    if count == 0:
        messagebox.showwarning("Convert", "No files to convert. Run Scan first.")
        return
    files = [video_listbox.get(i) for i in range(count)]
    def _run():
        ok, fail = 0, 0
        for f in files:
            success, msg = convert_to_mp4(f)
            if success:
                ok += 1
            else:
                fail += 1
                logging.error(f"Convert failed for {f}: {msg}")
        message = f"Converted: {ok}, Failed: {fail}"
        if fail:
            message += "\nCheck log for details."
        messagebox.showinfo("Convert All", message)
    threading.Thread(target=_run, daemon=True).start()

## Removed separate Captions and Converter frames; integrated into main controls

root.mainloop()