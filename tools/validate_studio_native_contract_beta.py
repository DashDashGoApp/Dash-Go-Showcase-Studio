#!/usr/bin/env python3
"""Static fail-closed checks for the immutable native-Contract beta candidate lane."""
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
            raise ValidationError(f"{path}: missing required native-beta statement: {snippet}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()

    preflight = root / ".github/workflows/studio-preflight.yml"
    stage = root / ".github/workflows/studio-stage-candidate.yml"
    windows = root / ".github/workflows/studio-windows-package-candidate.yml"
    intake = root / "tools/prepare_dashgo_release.py"
    intake_test = root / "tools/test_prepare_dashgo_release_beta.py"
    stage_packager = root / "ci/stage-package.py"
    package = root / "ci/package-ubuntu.sh"

    require_text(
        preflight,
        "tools/validate_studio_native_contract_beta.py --root .",
        "python3 tools/test_prepare_dashgo_release_beta.py",
    )
    require_text(
        stage,
        "dashgo-beta-release",
        "immutable native-contract beta release",
        "tools/validate_studio_native_contract_beta.py --root .",
        "tools/test_prepare_dashgo_release_beta.py",
        "candidate_origin:",
        "release_package_version:",
        'description: "Studio package identity: stable accepts Dash-Go X.Y.Z or X.Y.Z-rN; native beta accepts numeric core plus -test.N"',
    )
    require_text(
        intake,
        'BETA_NATIVE_PURPOSE = "beta release native contract candidate only"',
        'NATIVE_SHOWCASE_CONTRACT = "dashgo-showcase/v1"',
        '"dashgo-beta-release"',
        "require_beta_version",
        "require_beta_package_version",
        "published immutable beta release",
        "require_native_contract=beta_native",
        '"prerelease": beta_native',
        '"track": "beta" if beta_native else "stable"',
    )
    require_text(
        intake_test,
        "dashgo-beta-release",
        "beta release native contract candidate only",
        "dashgo-showcase/v1",
        '"track": "beta"',
    )
    require_text(
        stage_packager,
        'NATIVE_SHOWCASE_CONTRACT = "dashgo-showcase/v1"',
        "native_showcase_contract",
        "verify_native_showcase_runtime_contract",
        'ctx.showcase_runtime_mode = "native-contract"',
        '"legacyAdaptersApplied": False',
        '"showcaseRuntimeMode": ctx.showcase_runtime_mode',
        "native Showcase candidate must not carry legacy overlay source",
        "beta native candidate releasePackageVersion",
    )
    require_text(
        package,
        'origin_kind == "dashgo-beta-release"',
        "beta release native contract candidate only",
        "beta-release candidate must stage the native Showcase contract without legacy overlays",
        '"showcaseRuntimeMode": showcase_runtime_mode',
        'provenance["nativeShowcaseContract"] = NATIVE_SHOWCASE_CONTRACT',
    )
    require_text(
        windows,
        "beta release native contract candidate only",
        "dashgo-beta-release",
        "Beta candidate provenance does not prove the native Showcase Contract v1 path.",
        "beta native contract Windows package candidate only",
        "Windows beta candidate must inherit native Showcase Contract v1 evidence from Stage.",
        "nativeShowcaseContract = [string]$stageProvenance.nativeShowcaseContract",
    )

    print("Studio native Showcase Contract beta lane source is internally consistent.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as exc:
        raise SystemExit(f"STUDIO NATIVE BETA VALIDATION FAILED: {exc}")
