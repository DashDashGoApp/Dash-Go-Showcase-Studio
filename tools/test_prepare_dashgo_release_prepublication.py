#!/usr/bin/env python3
"""Hermetic positive-path test for the draft-prepublication Studio materializer."""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import sys
import tarfile
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True


VERSION = "9.8.7"
TAG = f"v{VERSION}"
COMMIT = "1" * 40
RELEASE_ID = 987654
SOURCE_ASSET_ID = 111222
SUMS_ASSET_ID = 333444
NONCE = "prepublish-test-1234"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def add_text(archive: tarfile.TarFile, name: str, text: str) -> None:
    data = text.encode("utf-8")
    info = tarfile.TarInfo(name)
    info.size = len(data)
    archive.addfile(info, io.BytesIO(data))


def make_source_archive(path: Path) -> None:
    root = f"dash-go-source-{VERSION}"
    with tarfile.open(path, "w:gz") as archive:
        add_text(archive, f"{root}/app/VERSION", VERSION + "\n")
        add_text(archive, f"{root}/app/release/release.json", json.dumps({"version": VERSION, "track": "stable"}) + "\n")
        add_text(archive, f"{root}/app/cmd/dashboard-control-server/main.go", "package main\n")
        add_text(archive, f"{root}/app/ui/js/bundle.manifest.json", "{}\n")


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("prepare_dashgo_release_under_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load prepare_dashgo_release.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    tool = load_module(Path(__file__).with_name("prepare_dashgo_release.py"))
    with tempfile.TemporaryDirectory(prefix="studio-prepublication-test-") as temp_name:
        temp = Path(temp_name)
        source_root = temp / "studio"
        source_root.mkdir()
        (source_root / "studio.manifest.json").write_text(
            json.dumps(
                {
                    "schema": 1,
                    "studioVersion": "2.0.0-test.10",
                    "dashGoVersion": "1.5.2",
                    "dashGoSourceArchive": "engine/Dash-Go_1.5.2_source.tar.gz",
                    "dashGoSourceSha256": "0" * 64,
                }
            ) + "\n",
            encoding="utf-8",
        )

        archive = temp / f"Dash-Go_{VERSION}_source.tar.gz"
        sums = temp / "SHA256SUMS"
        make_source_archive(archive)
        source_hash = sha256(archive)
        sums.write_text(f"{source_hash}  {archive.name}\n", encoding="utf-8")
        sums_hash = sha256(sums)

        release = {
            "id": RELEASE_ID,
            "tag_name": TAG,
            "draft": True,
            "prerelease": False,
            "immutable": False,
            "published_at": None,
            "assets": [
                {
                    "id": SOURCE_ASSET_ID,
                    "name": archive.name,
                    "state": "uploaded",
                    "url": "https://api.example.invalid/assets/source",
                    "digest": f"sha256:{source_hash}",
                },
                {
                    "id": SUMS_ASSET_ID,
                    "name": "SHA256SUMS",
                    "state": "uploaded",
                    "url": "https://api.example.invalid/assets/sums",
                    "digest": f"sha256:{sums_hash}",
                },
            ],
        }

        original_get_json = tool.get_json
        original_download = tool.download
        original_argv = sys.argv[:]
        try:
            def fake_get_json(url: str) -> dict:
                if url.endswith(f"/releases/{RELEASE_ID}"):
                    return release
                if "/git/ref/tags/" in url:
                    return {"object": {"type": "commit", "sha": COMMIT}}
                raise AssertionError(f"unexpected API URL: {url}")

            def fake_download(url: str, target: Path) -> None:
                if url.endswith("/source"):
                    target.write_bytes(archive.read_bytes())
                elif url.endswith("/sums"):
                    target.write_bytes(sums.read_bytes())
                else:
                    raise AssertionError(f"unexpected asset URL: {url}")

            tool.get_json = fake_get_json
            tool.download = fake_download
            origin = temp / "origin.json"
            sys.argv = [
                "prepare_dashgo_release.py",
                "--source-root", str(source_root),
                "--origin-path", str(origin),
                "--candidate-origin", "dashgo-draft-prepublish-release",
                "--dashgo-release-id", str(RELEASE_ID),
                "--dashgo-release-tag", TAG,
                "--dashgo-version", VERSION,
                "--dashgo-source-asset-id", str(SOURCE_ASSET_ID),
                "--dashgo-source-sha256", source_hash,
                "--dashgo-sha256sums-asset-id", str(SUMS_ASSET_ID),
                "--dashgo-tag-commit", COMMIT,
                "--dispatch-nonce", NONCE,
                "--release-package-version", VERSION,
                "--github-api-url", "https://api.example.invalid",
            ]
            with contextlib.redirect_stdout(io.StringIO()):
                result = tool.main()
        finally:
            tool.get_json = original_get_json
            tool.download = original_download
            sys.argv = original_argv

        if result != 0:
            raise AssertionError(f"materializer returned {result}")
        origin_payload = json.loads(origin.read_text(encoding="utf-8"))
        if origin_payload.get("schema") != 2:
            raise AssertionError("draft-prepublication origin must use schema 2")
        if origin_payload.get("candidateOrigin") != "dashgo-draft-prepublish-release":
            raise AssertionError("wrong draft-prepublication candidate origin")
        if origin_payload.get("purpose") != "draft prepublication package candidate only":
            raise AssertionError("wrong draft-prepublication candidate purpose")
        release_payload = origin_payload.get("dashGoRelease")
        if not isinstance(release_payload, dict):
            raise AssertionError("draft-prepublication origin lacks release payload")
        if release_payload.get("draft") is not True or release_payload.get("immutable") is not False:
            raise AssertionError("draft-prepublication origin does not prove a mutable unpublished Dash-Go draft")
        if release_payload.get("publishedAt") is not None:
            raise AssertionError("draft-prepublication origin unexpectedly has publishedAt")
        if release_payload.get("tagCommit") != COMMIT:
            raise AssertionError("draft-prepublication tag commit changed")
        if release_payload.get("sourceAsset", {}).get("id") != SOURCE_ASSET_ID:
            raise AssertionError("draft-prepublication source asset identity changed")
        if release_payload.get("sha256SumsAsset", {}).get("id") != SUMS_ASSET_ID:
            raise AssertionError("draft-prepublication SHA256SUMS asset identity changed")
        staged = source_root / "engine" / archive.name
        if not staged.is_file() or sha256(staged) != source_hash:
            raise AssertionError("draft-prepublication source archive was not staged exactly")

    print("PASS: draft-prepublication materializer hermetic test succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
