#!/usr/bin/env python3
"""Generate Dash-Go browser assets from the staged source's own contract.

Modern Dash-Go sources own the authoritative generated-asset implementation in
cmd/dashboard-control-server/runtime_assets.go.  Studio executes that file as a
small temporary Go command so JavaScript minification and any future bundle
semantics cannot drift between the release and Showcase packaging.

The original manifest-only Python generator remains as a legacy fallback for
older source handoffs that do not expose the standalone runtime-assets helper.
"""
from __future__ import annotations

import argparse
import json
import os
import posixpath
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True


class AssetError(RuntimeError):
    pass


RUNTIME_ASSETS_REL = Path("cmd/dashboard-control-server/runtime_assets.go")
SOURCE_OWNED_MAIN = r'''package main

import (
    "fmt"
    "os"
)

type app struct{ dash string }

func main() {
    if len(os.Args) != 3 {
        fmt.Fprintln(os.Stderr, "usage: studio-asset-generator <source-root> <write|verify>")
        os.Exit(2)
    }
    write := false
    switch os.Args[2] {
    case "write":
        write = true
    case "verify":
    default:
        fmt.Fprintln(os.Stderr, "mode must be write or verify")
        os.Exit(2)
    }
    if err := verifyGeneratedAssets(os.Args[1], write); err != nil {
        fmt.Fprintln(os.Stderr, err)
        os.Exit(1)
    }
    fmt.Println("generated assets are current")
}
'''


def source_text(path: Path) -> str:
    value = path.read_text(encoding="utf-8")
    return value if value.endswith("\n") else value + "\n"


