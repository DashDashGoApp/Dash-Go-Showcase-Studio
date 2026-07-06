#!/usr/bin/env python3
"""Verify native Stage provenance against the exact staged Contract v1 declaration."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from showcase_runtime_contract import (  # noqa: E402
    RuntimeContractMatrixError,
    load_runtime_contract_matrix,
    matrix_path,
    sha256_file,
    validate_native_runtime_plan_evidence,
)


class ValidationError(RuntimeError):
    """Raised when Stage evidence is not tied to the staged native contract."""


def read_json(path: Path, label: str) -> object:
    if not path.is_file():
        raise ValidationError(f"{label} is missing: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{label} is invalid JSON: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    provenance = read_json(args.provenance.resolve(), "candidate provenance")
    contract = read_json(args.contract.resolve(), "staged native contract")
    if not isinstance(provenance, dict):
        raise ValidationError("candidate provenance must be a JSON object")
    if provenance.get("candidateOrigin") != "dashgo-beta-release":
        raise ValidationError("candidate provenance is not a native beta candidate")
    if provenance.get("showcaseRuntimeMode") != "native-contract":
        raise ValidationError("candidate provenance does not select native-contract mode")
    if provenance.get("nativeShowcaseContract") != "dashgo-showcase/v1":
        raise ValidationError("candidate provenance does not declare dashgo-showcase/v1")

    try:
        matrix = load_runtime_contract_matrix(root)
        validate_native_runtime_plan_evidence(
            provenance.get("nativeRuntimePlan"),
            contract,
            matrix,
            matrix_sha256=sha256_file(matrix_path(root)),
            declaration_sha256=sha256_file(args.contract.resolve()),
        )
    except RuntimeContractMatrixError as exc:
        raise ValidationError(f"native runtime-plan evidence is invalid: {exc}") from exc

    print("PASS: native candidate provenance matches the staged Contract v1 declaration and resolved Studio plan")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as exc:
        raise SystemExit(f"NATIVE CANDIDATE PROVENANCE VALIDATION FAILED: {exc}")
