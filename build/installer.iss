; Inno Setup skripta: pravi PrelomKnjige-instaler.exe iz dist\PrelomKnjige
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{6B1E4D2A-7C3F-4E8B-9A51-2F0D8C7E4B19}
AppName=Prelom knjige
AppVersion={#AppVersion}
AppPublisher=Prelom knjige
DefaultDirName={autopf}\Prelom knjige
DefaultGroupName=Prelom knjige
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=PrelomKnjige-instaler-{#AppVersion}
SetupIconFile=ikona.ico
UninstallDisplayIcon={app}\PrelomKnjige.exe
; program otvoren -> instaler traži da se zatvori; CloseApplications ga zatvara sam
AppMutex=PrelomKnjigeMutex
CloseApplications=force
CloseApplicationsFilter=*.exe,*.dll,*.pyd
RestartApplications=no
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "sr"; MessagesFile: "SerbianLatin.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\PrelomKnjige\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Prelom knjige"; Filename: "{app}\PrelomKnjige.exe"
Name: "{group}\{cm:UninstallProgram,Prelom knjige}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Prelom knjige"; Filename: "{app}\PrelomKnjige.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\PrelomKnjige.exe"; Description: "{cm:LaunchProgram,Prelom knjige}"; Flags: nowait postinstall skipifsilent

[Code]
// Ako je stari program ostao u pozadini (bez prozora), ugasi ga pre kopiranja datoteka.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM PrelomKnjige.exe', '', SW_HIDE,
       ewWaitUntilTerminated, ResultCode);
  Sleep(500);
  Result := '';
end;

function InitializeUninstall(): Boolean;
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM PrelomKnjige.exe', '', SW_HIDE,
       ewWaitUntilTerminated, ResultCode);
  Result := True;
end;
