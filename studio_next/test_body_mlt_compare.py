"""Native editor before/after introspection: no fake media claims.

Source-affecting, cut-boundary-only, and control-only changes are distinct.
All actual native tests use owner-attested physical media, not an XML mock.
"""
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from studio_next.body_mlt_compare import (
    _source_at,_clip_intervals,_track_changes,compare_owned_mlt_projects)
from studio_next.body_document_schemas import document_contract
from studio_next.body_tool_contracts import real_operation_schema


class ExactNativeEditorialReviewTests(unittest.TestCase):
    def test_source_address_interval_sweep_is_frame_exact_without_frame_explosion(self):
        a={"clips":[{"asset_id":"real-a","attestation_id":"a","first_frame":0,
                     "end_frame":900000,"position_frame":0}]}
        b={"clips":[{"asset_id":"real-a","attestation_id":"a","first_frame":0,
                     "end_frame":100000,"position_frame":0},
                    {"asset_id":"real-a","attestation_id":"a","first_frame":100000,
                     "end_frame":900000,"position_frame":100000}]}
        structural=_track_changes(a,b,"picture",0,900000,900000)
        self.assertEqual(structural["source_frame_spans"],[])
        self.assertEqual(structural["unchanged_original_source_frames"],900000)
        self.assertIsNotNone(structural["native_clip_partition_delta"])
        self.assertIsNone(structural["native_track_controls"])
        different={"clips":[{"asset_id":"real-a","attestation_id":"a",
                             "first_frame":7,"end_frame":900007,
                             "position_frame":0}]}
        changed=_track_changes(a,different,"picture",0,900000,900000)
        self.assertEqual(len(changed["source_frame_spans"]),1)
        self.assertEqual(changed["source_frame_spans"][0]["duration_frames"],900000)
        self.assertEqual(changed["source_frame_spans"][0]["type"],
                         "repositioned_original_source_frame")
        removed=_track_changes(a,None,"picture",0,900000,900000)
        self.assertEqual(removed["source_frame_spans"][0]["type"],
                         "removed_original_source")
        recreated=_track_changes(None,a,"picture",0,900000,900000)
        self.assertEqual(recreated["source_frame_spans"][0]["type"],
                         "inserted_original_source")
        self.assertEqual(_source_at(_clip_intervals(b["clips"]),899999),
                         ("real-a","a",899999))

    def test_500_random_different_source_clip_topologies_match_independent_oracle(self):
        import random
        rng=random.Random(0xA770)
        def generate():
            clips=[]
            position=0
            while position<73 and len(clips)<8:
                position+=rng.randrange(0,5)
                if position>=73:
                    break
                width=min(rng.randint(1,18),73-position)
                first=rng.randrange(0,72)
                clips.append({
                    "source":"zx7:sha256:"+rng.choice(("a","b","c")),
                    "asset_id":rng.choice(("a","b","c")),
                    "attestation_id":"proof-"+str(rng.randrange(2)),
                    "first_frame":first,"end_frame":first+width,
                    "position_frame":position})
                position+=width
            return {"clips":clips}
        def reference(track,frame):
            for c in track["clips"]:
                start=c["position_frame"]
                length=c["end_frame"]-c["first_frame"]
                if start<=frame<start+length:
                    return c["asset_id"],c["attestation_id"],(
                        c["first_frame"]+frame-start)
            return None
        checked=0
        for seed in range(500):
            first=generate()
            second=generate()
            report=_track_changes(first,second,"sound",0,73,73)
            observed=set()
            for span in report["source_frame_spans"]:
                self.assertGreater(span["end_frame_exclusive"],
                                   span["start_frame"])
                observed.update(range(span["start_frame"],
                                      span["end_frame_exclusive"]))
            oracle={frame for frame in range(73)
                    if reference(first,frame)!=reference(second,frame)}
            self.assertEqual(observed,oracle,msg=("case",seed))
            self.assertEqual(report["unchanged_original_source_frames"],
                sum(reference(first,frame) is not None and
                    reference(first,frame)==reference(second,frame)
                    for frame in range(73)))
            checked+=73
        self.assertEqual(checked,36500)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                         "Real native physical source custody requires media decoders")
    def test_real_editor_review_distinguishes_razor_audio_gain_and_source_time(self):
        from studio_next.body_integration import body_catalog,validate_witness
        from studio_next.body_mlt_roundtrip import recover_original_mlt_plan
        from studio_next.media_vault import sha256_file
        from studio_next.test_body_mlt_editor import VerifiedMLTEditorialTests

        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            case=VerifiedMLTEditorialTests()
            plan,plan_file=case._case(root)
            sound=case._original_sound(root)
            plan["audio_tracks"]=[{"clips":[{
                "source":"zx7:sha256:"+sound["asset_id"],
                "asset_id":sound["asset_id"],
                "attestation_id":sound["attestation_id"],
                "first_frame":0,"end_frame":12,"position_frame":0}]}]
            plan_file.write_text(json.dumps(plan))
            cat=body_catalog(root)
            self.assertIn("body.mlt_owned_compare",
                {item["id"] for item in cat.discover()})
            abi=real_operation_schema("body.mlt_owned_compare",
                                      ("before_edit","after_edit"))
            self.assertEqual(abi["required"],["before_edit","after_edit"])
            self.assertEqual(set(abi["properties"]),
                             {"before_edit","after_edit"})
            cat.invoke("body.mlt_owned_export",{
                "plan":plan_file.name,"out":"revision-00.mlt"},
                allowed_access={"write"})
            original=root/"revision-00.mlt"
            before=original.read_bytes()
            baseline=cat.invoke("body.mlt_owned_compare",{
                "before_edit":original.name,"after_edit":original.name},
                allowed_access={"read"})
            self.assertFalse(baseline["structural_changes_verified"])
            self.assertTrue(validate_witness("body.mlt_owned_compare",baseline))
            forged_receipt=dict(baseline,after_mlt_sha256="0"*64)
            self.assertFalse(validate_witness("body.mlt_owned_compare",forged_receipt))
            forged_authority=dict(baseline,workspace_root=str(root.parent))
            self.assertFalse(validate_witness("body.mlt_owned_compare",forged_authority))
            self.assertEqual(baseline["before_mlt_sha256"],
                             hashlib.sha256(before).hexdigest())
            self.assertFalse(baseline["decoded_pixel_or_audio_equivalence_proven"])
            self.assertTrue(baseline["exact_source_rights_and_native_roundtrips_rechecked"])
            self.assertEqual(baseline["sound_changes"],[])

            patches={
                "sound-gain":{"operations":[
                    {"op":"add","path":"/audio_tracks/0/gain_db","value":-15}]},
                "razor":{"edits":[{
                    "kind":"blade","frame":6,"picture_tracks":[0,1],
                    "audio_tracks":[0]}]},
                "ripple":{"edits":[{
                    "kind":"ripple_insert","frame":6,"frames":3,
                    "picture_tracks":[0,1],"audio_tracks":[0],
                    "automation":"preserve_source_frame_values"}]},
            }
            observations={}
            for mode,operations in patches.items():
                command=root/(mode+".json")
                command.write_text(json.dumps(operations))
                target=mode+".mlt"
                cat.invoke("body.mlt_owned_revision",{
                    "edit":original.name,"operation":command.name,
                    "out":target},allowed_access={"write"})
                report=cat.invoke("body.mlt_owned_compare",{
                    "before_edit":original.name,"after_edit":target},
                    allowed_access={"read"})
                observations[mode]=report
                self.assertTrue(report["structural_changes_verified"])
                self.assertTrue(validate_witness("body.mlt_owned_compare",report))
                self.assertFalse(report["creative_or_professional_quality_approved"])
                self.assertEqual(report["before_mlt_sha256"],sha256_file(original))
                self.assertEqual(report["after_mlt_sha256"],sha256_file(root/target))
                self.assertEqual((root/target).suffix,".mlt")
                self.assertEqual(original.read_bytes(),before)
                self.assertEqual(report["frame_rate"],plan["frame_rate"])
                reversed_review=compare_owned_mlt_projects(
                    root/target,original,root,root/"vault")
                self.assertEqual(reversed_review["before_mlt_sha256"],
                                 report["after_mlt_sha256"])
                self.assertEqual(reversed_review["after_mlt_sha256"],
                                 report["before_mlt_sha256"])

            gain=observations["sound-gain"]
            self.assertEqual(gain["picture_changes"],[])
            self.assertEqual(len(gain["sound_changes"]),1)
            self.assertEqual(gain["sound_changes"][0]["source_frame_spans"],[])
            self.assertIsNone(gain["sound_changes"][0]["native_clip_partition_delta"])
            self.assertEqual(gain["sound_changes"][0]["native_track_controls"],
                             {"before":{},"after":{"gain_db":-15.0}})

            cut=observations["razor"]
            self.assertEqual(len(cut["picture_changes"]),2)
            self.assertEqual(len(cut["sound_changes"]),1)
            for edit in cut["picture_changes"]+cut["sound_changes"]:
                self.assertEqual(edit["source_frame_spans"],[])
                self.assertIsNotNone(edit["native_clip_partition_delta"])
            self.assertEqual(cut["before_frames"],cut["after_frames"])

            ripple=observations["ripple"]
            self.assertEqual(ripple["before_frames"],12)
            self.assertEqual(ripple["after_frames"],15)
            self.assertGreater(sum(len(track["source_frame_spans"])
                                   for track in ripple["picture_changes"]),0)
            self.assertGreater(sum(len(track["source_frame_spans"])
                                   for track in ripple["sound_changes"]),0)

            # Prove the original autonomous BODY process can execute, commit,
            # reverify and safely REUSE an observed native review after a
            # new process/controller instance. This is not a direct-call-only
            # helper dressed up as a model-facing capability.
            from studio_next.body_integration import run_body_project
            film_ir={
                "project":{"creative_intent":
                    "Independently inspect source-attested editing revisions"},
                "assets":[],
                "shots":[{"id":"self-review",
                    "purpose":"See true surviving original picture and audio",
                    "duration_seconds":1.0}],
                "tool_graph":[{
                    "id":"observe-original-change",
                    "tool_id":"body.mlt_owned_compare",
                    "purpose":"Inspect source positions and soundtrack controls",
                    "inputs":{"before_edit":original.name,
                              "after_edit":"sound-gain.mlt"},
                    "depends_on":[]}]}
            first=run_body_project(film_ir,root,
                                   db_name="original-review-proof.sqlite3")
            self.assertEqual(first["status"],"all_tool_results_verified")
            self.assertEqual(first["completed"],["observe-original-change"])
            self.assertEqual(first["reused"],[])
            resumed=run_body_project(film_ir,root,
                                     db_name="original-review-proof.sqlite3")
            self.assertEqual(resumed["status"],"all_tool_results_verified")
            self.assertEqual(resumed["reused"],["observe-original-change"])
            self.assertEqual(resumed["completed"],["observe-original-change"])

            # Reject fake or modified original facts, no read-only review output.
            forged=root/"forged-owned.mlt"
            forged.write_bytes(before.replace(b"zx7.original_sha256",
                                              b"forged.original_sha256"))
            with self.assertRaises(ValueError):
                compare_owned_mlt_projects(original,forged,root,root/"vault")
            with self.assertRaises(ValueError):
                compare_owned_mlt_projects(root.parent/"outside.mlt",
                                           original,root,root/"vault")
            self.assertEqual(original.read_bytes(),before)
            self.assertEqual(recover_original_mlt_plan(
                original,root,root/"vault")["source_mlt_sha256"],
                hashlib.sha256(before).hexdigest())


if __name__=="__main__":
    unittest.main()
