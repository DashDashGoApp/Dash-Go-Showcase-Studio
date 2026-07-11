#!/usr/bin/env python3
"""Static fail-closed contract checks for the Studio draft-prepublication bridge."""
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
            raise BridgeValidationError(f"{path}: missing required prepublication statement: {snippet}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()

    preflight = root / ".github" / "workflows" / "studio-preflight.yml"
    stage = root / ".github" / "workflows" / "studio-prepublish-candidate.yml"
    package = root / "ci" / "package-ubuntu.sh"
    intake = root / "tools" / "prepare_dashgo_release.py"
    test = root / "tools" / "test_prepare_dashgo_release_prepublication.py"
    stage_native_test = root / "tools" / "test_stage_package_native_contract.py"
    intake_doc = root / "PREPUBLICATION_CANDIDATE_INTAKE.md"

    require_text(
        preflight,
        "tools/validate_studio_prepublication_bridge.py --root .",
        "python3 tools/test_prepare_dashgo_release_prepublication.py",
        "python3 tools/test_stage_package_native_contract.py",
        'python3 tools/test_install_showcase_native_extensions.py --gofmt "$(go env GOROOT)/bin/gofmt"',
    )
    require_text(
        stage,
        "name: Studio Prepublication Candidate",
        "dashgo_release_id:",
        "dashgo_release_tag:",
        "dashgo_version:",
        "studio_source_commit:",
        "dashgo_source_asset_id:",
        "dashgo_source_sha256:",
        "dashgo_sha256sums_asset_id:",
        "dashgo_tag_commit:",
        "dispatch_nonce:",
        "release_package_version:",
        "git worktree add --detach",
        "--candidate-origin dashgo-draft-prepublish-release",
        "tools/prepare_dashgo_release.py",
        "studio-prepublication-candidate-${{ github.sha }}",
        "studio-prepublication-diagnostics-${{ github.sha }}",
        "Remove isolated candidate source",
        "retention-days: 7",
        "DASHGO_RELEASE_READ_TOKEN",
        "EXPECTED_STUDIO_SOURCE_COMMIT",
        "git rev-parse HEAD",
        "Studio source commit mismatch",
        "DASHGO_RELEASE_READ_TOKEN is required to read the Dash-Go draft release.",
        'export GITHUB_TOKEN="$DASHGO_RELEASE_READ_TOKEN"',
    )
    require_text(
        package,
        "dashgo-draft-prepublish-release",
        "draft prepublication package candidate only",
        "candidate origin schema must be 1 or 2",
        'provenance["schema"] = 3',
        "draft-prepublication origin does not prove a mutable unpublished Dash-Go draft",
        "draft-prepublication package version must exactly equal staged Dash-Go version",
    )
    require_text(
        intake,
        "DRAFT_PREPUBLICATION_PURPOSE = \"draft prepublication package candidate only\"",
        "dashgo-draft-prepublish-release",
        "--dashgo-release-id",
        "--dashgo-source-asset-id",
        "--dashgo-sha256sums-asset-id",
        "releases/{release_id}",
        "release.get(\"draft\") is not True",
        "release.get(\"immutable\") is not False",
        "release.get(\"published_at\") is not None",
        "draft source asset API URL",
        "draft SHA256SUMS asset API URL",
        "require_prepublication_package_version",
        "\"schema\": 2",
    )
    require_text(
        test,
        "dashgo-draft-prepublish-release",
        "draft prepublication package candidate only",
        "mutable unpublished Dash-Go draft",
    )
    require_text(
        intake_doc,
        "DASHGO_RELEASE_READ_TOKEN",
        "DashDashGoApp/Dash-Go",
        "draft prepublication package candidate only",
        "neither publishes the Dash-Go draft",
    )

    require_text(
        stage_native_test,
        "showcase_tour_guard_view_contract",
        "Runtime contract matrix",
        "exact Phase 4 native path",
    )

    print("Studio draft-prepublication bridge source is internally consistent.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BridgeValidationError as exc:
        raise SystemExit(f"STUDIO PREPUBLICATION BRIDGE VALIDATION FAILED: {exc}")
