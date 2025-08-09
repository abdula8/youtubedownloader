# YouTube Playlist & Single Video Downloader (GUI)

This Python application provides a **simple graphical interface** for downloading YouTube videos or playlists in different formats and qualities.  
It supports:
- Downloading single videos or full playlists
- Selecting specific items from playlists
- Downloading as **video** or **audio only**
- Saving downloaded files into organized folders
- Resuming downloads without re-downloading completed files

---

## Features
- ✅ Works with **both playlists and single video URLs**
- ✅ Video quality selection (`best`, `1080p`, `720p`, `worst`)
- ✅ Audio extraction in MP3 format
- ✅ Progress bar & status updates
- ✅ Keeps a **download archive** to skip already downloaded files
- ✅ Easy-to-use GUI built with Tkinter

---

## Requirements

Before running the app, make sure you have:

- **Python 3.7+** installed
- Internet connection
- The following Python packages (will be installed automatically):
  - `yt-dlp`
  - `tqdm`
  - `tkinter` (usually included with Python)
  - `ffmpeg` (must be installed separately on your system)

### the script download and install eny needed libraries without user need to do that from the file script "full_setup"

## How to Run

1. Clone or download this repository.
2. Run the application:
   ```bash
   python main.py
3. the script will install the important libraries needed for the application automatically without user interaction in backround before running in the first time and each time check again for libraries  
4. Place your YouTube URLs in the GUI when prompted.

## Usage Instructions

1. **Enter YouTube URL**
   - Can be a playlist link or a single video link

2. **Fetch Playlist/Videos**
   - Click **"Fetch Playlist"** to load video titles into the listbox  
     *(If a single video, only one entry will appear)*

3. **Choose Download Type**
   - **Video:** Select video quality (e.g., `1080p`, `720p`, `best`, `worst`)
   - **Audio:** Saves as MP3

4. **Select Videos**
   - Highlight the videos you want to download from the list

5. **Start Download**
   - Click **"Start Download"** to begin
   - Progress bar and messages will show download status

6. **Files are saved in:**
   - `YouTube_Downloads/<playlist name>` for playlists
   - `YouTube_Downloads` for single videos
   - `YouTube_Downloads/audio_only` for audio downloads


