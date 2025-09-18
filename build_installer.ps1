$ErrorActionPreference = 'Stop'

# Build PyInstaller app
py -3 -m pip install --upgrade pip | cat
py -3 -m pip install pyinstaller | cat
py -3 -m PyInstaller --noconfirm --clean YouTubeDownloader.spec | cat

# Build installer (requires Inno Setup iscc in PATH)
if (Get-Command iscc -ErrorAction SilentlyContinue) {
	iscc installer.iss | cat
	Write-Host "Installer built under dist/"
} else {
	Write-Warning "Inno Setup 'iscc' not found in PATH. Install from https://jrsoftware.org/isinfo.php"
}
