#!/usr/bin/env python3
"""Hermetic tests for Studio's machine-readable Dash-Go runtime-contract matrix."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from showcase_runtime_contract import (  # noqa: E402
    RuntimeContractMatrixError,
    load_runtime_contract_matrix,
    native_contract_defects,
    native_contract_error_message,
    required_capabilities,
    validate_runtime_contract_matrix,
)


def expected_contract(matrix: dict) -> dict:
    return {
        "schema": matrix["nativeContract"]["schema"],
        "contract": matrix["nativeContract"]["contract"],
        "capabilities": {capability: True for capability in required_capabilities(matrix)},
    }


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    matrix = load_runtime_contract_matrix(root)
    contract = expected_contract(matrix)

    require(native_contract_defects(contract, matrix) == [], "complete native contract should satisfy matrix")
    require(native_contract_error_message(contract, matrix) is None, "complete native contract should not produce an error")

    incomplete = copy.deepcopy(contract)
    incomplete["capabilities"].pop("statusEndpoint")
    incomplete["capabilities"]["staticScenarioAssets"] = False
    defects = native_contract_defects(incomplete, matrix)
    require(len(defects) == 2, f"expected two capability defects, got {defects!r}")
    require("'statusEndpoint'" in defects[0] and "native.status-readiness" in defects[0], "statusEndpoint defect lacks consumer evidence")
    require("'staticScenarioAssets'" in defects[1] and "native.browser-routes" in defects[1], "staticScenarioAssets defect lacks consumer evidence")
    message = native_contract_error_message(incomplete, matrix)
    require(message is not None and message.startswith("Dash-Go Showcase contract does not satisfy Studio runtime contract matrix:"), "matrix error lacks fail-closed prefix")
    require("- missing capability 'statusEndpoint'" in message, "matrix error lacks precise status capability detail")
    require("- missing capability 'staticScenarioAssets'" in message, "matrix error lacks precise browser capability detail")

    wrong_shape = {"schema": 1, "contract": "dashgo-showcase/v1", "capabilities": []}
    shape_defects = native_contract_defects(wrong_shape, matrix)
    require(shape_defects == ["capabilities must be a JSON object"], f"wrong capability type was not rejected precisely: {shape_defects!r}")

    malformed = copy.deepcopy(matrix)
    malformed["assumptions"] = [row for row in malformed["assumptions"] if row.get("classification") != "legacy-only"]
    try:
        validate_runtime_contract_matrix(malformed)
    except RuntimeContractMatrixError as exc:
        require("classify" in str(exc), f"unexpected missing classification failure: {exc}")
    else:
        raise AssertionError("matrix missing a classification did not fail")

    print("PASS: Studio runtime-contract matrix hermetic tests succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
