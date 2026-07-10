#!/usr/bin/env python3
"""Exercise the native Stage browser-contract path with its validated matrix."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE_PACKAGE = ROOT / "ci/stage-package.py"


def load_stage_package():
    spec = importlib.util.spec_from_file_location("studio_stage_package_native_contract_test", STAGE_PACKAGE)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load ci/stage-package.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    stage = load_stage_package()
    matrix = stage.load_runtime_contract_matrix(ROOT)
    native = matrix["nativeContract"]
    contract = {
        "schema": native["schema"],
        "contract": native["contract"],
        "capabilities": {
            row["id"]: True
            for row in native["requiredCapabilities"]
        },
    }

    with tempfile.TemporaryDirectory(prefix="studio-stage-native-contract-") as raw:
        app = Path(raw) / "app"
        required = (
            "cmd/dashboard-control-server/showcase_contract.go",
            "cmd/dashboard-control-server/showcase_contract_calendar.go",
            "cmd/dashboard-control-server/showcase_contract_http.go",
            "release/showcase-contract.json",
        )
        for relative in required:
            path = app / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if relative.endswith(".json"):
                path.write_text(json.dumps(contract, sort_keys=True) + "\n", encoding="utf-8")
            else:
                path.write_text("package main\n", encoding="utf-8")

        # This is the exact Phase 4 native path that failed for Dash-Go 1.5.9.
        # Passing four values proves the helper carries the matrix into the
        # three-argument verifier rather than raising a late TypeError.
        stage.showcase_tour_guard_view_contract(None, app, contract, matrix)

        try:
            stage.showcase_tour_guard_view_contract(None, app, contract, None)
        except stage.BuildFailure as exc:
            if exc.kind != "Runtime contract matrix" or "missing" not in str(exc):
                raise AssertionError(f"unexpected missing-matrix failure: {exc.kind}: {exc}") from exc
        else:
            raise AssertionError("native browser-contract validation accepted a missing matrix")

    print("PASS: Stage native browser-contract validation carries the runtime-contract matrix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
