[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string] $StageDir,
    [Parameter(Mandatory)] [string] $IsccPath,
    [Parameter(Mandatory)] [string] $OutputDir,
    [Parameter(Mandatory)] [string] $DiagnosticsDir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Resolve-RequiredDirectory {
    param([Parameter(Mandatory)] [string] $Path, [Parameter(Mandatory)] [string] $Label)

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "$Label directory is missing: $Path"
    }

    return (Resolve-Path -LiteralPath $Path).Path
}

function Resolve-RequiredFile {
    param([Parameter(Mandatory)] [string] $Path, [Parameter(Mandatory)] [string] $Label)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label file is missing: $Path"
    }

    return (Resolve-Path -LiteralPath $Path).Path
}

function Invoke-CheckedExternal {
    param(
        [Parameter(Mandatory)] [string] $FilePath,
        [Parameter(Mandatory)] [string[]] $ArgumentList,
        [Parameter(Mandatory)] [string] $Label
    )

    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE."
    }
}

function Require-ExactlyOneFile {
    param(
        [Parameter(Mandatory)] [System.IO.FileInfo[]] $Candidates,
        [Parameter(Mandatory)] [string] $Label
    )

    if ($Candidates.Count -ne 1) {
        throw "Expected exactly one $Label; found $($Candidates.Count)."
    }

    return $Candidates[0]
}

$StageDir = Resolve-RequiredDirectory -Path $StageDir -Label 'Windows staging payload'
$OutputDir = [System.IO.Path]::GetFullPath($OutputDir)
$DiagnosticsDir = [System.IO.Path]::GetFullPath($DiagnosticsDir)
$IsccPath = Resolve-RequiredFile -Path $IsccPath -Label 'Inno Setup compiler'
$InstallerScript = Resolve-RequiredFile -Path (Join-Path $PSScriptRoot '..\packaging\windows\DashGoShowcaseStudio.iss') -Label 'Inno Setup script'

if ($StageDir -match '\s' -or $OutputDir -match '\s' -or $DiagnosticsDir -match '\s') {
    throw 'Windows staging, output, and diagnostics paths must not contain spaces for the Inno Setup define contract.'
}

Remove-Item -LiteralPath $OutputDir -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $OutputDir, $DiagnosticsDir -Force | Out-Null

$Manifest = Require-ExactlyOneFile `
    -Candidates @(Get-ChildItem -LiteralPath $StageDir -Filter 'studio.manifest.json' -File -Recurse) `
    -Label 'staged studio.manifest.json'

$ManifestObject = Get-Content -LiteralPath $Manifest.FullName -Raw | ConvertFrom-Json
$StudioVersion = [string]$ManifestObject.studioVersion
if ($StudioVersion -notmatch '^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$') {
    throw "Staged Studio version is invalid: '$StudioVersion'."
}

$StudioExe = Require-ExactlyOneFile `
    -Candidates @(Get-ChildItem -LiteralPath $StageDir -Filter 'dash-go-showcase-studio.exe' -File -Recurse) `
    -Label 'staged Windows Studio executable'

$RequiredStageFiles = @(
    'assets\branding\dash-go-showcase-studio.ico',
    'assets\branding\dash-go-showcase-studio.svg',
    'assets\branding\linux\hicolor\scalable\apps\dash-go-showcase-studio.svg'
)

foreach ($RelativePath in $RequiredStageFiles) {
    $Candidate = Join-Path $StageDir $RelativePath
    if (-not (Test-Path -LiteralPath $Candidate -PathType Leaf)) {
        throw "Windows staging payload lacks required branding asset: $RelativePath"
    }
}

$NormalInstallerArgs = @(
    "/DStageDir=$StageDir",
    "/DStudioVersion=$StudioVersion",
    "/DOutputDir=$OutputDir",
    $InstallerScript
)
Invoke-CheckedExternal -FilePath $IsccPath -ArgumentList $NormalInstallerArgs -Label 'Production Inno Setup compilation'

$InstallerName = "Dash-Go_Showcase_Studio_${StudioVersion}_Windows_Setup.exe"
$InstallerPath = Join-Path $OutputDir $InstallerName
$InstallerPath = Resolve-RequiredFile -Path $InstallerPath -Label 'Windows installer candidate'

