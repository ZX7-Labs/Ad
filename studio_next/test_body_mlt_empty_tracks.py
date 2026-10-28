"""Source-empty professional NLE picture lanes, real renders, atomic source moves."""
import copy
import json
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from studio_next.body_document_schemas import validate_document
from studio_next.body_mlt_editor import (
    export_owned_mlt,validate_mlt_edit,verify_owned_mlt_project)
from studio_next.body_mlt_roundtrip import recover_original_mlt_plan
from studio_next.body_mlt_linked_actions import apply_linked_editor_actions
from studio_next import test_body_mlt_editor as source_fixtures


def place(src,dst):
    return {"edits":[{"kind":"place",
        "effects":"inherit_destination_track_at_film_time",
        "placements":[{"domain":"picture","from_track":src,"clip":0,
                       "to_track":dst,"at_frame":4}]}]}


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "Actual owned video sources needed to prove empty picture tracks")
class BlankUpperPictureTracks(unittest.TestCase):
    def make_project(self,root):
        plan,planfile=source_fixtures.VerifiedMLTEditorialTests()._case(root)
        plan["tracks"].insert(1,{"clips":[]})
        planfile.write_text(json.dumps(plan))
        mlt=root/"original-with-empty-upper.mlt"
        export_owned_mlt(planfile,root,root/"vault",mlt)
        return plan,planfile,mlt

    def test_original_sources_native_roundtrip_and_empty_track_stays_editable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan,_,mlt=self.make_project(root)
            self.assertTrue(validate_document("body.mlt_owned_export",plan))
            checked=validate_mlt_edit(plan,root,root/"vault")
            self.assertEqual([len(x) for x in checked["tracks"]],[1,0,1])
            self.assertEqual(checked["frames"],12)
            xml=ET.fromstring(mlt.read_bytes())
            self.assertEqual(xml.findall("./playlist")[1].find("blank").get("length"),"12")
            original=mlt.read_bytes()
            proof=verify_owned_mlt_project(mlt)
            self.assertEqual(proof["verified_mlt_tracks"],3)
            self.assertEqual(recover_original_mlt_plan(mlt,root,root/"vault")["plan"],plan)
            edited,receipt=apply_linked_editor_actions(plan,place(2,1))
            self.assertEqual([len(x["clips"]) for x in edited["tracks"]],[1,1,0])
            self.assertEqual(receipt["operations"][0]["kind"],"place")
            self.assertEqual(edited["tracks"][1]["clips"][0]["asset_id"],
                             plan["tracks"][2]["clips"][0]["asset_id"])
            self.assertEqual(edited["tracks"][1]["clips"][0]["attestation_id"],
                             plan["tracks"][2]["clips"][0]["attestation_id"])
            self.assertTrue(validate_document("body.mlt_owned_export",edited))
            self.assertEqual(validate_mlt_edit(edited,root,root/"vault")["frames"],12)
            undo,_=apply_linked_editor_actions(edited,place(1,2))
            self.assertEqual(undo,plan)
            self.assertEqual(mlt.read_bytes(),original)

    def test_empty_bottom_or_empty_unlicensed_sound_cannot_create_fake_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan,_,mlt=self.make_project(root)
            bad=copy.deepcopy(plan);bad["tracks"][0]["clips"]=[]
            self.assertTrue(validate_document("body.mlt_owned_export",bad))
            with self.assertRaisesRegex(ValueError,"bottom original picture"):
                validate_mlt_edit(bad,root,root/"vault")
            bad=copy.deepcopy(plan);bad["audio_tracks"]=[{"clips":[]}]
            with self.assertRaises(ValueError):
                validate_document("body.mlt_owned_export",bad)
            xml=ET.fromstring(mlt.read_bytes())
            bottom=xml.findall("./playlist")[0]
            for child in list(bottom):bottom.remove(child)
            ET.SubElement(bottom,"blank",{"length":"12"})
            forged=root/"unauthorized-empty-backing.mlt"
            forged.write_bytes(ET.tostring(xml))
            with self.assertRaisesRegex(ValueError,"bottom original picture"):
                verify_owned_mlt_project(forged)

    def test_new_version_and_undo_preserve_rights_and_original_movie(self):
        from studio_next.body_mlt_revision import revise_owned_mlt_project
        from studio_next.body_mlt_compare import compare_owned_mlt_projects
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan,_,original=self.make_project(root)
            untouched=original.read_bytes()
            cmd=root/"move.json";cmd.write_text(json.dumps(place(2,1)))
            updated=root/"moved-source-into-previously-empty-lane.mlt"
            proof=revise_owned_mlt_project(original,cmd,root,root/"vault",updated)
            self.assertTrue(proof["lossless_typed_native_roundtrip"])
            moved=recover_original_mlt_plan(updated,root,root/"vault")["plan"]
            self.assertEqual([len(x["clips"]) for x in moved["tracks"]],[1,1,0])
            changes=compare_owned_mlt_projects(original,updated,root,root/"vault",
                                                focus="all")
            self.assertTrue(changes["source_ownership_preserved"] if
                "source_ownership_preserved" in changes else changes["rights_attested"])
            self.assertEqual(original.read_bytes(),untouched)
            cmd=root/"move-back.json";cmd.write_text(json.dumps(place(1,2)))
            undone=root/"source-back-in-original-lane.mlt"
            revise_owned_mlt_project(updated,cmd,root,root/"vault",undone)
            self.assertEqual(recover_original_mlt_plan(undone,root,root/"vault")["plan"],plan)
            if not shutil.which("melt"):
                return
            from studio_next.body_mlt_render import render_owned_mlt
            from studio_next.test_body_mlt_transform import pictures
            before=root/"before.mp4";after=root/"after.mp4"
            render_owned_mlt(original,root,before)
            render_owned_mlt(updated,root,after)
            left=pictures(before);right=pictures(after)
            self.assertEqual(len(left),12)
            self.assertEqual(len(right),12)
            for index in (0,4,6,9,11):
                diff=[abs(x-y) for x,y in zip(left[index],right[index])]
                self.assertLess(sum(diff)/len(diff),4,(index,"unmodified source picture"))
                self.assertLess(sum(x>18 for x in diff)/len(diff),.03)
            self.assertEqual(original.read_bytes(),untouched)


if __name__=="__main__":
    unittest.main()
