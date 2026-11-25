#define AppName "Campos Defenser"
#define AppVersion "1.1.0"
#define AppPublisher "Campos Tecnologia"
#define AppExeName "CamposDefenser.exe"

[Setup]
AppId={{A63F03CB-D721-4EEA-9C46-7DFE3D7C8B2E}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\Campos Defenser
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\logo.ico
SetupIconFile=dist\logo.ico
OutputDir=site-campos-defenser
OutputBaseFilename=Setup
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
Source: "dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\logo.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "cloud_config.json"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\logo.ico"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\logo.ico"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Iniciar Campos Defenser"; Flags: postinstall nowait skipifsilent