$SmokeRoot = Join-Path $DiagnosticsDir 'isolated-smoke'
$SmokeInstallRoot = Join-Path $SmokeRoot 'install'
$SmokeStateRoot = Join-Path $SmokeRoot 'state'
$SmokeOutputRoot = Join-Path $SmokeRoot 'installer'
New-Item -ItemType Directory -Path $SmokeRoot, $SmokeOutputRoot -Force | Out-Null

$env:DASHGO_STUDIO_SMOKE_DEFAULT_DIR = $SmokeInstallRoot
$env:DASHGO_STUDIO_SMOKE_STATE_ROOT = $SmokeStateRoot

$SmokeInstallerArgs = @(
    "/DStageDir=$StageDir",
    "/DStudioVersion=$StudioVersion",
    "/DOutputDir=$SmokeOutputRoot",
    '/DSmokeTest=1',
    $InstallerScript
)
Invoke-CheckedExternal -FilePath $IsccPath -ArgumentList $SmokeInstallerArgs -Label 'Smoke-test Inno Setup compilation'

$SmokeInstaller = Resolve-RequiredFile -Path (Join-Path $SmokeOutputRoot $InstallerName) -Label 'Smoke-test installer'

$InstallProcess = Start-Process `
    -FilePath $SmokeInstaller `
    -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-') `
    -Wait `
    -PassThru
if ($InstallProcess.ExitCode -ne 0) {
    throw "Smoke-test installer failed with exit code $($InstallProcess.ExitCode)."
}

$InstalledExe = Resolve-RequiredFile -Path (Join-Path $SmokeInstallRoot 'dash-go-showcase-studio.exe') -Label 'installed Studio executable'
$InstalledIcon = Resolve-RequiredFile -Path (Join-Path $SmokeInstallRoot 'assets\branding\dash-go-showcase-studio.ico') -Label 'installed Studio icon'

$SelfTestLog = Join-Path $DiagnosticsDir 'installed-self-test.log'
& $InstalledExe `
    --action self-test `
    --state-root $SmokeStateRoot `
    --confirm-purge 'PURGE SHOWCASE STUDIO' `
    --no-browser `
    --trace *>&1 | Tee-Object -LiteralPath $SelfTestLog
if ($LASTEXITCODE -ne 0) {
    throw "Installed Studio self-test failed with exit code $LASTEXITCODE."
}

$Uninstaller = Require-ExactlyOneFile `
    -Candidates @(Get-ChildItem -LiteralPath $SmokeInstallRoot -Filter 'unins*.exe' -File) `
    -Label 'installed Studio uninstaller'

$UninstallProcess = Start-Process `
    -FilePath $Uninstaller.FullName `
    -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART') `
    -Wait `
    -PassThru
if ($UninstallProcess.ExitCode -ne 0) {
    throw "Smoke-test uninstaller failed with exit code $($UninstallProcess.ExitCode)."
}

if (Test-Path -LiteralPath $SmokeStateRoot) {
    throw "Smoke-test state root still exists after uninstall: $SmokeStateRoot"
}

if (Test-Path -LiteralPath (Join-Path $SmokeInstallRoot 'dash-go-showcase-studio.exe')) {
    throw "Installed Studio executable still exists after uninstall: $SmokeInstallRoot"
}

[pscustomobject]@{
    schema = 1
    result = 'PASS'
    studioVersion = $StudioVersion
    stageExecutable = $StudioExe.FullName
    installer = [System.IO.Path]::GetFileName($InstallerPath)
    installerSha256 = (Get-FileHash -LiteralPath $InstallerPath -Algorithm SHA256).Hash.ToLowerInvariant()
    smokeInstallRoot = $SmokeInstallRoot
    smokeStateRoot = $SmokeStateRoot
    installedIcon = $InstalledIcon.FullName
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $DiagnosticsDir 'windows-package-summary.json') -Encoding utf8

Write-Host "PASS: Windows installer candidate: $InstallerPath"
Write-Host 'PASS: isolated install, self-test, and uninstall smoke completed.'
