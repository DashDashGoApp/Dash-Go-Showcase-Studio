#!/usr/bin/env python3
"""Materialize a fail-closed Dash-Go baseline for a Studio package candidate."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

sys.dont_write_bytecode = True

DASHGO_REPOSITORY = "DashDashGoApp/Dash-Go"
API_VERSION = "2022-11-28"
USER_AGENT = "Dash-Go-Showcase-Studio-Stage"
MANUAL_PURPOSE = "manual package candidate only"
STABLE_PURPOSE = "stable release package candidate only"
DRAFT_PREPUBLICATION_PURPOSE = "draft prepublication package candidate only"


class ReleaseInputError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReleaseInputError(f"missing {label}")
    return value.strip()


def require_positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ReleaseInputError(f"{label} must be a positive integer")
    return value


def require_positive_int_string(value: object, label: str) -> int:
    raw = require_string(value, label)
    if not re.fullmatch(r"[1-9][0-9]*", raw):
        raise ReleaseInputError(f"{label} must be a positive integer")
    return int(raw)


def require_sha256(value: str, label: str) -> str:
    normalized = value.lower()
    if not re.fullmatch(r"[0-9a-f]{64}", normalized):
        raise ReleaseInputError(f"{label} must be a 64-character SHA-256 hex digest")
    return normalized


def require_commit(value: str, label: str) -> str:
    normalized = value.lower()
    if not re.fullmatch(r"[0-9a-f]{40}", normalized):
        raise ReleaseInputError(f"{label} must be a 40-character Git commit SHA")
    return normalized


def require_stable_version(value: str) -> str:
    if not re.fullmatch(r"\d+\.\d+\.\d+", value):
        raise ReleaseInputError("Dash-Go stable version must use X.Y.Z")
    return value


def github_headers(*, accept: str = "application/vnd.github+json") -> dict[str, str]:
    headers = {
        "Accept": accept,
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": USER_AGENT,
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers=github_headers())
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            value = json.load(response)
    except Exception as exc:
        raise ReleaseInputError(f"could not read GitHub API response: {url}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReleaseInputError(f"GitHub API response is not an object: {url}")
    return value


def download(url: str, target: Path) -> None:
    request = urllib.request.Request(
        url,
        headers=github_headers(accept="application/octet-stream"),
    )
    stage = target.with_name("." + target.name + ".stage")
    try:
        with urllib.request.urlopen(request, timeout=120) as response, stage.open("wb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
        os.replace(stage, target)
    except Exception as exc:
        stage.unlink(missing_ok=True)
        raise ReleaseInputError(f"could not download release asset {url}: {exc}") from exc


def release_asset(release: dict, name: str, *, download_key: str = "browser_download_url") -> dict:
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise ReleaseInputError("GitHub release metadata has no asset list")
    matches = [asset for asset in assets if isinstance(asset, dict) and asset.get("name") == name]
    if len(matches) != 1:
        raise ReleaseInputError(f"expected exactly one release asset named {name}, found {len(matches)}")
    asset = matches[0]
    if asset.get("state") != "uploaded":
        raise ReleaseInputError(f"release asset {name} is not uploaded")
    asset_url = asset.get(download_key)
    if not isinstance(asset_url, str) or not asset_url.startswith("https://"):
        raise ReleaseInputError(f"release asset {name} lacks a safe HTTPS {download_key}")
    digest = require_string(asset.get("digest"), f"release asset {name} digest")
    if not digest.startswith("sha256:"):
        raise ReleaseInputError(f"release asset {name} must provide a SHA-256 digest")
    require_sha256(digest.removeprefix("sha256:"), f"release asset {name} digest")
    require_positive_int(asset.get("id"), f"release asset {name} id")
    return asset


def resolve_tag_commit(api: str, tag: str) -> str:
    ref = get_json(f"{api}/repos/{DASHGO_REPOSITORY}/git/ref/tags/{urllib.parse.quote(tag, safe='')}")
    for _ in range(4):
        obj = ref.get("object")
        if not isinstance(obj, dict):
            raise ReleaseInputError("Git tag ref lacks an object")
        kind = require_string(obj.get("type"), "Git tag object type")
        sha = require_string(obj.get("sha"), "Git tag object SHA")
        if kind == "commit":
            return require_commit(sha, "resolved tag commit")
        if kind != "tag":
            raise ReleaseInputError(f"Git tag resolves to unsupported object type: {kind}")
        ref = get_json(f"{api}/repos/{DASHGO_REPOSITORY}/git/tags/{urllib.parse.quote(sha, safe='')}")
    raise ReleaseInputError("annotated Git tag nesting exceeds the supported limit")


def validate_archive(archive: Path, version: str) -> None:
    expected_root = f"dash-go-source-{version}"
    expected = {
        f"{expected_root}/app/VERSION",
        f"{expected_root}/app/release/release.json",
        f"{expected_root}/app/cmd/dashboard-control-server/main.go",
        f"{expected_root}/app/ui/js/bundle.manifest.json",
    }
    try:
        with tarfile.open(archive, "r:gz") as tar:
            names: set[str] = set()
            for member in tar.getmembers():
                name = member.name.replace("\\", "/")
                if not name or name.startswith("/") or name.startswith("../") or "/../" in name:
                    raise ReleaseInputError(f"unsafe Dash-Go source archive member: {member.name}")
                if member.issym() or member.islnk() or not (member.isdir() or member.isfile()):
                    raise ReleaseInputError(f"unsupported Dash-Go source archive member: {member.name}")
                names.add(name)
            if not names or not all(name == expected_root or name.startswith(expected_root + "/") for name in names):
                raise ReleaseInputError(f"Dash-Go source archive root must be exactly {expected_root}")
            if not expected.issubset(names):
                raise ReleaseInputError("Dash-Go source archive is missing required release entrypoints")
            version_file = tar.extractfile(f"{expected_root}/app/VERSION")
            release_file = tar.extractfile(f"{expected_root}/app/release/release.json")
            if version_file is None or release_file is None:
                raise ReleaseInputError("Dash-Go source archive cannot read release contract")
            archive_version = version_file.read().decode("utf-8").strip()
            release_contract = json.loads(release_file.read().decode("utf-8"))
    except tarfile.TarError as exc:
        raise ReleaseInputError(f"could not read Dash-Go source archive: {exc}") from exc
    if archive_version != version:
        raise ReleaseInputError(f"Dash-Go app/VERSION mismatch: expected {version}, found {archive_version!r}")
    if release_contract.get("version") != version or release_contract.get("track") != "stable":
        raise ReleaseInputError("Dash-Go release/release.json is not the expected stable release contract")


def parse_sums(path: Path, source_name: str) -> str:
    matches: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9A-Fa-f]{64})  (.+)", line)
        if match and match.group(2) == source_name:
            matches.append(match.group(1).lower())
    if len(matches) != 1:
        raise ReleaseInputError(f"SHA256SUMS must contain exactly one checksum for {source_name}")
    return matches[0]


def require_release_package_version(value: str, dashgo_version: str) -> str:
    package_version = value.strip() if value else dashgo_version
    pattern = re.escape(dashgo_version) + r"(?:-r[1-9][0-9]*)?"
    if not re.fullmatch(pattern, package_version):
        raise ReleaseInputError(
            "release package version must equal the Dash-Go stable version or use its -rN reissue suffix"
        )
    return package_version


def require_prepublication_package_version(value: str, dashgo_version: str) -> str:
    package_version = require_string(value, "prepublication release package version")
    if package_version != dashgo_version:
        raise ReleaseInputError("prepublication release package version must exactly equal the Dash-Go stable version")
    return package_version


def update_manifest(source_root: Path, version: str, archive_hash: str, release_package_version: str) -> None:
    manifest_path = source_root / "studio.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    archive_relative = f"engine/Dash-Go_{version}_source.tar.gz"
    manifest.update(
        {
            "dashGoVersion": version,
            "dashGoSourceArchive": archive_relative,
            "dashGoSourceSha256": archive_hash,
            "releasePackageVersion": release_package_version,
        }
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stage = path.with_name("." + path.name + ".stage")
    stage.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(stage, path)


def materialize_source_archive(
    *,
    source_root: Path,
    version: str,
    source_name: str,
    source_digest: str,
    sums_digest: str,
    source_url: str,
    sums_url: str,
) -> None:
    archive_target = source_root / "engine" / source_name
    archive_target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dashgo-studio-release-") as temp_name:
        temp = Path(temp_name)
        downloaded_source = temp / source_name
        downloaded_sums = temp / "SHA256SUMS"
        download(source_url, downloaded_source)
        download(sums_url, downloaded_sums)
        if sha256(downloaded_source) != source_digest:
            raise ReleaseInputError("downloaded Dash-Go source archive does not match GitHub asset digest")
        if sha256(downloaded_sums) != sums_digest:
            raise ReleaseInputError("downloaded SHA256SUMS does not match GitHub asset digest")
        if parse_sums(downloaded_sums, source_name) != source_digest:
            raise ReleaseInputError("SHA256SUMS source row does not match the GitHub source asset digest")
        validate_archive(downloaded_source, version)
        stage = archive_target.with_name("." + archive_target.name + ".stage")
        shutil.copy2(downloaded_source, stage)
        if sha256(stage) != source_digest:
            stage.unlink(missing_ok=True)
            raise ReleaseInputError("Dash-Go source archive changed while staging the Studio baseline")
        os.replace(stage, archive_target)


def require_api_url(value: object, label: str) -> str:
    url = require_string(value, label)
    if not url.startswith("https://"):
        raise ReleaseInputError(f"{label} must use HTTPS")
    return url


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--origin-path", type=Path, required=True)
    parser.add_argument(
        "--candidate-origin",
        choices=("manual", "dashgo-stable-release", "dashgo-draft-prepublish-release"),
        required=True,
    )
    parser.add_argument("--dashgo-release-id", default="")
    parser.add_argument("--dashgo-release-tag", default="")
    parser.add_argument("--dashgo-version", default="")
    parser.add_argument("--dashgo-source-asset-id", default="")
    parser.add_argument("--dashgo-source-sha256", default="")
    parser.add_argument("--dashgo-sha256sums-asset-id", default="")
    parser.add_argument("--dashgo-tag-commit", default="")
    parser.add_argument("--dispatch-nonce", default="")
    parser.add_argument("--release-package-version", default="")
    parser.add_argument("--github-api-url", default="https://api.github.com")
    args = parser.parse_args()

    source_root = args.source_root.resolve()
    origin_path = args.origin_path.resolve()
    if not (source_root / "studio.manifest.json").is_file():
        raise ReleaseInputError(f"Studio source root is missing studio.manifest.json: {source_root}")

    common = {
        "schema": 1,
        "candidateOrigin": args.candidate_origin,
        "studioSourceRoot": str(source_root),
    }

    all_release_fields = (
        args.dashgo_release_id,
        args.dashgo_release_tag,
        args.dashgo_version,
        args.dashgo_source_asset_id,
        args.dashgo_source_sha256,
        args.dashgo_sha256sums_asset_id,
        args.dashgo_tag_commit,
        args.dispatch_nonce,
        args.release_package_version,
    )

    if args.candidate_origin == "manual":
        if any(all_release_fields):
            raise ReleaseInputError("manual Stage input must not supply Dash-Go release bridge fields")
        manifest = json.loads((source_root / "studio.manifest.json").read_text(encoding="utf-8"))
        common.update(
            {
                "purpose": MANUAL_PURPOSE,
                "dashGoRelease": None,
                "dashGoVersion": require_string(manifest.get("dashGoVersion"), "pinned Dash-Go version"),
                "releasePackageVersion": require_string(manifest.get("releasePackageVersion", manifest.get("studioVersion")), "pinned release package version"),
                "dashGoSourceSha256": require_sha256(require_string(manifest.get("dashGoSourceSha256"), "pinned Dash-Go source SHA-256"), "pinned Dash-Go source SHA-256"),
            }
        )
        write_json(origin_path, common)
        print("STUDIO CANDIDATE INPUT: manual pinned baseline")
        return 0

    tag = require_string(args.dashgo_release_tag, "Dash-Go release tag")
    version = require_stable_version(require_string(args.dashgo_version, "Dash-Go version"))
    expected_source_hash = require_sha256(require_string(args.dashgo_source_sha256, "Dash-Go source SHA-256"), "Dash-Go source SHA-256")
    expected_tag_commit = require_commit(require_string(args.dashgo_tag_commit, "Dash-Go tag commit"), "Dash-Go tag commit")
    nonce = require_string(args.dispatch_nonce, "dispatch nonce")
    if tag != f"v{version}":
        raise ReleaseInputError("Dash-Go release tag must exactly match the stable version")
    if not re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z._-]{7,127}", nonce):
        raise ReleaseInputError("dispatch nonce must be 8-128 ASCII letters, digits, dots, underscores, or dashes")

    api = args.github_api_url.rstrip("/")
    if not api.startswith("https://"):
        raise ReleaseInputError("GitHub API URL must use HTTPS")

    source_name = f"Dash-Go_{version}_source.tar.gz"

    if args.candidate_origin == "dashgo-stable-release":
        if args.dashgo_release_id or args.dashgo_source_asset_id or args.dashgo_sha256sums_asset_id:
            raise ReleaseInputError("stable-release Stage input must not supply draft prepublication asset identity fields")
        release_package_version = require_release_package_version(args.release_package_version, version)
        release = get_json(f"{api}/repos/{DASHGO_REPOSITORY}/releases/tags/{urllib.parse.quote(tag, safe='')}")
        if release.get("tag_name") != tag or release.get("draft") or release.get("prerelease") or release.get("immutable") is not True:
            raise ReleaseInputError("Dash-Go release is not the expected published immutable stable release")
        release_id = require_positive_int(release.get("id"), "immutable Dash-Go release id")
        published_at = release.get("published_at")
        if not isinstance(published_at, str) or not published_at.strip():
            raise ReleaseInputError("Dash-Go release metadata lacks an immutable published identity")
        resolved_commit = resolve_tag_commit(api, tag)
        if resolved_commit != expected_tag_commit:
            raise ReleaseInputError(f"Dash-Go tag commit mismatch: expected {expected_tag_commit}, found {resolved_commit}")
        source_asset = release_asset(release, source_name)
        sums_asset = release_asset(release, "SHA256SUMS")
        source_digest = require_sha256(str(source_asset["digest"]).split(":", 1)[1], "published source digest")
        sums_digest = require_sha256(str(sums_asset["digest"]).split(":", 1)[1], "published SHA256SUMS digest")
        if source_digest != expected_source_hash:
            raise ReleaseInputError(f"publisher source digest mismatch: expected {expected_source_hash}, GitHub reports {source_digest}")
        materialize_source_archive(
            source_root=source_root,
            version=version,
            source_name=source_name,
            source_digest=source_digest,
            sums_digest=sums_digest,
            source_url=require_api_url(source_asset.get("browser_download_url"), "published source browser download URL"),
            sums_url=require_api_url(sums_asset.get("browser_download_url"), "published SHA256SUMS browser download URL"),
        )
        update_manifest(source_root, version, source_digest, release_package_version)
        common.update(
            {
                "purpose": STABLE_PURPOSE,
                "dashGoVersion": version,
                "releasePackageVersion": release_package_version,
                "dashGoSourceSha256": source_digest,
                "dashGoRelease": {
                    "repository": DASHGO_REPOSITORY,
                    "version": version,
                    "releaseTag": tag,
                    "releaseID": release_id,
                    "publishedAt": published_at,
                    "immutable": True,
                    "tagCommit": resolved_commit,
                    "dispatchNonce": nonce,
                    "sourceAsset": {
                        "name": source_name,
                        "id": require_positive_int(source_asset.get("id"), "published source asset id"),
                        "sha256": source_digest,
                    },
                    "sha256SumsAsset": {
                        "name": "SHA256SUMS",
                        "id": require_positive_int(sums_asset.get("id"), "published SHA256SUMS asset id"),
                        "sha256": sums_digest,
                    },
                },
            }
        )
        write_json(origin_path, common)
        print(f"STUDIO CANDIDATE INPUT: immutable Dash-Go stable release {tag} ({source_digest})")
        return 0

    release_id = require_positive_int_string(args.dashgo_release_id, "Dash-Go draft release id")
    expected_source_asset_id = require_positive_int_string(args.dashgo_source_asset_id, "Dash-Go draft source asset id")
    expected_sums_asset_id = require_positive_int_string(args.dashgo_sha256sums_asset_id, "Dash-Go draft SHA256SUMS asset id")
    release_package_version = require_prepublication_package_version(args.release_package_version, version)
    release = get_json(f"{api}/repos/{DASHGO_REPOSITORY}/releases/{release_id}")
    if require_positive_int(release.get("id"), "Dash-Go draft release metadata id") != release_id:
        raise ReleaseInputError("Dash-Go draft release metadata does not match the requested release id")
    if release.get("tag_name") != tag or release.get("draft") is not True or release.get("prerelease") or release.get("immutable") is not False:
        raise ReleaseInputError("Dash-Go release is not the expected mutable draft stable release")
    if release.get("published_at") is not None:
        raise ReleaseInputError("Dash-Go draft release must not have a published_at timestamp")
    resolved_commit = resolve_tag_commit(api, tag)
    if resolved_commit != expected_tag_commit:
        raise ReleaseInputError(f"Dash-Go tag commit mismatch: expected {expected_tag_commit}, found {resolved_commit}")
    source_asset = release_asset(release, source_name, download_key="url")
    sums_asset = release_asset(release, "SHA256SUMS", download_key="url")
    if require_positive_int(source_asset.get("id"), "Dash-Go draft source asset id") != expected_source_asset_id:
        raise ReleaseInputError("Dash-Go draft source asset identity mismatch")
    if require_positive_int(sums_asset.get("id"), "Dash-Go draft SHA256SUMS asset id") != expected_sums_asset_id:
        raise ReleaseInputError("Dash-Go draft SHA256SUMS asset identity mismatch")
    source_digest = require_sha256(str(source_asset["digest"]).split(":", 1)[1], "draft source digest")
    sums_digest = require_sha256(str(sums_asset["digest"]).split(":", 1)[1], "draft SHA256SUMS digest")
    if source_digest != expected_source_hash:
        raise ReleaseInputError(f"draft source digest mismatch: expected {expected_source_hash}, GitHub reports {source_digest}")
    materialize_source_archive(
        source_root=source_root,
        version=version,
        source_name=source_name,
        source_digest=source_digest,
        sums_digest=sums_digest,
        source_url=require_api_url(source_asset.get("url"), "draft source asset API URL"),
        sums_url=require_api_url(sums_asset.get("url"), "draft SHA256SUMS asset API URL"),
    )
    update_manifest(source_root, version, source_digest, release_package_version)
    common.update(
        {
            "schema": 2,
            "purpose": DRAFT_PREPUBLICATION_PURPOSE,
            "dashGoVersion": version,
            "releasePackageVersion": release_package_version,
            "dashGoSourceSha256": source_digest,
            "dashGoRelease": {
                "repository": DASHGO_REPOSITORY,
                "version": version,
                "releaseTag": tag,
                "releaseID": release_id,
                "draft": True,
                "publishedAt": None,
                "immutable": False,
                "tagCommit": resolved_commit,
                "dispatchNonce": nonce,
                "sourceAsset": {
                    "name": source_name,
                    "id": expected_source_asset_id,
                    "sha256": source_digest,
                },
                "sha256SumsAsset": {
                    "name": "SHA256SUMS",
                    "id": expected_sums_asset_id,
                    "sha256": sums_digest,
                },
            },
        }
    )
    write_json(origin_path, common)
    print(f"STUDIO CANDIDATE INPUT: Dash-Go draft prepublication release {tag} ({source_digest})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReleaseInputError as exc:
        raise SystemExit(f"STUDIO RELEASE INPUT ERROR: {exc}")
