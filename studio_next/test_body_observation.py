"""An actual BODY artist-review loop gets real pixels/sound without fake taste.

Two original audio/video moments are decoded, independently SHA256 licensed,
staged as lossless PNGs + physically decoded dBFS windows, and archived with a
content-verified portable observation manifest. Untrusted receipt tampering,
stolen source identity, timecode escape and output overwrite are refused.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from studio_next.body_observation import produce_review_bundle,verify_review_bundle
from studio_next.body_integration import body_catalog,validate_witness
from studio_next.body_materials import fingerprint_physical_inputs
from studio_next.media_vault import MediaVault,sha256_file

@unittest.skipUnless(importlib.util.find_spec("PIL"),
    "Actual Pillow pixel decoder required for review bundle validation")
class ReviewInputContracts(unittest.TestCase):
    def test_bogus_review_zip_and_missing_source_refuse_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            fake=root/"fake.zxreview"
            with zipfile.ZipFile(fake,"w") as z:
                z.writestr("review.json",'{"schema":1,"frames":[]}')
                z.writestr("../../escaped.png",b"not an actual screenshot")
            with self.assertRaises(ValueError):
                verify_review_bundle(fake)
            with self.assertRaises(ValueError):
                produce_review_bundle(root/"not-a-plan.json",root,root/"vault",
                                      root/"unverified.zxreview")
            self.assertFalse((root/"unverified.zxreview").exists())

@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe")
        and importlib.util.find_spec("PIL"),
        "Actual FFmpeg picture+sound and Pillow pixel decoder required")
class OriginalFilmObservationIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.original=self.root/"original-cinema.mp4"
        recorded=subprocess.run([
            "ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
            "-f","lavfi","-i","testsrc2=size=160x90:rate=12:duration=2",
            "-f","lavfi","-i","sine=frequency=444:duration=2",
            "-c:v","libx264","-pix_fmt","yuv420p",
            "-c:a","aac","-b:a","128k","-shortest",str(self.original)],
            capture_output=True,text=True,timeout=90)
        self.assertEqual(recorded.returncode,0,recorded.stderr)
        self.vault=MediaVault(self.root/"vault")
        self.receipt=self.vault.ingest(self.original,mime="video/mp4",
            rights="owner_supplied",source_type="owner_upload",
            source_id="owner-recorded-original-cinema",
            evidence="Actual independently recorded audio/picture QA fixture",
            owner_or_generator="owner")
        self.plan={
           "media":{"source":"zx7:sha256:"+self.receipt["asset_id"],
                    "asset_id":self.receipt["asset_id"],
                    "attestation_id":self.receipt["attestation_id"]},
           "timecodes_seconds":[0.1,0.7,1.5],
           "audio_windows_seconds":[[0,0.8],[1.0,1.8]]
        }
        self.plan_file=self.root/"review-director.json"
        self.save()
    def tearDown(self):self.tmp.cleanup()
    def save(self):self.plan_file.write_text(
        json.dumps(self.plan),encoding="utf-8")
    def test_physically_decode_review_pictures_audio_source_rights_and_manifest(self):
        out=self.root/"actual-original-observation.zxreview"
        fingerprint=fingerprint_physical_inputs(
           "body.review",{"plan":self.plan_file.name,"out":out.name},self.root)
        self.assertIn(self.receipt["asset_id"],[row["sha256"] for row in fingerprint])
        identity=sha256_file(self.original)
        result=produce_review_bundle(self.plan_file,self.root,self.root/"vault",out)
        self.assertEqual(result["source_sha256"],self.receipt["asset_id"])
        self.assertEqual(result["actual_decoded_review_frames"],3)
        self.assertEqual(result["original_audio_windows_measured"],2)
        self.assertFalse(result["human_artistic_quality_certified"])
        independent=verify_review_bundle(out)
        self.assertTrue(independent["true_image_decoders_completed"])
        self.assertEqual(independent["actual_sampled_frames"],3)
        self.assertEqual(independent["source_sha256"],identity)
        with zipfile.ZipFile(out) as z:
            manifest=json.loads(z.read("review.json"))
            self.assertEqual([x["time_seconds"] for x in manifest["frames"]],
                             [0.1,0.7,1.5])
            self.assertEqual(len(manifest["audio_window_evidence"]),2)
            self.assertTrue(all("mean_dbfs" in x and "peak_dbfs" in x
                                for x in manifest["audio_window_evidence"]))
            self.assertTrue(any(x["sample_pair_mean_absolute_luma_difference"] is not None
                                for x in manifest["frames"][1:]))
            self.assertFalse(manifest["creative_story_or_style_approval"])
            self.assertTrue(manifest["full_picture_and_sound_decode_verified"])
        self.assertEqual(sha256_file(self.original),identity)
        # Small real footage + its timestamped PNGs/audio evidence remain
        # available as downloadable GitHub Actions proof artifacts.
        retain=os.getenv("ZX7_OBSERVATION_PROOF")
        if retain:
            store=Path(retain).resolve()
            store.mkdir(parents=True,exist_ok=True)
            for source,name in ((out,"actual-review.zxreview"),
                                (self.original,"original-reviewed-picture-sound.mp4")):
                saved=store/name
                if saved.exists():
                    raise FileExistsError("Never overwrite owner review evidence")
                shutil.copyfile(source,saved)
            with zipfile.ZipFile(out) as archive:
                for entry in ("frames/review_0001.png","frames/review_0002.png",
                              "frames/review_0003.png","review.json"):
                    saved=store/Path(entry).name
                    saved.write_bytes(archive.read(entry))
            (store/"review-proof.json").write_text(json.dumps({
                "source_movie_sha256":identity,
                "original_archive_sha256":sha256_file(out),
                "actual_png_frames":3,
                "actual_audio_windows_decoded":2,
                "pixels_not_synthesized_or_inferred":True,
                "objective_observations_not_artistic_approval":True
            },sort_keys=True,indent=2)+"\n")
        with self.assertRaisesRegex(ValueError,"new standalone"):
            produce_review_bundle(self.plan_file,self.root,self.root/"vault",out)
    def test_competing_verified_review_remains_immutable_after_publication_race(self):
        from unittest.mock import patch
        from studio_next import body_observation
        original=self.root/"verified-existing.zxreview"
        first=produce_review_bundle(self.plan_file,self.root,self.root/"vault",original)
        expected=sha256_file(original)
        destination=self.root/"another-review-won.zxreview"
        native_link=os.link
        raced=False
        def external_review_wins(source,target,*args,**kwargs):
            nonlocal raced
            if Path(target)==destination:
                self.assertIn(".zx7-media-review-",str(source))
                shutil.copyfile(original,destination)
                raced=True
            return native_link(source,target,*args,**kwargs)
        with patch.object(body_observation.os,"link",side_effect=external_review_wins):
            with self.assertRaises(FileExistsError):
                produce_review_bundle(self.plan_file,self.root,self.root/"vault",destination)
        self.assertTrue(raced)
        self.assertEqual(sha256_file(destination),expected)
        self.assertEqual(verify_review_bundle(destination)["actual_sampled_frames"],3)
        self.assertFalse(list(self.root.glob(".zx7-media-review-*")))

    def test_rights_spoof_timestamp_injection_or_truncated_audio_block_before_export(self):
        for case in ("wrong_digest","unknown_attestation","outside_movie",
                     "unordered","invalid_nan","non_audio_time_window"):
            original=json.loads(json.dumps(self.plan))
            if case=="wrong_digest":
                self.plan["media"]["asset_id"]="0"*64
            elif case=="unknown_attestation":
                self.plan["media"]["attestation_id"]="0"*64
            elif case=="outside_movie":
                self.plan["timecodes_seconds"]=[999]
            elif case=="unordered":
                self.plan["timecodes_seconds"]=[1.5,0.5]
            elif case=="invalid_nan":
                self.plan["timecodes_seconds"]=[float("nan")]
            else:
                self.plan["audio_windows_seconds"]=[[0,20]]
            self.save()
            with self.subTest(case=case):
                with self.assertRaises((ValueError,RuntimeError)):
                    produce_review_bundle(self.plan_file,self.root,self.root/"vault",
                       self.root/"no-forged-review.zxreview")
                self.assertFalse((self.root/"no-forged-review.zxreview").exists())
            self.plan=original
        self.save()
    def test_legacy_whole_movie_audio_meter_receipts_cannot_masquerade_as_local_windows(self):
        genuine=self.root/"correct-window-v2.zxreview"
        produce_review_bundle(self.plan_file,self.root,self.root/"vault",genuine)
        with zipfile.ZipFile(genuine) as store:
            original=json.loads(store.read("review.json"))
            self.assertEqual(original["schema"],2)
            self.assertTrue(original["audio_windows_metered_after_original_exact_atrim"])
            observed=[v["mean_dbfs"] for v in original["audio_window_evidence"]]
            self.assertEqual(len(observed),2)
        forged=self.root/"old-whole-film-meter.zxreview"
        with zipfile.ZipFile(genuine) as real,zipfile.ZipFile(forged,"x") as legacy:
            content=json.loads(real.read("review.json"))
            content["schema"]=1
            content.pop("audio_windows_metered_after_original_exact_atrim")
            for member in real.namelist():
                legacy.writestr(member,
                    json.dumps(content) if member=="review.json" else real.read(member))
        with self.assertRaisesRegex(ValueError,"schema"):
            verify_review_bundle(forged)

    def test_review_bundle_rejects_forged_audio_windows_even_with_original_pngs(self):
        good=self.root/"good.zxreview"
        produce_review_bundle(self.plan_file,self.root,self.root/"vault",good)
        forged=self.root/"forged.zxreview"
        with zipfile.ZipFile(good) as inp,zipfile.ZipFile(forged,"x") as out:
            report=json.loads(inp.read("review.json"))
            report["audio_window_evidence"][0]["mean_dbfs"]="I say this is perfect"
            for name in inp.namelist():
                out.writestr(name,json.dumps(report) if name=="review.json"
                             else inp.read(name))
        with self.assertRaisesRegex(ValueError,"loudness"):
            verify_review_bundle(forged)

    def test_registered_operation_is_real_replay_verifiable_and_tampering_denied(self):
        catalog=body_catalog(self.root)
        status={x["id"]:x for x in catalog.discover()}
        self.assertEqual(status["body.review"]["status"],"installed")
        self.assertEqual(status["body.review"]["schema"]["required"],["plan","out"])
        with self.assertRaises(PermissionError):
            catalog.invoke("body.review",{
                 "plan":self.plan_file.name,"out":"review.zxreview"},
                 allowed_access={"read"})
        result=catalog.invoke("body.review",{
           "plan":self.plan_file.name,"out":"review.zxreview"},
           allowed_access={"write","read"})
        self.assertTrue(validate_witness("body.review",result))
        self.assertTrue(verify_review_bundle(self.root/"review.zxreview")[
                        "true_image_decoders_completed"])
        (self.root/"review.zxreview").write_bytes(b"fake creative evidence")
        self.assertFalse(validate_witness("body.review",result))

if __name__=="__main__":unittest.main()
