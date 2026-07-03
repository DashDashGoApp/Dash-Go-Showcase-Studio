[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string] $StageDir,
    [Parameter(Mandatory)] [string] $IsccPath,
    [Parameter(Mandatory)] [string] $OutputDir,
    [Parameter(Mandatory)] [string] $DiagnosticsDir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:PayloadLayout = 'windows-curated-v1'
$script:PayloadManifestName = 'INSTALLER_CONTENTS.json'
$script:CuratedExactFiles = @(
    'dash-go-showcase-studio.exe',
    'dash-go-showcase-studio.exe.manifest',
    'STUDIO_RUNTIME.json',
    'INSTALLER_CONTENTS.json',
    'NOTICE.md',
    'LICENSE',
    'DASH-GO-THIRD-PARTY-NOTICES.md',
    'WHAT-STUDIO-DOES-LOCALLY.txt',
    'assets/branding/dash-go-showcase-studio.ico',
    'runtime/app/VERSION',
    'runtime/app/index.html',
    'runtime/app/themes.list',
    'runtime/app/bin/dash-go-showcase-server.exe',
    'runtime/app/bin/dash-go-showcase-server.exe.manifest'
)
$script:CuratedTreePrefixes = @(
    'runtime/app/base/',
    'runtime/app/release/',
    'runtime/app/ui/'
)

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

