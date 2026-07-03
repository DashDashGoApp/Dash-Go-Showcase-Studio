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

function Invoke-CheckedProcess {
    param(
        [Parameter(Mandatory)] [string] $FilePath,
        [Parameter(Mandatory)] [string[]] $ArgumentList,
        [Parameter(Mandatory)] [string] $Label,
        [Parameter(Mandatory)] [ValidateRange(1, 3600)] [int] $TimeoutSeconds,
        [Parameter(Mandatory)] [string] $DiagnosticsPath,
        [string] $StandardOutputPath = '',
        [string] $StandardErrorPath = ''
    )

    $startParameters = @{
        FilePath = $FilePath
        ArgumentList = $ArgumentList
        PassThru = $true
    }
    if (-not [string]::IsNullOrWhiteSpace($StandardOutputPath)) {
        $startParameters.RedirectStandardOutput = $StandardOutputPath
    }
    if (-not [string]::IsNullOrWhiteSpace($StandardErrorPath)) {
        $startParameters.RedirectStandardError = $StandardErrorPath
    }

    $startedAtUtc = [DateTime]::UtcNow
    $process = Start-Process @startParameters
    $completed = $process.WaitForExit($TimeoutSeconds * 1000)
    $timedOut = -not $completed
    $terminated = $false

    if ($timedOut) {
        $taskKill = Join-Path $env:SystemRoot 'System32\taskkill.exe'
        if (Test-Path -LiteralPath $taskKill -PathType Leaf) {
            & $taskKill /PID $process.Id /T /F | Out-Null
            $terminated = $LASTEXITCODE -eq 0
        }
        else {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            $terminated = $true
        }
        $null = $process.WaitForExit(15000)
    }

    $finishedAtUtc = [DateTime]::UtcNow
    $exitCode = $null
    if ($process.HasExited) {
        $exitCode = $process.ExitCode
    }

    [pscustomobject]@{
        schema = 1
        label = $Label
        filePath = $FilePath
        arguments = @($ArgumentList)
        processID = $process.Id
        startedAtUtc = $startedAtUtc.ToString('o')
        finishedAtUtc = $finishedAtUtc.ToString('o')
        timeoutSeconds = $TimeoutSeconds
        timedOut = $timedOut
        terminationRequested = $terminated
        exitCode = $exitCode
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $DiagnosticsPath -Encoding utf8

    if ($timedOut) {
        throw "${Label} exceeded its ${TimeoutSeconds}-second limit. The process tree was stopped; inspect $(Split-Path -Leaf $DiagnosticsPath) and its matching log."
    }
    if ($exitCode -ne 0) {
        throw "${Label} failed with exit code $exitCode. Inspect $(Split-Path -Leaf $DiagnosticsPath)."
    }
}
function Require-ExactlyOneFile {
    param(
        [Parameter(Mandatory)] [AllowEmptyCollection()] [System.IO.FileInfo[]] $Candidates,
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

$RuntimeMetadata = Resolve-RequiredFile `
    -Path (Join-Path $StageDir 'STUDIO_RUNTIME.json') `
    -Label 'staged Studio runtime metadata'

$RuntimeObject = Get-Content -LiteralPath $RuntimeMetadata -Raw | ConvertFrom-Json
$StudioVersion = [string]$RuntimeObject.studioVersion
if ($StudioVersion -notmatch '^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$') {
    throw "Staged Studio runtime version is invalid: '$StudioVersion'."
}

$ReleasePackageVersion = [string]$RuntimeObject.releasePackageVersion
if ($ReleasePackageVersion -notmatch '^[0-9]+\.[0-9]+\.[0-9]+(?:-(?:test\.[0-9]+|r[1-9][0-9]*))?$') {
    throw "Staged release package version is invalid: '$ReleasePackageVersion'."
}

$RuntimePlatform = [string]$RuntimeObject.platform
if ($RuntimePlatform -ne 'windows-amd64') {
    throw "Staged Studio runtime platform is invalid: '$RuntimePlatform'."
}

$StudioExe = Require-ExactlyOneFile `
    -Candidates @(Get-ChildItem -LiteralPath $StageDir -Filter 'dash-go-showcase-studio.exe' -File -Recurse) `
    -Label 'staged Windows Studio executable'

$RequiredStageFiles = @(
    'assets\branding\dash-go-showcase-studio.ico'
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
    "/DReleasePackageVersion=$ReleasePackageVersion",
    "/DOutputDir=$OutputDir",
    $InstallerScript
)
Invoke-CheckedExternal -FilePath $IsccPath -ArgumentList $NormalInstallerArgs -Label 'Production Inno Setup compilation'

$InstallerName = "Dash-Go_Showcase_Studio_${ReleasePackageVersion}_Windows_Setup.exe"
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
    "/DReleasePackageVersion=$ReleasePackageVersion",
    "/DOutputDir=$SmokeOutputRoot",
    '/DSmokeTest=1',
    $InstallerScript
)
Invoke-CheckedExternal -FilePath $IsccPath -ArgumentList $SmokeInstallerArgs -Label 'Smoke-test Inno Setup compilation'

$SmokeInstaller = Resolve-RequiredFile -Path (Join-Path $SmokeOutputRoot $InstallerName) -Label 'Smoke-test installer'

$SmokeInstallerLog = Join-Path $DiagnosticsDir 'smoke-installer.log'
$SmokeInstallerProcess = Join-Path $DiagnosticsDir 'smoke-installer-process.json'
Invoke-CheckedProcess `
    -FilePath $SmokeInstaller `
    -ArgumentList @(
        '/VERYSILENT',
        '/SUPPRESSMSGBOXES',
        '/NORESTART',
        '/SP-',
        '/NOCLOSEAPPLICATIONS',
        '/NORESTARTAPPLICATIONS',
        ("/LOG={0}" -f $SmokeInstallerLog)
    ) `
    -Label 'Smoke-test installer' `
    -TimeoutSeconds 300 `
    -DiagnosticsPath $SmokeInstallerProcess

$InstalledExe = Resolve-RequiredFile -Path (Join-Path $SmokeInstallRoot 'dash-go-showcase-studio.exe') -Label 'installed Studio executable'
$InstalledIcon = Resolve-RequiredFile -Path (Join-Path $SmokeInstallRoot 'assets\branding\dash-go-showcase-studio.ico') -Label 'installed Studio icon'

$SelfTestLog = Join-Path $DiagnosticsDir 'installed-self-test.log'
$SelfTestErrorLog = Join-Path $DiagnosticsDir 'installed-self-test.stderr.log'
$SelfTestProcess = Join-Path $DiagnosticsDir 'installed-self-test-process.json'
Invoke-CheckedProcess `
    -FilePath $InstalledExe `
    -ArgumentList @(
        '--action',
        'self-test',
        '--state-root',
        $SmokeStateRoot,
        '--confirm-purge',
        '"PURGE SHOWCASE STUDIO"',
        '--no-browser',
        '--trace'
    ) `
    -Label 'Installed Studio self-test' `
    -TimeoutSeconds 300 `
    -DiagnosticsPath $SelfTestProcess `
    -StandardOutputPath $SelfTestLog `
    -StandardErrorPath $SelfTestErrorLog

$Uninstaller = Require-ExactlyOneFile `
    -Candidates @(Get-ChildItem -LiteralPath $SmokeInstallRoot -Filter 'unins*.exe' -File) `
    -Label 'installed Studio uninstaller'

$SmokeUninstallerLog = Join-Path $DiagnosticsDir 'smoke-uninstaller.log'
$SmokeUninstallerProcess = Join-Path $DiagnosticsDir 'smoke-uninstaller-process.json'
Invoke-CheckedProcess `
    -FilePath $Uninstaller.FullName `
    -ArgumentList @(
        '/VERYSILENT',
        '/SUPPRESSMSGBOXES',
        '/NORESTART',
        ("/LOG={0}" -f $SmokeUninstallerLog)
    ) `
    -Label 'Smoke-test uninstaller' `
    -TimeoutSeconds 180 `
    -DiagnosticsPath $SmokeUninstallerProcess

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
    releasePackageVersion = $ReleasePackageVersion
    stageExecutable = $StudioExe.FullName
    installer = [System.IO.Path]::GetFileName($InstallerPath)
    installerSha256 = (Get-FileHash -LiteralPath $InstallerPath -Algorithm SHA256).Hash.ToLowerInvariant()
    smokeInstallRoot = $SmokeInstallRoot
    smokeStateRoot = $SmokeStateRoot
    installedIcon = [System.IO.Path]::GetFileName($InstalledIcon)
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $DiagnosticsDir 'windows-package-summary.json') -Encoding utf8

Write-Host "PASS: Windows installer candidate: $InstallerPath"
Write-Host 'PASS: isolated install, self-test, and uninstall smoke completed.'
