import tempfile
import unittest
import wave
from pathlib import Path

from motion_studio.voice import write_silent_voice_slot


class NarratorSceneSilenceTests(unittest.TestCase):
    def test_unspoken_beat_produces_actual_measured_pcm_not_fake_tts(self):
        with tempfile.TemporaryDirectory() as root:
            output=Path(root)/"voice-01.wav"
            seconds=write_silent_voice_slot(output)
            self.assertTrue(output.is_file())
            with wave.open(str(output),"rb") as audio:
                self.assertEqual(audio.getnchannels(),1)
                self.assertEqual(audio.getsampwidth(),2)
                self.assertEqual(audio.getframerate(),16000)
                self.assertEqual(audio.getnframes(),800)
                self.assertEqual(audio.readframes(audio.getnframes()),b"\x00\x00"*800)
            self.assertAlmostEqual(seconds,.05)

    def test_slot_does_not_choose_an_unrequested_voice_or_invent_audio(self):
        with tempfile.TemporaryDirectory() as root:
            f=Path(root)/"silence.wav"
            for seconds in (-1,0,12):
                with self.assertRaises(ValueError):
                    write_silent_voice_slot(f,seconds=seconds)
            self.assertFalse(f.exists())


if __name__=="__main__":
    unittest.main()
