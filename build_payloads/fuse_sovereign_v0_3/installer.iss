#define MyAppName "FUSE Sovereign Platform"
#define MyAppVersion "0.3.0"
#define MyAppPublisher "FUSE"
#define MyAppExeName "FUSE-Sovereign-Platform.exe"

[Setup]
AppId={{D6827192-2FE4-49D9-A9D7-50A7AE19B71B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\FUSE\SovereignPlatform
DefaultGroupName=FUSE
OutputDir=installer-dist
OutputBaseFilename=FUSE-Sovereign-Platform-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
WizardStyle=modern

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
