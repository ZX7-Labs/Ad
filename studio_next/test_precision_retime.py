"""Adversarial + real audiovisual tests of frame-precise artist-selected speed ramps."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from studio_next.precision_retime import _speed,_tempo_chain,plan_retime,retime_command,render_retime
from studio_next.media_vault import MediaVault
from studio_next.body_integration import body_catalog
from studio_next.body_materials import fingerprint_physical_inputs
from studio_next.delivery_audit import _probe_details


class RetimeContractTests(unittest.TestCase):
    def test_exact_rational_and_no_default_edit_style(self):
        self.assertEqual(_speed({"numerator":300,"denominator":1000}),Fraction(3,10))
        self.assertEqual(_tempo_chain(Fraction(8,1)),"atempo=2,atempo=2,atempo=2")
        self.assertEqual(_tempo_chain(Fraction(1,8)),"atempo=0.5,atempo=0.5,atempo=0.5,atempo=1")
        for q in ({"numerator":True,"denominator":1},
                  {"numerator":0,"denominator":2},
                  {"numerator":1,"denominator":0},
                  {"numerator":100000,"denominator":1},{}):
            with self.assertRaises(ValueError):
                _speed(q)
    def test_prepared_tool_filter_does_not_interpret_model_code(self):
        spec={"source":Path("/trusted/media.mp4"),"fps":Fraction(24000,1001),
              "audio":"preserve_source",
              "parts":[{"first":11,"end":22,"speed":Fraction(3,4),
                        "duration":Fraction(11,1)/Fraction(24000,1001)}]}
        cmd=retime_command(spec,"/tmp/render.mp4")
        self.assertEqual(cmd[0],"ffmpeg")
        self.assertIn("trim=start_frame=11:end_frame=22",cmd[cmd.index("-filter_complex")+1])
        self.assertIn("atempo=0.75",cmd[cmd.index("-filter_complex")+1])
        self.assertEqual(cmd[-1],"/tmp/render.mp4")


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "Actual FFmpeg needed; live release runner covers this path")
class PhysicalRetimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.src=self.root/"owner_capture.mp4"
        subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
            "-f","lavfi","-i","testsrc2=size=160x90:rate=24:duration=2",
            "-f","lavfi","-i","sine=frequency=440:sample_rate=48000:duration=2",
            "-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac","-shortest",
            str(self.src)],check=True,timeout=50)
        self.vault=MediaVault(self.root/"vault")
        att=self.vault.ingest(self.src,mime="video/mp4",rights="owner_supplied",
            source_type="owner_upload",source_id="test-original-camera-clip",
            evidence="Owner-created real original footage fixture",
            owner_or_generator="owner")
        self.plan={"source":self.src.name,"asset_id":att["asset_id"],
                   "attestation_id":att["attestation_id"],
                   "source_fps":{"numerator":24,"denominator":1},
                   "segments":[
                       {"first_frame":0,"end_frame":24,
                        "speed":{"numerator":1,"denominator":2}},
                       {"first_frame":24,"end_frame":48,
                        "speed":{"numerator":2,"denominator":1}}],
                   "audio":"preserve_source"}
        self.plan_file=self.root/"retime.json"
        self.save()

    def tearDown(self):
        self.temp.cleanup()

    def save(self): self.plan_file.write_text(json.dumps(self.plan),encoding="utf-8")

    def test_real_2_5_second_video_and_original_audio_continuity(self):
        checked=plan_retime(self.plan,self.root,self.root/"vault")
        self.assertEqual(checked["expected_seconds"],2.5)
        result=render_retime(self.plan_file,self.root,self.root/"vault",
                             self.root/"newly-edited.mp4")
        self.assertEqual(result["retime_operations"],2)
        self.assertLess(abs(result["duration_seconds"]-2.5),0.14)
        self.assertTrue(result["audio_present"])
        meta=_probe_details(self.root/"newly-edited.mp4")
        self.assertEqual((meta["width"],meta["height"]),(160,90))
        self.assertTrue(meta["audio_stream_present"])
        # Physical video + audio both decode completely, not just header scan.
        subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-xerror",
            "-i",str(self.root/"newly-edited.mp4"),"-map","0:v:0",
            "-map","0:a:0","-f","null","-"],check=True,timeout=60)

    def test_body_registry_exposes_real_registered_operation_and_source_material(self):
        tools={x["id"]:x for x in body_catalog(self.root).discover()}
        self.assertEqual(tools["body.retime"]["status"],"installed")
        self.assertEqual(tools["body.retime"]["schema"]["required"],["plan","out"])
        materials=fingerprint_physical_inputs("body.retime",{"plan":"retime.json",
                  "out":"timeline-v2.mp4"},self.root)
        self.assertIn("owner_capture.mp4",[x["relative"] for x in materials])
        self.assertIn("retime.json",[x["relative"] for x in materials])

    def test_mutated_media_and_rights_proof_rejected_before_encoder(self):
        self.src.write_bytes(self.src.read_bytes()+b"owner footage changed")
        with self.assertRaises(ValueError):
            plan_retime(self.plan,self.root,self.root/"vault")
        self.assertFalse((self.root/"unlicensed.mp4").exists())

    def test_source_frame_range_missing_audio_and_path_traversal_rejected(self):
        self.plan["segments"][0]["end_frame"]=10000
        with self.assertRaisesRegex(ValueError,"beyond source"):
            plan_retime(self.plan,self.root,self.root/"vault")
        self.plan["segments"][0]["end_frame"]=24
        self.plan["source"]="../owner_capture.mp4"
        with self.assertRaises(ValueError):
            plan_retime(self.plan,self.root,self.root/"vault")
        self.plan["source"]=self.src.name
        self.plan["source_fps"]={"numerator":30,"denominator":1}
        with self.assertRaisesRegex(ValueError,"rate"):
            plan_retime(self.plan,self.root,self.root/"vault")

    def test_explicit_silence_is_physical_and_audible_media_never_fabricated(self):
        self.plan["audio"]="intentional_silence";self.save()
        result=render_retime(self.plan_file,self.root,self.root/"vault",
                             self.root/"intentionally-silent.mp4")
        self.assertTrue(result["audio_present"])
        self.assertLess(abs(result["duration_seconds"]-2.5),0.14)
        self.plan["audio"]="unlicensed-music"
        with self.assertRaises(ValueError):
            plan_retime(self.plan,self.root,self.root/"vault")


if __name__=="__main__":
    unittest.main()
