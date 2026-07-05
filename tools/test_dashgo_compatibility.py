#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("showcase_compatibility", ROOT / "tools" / "apply_dashgo_compatibility.py")
if SPEC is None or SPEC.loader is None:
    raise SystemExit("could not load compatibility bridge")
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


class CompatibilityMatrixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.matrix = bridge.load_matrix(ROOT / "tools" / "dashgo_compatibility.json")

    def test_known_stable_version_selects_the_adapter_probe_profile(self) -> None:
        profile, policy = bridge.select_profile(self.matrix, "1.5.7", "24ddab805da64c4ddb40d277362f06b21bb3b0839f56e27a77389f71f0ce7d3d")
        self.assertEqual(profile["id"], "legacy-bridge-v1")
        self.assertEqual(policy["selection"], "adapter-probe")

    def test_compatible_future_1_5_x_version_reaches_the_adapter_probe(self) -> None:
        profile, policy = bridge.select_profile(self.matrix, "1.5.9", "f" * 64)
        self.assertEqual(profile["id"], "legacy-bridge-v1")
        self.assertEqual(policy["maximumVersionExclusive"], "1.6.0")

    def test_known_beta_version_selects_the_adapter_probe_profile(self) -> None:
        profile, policy = bridge.select_profile(self.matrix, "1.5.8-beta.4", "c" * 64)
        self.assertEqual(profile["id"], "legacy-bridge-v1")
        self.assertEqual(policy["minimumVersion"], "1.5.7")

    def test_unknown_archive_hash_does_not_override_version_selection(self) -> None:
        profile, _ = bridge.select_profile(self.matrix, "1.5.7", "0" * 64)
        self.assertEqual(profile["id"], "legacy-bridge-v1")

    def test_version_outside_the_reviewed_window_is_rejected(self) -> None:
        for version in ("1.5.6", "1.6.0", "2.0.0"):
            with self.subTest(version=version):
                with self.assertRaises(bridge.CompatibilityError):
                    bridge.select_profile(self.matrix, version, "0" * 64)

    def test_release_version_requires_matching_version_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            app = Path(temporary)
            (app / "release").mkdir()
            (app / "release" / "release.json").write_text(json.dumps({"version": "1.5.7"}), encoding="utf-8")
            (app / "VERSION").write_text("1.5.6\n", encoding="utf-8")
            with self.assertRaises(bridge.CompatibilityError):
                bridge.load_release_version(app)


if __name__ == "__main__":
    unittest.main()