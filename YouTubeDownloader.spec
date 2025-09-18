# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

added_datas = []
import os
ffmpeg_dir = os.path.join(os.getcwd(), 'ffmpeg_bin')
if os.path.isdir(ffmpeg_dir):
	added_datas.append((ffmpeg_dir, 'ffmpeg_bin'))

a = Analysis(
	['qt_main.py'],
	pathex=[],
	binaries=[],
	datas=added_datas,
	hiddenimports=[],
	hookspath=[],
	runtime_hooks=[],
	excludes=[],
	noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
	pyz,
	a.scripts,
	a.binaries,
	a.zipfiles,
	a.datas,
	[],
	name='YouTubeDownloader',
	debug=False,
	bootloader_ignore_signals=False,
	strip=False,
	upx=True,
	console=False,
)

coll = COLLECT(
	exe,
	name='YouTubeDownloader',
	strip=False,
	upx=True,
	upx_exclude=[],
)


