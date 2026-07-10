#!/usr/bin/env python3
"""Static contract checks for the PR-triggered Studio prepublication gate."""
from __future__ import annotations

import argparse
from pathlib import Path


class GateValidationError(RuntimeError):
    pass


def require_text(path: Path, *snippets: str) -> None:
    if not path.is_file():
        raise GateValidationError(f"missing required file: {path}")
    text = path.read_text(encoding="utf-8")
    for snippet in snippets:
        if snippet not in text:
            raise GateValidationError(
                f"{path}: missing required prepublication-gate statement: {snippet}"
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()

    workflow = root / ".github" / "workflows" / "studio-preflight.yml"

    require_text(
        workflow,
        "name: Studio CI Preflight",
        "pull_request:",
        "branches:",
        "- main",
        "workflow_dispatch:",
        "'.github/workflows/**'",
        "'assets/**'",
        "'ci/**'",
        "'cmd/**'",
        "'engine/**'",
        "'go.mod'",
        "'go.sum'",
        "'internal/**'",
        "'packaging/**'",
        "'studio.manifest.json'",
        "'tools/**'",
        "tools/validate_studio_source.py --root .",
        "tools/validate_studio_prepublication_gate.py --root .",
        "tools/validate_studio_prepublication_bridge.py --root .",
        "python3 tools/test_prepare_dashgo_release_prepublication.py",
        "python3 tools/test_stage_package_native_contract.py",
        "tools/validate_studio_stable_release_bridge.py --root .",
        "tools/validate_studio_windows_candidate.py --root .",
        "go test -count=1 -race ./...",
    )

    print("Studio PR-triggered prepublication gate source is internally consistent.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GateValidationError as exc:
        raise SystemExit(f"STUDIO PREPUBLICATION GATE VALIDATION FAILED: {exc}")
