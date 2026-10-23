"""Actual EBU R128 integrated LUFS/LRA and TRUE PEAK on licensed original movies."""
from __future__ import annotations
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from studio_next.body_loudness import inspect_original_loudness
from studio_next.body_integration import body_catalog,validate_witness
from studio_next.media_vault import MediaVault,sha256_file
from studio_next.body_materials import fingerprint_physical_inputs


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
   "Real decoded program audio and ebur128 filter required")
class NativeSoundLevelProof(unittest.TestCase):
    def test_truepeak_and_ebu_loudness_measure_input_not_reencode_or_impose_lufs(self):
        with tempfile.TemporaryDirectory() as home:
            root=Path(home)
            vault=MediaVault(root/"vault")
            measurements=[]
            for count,gain in enumerate((0,-12)):
                movie=root/f"original-audio-{count}.mp4"
                args=["ffmpeg","-hide_banner","-loglevel","error",
                      "-nostdin","-y",
                      "-f","lavfi","-i","color=c=black:s=160x90:r=12:d=2",
                      "-f","lavfi","-i","sine=frequency=440:sample_rate=48000:duration=2",
                      "-map","0:v:0","-map","1:a:0"]
                if gain:args+=["-af",f"volume={gain}dB"]
                args+=["-c:v","libx264","-pix_fmt","yuv420p",
                       "-c:a","aac","-b:a","160k","-shortest",str(movie)]
                built=subprocess.run(args,capture_output=True,text=True,timeout=60)
                self.assertEqual(built.returncode,0,built.stderr)
                receipt=vault.ingest(movie,mime="video/mp4",
                    rights="owner_supplied",source_type="owner_upload",
                    source_id=f"true-peak-original-{count}",
                    evidence="Local original physically generated movie and audio test",
                    owner_or_generator="owner")
                plan=root/f"music-loudness-{count}.json"
                plan.write_text(json.dumps({"media":{
                    "source":"zx7:sha256:"+receipt["asset_id"],
                    "asset_id":receipt["asset_id"],
                    "attestation_id":receipt["attestation_id"]}}))
                before=sha256_file(movie)
                result=body_catalog(root).invoke("body.loudness",
                    {"plan":plan.name},allowed_access={"read"})
                self.assertEqual(result["sha256"],before)
                self.assertTrue(validate_witness("body.loudness",result))
                self.assertTrue(result["source_original_audio_stream_verified"])
                self.assertTrue(result["lra_short_film_less_than_60_seconds_unreliable"])
                self.assertFalse(result["loudness_normalization_applied_to_source"])
                self.assertFalse(result["any_target_lufs_or_peak_imposed"])
                self.assertFalse(result["dialogue_intelligibility_or_aesthetic_quality_approved"])
                self.assertEqual(before,sha256_file(movie))
                self.assertIsInstance(result["integrated_loudness_lufs"],float)
                self.assertIsInstance(result["measured_true_peak_dbfs"],float)
                self.assertIsInstance(result["loudness_range_lu"],float)
                expected=fingerprint_physical_inputs("body.loudness",
                              {"plan":plan.name},root)
                self.assertIn(before,[x["sha256"] for x in expected])
                measurements.append(result)
            a,b=measurements
            self.assertGreater(a["integrated_loudness_lufs"]-
                               b["integrated_loudness_lufs"],9)
            self.assertGreater(a["measured_true_peak_dbfs"]-
                               b["measured_true_peak_dbfs"],9)
    def test_loudness_analyzer_reads_attested_cas_not_mutable_owner_movie_checkout(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as home:
            root=Path(home)
            source=root/"original-artist-voice-clip.mp4"
            proc=subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
                "-f","lavfi","-i","color=c=black:s=160x90:r=12:d=2",
                "-f","lavfi","-i",
                "sine=frequency=560:sample_rate=48000:duration=2",
                "-c:v","libx264","-pix_fmt","yuv420p",
                "-c:a","aac","-shortest",str(source)],
                capture_output=True,text=True,timeout=65)
            self.assertEqual(proc.returncode,0,proc.stderr)
            vault=MediaVault(root/"vault")
            receipt=vault.ingest(source,mime="video/mp4",rights="owner_supplied",
                source_type="owner_upload",source_id="licensed-original-voice",
                evidence="Actual original voice and picture authored in test",
                owner_or_generator="owner")
            plan=root/"director-sound-audit.json"
            plan.write_text(json.dumps({"media":{"source":source.name,
                "asset_id":receipt["asset_id"],
                "attestation_id":receipt["attestation_id"]}}))
            owner=source.read_bytes()
            original_run=subprocess.run
            observed=[]
            def intercept(argv,**kwargs):
                if argv and argv[0]=="ffmpeg" and "-af" in argv and "ebur128=peak=true" in argv:
                    decoder=Path(argv[argv.index("-i")+1])
                    self.assertIn(".zx7-owned-sources-",str(decoder))
                    self.assertFalse(decoder.stat().st_mode & 0o222)
                    self.assertEqual(sha256_file(decoder),receipt["asset_id"])
                    observed.append(decoder)
                    source.write_bytes(b"unlicensed replacement while analyzer is measuring")
                    try:return original_run(argv,**kwargs)
                    finally:source.write_bytes(owner)
                return original_run(argv,**kwargs)
            with patch("studio_next.body_loudness.subprocess.run",side_effect=intercept):
                proven=inspect_original_loudness(plan,root,root/"vault")
            self.assertTrue(proven["meter_analyzed_exact_private_attested_cas"])
            self.assertTrue(proven["source_original_audio_stream_verified"])
            self.assertIsInstance(proven["measured_true_peak_dbfs"],float)
            self.assertEqual(sha256_file(source),receipt["asset_id"])
            self.assertEqual(len(observed),1)
            self.assertFalse(observed[0].exists())
            self.assertFalse(list(root.glob(".zx7-owned-sources-*")))

    def test_unlicensed_source_or_movie_without_audio_is_never_called_sound_compliant(self):
        with tempfile.TemporaryDirectory() as home:
            root=Path(home)
            plan=root/"forged.json"
            plan.write_text('{"media":{"source":"zx7:sha256:'+("0"*64)+
                            '","asset_id":"'+("0"*64)+'","attestation_id":"forged"}}')
            with self.assertRaises((ValueError,RuntimeError)):
                inspect_original_loudness(plan,root,root/"vault")
            movie=root/"actual-silent.mp4"
            process=subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
                "-f","lavfi","-i","color=c=red:s=160x90:r=12:d=1",
                "-c:v","libx264","-pix_fmt","yuv420p",str(movie)],
                capture_output=True,text=True,timeout=60)
            self.assertEqual(process.returncode,0,process.stderr)
            v=MediaVault(root/"vault")
            att=v.ingest(movie,mime="video/mp4",rights="owner_supplied",
                  source_type="owner_upload",source_id="recording-with-no-voices",
                  evidence="Original silent movie for licensed native audio testing",
                  owner_or_generator="owner")
            plan.write_text(json.dumps({"media":{
                 "source":"zx7:sha256:"+att["asset_id"],"asset_id":att["asset_id"],
                 "attestation_id":att["attestation_id"]}}))
            with self.assertRaisesRegex(ValueError,"no audio"):
                inspect_original_loudness(plan,root,root/"vault")

if __name__=="__main__":unittest.main()
