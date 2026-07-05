#!/usr/bin/env python3
"""Hermetic positive-path test for the immutable native-contract beta materializer."""
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

VERSION = "9.8.7-beta.3"
TAG = f"v{VERSION}"
COMMIT = "2" * 40
RELEASE_ID = 987655
NONCE = "native-beta-test-1234"
REQUIRED_CAPABILITIES = {
    "separateDataRoot": True,
    "scenarioManifest": True,
    "scenarioCalendars": True,
    "calendarWritebackAllowlist": True,
    "cacheRebuildReport": True,
    "statusEndpoint": True,
    "staticScenarioAssets": True,
}


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


def make_source_archive(path: Path, capabilities: dict[str, bool] = REQUIRED_CAPABILITIES) -> None:
    root = f"dash-go-source-{VERSION}"
    with tarfile.open(path, "w:gz") as archive:
        add_text(archive, f"{root}/app/VERSION", VERSION + "\n")
        add_text(archive, f"{root}/app/release/release.json", json.dumps({"version": VERSION, "track": "beta"}) + "\n")
        add_text(
            archive,
            f"{root}/app/release/showcase-contract.json",
            json.dumps({"schema": 1, "contract": "dashgo-showcase/v1", "capabilities": capabilities}) + "\n",
        )
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
    with tempfile.TemporaryDirectory(prefix="studio-native-beta-test-") as temp_name:
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
            "draft": False,
            "prerelease": True,
            "immutable": True,
            "published_at": "2026-07-05T18:00:00Z",
            "assets": [
                {
                    "id": 123456,
                    "name": archive.name,
                    "state": "uploaded",
                    "browser_download_url": "https://example.invalid/source",
                    "digest": f"sha256:{source_hash}",
                },
                {
                    "id": 123457,
                    "name": "SHA256SUMS",
                    "state": "uploaded",
                    "browser_download_url": "https://example.invalid/sums",
                    "digest": f"sha256:{sums_hash}",
                },
            ],
        }
        original_get_json = tool.get_json
        original_download = tool.download
        original_argv = sys.argv[:]
        try:
            def fake_get_json(url: str) -> dict:
                if url.endswith(f"/releases/tags/{TAG}"):
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
                "--candidate-origin", "dashgo-beta-release",
                "--dashgo-release-tag", TAG,
                "--dashgo-version", VERSION,
                "--dashgo-source-sha256", source_hash,
                "--dashgo-tag-commit", COMMIT,
                "--dispatch-nonce", NONCE,
                "--release-package-version", "9.8.7-test.1",
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
        payload = json.loads(origin.read_text(encoding="utf-8"))
        if payload.get("candidateOrigin") != "dashgo-beta-release" or payload.get("purpose") != "beta release native contract candidate only":
            raise AssertionError("native beta candidate origin/purpose is incorrect")
        release_payload = payload.get("dashGoRelease")
        if not isinstance(release_payload, dict) or release_payload.get("prerelease") is not True or release_payload.get("track") != "beta":
            raise AssertionError("native beta release evidence is incomplete")
        staged = source_root / "engine" / archive.name
        if not staged.is_file() or sha256(staged) != source_hash:
            raise AssertionError("native beta source archive was not staged exactly")
        manifest = json.loads((source_root / "studio.manifest.json").read_text(encoding="utf-8"))
        if manifest.get("dashGoVersion") != VERSION or manifest.get("releasePackageVersion") != "9.8.7-test.1":
            raise AssertionError("native beta did not update the isolated Studio manifest")

        incomplete = temp / "Dash-Go_incomplete_source.tar.gz"
        incomplete_capabilities = dict(REQUIRED_CAPABILITIES)
        incomplete_capabilities.pop("statusEndpoint")
        incomplete_capabilities["staticScenarioAssets"] = False
        make_source_archive(incomplete, incomplete_capabilities)
        try:
            tool.validate_archive(incomplete, VERSION, "beta", require_native_contract=True)
        except tool.ReleaseInputError as exc:
            message = str(exc)
            for token in (
                "does not satisfy Studio runtime contract matrix",
                "missing capability 'statusEndpoint' required by native.status-readiness",
                "missing capability 'staticScenarioAssets' required by native.browser-routes",
            ):
                if token not in message:
                    raise AssertionError(f"native beta materializer error lacks {token!r}: {message}")
        else:
            raise AssertionError("native beta materializer accepted an incomplete Contract v1 declaration")

    print("PASS: immutable native-contract beta materializer hermetic test succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
