#!/usr/bin/env python3
"""Hermetic regression tests for Studio's Dash-Go generated-asset bridge."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools/generate_dashgo_assets.py"

SOURCE_OWNED_RUNTIME_ASSETS = r'''package main

import (
    "fmt"
    "os"
    "path/filepath"
)

func (a *app) runVerifyGeneratedAssetsCLI(args []string) int { return 0 }

func verifyGeneratedAssets(root string, write bool) error {
    target := filepath.Join(root, "ui", "js", "app.bundle.js")
    expected := []byte("/* source-owned */\nconst retainedIdentifier=1;\n")
    if write {
        if err := os.MkdirAll(filepath.Dir(target), 0755); err != nil { return err }
        return os.WriteFile(target, expected, 0644)
    }
    body, err := os.ReadFile(target)
    if err != nil { return err }
    if string(body) != string(expected) { return fmt.Errorf("stale source-owned asset") }
    return nil
}
'''


def write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def run(*args: str, expect: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, str(GENERATOR), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != expect:
        raise AssertionError(
            f"generator returned {result.returncode}, expected {expect}:\n{result.stdout}"
        )
    return result


def source_owned_case(go_binary: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="studio-source-owned-assets-") as raw:
        app = Path(raw) / "app"
        write(app / "VERSION", "9.9.9\n")
        write(app / "go.mod", "module example.test/dashgo\n\ngo 1.23\n")
        write(app / "cmd/dashboard-control-server/runtime_assets.go", SOURCE_OWNED_RUNTIME_ASSETS)
        run("--app", str(app), "--go", str(go_binary))
        target = app / "ui/js/app.bundle.js"
        expected = "/* source-owned */\nconst retainedIdentifier=1;\n"
        if target.read_text(encoding="utf-8") != expected:
            raise AssertionError("Studio did not use the staged source-owned Go generator")
        verified = run("--app", str(app), "--go", str(go_binary), "--verify")
        if "source-owned browser assets" not in verified.stdout:
            raise AssertionError("source-owned verification did not report its selected path")
        target.write_text("tampered\n", encoding="utf-8")
        failed = run("--app", str(app), "--go", str(go_binary), "--verify", expect=1)
        if "stale source-owned asset" not in failed.stdout:
            raise AssertionError("source-owned verifier did not reject a stale generated asset")
        leftovers = [path for path in app.iterdir() if path.name.startswith(".studio-asset-generator-")]
        if leftovers:
            raise AssertionError(f"temporary source-owned helper was not removed: {leftovers}")


def legacy_case() -> None:
    with tempfile.TemporaryDirectory(prefix="studio-legacy-assets-") as raw:
        app = Path(raw) / "app"
        write(app / "VERSION", "1.0.0\n")
        write(app / "ui/js/app.js", "window.app=true;\n")
        write(app / "ui/js/control.js", "window.control=true;\n")
        write(
            app / "ui/js/bundle.manifest.json",
            json.dumps({"schema": 1, "bundles": {"app": ["app.js"], "control": ["control.js"]}}) + "\n",
        )
        write(app / "ui/css/dashboard/base.css", "body{}\n")
        write(app / "ui/css/control/base.css", ".control{}\n")
        write(
            app / "ui/css/bundle.manifest.json",
            json.dumps(
                {
                    "schema": 1,
                    "bundles": {
                        "dashboard": ["dashboard/base.css"],
                        "control": ["control/base.css"],
                    },
                }
            )
            + "\n",
        )
        generated = run("--app", str(app))
        if "legacy browser assets" not in generated.stdout:
            raise AssertionError("legacy source did not select the manifest-only fallback")
        run("--app", str(app), "--verify")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--go", type=Path, required=True)
    args = parser.parse_args()
    go_binary = args.go.resolve()
    if not go_binary.is_file():
        raise SystemExit(f"selected Go compiler is unavailable: {go_binary}")
    source_owned_case(go_binary)
    legacy_case()
    print("PASS: Studio uses Dash-Go's source-owned asset generator and retains a legacy-only fallback")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
