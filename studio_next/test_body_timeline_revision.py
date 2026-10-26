"""Frame-exact director NLE operations and live rights-safe film proof."""
import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from studio_next.body_timeline_revision import apply_editorial_operations,render_editorial_revision
from studio_next.media_vault import MediaVault,sha256_file
from studio_next.precision_retime import _source_timebase
from studio_next.body_integration import body_catalog,validate_witness


def plan_three():
    def shot(asset,a,b):
        return {"source":"zx7:sha256:"+asset,"asset_id":asset,
                "attestation_id":"original-test-owner",
                "first_frame":a,"end_frame":b,"audio":"preserve_source"}
    return {"frame_rate":{"numerator":24,"denominator":1},
            "frame_size":{"width":160,"height":90},
            "clips":[shot("a"*64,4,12),shot("b"*64,8,16),shot("c"*64,12,20)]}


class EditDecisionMath(unittest.TestCase):
    def setUp(self):
        self.original=plan_three()
        self.lengths={c["asset_id"]:36 for c in self.original["clips"]}
    def revision(self,op):
        return apply_editorial_operations(self.original,{"operations":[op]},self.lengths)
    def test_roll_keeps_total_frames_and_moves_both_source_cut_edges(self):
        movie,history=self.revision({"kind":"roll","at":0,"delta":2})
        self.assertEqual([(c["first_frame"],c["end_frame"]) for c in movie["clips"]],
                         [(4,14),(10,16),(12,20)])
        self.assertEqual(history[0]["frames_before"],history[0]["frames_after"])
        self.assertEqual(self.original,plan_three())
    def test_slip_preserves_duration_and_moves_source_selection(self):
        movie,_=self.revision({"kind":"slip","clip":1,"delta":-3})
        self.assertEqual((movie["clips"][1]["first_frame"],movie["clips"][1]["end_frame"]),(5,13))
    def test_slide_preserves_center_source_and_total_timeline(self):
        movie,_=self.revision({"kind":"slide","clip":1,"delta":2})
        self.assertEqual([(x["first_frame"],x["end_frame"]) for x in movie["clips"]],
                         [(4,14),(8,16),(14,20)])
    def test_ripple_trim_changes_duration_only_as_directed(self):
        movie,history=self.revision({"kind":"ripple_trim","clip":1,"edge":"in","delta":3})
        self.assertEqual(history[0]["frames_after"],history[0]["frames_before"]-3)
    def test_split_and_reorder_still_preserve_exact_original_custody(self):
        steps={"operations":[{"kind":"split","clip":0,"offset":3},
                             {"kind":"reorder","clip":1,"to":3}]}
        movie,history=apply_editorial_operations(self.original,steps,self.lengths)
        self.assertEqual(len(movie["clips"]),4)
        self.assertEqual(history[0]["frames_after"],24)
        self.assertEqual(history[1]["frames_after"],24)
        self.assertEqual([x["asset_id"] for x in movie["clips"]],
                         ["a"*64,"b"*64,"c"*64,"a"*64])
        self.assertEqual(self.original,plan_three())
    def test_invalid_operation_original_bounds_and_untrusted_json_rejected(self):
        cases=[{"kind":"roll","at":2,"delta":1},
               {"kind":"roll","at":0,"delta":-8},
               {"kind":"slip","clip":0,"delta":-10},
               {"kind":"slide","clip":0,"delta":1},
               {"kind":"slide","clip":1,"delta":8},
               {"kind":"ripple_trim","clip":0,"edge":"out","delta":-9},
               {"kind":"split","clip":0,"offset":8},
               {"kind":"reorder","clip":0,"to":0},
               {"kind":"slip","clip":True,"delta":1},
               {"kind":"slip","clip":0,"delta":"1"},
               {"kind":"slip","clip":0,"delta":1,"shell":"ffmpeg"}]
        for op in cases:
            with self.subTest(op=op),self.assertRaises(ValueError):
                self.revision(op)
        with self.assertRaises(ValueError):
            apply_editorial_operations(self.original,{"operations":[]},self.lengths)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "Real source and output codec required")