function ConvertTo-NormalizedRelativePath {
    param(
        [Parameter(Mandatory)] [string] $Root,
        [Parameter(Mandatory)] [string] $FullName
    )

    $relative = [System.IO.Path]::GetRelativePath($Root, $FullName).Replace('\', '/')
    if ([string]::IsNullOrWhiteSpace($relative) -or $relative -eq '.' -or
        $relative.StartsWith('../', [StringComparison]::Ordinal) -or
        $relative.Contains('/../', [StringComparison]::Ordinal) -or
        [System.IO.Path]::IsPathRooted($relative)) {
        throw "Payload file resolves outside its expected root: $FullName"
    }

    return $relative
}

function Get-FileInventory {
    param(
        [Parameter(Mandatory)] [string] $Root,
        [string[]] $ExcludeRelativePaths = @()
    )

    $excluded = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($relative in $ExcludeRelativePaths) {
        $null = $excluded.Add($relative.Replace('\', '/'))
    }

    return @(
        Get-ChildItem -LiteralPath $Root -Recurse -File |
            ForEach-Object {
                $relative = ConvertTo-NormalizedRelativePath -Root $Root -FullName $_.FullName
                if (-not $excluded.Contains($relative)) {
                    [pscustomobject]@{
                        relativePath = $relative
                        sizeBytes = $_.Length
                        sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
                    }
                }
            } |
            Sort-Object -Property relativePath
    )
}

function Test-IsCuratedPayloadPath {
    param([Parameter(Mandatory)] [string] $RelativePath)

    if ($script:CuratedExactFiles -contains $RelativePath) {
        return $true
    }

    foreach ($prefix in $script:CuratedTreePrefixes) {
        if ($RelativePath.StartsWith($prefix, [StringComparison]::Ordinal)) {
            return $true
        }
    }

    return $false
}

function Get-WindowsCuratedPayload {
    param([Parameter(Mandatory)] [string] $Root)

    $manifestPath = Resolve-RequiredFile -Path (Join-Path $Root $script:PayloadManifestName) -Label 'curated Windows payload manifest'
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json

    if ([int]$manifest.schema -ne 1 -or
        [string]$manifest.payloadLayout -ne $script:PayloadLayout -or
        [string]$manifest.platform -ne 'windows-amd64' -or
        [bool]$manifest.selfExcluded -ne $true) {
        throw 'Curated Windows payload manifest header is invalid.'
    }

    $manifestFiles = @($manifest.files)
    if ($manifestFiles.Count -eq 0) {
        throw 'Curated Windows payload manifest contains no files.'
    }

    $actual = @(Get-FileInventory -Root $Root -ExcludeRelativePaths @($script:PayloadManifestName))
    $actualByPath = @{}
    foreach ($item in $actual) {
        if (-not (Test-IsCuratedPayloadPath -RelativePath $item.relativePath)) {
            throw "Windows staging payload contains an unapproved file: $($item.relativePath)"
        }
        $actualByPath[$item.relativePath] = $item
    }

    foreach ($required in $script:CuratedExactFiles) {
        if ($required -eq $script:PayloadManifestName) {
            continue
        }
        if (-not $actualByPath.ContainsKey($required)) {
            throw "Windows staging payload is missing required file: $required"
        }
    }

    foreach ($prefix in $script:CuratedTreePrefixes) {
        if (-not ($actual | Where-Object { $_.relativePath.StartsWith($prefix, [StringComparison]::Ordinal) })) {
            throw "Windows staging payload has an empty required tree: $prefix"
        }
    }

    $expectedExecutables = @(
        'dash-go-showcase-studio.exe',
        'runtime/app/bin/dash-go-showcase-server.exe'
    )
    $actualExecutables = @($actual | Where-Object { $_.relativePath.EndsWith('.exe', [StringComparison]::OrdinalIgnoreCase) } | ForEach-Object { $_.relativePath })
    if (($actualExecutables -join "`n") -ne ($expectedExecutables -join "`n")) {
        throw "Windows staging payload must contain exactly the approved executables. Found: $($actualExecutables -join ', ')"
    }

    foreach ($manifestName in @('dash-go-showcase-studio.exe.manifest', 'runtime/app/bin/dash-go-showcase-server.exe.manifest')) {
        $text = Get-Content -LiteralPath (Join-Path $Root $manifestName) -Raw
        if ($text -notmatch 'requestedExecutionLevel level="asInvoker" uiAccess="false"') {
            throw "Windows executable manifest is not explicit asInvoker/uiAccess=false: $manifestName"
        }
    }

    $seen = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach ($item in $manifestFiles) {
        $relative = [string]$item.path
        if ([string]::IsNullOrWhiteSpace($relative) -or $relative.Contains('\') -or
            $relative.StartsWith('/', [StringComparison]::Ordinal) -or
            $relative.StartsWith('../', [StringComparison]::Ordinal) -or
            $relative.Contains('/../', [StringComparison]::Ordinal) -or
            -not $seen.Add($relative)) {
            throw "Curated Windows payload manifest has an unsafe or duplicate path: $relative"
        }
        if (-not $actualByPath.ContainsKey($relative)) {
            throw "Curated Windows payload manifest names a missing stage file: $relative"
        }
        $actualItem = $actualByPath[$relative]
        if ([Int64]$item.sizeBytes -ne [Int64]$actualItem.sizeBytes -or
            [string]$item.sha256 -ne [string]$actualItem.sha256) {
            throw "Curated Windows payload manifest hash or size mismatch: $relative"
        }
    }

    if ($seen.Count -ne $actualByPath.Count) {
        throw 'Curated Windows payload manifest does not exactly describe the stage files.'
    }

    [pscustomobject]@{
        manifestPath = $manifestPath
        manifestSha256 = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
        manifest = $manifest
        fileCount = $actual.Count
        files = $actual
    }
}

function Get-InnoVersionInfoVersion {
    param([Parameter(Mandatory)] [string] $ReleasePackageVersion)

    $match = [regex]::Match($ReleasePackageVersion, '^(?<major>[0-9]+)\.(?<minor>[0-9]+)\.(?<patch>[0-9]+)(?:-(?:test\.|r)(?<revision>[0-9]+))?$')
    if (-not $match.Success) {
        throw "Could not derive a numeric Inno version from release package version '$ReleasePackageVersion'."
    }

    $revision = if ($match.Groups['revision'].Success) { $match.Groups['revision'].Value } else { '0' }
    return "$($match.Groups['major'].Value).$($match.Groups['minor'].Value).$($match.Groups['patch'].Value).$revision"
}

function Test-InstalledCuratedPayload {
    param(
        [Parameter(Mandatory)] [string] $InstallRoot,
        [Parameter(Mandatory)] $Payload
    )

    $installedManifestPath = Resolve-RequiredFile `
        -Path (Join-Path $InstallRoot $script:PayloadManifestName) `
        -Label 'installed curated Windows payload manifest'
    $installedManifestSha256 = (Get-FileHash -LiteralPath $installedManifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($installedManifestSha256 -ne [string]$Payload.manifestSha256) {
        throw 'Installed Studio payload manifest does not match the curated stage manifest.'
    }

    $allInstalled = @(Get-FileInventory -Root $InstallRoot)
    $installed = @(
        $allInstalled |
            Where-Object {
                $_.relativePath -notlike 'unins*.exe' -and
                $_.relativePath -notlike 'unins*.dat' -and
                $_.relativePath -notlike 'unins*.msg' -and
                $_.relativePath -ne $script:PayloadManifestName
            }
    )

    $expectedByPath = @{}
    foreach ($item in @($Payload.manifest.files)) {
        $expectedByPath[[string]$item.path] = $item
    }
    $installedByPath = @{}
    foreach ($item in $installed) {
        $installedByPath[$item.relativePath] = $item
    }

    if ($expectedByPath.Count -ne $installedByPath.Count) {
        throw "Installed Studio payload file count does not match the curated stage manifest. Expected $($expectedByPath.Count); found $($installedByPath.Count)."
    }

    foreach ($relative in $expectedByPath.Keys) {
        if (-not $installedByPath.ContainsKey($relative)) {
            throw "Installed Studio payload is missing manifest file: $relative"
        }
        $expected = $expectedByPath[$relative]
        $actual = $installedByPath[$relative]
        if ([Int64]$expected.sizeBytes -ne [Int64]$actual.sizeBytes -or
            [string]$expected.sha256 -ne [string]$actual.sha256) {
            throw "Installed Studio payload hash or size mismatch: $relative"
        }
    }

    return $installed.Count
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
if ([string]$RuntimeObject.payloadLayout -ne $script:PayloadLayout -or
    [string]$RuntimeObject.payloadManifest -ne $script:PayloadManifestName) {
    throw 'Staged Studio runtime metadata does not identify the curated Windows payload.'
}

$Payload = Get-WindowsCuratedPayload -Root $StageDir
$StudioExe = Require-ExactlyOneFile `
    -Candidates @(Get-ChildItem -LiteralPath $StageDir -Filter 'dash-go-showcase-studio.exe' -File -Recurse) `
    -Label 'staged Windows Studio executable'
$InstalledIcon = Resolve-RequiredFile -Path (Join-Path $StageDir 'assets\branding\dash-go-showcase-studio.ico') -Label 'staged Studio icon'
$VersionInfoVersion = Get-InnoVersionInfoVersion -ReleasePackageVersion $ReleasePackageVersion

$NormalInstallerArgs = @(
    "/DStageDir=$StageDir",
    "/DStudioVersion=$StudioVersion",
    "/DReleasePackageVersion=$ReleasePackageVersion",
    "/DVersionInfoVersion=$VersionInfoVersion",
    "/DOutputDir=$OutputDir",
    $InstallerScript
)
Invoke-CheckedExternal -FilePath $IsccPath -ArgumentList $NormalInstallerArgs -Label 'Production Inno Setup compilation'

$InstallerName = "Dash-Go_Showcase_Studio_${ReleasePackageVersion}_Windows_Setup.exe"
$InstallerPath = Join-Path $OutputDir $InstallerName
$InstallerPath = Resolve-RequiredFile -Path $InstallerPath -Label 'Windows installer candidate'
Copy-Item -LiteralPath $Payload.manifestPath -Destination (Join-Path $OutputDir $script:PayloadManifestName) -Force

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
    "/DVersionInfoVersion=$VersionInfoVersion",
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
$InstalledPayloadFileCount = Test-InstalledCuratedPayload -InstallRoot $SmokeInstallRoot -Payload $Payload

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
    schema = 2
    result = 'PASS'
    studioVersion = $StudioVersion
    releasePackageVersion = $ReleasePackageVersion
    versionInfoVersion = $VersionInfoVersion
    payloadLayout = $script:PayloadLayout
    payloadManifest = $script:PayloadManifestName
    payloadManifestSha256 = $Payload.manifestSha256
    payloadFileCount = $Payload.fileCount
    installedPayloadFileCount = $InstalledPayloadFileCount
    stageExecutable = $StudioExe.FullName
    installer = [System.IO.Path]::GetFileName($InstallerPath)
    installerSha256 = (Get-FileHash -LiteralPath $InstallerPath -Algorithm SHA256).Hash.ToLowerInvariant()
    smokeInstallRoot = $SmokeInstallRoot
    smokeStateRoot = $SmokeStateRoot
    installedIcon = [System.IO.Path]::GetFileName($InstalledIcon)
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $DiagnosticsDir 'windows-package-summary.json') -Encoding utf8

Write-Host "PASS: Windows installer candidate: $InstallerPath"
Write-Host "PASS: curated Windows payload manifest contains $($Payload.fileCount) files and matches the installed package."
Write-Host 'PASS: isolated install, self-test, and uninstall smoke completed.'
