; Inno Setup script for Subtitle Cleaner.
; Compile with ISCC (Inno Setup Compiler).
; Driven from the project root via MAKE_INSTALLER.bat.

#define MyAppName "Subtitle Cleaner"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "Subtitle Cleaner"
#define MyAppExeName "SubtitleCleaner.exe"

[Setup]
; A unique GUID identifies this app for upgrades/uninstall.
AppId={{8B4F2A7E-1C3D-4B8A-9E2F-7A6D5C8B9E0F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={commonpf}\SubtitleCleaner
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=SubtitleCleaner-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
; Everything PyInstaller produced, including the bundled libmpv-2.dll
; and ffmpeg/ffprobe in bin/. v2 dropped python-vlc, so there is no
; runtime VLC dependency to install for the end user any more.
Source: "..\build\dist\SubtitleCleaner\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
