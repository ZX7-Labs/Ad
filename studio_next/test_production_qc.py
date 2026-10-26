import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from studio_next.production_qc import full_decode_inspection

class FullPhysicalFilmDecodeQA(unittest.TestCase):
    def test_audio_peak_not_aesthetics_measured_after_full_media_decode(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"original.mp4";p.write_bytes(b"encoded"*100)
            meta={"width":1920,"height":816,"duration_seconds":5.2,
                  "audio_stream_present":True}
            calls=[]
            def fake(cmd,**kwargs):
                calls.append(cmd)
                if "volumedetect" in cmd:
                    return SimpleNamespace(returncode=0,stderr="max_volume: -1.2 dB\nmean_volume: -21.1 dB")
                return SimpleNamespace(returncode=0,stderr="")
            with patch("studio_next.production_qc._probe_details",return_value=meta):
                result=full_decode_inspection(p,runner=fake,expected={
                  "width":1920,"height":816,"duration_seconds":5.2,
                  "require_audio":True})
            self.assertEqual(result["audio_measurements"]["max_volume_dbfs"],"-1.2")
            self.assertTrue(result["technical_delivery_verified"])
            self.assertFalse(result["aesthetic_or_human_approval"])
            self.assertEqual(len(calls),2)
            self.assertIn("-xerror",calls[0])

    def test_decoder_failure_and_missing_sound_never_claim_success(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"truth.mp4";p.write_bytes(b"movie"*100)
            meta={"width":1280,"height":720,"duration_seconds":6.1,
                  "audio_stream_present":False}
            with patch("studio_next.production_qc._probe_details",return_value=meta):
                result=full_decode_inspection(p,runner=lambda *a,**k:SimpleNamespace(returncode=1),
                    expected={"require_audio":True})
            self.assertFalse(result["technical_delivery_verified"])
            self.assertEqual(len(result["delivery_mismatches"]),2)

    def test_never_invent_strict_limits_on_original_artistic_darkness_or_silence(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"still.mp4";p.write_bytes(b"movie"*100)
            meta={"width":900,"height":900,"duration_seconds":188.0,
                  "audio_stream_present":False}
            with patch("studio_next.production_qc._probe_details",return_value=meta):
                observed=full_decode_inspection(p,
                    runner=lambda *a,**k:SimpleNamespace(returncode=0),
                    expected={"width":900,"height":900})
            self.assertTrue(observed["technical_delivery_verified"])
            self.assertIsNone(observed["audio_measurements"])

if __name__=="__main__":unittest.main()
