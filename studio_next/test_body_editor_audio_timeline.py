"""Physical A/V tests for actual non-template temporal audio sensing."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from studio_next.body_editor_audio_timeline import observe_verified_export_audio_timeline
from studio_next.body_editor_client import EditorAccessError
from studio_next.body_editor_policy import EditorPathPolicy
from studio_next.media_vault import sha256_file


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "Real audio timeline requires FFmpeg and FFprobe")
class VerifiedAudioTimelineTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        p, s, o = (root / n for n in ("projects", "staging", "outputs"))
        for x in (p, s, o):
            x.mkdir()
        self.policy = EditorPathPolicy(p, s, o)
        self.movie = o / "four-seconds.mp4"
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
            "-f", "lavfi", "-i", "testsrc2=s=160x90:r=12:d=4",
            "-f", "lavfi", "-i", "sine=f=440:r=48000:d=2",
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono:d=2",
            "-filter_complex", "[1:a][2:a]concat=n=2:v=0:a=1[a]",
            "-map", "0:v", "-map", "[a]", "-c:v", "mpeg4",
            "-c:a", "aac", "-shortest", str(self.movie)
        ], check=True, timeout=45)
        self.sha = sha256_file(self.movie)

    def observe(self, **changes):
        data = {"policy": self.policy, "verified_sha256": self.sha,
                "start_seconds": 0, "duration_seconds": 4, "bins": 8}
        data.update(changes)
        return observe_verified_export_audio_timeline(str(self.movie), **data)

    def test_actual_time_signal_distinguishes_audible_and_silent_film_halves(self):
        receipt = self.observe()
        self.assertEqual(receipt["kind"], "verified_native_editor_audio_temporal_envelope")
        self.assertEqual(receipt["export_sha256"], self.sha)
        self.assertEqual(receipt["observed_pcm_samples"], 32000)
        self.assertEqual(len(receipt["intervals"]), 8)
        self.assertFalse(receipt["exact_original_audio_pts_proven"])
        self.assertFalse(receipt["full_resolution_or_multichannel_audio_proven"])
        self.assertFalse(receipt["integrated_lufs_or_true_peak_proven"])
        self.assertFalse(receipt["human_or_artistic_quality_approved"])
        for entry in receipt["intervals"][:3]:
            self.assertGreater(entry["sample_peak_normalized"], 0.02)
            self.assertGreater(entry["rms_dbfs"], -45)
        for entry in receipt["intervals"][5:]:
            self.assertLess(entry["sample_peak_normalized"], 0.008)
        self.assertEqual(receipt["intervals"][0]["decode_relative_start_seconds"], 0)
        self.assertEqual(receipt["intervals"][-1]["decode_relative_end_seconds"], 4)
        json.dumps(receipt, allow_nan=False)
        self.assertEqual(sha256_file(self.movie), self.sha)

    def test_time_window_can_observe_a_short_derived_interval(self):
        r = self.observe(start_seconds=2.5, duration_seconds=1, bins=4)
        self.assertEqual(len(r["intervals"]), 4)
        self.assertTrue(all(e["sample_peak_normalized"] < 0.008 for e in r["intervals"]))

    def test_reject_invalid_time_bins_changed_source_and_path_escapes(self):
        for params in ({"bins": 0}, {"bins": 257}, {"bins": True},
                       {"duration_seconds": 0}, {"duration_seconds": 301},
                       {"start_seconds": 3.5, "duration_seconds": 1},
                       {"start_seconds": float("nan")}, {"start_seconds": True},
                       {"duration_seconds": float("inf")},
                       {"duration_seconds": .0001, "bins": 100},
                       {"verified_sha256": "f" * 64}):
            with self.subTest(params=params), self.assertRaises(ValueError):
                self.observe(**params)
        link = self.policy.outputs_root / "linked.mp4"
        link.symlink_to(self.movie)
        with self.assertRaises(EditorAccessError):
            observe_verified_export_audio_timeline(str(link), policy=self.policy,
                verified_sha256=self.sha, start_seconds=0, duration_seconds=1)
        staging = self.policy.staging_root / "private.mp4"
        staging.write_bytes(self.movie.read_bytes())
        with self.assertRaises(EditorAccessError):
            observe_verified_export_audio_timeline(str(staging), policy=self.policy,
                verified_sha256=self.sha, start_seconds=0, duration_seconds=1)
        self.movie.write_bytes(self.movie.read_bytes() + b"altered")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.observe()

    def test_decoder_stdout_spools_to_disk_and_enforces_output_limit(self):
        original = subprocess.run
        caught = []
        def inspected(argv, **kwargs):
            if argv[0] == "ffmpeg":
                self.assertNotEqual(kwargs.get("stdout"), subprocess.PIPE)
                self.assertEqual(kwargs.get("stderr"), subprocess.DEVNULL)
                self.assertIn("-fs", argv)
                caught.append(argv)
            return original(argv, **kwargs)
        with patch("studio_next.body_editor_audio_timeline.subprocess.run",
                   side_effect=inspected):
            self.observe()
        self.assertEqual(len(caught), 1)

    def test_no_audio_track_is_not_invented_silence(self):
        no_audio = self.policy.outputs_root / "picture-only.mp4"
        subprocess.run([
            "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
            "testsrc2=s=160x90:r=12:d=2", "-an", "-c:v", "mpeg4",
            str(no_audio)], check=True, timeout=30)
        with self.assertRaisesRegex(ValueError, "no actual audio track"):
            observe_verified_export_audio_timeline(
                str(no_audio), policy=self.policy,
                verified_sha256=sha256_file(no_audio),
                start_seconds=0, duration_seconds=1, bins=8)


if __name__ == "__main__":
    unittest.main()
