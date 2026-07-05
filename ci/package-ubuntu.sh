#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 && $# -ne 3 ]]; then
  echo "usage: package-ubuntu.sh <native-work-directory> <artifact-directory> [candidate-origin-json]" >&2
  exit 64
fi

work="$1"
output="$2"
candidate_origin="${3:-}"
source="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -n "$candidate_origin" && ! -f "$candidate_origin" ]]; then
  echo "candidate origin JSON is missing: $candidate_origin" >&2
  exit 64
fi

rm -rf "$work" "$output"
mkdir -p "$work" "$output"

export PYTHONDONTWRITEBYTECODE=1
export GOTOOLCHAIN=local

python3 "$source/ci/stage-package.py" \
  --source "$source" \
  --kit "$source" \
  --work "$work" \
  --go "$(command -v go)" \
  --node node \
  --targets windows,linux \
  --performance safe

python3 - "$source" "$work/summary.json" "$output" "$candidate_origin" <<'PY'
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

NATIVE_SHOWCASE_CONTRACT = "dashgo-showcase/v1"

source = Path(sys.argv[1]).resolve()
summary_path = Path(sys.argv[2]).resolve()
output = Path(sys.argv[3]).resolve()
origin_argument = sys.argv[4].strip()

summary = json.loads(summary_path.read_text(encoding="utf-8"))
if summary.get("result") != "PASS":
    raise SystemExit("staging summary did not report PASS")

windows_stage = Path(summary["windowsStage"]).resolve()
linux_deb = Path(summary["linuxDeb"]).resolve()

if not windows_stage.is_dir():
    raise SystemExit(f"Windows staging payload is missing: {windows_stage}")
if not linux_deb.is_file():
    raise SystemExit(f"Linux Debian package is missing: {linux_deb}")

output.mkdir(parents=True, exist_ok=True)

windows_archive = output / "windows-stage.tar.gz"
with tarfile.open(windows_archive, "w:gz", dereference=False) as archive:
    archive.add(windows_stage, arcname="windows", recursive=True)

linux_output = output / linux_deb.name
shutil.copy2(linux_deb, linux_output)

for name in (
    "summary.json",
    "run.json",
    "events.jsonl",
    "performance.json",
    "timing.json",
):
    candidate = summary_path.parent / name
    if candidate.is_file():
        shutil.copy2(candidate, output / name)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def required_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(f"candidate origin is missing {label}")
    return value.strip()


def required_positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SystemExit(f"candidate origin {label} must be a positive integer")
    return value


def required_sha256(value: object, label: str) -> str:
    normalized = required_string(value, label).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", normalized):
        raise SystemExit(f"candidate origin {label} must be a SHA-256 digest")
    return normalized


manifest = json.loads((source / "studio.manifest.json").read_text(encoding="utf-8"))
studio_commit = subprocess.check_output(
    ["git", "-C", str(source), "rev-parse", "HEAD"],
    text=True,
).strip()
dashgo_version = str(summary["dashGoVersion"])
release_package_version = required_string(summary.get("releasePackageVersion"), "staging releasePackageVersion")
if not re.fullmatch(r"\d+\.\d+\.\d+(?:-(?:test\.\d+|r[1-9]\d*))?", release_package_version):
    raise SystemExit("staging releasePackageVersion is invalid")
dashgo_hash = required_sha256(manifest["dashGoSourceSha256"], "manifest Dash-Go source SHA-256")
showcase_runtime_mode = required_string(summary.get("showcaseRuntimeMode"), "staging showcaseRuntimeMode")
if showcase_runtime_mode not in ("legacy-bridge", "native-contract"):
    raise SystemExit("staging showcaseRuntimeMode is invalid")

if origin_argument:
    origin_path = Path(origin_argument).resolve()
    try:
        origin = json.loads(origin_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"candidate origin JSON is unreadable: {exc}") from exc
else:
    origin = {
        "schema": 1,
        "candidateOrigin": "manual",
        "purpose": "manual package candidate only",
        "dashGoVersion": dashgo_version,
        "releasePackageVersion": release_package_version,
        "dashGoSourceSha256": dashgo_hash,
        "dashGoRelease": None,
    }

origin_schema = origin.get("schema")
if origin_schema not in (1, 2):
    raise SystemExit("candidate origin schema must be 1 or 2")
origin_kind = required_string(origin.get("candidateOrigin"), "candidateOrigin")
purpose = required_string(origin.get("purpose"), "purpose")
draft_prepublication = False
native_beta = False

if origin_kind == "manual":
    if origin_schema != 1 or purpose != "manual package candidate only" or origin.get("dashGoRelease") is not None:
        raise SystemExit("manual candidate origin has an invalid release payload")
