#!/usr/bin/env python3
"""Focused offline tests for the automatic legacy bridge candidate gate."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("run_legacy_bridge_candidate.py")
spec = importlib.util.spec_from_file_location("legacy_bridge_gate", MODULE_PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class FakeClient:
    def __init__(self, responses: dict[tuple[str, str], tuple[int, object]]) -> None:
        self.responses = responses

    def request(self, method: str, path: str, payload: object = None) -> tuple[int, object]:
        key = (method, path)
        if key not in self.responses:
            raise AssertionError(f"unexpected request: {key} payload={payload!r}")
        return self.responses[key]


class LegacyBridgeCandidateTests(unittest.TestCase):
    def write_matrix(self, payload: dict) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / "tools").mkdir()
        (root / "tools" / "dashgo_compatibility.json").write_text(json.dumps(payload), encoding="utf-8")
        return root

    def good_matrix(self) -> dict:
        return {
            "schema": 2,
            "profiles": [
                {
                    "id": "legacy-bridge-v1",
                    "sourcePolicy": {
                        "selection": "adapter-probe",
                        "minimumVersion": "1.5.7",
                        "maximumVersionExclusive": "1.6.0",
                    },
                    "requiredCandidateChecks": [
                        "staged-linux-package-and-runtime-self-test",
                        "windows-installer-install-self-test-and-uninstall-smoke",
                    ],
                }
            ],
        }

    def test_loads_reviewed_adapter_probe_policy(self) -> None:
        policy = module.load_bridge_policy(self.write_matrix(self.good_matrix()))
        self.assertEqual(policy.minimum_version, "1.5.7")
        module.assert_version_in_window("1.5.7", policy)
        module.assert_version_in_window("1.5.9", policy)

    def test_rejects_missing_windows_smoke_requirement(self) -> None:
        matrix = self.good_matrix()
        matrix["profiles"][0]["requiredCandidateChecks"] = ["staged-linux-package-and-runtime-self-test"]
        with self.assertRaisesRegex(module.CandidateError, "windows-installer"):
            module.load_bridge_policy(self.write_matrix(matrix))

    def test_rejects_version_outside_reviewed_window(self) -> None:
        policy = module.load_bridge_policy(self.write_matrix(self.good_matrix()))
        with self.assertRaisesRegex(module.CandidateError, "outside reviewed legacy bridge window"):
            module.assert_version_in_window("1.6.0", policy)

    def test_loads_immutable_release_and_annotated_tag(self) -> None:
        release_path = "/repos/DashDashGoApp/Dash-Go/releases/tags/v1.5.7"
        ref_path = "/repos/DashDashGoApp/Dash-Go/git/ref/tags/v1.5.7"
        tag_path = "/repos/DashDashGoApp/Dash-Go/git/tags/" + "a" * 40
        fake = FakeClient({
            ("GET", release_path): (200, {
                "tag_name": "v1.5.7", "draft": False, "prerelease": False, "immutable": True,
                "assets": [{"name": "Dash-Go_1.5.7_source.tar.gz", "digest": "sha256:" + "b" * 64}],
            }),
            ("GET", ref_path): (200, {"object": {"type": "tag", "sha": "a" * 40}}),
            ("GET", tag_path): (200, {"object": {"type": "commit", "sha": "c" * 40}}),
        })
        policy = module.load_bridge_policy(self.write_matrix(self.good_matrix()))
        release = module.load_dashgo_release(fake, "1.5.7", policy)
        self.assertEqual(release.source_sha256, "b" * 64)
        self.assertEqual(release.tag_commit, "c" * 40)

    def test_discovers_only_exact_branch_head_nonce_and_workflow(self) -> None:
        query = "branch=feature&event=workflow_dispatch&per_page=100"
        path = "/repos/DashDashGoApp/Dash-Go-Showcase-Studio/actions/workflows/studio-stage-candidate.yml/runs?" + query
        fake = FakeClient({
            ("GET", path): (200, {"workflow_runs": [
                {"id": 99, "head_sha": "a" * 40, "event": "workflow_dispatch", "path": ".github/workflows/studio-stage-candidate.yml@refs/heads/feature", "display_title": "nonce-123", "status": "queued", "conclusion": None},
                {"id": 100, "head_sha": "b" * 40, "event": "workflow_dispatch", "path": ".github/workflows/studio-stage-candidate.yml", "display_title": "nonce-123", "status": "queued", "conclusion": None},
            ]}),
        })
        run = module.discover_dispatched_run(fake, "DashDashGoApp/Dash-Go-Showcase-Studio", "studio-stage-candidate.yml", "feature", "a" * 40, "nonce-123")
        self.assertIsNotNone(run)
        assert run is not None
        self.assertEqual(run.run_id, "99")

    def test_run_url_rejects_untrusted_identity(self) -> None:
        with self.assertRaisesRegex(module.CandidateError, "invalid"):
            module.run_url("DashDashGoApp/Dash-Go-Showcase-Studio", "1/2")


if __name__ == "__main__":
    unittest.main()
