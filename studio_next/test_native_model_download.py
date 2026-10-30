"""No-network tests for fully bounded, hash-pinned local neural input custody.

These fixtures do NOT certify candidate weights, copyright eligibility,
inference capability or an independently successful creative edit.
"""
import hashlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.run_native_model_trial import ROOT, download


class NativeModelDownloadTests(unittest.TestCase):
    def test_exact_size_and_hash_still_verified(self):
        binary = b"already-owned-weight-fixture"
        info = {"filename": "weights.gguf", "bytes": len(binary),
                "sha256": hashlib.sha256(binary).hexdigest(),
                "url": "https://example.invalid/owned-fixture"}
        with TemporaryDirectory() as folder:
            with patch("scripts.run_native_model_trial.urlopen",
                       return_value=io.BytesIO(binary)):
                path = download(info, Path(folder))
            self.assertEqual(path.read_bytes(), binary)
            with patch("scripts.run_native_model_trial.urlopen",
                       side_effect=AssertionError("Verified cache should not download")):
                self.assertEqual(download(info, Path(folder)), path)

    def test_size_unverified_candidate_must_still_have_byte_bound_and_sha(self):
        binary = b"source-owned-projector"
        info = {"filename": "projector.gguf", "max_bytes": len(binary) + 1,
                "sha256": hashlib.sha256(binary).hexdigest(),
                "url": "https://example.invalid/owned-fixture"}
        with TemporaryDirectory() as folder:
            with patch("scripts.run_native_model_trial.urlopen",
                       return_value=io.BytesIO(binary)):
                self.assertEqual(download(info, Path(folder)).read_bytes(), binary)

    def test_partial_oversize_or_wrong_digest_never_becomes_a_weight(self):
        payload = b"x" * 17
        for bad in ({"max_bytes": 8, "sha256": hashlib.sha256(payload).hexdigest()},
                    {"max_bytes": 20, "sha256": "0" * 64},
                    {"bytes": 18, "sha256": hashlib.sha256(payload).hexdigest()}):
            with self.subTest(bad=bad), TemporaryDirectory() as folder:
                info = {"filename": "invalid.gguf", "url": "https://example.invalid/test", **bad}
                with patch("scripts.run_native_model_trial.urlopen",
                           return_value=io.BytesIO(payload)):
                    with self.assertRaisesRegex(ValueError,
                            "download|identity|safety"):
                        download(info, Path(folder))
                self.assertFalse((Path(folder) / "invalid.gguf").exists())
                self.assertFalse((Path(folder) / "invalid.gguf.partial").exists())

    def test_unbounded_candidate_not_silently_accepted(self):
        base = {"filename": "invalid.gguf",
                "sha256": "0" * 64, "url": "https://example.invalid/test"}
        with TemporaryDirectory() as folder:
            for variant in ({}, {"max_bytes": True}, {"max_bytes": -4},
                            {"max_bytes": 10_000_000_001}):
                with self.subTest(variant=variant):
                    with self.assertRaisesRegex(ValueError, "safety bound|size|byte"):
                        download(dict(base, **variant), Path(folder))

    def test_alternative_brain_is_explicitly_unverified_and_source_pinned(self):
        manifest = json.loads((ROOT / "engines/velorn/local-model-trial-4b.candidate.json").read_text())
        model = manifest["model"]
        self.assertTrue(model["candidate_unverified_until_actual_download"])
        self.assertEqual(model["license"], "Apache-2.0")
        self.assertEqual(len(model["revision"]), 40)
        self.assertNotIn("verified", manifest)
        for entry in model["files"]:
            self.assertFalse(entry["download_and_hash_verified"])
            self.assertEqual(len(entry["sha256"]), 64)
            self.assertIn("/" + model["revision"] + "/", entry["url"])
            self.assertTrue("bytes" in entry or "max_bytes" in entry)


    def test_manifest_cannot_escape_runtime_root_or_fetch_local_urls(self):
        good = b"verified-fixture"
        checksum = hashlib.sha256(good).hexdigest()
        for name, url in (
            ("../escaped.gguf", "https://example.invalid/fixture"),
            ("nested/escaped.gguf", "https://example.invalid/fixture"),
            ("evil\\\\part.gguf", "https://example.invalid/fixture"),
            ("valid.gguf", "file:///etc/passwd"),
            ("valid.gguf", "http://127.0.0.1:8080/private"),
            ("valid.gguf", "https://me:secret@example.invalid/fixture"),
        ):
            with self.subTest(name=name, url=url), TemporaryDirectory() as root:
                spec = {"filename": name, "url": url, "bytes": len(good),
                        "sha256": checksum}
                with self.assertRaises(ValueError):
                    download(spec, Path(root))

    def test_symlink_target_is_refused_before_read_or_replace(self):
        binary = b"private unrelated file"
        with TemporaryDirectory() as root:
            root = Path(root)
            private = root / "private.txt"
            private.write_bytes(binary)
            (root / "model.gguf").symlink_to(private)
            entry = {"filename": "model.gguf",
                     "url": "https://example.invalid/fixture",
                     "bytes": len(binary),
                     "sha256": hashlib.sha256(binary).hexdigest()}
            with self.assertRaisesRegex(ValueError, "symbolic link"):
                download(entry, root)
            self.assertEqual(private.read_bytes(), binary)


if __name__ == "__main__":
    unittest.main()
