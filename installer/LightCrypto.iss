; LightCrypto Installer Script for Inno Setup
; Creates a Windows installer with all dependencies

#define AppName "LightCrypto"
#define AppVersion "2.0.0"
#define AppPublisher "LightCrypto Project"
#define AppURL "https://github.com/yourusername/LightCrypto"
#define AppExeName "LightCrypto.exe"
#define AppId "{{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}"

[Setup]
; Basic information
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
LicenseFile=
OutputDir=..\dist
OutputBaseFilename=LightCrypto_Setup
SetupIconFile=
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
DisableProgramGroupPage=yes

; UI
WizardImageFile=
WizardSmallImageFile=

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
; PyInstaller bundle (main application)
; Включаем все файлы из PyInstaller bundle (Python runtime, PyQt6, и т.д.)
Source: "..\dist\LightCrypto\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; C++ executables and libraries (from staging/bin)
; Копируем в bin/ подпапку, чтобы приложение могло их найти
Source: "staging\bin\*.exe"; DestDir: "{app}\bin"; Flags: ignoreversion
Source: "staging\bin\*.dll"; DestDir: "{app}\bin"; Flags: ignoreversion

; CipherKeys (CSV files)
; Копируем CSV файлы в корень приложения (CipherKeys/)
Source: "staging\CipherKeys\*.csv"; DestDir: "{app}\CipherKeys"; Flags: ignoreversion

; Note: PyInstaller bundle уже содержит:
; - Python runtime (встроенный)
; - PyQt6 и все зависимости
; - GUI код (gui_qt/)
; - CipherKeys/ (если были включены в spec)

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// Custom code for checking dependencies and handling installation

function InitializeSetup(): Boolean;
begin
  Result := True;
  
  // Check if Visual C++ Redistributable is installed
  // This is optional - the app might work without it if libsodium.dll is statically linked
  // Uncomment if you want to check for VC++ Redistributable:
  {
  if not RegKeyExists(HKEY_LOCAL_MACHINE, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64') then
  begin
    if MsgBox('Visual C++ Redistributable не найден. Продолжить установку?', mbConfirmation, MB_YESNO) = IDNO then
      Result := False;
  end;
  }
end;

function InitializeUninstall(): Boolean;
begin
  Result := True;
end;

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