class OwnedFilmRevisionProof(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.vault=MediaVault(self.root/"vault")
        clips=[]
        for ix,(color,hz) in enumerate((("red",310),("blue",620),("green",850))):
            path=self.root/("source"+str(ix)+".mp4")
            command=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
                     "-f","lavfi","-i",f"color=c={color}:s=160x90:r=24:d=1.5",
                     "-f","lavfi","-i",f"sine=frequency={hz}:sample_rate=48000:duration=1.5",
                     "-c:v","libx264","-pix_fmt","yuv420p",
                     "-x264-params","colorprim=bt709:transfer=bt709:colormatrix=bt709",
                     "-color_primaries","bt709","-color_trc","bt709","-colorspace","bt709",
                     "-c:a","aac","-b:a","128k","-shortest",str(path)]
            p=subprocess.run(command,capture_output=True,timeout=50)
            self.assertEqual(p.returncode,0,p.stderr)
            receipt=self.vault.ingest(path,mime="video/mp4",
                   rights="owner_supplied",source_type="owner_upload",
                   source_id=str(ix),evidence="Actually decoded original test movie",
                   owner_or_generator="owner")
            clips.append({"source":"zx7:sha256:"+receipt["asset_id"],
                         "asset_id":receipt["asset_id"],
                         "attestation_id":receipt["attestation_id"],
                         "first_frame":4,"end_frame":16,"audio":"preserve_source"})
        self.plan={"frame_rate":{"numerator":24,"denominator":1},
                   "frame_size":{"width":160,"height":90},"clips":clips}
        self.planfile=self.root/"old.json"
        self.operationfile=self.root/"decision.json"
        self.planfile.write_text(json.dumps(self.plan))
        self.operationfile.write_text(json.dumps({"operations":[
            {"kind":"roll","at":0,"delta":2},
            {"kind":"slip","clip":1,"delta":2},
            {"kind":"slide","clip":1,"delta":1},
            {"kind":"ripple_trim","clip":2,"edge":"out","delta":-2},
            {"kind":"split","clip":0,"offset":5}]}))
    def tearDown(self):
        self.tmp.cleanup()
    def test_multiple_original_editor_operations_decode_as_real_reversible_movie(self):
        preserved=[sha256_file(p) for p in (self.planfile,self.operationfile)]
        result=render_editorial_revision(self.planfile,self.operationfile,self.root,
                  self.root/"vault",self.root/"revised.mp4")
        self.assertEqual(result["physical_original_frames_delivered"],34)
        self.assertEqual(_source_timebase(self.root/"revised.mp4")[1],34)
        self.assertEqual(result["actual_cut_operations"],4)
        self.assertEqual([sha256_file(p) for p in (self.planfile,self.operationfile)],preserved)
        revision=self.root/result["revision_plan"]
        self.assertEqual(sha256_file(revision),result["revision_plan_sha256"])
        self.assertEqual(len(json.loads(revision.read_text())["clips"]),4)
        self.assertTrue(result["reversible_original_media"])
        second=self.root/"from-revision.mp4"
        from studio_next.body_sequence_cuts import render_verified_sequence
        result2=render_verified_sequence(revision,self.root,self.root/"vault",second)
        self.assertEqual(result2["physical_original_frames_delivered"],34)
        self.assertTrue(second.exists())
        check=subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-xerror",
              "-i",str(second),"-map","0:v:0","-map","0:a:0",
              "-f","null","-"],capture_output=True,timeout=45)
        self.assertEqual(check.returncode,0,check.stderr)
    def test_bad_command_never_publishes_movie_or_modifies_approved_plan(self):
        before=sha256_file(self.planfile)
        self.operationfile.write_text('{"operations":[{"kind":"slip","clip":0,"delta":999}]}')
        with self.assertRaises(ValueError):
            render_editorial_revision(self.planfile,self.operationfile,self.root,
                    self.root/"vault",self.root/"refused.mp4")
        self.assertFalse((self.root/"refused.mp4").exists())
        self.assertEqual(sha256_file(self.planfile),before)
    def test_real_installed_body_operation_publishes_measured_video_and_revision(self):
        listing={x["id"]:x for x in body_catalog(self.root).discover()}
        self.assertEqual(listing["body.timeline_revision"]["status"],"installed")
        inputs={"plan":"old.json","operation":"decision.json","out":"body-edited.mp4"}
        catalog=body_catalog(self.root)
        physical=catalog.trusted_material_fingerprint("body.timeline_revision",inputs)
        hashes=[item["sha256"] for item in physical]
        self.assertIn(sha256_file(self.planfile),hashes)
        self.assertIn(sha256_file(self.operationfile),hashes)
        result=catalog.invoke("body.timeline_revision",inputs,allowed_access={"read","write"})
        self.assertTrue(validate_witness("body.timeline_revision",result))
        self.assertTrue((self.root/"body-edited.mp4").exists())

    def test_editorial_revision_survives_archive_import_on_a_different_host(self):
        from studio_next.body_archive import create_body_archive,restore_body_archive
        from studio_next.body_sequence_cuts import render_verified_sequence
        original=render_editorial_revision(self.planfile,self.operationfile,self.root,
              self.root/"vault",self.root/"approved.mp4")
        with tempfile.TemporaryDirectory() as offhost:
            off=Path(offhost)
            snapshot=create_body_archive(self.root,off/"studio.tar.gz")
            relocated=off/"new-machine-workspace"
            restore_body_archive(off/"studio.tar.gz",relocated,
                                 expected_sha256=snapshot["sha256"],relocate=True)
            revision=relocated/original["revision_plan"]
            self.assertEqual(sha256_file(revision),original["revision_plan_sha256"])
            self.assertEqual(sha256_file(relocated/"approved.mp4"),
                             sha256_file(self.root/"approved.mp4"))
            evidence=render_verified_sequence(revision,relocated,
                         relocated/"vault",relocated/"new-worker.mp4")
            self.assertEqual(evidence["physical_original_frames_delivered"],34)
            self.assertTrue(evidence["original_audio_stream_present"])

    def test_changed_original_editor_instructions_during_real_render_refused(self):
        from unittest.mock import patch
        real_run=subprocess.run
        mutated=False
        def tamper_during_encoder(command,*args,**kwargs):
            nonlocal mutated
            outcome=real_run(command,*args,**kwargs)
            if (not mutated and isinstance(command,list) and
                    command[0]=="ffmpeg" and outcome.returncode==0 and
                    any(str(x).endswith("native-original-edited.mp4")
                        for x in command)):
                # Modify authored plan after actual codec completed, before
                # the trusted native film publisher checks final custody.
                self.operationfile.write_text(
                    '{"operations":[{"kind":"slip","clip":0,"delta":1}]}')
                mutated=True
            return outcome
        with patch("studio_next.body_sequence_cuts.subprocess.run",
                   side_effect=tamper_during_encoder):
            with self.assertRaisesRegex(ValueError,"changed during render"):
                render_editorial_revision(self.planfile,self.operationfile,self.root,
                    self.root/"vault",self.root/"must-never-publish.mp4")
        self.assertTrue(mutated)
        self.assertFalse((self.root/"must-never-publish.mp4").exists())

    def test_rival_master_survives_actual_codec_publication_collision(self):
        from unittest.mock import patch
        import os
        accepted=self.root/"rival-won.mp4"
        competitor=self.root/"source1.mp4"
        competitor_sha=sha256_file(competitor)
        real_link=os.link
        collided=False
        def another_editor_publishes_first(source,destination,*args,**kwargs):
            nonlocal collided
            if Path(destination)==accepted:
                shutil.copyfile(competitor,accepted)
                collided=True
            return real_link(source,destination,*args,**kwargs)
        with patch("studio_next.body_sequence_cuts.os.link",
                   side_effect=another_editor_publishes_first):
            with self.assertRaises(FileExistsError):
                render_editorial_revision(self.planfile,self.operationfile,self.root,
                                           self.root/"vault",accepted)
        self.assertTrue(collided)
        self.assertEqual(sha256_file(accepted),competitor_sha)
        probe=subprocess.run(["ffmpeg","-hide_banner","-loglevel","error",
                              "-xerror","-i",str(accepted),"-map","0:v:0",
                              "-map","0:a:0","-f","null","-"],
                             capture_output=True,timeout=45)
        self.assertEqual(probe.returncode,0,probe.stderr)

    def test_immutable_revision_tamper_before_last_publish_refused(self):
        from unittest.mock import patch
        real_run=subprocess.run
        changed=False
        def corrupt_revision_after_codec(command,*args,**kwargs):
            nonlocal changed
            outcome=real_run(command,*args,**kwargs)
            if (not changed and isinstance(command,list) and
                    command[0]=="ffmpeg" and outcome.returncode==0 and
                    any(str(x).endswith("native-original-edited.mp4")
                        for x in command)):
                archives=list((self.root/".zx7-timeline-revisions").glob("*.json"))
                self.assertEqual(len(archives),1)
                archives[0].write_text('{"unauthorized":"change"}')
                changed=True
            return outcome
        with patch("studio_next.body_sequence_cuts.subprocess.run",
                   side_effect=corrupt_revision_after_codec):
            with self.assertRaisesRegex(ValueError,"revision changed before film publication"):
                render_editorial_revision(self.planfile,self.operationfile,self.root,
                                           self.root/"vault",self.root/"no-bad-master.mp4")
        self.assertTrue(changed)
        self.assertFalse((self.root/"no-bad-master.mp4").exists())

    def test_existing_revision_is_immutable_even_if_actor_changes_hidden_json(self):
        result=render_editorial_revision(self.planfile,self.operationfile,self.root,
                 self.root/"vault",self.root/"accepted.mp4")
        revision=self.root/result["revision_plan"]
        revision.write_text('{"edited":"malicious rewrite"}')
        with self.assertRaisesRegex(ValueError,"immutable timeline revision"):
            render_editorial_revision(self.planfile,self.operationfile,self.root,
               self.root/"vault",self.root/"blocked-replay.mp4")
        self.assertFalse((self.root/"blocked-replay.mp4").exists())

if __name__=="__main__":
    unittest.main()
