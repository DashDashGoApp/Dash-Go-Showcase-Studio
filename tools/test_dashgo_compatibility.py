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

    def test_known_stable_source_selects_one_profile(self) -> None:
        profile, source = bridge.select_profile(
            self.matrix,
            "1.5.7",
            "1d04eef5096db1d9aab9f8095ba9bf3dada1284b793cd6aa4b158f89b287c53a",
        )
        self.assertEqual(profile["id"], "legacy-bridge-v1")
        self.assertEqual(source["version"], "1.5.7")

    def test_known_beta_source_selects_one_profile(self) -> None:
        profile, source = bridge.select_profile(
            self.matrix,
            "1.5.8-beta.4",
            "cdae46b0c3e75189bd8a53b53429a939adb95d5132735eabf0522e53beb64d37",
        )
        self.assertEqual(profile["id"], "legacy-bridge-v1")
        self.assertEqual(source["version"], "1.5.8-beta.4")

    def test_unknown_source_hash_is_rejected(self) -> None:
        with self.assertRaises(bridge.CompatibilityError):
            bridge.select_profile(self.matrix, "1.5.7", "0" * 64)

    def test_unknown_release_version_is_rejected(self) -> None:
        with self.assertRaises(bridge.CompatibilityError):
            bridge.select_profile(self.matrix, "1.5.8", "0" * 64)

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
