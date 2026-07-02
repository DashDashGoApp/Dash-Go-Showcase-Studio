#!/usr/bin/env python3
"""Static fail-closed validation for the Windows draft-prepublication package lane."""
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

    workflow = root / ".github" / "workflows" / "studio-windows-prepublish-package-candidate.yml"
    legacy_workflow = root / ".github" / "workflows" / "studio-windows-package-candidate.yml"
    stage_workflow = root / ".github" / "workflows" / "studio-prepublish-candidate.yml"
    package_script = root / "ci" / "package-windows.ps1"
    inno_script = root / "packaging" / "windows" / "DashGoShowcaseStudio.iss"

    require_text(
        workflow,
        "name: Studio Windows Prepublication Package Candidate",
        "stage_run_id:",
        "studio_source_commit:",
        "dashgo_release_id:",
        "dashgo_version:",
        "dashgo_source_asset_id:",
        "dashgo_source_sha256:",
        "dashgo_sha256sums_asset_id:",
        "dispatch_nonce:",
        "runs-on: windows-2025",
        "actions: read",
        "Studio source commit mismatch",
        "tools/validate_studio_windows_prepublication.py --root .",
        "expectedStageWorkflowPath = '.github/workflows/studio-prepublish-candidate.yml'",
        "explicitly dispatched Studio Prepublication Candidate run",
        "studio-prepublication-candidate-$($run.head_sha)",
        "$run.path",
        "stage-input.json",
        "Invoke-WebRequest",
        "$env:GITHUB_API_URL",
        "Authorization",
        "-OutFile $artifactZip",
        "candidate-provenance.json",
        "windows-stage.tar.gz",
        "Get-RequiredObjectString",
        "Assert-ExplicitNullProperty",
        "Prepublication Candidate provenance schema must be 3",
        "Legacy stable or manual candidates are not accepted by this workflow.",
        "'draft prepublication package candidate only'",
        "'dashgo-draft-prepublish-release'",
        "Prepublication package version must exactly equal the staged Dash-Go version.",
        "does not prove a mutable unpublished Dash-Go draft",
        "dashGoRelease.publishedAt",
        "does not match the dispatched asset ID",
        "$innoVersion = '7.0.1-beta'",
        "$innoVersionVerification",
        "compilerVersionVerification = $innoVersionVerification",
        "innosetup-7.0.1-beta-x64.exe",
        "Get-AuthenticodeSignature",
        "Pyrsys B",
        "windows-package-provenance.json",
        "purpose = 'draft prepublication Windows package candidate only'",
        "prepublicationOnly = $true",
        "dispatchNonce = $env:DISPATCH_NONCE",
        "installerName",
        "studio-windows-prepublish-package-candidate-${{ github.sha }}",
        "studio-windows-prepublish-package-diagnostics-${{ github.sha }}",
        "retention-days: 7",
    )
    forbid_text(workflow, "studio-stage-candidate.yml")
    forbid_text(workflow, "dashgo-stable-release")
    forbid_text(workflow, "manual package candidate only")
    forbid_text(workflow, "stable release package candidate only")
    forbid_text(workflow, "schema must be 2")
    forbid_text(workflow, "immutable = true")
    forbid_text(workflow, "$run.name")
    forbid_text(workflow, ".VersionInfo.FileVersion")

    require_text(
        legacy_workflow,
        "name: Studio Windows Package Candidate",
        "studio-stage-candidate.yml",
        "studio-windows-package-candidate-${{ github.sha }}",
    )
    forbid_text(legacy_workflow, "studio-prepublish-candidate.yml")
    forbid_text(legacy_workflow, "dashgo-draft-prepublish-release")

    require_text(
        stage_workflow,
        "name: Studio Prepublication Candidate",
        "studio_source_commit:",
        "--candidate-origin dashgo-draft-prepublish-release",
        "studio-prepublication-candidate-${{ github.sha }}",
        "DASHGO_RELEASE_READ_TOKEN",
    )

    require_text(
        package_script,
        "STUDIO_RUNTIME.json",
        "windows-amd64",
        "ReleasePackageVersion",
        "Dash-Go_Showcase_Studio_${ReleasePackageVersion}_Windows_Setup.exe",
    )
    require_text(
        inno_script,
        "#ifdef SmokeTest",
        "--action purge",
    )

    print("Studio Windows prepublication package workflow source is internally consistent.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as exc:
        raise SystemExit(f"WINDOWS PREPUBLICATION WORKFLOW VALIDATION FAILED: {exc}")
