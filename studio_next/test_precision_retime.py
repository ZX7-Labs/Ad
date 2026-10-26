"""Adversarial + real audiovisual tests of frame-precise artist-selected speed ramps."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from fractions import Fraction
from unittest.mock import patch
from pathlib import Path

from studio_next.precision_retime import _speed,_tempo_chain,_verify_decoded_frame_clock,plan_retime,retime_command,render_retime
from studio_next.media_vault import MediaVault
from studio_next.body_integration import body_catalog
from studio_next.body_materials import fingerprint_physical_inputs
from studio_next.delivery_audit import _probe_details


class RetimeContractTests(unittest.TestCase):
    def test_exact_rational_and_no_default_edit_style(self):
        self.assertEqual(_speed({"numerator":300,"denominator":1000}),Fraction(3,10))
        self.assertEqual(_tempo_chain(Fraction(8,1)),"atempo=2,atempo=2,atempo=2")
        self.assertEqual(_tempo_chain(Fraction(1,8)),"atempo=0.5,atempo=0.5,atempo=0.5")
        for q in ({"numerator":True,"denominator":1},
                  {"numerator":0,"denominator":2},
                  {"numerator":1,"denominator":0},
                  {"numerator":100000,"denominator":1},{}):
            with self.assertRaises(ValueError):
                _speed(q)
    def test_every_decoded_frame_pts_must_match_exact_original_clock(self):
        # Avg fps equals 24 in each case; mid-stream irregularity is still
        # fatal. B-frame first-record SEI side data does not hide real PTS.
        valid="0.000000,H.264 User Data SEI\n0.041667\n0.083333\n0.125000\n0.166667\n"
        def audit(rows):
            completed=subprocess.CompletedProcess(["ffprobe"],0,
                                         stdout=rows,stderr="")
            with patch("studio_next.precision_retime.subprocess.run",
                       return_value=completed) as running:
                return _verify_decoded_frame_clock(
                    Path("/original/film.mp4"),Fraction(24,1),5)
        self.assertEqual(audit(valid),5)
        for bad in (
            "0.000000\n0.041667\n0.083333\n0.145000\n0.166667\n",
            "0.000000\n0.041667\n0.041667\n0.125000\n0.166667\n",
            "0.000000\n0.041667\n0.083333\n0.125000\n",
            "0.000000\n0.041667\n0.083333\n0.125000\n0.166667\n0.208333\n",
            "0.000000\n0.041667\nnan\n0.125000\n0.166667\n"
        ):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError,
                         "Variable-rate|frame timestamps|PTS"):
                    audit(bad)

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

    def test_actual_motion_compensated_slow_motion_uses_native_flow_and_real_sound(self):
        installed=subprocess.run(["ffmpeg","-hide_banner","-filters"],
            capture_output=True,text=True,timeout=15,check=True)
        if not any(line.split()[1:2]==["minterpolate"]
                   for line in installed.stdout.splitlines()):
            self.skipTest("No actual FFmpeg minterpolate host capability")
        self.plan["interpolation"]="motion_compensated"
        self.save()
        checked=plan_retime(self.plan,self.root,self.root/"vault")
        self.assertEqual(checked["interpolation"],"motion_compensated")
        graph=retime_command(checked,self.root/"native-flow.mp4")
        self.assertIn("minterpolate=fps=24/1:mi_mode=mci",
                      graph[graph.index("-filter_complex")+1])
        destination=self.root/"owner-motion-interpolation.mp4"
        native=render_retime(self.plan_file,self.root,self.root/"vault",destination)
        self.assertTrue(native["verified_physically"])
        self.assertTrue(native["native_motion_compensated_interpolation_physically_proven"])
        self.assertAlmostEqual(native["duration_seconds"],2.5,delta=.14)
        movie=_probe_details(destination)
        self.assertEqual((movie["width"],movie["height"]),(160,90))
        self.assertTrue(movie["audio_stream_present"])
        self.assertFalse(native["optical_flow_is_not_independent_artistic_approval"] is False)
        for forged in (None,True,"unverified_ai","frame_interpolation_gpu",42):
            self.plan["interpolation"]=forged
            with self.subTest(value=forged):
                with self.assertRaisesRegex(ValueError,"frame-repeat or optical-flow"):
                    plan_retime(self.plan,self.root,self.root/"vault")

    def test_body_registry_exposes_real_registered_operation_and_source_material(self):
        tools={x["id"]:x for x in body_catalog(self.root).discover()}
        self.assertEqual(tools["body.retime"]["status"],"installed")
        self.assertEqual(tools["body.retime"]["schema"]["required"],["plan","out"])
        materials=fingerprint_physical_inputs("body.retime",{"plan":"retime.json",
                  "out":"timeline-v2.mp4"},self.root)
        self.assertIn("owner_capture.mp4",[x["relative"] for x in materials])
        self.assertIn("retime.json",[x["relative"] for x in materials])

    def test_actual_source_independent_retimming_over_content_hash_identity(self):
        self.plan["source"]="zx7:sha256:"+self.plan["asset_id"]
        self.save()
        proof=fingerprint_physical_inputs("body.retime",
            {"plan":"retime.json","out":"verified-artist-speed.mp4"},self.root)
        self.assertIn(self.plan["asset_id"],[x["sha256"] for x in proof])
        result=render_retime(self.plan_file,self.root,self.root/"vault",
                            self.root/"verified-artist-speed.mp4")
        self.assertLess(abs(result["duration_seconds"]-2.5),0.14)
        self.assertTrue(_probe_details(self.root/"verified-artist-speed.mp4")["audio_stream_present"])
        self.plan["source"]="zx7:sha256:"+("0"*64)
        with self.assertRaises(ValueError):
            plan_retime(self.plan,self.root,self.root/"vault")

    def test_mutable_camera_checkout_swap_during_real_speed_render_keeps_original_frame_audio(self):
        from studio_next.media_vault import sha256_file
        original=self.src.read_bytes()
        actual_run=subprocess.run
        seen=[]
        def malicious_swap(argv,**kwargs):
            if argv and argv[0]=="ffmpeg" and "-filter_complex" in argv:
                index=argv.index("-i")
                protected=Path(argv[index+1])
                self.assertIn(".zx7-owned-sources-",str(protected))
                self.assertFalse(protected.stat().st_mode & 0o222)
                self.assertEqual(sha256_file(protected),self.plan["asset_id"])
                seen.append(protected)
                self.src.write_bytes(b"untrusted replacement while real retime executes")
                try:
                    return actual_run(argv,**kwargs)
                finally:
                    self.src.write_bytes(original)
            return actual_run(argv,**kwargs)
        with patch("studio_next.precision_retime.subprocess.run",
                   side_effect=malicious_swap):
            receipt=render_retime(self.plan_file,self.root,self.root/"vault",
                                  self.root/"actual-sealed-slow-fast.mp4")
        self.assertEqual(len(seen),1)
        self.assertFalse(seen[0].exists())
        self.assertFalse(list(self.root.glob(".zx7-owned-sources-*")))
        self.assertEqual(sha256_file(self.src),self.plan["asset_id"])
        self.assertTrue(receipt["sealed_original_cas_during_decode"])
        self.assertTrue(receipt["full_picture_and_sound_decoder_completed"])
        self.assertAlmostEqual(receipt["duration_seconds"],2.5,delta=.14)

    def test_concurrent_master_is_not_unlinked_by_losing_speed_editor(self):
        master=self.root/"protected-original-director-speed.mp4"
        protected=b"APPROVED-DIRECTOR-RESULT-DO-NOT-REPLACE"
        actual_run=subprocess.run
        def other_artist_wins(argv,**kwargs):
            finished=actual_run(argv,**kwargs)
            if argv and argv[0]=="ffmpeg" and "-filter_complex" in argv:
                master.write_bytes(protected)
            return finished
        with patch("studio_next.precision_retime.subprocess.run",
                   side_effect=other_artist_wins):
            with self.assertRaises(FileExistsError):
                render_retime(self.plan_file,self.root,self.root/"vault",master)
        self.assertEqual(master.read_bytes(),protected)

    def test_original_video_longer_than_original_audio_not_preserved_by_speed_map(self):
        video=self.root/"two-second-picture-one-second-voice.mp4"
        command=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
            "-f","lavfi","-i","testsrc2=size=160x90:rate=24:duration=2",
            "-f","lavfi","-i",
            "sine=frequency=600:sample_rate=48000:duration=1",
            "-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac",str(video)]
        subprocess.run(command,check=True,capture_output=True,timeout=60)
        proof=self.vault.ingest(video,mime="video/mp4",
            rights="owner_supplied",source_type="owner_upload",
            source_id="actual-picture-longer-than-narration",
            evidence="Physical independent original picture/sound stream lengths",
            owner_or_generator="owner")
        self.plan.update(source=video.name,asset_id=proof["asset_id"],
                         attestation_id=proof["attestation_id"])
        with self.assertRaisesRegex(ValueError,"recorded-audio stream"):
            plan_retime(self.plan,self.root,self.root/"vault")
        self.plan["audio"]="intentional_silence"
        validated=plan_retime(self.plan,self.root,self.root/"vault")
        self.assertEqual(validated["expected_seconds"],2.5)

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
