[Setup]
AppName=YouTube Downloader
AppVersion=1.0.0
DefaultDirName={pf}\YouTubeDownloader
DefaultGroupName=YouTube Downloader
UninstallDisplayIcon={app}\YouTubeDownloader.exe
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
OutputDir=dist
OutputBaseFilename=YouTubeDownloader-Setup

[Files]
Source: "dist\YouTubeDownloader\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\YouTube Downloader"; Filename: "{app}\YouTubeDownloader.exe"
Name: "{commondesktop}\YouTube Downloader"; Filename: "{app}\YouTubeDownloader.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Run]
Filename: "{app}\YouTubeDownloader.exe"; Description: "Launch YouTube Downloader"; Flags: nowait postinstall skipifsilent
