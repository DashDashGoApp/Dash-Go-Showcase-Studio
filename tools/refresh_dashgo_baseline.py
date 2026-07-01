#!/usr/bin/env python3
"""Fail-closed Dash-Go baseline refresh helper for Showcase Studio."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

class RefreshError(RuntimeError):
    pass

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def studio_tuple(value: str) -> tuple[int, int, int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:-test\.(\d+))?", value)
    if not match:
        raise RefreshError("Studio version must use X.Y.Z or X.Y.Z-test.N")
    return tuple(int(part or 0) for part in match.groups())

def validate_dashgo_version(value: str) -> None:
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-beta\.\d+)?", value):
        raise RefreshError("Dash-Go version must use X.Y.Z or X.Y.Z-beta.N")

def validate_archive(archive: Path, version: str) -> tuple[str, str]:
    root = f"dash-go-source-{version}"
    required = {
        f"{root}/app/VERSION", f"{root}/app/release/release.json",
        f"{root}/app/cmd/dashboard-control-server/main.go", f"{root}/app/ui/js/bundle.manifest.json",
    }
    try:
        with tarfile.open(archive, "r:gz") as tar:
            names = [member.name.replace("\\", "/") for member in tar.getmembers()]
            if not names or not all(name == root or name.startswith(root + "/") for name in names):
                raise RefreshError(f"Dash-Go source archive must have exactly one root named {root}")
            if not required.issubset(names):
                raise RefreshError("Dash-Go source archive is missing required release entrypoints")
            version_file = tar.extractfile(f"{root}/app/VERSION")
            release_file = tar.extractfile(f"{root}/app/release/release.json")
            if version_file is None or release_file is None:
                raise RefreshError("Dash-Go source archive could not read version contract")
            app_version = version_file.read().decode("utf-8").strip()
            release_version = json.loads(release_file.read().decode("utf-8")).get("version")
    except tarfile.TarError as exc:
        raise RefreshError(f"cannot read Dash-Go source archive: {exc}") from exc
    if app_version != version or release_version != version:
        raise RefreshError(f"Dash-Go version contract mismatch: app/VERSION={app_version!r}, release={release_version!r}, expected={version!r}")
    return root, sha256(archive)

def extract_checked(archive: Path, target: Path, root: str) -> Path:
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            name = member.name.replace("\\", "/")
            if not name or name.startswith("/") or name.startswith("../") or "/../" in name:
                raise RefreshError(f"unsafe Dash-Go archive member: {member.name}")
            if member.issym() or member.islnk() or not (member.isdir() or member.isfile()):
                raise RefreshError(f"unsupported Dash-Go archive member: {member.name}")
        try:
            tar.extractall(target, filter="fully_trusted")
        except TypeError:
            tar.extractall(target)
    app = target / root / "app"
    if not (app / "go.mod").is_file():
        raise RefreshError("extracted Dash-Go app is missing go.mod")
    return app

def overlay_preflight(source_root: Path, archive: Path, root: str) -> None:
    patcher = source_root / "tools" / "patch_dashgo_engine.py"
    with tempfile.TemporaryDirectory(prefix="dashgo-showcase-refresh-") as raw:
        app = extract_checked(archive, Path(raw), root)
        result = subprocess.run(
            [sys.executable, str(patcher), "--app", str(app)], cwd=source_root,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, check=False,
        )
        if result.returncode:
            detail = result.stdout.strip()
            raise RefreshError(
                "Showcase overlay anchors do not match the proposed Dash-Go baseline. No source file was changed; update the overlay deliberately before retrying."
                + (f"\n{detail[-4000:]}" if detail else "")
            )

def replace_text(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace(old, new), encoding="utf-8")

def update_docs(root: Path, old_studio: str, new_studio: str, old_dashgo: str, new_dashgo: str) -> None:
    for relative in ("README.md", "CURRENT_STATE.md", "SHOWCASE_STUDIO_2.0_CONTRACT.md", "PORTABLE_RUNTIME_OVERLAY.md"):
        replace_text(root / relative, old_studio, new_studio)
        replace_text(root / relative, f"Dash-Go {old_dashgo}", f"Dash-Go {new_dashgo}")
        replace_text(root / relative, f"baseline: `{old_dashgo}`", f"baseline: `{new_dashgo}`")
    changelog = root / "CHANGELOG.md"
    prior = changelog.read_text(encoding="utf-8")
    entry = (
        f"## {new_studio}\n\n"
        f"- Refreshed the pinned Dash-Go source from `{old_dashgo}` to `{new_dashgo}` after exact archive, version, SHA-256, and overlay-anchor preflight validation.\n"
        "- The refresh stayed fail-closed: source-anchor drift requires a deliberate overlay update and cannot be auto-merged.\n\n"
    )
    if not prior.startswith(f"# Changelog\n\n## {new_studio}"):
        changelog.write_text(prior.replace("# Changelog\n\n", "# Changelog\n\n" + entry, 1), encoding="utf-8")

def apply_refresh(root: Path, archive: Path, dashgo_version: str, studio_version: str, archive_hash: str) -> Path:
    manifest_path = root / "studio.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    old_studio = str(manifest["studioVersion"])
    old_dashgo = str(manifest["dashGoVersion"])
    relative = f"engine/Dash-Go_{dashgo_version}_source.tar.gz"
    target = root / relative
    stage = target.with_name("." + target.name + ".stage")
    shutil.copy2(archive, stage)
    if sha256(stage) != archive_hash:
        stage.unlink(missing_ok=True)
        raise RefreshError("archive SHA-256 changed while staging the baseline refresh")
    os.replace(stage, target)
    old_archive = root / str(manifest["dashGoSourceArchive"])
    if old_archive != target and old_archive.is_file():
        old_archive.unlink()
    manifest.update({
        "studioVersion": studio_version,
        "dashGoVersion": dashgo_version,
        "dashGoSourceArchive": relative,
        "dashGoSourceSha256": archive_hash,
    })
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    ignore = root / ".gitignore"
    ignore.write_text(re.sub(r"!engine/Dash-Go_[^\n]+_source\.tar\.gz", f"!engine/Dash-Go_{dashgo_version}_source.tar.gz", ignore.read_text(encoding="utf-8")), encoding="utf-8")
    update_docs(root, old_studio, studio_version, old_dashgo, dashgo_version)
    return target

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--dashgo-version", required=True)
    parser.add_argument("--studio-version", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    archive = args.archive.resolve()
    validate_dashgo_version(args.dashgo_version)
    if not archive.is_file():
        raise RefreshError(f"Dash-Go source archive is missing: {archive}")
    manifest = json.loads((root / "studio.manifest.json").read_text(encoding="utf-8"))
    old_studio = str(manifest.get("studioVersion", ""))
    old_dashgo = str(manifest.get("dashGoVersion", ""))
    if studio_tuple(args.studio_version) <= studio_tuple(old_studio):
        raise RefreshError(f"new Studio version must be newer than {old_studio}")
    archive_root, archive_hash = validate_archive(archive, args.dashgo_version)
    overlay_preflight(root, archive, archive_root)
    report = {
        "schema": 1, "result": "APPLIED" if args.apply else "READY", "sourceRoot": str(root),
        "currentStudioVersion": old_studio, "newStudioVersion": args.studio_version,
        "currentDashGoVersion": old_dashgo, "newDashGoVersion": args.dashgo_version,
        "archive": str(archive), "archiveSha256": archive_hash, "archiveRoot": archive_root,
        "overlayPreflight": "PASS", "apply": bool(args.apply),
    }
    if args.apply:
        report["installedArchive"] = str(apply_refresh(root, archive, args.dashgo_version, args.studio_version, archive_hash))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"BASELINE REFRESH {report['result']}: Dash-Go {old_dashgo} -> {args.dashgo_version}; Studio {old_studio} -> {args.studio_version}")
    print(f"Report: {args.report}")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RefreshError as exc:
        raise SystemExit(f"BASELINE REFRESH ERROR: {exc}")
