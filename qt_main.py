import os
import re
import sys
import logging
import threading
import subprocess
import tempfile
import shutil
import json
import sqlite3
import base64
from pathlib import Path
from datetime import datetime

from setup_helper import full_setup

full_setup()

from yt_dlp import YoutubeDL

from PyQt5 import QtCore, QtGui, QtWidgets


def get_default_download_dir() -> str:
	# Use Movies/Videos standard path; fallback to local folder
	try:
		location = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.MoviesLocation)
	except Exception:
		location = ''
	if not location:
		location = os.path.join(str(Path.home()), 'Videos')
	return location


APP_NAME = "YouTube Downloader"
DEFAULT_DOWNLOAD_DIR = os.path.join(get_default_download_dir(), 'YouTube_Downloads')
LOG_FILE = os.path.join(os.path.dirname(Path(__file__).resolve()), 'youtube_downloader.log')

# Create cookies/tokens temp folder
COOKIES_TEMP_DIR = os.path.join(tempfile.gettempdir(), 'YouTubeDownloader_Cookies')
os.makedirs(COOKIES_TEMP_DIR, exist_ok=True)

class CookieCollector:
	"""Automatically collect cookies and tokens from all major browsers"""
	
	def __init__(self):
		self.collected_cookies = []
		self.browser_paths = self._get_browser_paths()
	
	def _get_browser_paths(self):
		"""Get browser data paths for different operating systems"""
		paths = {}
		home = Path.home()
		
		if sys.platform == "win32":
			appdata = os.environ.get('APPDATA', '')
			localappdata = os.environ.get('LOCALAPPDATA', '')
			
			paths = {
				'chrome': Path(localappdata) / 'Google' / 'Chrome' / 'User Data',
				'edge': Path(localappdata) / 'Microsoft' / 'Edge' / 'User Data',
				'firefox': Path(appdata) / 'Mozilla' / 'Firefox' / 'Profiles',
				'opera': Path(appdata) / 'Opera Software' / 'Opera Stable',
				'brave': Path(localappdata) / 'BraveSoftware' / 'Brave-Browser' / 'User Data',
			}
		elif sys.platform == "darwin":  # macOS
			paths = {
				'chrome': home / 'Library' / 'Application Support' / 'Google' / 'Chrome',
				'firefox': home / 'Library' / 'Application Support' / 'Firefox' / 'Profiles',
				'safari': home / 'Library' / 'Cookies',
				'edge': home / 'Library' / 'Application Support' / 'Microsoft Edge',
			}
		else:  # Linux
			paths = {
				'chrome': home / '.config' / 'google-chrome',
				'firefox': home / '.mozilla' / 'firefox',
				'chromium': home / '.config' / 'chromium',
			}
		
		return {k: str(v) for k, v in paths.items() if v.exists()}
	
	def collect_all_cookies(self):
		"""Collect cookies from all available browsers"""
		self.collected_cookies = []
		
		for browser, path in self.browser_paths.items():
			try:
				if browser == 'chrome' or browser == 'edge' or browser == 'brave':
					self._collect_chrome_cookies(browser, path)
				elif browser == 'firefox':
					self._collect_firefox_cookies(browser, path)
				elif browser == 'safari':
					self._collect_safari_cookies(browser, path)
			except Exception as e:
				logging.warning(f"Failed to collect cookies from {browser}: {e}")
		
		# Save collected cookies to temp folder
		self._save_cookies_to_temp()
		return len(self.collected_cookies)
	
	def _collect_chrome_cookies(self, browser, path):
		"""Collect cookies from Chrome-based browsers"""
		cookie_db = os.path.join(path, 'Default', 'Cookies')
		if not os.path.exists(cookie_db):
			return
		
		try:
			# Copy database to temp location (Chrome locks the original)
			temp_db = os.path.join(COOKIES_TEMP_DIR, f'{browser}_cookies.db')
			shutil.copy2(cookie_db, temp_db)
			
			conn = sqlite3.connect(temp_db)
			cursor = conn.cursor()
			
			# Query cookies for social media sites
			social_sites = ['youtube.com', 'twitter.com', 'x.com', 'facebook.com', 'instagram.com', 'tiktok.com', 'linkedin.com']
			placeholders = ','.join(['?' for _ in social_sites])
			
			query = f"""
			SELECT name, value, host_key, path, expires_utc, is_secure, is_httponly
			FROM cookies 
			WHERE host_key LIKE '%' || ? || '%' OR host_key IN ({placeholders})
			"""
			
			cursor.execute(query, ['youtube'] + social_sites)
			rows = cursor.fetchall()
			
			for row in rows:
				name, value, domain, path, expires, secure, httponly = row
				# Convert Chrome timestamp to Unix timestamp
				if expires > 0:
					expires = (expires - 11644473600000000) / 1000000
				else:
					expires = 0
				
				cookie = {
					'name': name,
					'value': value,
					'domain': domain,
					'path': path or '/',
					'expires': expires,
					'secure': bool(secure),
					'httponly': bool(httponly)
				}
				self.collected_cookies.append(cookie)
			
			conn.close()
			os.remove(temp_db)  # Clean up temp file
			
		except Exception as e:
			logging.error(f"Error collecting Chrome cookies: {e}")
	
	def _collect_firefox_cookies(self, browser, path):
		"""Collect cookies from Firefox"""
		# Find the default profile
		profiles = [d for d in os.listdir(path) if d.startswith('.') and os.path.isdir(os.path.join(path, d))]
		if not profiles:
			return
		
		profile_path = os.path.join(path, profiles[0])
		cookie_db = os.path.join(profile_path, 'cookies.sqlite')
		
		if not os.path.exists(cookie_db):
			return
		
		try:
			conn = sqlite3.connect(cookie_db)
			cursor = conn.cursor()
			
			query = """
			SELECT name, value, host, path, expiry, isSecure, isHttpOnly
			FROM moz_cookies 
			WHERE host LIKE '%youtube%' OR host LIKE '%twitter%' OR host LIKE '%x.com%' 
			OR host LIKE '%facebook%' OR host LIKE '%instagram%' OR host LIKE '%tiktok%'
			"""
			
			cursor.execute(query)
			rows = cursor.fetchall()
			
			for row in rows:
				name, value, domain, path, expires, secure, httponly = row
				cookie = {
					'name': name,
					'value': value,
					'domain': domain,
					'path': path or '/',
					'expires': expires or 0,
					'secure': bool(secure),
					'httponly': bool(httponly)
				}
				self.collected_cookies.append(cookie)
			
			conn.close()
			
		except Exception as e:
			logging.error(f"Error collecting Firefox cookies: {e}")
	
	def _collect_safari_cookies(self, browser, path):
		"""Collect cookies from Safari (macOS only)"""
		# Safari cookies are in binary format, this is a simplified approach
		try:
			# This would require additional libraries to parse Safari's binary format
			# For now, we'll skip Safari and focus on Chrome/Firefox
			pass
		except Exception as e:
			logging.error(f"Error collecting Safari cookies: {e}")
	
	def _save_cookies_to_temp(self):
		"""Save collected cookies in various formats for yt-dlp"""
		if not self.collected_cookies:
			return
		
		# Save as Netscape format (cookies.txt)
		cookies_txt = os.path.join(COOKIES_TEMP_DIR, 'cookies.txt')
		with open(cookies_txt, 'w', encoding='utf-8') as f:
			f.write("# Netscape HTTP Cookie File\n")
			f.write("# This file contains cookies automatically collected from your browsers\n")
			f.write(f"# Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
			
			for cookie in self.collected_cookies:
				domain = cookie['domain']
				if domain.startswith('.'):
					domain_flag = 'TRUE'
				else:
					domain_flag = 'FALSE'
				
				path = cookie['path']
				secure = 'TRUE' if cookie['secure'] else 'FALSE'
				expires = str(int(cookie['expires'])) if cookie['expires'] > 0 else '0'
				name = cookie['name']
				value = cookie['value']
				
				f.write(f"{domain}\t{domain_flag}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n")
		
		# Save as JSON format for debugging
		cookies_json = os.path.join(COOKIES_TEMP_DIR, 'cookies.json')
		with open(cookies_json, 'w', encoding='utf-8') as f:
			json.dump(self.collected_cookies, f, indent=2, ensure_ascii=False)
		
		logging.info(f"Collected {len(self.collected_cookies)} cookies from browsers")


class CookieCollectionWorker(QtCore.QObject):
	"""Worker for cookie collection in background thread"""
	cookies_collected = QtCore.pyqtSignal(int)
	cookies_error = QtCore.pyqtSignal(str)
	finished = QtCore.pyqtSignal()
	
	def collect_cookies(self):
		"""Collect cookies from all browsers"""
		try:
			collector = CookieCollector()
			count = collector.collect_all_cookies()
			
			if count > 0:
				cookies_file = os.path.join(COOKIES_TEMP_DIR, 'cookies.txt')
				if os.path.exists(cookies_file):
					self.cookies_collected.emit(count)
				else:
					self.cookies_error.emit('No cookies found in browsers')
			else:
				self.cookies_error.emit('No cookies found. Make sure you are logged into social media sites in your browsers.')
		except Exception as e:
			self.cookies_error.emit(f'Error collecting cookies: {e}')
		finally:
			self.finished.emit()


os.makedirs(DEFAULT_DOWNLOAD_DIR, exist_ok=True)

logging.basicConfig(
	filename=LOG_FILE,
	level=logging.INFO,
	format='%(asctime)s - %(levelname)s - %(message)s'
)


class DownloadWorker(QtCore.QObject):
	progress = QtCore.pyqtSignal(str)
	counts = QtCore.pyqtSignal(int, int, int)
	finished = QtCore.pyqtSignal()
	message = QtCore.pyqtSignal(str, str)

	def __init__(self, *,
				url: str,
				mode: str,
				selected_indices: list[int],
				quality_selector: str | None,
				download_dir: str,
				cookies_path: str | None,
				captions_lang: str,
				use_archive: bool = True):
		super().__init__()
		self.url = url
		self.mode = mode
		self.selected_indices = selected_indices
		self.quality_selector = quality_selector
		self.download_dir = download_dir
		self.cookies_path = cookies_path
		self.captions_lang = captions_lang
		self.use_archive = use_archive

	def _progress_hook(self, d):
		try:
			if d.get('status') == 'downloading':
				percent = d.get('_percent_str', '').strip()
				self.progress.emit(f"Downloading: {percent}")
			elif d.get('status') == 'finished':
				self.progress.emit(f"Finished: {d.get('filename')}")
		except Exception:
			pass

	def run(self):
		try:
			ARCHIVE_FILE = os.path.join(self.download_dir, 'downloaded_videos.txt')
			AUDIO_DIR = os.path.join(self.download_dir, 'audio_only')
			os.makedirs(self.download_dir, exist_ok=True)
			os.makedirs(AUDIO_DIR, exist_ok=True)

			if self.mode == 'Captions':
				target_dir = os.path.join(self.download_dir, 'captions')
				os.makedirs(target_dir, exist_ok=True)
				opts = {
					'skip_download': True,
					'writeautomaticsub': True,
					'writesubtitles': True,
					'subtitleslangs': [self.captions_lang or 'en'],
					'outtmpl': os.path.join(target_dir, '%(title)s.%(ext)s'),
					'subtitle_format': 'vtt',
					'quiet': False,
					'ignoreerrors': True,
				}
				if self.cookies_path:
					opts['cookiefile'] = self.cookies_path
				with YoutubeDL(opts) as ydl:
					ydl.download([self.url])
				self.message.emit('info', f"Captions saved to: {target_dir}")
				self.finished.emit()
				return

			success_count = 0
			failure_count = 0
			total_items = len(self.selected_indices)
			self.counts.emit(success_count, failure_count, total_items)

			for offset, idx in enumerate(self.selected_indices, start=1):
				outtmpl = '%(playlist_index|NA)s - %(title)s.%(ext)s'
				paths = {'home': self.download_dir, 'temp': self.download_dir}
				ydl_opts_item = {
					'format': self.quality_selector or 'best',
					'outtmpl': outtmpl,
					'paths': paths,
					'ignoreerrors': False,
					'progress_hooks': [self._progress_hook],
					'playlist_items': str(idx),
					'retries': 10,
					'fragment_retries': 10,
					'concurrent_fragment_downloads': 3,
					'windowsfilenames': True,
					'restrictfilenames': True,
					'socket_timeout': 60,
					'http_timeout': 60,
					'extractor_retries': 3,
				}
				if self.cookies_path:
					ydl_opts_item['cookiefile'] = self.cookies_path
				if self.use_archive:
					ydl_opts_item['download_archive'] = ARCHIVE_FILE

				if self.mode == 'Audio':
					ydl_opts_item['extractaudio'] = True
					ydl_opts_item['postprocessors'] = [{
						'key': 'FFmpegExtractAudio',
						'preferredcodec': 'mp3',
						'preferredquality': '192',
					}]
				else:
					ydl_opts_item['postprocessors'] = [{
						'key': 'FFmpegVideoRemuxer',
						'preferedformat': 'mkv'
					}]

				attempts = 0
				local_max = 5
				while True:
					try:
						self.progress.emit(f"Starting item {offset}/{total_items}")
						with YoutubeDL(ydl_opts_item) as ydl:
							ydl.download([self.url])
						success_count += 1
						self.counts.emit(success_count, failure_count, total_items)
						break
					except Exception as e:
						attempts += 1
						logging.error(f"Download failed (item {idx}) attempt {attempts}: {e}")
						self.progress.emit(f"Error (attempt {attempts}/{local_max})")
						if attempts >= local_max:
							failure_count += 1
							self.counts.emit(success_count, failure_count, total_items)
							break

			if failure_count == 0:
				self.message.emit('info', f"All {success_count} item(s) downloaded successfully.")
			else:
				self.message.emit('warn', f"Downloaded {success_count} with {failure_count} error(s). Check logs.")
		except Exception as e:
			logging.exception("Worker error")
			self.message.emit('error', str(e))
		finally:
			self.finished.emit()


class FfmpegConvertWorker(QtCore.QObject):
	progress = QtCore.pyqtSignal(str)
	finished = QtCore.pyqtSignal(int, int)

	def __init__(self, files: list[str]):
		super().__init__()
		self.files = files

	def run(self):
		ok = 0
		fail = 0
		for f in self.files:
			base, ext = os.path.splitext(f)
			out = f"{base}.mp4"
			if os.path.normpath(f).lower() == os.path.normpath(out).lower():
				ok += 1
				continue
			cmd = ['ffmpeg', '-y', '-i', f, '-c:v', 'copy', '-c:a', 'copy', out]
			try:
				subprocess.run(cmd, check=True, text=True, capture_output=True, encoding='utf-8')
				ok += 1
			except Exception as e:
				logging.error(f"Convert failed for {f}: {e}")
				fail += 1
		self.finished.emit(ok, fail)


class DropLineEdit(QtWidgets.QLineEdit):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.setAcceptDrops(True)

	def dragEnterEvent(self, event: QtGui.QDragEnterEvent):
		if event.mimeData().hasUrls() or event.mimeData().hasText():
			event.acceptProposedAction()
		else:
			event.ignore()

	def dropEvent(self, event: QtGui.QDropEvent):
		if event.mimeData().hasUrls():
			urls = event.mimeData().urls()
			if urls:
				self.setText(urls[0].toString())
		elif event.mimeData().hasText():
			self.setText(event.mimeData().text())


class MainWindow(QtWidgets.QMainWindow):
	def __init__(self):
		super().__init__()
		self.setWindowTitle(APP_NAME)
		self.resize(900, 700)
		self.setUnifiedTitleAndToolBarOnMac(True)

		self.settings = QtCore.QSettings('YTTools', 'Downloader')

		self.download_dir = self.settings.value('download_dir', DEFAULT_DOWNLOAD_DIR, type=str)
		self.cookies_path = self.settings.value('cookies_path', '', type=str) or None
		self.last_url = self.settings.value('last_url', '', type=str)
		self.last_mode = self.settings.value('last_mode', 'Video', type=str)
		self.captions_lang = self.settings.value('captions_lang', 'en', type=str)

		self.playlist_entries: list[dict] = []
		self.current_formats: list[tuple[str, str]] = []

		self._build_ui()
		self._apply_theme()

	def closeEvent(self, event: QtGui.QCloseEvent):
		self.settings.setValue('download_dir', self.download_dir)
		self.settings.setValue('cookies_path', self.cookies_path or '')
		self.settings.setValue('last_url', self.url_edit.text().strip())
		self.settings.setValue('last_mode', self.mode_group.checkedButton().text())
		self.settings.setValue('captions_lang', self.captions_combo.currentText())
		super().closeEvent(event)

	def _build_ui(self):
		central = QtWidgets.QWidget(self)
		self.setCentralWidget(central)

		layout = QtWidgets.QVBoxLayout(central)

		# URL row
		url_row = QtWidgets.QHBoxLayout()
		layout.addLayout(url_row)
		url_label = QtWidgets.QLabel('Media URL:')
		self.url_edit = DropLineEdit()
		self.url_edit.setPlaceholderText('Paste or drop a video/playlist URL here')
		self.url_edit.setText(self.last_url)
		fetch_btn = QtWidgets.QPushButton('Fetch')
		fetch_btn.clicked.connect(self.fetch_videos)
		url_row.addWidget(url_label)
		url_row.addWidget(self.url_edit, 1)
		url_row.addWidget(fetch_btn)

		# Mode + quality row
		mode_row = QtWidgets.QHBoxLayout()
		layout.addLayout(mode_row)
		mode_label = QtWidgets.QLabel('Type:')
		mode_row.addWidget(mode_label)
		self.mode_group = QtWidgets.QButtonGroup(self)
		self.video_rb = QtWidgets.QRadioButton('Video')
		self.audio_rb = QtWidgets.QRadioButton('Audio')
		self.captions_rb = QtWidgets.QRadioButton('Captions')
		self.mode_group.addButton(self.video_rb)
		self.mode_group.addButton(self.audio_rb)
		self.mode_group.addButton(self.captions_rb)
		(mode_row.addWidget(self.video_rb), mode_row.addWidget(self.audio_rb), mode_row.addWidget(self.captions_rb))
		if self.last_mode == 'Audio':
			self.audio_rb.setChecked(True)
		elif self.last_mode == 'Captions':
			self.captions_rb.setChecked(True)
		else:
			self.video_rb.setChecked(True)

		self.quality_combo = QtWidgets.QComboBox()
		self.quality_combo.setMinimumWidth(320)
		video_qualities = ['best', 'bestvideo[height<=1080]+bestaudio', 'bestvideo[height<=720]+bestaudio', 'worst']
		audio_qualities = ['bestaudio', 'bestaudio[ext=mp3]', 'bestaudio/best']
		self.default_video_qualities = video_qualities
		self.default_audio_qualities = audio_qualities
		self.quality_combo.addItems(video_qualities)
		mode_row.addWidget(self.quality_combo)
		self.load_formats_btn = QtWidgets.QPushButton('Load Formats')
		self.load_formats_btn.clicked.connect(self.load_formats_for_selection)
		mode_row.addWidget(self.load_formats_btn)

		mode_row.addSpacing(12)
		mode_row.addWidget(QtWidgets.QLabel('CC Lang:'))
		self.captions_combo = QtWidgets.QComboBox()
		self.captions_combo.addItems(['en', 'ar'])
		self.captions_combo.setCurrentText(self.captions_lang)
		mode_row.addWidget(self.captions_combo)

		self.mode_group.buttonClicked.connect(self._update_quality_options)
		self._update_quality_options()

		# List and actions
		list_row = QtWidgets.QHBoxLayout()
		layout.addLayout(list_row, 1)
		self.list_widget = QtWidgets.QListWidget()
		self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
		list_row.addWidget(self.list_widget, 1)

		# Right actions
		actions_col = QtWidgets.QVBoxLayout()
		list_row.addLayout(actions_col)
		self.cookies_btn = QtWidgets.QPushButton('🍪 Smart Cookies Manager')
		self.cookies_btn.clicked.connect(self.smart_cookies_manager)
		self.cookies_btn.setStyleSheet('QPushButton { background: #1976d2; color: white; padding: 8px 14px; font-weight: bold; }')
		actions_col.addWidget(self.cookies_btn)
		self.convert_btn = QtWidgets.QPushButton('Convert MKV→MP4')
		self.convert_btn.clicked.connect(self.convert_mkv)
		actions_col.addWidget(self.convert_btn)
		self.scan_btn = QtWidgets.QPushButton('Scan Folder for Videos')
		self.scan_btn.clicked.connect(self.scan_folder)
		actions_col.addWidget(self.scan_btn)
		actions_col.addStretch(1)

		# Folder chooser and counts
		folder_row = QtWidgets.QHBoxLayout()
		layout.addLayout(folder_row)
		self.folder_btn = QtWidgets.QPushButton('Choose Folder')
		self.folder_btn.clicked.connect(self.choose_folder)
		self.folder_label = QtWidgets.QLabel(self.download_dir)
		self.folder_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
		folder_row.addWidget(self.folder_btn)
		folder_row.addWidget(self.folder_label, 1)

		# Progress and start
		self.counts_label = QtWidgets.QLabel('Downloaded: 0/0 | Errors: 0')
		layout.addWidget(self.counts_label)
		self.progress_label = QtWidgets.QLabel('')
		layout.addWidget(self.progress_label)
		self.progress_bar = QtWidgets.QProgressBar()
		self.progress_bar.setRange(0, 0)  # indeterminate; update text instead
		self.progress_bar.setVisible(False)
		layout.addWidget(self.progress_bar)
		self.start_btn = QtWidgets.QPushButton('Start Download')
		self.start_btn.clicked.connect(self.download_selected)
		self.start_btn.setStyleSheet('QPushButton { background: #2e7d32; color: white; padding: 8px 14px; }')
		layout.addWidget(self.start_btn)

		# Status bar
		self.status = QtWidgets.QStatusBar(self)
		self.setStatusBar(self.status)
		self.status.showMessage(f'Ready | Cookies folder: {COOKIES_TEMP_DIR}')
		
		# Auto-collect cookies on startup
		self._auto_collect_on_startup()

	def _auto_collect_on_startup(self):
		"""Automatically collect cookies on startup in background"""
		def _startup_collect():
			try:
				collector = CookieCollector()
				count = collector.collect_all_cookies()
				if count > 0:
					cookies_file = os.path.join(COOKIES_TEMP_DIR, 'cookies.txt')
					if os.path.exists(cookies_file):
						self.cookies_path = cookies_file
						QtCore.QMetaObject.invokeMethod(self, '_update_startup_status', 
							QtCore.Qt.QueuedConnection, 
							QtCore.Q_ARG(int, count))
			except Exception as e:
				logging.warning(f"Startup cookie collection failed: {e}")
		
		threading.Thread(target=_startup_collect, daemon=True).start()

	def _update_startup_status(self, count: int):
		"""Update status bar after startup cookie collection"""
		self.status.showMessage(f'Ready | Auto-collected {count} cookies | Folder: {COOKIES_TEMP_DIR}')

	def _apply_theme(self):
		# Simple dark-aware palette toggle based on OS; keep light with good spacing
		self.setStyleSheet('')

	def _update_quality_options(self):
		mode = self.mode_group.checkedButton().text() if self.mode_group.checkedButton() else 'Video'
		self.load_formats_btn.setEnabled(mode != 'Captions')
		self.captions_combo.setEnabled(mode == 'Captions')
		self.quality_combo.clear()
		if mode == 'Video':
			self.quality_combo.addItems(self.default_video_qualities)
		elif mode == 'Audio':
			self.quality_combo.addItems(self.default_audio_qualities)
		else:
			self.quality_combo.setEnabled(False)
			return
		self.quality_combo.setEnabled(True)

	def show_message(self, kind: str, text: str):
		if kind == 'info':
			QtWidgets.QMessageBox.information(self, APP_NAME, text)
		elif kind == 'warn':
			QtWidgets.QMessageBox.warning(self, APP_NAME, text)
		else:
			QtWidgets.QMessageBox.critical(self, APP_NAME, text)

	def resolve_final_url(self, input_url: str) -> str:
		try:
			import requests
			headers = {'User-Agent': 'Mozilla/5.0'}
			resp = requests.get(input_url, headers=headers, allow_redirects=True, timeout=15)
			return resp.url or input_url
		except ImportError:
			# Fallback if requests not available
			return input_url
		except Exception:
			return input_url

	def fetch_videos(self):
		self.playlist_entries = []
		self.list_widget.clear()
		url = (self.url_edit.text() or '').strip()
		url = self.resolve_final_url(url)
		if not url:
			self.show_message('warn', 'Please enter a URL.')
			return
		self.status.showMessage('Fetching...')
		QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
		QtWidgets.QApplication.processEvents()
		try:
			ydl_opts = {
				'extract_flat': True,
				'quiet': True,
				'skip_download': True,
				'socket_timeout': 60,
				'http_timeout': 60,
				'extractor_retries': 3,
			}
			if self.cookies_path:
				ydl_opts['cookiefile'] = self.cookies_path
			with YoutubeDL(ydl_opts) as ydl:
				info = ydl.extract_info(url, download=False)
				if isinstance(info, dict) and info.get('entries'):
					for i, entry in enumerate(info['entries'] or []):
						if not isinstance(entry, dict):
							continue
						title = entry.get('title') or entry.get('id', 'Unknown')
						self.playlist_entries.append(entry)
						self.list_widget.addItem(f"{i+1:03d}. {title}")
					if not info['entries']:
						self.show_message('warn', 'No media found.')
				elif isinstance(info, dict):
					title = info.get('title') or info.get('id', 'Unknown')
					self.playlist_entries.append(info)
					self.list_widget.addItem(f"001. {title}")
				else:
					self.show_message('warn', 'No downloadable media found.')
		except Exception as e:
			self.show_message('error', f"Could not fetch info. If site requires auth, try loading cookies.txt and retry.\n\n{e}")
		finally:
			self.status.showMessage('Ready')
			QtWidgets.QApplication.restoreOverrideCursor()

	def load_formats_for_selection(self):
		selected = self.list_widget.selectedIndexes()
		if not selected:
			self.show_message('warn', 'Select a video to load formats.')
			return
		idx = selected[0].row()
		url = (self.url_edit.text() or '').strip()
		url = self.resolve_final_url(url)
		if not url:
			self.show_message('warn', 'Please enter a URL first.')
			return
		self.progress_label.setText('Loading formats...')

		def _load():
			try:
				base_opts = {
					'quiet': True,
					'playlist_items': str(idx + 1),
					'extract_flat': False,  # Need full info for formats
					'socket_timeout': 60,
					'http_timeout': 60,
					'extractor_retries': 3,
				}
				if self.cookies_path:
					base_opts['cookiefile'] = self.cookies_path
				with YoutubeDL(base_opts) as ydl:
					info = ydl.extract_info(url, download=False)
			except Exception as e:
				logging.error(f"Format load failed: {e}")
				QtCore.QMetaObject.invokeMethod(self, '_update_progress_text', QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, 'Failed to load formats'))
				return

			# Handle different info structures
			formats = []
			if isinstance(info, dict):
				if 'formats' in info:
					formats = info['formats']
				elif 'entries' in info and info['entries'] and isinstance(info['entries'], list):
					# Playlist with entries
					entry = info['entries'][idx] if idx < len(info['entries']) else None
					if entry and isinstance(entry, dict) and 'formats' in entry:
						formats = entry['formats']
			elif isinstance(info, list) and info and idx < len(info):
				entry = info[idx]
				if isinstance(entry, dict) and 'formats' in entry:
					formats = entry['formats']

			heights = []
			for f in formats:
				vcodec = f.get('vcodec')
				height = f.get('height')
				if vcodec and vcodec != 'none' and height and isinstance(height, int):
					heights.append(height)
			heights = sorted(set(heights), reverse=True)

			choices: list[tuple[str, str]] = [('best', 'best (auto)')]
			for h in heights:
				selector = f"bestvideo[height<={h}]+bestaudio/best"
				label = f"<= {h}p (video+bestaudio)"
				choices.append((selector, label))
			if len(choices) == 1:
				choices.extend([('best', 'best'), ('worst', 'worst')])

			self.current_formats = choices
			labels = [label for _, label in choices]
			
			# Use direct method calls instead of QMetaObject
			QtCore.QMetaObject.invokeMethod(self, '_update_quality_combo', QtCore.Qt.QueuedConnection, QtCore.Q_ARG(list, labels))
			QtCore.QMetaObject.invokeMethod(self, '_update_progress_text', QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, 'Formats loaded.'))

		threading.Thread(target=_load, daemon=True).start()

	def _update_progress_text(self, text: str):
		self.progress_label.setText(text)

	def _update_quality_combo(self, labels: list):
		self.quality_combo.clear()
		for label in labels:
			self.quality_combo.addItem(label)

	def download_selected(self):
		selected = self.list_widget.selectedIndexes()
		if not selected and self.list_widget.count() > 0:
			# If nothing selected, default to all
			selected_indices = [i + 1 for i in range(self.list_widget.count())]
		elif not selected:
			self.show_message('warn', 'Select at least one item.')
			return
		else:
			selected_indices = [s.row() + 1 for s in selected]

		mode = self.mode_group.checkedButton().text() if self.mode_group.checkedButton() else 'Video'
		selected_label = self.quality_combo.currentText()
		quality = None
		if mode in ('Video', 'Audio') and self.current_formats:
			for selector, label in self.current_formats:
				if label == selected_label:
					quality = selector
					break
		if not quality and mode != 'Captions':
			quality = selected_label

		url = (self.url_edit.text() or '').strip()
		if not url:
			self.show_message('warn', 'Enter URL')
			return

		self.progress_bar.setVisible(True)
		self.progress_label.setText('Starting...')
		self.progress_bar.setRange(0, 0)
		self.start_btn.setEnabled(False)

		self.worker = DownloadWorker(
			url=url,
			mode=mode,
			selected_indices=selected_indices,
			quality_selector=quality,
			download_dir=self.download_dir,
			cookies_path=self.cookies_path,
			captions_lang=self.captions_combo.currentText(),
		)
		self.thread = QtCore.QThread(self)
		self.worker.moveToThread(self.thread)
		self.thread.started.connect(self.worker.run)
		self.worker.progress.connect(self.progress_label.setText)
		self.worker.counts.connect(lambda ok, fail, total: self.counts_label.setText(f"Downloaded: {ok}/{total} | Errors: {fail}"))
		self.worker.message.connect(self._on_worker_message)
		self.worker.finished.connect(self._on_worker_finished)
		self.worker.finished.connect(self.thread.quit)
		self.worker.finished.connect(self.worker.deleteLater)
		self.thread.finished.connect(self.thread.deleteLater)
		self.thread.start()

	def _on_worker_message(self, kind: str, text: str):
		self.show_message(kind, text)

	def _on_worker_finished(self):
		self.progress_bar.setVisible(False)
		self.start_btn.setEnabled(True)
		self.status.showMessage('Ready')

	def choose_folder(self):
		dir_ = QtWidgets.QFileDialog.getExistingDirectory(self, 'Choose download folder', self.download_dir)
		if dir_:
			self.download_dir = dir_
			self.folder_label.setText(self.download_dir)

	def smart_cookies_manager(self):
		"""Smart cookies manager - auto-collect, open folder, and load cookies"""
		# Show options dialog
		msg = QtWidgets.QMessageBox(self)
		msg.setWindowTitle('🍪 Smart Cookies Manager')
		msg.setText('Choose an action:')
		msg.setIcon(QtWidgets.QMessageBox.Question)
		
		collect_btn = msg.addButton('🔄 Auto-Collect from Browsers', QtWidgets.QMessageBox.ActionRole)
		open_folder_btn = msg.addButton('📁 Open Cookies Folder', QtWidgets.QMessageBox.ActionRole)
		load_btn = msg.addButton('📂 Load Custom cookies.txt', QtWidgets.QMessageBox.ActionRole)
		cancel_btn = msg.addButton('❌ Cancel', QtWidgets.QMessageBox.RejectRole)
		
		msg.exec_()
		
		if msg.clickedButton() == collect_btn:
			self._auto_collect_cookies()
		elif msg.clickedButton() == open_folder_btn:
			self._open_cookies_folder()
		elif msg.clickedButton() == load_btn:
			self._load_custom_cookies()

	def _auto_collect_cookies(self):
		"""Automatically collect cookies from all browsers"""
		self.cookies_btn.setEnabled(False)
		self.cookies_btn.setText('🔄 Collecting...')
		self.status.showMessage('Auto-collecting cookies from browsers...')
		
		# Create worker for cookie collection
		self.cookie_worker = CookieCollectionWorker()
		self.cookie_thread = QtCore.QThread()
		self.cookie_worker.moveToThread(self.cookie_thread)
		
		# Connect signals
		self.cookie_thread.started.connect(self.cookie_worker.collect_cookies)
		self.cookie_worker.cookies_collected.connect(self._on_cookies_collected)
		self.cookie_worker.cookies_error.connect(self._on_cookies_error)
		self.cookie_worker.finished.connect(self.cookie_thread.quit)
		self.cookie_worker.finished.connect(self.cookie_worker.deleteLater)
		self.cookie_thread.finished.connect(self.cookie_thread.deleteLater)
		
		# Start the thread
		self.cookie_thread.start()

	def _on_cookies_collected(self, count: int):
		"""Called when cookies are successfully collected"""
		self.cookies_btn.setEnabled(True)
		self.cookies_btn.setText('🍪 Smart Cookies Manager')
		self.status.showMessage(f'Successfully collected {count} cookies from browsers')
		
		# Auto-load the collected cookies
		cookies_file = os.path.join(COOKIES_TEMP_DIR, 'cookies.txt')
		if os.path.exists(cookies_file):
			self.cookies_path = cookies_file
		
		self.show_message('info', f'Successfully collected {count} cookies from your browsers!\n\nCookies saved to: {COOKIES_TEMP_DIR}\n\nYou can now download from social media sites that require authentication.')

	def _on_cookies_error(self, error: str):
		"""Called when cookie collection fails"""
		self.cookies_btn.setEnabled(True)
		self.cookies_btn.setText('🍪 Smart Cookies Manager')
		self.status.showMessage('Cookie collection failed')
		self.show_message('warn', f'Cookie collection failed:\n{error}')

	def _open_cookies_folder(self):
		"""Open the cookies/tokens temp folder for user convenience"""
		try:
			import subprocess
			import platform
			if platform.system() == 'Windows':
				subprocess.run(['explorer', COOKIES_TEMP_DIR], check=True)
			elif platform.system() == 'Darwin':  # macOS
				subprocess.run(['open', COOKIES_TEMP_DIR], check=True)
			else:  # Linux
				subprocess.run(['xdg-open', COOKIES_TEMP_DIR], check=True)
		except Exception as e:
			self.show_message('warn', f'Could not open folder: {e}\n\nFolder location: {COOKIES_TEMP_DIR}')

	def _load_custom_cookies(self):
		"""Load custom cookies.txt file"""
		path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Select cookies.txt', COOKIES_TEMP_DIR, 'Text Files (*.txt);;All Files (*)')
		if path:
			self.cookies_path = path
			self.show_message('info', f'Using custom cookies from:\n{path}\n\nCookies folder: {COOKIES_TEMP_DIR}')

	def convert_mkv(self):
		files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, 'Choose MKV/Video files', '', 'Video Files (*.mkv *.mp4 *.avi *.mov *.wmv *.flv *.webm);;All Files (*)')
		if not files:
			return
		self.progress_bar.setVisible(True)
		self.progress_bar.setRange(0, 0)
		worker = FfmpegConvertWorker(files)
		thread = QtCore.QThread(self)
		worker.moveToThread(thread)
		thread.started.connect(worker.run)
		worker.finished.connect(lambda ok, fail: self.show_message('info', f'Converted: {ok}, Failed: {fail}'))
		worker.finished.connect(thread.quit)
		worker.finished.connect(worker.deleteLater)
		thread.finished.connect(self._hide_progress)
		thread.finished.connect(thread.deleteLater)
		thread.start()

	def _hide_progress(self):
		self.progress_bar.setVisible(False)

	def scan_folder(self):
		path = QtWidgets.QFileDialog.getExistingDirectory(self, 'Choose folder to scan for videos', self.download_dir)
		if not path:
			return
		self.list_widget.clear()
		def _scan():
			video_extensions = ['.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm']
			for dirpath, dirnames, filenames in os.walk(path):
				for filename in filenames:
					if any(filename.lower().endswith(ext) for ext in video_extensions):
						self.list_widget.addItem(os.path.join(dirpath, filename))
			if self.list_widget.count() == 0:
				self.show_message('info', 'No videos found in the selected folder.')
		threading.Thread(target=_scan, daemon=True).start()


