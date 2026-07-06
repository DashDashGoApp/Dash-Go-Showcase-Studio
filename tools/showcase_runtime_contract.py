#!/usr/bin/env python3
"""Shared native Showcase Contract v1 matrix loader and fail-closed validator."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

MATRIX_RELATIVE_PATH = Path("internal/studiohost/dashgo_runtime_contract_matrix.json")
EXPECTED_CLASSIFICATIONS = frozenset({"contract-owned", "legacy-only", "studio-owned"})
EXPECTED_CATEGORIES = frozenset({"path", "binary", "calendars", "fixture-data", "readiness", "browser-url"})


class RuntimeContractMatrixError(RuntimeError):
    """Raised when the Studio-owned runtime-contract matrix is malformed."""


def require_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeContractMatrixError(f"runtime contract matrix {label} must be a non-empty string")
    return value.strip()


def matrix_path(root: Path) -> Path:
    return root.resolve() / MATRIX_RELATIVE_PATH


def load_runtime_contract_matrix(root: Path) -> dict[str, Any]:
    path = matrix_path(root)
    if not path.is_file():
        raise RuntimeContractMatrixError(f"runtime contract matrix is missing: {path}")
    try:
        matrix = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeContractMatrixError(f"runtime contract matrix is invalid JSON: {exc}") from exc
    validate_runtime_contract_matrix(matrix)
    return matrix


def validate_browser_routes(routes: object, label: str, *, require_studio_owned: bool) -> None:
    if not isinstance(routes, list) or not routes:
        raise RuntimeContractMatrixError(f"runtime contract matrix {label} must be a non-empty list")
    for index, row in enumerate(routes):
        if not isinstance(row, dict):
            raise RuntimeContractMatrixError(f"runtime contract matrix {label}[{index}] must be an object")
        path = require_string(row.get("path"), f"{label}[{index}].path")
        if not path.startswith("/"):
            raise RuntimeContractMatrixError(f"runtime contract matrix browser route {path!r} must start with /")
        require_string(row.get("contains"), f"{label}[{index}].contains")
        if not isinstance(row.get("parseJSON"), bool):
            raise RuntimeContractMatrixError(f"runtime contract matrix browser route {path!r} parseJSON must be boolean")
        if require_studio_owned and row.get("classification") != "studio-owned":
            raise RuntimeContractMatrixError(f"runtime contract matrix browser route {path!r} must be classified studio-owned")


def validate_runtime_contract_matrix(matrix: object) -> None:
    if not isinstance(matrix, dict):
        raise RuntimeContractMatrixError("runtime contract matrix root must be an object")
    if matrix.get("schema") != 1:
        raise RuntimeContractMatrixError("runtime contract matrix schema must be 1")

    native = matrix.get("nativeContract")
    if not isinstance(native, dict):
        raise RuntimeContractMatrixError("runtime contract matrix nativeContract must be an object")
    if native.get("schema") != 1:
        raise RuntimeContractMatrixError("runtime contract matrix nativeContract.schema must be 1")
    require_string(native.get("contract"), "nativeContract.contract")
    require_string(native.get("declarationPath"), "nativeContract.declarationPath")

    capabilities = native.get("requiredCapabilities")
    if not isinstance(capabilities, list) or not capabilities:
        raise RuntimeContractMatrixError("runtime contract matrix nativeContract.requiredCapabilities must be a non-empty list")
    seen_capabilities: set[str] = set()
    for index, row in enumerate(capabilities):
        if not isinstance(row, dict):
            raise RuntimeContractMatrixError(f"runtime contract matrix requiredCapabilities[{index}] must be an object")
        capability = require_string(row.get("id"), f"requiredCapabilities[{index}].id")
        if capability in seen_capabilities:
            raise RuntimeContractMatrixError(f"runtime contract matrix has duplicate required capability {capability!r}")
        seen_capabilities.add(capability)
        require_string(row.get("reason"), f"requiredCapabilities[{index}].reason")
        consumers = row.get("consumers")
        if not isinstance(consumers, list) or not consumers or any(not isinstance(item, str) or not item.strip() for item in consumers):
            raise RuntimeContractMatrixError(f"runtime contract matrix requiredCapabilities[{index}].consumers must be a non-empty string list")

    activation = native.get("activation")
    if not isinstance(activation, dict):
        raise RuntimeContractMatrixError("runtime contract matrix nativeContract.activation must be an object")
    profile = activation.get("runtimeProfile")
    manifest = activation.get("scenarioManifest")
    data_root = activation.get("dataRoot")
    for label, row in (("runtimeProfile", profile), ("scenarioManifest", manifest), ("dataRoot", data_root)):
        if not isinstance(row, dict):
            raise RuntimeContractMatrixError(f"runtime contract matrix nativeContract.activation.{label} must be an object")
        require_string(row.get("environment"), f"nativeContract.activation.{label}.environment")
    require_string(profile.get("value") if isinstance(profile, dict) else None, "nativeContract.activation.runtimeProfile.value")
    for label, row in (("scenarioManifest", manifest), ("dataRoot", data_root)):
        require_string(row.get("relativePath") if isinstance(row, dict) else None, f"nativeContract.activation.{label}.relativePath")

    readiness = native.get("readiness")
    if not isinstance(readiness, dict):
        raise RuntimeContractMatrixError("runtime contract matrix nativeContract.readiness must be an object")
    for key in ("livenessPath", "statusPath", "profile", "problems"):
        require_string(readiness.get(key), f"nativeContract.readiness.{key}")
    cache = readiness.get("cache")
    if not isinstance(cache, dict) or cache.get("rebuilt") is not True:
        raise RuntimeContractMatrixError("runtime contract matrix nativeContract.readiness.cache must require rebuilt=true")
    for key in ("minimumEvents", "minimumWritebackCandidates"):
        value = cache.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise RuntimeContractMatrixError(f"runtime contract matrix nativeContract.readiness.cache.{key} must be a positive integer")

    calendars = native.get("calendars")
    if not isinstance(calendars, list) or not calendars:
        raise RuntimeContractMatrixError("runtime contract matrix nativeContract.calendars must be a non-empty list")
    seen_calendars: set[str] = set()
    writable = 0
    for index, row in enumerate(calendars):
        if not isinstance(row, dict):
            raise RuntimeContractMatrixError(f"runtime contract matrix calendars[{index}] must be an object")
        source = require_string(row.get("source"), f"calendars[{index}].source")
        if source in seen_calendars:
            raise RuntimeContractMatrixError(f"runtime contract matrix has duplicate calendar source {source!r}")
        seen_calendars.add(source)
        mode = require_string(row.get("mode"), f"calendars[{index}].mode")
        if mode not in {"writable", "fixture-only"}:
            raise RuntimeContractMatrixError(f"runtime contract matrix calendar {source!r} has unsupported mode {mode!r}")
        require_string(row.get("expectedEventMarker"), f"calendars[{index}].expectedEventMarker")
        if mode == "writable":
            writable += 1
            candidates = row.get("minimumWritebackCandidates")
            if isinstance(candidates, bool) or not isinstance(candidates, int) or candidates < 1:
                raise RuntimeContractMatrixError(f"runtime contract matrix writable calendar {source!r} must require positive writeback candidates")
    if writable != 4:
        raise RuntimeContractMatrixError(f"runtime contract matrix must declare exactly four writable calendars; found {writable}")

    validate_browser_routes(native.get("browserRoutes"), "nativeContract.browserRoutes", require_studio_owned=True)

    assumptions = matrix.get("assumptions")
    if not isinstance(assumptions, list) or not assumptions:
        raise RuntimeContractMatrixError("runtime contract matrix assumptions must be a non-empty list")
    seen_assumptions: set[str] = set()
    categories: set[str] = set()
    classifications: set[str] = set()
    for index, row in enumerate(assumptions):
        if not isinstance(row, dict):
            raise RuntimeContractMatrixError(f"runtime contract matrix assumptions[{index}] must be an object")
        ident = require_string(row.get("id"), f"assumptions[{index}].id")
        if ident in seen_assumptions:
            raise RuntimeContractMatrixError(f"runtime contract matrix has duplicate assumption {ident!r}")
        seen_assumptions.add(ident)
        classification = require_string(row.get("classification"), f"assumptions[{index}].classification")
        if classification not in EXPECTED_CLASSIFICATIONS:
            raise RuntimeContractMatrixError(f"runtime contract matrix assumption {ident!r} has unsupported classification {classification!r}")
        classifications.add(classification)
        category = require_string(row.get("category"), f"assumptions[{index}].category")
        if category not in EXPECTED_CATEGORIES:
            raise RuntimeContractMatrixError(f"runtime contract matrix assumption {ident!r} has unsupported category {category!r}")
        categories.add(category)
        require_string(row.get("value"), f"assumptions[{index}].value")
        require_string(row.get("detail"), f"assumptions[{index}].detail")
    if classifications != EXPECTED_CLASSIFICATIONS:
        raise RuntimeContractMatrixError("runtime contract matrix must classify contract-owned, legacy-only, and studio-owned assumptions")
    if categories != EXPECTED_CATEGORIES:
        raise RuntimeContractMatrixError("runtime contract matrix must inventory paths, binaries, calendars, fixture data, readiness, and browser URLs")

    legacy = matrix.get("legacyBridge")
    if not isinstance(legacy, dict) or legacy.get("classification") != "legacy-only":
        raise RuntimeContractMatrixError("runtime contract matrix legacyBridge must be legacy-only")
    for key in ("profile", "minimumVersion", "maximumVersionExclusive", "fallbackRule"):
        require_string(legacy.get(key), f"legacyBridge.{key}")
    validate_browser_routes(legacy.get("browserRoutes"), "legacyBridge.browserRoutes", require_studio_owned=True)


def required_capabilities(matrix: dict[str, Any]) -> tuple[str, ...]:
    native = matrix["nativeContract"]
    return tuple(row["id"] for row in native["requiredCapabilities"])


def native_contract_name(matrix: dict[str, Any]) -> str:
    return str(matrix["nativeContract"]["contract"])


def native_contract_declaration_path(matrix: dict[str, Any]) -> str:
    return str(matrix["nativeContract"]["declarationPath"])


def native_contract_defects(payload: object, matrix: dict[str, Any]) -> list[str]:
    """Return human-actionable native-contract defects in a deterministic order."""
    native = matrix["nativeContract"]
    if not isinstance(payload, dict):
        return ["declaration must be a JSON object"]

    defects: list[str] = []
    if payload.get("schema") != native["schema"]:
        defects.append(f"schema must be {native['schema']}; found {payload.get('schema')!r}")
    if payload.get("contract") != native["contract"]:
        defects.append(f"contract must be {native['contract']!r}; found {payload.get('contract')!r}")

    capabilities = payload.get("capabilities")
    if not isinstance(capabilities, dict):
        defects.append("capabilities must be a JSON object")
        return defects

    for row in native["requiredCapabilities"]:
        capability = row["id"]
        if capabilities.get(capability) is not True:
            consumers = ", ".join(row["consumers"])
            defects.append(f"missing capability {capability!r} required by {consumers}: {row['reason']}")
    return defects


def native_contract_error_message(payload: object, matrix: dict[str, Any], *, context: str = "Dash-Go Showcase contract") -> str | None:
    defects = native_contract_defects(payload, matrix)
    if not defects:
        return None
    return context + " does not satisfy Studio runtime contract matrix:\n" + "\n".join(f"- {defect}" for defect in defects)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def native_runtime_plan_evidence(
    payload: object,
    matrix: dict[str, Any],
    *,
    matrix_sha256: str,
    declaration_sha256: str,
) -> dict[str, Any]:
    """Return the exact native plan proven by a validated Dash-Go declaration.

    This is intentionally a compact, JSON-only witness. It carries no private
    machine paths and can be re-derived by Windows from the staged contract.
    """
    message = native_contract_error_message(payload, matrix)
    if message is not None:
        raise RuntimeContractMatrixError(message)
    if not isinstance(payload, dict):  # defensive; native_contract_error_message already rejects this.
        raise RuntimeContractMatrixError("native contract declaration must be an object")
    if not isinstance(matrix_sha256, str) or len(matrix_sha256) != 64:
        raise RuntimeContractMatrixError("runtime contract matrix SHA-256 is invalid")
    if not isinstance(declaration_sha256, str) or len(declaration_sha256) != 64:
        raise RuntimeContractMatrixError("native contract declaration SHA-256 is invalid")

    native = matrix["nativeContract"]
    verified_capabilities = []
    for row in native["requiredCapabilities"]:
        verified_capabilities.append(
            {
                "id": row["id"],
                "verified": True,
                "reason": row["reason"],
                "consumers": list(row["consumers"]),
            }
        )

    writable_calendars = []
    for calendar in native["calendars"]:
        if calendar["mode"] == "writable":
            writable_calendars.append(
                {
                    "source": calendar["source"],
                    "expectedEventMarker": calendar["expectedEventMarker"],
                    "minimumWritebackCandidates": calendar["minimumWritebackCandidates"],
                }
            )

    return {
        "schema": 1,
        "contract": native_contract_name(matrix),
        "matrix": {
            "path": MATRIX_RELATIVE_PATH.as_posix(),
            "sha256": matrix_sha256.lower(),
        },
        "declaration": {
            "path": native_contract_declaration_path(matrix),
            "sha256": declaration_sha256.lower(),
            "schema": payload["schema"],
            "contract": payload["contract"],
        },
        "verifiedCapabilities": verified_capabilities,
        "resolvedRuntimePlan": {
            "activation": deepcopy(native["activation"]),
            "readiness": deepcopy(native["readiness"]),
            "writableCalendars": writable_calendars,
            "browserRoutes": deepcopy(native["browserRoutes"]),
        },
    }


def native_runtime_plan_evidence_from_files(root: Path, declaration_path: Path) -> dict[str, Any]:
    matrix = load_runtime_contract_matrix(root)
    if not declaration_path.is_file():
        raise RuntimeContractMatrixError(f"native contract declaration is missing: {declaration_path}")
    try:
        payload = json.loads(declaration_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeContractMatrixError(f"native contract declaration is invalid JSON: {exc}") from exc
    return native_runtime_plan_evidence(
        payload,
        matrix,
        matrix_sha256=sha256_file(matrix_path(root)),
        declaration_sha256=sha256_file(declaration_path),
    )


def validate_native_runtime_plan_evidence(
    evidence: object,
    payload: object,
    matrix: dict[str, Any],
    *,
    matrix_sha256: str,
    declaration_sha256: str,
) -> None:
    expected = native_runtime_plan_evidence(
        payload,
        matrix,
        matrix_sha256=matrix_sha256,
        declaration_sha256=declaration_sha256,
    )
    if not isinstance(evidence, dict):
        raise RuntimeContractMatrixError("native runtime plan evidence must be a JSON object")
    if set(evidence) != set(expected):
        raise RuntimeContractMatrixError("native runtime plan evidence has an unexpected field set")
    for field, value in expected.items():
        if evidence.get(field) != value:
            raise RuntimeContractMatrixError(f"native runtime plan evidence mismatch at {field}")
