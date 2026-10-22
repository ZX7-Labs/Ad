"""Compare TWO physically rendered films, not words describing fake edits."""
from __future__ import annotations
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from studio_next.body_observation import produce_review_bundle
from studio_next.body_review_compare import compare_verified_revisions
from studio_next.body_integration import body_catalog,validate_witness
from studio_next.body_materials import fingerprint_physical_inputs
from studio_next.media_vault import MediaVault,sha256_file

@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe")
    and importlib.util.find_spec("PIL"),
    "Real film decoder and image difference library are required")
class OriginalAudiovisualRevisionComparison(unittest.TestCase):
    def test_real_red_then_blue_original_film_edit_changes_pixels_and_preserves_authored_timecodes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            vault=MediaVault(root/"vault")
            proofs=[]
            for idx,(color,frequency,times) in enumerate((
                ("red",440,[0.15,0.9]),("blue",700,[0.15,0.75]))):
                movie=root/f"original-movie-{idx}.mp4"
                recorded=subprocess.run([
                    "ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
                    "-f","lavfi","-i",f"color={color}:s=160x90:r=12:d=1.25",
                    "-f","lavfi","-i",f"sine=frequency={frequency}:duration=1.25",
                    "-c:v","libx264","-pix_fmt","yuv420p",
                    "-c:a","aac","-shortest",str(movie)
                ],capture_output=True,text=True,timeout=90)
                self.assertEqual(recorded.returncode,0,recorded.stderr)
                owned=vault.ingest(movie,mime="video/mp4",
                    rights="owner_supplied",source_type="owner_upload",
                    source_id=f"original-cut-{idx}",
                    evidence="Actually rendered original two-version picture and soundtrack",
                    owner_or_generator="owner")
                plan=root/f"comparison-{idx}.json"
                plan.write_text(json.dumps({
                  "media":{"source":"zx7:sha256:"+owned["asset_id"],
                           "asset_id":owned["asset_id"],
                           "attestation_id":owned["attestation_id"]},
                  "timecodes_seconds":times,
                  "audio_windows_seconds":[[0.1,0.65]]}),encoding="utf-8")
                evidence=root/f"actual-review-{idx}.zxreview"
                result=produce_review_bundle(plan,root,root/"vault",evidence)
                proofs.append((movie,evidence,result))
            original=(sha256_file(proofs[0][0]),sha256_file(proofs[1][0]))
            args={"before_bundle":proofs[0][1].name,
                  "before_sha256":proofs[0][2]["sha256"],
                  "after_bundle":proofs[1][1].name,
                  "after_sha256":proofs[1][2]["sha256"]}
            catalog=body_catalog(root)
            specs={t["id"]:t for t in catalog.discover()}
            self.assertEqual(specs["body.review_compare"]["status"],"installed")
            self.assertEqual(specs["body.review_compare"]["access"],"read")
            self.assertEqual(specs["body.review_compare"]["schema"]["required"],
                             list(args))
            evidence=catalog.invoke("body.review_compare",args,
                                    allowed_access={"read"})
            self.assertTrue(validate_witness("body.review_compare",evidence))
            self.assertEqual(len(evidence["matching_frame_comparisons"]),1)
            change=evidence["matching_frame_comparisons"][0]
            self.assertEqual(change["time_seconds"],0.15)
            self.assertTrue(change["image_pixels_physically_decoded"])
            self.assertGreater(change["mean_absolute_rgb_difference_8bit"],40)
            self.assertEqual(evidence["before_only_picture_sample_times"],[0.9])
            self.assertEqual(evidence["revised_only_picture_sample_times"],[0.75])
            self.assertEqual(len(evidence["matching_audio_window_comparisons"]),1)
            self.assertTrue(evidence["no_continuity_dialogue_style_or_narrative_quality_inference"])
            self.assertTrue(evidence["human_artist_has_not_approved_a_revision"])
            both=fingerprint_physical_inputs("body.review_compare",args,root)
            self.assertIn(proofs[0][2]["sha256"],[v["sha256"] for v in both])
            self.assertIn(proofs[1][2]["sha256"],[v["sha256"] for v in both])
            self.assertEqual(original,
                             (sha256_file(proofs[0][0]),sha256_file(proofs[1][0])))
            with self.assertRaises(ValueError):
                compare_verified_revisions(proofs[0][1],"0"*64,
                      proofs[1][1],proofs[1][2]["sha256"],root)
            proofs[1][1].write_bytes(b"tampered revision evidence")
            self.assertFalse(validate_witness("body.review_compare",evidence))

if __name__=="__main__":unittest.main()
