"""Physically decoded visual feedback for an authorized completed native edit."""
import hashlib
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from studio_next.body_editor_frame import observe_verified_export_frame
from studio_next.body_editor_policy import EditorPathPolicy
from studio_next.body_editor_client import EditorAccessError
from studio_next.media_vault import sha256_file


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "Requires a real physical A/V decoder")
class NativeEditorVisualFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.projects, self.staging, self.outputs = (root / name for name in
                                                     ("projects", "staging", "outputs"))
        for item in (self.projects, self.staging, self.outputs):
            item.mkdir()
        self.policy = EditorPathPolicy(self.projects, self.staging, self.outputs)
        self.source = self.outputs / "review.mp4"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                        "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=12:duration=1",
                        "-c:v", "mpeg4", str(self.source)], check=True, timeout=30)
        self.digest = sha256_file(self.source)

    def sample(self, **options):
        return observe_verified_export_frame(str(self.source), policy=self.policy,
                                            verified_sha256=self.digest, **options)

    def test_real_verified_frame_matches_actual_video_and_has_bounded_png(self):
        png, receipt = self.sample(at_seconds=0.5)
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual((receipt["observed_picture_width"],
                          receipt["observed_picture_height"]), (320, 180))
        self.assertEqual(receipt["png_sha256"], hashlib.sha256(png).hexdigest())
        self.assertEqual(receipt["export_sha256"], self.digest)
        self.assertFalse(receipt["sampled_video_seconds_exact_pts_proven"])
        self.assertFalse(receipt["human_or_artistic_quality_approved"])

    def test_bad_time_and_bad_hash_fail_closed(self):
        for time_value in (float("nan"), float("inf"), -1, True, 1.1):
            with self.subTest(time_value=time_value), self.assertRaises(ValueError):
                self.sample(at_seconds=time_value)
        with self.assertRaises(ValueError):
            observe_verified_export_frame(str(self.source), policy=self.policy,
                verified_sha256="0" * 64, at_seconds=0.5)

    def test_mutation_since_export_proof_is_rejected(self):
        self.source.write_bytes(self.source.read_bytes() + b"modified after verified export")
        with self.assertRaisesRegex(ValueError, "no longer match"):
            self.sample(at_seconds=0.5)

    def test_out_of_root_and_symbolic_link_observation_are_denied(self):
        other = self.staging / "not-authorized.mp4"
        other.write_bytes(self.source.read_bytes())
        link = self.outputs / "alias.mp4"
        link.symlink_to(self.source)
        project_original = self.projects / "not-an-export.mp4"
        project_original.write_bytes(self.source.read_bytes())
        for item in (other, link, project_original):
            with self.subTest(item=item), self.assertRaises(EditorAccessError):
                observe_verified_export_frame(str(item), policy=self.policy,
                    verified_sha256=self.digest, at_seconds=0.5)


if __name__ == "__main__":
    unittest.main()
