#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
[Setup]
AppId={{AAE0E3E8-B729-46AE-B534-2E04C256A5C1}
AppName=Instante
AppVersion={#AppVersion}
AppPublisher=RedLab
AppPublisherURL=https://github.com/redlab-coder/instante
AppSupportURL=https://github.com/redlab-coder/instante/issues
AppUpdatesURL=https://github.com/redlab-coder/instante/releases
DefaultDirName={localappdata}\Programs\Instante
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
WizardStyle=modern
SetupIconFile=..\assets\instante.ico
UninstallDisplayIcon={app}\Instante.exe
OutputDir=..\dist
OutputBaseFilename=Instante-Setup-{#AppVersion}
Compression=lzma2/fast
SolidCompression=yes
MinVersion=10.0.17763
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
AppMutex=Local\Instante.Installed.Running
SetupMutex=Local\Instante.Setup.Running
CloseApplications=no
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; Flags: unchecked

[Files]
Source: "..\dist\Instante-Portable.exe"; DestDir: "{app}"; DestName: "Instante.exe"; Flags: ignoreversion
Source: "..\assets\installed.marker"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\Instante"; Filename: "{app}\Instante.exe"
Name: "{userdesktop}\Instante"; Filename: "{app}\Instante.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Instante.exe"; Description: "Abrir o Instante"; Flags: nowait postinstall skipifsilent

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
