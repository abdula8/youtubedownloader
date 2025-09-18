# setup_helper.py
import os
import sys
import subprocess
import shutil
import platform
import urllib.request
import zipfile
import tarfile

REQUIRED_PACKAGES = ["yt_dlp", "ffmpeg-python"]

def install_missing_packages():
    for pkg in REQUIRED_PACKAGES:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

def download_and_setup_ffmpeg():
    system = platform.system()
    ffmpeg_dir = os.path.join(os.getcwd(), "ffmpeg_bin")
    ffmpeg_path = os.path.join(ffmpeg_dir, "ffmpeg.exe" if system == "Windows" else "ffmpeg")

    if shutil.which("ffmpeg") or os.path.exists(ffmpeg_path):
        os.environ["PATH"] += os.pathsep + ffmpeg_dir
        return

    print("Downloading FFmpeg...")
    os.makedirs(ffmpeg_dir, exist_ok=True)

    if system == "Windows":
        url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        zip_path = os.path.join(ffmpeg_dir, "ffmpeg.zip")
        urllib.request.urlretrieve(url, zip_path)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(ffmpeg_dir)
        # Locate ffmpeg.exe inside the extracted folder
        for root, dirs, files in os.walk(ffmpeg_dir):
            if "ffmpeg.exe" in files:
                shutil.copy(os.path.join(root, "ffmpeg.exe"), ffmpeg_path)
                break
        os.remove(zip_path)

    elif system == "Linux":
        url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
        tar_path = os.path.join(ffmpeg_dir, "ffmpeg.tar.xz")
        urllib.request.urlretrieve(url, tar_path)
        with tarfile.open(tar_path) as tar_ref:
            tar_ref.extractall(ffmpeg_dir)
        for root, dirs, files in os.walk(ffmpeg_dir):
            if "ffmpeg" in files and os.access(os.path.join(root, "ffmpeg"), os.X_OK):
                shutil.copy(os.path.join(root, "ffmpeg"), ffmpeg_path)
                break
        os.remove(tar_path)

    os.environ["PATH"] += os.pathsep + ffmpeg_dir

def full_setup():
    install_missing_packages()
    download_and_setup_ffmpeg()
