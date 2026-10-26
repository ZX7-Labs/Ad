"""Physical frame-by-frame licensed cinema evidence, not fictitious AI taste."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_next.body_temporal_evidence import (
    observe_every_original_frame,verify_full_temporal_evidence)
from studio_next.body_integration import body_catalog,validate_witness
from studio_next.media_vault import MediaVault,sha256_file


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "Physical original picture/sound encoder and decoder required")
class FullLicensedFilmTemporalSensor(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.movie=self.root/"original-red-to-blue.mp4"
        command=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
            "-f","lavfi","-i","color=c=red:s=96x54:r=12:d=1",
            "-f","lavfi","-i","color=c=blue:s=96x54:r=12:d=1",
            "-f","lavfi","-i","sine=frequency=440:sample_rate=48000:duration=2",
            "-filter_complex","[0:v][1:v]concat=n=2:v=1:a=0[v]",
            "-map","[v]","-map","2:a:0",
            "-c:v","libx264","-pix_fmt","yuv420p",
            "-color_primaries","bt709","-color_trc","bt709",
            "-colorspace","bt709","-c:a","aac","-b:a","128k",
            "-shortest",str(self.movie)]
        p=subprocess.run(command,capture_output=True,text=True,timeout=60)
        self.assertEqual(p.returncode,0,p.stderr)
        self.vault=MediaVault(self.root/"vault")
        self.custody=self.vault.ingest(self.movie,mime="video/mp4",
            rights="owner_supplied",source_type="owner_upload",
            source_id="exact-real-film-reel",evidence="Owner-provided color-change fixture",
            owner_or_generator="authorized-owner")
        self.plan={"media":{
            "source":"zx7:sha256:"+self.custody["asset_id"],
            "asset_id":self.custody["asset_id"],
            "attestation_id":self.custody["attestation_id"]},
            "preview":{"width":48,"height":27}}
        self.planfile=self.root/"review-every-original-frame.json"
        self.planfile.write_text(json.dumps(self.plan))
    def tearDown(self):
        self.temp.cleanup()

    def test_actual_all_frames_including_cut_boundary_and_sound_observed(self):
        src_sha=sha256_file(self.movie)
        catalog=body_catalog(self.root)
        self.assertEqual({t["id"]:t for t in catalog.discover()}[
            "body.temporal_evidence"]["status"],"installed")
        args={"plan":self.planfile.name,"out":"measured-all-frames.json"}
        witnesses=catalog.trusted_material_fingerprint("body.temporal_evidence",args)
        self.assertIn(src_sha,[row["sha256"] for row in witnesses])
        result=catalog.invoke("body.temporal_evidence",args,
                              allowed_access={"read","write"})
        self.assertTrue(validate_witness("body.temporal_evidence",result))
        self.assertTrue(result["original_sound_physically_measured"])
        self.assertTrue(result["original_sound_covers_entire_picture"])
        self.assertEqual(result["actual_full_movie_frame_count"],24)
        report=json.loads((self.root/"measured-all-frames.json").read_text())
        self.assertEqual(report["picture_frames_observed"],24)
        self.assertTrue(report["complete_original_video_and_sound_decoded"])
        self.assertFalse(report["creative_quality_or_continuity_certified"])
        self.assertEqual(report["original_movie_sha256"],src_sha)
        self.assertEqual(len(report["frames"]),24)
        diffs=[x["previous_frame_mean_abs_luma_delta_8bit"]
               for x in report["frames"]]
        self.assertIsNone(diffs[0])
        # The actual physical palette boundary is at source frame 12, not a
        # made-up "bad cut" or aesthetic alarm.
        self.assertGreater(diffs[12],20)
        self.assertTrue(all(d<2 for d in diffs[1:12]))
        self.assertTrue(all(d<2 for d in diffs[13:]))
        self.assertEqual(sha256_file(self.movie),src_sha)
        receipt=verify_full_temporal_evidence(
            self.root/"measured-all-frames.json")
        self.assertEqual(receipt["observed_original_picture_frames"],24)
        forged=self.root/"forged-evidence.json"
        report["frames"].pop(5)
        forged.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError,"Incomplete whole-movie"):
            verify_full_temporal_evidence(forged)

    def test_short_real_soundtrack_is_never_described_as_full_movie_speech(self):
        picture=self.root/"original-camera-outlasts-microphone.mp4"
        p=subprocess.run(["ffmpeg","-hide_banner","-loglevel","error",
            "-nostdin","-y",
            "-f","lavfi","-i","color=c=purple:s=96x54:r=12:d=2",
            "-f","lavfi","-i",
            "sine=frequency=490:sample_rate=48000:duration=1",
            "-c:v","libx264","-pix_fmt","yuv420p",
            "-c:a","aac","-b:a","128k",str(picture)],
            capture_output=True,text=True,timeout=60)
        self.assertEqual(p.returncode,0,p.stderr)
        from studio_next.body_temporal_evidence import verify_full_temporal_evidence
        proof=self.vault.ingest(picture,mime="video/mp4",
            rights="owner_supplied",source_type="owner_upload",
            source_id="actual-incomplete-microphone",
            evidence="Twenty-four decoded camera pictures but twelve recorded sound frames",
            owner_or_generator="verified-owner")
        plan={**self.plan,"media":{
            "source":"zx7:sha256:"+proof["asset_id"],
            "asset_id":proof["asset_id"],
            "attestation_id":proof["attestation_id"]}}
        self.planfile.write_text(json.dumps(plan))
        out=self.root/"honest-audio-gap.json"
        original=observe_every_original_frame(
            self.planfile,self.root,self.root/"vault",out)
        self.assertEqual(original["actual_full_movie_frame_count"],24)
        self.assertTrue(original["original_sound_physically_measured"])
        self.assertFalse(original["original_sound_covers_entire_picture"])
        measured=verify_full_temporal_evidence(out)
        self.assertFalse(measured["original_sound_covers_entire_picture"])
        report=json.loads(out.read_text())
        self.assertLess(report["original_decoded_audio_stream_seconds"],1.2)
        self.assertGreater(report["original_decoded_audio_stream_seconds"],.9)
        self.assertLess(report["measured_soundtrack_dbfs"]["end_seconds"],1.2)
        self.assertFalse(report["creative_quality_or_continuity_certified"])
        forged=self.root/"fabricated-original-voice.json"
        report["original_sound_covers_entire_picture"]=True
        forged.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError,"length was not verified"):
            verify_full_temporal_evidence(forged)

    def test_untrusted_attestation_and_unauthorized_shape_are_rejected(self):
        baseline=sha256_file(self.planfile)
        for plan in (
            {**self.plan,"preview":{"width":500,"height":30}},
            {**self.plan,"media":{**self.plan["media"],
                                  "attestation_id":"forged-owner"}},
            {**self.plan,"preview":{"width":True,"height":20}},
        ):
            with self.subTest(plan=plan),self.assertRaises(ValueError):
                self.planfile.write_text(json.dumps(plan))
                observe_every_original_frame(self.planfile,self.root,
                                             self.root/"vault",self.root/"refused.json")
            self.assertFalse((self.root/"refused.json").exists())
        self.planfile.write_text(json.dumps(self.plan))
        self.assertEqual(sha256_file(self.planfile),baseline)

    def test_competing_completed_sensor_output_is_not_clobbered(self):
        out=self.root/"accepted-by-first-director.json"
        first=observe_every_original_frame(self.planfile,self.root,
                                           self.root/"vault",out)
        prior=sha256_file(out)
        second=self.root/"rival-director-proof.json"
        real_link=os.link
        raced=False
        def first_producer_wins(stage,target,*args,**kwargs):
            nonlocal raced
            if Path(target)==second:
                shutil.copyfile(out,second)
                raced=True
            return real_link(stage,target,*args,**kwargs)
        from studio_next import body_temporal_evidence as module
        with patch.object(module.os,"link",side_effect=first_producer_wins):
            with self.assertRaises(FileExistsError):
                observe_every_original_frame(self.planfile,self.root,
                                             self.root/"vault",second)
        self.assertTrue(raced)
        self.assertEqual(sha256_file(second),prior)
        self.assertFalse(list(self.root.glob(".zx7-temporal-*")))

    def test_mutable_original_replaced_during_real_decoder_but_frozen_snapshot_used(self):
        from studio_next import body_temporal_evidence as module
        initial=self.movie.read_bytes()
        sha=sha256_file(self.movie)
        other=self.root/"different-picture.mp4"
        shutil.copyfile(self.movie,other)
        altered=b"tampered live checkout not authentic cinema"
        native=subprocess.run
        observed=[]
        def original_source_swap(command,*args,**kwargs):
            if (isinstance(command,list) and command[0]=="ffmpeg" and
                    "rawvideo" in command):
                uri=Path(command[command.index("-i")+1])
                self.assertNotEqual(uri.resolve(),self.movie.resolve())
                self.assertIn(".zx7-temporal-",str(uri))
                self.assertEqual(sha256_file(uri),sha)
                observed.append(uri)
                self.movie.write_bytes(altered)
                try:return native(command,*args,**kwargs)
                finally:self.movie.write_bytes(initial)
            return native(command,*args,**kwargs)
        with patch.object(module.subprocess,"run",side_effect=original_source_swap):
            result=observe_every_original_frame(
                self.planfile,self.root,self.root/"vault",self.root/"frozen-data.json")
        self.assertEqual(result["actual_full_movie_frame_count"],24)
        self.assertEqual(sha256_file(self.movie),sha)
        self.assertTrue(observed)
        self.assertFalse(list(self.root.glob(".zx7-temporal-*")))


if __name__=="__main__":
    unittest.main()
