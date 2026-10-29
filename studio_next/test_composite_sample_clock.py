"""Physical regression gate for BODY's exact audio sample placement.

The differential operates on licensed synthetic PCM, real FFmpeg/FFprobe,
the actual BODY composite compiler and a separate sample-unit oracle.
Do not replace it with command-string assertions or a mocked renderer.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.research_audio_clock import measure


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "Actual FFmpeg/FFprobe are required for the sample-clock contract")
class CompositeAudioSampleClockTests(unittest.TestCase):
    def test_real_legacy_composition_matches_sample_clock_oracle(self):
        with tempfile.TemporaryDirectory(prefix="zx7-audio-regression-") as directory:
            rows = measure(Path(directory))
        self.assertEqual(len(rows), 108)
        failures = [row for row in rows if not row["matches"]]
        self.assertFalse(failures,
                         f"{len(failures)} real decoded sample-clock failures; "
                         f"first: {failures[0] if failures else None}")


if __name__ == "__main__":
    unittest.main()
