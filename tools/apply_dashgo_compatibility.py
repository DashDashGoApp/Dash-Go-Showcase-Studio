#!/usr/bin/env python3
"""Apply one checked-in, fail-closed Dash-Go Showcase compatibility profile.

This bridge is temporary while Dash-Go Showcase Contract v1 is built. GitHub
release-asset SHA-256 remains an immutable provenance check. Profile selection
uses a narrow Dash-Go version window; the adapters themselves are the final,
fail-closed source-shape probe and reject any changed required anchor.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


class CompatibilityError(RuntimeError):
    pass


VERSION_RE = re.compile(r"(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?:-beta\.(?P<beta>\d+))?")
SHA256_RE = re.compile(r"[0-9a-f]{64}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path, label: str) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CompatibilityError(f"cannot read {label}: {exc}") from exc
    if not isinstance(payload, dict):
        raise CompatibilityError(f"{label} must be a JSON object")
    return payload


def parse_version(value: str, label: str = "Dash-Go version") -> tuple[int, int, int, int, int]:
    match = VERSION_RE.fullmatch(value)
    if not match:
        raise CompatibilityError(f"{label} must use X.Y.Z or X.Y.Z-beta.N")
    beta = match.group("beta")
    # A beta precedes the stable release with the same numeric core.
    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        0 if beta is not None else 1,
        int(beta or 0),
    )


def load_matrix(path: Path) -> dict:
    matrix = load_json(path, "compatibility matrix")
    profiles = matrix.get("profiles")
    if matrix.get("schema") != 2 or not isinstance(profiles, list) or not profiles:
        raise CompatibilityError("compatibility matrix schema must be 2 with a non-empty profiles array")
    return matrix


def load_release_version(app: Path) -> str:
    release = load_json(app / "release" / "release.json", "Dash-Go release metadata")
    version = release.get("version")
    if not isinstance(version, str):
        raise CompatibilityError("Dash-Go release metadata has an invalid version")
    parse_version(version, "Dash-Go release metadata version")
    version_file = app / "VERSION"
    if not version_file.is_file() or version_file.read_text(encoding="utf-8").strip() != version:
        raise CompatibilityError("Dash-Go app/VERSION does not match release metadata")
    return version


def source_policy(profile: dict) -> dict:
    policy = profile.get("sourcePolicy")
    if not isinstance(policy, dict):
        raise CompatibilityError(f"compatibility profile {profile['id']} has no source policy")
    if policy.get("selection") != "adapter-probe":
        raise CompatibilityError(f"compatibility profile {profile['id']} has an unsupported source selection policy")
    minimum = policy.get("minimumVersion")
    maximum = policy.get("maximumVersionExclusive")
    if not isinstance(minimum, str) or not isinstance(maximum, str):
        raise CompatibilityError(f"compatibility profile {profile['id']} has an invalid version window")
    if parse_version(minimum, "compatibility minimum version") >= parse_version(maximum, "compatibility maximum version"):
        raise CompatibilityError(f"compatibility profile {profile['id']} has an empty version window")
    return policy


def select_profile(matrix: dict, version: str, source_sha256: str) -> tuple[dict, dict]:
    actual_version = parse_version(version)
    if not SHA256_RE.fullmatch(source_sha256):
        raise CompatibilityError("source SHA-256 must be lowercase hexadecimal")
    matches: list[tuple[dict, dict]] = []
    for profile in matrix["profiles"]:
        if not isinstance(profile, dict) or not isinstance(profile.get("id"), str) or not profile["id"].strip():
            raise CompatibilityError("compatibility matrix has an invalid profile")
        policy = source_policy(profile)
        minimum = parse_version(policy["minimumVersion"], "compatibility minimum version")
        maximum = parse_version(policy["maximumVersionExclusive"], "compatibility maximum version")
        if minimum <= actual_version < maximum:
            matches.append((profile, policy))
    if len(matches) != 1:
        raise CompatibilityError(
            f"no single supported legacy profile matches Dash-Go {version}; "
            "the current version is outside the reviewed adapter-probe window or must migrate to Showcase Contract v1"
        )
    return matches[0]


def require_app_paths(app: Path, profile: dict) -> None:
    paths = profile.get("requiredAppPaths")
    if not isinstance(paths, list) or not paths:
        raise CompatibilityError(f"compatibility profile {profile['id']} has no required app paths")
    for relative in paths:
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise CompatibilityError(f"compatibility profile {profile['id']} contains an unsafe required app path")
        if not (app / relative).is_file():
            raise CompatibilityError(f"profile {profile['id']} requires missing staged app path: {relative}")


def run_adapter(source_root: Path, app: Path, adapter: dict, gofmt: str) -> str:
    adapter_id = adapter.get("id")
    script_relative = adapter.get("script")
    if not isinstance(adapter_id, str) or not adapter_id.strip() or not isinstance(script_relative, str):
        raise CompatibilityError("compatibility profile has an invalid adapter")
    relative = Path(script_relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise CompatibilityError(f"compatibility adapter {adapter_id} has an unsafe script path")
    script = source_root / relative
    if not script.is_file():
        raise CompatibilityError(f"compatibility adapter is missing: {script_relative}")
    command = [sys.executable, str(script), "--app", str(app)]
    if adapter.get("requiresGofmt") is True:
        gofmt_path = Path(gofmt)
        if not gofmt_path.is_file():
            raise CompatibilityError(f"compatibility adapter {adapter_id} requires a missing gofmt executable: {gofmt}")
        command.extend(("--gofmt", str(gofmt_path)))
    result = subprocess.run(command, cwd=source_root, check=False)
    if result.returncode != 0:
        raise CompatibilityError(f"adapter {adapter_id} failed with exit code {result.returncode}")
    return adapter_id


def write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--source-archive", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--gofmt", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--matrix", type=Path, default=None)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    source_root = args.source_root.resolve()
    app = args.app.resolve()
    archive = args.source_archive.resolve()
    matrix_path = (args.matrix or source_root / "tools" / "dashgo_compatibility.json").resolve()
    requested_sha = args.source_sha256.strip().lower()

    if not source_root.is_dir():
        raise CompatibilityError(f"Studio source root is missing: {source_root}")
    if not archive.is_file():
        raise CompatibilityError(f"source archive is missing: {archive}")
    if not SHA256_RE.fullmatch(requested_sha):
        raise CompatibilityError("requested source SHA-256 must be lowercase hexadecimal")
    actual_sha = sha256(archive)
    if requested_sha != actual_sha:
        raise CompatibilityError(f"source archive SHA-256 mismatch: requested {requested_sha}; actual {actual_sha}")
    if not app.is_dir():
        raise CompatibilityError(f"staged Dash-Go app directory is missing: {app}")

    version = load_release_version(app)
    profile, policy = select_profile(load_matrix(matrix_path), version, actual_sha)
    require_app_paths(app, profile)
    checks = profile.get("requiredCandidateChecks")
    adapters = profile.get("adapters")
    if not isinstance(checks, list) or not all(isinstance(item, str) and item for item in checks):
        raise CompatibilityError(f"compatibility profile {profile['id']} has invalid required candidate checks")
    if not isinstance(adapters, list) or not adapters:
        raise CompatibilityError(f"compatibility profile {profile['id']} has no adapters")

    report = {
        "schema": 2,
        "result": "PASS",
        "profile": profile["id"],
        "dashGoVersion": version,
        "dashGoSourceSha256": actual_sha,
        "sourcePolicy": policy,
        "requiredCandidateChecks": checks,
        "adapters": [],
    }
    if not args.check_only:
        for adapter in adapters:
            if not isinstance(adapter, dict):
                raise CompatibilityError(f"compatibility profile {profile['id']} has an invalid adapter")
            report["adapters"].append(run_adapter(source_root, app, adapter, args.gofmt))
    write_report(args.report, report)
    print(f"PASS: Dash-Go Showcase compatibility profile {profile['id']} accepted Dash-Go {version} ({actual_sha})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CompatibilityError as exc:
        raise SystemExit("SHOWCASE COMPATIBILITY ERROR: " + str(exc))