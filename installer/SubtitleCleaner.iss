; Inno Setup script for Subtitle Cleaner.
; Compile with ISCC (Inno Setup Compiler).
; Driven from the project root via MAKE_INSTALLER.bat.

#define MyAppName "Subtitle Cleaner"
#define MyAppVersion "1.0.0"
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
; Everything PyInstaller produced for the slim app.
Source: "..\build\dist\SubtitleCleaner\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; VLC's installer is embedded but only extracted at runtime if VLC is missing.
Source: "deps\vlc-installer.exe"; Flags: dontcopy

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
function IsVLCInstalled(): Boolean;
var
  InstallDir: String;
begin
  Result := False;
  // Native (matches setup architecture)
  if RegQueryStringValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\VideoLAN\VLC', 'InstallDir', InstallDir) then
    if FileExists(InstallDir + '\vlc.exe') then
      Result := True;
  // 32-bit VLC on a 64-bit system
  if not Result then
    if RegQueryStringValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\WOW6432Node\VideoLAN\VLC', 'InstallDir', InstallDir) then
      if FileExists(InstallDir + '\vlc.exe') then
        Result := True;
  // Fallback: well-known install paths
  if not Result then
    if FileExists(ExpandConstant('{commonpf}\VideoLAN\VLC\vlc.exe')) then
      Result := True;
  if not Result then
    if FileExists(ExpandConstant('{commonpf32}\VideoLAN\VLC\vlc.exe')) then
      Result := True;
end;

procedure InstallVLC();
var
  ResultCode: Integer;
  VLCInstaller: String;
begin
  WizardForm.StatusLabel.Caption := 'Installing VLC media player (required for video playback)...';
  WizardForm.StatusLabel.Refresh;
  ExtractTemporaryFile('vlc-installer.exe');
  VLCInstaller := ExpandConstant('{tmp}\vlc-installer.exe');
  // VLC's installer is NSIS-based; /S = silent install.
  if not Exec(VLCInstaller, '/S', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    MsgBox('VLC could not be installed automatically. ' + #13#10 +
           'You can install it manually from https://www.videolan.org/' + #13#10 +
           'until then, video playback will not work.',
           mbInformation, MB_OK);
  end
  else if ResultCode <> 0 then
  begin
    MsgBox('VLC installer returned an error code (' + IntToStr(ResultCode) + ').' + #13#10 +
           'You may need to install VLC manually from https://www.videolan.org/',
           mbInformation, MB_OK);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if not IsVLCInstalled() then
    begin
      InstallVLC();
    end;
  end;
end;
