#!/usr/bin/env python3
"""Fast deterministic source contract checks for Dash-Go Showcase Studio."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
import tarfile
from pathlib import Path

sys.dont_write_bytecode = True

class CheckError(RuntimeError):
    pass

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = json.loads((root / "studio.manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != 1:
        raise CheckError("studio.manifest.json schema must be 1")
    for field in ("studioVersion", "dashGoVersion", "dashGoSourceArchive", "dashGoSourceSha256", "goToolchain", "defaultScenario"):
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            raise CheckError(f"missing manifest field: {field}")
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-test\.\d+)?", manifest["studioVersion"]):
        raise CheckError("studioVersion must use X.Y.Z or X.Y.Z-test.N")
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-beta\.\d+)?", manifest["dashGoVersion"]):
        raise CheckError("dashGoVersion must use X.Y.Z or X.Y.Z-beta.N")
    if manifest["goToolchain"] != "1.26.4":
        raise CheckError("current Studio source requires Go toolchain 1.26.4")
    dashgo_root = f"dash-go-source-{manifest['dashGoVersion']}"
    source = root / manifest["dashGoSourceArchive"]
    if not source.is_file():
        raise CheckError("pinned Dash-Go source archive is missing")
    if sha256(source) != manifest["dashGoSourceSha256"]:
        raise CheckError("pinned Dash-Go source archive SHA-256 mismatch")
    with tarfile.open(source, "r:gz") as tar:
        names = [member.name.replace("\\", "/") for member in tar.getmembers()]
        required = {
            f"{dashgo_root}/app/VERSION",
            f"{dashgo_root}/app/release/release.json",
            f"{dashgo_root}/app/cmd/dashboard-control-server/main.go",
            f"{dashgo_root}/app/ui/js/bundle.manifest.json",
        }
        if not names or not all(name == dashgo_root or name.startswith(dashgo_root + "/") for name in names):
            raise CheckError(f"pinned source archive does not have the expected root {dashgo_root}")
        if not required.issubset(names):
            raise CheckError("pinned source archive is incomplete")
    caches = [p.relative_to(root).as_posix() for p in root.rglob("*") if p.name == "__pycache__" or (p.is_file() and p.suffix == ".pyc")]
    if caches:
        print("NOTE: ignored local Python cache artifacts (not part of source handoff or package): " + ", ".join(sorted(caches)[:8]))
    for relative in (
        "go.mod", "cmd/dash-go-showcase-studio/main.go", "internal/studiohost/runtime.go", "internal/studiohost/app.go",
        "internal/fixtures/fixtures.go", "tools/patch_dashgo_engine.py", "tools/generate_dashgo_assets.py",
        "tools/refresh_dashgo_baseline.py", "tools/prepare_dashgo_release.py",
        "tools/validate_studio_prepublication_bridge.py", "tools/test_prepare_dashgo_release_prepublication.py",
        ".github/workflows/studio-prepublish-candidate.yml", "PREPUBLICATION_CANDIDATE_INTAKE.md",
        "packaging/windows/DashGoShowcaseStudio.iss", "WHAT-STUDIO-DOES-LOCALLY.txt",
        "packaging/linux/dash-go-showcase-studio-uninstall", "SHOWCASE_STUDIO_2.0_CONTRACT.md", "PORTABLE_RUNTIME_OVERLAY.md",
        "STUDIO_WINDOWS_RUNTIME_BOUNDARY.md",
    ):
        if not (root / relative).is_file():
            raise CheckError(f"missing Studio source: {relative}")
    if manifest["defaultScenario"] not in (root / "internal/fixtures/fixtures.go").read_text(encoding="utf-8"):
        raise CheckError("default scenario is not represented by fixtures")
    installer = (root / "packaging/windows/DashGoShowcaseStudio.iss").read_text(encoding="utf-8")
    for token in (
        "SetupArchitecture=x64", "ArchitecturesAllowed=x64compatible", "#ifdef SmokeTest",
        'GetEnv("DASHGO_STUDIO_SMOKE_DEFAULT_DIR")', 'GetEnv("DASHGO_STUDIO_SMOKE_STATE_ROOT")',
        "DASHGO_STUDIO_SMOKE_DEFAULT_DIR must be supplied for a SmokeTest build.",
        "DASHGO_STUDIO_SMOKE_STATE_ROOT must be supplied for a SmokeTest build.",
        "UsePreviousAppDir=no", "SmokeAppId", "ReleasePackageVersion", "VersionInfoVersion", "AppVerName", "[UninstallRun]", "--action purge", "RunOnceId", "[UninstallDelete]",
        'Type: filesandordirs; Name: "{localappdata}\\Dash-Go Showcase Studio"',
        "Compression=lzma2/max", "SolidCompression=no", "AppSupportURL=", "AppUpdatesURL=",
        "VersionInfoCompany=DashDashGoApp", "VersionInfoDescription=Dash-Go Showcase Studio Installer",
        "VersionInfoProductName={#StudioName}", "VersionInfoOriginalFileName=",
        "INSTALLER_CONTENTS.json", "WHAT-STUDIO-DOES-LOCALLY.txt",
    ):
        if token not in installer:
            raise CheckError(f"Windows installer is missing full-removal contract token: {token}")
    for retired in (
        'Source: "{#StageDir}\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs',
        "Compression=lzma2/ultra64", "SolidCompression=yes", "PrivilegesRequiredOverridesAllowed=dialog",
    ):
        if retired in installer:
            raise CheckError(f"Windows installer still contains retired broad or high-risk packaging setting: {retired}")
    local_behavior = (root / "WHAT-STUDIO-DOES-LOCALLY.txt").read_text(encoding="utf-8")
    for token in (
        "127.0.0.1", "per-user", "Windows service", "scheduled task", "startup entry", "firewall",
        "download and run", "source files", "test suites", "script helpers", "CLI companion",
    ):
        if token not in local_behavior:
            raise CheckError(f"Studio local-behavior document is missing transparency token: {token}")
    host_app = (root / "internal/studiohost/app.go").read_text(encoding="utf-8")
    host_options = (root / "internal/studiohost/options.go").read_text(encoding="utf-8")
    host_runtime = (root / "internal/studiohost/runtime.go").read_text(encoding="utf-8")
    host_controller = (root / "internal/studiohost/controller.go").read_text(encoding="utf-8")
    host_browser = (root / "internal/studiohost/browser.go").read_text(encoding="utf-8")
    child_windows = (root / "internal/studiohost/childprocess_windows.go").read_text(encoding="utf-8")
    hub_html = (root / "internal/studiohost/web/hub.html").read_text(encoding="utf-8")
    hub_js = (root / "internal/studiohost/web/hub.js").read_text(encoding="utf-8")
    fixtures = (root / "internal/fixtures/fixtures.go").read_text(encoding="utf-8")
    patcher = (root / "tools/patch_dashgo_engine.py").read_text(encoding="utf-8")
    stage_packager = (root / "ci/stage-package.py").read_text(encoding="utf-8")
    for token in ("case \"purge\"", "func (a *App) purge() error", "validatePurgeRequest", "requireRuntime := normalized.Action != \"clean\" && normalized.Action != \"purge\""):
        if token not in host_app:
            raise CheckError(f"Studio host is missing guarded full-state purge contract: {token}")
    if 'const customPurgeConfirmation = "PURGE SHOWCASE STUDIO"' not in host_options:
        raise CheckError("Studio host is missing the exact custom purge confirmation contract")
    for token in ("Location", "LookupLocation", "SeedForLocation", "AllLocations", "studio-discovery", "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles", "America/Anchorage", "Pacific/Honolulu"):
        if token not in fixtures:
            raise CheckError(f"Studio city-fixture contract is missing: {token}")
    for token in ("/api/start-tour", "/api/restart-tour", "/api/return-home", "/api/viewport", "prepareScenarioForLocation", "defer func() { _ = a.clean() }()"):
        if token not in host_controller:
            raise CheckError(f"Studio Start Tour lifecycle contract is missing: {token}")
    if "Start Tour" not in hub_html or "Choose a demo location" not in hub_html or "/api/start-tour" not in hub_js:
        raise CheckError("Studio Hub must expose exactly the Start Tour location-entry flow")
    for retired in ("Capture Gallery", "/api/launch", "Scenario", "id=\"reset\""):
        if retired in hub_html or retired in hub_js:
            raise CheckError(f"Studio Hub still exposes a retired scenario/reset surface: {retired}")
    for token in ("prepareStudioChildCommand(cmd)", "func (a *App) prepareScenarioForLocation", "func (a *App) stopActiveRuntime", "DASHGO_SHOWCASE_DATA_ROOT", "a.paths.scenarioData", "cmd.Dir = a.paths.runtimeApp"):
        if token not in host_runtime:
            raise CheckError(f"Studio runtime isolation contract is missing: {token}")
    for retired in ("workspaceApp", "workspaceHome", "workspaceRoot", ".workspace-stage-", "copyTree(a.paths.runtimeApp"):
        if retired in host_runtime:
            raise CheckError(f"Studio runtime still contains a mutable executable-workspace pattern: {retired}")
    for token in ("scenarioRoot", "scenarioData", "scenarioHome"):
        if token not in (root / "internal/studiohost/paths.go").read_text(encoding="utf-8"):
            raise CheckError(f"Studio state-path contract is missing: {token}")
    for token in (
        "DASHGO_SHOWCASE_DATA_ROOT", "dashGoShowcaseDataRoot(dash)",
        "configDir: filepath.Join(data, \"config\")", "fontsDir: filepath.Join(data, \"fonts\")",
    ):
        if token not in patcher:
            raise CheckError(f"Showcase engine data-root overlay is missing: {token}")
    # patch_dashgo_engine.py keeps the pre-overlay source literal as an exact
    # replace_once anchor. The staged runtime—not the patcher text—is the
    # authoritative place to assert that no mutable path remains under dash.
    for token in (
        "fontsDir: filepath.Join(data, \\\"fonts\\\")",
        "fontsDir: filepath.Join(dash, \\\"fonts\\\")",
        "staged Showcase runtime still writes mutable data under its install root",
        '"DASHGO_SHOWCASE_DATA_ROOT": str(work / "runtime-data")',
        "MUTABLE_STATE_ALLOWED_SCRIPT_PATHS",
        "assert_private_state_has_no_unapproved_executables_or_scripts",
        'state / "scenario" / "data"',
        'state / "scenario" / "home"',
        'state / "scenario" / "SHOWCASE_RUNTIME.json"',
        'state / "scenario" / "data" / "config" / "config.local.js"',
        "recreated the retired private executable workspace",
    ):
        if token not in stage_packager:
            raise CheckError(f"Showcase engine staged data-root contract is missing: {token}")
    boundary = (root / "STUDIO_WINDOWS_RUNTIME_BOUNDARY.md").read_text(encoding="utf-8")
    for token in ("dash-go-showcase-server.exe", "DASHGO_SHOWCASE_DATA_ROOT", "127.0.0.1", "never copies", "user-writable", "scenario/data/config/config.local.js", "sole allowlisted"):
        if token not in boundary:
            raise CheckError(f"Studio Windows runtime-boundary contract is missing: {token}")
    for token in (
        "--user-data-dir=",
        "--remote-debugging-address=127.0.0.1",
        "Emulation.setDeviceMetricsOverride",
        "Emulation.clearDeviceMetricsOverride",
        "Browser.getWindowForTarget",
        "Browser.setWindowBounds",
        "Browser.setContentsSize",
        "wall-landscape",
        "laptop",
        "wide-tablet",
        "portrait-wall",
        "portrait-tablet",
        "portrait-four-three",
        "startupShowcaseViewports",
        "selectStartupViewport",
        "adaptiveStartupViewport",
    ):
        if token not in host_browser:
            raise CheckError(f"Studio browser viewport contract is missing: {token}")
    for retired in ("compact-touch", "compact-portrait"):
        if retired in host_browser:
            raise CheckError(f"Studio browser viewport contract still exposes retired live preset: {retired}")
    for token in ("HideWindow: true", "CreationFlags: createNoWindow"):
        if token not in child_windows:
            raise CheckError(f"Windows child no-console contract is missing: {token}")
    for token in (
        "install_showcase_studio_overlay", "showcase-tour.js", "showcase-view.js", "showcase-studio.css", "runtime_assets_manifest_test.go",
        '\\t\\t\\t\\"ui/js/showcase-tour.js\\",\\n', '\\t\\t\\t\\"ui/js/showcase-view.js\\",\\n',
        "openOnly", "clearPrimarySurface", "dashboardListsDockEnable", "dashboardListsDockDisable", "Sample Weather Alert — Studio Preview",
        "studio_location_locked", "Ah ah ah, you didn’t say the magic word.", "showcaseGeocode", "showcaseRestrictedPost", "showcaseRestrictedGet",
        "Clean View", "Fit Display", "Wall Display", "Common Laptop", "16:10 Display", "Portrait Wall", "Portrait Tablet", "4:3 Portrait",
    ):
        if token not in patcher:
            raise CheckError(f"Staged Dash-Go Studio contract is missing: {token}")
    for retired in ("compact-touch", "compact-portrait"):
        if retired in patcher:
            raise CheckError(f"Staged Dash-Go Studio contract still exposes retired live preset: {retired}")
    if "const location=" in patcher or re.search(r"(?<![\w.])location\.(?:reload|assign)\(", patcher):
        raise CheckError("Staged Dash-Go tour must not shadow window.location")
    linux_uninstall = (root / "packaging/linux/dash-go-showcase-studio-uninstall").read_text(encoding="utf-8")
    for token in ("--purge-state", "--purge", "--action purge", "apt-get purge", "id -u", "sudo"):
        if token not in linux_uninstall:
            raise CheckError(f"Linux full-removal wrapper is missing contract token: {token}")
    print(f"PASS: Studio source {manifest['studioVersion']} pinned to Dash-Go {manifest['dashGoVersion']}")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckError as exc:
        raise SystemExit(f"STUDIO SOURCE ERROR: {exc}")
