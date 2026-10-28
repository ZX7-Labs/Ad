"""One attested source can carry different reversible grades on different cuts.

This uses a verified, dedicated native producer for each grade-bearing clip.
Filters are NEVER inserted into XML playlist entries, where native editors
can silently discard them when saving. Artist controls live in original-source
frame coordinates and remain tied to those bytes through timeline movement.
"""
import copy
import json
import math
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from studio_next.body_mlt_grade import GRADE_FIELDS
from studio_next.body_document_schemas import validate_document,document_contract
from studio_next.body_mlt_editor import export_owned_mlt,verify_owned_mlt_project
from studio_next.body_mlt_roundtrip import recover_original_mlt_plan
from studio_next.body_mlt_linked_actions import apply_linked_editor_actions
from studio_next.test_body_mlt_linked_actions import action
from studio_next import test_body_mlt_editor as original_fixtures


def source_key(frame,**values):
    key={"frame":frame,**{name:(0 if name.startswith("lift_") else 1)
                        for name in GRADE_FIELDS}}
    key.update(values)
    return key


def unique_sources(plan):
    original=copy.deepcopy(plan["tracks"][1]["clips"][0])
    first={**original,"first_frame":0,"end_frame":5,
           "position_frame":0,
           "clip_grade":{"keyframes":[source_key(0,gain_b=.05)]}}
    second={**original,"first_frame":6,"end_frame":12,
            "position_frame":6,
            "clip_grade":{"keyframes":[source_key(0,gain_b=1.0)]}}
    plan["tracks"][1]["clips"]=[first,second]
    return plan


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "Real source-bound media custody requires actual FFmpeg")
class NativeClipGradeTests(unittest.TestCase):
    def _case(self,root):
        plan,file=original_fixtures.VerifiedMLTEditorialTests()._case(root)
        unique_sources(plan)
        file.write_text(json.dumps(plan))
        edit=root/"source-grades.mlt"
        export_owned_mlt(file,root,root/"vault",edit)
        return plan,file,edit

    def test_two_cuts_share_the_same_original_without_sharing_an_artist_look(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan,file,edit=self._case(root)
            original=edit.read_bytes()
            self.assertTrue(validate_document("body.mlt_owned_export",plan))
            self.assertEqual(recover_original_mlt_plan(edit,root,root/"vault")["plan"],plan)
            xml=ET.fromstring(original)
            clips=xml.findall("playlist")[1].findall("entry")
            self.assertEqual(len(clips),2)
            self.assertNotEqual(clips[0].get("producer"),clips[1].get("producer"))
            self.assertTrue(all(item.get("producer").startswith("clip-source-1-")
                                for item in clips))
            producers=xml.findall("producer")
            graded=[p for p in producers if p.get("id","").startswith("clip-source-")]
            self.assertEqual(len(graded),2)
            self.assertEqual([x.find("filter").find("./property[@name='gain_b']").text
                              for x in graded],["0=0.05","0=1"])
            self.assertTrue(all(x.find("filter").get("out")=="11" for x in graded))
            self.assertEqual(len({x.find("./property[@name='zx7.original_sha256']").text
                                  for x in graded}),1)
            self.assertEqual(verify_owned_mlt_project(edit)["verified_mlt_tracks"],2)
            self.assertEqual(edit.read_bytes(),original)

    def test_revision_changes_only_the_selected_source_cuts_grade_and_keeps_prior(self):
        from studio_next.body_mlt_revision import revise_owned_mlt_project
        from studio_next.body_mlt_compare import compare_owned_mlt_projects
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan,file,edit=self._case(root)
            old=edit.read_bytes()
            document=root/"change.json"
            document.write_text(json.dumps({"operations":[{"op":"replace",
                "path":"/tracks/1/clips/0/clip_grade/keyframes/0/gain_b","value":0.2}]}))
            latest=root/"source-grades-v2.mlt"
            status=revise_owned_mlt_project(edit,document,root,root/"vault",latest)
            self.assertTrue(status["lossless_typed_native_roundtrip"])
            recovered=recover_original_mlt_plan(latest,root,root/"vault")["plan"]
            self.assertEqual(recovered["tracks"][1]["clips"][0]["clip_grade"][
                "keyframes"][0]["gain_b"],0.2)
            self.assertEqual(recovered["tracks"][1]["clips"][1]["clip_grade"],
                             plan["tracks"][1]["clips"][1]["clip_grade"])
            review=compare_owned_mlt_projects(edit,latest,root,root/"vault",
                                               focus="picture:1")
            self.assertEqual(review["selected_track"]["change"]["source_frame_spans"],[])
            self.assertIsNotNone(review["selected_track"]["change"][
                "native_clip_partition_delta"])
            self.assertEqual(edit.read_bytes(),old)

    def test_untrusted_nested_services_and_orphan_filters_fail_before_native_loading(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan,file,edit=self._case(root)
            original=edit.read_bytes()
            for kind in ("resource","service","extra","clip","source_clock","owner","orphan","duplicate"):
                xml=ET.fromstring(original)
                graded=[p for p in xml.findall("producer")
                        if p.get("id","").startswith("clip-source-")]
                producer=graded[0]
                filt=producer.find("filter")
                if kind=="resource":
                    ET.SubElement(filt,"property",{"name":"resource"}).text="/etc/passwd"
                elif kind=="service":
                    filt.find("./property[@name='mlt_service']").text="avformat"
                elif kind=="extra":
                    producer.append(copy.deepcopy(filt))
                elif kind=="clip":
                    producer.set("id","clip-source-0-0-"+plan["tracks"][1]["clips"][0]["asset_id"][:24])
                elif kind=="source_clock":
                    filt.set("out","7")
                elif kind=="owner":
                    producer.find("./property[@name='zx7.attestation_id']").text="0"*64
                elif kind=="orphan":
                    entry=xml.findall("playlist")[1].findall("entry")[0]
                    entry.set("producer","source-"+plan["tracks"][1]["clips"][0]["asset_id"][:24])
                elif kind=="duplicate":
                    xml.insert(3,copy.deepcopy(producer))
                forged=root/(kind+".mlt")
                forged.write_bytes(ET.tostring(xml))
                with self.subTest(kind=kind),self.assertRaises((ValueError,KeyError)):
                    verify_owned_mlt_project(forged)
            bad=copy.deepcopy(plan)
            bad["tracks"][1]["clips"][0]["clip_grade"]["keyframes"][0]["gain_b"]=math.inf
            with self.assertRaises(ValueError):
                validate_document("body.mlt_owned_export",bad)
            self.assertEqual(original,edit.read_bytes())

    def test_source_bound_grade_survives_director_blade_and_ripple_without_key_retiming(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan,_,edit=self._case(root)
            first=plan["tracks"][1]["clips"][0]["clip_grade"]
            decision=action("blade",3)
            decision["audio_tracks"]=[]
            changed,report=apply_linked_editor_actions(plan,{"edits":[decision]})
            self.assertEqual(changed["tracks"][1]["clips"][0]["clip_grade"],first)
            self.assertEqual(changed["tracks"][1]["clips"][1]["clip_grade"],first)
            next_step=action("ripple_insert",2,duration=2)
            next_step["audio_tracks"]=[]
            moved,_=apply_linked_editor_actions(plan,{"edits":[next_step]})
            self.assertTrue(all(c["clip_grade"] in (first,
                plan["tracks"][1]["clips"][1]["clip_grade"])
                for c in moved["tracks"][1]["clips"]))
            self.assertEqual(recover_original_mlt_plan(edit,root,root/"vault")["plan"],plan)

    @unittest.skipUnless(shutil.which("melt"),
                         "Installed MLT clip-source filter required for actual pixels")
    def test_one_original_media_source_yields_two_different_real_native_clip_looks(self):
        from studio_next.body_mlt_render import render_owned_mlt
        from studio_next.test_body_mlt_transform import pictures,pixel
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan,_,edit=self._case(root)
            before=edit.read_bytes()
            report=render_owned_mlt(edit,root,root/"source-graded.mp4")
            frames=pictures(root/"source-graded.mp4")
            first=pixel(frames[2],32,24)
            second=pixel(frames[9],32,24)
            gap=pixel(frames[5],32,24)
            self.assertGreater(second[2],first[2]+100,(first,second))
            self.assertGreater(second[2],170,(first,second))
            self.assertGreater(gap[0],180,(gap,"ungraded red lower layer disappeared"))
            self.assertEqual(edit.read_bytes(),before)
            self.assertTrue(report["full_decoded_picture"])


if __name__=="__main__":
    unittest.main()
