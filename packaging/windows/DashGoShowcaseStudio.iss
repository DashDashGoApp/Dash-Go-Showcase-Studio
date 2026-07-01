; Dash-Go Showcase Studio Windows installer.
; Requires Inno Setup 7.0.1 or later, 64-bit compiler edition.
; The Builder supplies StageDir, StudioVersion, and OutputDir. This file never
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
#ifndef OutputDir
  #error OutputDir must be supplied by the Builder.
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
AppVersion={#StudioVersion}
AppPublisher=DashDashGoApp
AppPublisherURL=https://github.com/DashDashGoApp
DefaultGroupName=Dash-Go Showcase Studio
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir={#OutputDir}
OutputBaseFilename=Dash-Go_Showcase_Studio_{#StudioVersion}_Windows_Setup
Compression=lzma2/ultra64
SolidCompression=yes
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
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Dash-Go Showcase Studio"; Filename: "{app}\{#StudioExe}"; WorkingDir: "{app}"; IconFilename: "{app}\assets\branding\dash-go-showcase-studio.ico"; Comment: "Explore Dash-Go with safe local showcase data"
Name: "{autodesktop}\Dash-Go Showcase Studio"; Filename: "{app}\{#StudioExe}"; WorkingDir: "{app}"; IconFilename: "{app}\assets\branding\dash-go-showcase-studio.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#StudioExe}"; Description: "Launch Dash-Go Showcase Studio"; Flags: nowait postinstall skipifsilent

[UninstallRun]
#ifdef SmokeTest
Filename: "{app}\{#StudioExe}"; Parameters: "--action purge --state-root ""{#SmokeStateRoot}"" --confirm-purge ""PURGE SHOWCASE STUDIO"""; Flags: runhidden waituntilterminated skipifdoesntexist
#else
Filename: "{app}\{#StudioExe}"; Parameters: "--action purge"; Flags: runhidden waituntilterminated skipifdoesntexist
#endif

[UninstallDelete]
#ifndef SmokeTest
; The host purge removes only this exact private Studio root. This Inno fallback
; covers a missing or corrupt host without traversing an arbitrary user path.
Type: filesandordirs; Name: "{localappdata}\Dash-Go Showcase Studio"
#endif
