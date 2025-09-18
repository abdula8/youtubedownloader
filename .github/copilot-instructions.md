# Copilot Instructions for YouTubeDownloader

## Project Overview
- Main GUI: `qt_main.py` (PyQt5)
- Legacy GUI: `main.py` (Tkinter)
- Download logic uses `yt-dlp` and organizes files in `YouTube_Downloads/`
- Automatic setup: `setup_helper.py` runs `full_setup()` to install dependencies
- Logging: `youtube_downloader.log` in project root

## Key Patterns & Conventions
- All required Python packages are auto-installed at runtime (see `setup_helper.py`)
- Downloaded files are archived to avoid duplicates
- Settings (download folder, cookies, last URL, mode, CC language) are auto-saved
- Cookies are auto-collected from browsers for authentication (see `CookieCollector` in `qt_main.py`)
- Use `DEFAULT_DOWNLOAD_DIR` for all downloads

## Developer Workflows
### Running the App
- For PyQt5 UI: `python qt_main.py`
- For Tkinter UI: `python main.py`

### Building EXE
- Install PyInstaller: `py -3 -m pip install pyinstaller`
- Build: `py -3 -m PyInstaller --noconfirm --clean --name "YouTubeDownloader" --windowed qt_main.py`

### Testing
- Python tests: Place test scripts like `test_qt_main.py` in project root
- Run all tests: `python -m unittest discover`

## DevOps & CI/CD Guidance
- Recommend GitHub Actions for CI: use `actions/setup-python` and `actions/checkout`
- Add a workflow to run `python -m unittest discover` on push
- For security: use `github/codeql-action` for Python vulnerability scanning
- Example workflow:

```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: python -m unittest discover
  codeql:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - uses: github/codeql-action/init@v2
        with:
          languages: python
      - uses: github/codeql-action/analyze@v2
```

## Integration Points
- External: `yt-dlp`, `ffmpeg` (system dependency)
- GUI: PyQt5 (`qt_main.py`), Tkinter (`main.py`)
- Download archive: text files in `YouTube_Downloads/`

## Security
- Use CodeQL for static analysis
- Consider adding `bandit` for Python security linting

---
For new features, follow the patterns in `qt_main.py` and use `setup_helper.py` for dependency management.