def check_admin_privileges():
	"""Check if running with administrator privileges"""
	if sys.platform == "win32":
		try:
			import ctypes
			return ctypes.windll.shell32.IsUserAnAdmin()
		except:
			return False
	return True  # Assume admin on non-Windows

def request_admin_privileges():
	"""Request administrator privileges on Windows"""
	if sys.platform == "win32":
		try:
			import ctypes
			ctypes.windll.shell32.ShellExecuteW(
				None, "runas", sys.executable, " ".join(sys.argv), None, 1
			)
			return True
		except:
			return False
	return False

def main():
	# Create QApplication first
	app = QtWidgets.QApplication(sys.argv)
	app.setApplicationName(APP_NAME)
	
	# Check for admin privileges after QApplication is created
	if not check_admin_privileges():
		if sys.platform == "win32":
			reply = QtWidgets.QMessageBox.question(
				None, 
				'Administrator Required',
				'This application needs administrator privileges to access browser cookies.\n\nWould you like to restart as administrator?',
				QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
				QtWidgets.QMessageBox.Yes
			)
			if reply == QtWidgets.QMessageBox.Yes:
				if request_admin_privileges():
					sys.exit(0)
				else:
					QtWidgets.QMessageBox.warning(None, 'Error', 'Failed to restart as administrator.')
					sys.exit(1)
			else:
				QtWidgets.QMessageBox.warning(None, 'Warning', 'Running without administrator privileges may limit cookie collection functionality.')
	
	window = MainWindow()
	window.show()
	sys.exit(app.exec_())


if __name__ == '__main__':
	main()