elif origin_kind == "dashgo-stable-release":
    if origin_schema != 1 or purpose != "stable release package candidate only":
        raise SystemExit("stable-release candidate origin has an invalid purpose")
    release = origin.get("dashGoRelease")
    if not isinstance(release, dict):
        raise SystemExit("stable-release candidate origin lacks dashGoRelease")
    version = required_string(release.get("version"), "dashGoRelease.version")
    tag = required_string(release.get("releaseTag"), "dashGoRelease.releaseTag")
    if version != dashgo_version or tag != f"v{dashgo_version}":
        raise SystemExit("stable-release origin version/tag does not match staged Dash-Go version")
    if required_string(release.get("repository"), "dashGoRelease.repository") != "DashDashGoApp/Dash-Go":
        raise SystemExit("stable-release origin repository is not DashDashGoApp/Dash-Go")
    if release.get("immutable") is not True:
        raise SystemExit("stable-release origin is not immutable")
    tag_commit = required_string(release.get("tagCommit"), "dashGoRelease.tagCommit").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", tag_commit):
        raise SystemExit("stable-release origin tag commit is invalid")
    source_asset = release.get("sourceAsset")
    sums_asset = release.get("sha256SumsAsset")
    if not isinstance(source_asset, dict) or not isinstance(sums_asset, dict):
        raise SystemExit("stable-release origin asset metadata is incomplete")
    expected_source_name = f"Dash-Go_{dashgo_version}_source.tar.gz"
    if required_string(source_asset.get("name"), "dashGoRelease.sourceAsset.name") != expected_source_name:
        raise SystemExit("stable-release origin source asset name is invalid")
    if required_sha256(source_asset.get("sha256"), "dashGoRelease.sourceAsset.sha256") != dashgo_hash:
        raise SystemExit("stable-release origin source asset digest does not match staged manifest")
    if required_string(sums_asset.get("name"), "dashGoRelease.sha256SumsAsset.name") != "SHA256SUMS":
        raise SystemExit("stable-release origin checksum asset name is invalid")
    required_sha256(sums_asset.get("sha256"), "dashGoRelease.sha256SumsAsset.sha256")
elif origin_kind == "dashgo-beta-release":
    if origin_schema != 1 or purpose != "beta release native contract candidate only":
        raise SystemExit("beta-release candidate origin has an invalid purpose")
    numeric = dashgo_version.split("-beta.", 1)[0]
    if not re.fullmatch(re.escape(numeric) + r"-test\.[1-9]\d*", release_package_version):
        raise SystemExit("beta native candidate package version must use the Dash-Go numeric core plus -test.N")
    release = origin.get("dashGoRelease")
    if not isinstance(release, dict):
        raise SystemExit("beta-release candidate origin lacks dashGoRelease")
    if required_string(release.get("repository"), "dashGoRelease.repository") != "DashDashGoApp/Dash-Go":
        raise SystemExit("beta-release origin repository is not DashDashGoApp/Dash-Go")
    version = required_string(release.get("version"), "dashGoRelease.version")
    tag = required_string(release.get("releaseTag"), "dashGoRelease.releaseTag")
    if version != dashgo_version or tag != f"v{dashgo_version}":
        raise SystemExit("beta-release origin version/tag does not match staged Dash-Go version")
    if release.get("immutable") is not True or release.get("prerelease") is not True or release.get("track") != "beta":
        raise SystemExit("beta-release origin is not an immutable published beta")
    tag_commit = required_string(release.get("tagCommit"), "dashGoRelease.tagCommit").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", tag_commit):
        raise SystemExit("beta-release origin tag commit is invalid")
    source_asset = release.get("sourceAsset")
    sums_asset = release.get("sha256SumsAsset")
    if not isinstance(source_asset, dict) or not isinstance(sums_asset, dict):
        raise SystemExit("beta-release origin asset metadata is incomplete")
    expected_source_name = f"Dash-Go_{dashgo_version}_source.tar.gz"
    if required_string(source_asset.get("name"), "dashGoRelease.sourceAsset.name") != expected_source_name:
        raise SystemExit("beta-release origin source asset name is invalid")
    if required_sha256(source_asset.get("sha256"), "dashGoRelease.sourceAsset.sha256") != dashgo_hash:
        raise SystemExit("beta-release origin source asset digest does not match staged manifest")
    if required_string(sums_asset.get("name"), "dashGoRelease.sha256SumsAsset.name") != "SHA256SUMS":
        raise SystemExit("beta-release origin checksum asset name is invalid")
    required_sha256(sums_asset.get("sha256"), "dashGoRelease.sha256SumsAsset.sha256")
    if showcase_runtime_mode != "native-contract":
        raise SystemExit("beta-release candidate must stage the native Showcase contract without legacy overlays")
    native_beta = True
