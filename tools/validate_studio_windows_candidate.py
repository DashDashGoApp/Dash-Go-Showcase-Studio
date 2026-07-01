#!/usr/bin/env python3
"""Static fail-closed validation for the Windows package-candidate lane."""
from __future__ import annotations

import argparse
from pathlib import Path


class ValidationError(RuntimeError):
    pass


def require_text(path: Path, *snippets: str) -> None:
    if not path.is_file():
        raise ValidationError(f"missing required file: {path}")
    text = path.read_text(encoding="utf-8")
    for snippet in snippets:
        if snippet not in text:
            raise ValidationError(f"{path}: missing required statement: {snippet}")


def forbid_text(path: Path, snippet: str) -> None:
    if not path.is_file():
        raise ValidationError(f"missing required file: {path}")
    if snippet in path.read_text(encoding="utf-8"):
        raise ValidationError(f"{path}: forbidden legacy statement: {snippet}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()

    workflow = root / ".github" / "workflows" / "studio-windows-package-candidate.yml"
    package_script = root / "ci" / "package-windows.ps1"
    inno_script = root / "packaging" / "windows" / "DashGoShowcaseStudio.iss"
    stage_workflow = root / ".github" / "workflows" / "studio-stage-candidate.yml"

    require_text(
        package_script,
        "STUDIO_RUNTIME.json",
        "windows-amd64",
        "AllowEmptyCollection",
        "ReleasePackageVersion",
        "Dash-Go_Showcase_Studio_${ReleasePackageVersion}_Windows_Setup.exe",
        r"assets\branding\dash-go-showcase-studio.ico",
    )
    forbid_text(package_script, "studio.manifest.json")
    forbid_text(package_script, r"assets\branding\dash-go-showcase-studio.svg")
    forbid_text(package_script, r"assets\branding\linux\hicolor\scalable\apps\dash-go-showcase-studio.svg")
    forbid_text(workflow, "$run.name")
    forbid_text(workflow, 'actions/artifacts/$($matches[0].id)/zip" --output')
    forbid_text(workflow, ".VersionInfo.FileVersion")

    require_text(
        workflow,
        "$innoVersion = '7.0.1-beta'",
        "$innoVersionVerification",
        "compilerVersionVerification = $innoVersionVerification",
        "Invoke-WebRequest",
        "$env:GITHUB_API_URL",
        "Authorization",
        "-OutFile $artifactZip",
        "stage-input.json",
        "expectedStageWorkflowPath",
        "$run.path",
        "studio-stage-candidate.yml",
        "name: Studio Windows Package Candidate",
        "stage_run_id:",
        "runs-on: windows-2025",
        "actions: read",
        "explicitly dispatched Studio Stage Candidate run",
        "windows-stage.tar.gz",
        "candidate-provenance.json",
        "windows-package-provenance.json",
        "candidateOrigin",
        "releasePackageVersion",
        "installerName",
        "manual package candidate only",
        "stable release package candidate only",
        "manual Windows package candidate only",
        "stable release Windows package candidate only",
        "dashGoRelease",
        "Get-RequiredObjectString",
        "innosetup-7.0.1-beta-x64.exe",
        "Get-AuthenticodeSignature",
        "Pyrsys B",
        "studio-windows-package-candidate-${{ github.sha }}",
        "retention-days: 7",
    )
    require_text(
        package_script,
        "--action self-test",
        "--no-browser",
        "PURGE SHOWCASE STUDIO",
        "/DSmokeTest=1",
        "isolated install, self-test, and uninstall smoke",
        "installedIcon = [System.IO.Path]::GetFileName($InstalledIcon)",
    )
    forbid_text(package_script, "installedIcon = $InstalledIcon.FullName")
    require_text(
        inno_script,
        "#ifdef SmokeTest",
        "DASHGO_STUDIO_SMOKE_DEFAULT_DIR",
        "DASHGO_STUDIO_SMOKE_STATE_ROOT",
        "--action purge",
    )
    require_text(
        stage_workflow,
        "name: Studio Stage Candidate",
        "studio-stage-candidate-${{ github.sha }}",
        "candidate_origin:",
        "dashgo_release_tag:",
        "dashgo_source_sha256:",
        "dashgo_tag_commit:",
        "dispatch_nonce:",
        "release_package_version:",
        "tools/prepare_dashgo_release.py",
        "git worktree add --detach",
    )

    print("Studio Windows package-candidate workflow source is internally consistent.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as exc:
        raise SystemExit(f"WINDOWS PACKAGE WORKFLOW VALIDATION FAILED: {exc}")
