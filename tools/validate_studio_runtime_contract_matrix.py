#!/usr/bin/env python3
"""Fail-closed static validation for Studio's native/legacy runtime-contract matrix."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from showcase_runtime_contract import (  # noqa: E402
    MATRIX_RELATIVE_PATH,
    RuntimeContractMatrixError,
    load_runtime_contract_matrix,
    native_contract_declaration_path,
    native_contract_name,
    required_capabilities,
)


class ValidationError(RuntimeError):
    pass


def require_text(path: Path, *snippets: str) -> None:
    if not path.is_file():
        raise ValidationError(f"missing required file: {path}")
    text = path.read_text(encoding="utf-8")
    for snippet in snippets:
        if snippet not in text:
            raise ValidationError(f"{path}: missing runtime-contract statement: {snippet}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()

    try:
        matrix = load_runtime_contract_matrix(root)
    except RuntimeContractMatrixError as exc:
        raise ValidationError(str(exc)) from exc

    native = matrix["nativeContract"]
    if native_contract_name(matrix) != "dashgo-showcase/v1":
        raise ValidationError("runtime contract matrix has an unexpected native contract name")
    if native_contract_declaration_path(matrix) != "release/showcase-contract.json":
        raise ValidationError("runtime contract matrix has an unexpected native declaration path")
    if tuple(required_capabilities(matrix)) != (
        "separateDataRoot",
        "scenarioManifest",
        "scenarioCalendars",
        "calendarWritebackAllowlist",
        "cacheRebuildReport",
        "statusEndpoint",
        "staticScenarioAssets",
    ):
        raise ValidationError("runtime contract matrix has an unexpected required native capability order")

    runtime = root / "internal/studiohost/runtime.go"
    runtime_plan = root / "internal/studiohost/runtime_contract_plan.go"
    matrix_module = root / "tools/showcase_runtime_contract.py"
    materializer = root / "tools/prepare_dashgo_release.py"
    stage = root / "ci/stage-package.py"
    preflight = root / ".github/workflows/studio-preflight.yml"
    stage_workflow = root / ".github/workflows/studio-stage-candidate.yml"
    beta_validator = root / "tools/validate_studio_native_contract_beta.py"
    stage_native_test = root / "tools/test_stage_package_native_contract.py"
    prepublish_workflow = root / ".github/workflows/studio-prepublish-candidate.yml"

    require_text(
        runtime,
        "nativeShowcaseRuntimePlanAvailable",
        "nativePlan.launchEnvironment",
        "nativePlan.clientVisibleScenarioData",
        "assertNativeShowcaseContractReadyWithPlan",
        "legacyShowcaseLivenessPath",
        "DASHGO_HOME=",
        "DASHGO_SHOWCASE=1",
        "DASHGO_SHOWCASE_DATA_ROOT=",
    )
    require_text(
        runtime_plan,
        "//go:embed dashgo_runtime_contract_matrix.json",
        "loadNativeRuntimeContractPlan",
        "launchEnvironment",
        "scenarioPaths",
        "clientVisibleScenarioData",
        "writableCalendarRequirements",
        "runtime-contract data root",
    )
    require_text(
        matrix_module,
        "native_contract_error_message",
        "missing capability",
        "required by",
        "legacyBridge",
        "browserRoutes",
    )
    require_text(
        materializer,
        "load_runtime_contract_matrix",
        "native_contract_error_message",
        "require_native_contract",
        "dashgo-beta-release",
    )
    require_text(
        stage,
        "load_runtime_contract_matrix",
        "native_contract_error_message",
        "Select Dash-Go Showcase runtime",
        "native Showcase candidate must not carry legacy overlay source",
    )
    require_text(
        preflight,
        "tools/validate_studio_runtime_contract_matrix.py --root .",
        "tools/test_showcase_runtime_contract.py",
        "tools/test_stage_package_native_contract.py",
    )
    require_text(
        stage_workflow,
        "tools/validate_studio_runtime_contract_matrix.py --root .",
        "tools/test_showcase_runtime_contract.py",
        "tools/test_stage_package_native_contract.py",
    )
    require_text(
        beta_validator,
        "validate_studio_runtime_contract_matrix.py",
        "test_showcase_runtime_contract.py",
    )
    require_text(
        prepublish_workflow,
        "tools/test_stage_package_native_contract.py",
    )
    require_text(
        stage_native_test,
        "showcase_tour_guard_view_contract",
        "Runtime contract matrix",
    )

    print(
        "Studio runtime-contract matrix is internally consistent: "
        f"{MATRIX_RELATIVE_PATH.as_posix()} inventories "
        "contract-owned, legacy-only, and Studio-owned assumptions."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValidationError, RuntimeContractMatrixError) as exc:
        raise SystemExit(f"STUDIO RUNTIME CONTRACT MATRIX ERROR: {exc}")