def manifest_files(
    app: Path,
    manifest_rel: str,
    root_rel: str,
    suffix: str,
    names: tuple[str, ...],
) -> dict[str, list[Path]]:
    path = app / manifest_rel
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise AssetError(f"invalid {manifest_rel}: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("schema") != 1 or not isinstance(raw.get("bundles"), dict):
        raise AssetError(f"invalid manifest shape: {manifest_rel}")
    bundles = raw["bundles"]
    out: dict[str, list[Path]] = {}
    seen: set[str] = set()
    if set(bundles) != set(names):
        raise AssetError(f"{manifest_rel} bundle names do not match {names}")
    for name in names:
        rows = bundles.get(name)
        if not isinstance(rows, list) or not rows:
            raise AssetError(f"{manifest_rel} {name} is empty")
        files: list[Path] = []
        for item in rows:
            if not isinstance(item, str) or not item or item.strip() != item or "\\" in item:
                raise AssetError(f"invalid source entry {item!r}")
            clean = posixpath.normpath(item)
            if item.startswith("/") or clean in (".", "..") or clean.startswith("../"):
                raise AssetError(f"unsafe source entry {item!r}")
            if clean in seen:
                raise AssetError(f"duplicate bundle source {clean}")
            candidate = app / root_rel / Path(*clean.split("/"))
            try:
                info = candidate.lstat()
            except OSError as exc:
                raise AssetError(f"invalid source file {candidate}: {exc}") from exc
            if candidate.suffix != suffix or stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                raise AssetError(f"invalid source file {candidate}")
            seen.add(clean)
            files.append(candidate)
        out[name] = files
    return out


def build_legacy_assets(app: Path, version: str) -> dict[Path, bytes]:
    js = manifest_files(app, "ui/js/bundle.manifest.json", "ui/js", ".js", ("app", "control"))
    css = manifest_files(app, "ui/css/bundle.manifest.json", "ui/css", ".css", ("dashboard", "control"))

    def js_bundle(name: str) -> bytes:
        control = name == "control"
        target = "ui/js/app.control.bundle.js" if control else "ui/js/app.bundle.js"
        kind = "control bundle" if control else "browser bundle"
        parts = [
            f"/* Dash-Go {version} {kind}. GENERATED as {target} from ui/js split source files; edit split files, not this bundle. */\n"
        ]
        for file in js[name]:
            parts.append(f"\n/* ===== {file.relative_to(app).as_posix()} ===== */\n{source_text(file)}")
        return "".join(parts).encode()

    def css_bundle(name: str, target: str) -> bytes:
        parts = [
            f"/* Dash-Go {version} {target} browser bundle.\n"
            f"   GENERATED from ui/css/{name} split source files; edit split files, not this bundle. */\n"
        ]
        for file in css[name]:
            parts.append(f"\n/* ---- {file.relative_to(app).as_posix()} ---- */\n{source_text(file)}")
        return "".join(parts).encode()

    return {
        app / "ui/js/app.bundle.js": js_bundle("app"),
        app / "ui/js/app.control.bundle.js": js_bundle("control"),
        app / "ui/dashboard.css": css_bundle("dashboard", "dashboard.css"),
        app / "ui/control-layout.css": css_bundle("control", "control-layout.css"),
    }


def run_legacy_generator(app: Path, version: str, verify: bool) -> None:
    expected = build_legacy_assets(app, version)
    for path, data in expected.items():
        if verify:
            if not path.is_file() or path.read_bytes() != data:
                raise AssetError(f"generated asset differs: {path.relative_to(app)}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    print(("VERIFIED" if verify else "GENERATED") + f": {len(expected)} legacy browser assets for Dash-Go {version}")


def run_source_owned_generator(app: Path, go_binary: Path, verify: bool) -> None:
    runtime_assets = app / RUNTIME_ASSETS_REL
    if not runtime_assets.is_file():
        raise AssetError(f"missing source-owned generated-asset implementation: {RUNTIME_ASSETS_REL.as_posix()}")
    if not (app / "go.mod").is_file():
        raise AssetError("source-owned generated-asset implementation requires app/go.mod")
    if not go_binary.is_file():
        raise AssetError(f"selected Go compiler is unavailable: {go_binary}")

    # Keep the helper inside the Dash-Go module so Go's internal-package rules
    # permit runtime_assets.go to import app/internal helpers.  It is removed in
    # every success/failure path and never enters the staged package.
    helper_root = Path(tempfile.mkdtemp(prefix=".studio-asset-generator-", dir=app))
    try:
        shutil.copy2(runtime_assets, helper_root / "runtime_assets.go")
        (helper_root / "main.go").write_text(SOURCE_OWNED_MAIN, encoding="utf-8")
        env = os.environ.copy()
        env.update({"GOTOOLCHAIN": "local", "GOWORK": "off", "GOFLAGS": "-mod=readonly"})
        command = [str(go_binary), "run", ".", str(app), "verify" if verify else "write"]
        try:
            result = subprocess.run(
                command,
                cwd=helper_root,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=540,
            )
        except subprocess.TimeoutExpired as exc:
            detail = (exc.stdout or "").strip() if isinstance(exc.stdout, str) else ""
            raise AssetError(
                "source-owned generated-asset command timed out"
                + (f": {detail}" if detail else "")
            ) from exc
        if result.returncode != 0:
            detail = result.stdout.strip() or "source-owned generator returned no output"
            raise AssetError(f"source-owned generated-asset command failed ({result.returncode}): {detail}")
        if "generated assets are current" not in result.stdout:
            raise AssetError("source-owned generated-asset command did not report success")
    finally:
        shutil.rmtree(helper_root, ignore_errors=True)

    action = "VERIFIED" if verify else "GENERATED"
    print(f"{action}: source-owned browser assets for Dash-Go {(app / 'VERSION').read_text(encoding='utf-8').strip()}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--go", type=Path, default=None)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    app = args.app.resolve()
    version = (app / "VERSION").read_text(encoding="utf-8").strip()
    if not version:
        raise AssetError("app/VERSION is empty")

    if (app / RUNTIME_ASSETS_REL).is_file():
        if args.go is None:
            raise AssetError("--go is required for a Dash-Go source-owned generated-asset implementation")
        run_source_owned_generator(app, args.go.resolve(), args.verify)
    else:
        run_legacy_generator(app, version, args.verify)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssetError as exc:
        raise SystemExit(f"ASSET ERROR: {exc}")
