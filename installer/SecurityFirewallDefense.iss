; Inno Setup script for aThemeArt Security Firewall Defense
; Requires Inno Setup 6.x
;
; Developed by: aThemeArt
; Website: https://athemeart.com
; Author: Saiful Islam

#define MyAppName "Security Firewall Defense"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "aThemeArt"
#define MyAppURL "https://athemeart.com"
#define MyAppExeName "SecurityFirewallDefense.exe"
#define MyAppAuthor "Saiful Islam"

[Setup]
AppId={{A7F3C2E1-9B4D-4E8A-9C1F-5D6E7A8B9C0D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}

AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

DefaultDirName={autopf}\{#MyAppPublisher}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes

OutputDir=output
OutputBaseFilename=SecurityFirewallDefense_Setup_{#MyAppVersion}

Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

UninstallDisplayIcon={app}\{#MyAppExeName}

VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} - Windows Firewall & Anti-RAT Hardening
VersionInfoCopyright=Copyright (C) 2024-2026 {#MyAppPublisher}. Author: {#MyAppAuthor}
VersionInfoProductName={#MyAppName}

DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; \
    Description: "{cm:CreateDesktopIcon}"; \
    GroupDescription: "{cm:AdditionalIcons}"; \
    Flags: unchecked

[Files]

; Main executable built by PyInstaller
Source: "..\dist\{#MyAppExeName}"; \
    DestDir: "{app}"; \
    Flags: ignoreversion

; Original PowerShell firewall script
Source: "..\scripts\Security-Firewall-Defense.ps1"; \
    DestDir: "{app}\scripts"; \
    Flags: ignoreversion

[Icons]

; Start Menu
Name: "{group}\{#MyAppName}"; \
    Filename: "{app}\{#MyAppExeName}"

; Uninstaller
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; \
    Filename: "{uninstallexe}"

; Desktop shortcut
Name: "{autodesktop}\{#MyAppName}"; \
    Filename: "{app}\{#MyAppExeName}"; \
    Tasks: desktopicon

[Run]

; Launch application after installation
Filename: "{app}\{#MyAppExeName}"; \
    Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; \
    Flags: nowait postinstall skipifsilent runascurrentuser

[Code]

function InitializeSetup(): Boolean;
begin
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    ForceDirectories(ExpandConstant('{app}\data'));
  end;
end;