elif origin_kind == "dashgo-draft-prepublish-release":
    if origin_schema != 2 or purpose != "draft prepublication package candidate only":
        raise SystemExit("draft-prepublication candidate origin has an invalid purpose")
    if release_package_version != dashgo_version:
        raise SystemExit("draft-prepublication package version must exactly equal staged Dash-Go version")
    release = origin.get("dashGoRelease")
    if not isinstance(release, dict):
        raise SystemExit("draft-prepublication candidate origin lacks dashGoRelease")
    if required_string(release.get("repository"), "dashGoRelease.repository") != "DashDashGoApp/Dash-Go":
        raise SystemExit("draft-prepublication origin repository is not DashDashGoApp/Dash-Go")
    if required_string(release.get("version"), "dashGoRelease.version") != dashgo_version:
        raise SystemExit("draft-prepublication origin version does not match staged Dash-Go version")
    if required_string(release.get("releaseTag"), "dashGoRelease.releaseTag") != f"v{dashgo_version}":
        raise SystemExit("draft-prepublication origin tag does not match staged Dash-Go version")
    required_positive_int(release.get("releaseID"), "dashGoRelease.releaseID")
    if release.get("draft") is not True or release.get("immutable") is not False or release.get("publishedAt") is not None:
        raise SystemExit("draft-prepublication origin does not prove a mutable unpublished Dash-Go draft")
    tag_commit = required_string(release.get("tagCommit"), "dashGoRelease.tagCommit").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", tag_commit):
        raise SystemExit("draft-prepublication origin tag commit is invalid")
    source_asset = release.get("sourceAsset")
    sums_asset = release.get("sha256SumsAsset")
    if not isinstance(source_asset, dict) or not isinstance(sums_asset, dict):
        raise SystemExit("draft-prepublication origin asset metadata is incomplete")
    expected_source_name = f"Dash-Go_{dashgo_version}_source.tar.gz"
    if required_string(source_asset.get("name"), "dashGoRelease.sourceAsset.name") != expected_source_name:
        raise SystemExit("draft-prepublication origin source asset name is invalid")
    required_positive_int(source_asset.get("id"), "dashGoRelease.sourceAsset.id")
    if required_sha256(source_asset.get("sha256"), "dashGoRelease.sourceAsset.sha256") != dashgo_hash:
        raise SystemExit("draft-prepublication origin source asset digest does not match staged manifest")
    if required_string(sums_asset.get("name"), "dashGoRelease.sha256SumsAsset.name") != "SHA256SUMS":
        raise SystemExit("draft-prepublication origin checksum asset name is invalid")
    required_positive_int(sums_asset.get("id"), "dashGoRelease.sha256SumsAsset.id")
    required_sha256(sums_asset.get("sha256"), "dashGoRelease.sha256SumsAsset.sha256")
    draft_prepublication = True
else:
    raise SystemExit(f"unsupported candidate origin: {origin_kind}")

if required_string(origin.get("dashGoVersion"), "dashGoVersion") != dashgo_version:
    raise SystemExit("candidate origin Dash-Go version does not match staging summary")
if required_string(origin.get("releasePackageVersion"), "releasePackageVersion") != release_package_version:
    raise SystemExit("candidate origin release package version does not match staging summary")
if required_sha256(origin.get("dashGoSourceSha256"), "dashGoSourceSha256") != dashgo_hash:
    raise SystemExit("candidate origin Dash-Go source digest does not match staged manifest")

provenance = {
    "schema": 2,
    "purpose": purpose,
    "candidateOrigin": origin_kind,
    "studioVersion": summary["studioVersion"],
    "releasePackageVersion": release_package_version,
    "dashGoVersion": dashgo_version,
    "studioCommit": studio_commit,
    "dashGoSourceSha256": dashgo_hash,
    "showcaseRuntimeMode": showcase_runtime_mode,
    "dashGoRelease": origin.get("dashGoRelease"),
    "artifacts": {
        linux_output.name: sha256(linux_output),
        windows_archive.name: sha256(windows_archive),
    },
}
if draft_prepublication:
    provenance["schema"] = 3
if native_beta:
    provenance["nativeShowcaseContract"] = NATIVE_SHOWCASE_CONTRACT

(output / "candidate-provenance.json").write_text(
    json.dumps(provenance, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)

print(f"PASS: staged Linux package: {linux_output.name}")
print(f"PASS: release package version: {release_package_version}")
print(f"PASS: staged Windows payload: {windows_archive.name}")
print(f"PASS: candidate origin: {origin_kind}")
PY
