#ifndef AppVersion
  #define AppVersion "1.1.1"
#endif
[Setup]
AppId={{F2777E7D-38D9-45D3-A932-F9E7F7BD5D71}
AppName=Polaroid Editor
AppVersion={#AppVersion}
AppPublisher=RedLab
AppPublisherURL=https://github.com/redlab-coder/polaroid-editor
AppSupportURL=https://github.com/redlab-coder/polaroid-editor/issues
AppUpdatesURL=https://github.com/redlab-coder/polaroid-editor/releases
DefaultDirName={localappdata}\Programs\Polaroid Editor
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
WizardStyle=modern
SetupIconFile=..\assets\polaroid-editor.ico
UninstallDisplayIcon={app}\PolaroidEditor.exe
OutputDir=..\dist
OutputBaseFilename=PolaroidEditor-Setup-{#AppVersion}
Compression=lzma2/fast
SolidCompression=yes
MinVersion=10.0.17763
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
AppMutex=Local\PolaroidEditor.Installed.Running
SetupMutex=Local\PolaroidEditor.Setup.Running
CloseApplications=no
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; Flags: unchecked

[Files]
Source: "..\dist\PolaroidEditor-Portable.exe"; DestDir: "{app}"; DestName: "PolaroidEditor.exe"; Flags: ignoreversion
Source: "..\assets\installed.marker"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\Polaroid Editor"; Filename: "{app}\PolaroidEditor.exe"
Name: "{userdesktop}\Polaroid Editor"; Filename: "{app}\PolaroidEditor.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\PolaroidEditor.exe"; Description: "Abrir o Polaroid Editor"; Flags: nowait postinstall skipifsilent

[Code]
function OpenProcess(Access: LongWord; InheritHandle: Boolean; ProcessId: LongWord): THandle;
external 'OpenProcess@kernel32.dll stdcall';
function WaitForSingleObject(Handle: THandle; Milliseconds: LongWord): LongWord;
external 'WaitForSingleObject@kernel32.dll stdcall';
function CloseHandle(Handle: THandle): Boolean;
external 'CloseHandle@kernel32.dll stdcall';

function InitializeSetup(): Boolean;
var
  ProcessId: Integer;
  Handle: THandle;
begin
  Result := True;
  ProcessId := StrToIntDef(ExpandConstant('{param:WAITPID|0}'), 0);
  if ProcessId > 0 then
  begin
    Handle := OpenProcess($00100000, False, ProcessId);
    if Handle <> 0 then
    begin
      Result := WaitForSingleObject(Handle, 120000) = 0;
      CloseHandle(Handle);
      Sleep(1000);
    end;
  end;
end;
