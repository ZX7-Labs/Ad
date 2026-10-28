import tempfile
import shutil
import subprocess
import json
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
            self.assertEqual(calls[0][calls[0].index("-map")+1],"0:v")
            self.assertIn(["-map","0:a?"],[calls[0][i:i+2]
                for i in range(len(calls[0])-1)])
            self.assertNotIn("0:a:0?",calls[0])

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

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                         "Real multi-track FFmpeg decoders required")
    def test_actual_two_original_audio_streams_are_decoded_not_just_primary(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/"two-original-soundtracks.mp4"
            subprocess.run(["ffmpeg","-hide_banner","-loglevel","error",
                "-f","lavfi","-i","color=c=green:s=64x48:r=12:d=1",
                "-f","lavfi","-i","sine=frequency=440:duration=1",
                "-f","lavfi","-i","sine=frequency=880:duration=1",
                "-map","0:v:0","-map","1:a:0","-map","2:a:0",
                "-c:v","libx264","-pix_fmt","yuv420p","-frames:v","12",
                "-c:a","aac","-y",str(source)],check=True,timeout=40)
            observed=json.loads(subprocess.check_output(["ffprobe","-v","error",
                "-select_streams","a","-show_entries","stream=index",
                "-of","json",str(source)],timeout=40))
            self.assertEqual(len(observed["streams"]),2)
            emitted=[]
            def physical_run(argv,**kwargs):
                emitted.append(argv)
                return subprocess.run(argv,**kwargs)
            result=full_decode_inspection(source,runner=physical_run,
                expected={"width":64,"height":48,"require_audio":True})
            self.assertTrue(result["technical_delivery_verified"],result)
            self.assertEqual(emitted[0][emitted[0].index("-map")+1],"0:v")
            self.assertIn(["-map","0:a?"],[emitted[0][i:i+2]
                for i in range(len(emitted[0])-1)])
            self.assertIsNotNone(result["audio_measurements"])
            self.assertIn("primary audio",result["audio_measurements"]["measurement"])
            # Original custody is the initial trust boundary: independently
            # decode every track BEFORE rights-attesting the complete asset.
            from studio_next.media_vault import verify_media_container
            original_run=subprocess.run
            physical_commands=[]
            def recorded(argv,**kwargs):
                if argv and argv[0]=="ffmpeg":
                    physical_commands.append(argv)
                return original_run(argv,**kwargs)
            with patch("subprocess.run",side_effect=recorded):
                verify_media_container(source,"video/mp4")
            full_mapping=[c for c in physical_commands if "-xerror" in c]
            self.assertEqual(len(full_mapping),1,physical_commands)
            self.assertIn(["-map","0:v"],[full_mapping[0][i:i+2]
                for i in range(len(full_mapping[0])-1)])
            self.assertIn(["-map","0:a?"],[full_mapping[0][i:i+2]
                for i in range(len(full_mapping[0])-1)])

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
