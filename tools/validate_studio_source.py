#!/usr/bin/env python3
"""Fast deterministic source contract checks for Dash-Go Showcase Studio."""
from __future__ import annotations
import argparse
import ast
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


def assert_stage_packager_syntax_and_r7_phase(root: Path) -> None:
    path = root / "ci/stage-package.py"
    if not path.is_file():
        raise CheckError("missing Studio source: ci/stage-package.py")
    text = path.read_text(encoding="utf-8")
    try:
        compile(text, str(path), "exec")
    except SyntaxError as exc:
        raise CheckError(f"ci/stage-package.py has invalid Python syntax: {exc.msg} (line {exc.lineno})") from exc

    tree = ast.parse(text, filename=str(path))
    expected_arities = {
        "verify_native_showcase_runtime_contract": 3,
        "showcase_tour_guard_view_contract": 4,
    }
    definitions = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in expected_arities
    }
    for name, expected in expected_arities.items():
        definition = definitions.get(name)
        if definition is None:
            raise CheckError(f"ci/stage-package.py is missing required function: {name}")
        positional = len(definition.args.posonlyargs) + len(definition.args.args)
        if positional != expected or definition.args.vararg is not None:
            raise CheckError(
                f"ci/stage-package.py {name} must declare exactly {expected} positional arguments"
            )
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == name
        ]
        if not calls:
            raise CheckError(f"ci/stage-package.py never calls required function: {name}")
        for call in calls:
            if len(call.args) != expected or call.keywords:
                raise CheckError(
                    f"ci/stage-package.py call to {name} must supply exactly {expected} positional arguments"
                )

    lines = text.splitlines()
    bridge = [index for index, line in enumerate(lines) if '"Apply Dash-Go Showcase compatibility profile"' in line]
    if len(bridge) != 1:
        raise CheckError("ci/stage-package.py must contain exactly one legacy Showcase compatibility invocation")
    bridge_indent = len(lines[bridge[0]]) - len(lines[bridge[0]].lstrip(" \t"))
    if not bridge_indent:
        raise CheckError("ci/stage-package.py central Showcase compatibility invocation must remain nested in phase 3")
    for retired in (
        'run(ctx, "Apply Showcase overlay",',
        'run(ctx, "Apply Showcase r7 calendar and presentation overlay",',
    ):
        if retired in text:
            raise CheckError("ci/stage-package.py still invokes a legacy adapter directly")
    for token in (
        "tools/apply_dashgo_compatibility.py",
        "showcase-compatibility-report.json",
        "--source-archive",
        "--source-sha256",
        "--gofmt",
        "--report",
        "native_showcase_contract",
        "verify_native_showcase_runtime_contract",
        "legacyAdaptersApplied",
        "showcaseRuntimeMode",
        '"--go"',
        "asset_generator",
        "install_showcase_native_extensions.py",
        "Install Studio-owned native presentation, safety, and session-calendar extensions",
    ):
        if token not in text:
            raise CheckError(f"ci/stage-package.py Showcase runtime selection is missing: {token}")

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
    if manifest["goToolchain"] != "1.26.5":
        raise CheckError("current Studio source requires Go toolchain 1.26.5")
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
        "internal/fixtures/fixtures.go", "tools/patch_dashgo_engine.py", "tools/patch_dashgo_r7.py", "tools/apply_dashgo_compatibility.py", "tools/dashgo_compatibility.json", "tools/test_dashgo_compatibility.py", "tools/generate_dashgo_assets.py",
        "tools/refresh_dashgo_baseline.py", "tools/prepare_dashgo_release.py",
        "tools/run_legacy_bridge_candidate.py", "tools/test_run_legacy_bridge_candidate.py",
        "tools/validate_studio_legacy_bridge_candidate.py", "tools/validate_studio_native_contract_beta.py", "tools/test_prepare_dashgo_release_beta.py",
        "tools/validate_studio_prepublication_bridge.py", "tools/test_prepare_dashgo_release_prepublication.py",
        "tools/test_stage_package_native_contract.py", "tools/test_generate_dashgo_assets.py",
        "tools/install_showcase_native_extensions.py", "tools/test_install_showcase_native_extensions.py",
        "tools/native_extension_assets/showcase-tour.js", "tools/native_extension_assets/showcase-view.js",
        "tools/native_extension_assets/showcase-calendar-sandbox.js",
        "tools/native_extension_assets/showcase-studio.css",
        "tools/native_extension_assets/showcase_studio_extension.go.txt",
        "tools/native_extension_assets/showcase_studio_calendar.go.txt",
        "tools/native_extension_assets/showcase_studio_extension_test.go.txt",
        ".github/workflows/studio-prepublish-candidate.yml",
        ".github/workflows/studio-legacy-bridge-candidate.yml", "PREPUBLICATION_CANDIDATE_INTAKE.md",
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
    r7_patcher = (root / "tools/patch_dashgo_r7.py").read_text(encoding="utf-8")
    stage_packager = (root / "ci/stage-package.py").read_text(encoding="utf-8")
    assert_stage_packager_syntax_and_r7_phase(root)
    asset_generator = (root / "tools/generate_dashgo_assets.py").read_text(encoding="utf-8")
    for token in (
        "RUNTIME_ASSETS_REL",
        "run_source_owned_generator",
        "verifyGeneratedAssets",
        'env.update({"GOTOOLCHAIN": "local", "GOWORK": "off", "GOFLAGS": "-mod=readonly"})',
        "run_legacy_generator",
        "--go is required",
    ):
        if token not in asset_generator:
            raise CheckError(f"Studio generated-asset bridge is missing: {token}")
    if "minifyjs" in asset_generator or "tdewolff" in asset_generator:
        raise CheckError("Studio generated-asset bridge must not duplicate Dash-Go minifier semantics")
    for workflow in (
        ".github/workflows/studio-preflight.yml",
        ".github/workflows/studio-prepublish-candidate.yml",
        ".github/workflows/studio-stage-candidate.yml",
    ):
        workflow_text = (root / workflow).read_text(encoding="utf-8")
        if 'python3 tools/test_generate_dashgo_assets.py --go "$(go env GOROOT)/bin/go"' not in workflow_text:
            raise CheckError(f"{workflow} does not run the generated-asset bridge regression")
        if 'python3 tools/test_install_showcase_native_extensions.py --gofmt "$(go env GOROOT)/bin/gofmt"' not in workflow_text:
            raise CheckError(f"{workflow} does not run the native Studio-extension regression")
    generated_asset_contract = (root / "SHOWCASE_STUDIO_2.0_CONTRACT.md").read_text(encoding="utf-8")
    for token in (
        "Source-owned browser asset generation",
        "cmd/dashboard-control-server/runtime_assets.go",
        "manifest-only Python generator is a legacy fallback",
        "never silently falls back",
    ):
        if token not in generated_asset_contract:
            raise CheckError(f"Studio generated-asset ownership contract is missing: {token}")
    for token in ("case \"purge\"", "func (a *App) purge() error", "validatePurgeRequest", "requireRuntime := normalized.Action != \"clean\" && normalized.Action != \"purge\""):
        if token not in host_app:
            raise CheckError(f"Studio host is missing guarded full-state purge contract: {token}")
    if 'const customPurgeConfirmation = "PURGE SHOWCASE STUDIO"' not in host_options:
        raise CheckError("Studio host is missing the exact custom purge confirmation contract")
    for token in ("Location", "LookupLocation", "SeedForLocation", "AllLocations", "studio-discovery", "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles", "America/Anchorage", "Pacific/Honolulu"):
        if token not in fixtures:
            raise CheckError(f"Studio city-fixture contract is missing: {token}")
    for token in ("showcase-manifest.json", "dashgo-showcase/v1", "seedShowcaseContractManifest", ".dashboard-vdirsyncer", "showcase-"):
        if token not in fixtures:
            raise CheckError(f"Studio native Showcase manifest contract is missing: {token}")
    for token in ("/api/start-tour", "/api/restart-tour", "/api/return-home", "/api/viewport", "prepareScenarioForLocation", "defer func() { _ = a.clean() }()"):
        if token not in host_controller:
            raise CheckError(f"Studio Start Tour lifecycle contract is missing: {token}")
    if "Start Tour" not in hub_html or "Choose a demo location" not in hub_html or "/api/start-tour" not in hub_js:
        raise CheckError("Studio Hub must expose exactly the Start Tour location-entry flow")
    for retired in ("Capture Gallery", "/api/launch", "Scenario", "id=\"reset\""):
        if retired in hub_html or retired in hub_js:
            raise CheckError(f"Studio Hub still exposes a retired scenario/reset surface: {retired}")
    for token in ("prepareStudioChildCommand(cmd)", "func (a *App) prepareScenarioForLocation", "func (a *App) stopActiveRuntime", "DASHGO_SHOWCASE_DATA_ROOT", "nativeShowcaseRuntimePlanAvailable", "nativePlan.launchEnvironment", "nativePlan.clientVisibleScenarioData", "a.paths.scenarioData", "cmd.Dir = a.paths.runtimeApp"):
        if token not in host_runtime:
            raise CheckError(f"Studio runtime isolation contract is missing: {token}")
    host_runtime_plan = (root / "internal/studiohost/runtime_contract_plan.go").read_text(encoding="utf-8")
    for token in ("//go:embed dashgo_runtime_contract_matrix.json", "loadNativeRuntimeContractPlan", "scenarioPaths", "stagedManifestPath", "launchEnvironment", "clientVisibleScenarioData", "writableCalendarRequirements"):
        if token not in host_runtime_plan:
            raise CheckError(f"Studio executable runtime-contract plan is missing: {token}")
    native_provenance_validator = (root / "tools/validate_studio_native_candidate_provenance.py").read_text(encoding="utf-8")
    for token in ("validate_native_runtime_plan_evidence", "candidate provenance is not a native beta candidate", "staged Contract v1 declaration"):
        if token not in native_provenance_validator:
            raise CheckError(f"Studio native runtime-plan provenance validator is missing: {token}")
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
        "fitPreviewContents",
        "Presentation Fit",
        "wall-landscape",
        "laptop",
        "wide-tablet",
        "portrait-wall",
        "portrait-tablet",
        "portrait-four-three",
        "startupPreferredWidth",
        "startupPreferredHeight",
        "selectStartupViewport",
        "adaptiveStartupViewport",
        "centerChromiumWindow",
        "ScalePercent",
    ):
        if token not in host_browser:
            raise CheckError(f"Studio browser viewport contract is missing: {token}")
    for token in ("calendars/school.blue.ics", "Studio session calendars", "showcase-dashboard-control-open", "dashgo:control-loaded"):
        if token not in r7_patcher:
            raise CheckError(f"Showcase r7 overlay contract is missing: {token}")
    for retired in ("compact-touch", "compact-portrait"):
        if retired in host_browser:
            raise CheckError(f"Studio browser viewport contract still exposes retired live preset: {retired}")
    native_extension_installer = (root / "tools/install_showcase_native_extensions.py").read_text(encoding="utf-8")
    for token in (
        "dashgo-showcase/v1",
        "showcase-tour.js",
        "showcase-view.js",
        "showcase-calendar-sandbox.js",
        "showcase-studio.css",
        "showcase_studio_extension.go",
        "showcase_studio_calendar.go",
        "showcaseStudioRestrictedPost",
        "showcaseStudioRestrictedGet",
        "showcaseStudioGeocode",
        "showcaseStudioWeatherPayload",
        "showcaseStudioEventMapLookup",
        "showcaseStudioSystemUpdateStatus",
        "showcaseStudioUpdateAvailability",
        "showcaseWritableCalendarSource",
        "showcaseCalendarMove",
        "showcaseCalendarDeleteSeries",
        "weather_facade.go",
        "maps_facade.go",
        "runtime_assets_manifest_test.go",
    ):
        if token not in native_extension_installer:
            raise CheckError(f"Studio native extension installer is missing: {token}")
    native_view = (root / "tools/native_extension_assets/showcase-view.js").read_text(encoding="utf-8")
    native_calendar = (root / "tools/native_extension_assets/showcase-calendar-sandbox.js").read_text(encoding="utf-8")
    for token in (
        'view_asset = Path(__file__).resolve().parent / "native_extension_assets/showcase-view.js"',
        'write(view, view_asset.read_text(encoding="utf-8"))',
    ):
        if token not in patcher:
            raise CheckError(f"Studio legacy bridge does not reuse the shared viewport asset: {token}")
    for token in (
        "Device previews preserve the selected CSS aspect ratio",
        "hostWidth",
        "hostHeight",
        "scalePercent",
        "aria-pressed",
    ):
        if token not in native_view:
            raise CheckError(f"Studio native viewport extension is missing: {token}")
    for token in ("showcaseMoveCalendarEvent", "showcaseDeleteCalendarSeries", "/api/calendar/event/move", "/api/calendar/event/series/delete"):
        if token not in native_calendar:
            raise CheckError(f"Studio native session-calendar UI is missing: {token}")
    native_policy = (root / "tools/native_extension_assets/showcase_studio_extension.go.txt").read_text(encoding="utf-8")
    native_calendar_policy = (root / "tools/native_extension_assets/showcase_studio_calendar.go.txt").read_text(encoding="utf-8")
    for token in (
        "showcaseStudioRestrictedPost",
        "showcaseStudioRestrictedGet",
        "showcaseStudioGeocode",
        "showcaseStudioWeatherPayload",
        "showcaseStudioEventMapLookup",
        "showcase-fixture",
        "studio_location_locked",
        "studio_external_integration_locked",
        "showcaseStudioSystemUpdateStatus",
        "showcaseStudioUpdateAvailability",
        "showcaseWritableCalendarSource",
    ):
        if token not in native_policy:
            raise CheckError(f"Studio native safety extension is missing: {token}")
    for token in ("showcaseCalendarMove", "showcaseCalendarDeleteSeries", "showcaseSessionCalendarMessage", "sync"):
        if token not in native_calendar_policy:
            raise CheckError(f"Studio native session-calendar runtime is missing: {token}")
    for token in ("HideWindow: true", "CreationFlags: createNoWindow"):
        if token not in child_windows:
            raise CheckError(f"Windows child no-console contract is missing: {token}")
    for token in (
        "install_showcase_studio_overlay", "showcase-tour.js", "showcase-view.js", "showcase-studio.css", "runtime_assets_manifest_test.go",
        '\\t\\t\\t\\"ui/js/showcase-tour.js\\",\\n', '\\t\\t\\t\\"ui/js/showcase-view.js\\",\\n',
        "openOnly", "clearPrimarySurface", "dashboardListsDockEnable", "dashboardListsDockDisable", "Sample Weather Alert — Studio Preview",
        "studio_location_locked", "Ah ah ah, you didn’t say the magic word.", "showcaseGeocode", "showcaseRestrictedPost", "showcaseRestrictedGet",
        "Clean View", "Wall Display", "Common Laptop", "16:10 Display", "Portrait Wall", "Portrait Tablet", "4:3 Portrait",
    ):
        if token not in patcher:
            raise CheckError(f"Staged Dash-Go Studio contract is missing: {token}")
    for retired in ("compact-touch", "compact-portrait"):
        if retired in patcher:
            raise CheckError(f"Staged Dash-Go Studio contract still exposes retired live preset: {retired}")
    if "const location=" in patcher or re.search(r"(?<![\w.])location\.(?:reload|assign)\(", patcher):
        raise CheckError("Staged Dash-Go tour must not shadow window.location")
    compatibility_matrix = json.loads((root / "tools/dashgo_compatibility.json").read_text(encoding="utf-8"))
    if compatibility_matrix.get("schema") != 2:
        raise CheckError("Showcase compatibility matrix schema must be 2")
    profiles = compatibility_matrix.get("profiles")
    if not isinstance(profiles, list) or len(profiles) != 1:
        raise CheckError("Showcase compatibility matrix must define exactly one legacy profile")
    profile = profiles[0]
    if not isinstance(profile, dict) or profile.get("id") != "legacy-bridge-v1":
        raise CheckError("Showcase compatibility matrix has an unexpected legacy profile")
    if "sources" in profile:
        raise CheckError("Showcase compatibility matrix must not retain brittle exact-archive source rules")
    policy = profile.get("sourcePolicy")
    if not isinstance(policy, dict):
        raise CheckError("Showcase compatibility matrix source policy is missing")
    if policy != {
        "selection": "adapter-probe",
        "minimumVersion": "1.5.7",
        "maximumVersionExclusive": "1.6.0",
    }:
        raise CheckError("Showcase compatibility matrix has an unexpected adapter-probe window")
    checks = profile.get("requiredCandidateChecks")
    if checks != [
        "staged-linux-package-and-runtime-self-test",
        "windows-installer-install-self-test-and-uninstall-smoke",
    ]:
        raise CheckError("Showcase compatibility matrix has an unexpected candidate-check contract")
    bridge = (root / "tools/apply_dashgo_compatibility.py").read_text(encoding="utf-8")
    for token in (
        "requiredCandidateChecks",
        "SHOWCASE COMPATIBILITY ERROR",
        "source archive SHA-256 mismatch",
        "adapter-probe",
        "maximumVersionExclusive",
        "the adapters themselves are the final",
    ):
        if token not in bridge:
            raise CheckError(f"Showcase compatibility bridge is missing contract token: {token}")
    for retired in ("add a reviewed exact-hash matrix entry", "sourceHashMode", "manifest-verified"):
        if retired in bridge:
            raise CheckError("Showcase compatibility bridge retains a broad or brittle retired selection path")

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