#!/usr/bin/env python3
"""Static fail-closed validation for the automatic legacy bridge proof gate."""
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()

    workflow = root / ".github" / "workflows" / "studio-legacy-bridge-candidate.yml"
    runner = root / "tools" / "run_legacy_bridge_candidate.py"
    tests = root / "tools" / "test_run_legacy_bridge_candidate.py"
    matrix = root / "tools" / "dashgo_compatibility.json"

    require_text(
        workflow,
        "name: Legacy Bridge Candidate Proof",
        "pull_request:",
        "workflow_dispatch:",
        "pull-requests: read",
        "actions: write",
        "bridge_changed",
        "same_repository",
        "tools/run_legacy_bridge_candidate.py",
        "github.event.pull_request.head.sha || github.sha",
        "github.head_ref || github.ref_name",
        "studio-stage-candidate.yml",
        "studio-windows-package-candidate.yml",
        "legacy-bridge-candidate-",
        "cancel-in-progress: true",
        "pulls/$PR_NUMBER/files?per_page=100",
        "tools/apply_dashgo_compatibility.py",
        "tools/dashgo_compatibility.json",
        "tools/patch_dashgo_engine.py",
        "tools/patch_dashgo_r7.py",
        "ci/stage-package.py",
        "ci/package-ubuntu.sh",
        "ci/package-windows.ps1",
    )
    require_text(
        runner,
        "EXPECTED_STUDIO_REPOSITORY = \"DashDashGoApp/Dash-Go-Showcase-Studio\"",
        "DASHGO_REPOSITORY = \"DashDashGoApp/Dash-Go\"",
        "legacy-bridge-v1",
        "adapter-probe",
        "immutable stable release",
        "studio-stage-candidate.yml",
        "studio-windows-package-candidate.yml",
        "candidate_origin",
        "dashgo-stable-release",
        "dashgo_source_sha256",
        "dashgo_tag_commit",
        "stage_run_id",
        "workflow_dispatch",
        "actions/workflows",
        "actions/runs",
        "GITHUB_STEP_SUMMARY",
        "GITHUB_OUTPUT",
        "LEGACY BRIDGE CANDIDATE ERROR",
    )
    require_text(
        tests,
        "test_loads_reviewed_adapter_probe_policy",
        "test_loads_immutable_release_and_annotated_tag",
        "test_discovers_only_exact_branch_head_nonce_and_workflow",
        "test_rejects_version_outside_reviewed_window",
    )
    require_text(
        matrix,
        '"schema": 2',
        '"selection": "adapter-probe"',
        '"minimumVersion"',
        '"maximumVersionExclusive"',
    )
    print("Studio automatic legacy bridge candidate gate source is internally consistent.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as exc:
        raise SystemExit(f"LEGACY BRIDGE CANDIDATE GATE VALIDATION FAILED: {exc}")
