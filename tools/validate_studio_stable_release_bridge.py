#!/usr/bin/env python3
"""Static fail-closed contract checks for the Studio stable-release bridge."""
from __future__ import annotations

import argparse
from pathlib import Path


class BridgeValidationError(RuntimeError):
    pass


def require_text(path: Path, *snippets: str) -> None:
    if not path.is_file():
        raise BridgeValidationError(f"missing required file: {path}")
    text = path.read_text(encoding="utf-8")
    for snippet in snippets:
        if snippet not in text:
            raise BridgeValidationError(f"{path}: missing required bridge statement: {snippet}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()

    stage = root / ".github" / "workflows" / "studio-stage-candidate.yml"
    windows = root / ".github" / "workflows" / "studio-windows-package-candidate.yml"
    package = root / "ci" / "package-ubuntu.sh"
    stage_package = root / "ci" / "stage-package.py"
    intake = root / "tools" / "prepare_dashgo_release.py"

    require_text(
        stage,
        "candidate_origin:",
        "dashgo_release_tag:",
        "dashgo_version:",
        "dashgo_source_sha256:",
        "dashgo_tag_commit:",
        "dispatch_nonce:",
        "release_package_version:",
        "git worktree add --detach",
        "tools/prepare_dashgo_release.py",
        "candidate-origin-input.json",
        "Remove isolated candidate source",
        "studio-stage-candidate-${{ github.sha }}",
    )
    require_text(
        package,
        "candidate-origin-json",
        '"schema": 2',
        "manual package candidate only",
        "stable release package candidate only",
        "candidateOrigin",
        "releasePackageVersion",
        "dashGoRelease",
    )
    require_text(
        stage_package,
        "releasePackageVersion",
        "Dash-Go_Showcase_Studio_",
        "Linux_amd64.deb",
    )
    require_text(
        intake,
        'DASHGO_REPOSITORY = "DashDashGoApp/Dash-Go"',
        "candidate-origin",
        "dashgo-stable-release",
        "release.get(\"immutable\") is not True",
        "SHA256SUMS",
        "validate_archive",
        "git/ref/tags",
        "Dash-Go source archive root must be exactly",
        "Dash-Go release/release.json is not the expected {track} release contract",
        "release-package-version",
        "releasePackageVersion",
    )
    require_text(
        windows,
        "Stage Candidate provenance schema must be 2",
        "stable release package candidate only",
        "dashGoRelease.repository",
        "dashGoRelease.sourceAsset.name",
        "dashGoRelease.sha256SumsAsset.name",
        "workflow_dispatch",
        "windows-package-provenance.json",
        "stable release Windows package candidate only",
        "candidateOrigin",
        "releasePackageVersion",
        "installerName",
    )

    print("Studio stable-release bridge source is internally consistent.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BridgeValidationError as exc:
        raise SystemExit(f"STUDIO STABLE RELEASE BRIDGE VALIDATION FAILED: {exc}")
