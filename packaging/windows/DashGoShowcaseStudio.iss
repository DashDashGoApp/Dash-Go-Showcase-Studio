; Dash-Go Showcase Studio Windows installer.
; Requires Inno Setup 7.0.1 or later, 64-bit compiler edition.
; The Builder supplies StageDir, StudioVersion, ReleasePackageVersion, and OutputDir. This file never
; packages a developer workspace or a mutable Studio state directory.
; SmokeTest builds use an isolated AppId, exact Builder-owned install/state
; directories, and a distinct cleanup contract so they cannot touch a normal
; Studio installation or its private state.
#ifndef StageDir
  #error StageDir must be supplied by the Builder.
#endif
#ifndef StudioVersion
  #error StudioVersion must be supplied by the Builder.
#endif
#ifndef ReleasePackageVersion
  #error ReleasePackageVersion must be supplied by the Builder.
#endif
#ifndef OutputDir
  #error OutputDir must be supplied by the Builder.
#endif
#ifndef VersionInfoVersion
  #error VersionInfoVersion must be supplied by the Builder.
#endif

#define StudioName "Dash-Go Showcase Studio"
#define StudioExe "dash-go-showcase-studio.exe"
#define ProductionAppId "{{B3D7564E-3C14-4B78-98B1-4C9F1865A021}}"
#define SmokeAppId "{{B3D7564E-3C14-4B78-98B1-4C9F1865A022}}"

#ifdef SmokeTest
  #define SmokeDefaultDir GetEnv("DASHGO_STUDIO_SMOKE_DEFAULT_DIR")
  #define SmokeStateRoot GetEnv("DASHGO_STUDIO_SMOKE_STATE_ROOT")
  #if SmokeDefaultDir == ""
    #error DASHGO_STUDIO_SMOKE_DEFAULT_DIR must be supplied for a SmokeTest build.
  #endif
  #if SmokeStateRoot == ""
    #error DASHGO_STUDIO_SMOKE_STATE_ROOT must be supplied for a SmokeTest build.
  #endif
#endif

[Setup]
#ifdef SmokeTest
AppId={#SmokeAppId}
DefaultDirName={#SmokeDefaultDir}
UsePreviousAppDir=no
#else
AppId={#ProductionAppId}
DefaultDirName={localappdata}\Programs\Dash-Go Showcase Studio
#endif
AppName={#StudioName}
AppVersion={#ReleasePackageVersion}
AppVerName={#StudioName} for Dash-Go {#ReleasePackageVersion}
AppPublisher=DashDashGoApp
AppPublisherURL=https://github.com/DashDashGoApp
AppSupportURL=https://github.com/DashDashGoApp/Dash-Go-Showcase-Studio/issues
AppUpdatesURL=https://github.com/DashDashGoApp/Dash-Go-Showcase-Studio/releases
DefaultGroupName=Dash-Go Showcase Studio
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#OutputDir}
OutputBaseFilename=Dash-Go_Showcase_Studio_{#ReleasePackageVersion}_Windows_Setup
Compression=lzma2/max
SolidCompression=no
VersionInfoCompany=DashDashGoApp
VersionInfoDescription=Dash-Go Showcase Studio Installer
VersionInfoVersion={#VersionInfoVersion}
VersionInfoTextVersion={#ReleasePackageVersion}
VersionInfoProductName={#StudioName}
VersionInfoProductVersion={#VersionInfoVersion}
VersionInfoProductTextVersion={#ReleasePackageVersion}
VersionInfoOriginalFileName=Dash-Go_Showcase_Studio_{#ReleasePackageVersion}_Windows_Setup.exe
VersionInfoCopyright=Copyright (C) 2026 DashDashGoApp
WizardStyle=modern
SetupIconFile={#StageDir}\assets\branding\dash-go-showcase-studio.ico
UninstallDisplayIcon={app}\assets\branding\dash-go-showcase-studio.ico
SetupArchitecture=x64
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName=Dash-Go Showcase Studio
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: desktopicon; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
; The public Windows payload is an explicit allowlist. Never package the entire stage tree.
Source: "{#StageDir}\dash-go-showcase-studio.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#StageDir}\dash-go-showcase-studio.exe.manifest"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#StageDir}\STUDIO_RUNTIME.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#StageDir}\INSTALLER_CONTENTS.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#StageDir}\NOTICE.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#StageDir}\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#StageDir}\DASH-GO-THIRD-PARTY-NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#StageDir}\WHAT-STUDIO-DOES-LOCALLY.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#StageDir}\assets\branding\dash-go-showcase-studio.ico"; DestDir: "{app}\assets\branding"; Flags: ignoreversion
Source: "{#StageDir}\runtime\app\VERSION"; DestDir: "{app}\runtime\app"; Flags: ignoreversion
Source: "{#StageDir}\runtime\app\index.html"; DestDir: "{app}\runtime\app"; Flags: ignoreversion
Source: "{#StageDir}\runtime\app\themes.list"; DestDir: "{app}\runtime\app"; Flags: ignoreversion
Source: "{#StageDir}\runtime\app\bin\dash-go-showcase-server.exe"; DestDir: "{app}\runtime\app\bin"; Flags: ignoreversion
Source: "{#StageDir}\runtime\app\bin\dash-go-showcase-server.exe.manifest"; DestDir: "{app}\runtime\app\bin"; Flags: ignoreversion
Source: "{#StageDir}\runtime\app\base\*"; DestDir: "{app}\runtime\app\base"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#StageDir}\runtime\app\release\*"; DestDir: "{app}\runtime\app\release"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#StageDir}\runtime\app\ui\*"; DestDir: "{app}\runtime\app\ui"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Dash-Go Showcase Studio"; Filename: "{app}\{#StudioExe}"; WorkingDir: "{app}"; IconFilename: "{app}\assets\branding\dash-go-showcase-studio.ico"; Comment: "Explore Dash-Go with safe local showcase data"
Name: "{autodesktop}\Dash-Go Showcase Studio"; Filename: "{app}\{#StudioExe}"; WorkingDir: "{app}"; IconFilename: "{app}\assets\branding\dash-go-showcase-studio.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#StudioExe}"; Description: "Launch Dash-Go Showcase Studio"; Flags: nowait postinstall skipifsilent

[UninstallRun]
#ifdef SmokeTest
Filename: "{app}\{#StudioExe}"; Parameters: "--action purge --state-root ""{#SmokeStateRoot}"" --confirm-purge ""PURGE SHOWCASE STUDIO"""; Flags: runhidden waituntilterminated skipifdoesntexist; RunOnceId: "DashGoShowcaseStudioSmokePurge"
#else
Filename: "{app}\{#StudioExe}"; Parameters: "--action purge"; Flags: runhidden waituntilterminated skipifdoesntexist; RunOnceId: "DashGoShowcaseStudioPurge"
#endif

[UninstallDelete]
#ifndef SmokeTest
; The host purge removes only this exact private Studio root. This Inno fallback
; covers a missing or corrupt host without traversing an arbitrary user path.
Type: filesandordirs; Name: "{localappdata}\Dash-Go Showcase Studio"
#endif
