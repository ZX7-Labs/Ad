"""Real decoded WAV listening excerpt from an authorized native video export."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import wave

from studio_next.body_editor_audio import observe_verified_export_audio
from studio_next.body_editor_client import EditorAccessError
from studio_next.body_editor_policy import EditorPathPolicy
from studio_next.media_vault import sha256_file


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "Requires real FFmpeg/FFprobe and physical A/V files")
class VerifiedNativeAudioTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.projects, self.staging, self.outputs = (root / x for x in
                                                      ("projects", "staging", "outputs"))
        for p in (self.projects, self.staging, self.outputs):
            p.mkdir()
        self.policy = EditorPathPolicy(self.projects, self.staging, self.outputs)
        self.movie = self.outputs / "genuine-source.mp4"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                        "-f", "lavfi", "-i", "testsrc2=s=320x180:r=12:d=2",
                        "-f", "lavfi", "-i", "sine=f=440:r=48000:d=2",
                        "-map", "0:v", "-map", "1:a",
                        "-c:v", "mpeg4", "-c:a", "aac", "-shortest",
                        str(self.movie)], check=True, timeout=40)
        self.digest = sha256_file(self.movie)

    def listen(self, **overrides):
        args = {"policy": self.policy, "verified_sha256": self.digest,
                "start_seconds": .25, "duration_seconds": 1.0}
        args.update(overrides)
        return observe_verified_export_audio(str(self.movie), **args)

    def test_genuine_audio_is_playable_source_bound_mono_wav_not_spatial_master(self):
        wav_bytes, proof = self.listen()
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
            self.assertEqual((wav.getnchannels(), wav.getframerate(), wav.getsampwidth()),
                             (1, 16000, 2))
            self.assertGreater(wav.getnframes(), 12000)
            self.assertLessEqual(wav.getnframes(), 16000)
        self.assertEqual(proof["export_sha256"], self.digest)
        self.assertEqual(proof["wav_sha256"], hashlib.sha256(wav_bytes).hexdigest())
        self.assertTrue(proof["preview_downmixed_and_resampled"])
        self.assertFalse(proof["full_film_listening_or_spatial_mix_verified"])
        self.assertFalse(proof["human_or_artistic_quality_approved"])
        self.assertIsNotNone(proof["preview_rms_dbfs"])
        self.assertGreater(proof["preview_peak_normalized"], .01)
        json.dumps(proof, allow_nan=False)
        self.assertEqual(sha256_file(self.movie), self.digest)

    def test_no_audio_stream_is_rejected_not_mislabeled_as_silence(self):
        silent_video = self.outputs / "no-audio.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                        "testsrc2=s=160x90:r=12:d=2", "-an", "-c:v", "mpeg4",
                        str(silent_video)], check=True, timeout=30)
        with self.assertRaisesRegex(ValueError, "no physical audio stream"):
            observe_verified_export_audio(str(silent_video), policy=self.policy,
                verified_sha256=sha256_file(silent_video),
                start_seconds=0, duration_seconds=1)

    def test_invalid_requests_and_stale_verification_are_rejected(self):
        for options in ({"start_seconds": -1}, {"start_seconds": 1.5, "duration_seconds": 1},
                        {"start_seconds": float("nan")}, {"start_seconds": True},
                        {"duration_seconds": 4}, {"duration_seconds": 0},
                        {"duration_seconds": float("inf")}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.listen(**options)
        with self.assertRaises(ValueError):
            self.listen(verified_sha256="f"*64)
        self.movie.write_bytes(self.movie.read_bytes() + b"mutated")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.listen()

    def test_original_project_staging_and_symlink_paths_are_not_observable(self):
        link = self.outputs / "linked.mp4"
        link.symlink_to(self.movie)
        outside = self.staging / "original.mp4"
        outside.write_bytes(self.movie.read_bytes())
        for p in (link, outside):
            with self.subTest(path=p), self.assertRaises(EditorAccessError):
                observe_verified_export_audio(str(p), policy=self.policy,
                    verified_sha256=sha256_file(p),
                    start_seconds=0, duration_seconds=.5)

    def test_decoder_never_buffers_unbounded_output_or_error(self):
        from unittest.mock import patch
        original = subprocess.run
        observed = []
        def intercept(command, **kwargs):
            if command[0] == "ffmpeg":
                observed.append(command)
                self.assertNotEqual(kwargs.get("stdout"), subprocess.PIPE)
                self.assertEqual(kwargs.get("stderr"), subprocess.DEVNULL)
                self.assertIn("-fs", command)
            return original(command, **kwargs)
        with patch("studio_next.body_editor_audio.subprocess.run", side_effect=intercept):
            audio, _ = self.listen()
        self.assertEqual(len(observed), 1)
        self.assertGreater(len(audio), 5000)


if __name__ == "__main__":
    unittest.main()
