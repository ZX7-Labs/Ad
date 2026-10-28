"""Independent director-owned RGB color wheels and actual native media proof.

The selected values are model-controlled, never a prescribed look. The native
filter is not equivalent to scene-linear or comprehensive professional grading.
"""
import copy
import json
import math
import random
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from studio_next.body_mlt_grade import (
    GRADE_FIELDS,encode_grade,decode_grade,rekey_grade)
from studio_next.body_document_schemas import validate_document,document_contract
from studio_next.body_mlt_editor import export_owned_mlt,verify_owned_mlt_project
from studio_next.body_mlt_roundtrip import recover_original_mlt_plan
from studio_next.body_mlt_linked_actions import apply_linked_editor_actions
from studio_next.test_body_mlt_linked_actions import original_project,value_at,action
from studio_next import test_body_mlt_editor as original_fixtures


def grade_key(frame,**changes):
    key={"frame":frame}
    for name in GRADE_FIELDS:
        key[name]=0 if name.startswith("lift_") else 1
    key.update(changes)
    return key


def grade(*keys):
    return {"keyframes":list(keys or [grade_key(0)])}


def properties(node):
    return {p.get("name"):p.text for p in node.findall("property")}


class NativeRGBGradeContracts(unittest.TestCase):
    def test_all_nine_channel_values_preserve_full_precision_and_reject_expressions(self):
        authored=grade(grade_key(0,lift_r=0.12345678901234568,
                                  gamma_g=1.2345678901234567),
                      grade_key(11,gain_b=2.3456789012345678))
        encoded={"track":"0",**encode_grade(authored,12)}
        self.assertEqual(decode_grade(encoded,12),authored)
        self.assertEqual(len(GRADE_FIELDS),9)
        for name,bad in (("lift_r",-1),("lift_b",5.01),("gamma_g",0),
                         ("gamma_b",math.inf),("gain_r",True),
                         ("gain_g","0=eval"),("lift_g",math.nan)):
            with self.subTest(name=name,bad=bad),self.assertRaises(ValueError):
                encode_grade(grade(grade_key(0,**{name:bad})),12)
        for candidate in (grade(grade_key(1)),
                          grade(grade_key(0),grade_key(0)),
                          grade(grade_key(0),grade_key(12)),
                          {"keyframes":[grade_key(0)],"plugin":"avformat"},
                          {"keyframes":[{"frame":0,"gain_r":1}]}):
            with self.subTest(candidate=candidate),self.assertRaises(ValueError):
                encode_grade(candidate,12)
        for name,value in (("gain_r","0=1;11=$(touch /tmp/payload)"),
                           ("lift_r","0=nan;11=1"),("gamma_b","0=0"),
                           ("track","0;system"),("mlt_service","avformat"),
                           ("resource","/etc/passwd")):
            forged={**encoded,name:value}
            with self.subTest(name=name),self.assertRaises(ValueError):
                decode_grade(forged,12)

    def test_grading_is_discoverable_without_any_fixed_style_or_art_direction(self):
        original=original_project()
        original["tracks"][0]["grade"]=grade(grade_key(0))
        self.assertTrue(validate_document("body.mlt_owned_export",original))
        controls=document_contract("body.mlt_owned_export")["json_schema"]
        item=controls["properties"]["tracks"]["items"]["properties"]["grade"]
        self.assertEqual(set(item["properties"]["keyframes"]["items"]["properties"]),
                         {"frame",*GRADE_FIELDS})
        original["tracks"][0]["grade"]["style"]="preset"
        with self.assertRaises(ValueError):
            validate_document("body.mlt_owned_export",original)

    def test_100_arbitrary_director_curves_preserve_source_frames_through_ripple(self):
        rng=random.Random(734521)
        for case in range(100):
            original=original_project()
            original["tracks"][1]["clips"][0].update(
                first_frame=0,end_frame=12,position_frame=0)
            positions=[0]+sorted(rng.sample(range(1,12),4))
            keys=[]
            for frame in positions:
                controls={name:rng.uniform(0.01,3) for name in GRADE_FIELDS}
                keys.append(grade_key(frame,**controls))
            original["tracks"][1]["grade"]=grade(*keys)
            pristine=copy.deepcopy(original)
            at=rng.randrange(0,10)
            duration=rng.randrange(1,12-at)
            for kind in ("ripple_insert","ripple_delete"):
                revised,report=apply_linked_editor_actions(original,{
                    "edits":[action(kind,at,duration=duration)]})
                now=revised["tracks"][1]["grade"]["keyframes"]
                for frame in range(12):
                    if kind=="ripple_delete" and at<=frame<at+duration:
                        continue
                    moved=frame+(duration if frame>=at else 0) if (
                        kind=="ripple_insert") else frame-(
                        duration if frame>=at+duration else 0)
                    for field in GRADE_FIELDS:
                        self.assertAlmostEqual(
                            value_at(keys,frame,field),value_at(now,moved,field),
                            delta=1e-9,msg=str((case,kind,at,duration,frame,field)))
                self.assertEqual(report["largest_interpolated_key_rounding"],0)
            self.assertEqual(original,pristine)


@unittest.skipUnless(all(shutil.which(command) for command in
                     ("melt","ffmpeg","ffprobe")),
                     "Full native tool fingerprint proof requires installed renderer")
class NativeRGBGradeCodeIdentity(unittest.TestCase):
    def test_color_engine_code_mutation_invalidates_all_affected_operation_revisions(self):
        from studio_next.body_integration import _trusted_body_revision
        ids=("body.mlt_owned_export","body.mlt_owned_render",
             "body.mlt_owned_import","body.mlt_owned_relink",
             "body.mlt_owned_compare","body.mlt_owned_revision",
             "body.mlt_owned_timecode_format","body.mlt_owned_timecode_parse")
        read=Path.read_bytes
        def modified(file):
            content=read(file)
            if file.name=="body_mlt_grade.py":
                return content+b"\\n# proposed upgraded grading math\\n"
            return content
        for tool in ids:
            with self.subTest(tool=tool):
                previous=_trusted_body_revision(tool)
                with patch.object(Path,"read_bytes",modified):
                    changed=_trusted_body_revision(tool)
                self.assertNotEqual(previous,changed)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "Native RGB grade source custody requires actual FFmpeg")
class NativeRGBGradeProjectTests(unittest.TestCase):
    def _project(self,root):
        plan,file=original_fixtures.VerifiedMLTEditorialTests()._case(root)
        plan["tracks"][0]["grade"]=grade(grade_key(0,lift_g=0.15),
                                         grade_key(11,lift_g=0.8))
        plan["tracks"][1]["grade"]=grade(grade_key(0,gamma_b=2,gain_b=0.3))
        file.write_text(json.dumps(plan))
        edit=root/"graded-original.mlt"
        export_owned_mlt(file,root,root/"vault",edit)
        return plan,file,edit

    def test_original_sources_recover_all_color_controls_and_native_hostile_xml_is_rejected(self):
        from studio_next.body_mlt_revision import revise_owned_mlt_project
        from studio_next.body_mlt_compare import compare_owned_mlt_projects
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan,_,edit=self._project(root)
            original=edit.read_bytes()
            self.assertEqual(recover_original_mlt_plan(edit,root,root/"vault")["plan"],plan)
            for case in ("unknown","service","clock","duplicate","track","order","negative"):
                xml=ET.fromstring(original);tractor=xml.find("tractor")
                filt=tractor.findall("filter")[0]
                p={x.get("name"):x for x in filt.findall("property")}
                if case=="unknown":
                    ET.SubElement(filt,"property",{"name":"producer"}).text="/etc/passwd"
                elif case=="service":p["mlt_service"].text="avformat"
                elif case=="clock":p["lift_g"].text="0=0.15;12=0.8"
                elif case=="duplicate":
                    ET.SubElement(filt,"property",{"name":"lift_g"}).text="0=1"
                elif case=="track":p["track"].text="3"
                elif case=="order":
                    tractor.remove(filt);tractor.append(filt)
                elif case=="negative":p["gamma_r"].text="0=-1"
                forged=root/(case+".mlt")
                forged.write_bytes(ET.tostring(xml))
                with self.subTest(case=case),self.assertRaises(ValueError):
                    verify_owned_mlt_project(forged)
            change=root/"change.json"
            change.write_text(json.dumps({"operations":[{
                "op":"replace","path":"/tracks/0/grade/keyframes/0/lift_g","value":0.32}]}))
            modified=root/"graded-revision.mlt"
            result=revise_owned_mlt_project(edit,change,root,root/"vault",modified)
            self.assertTrue(result["lossless_typed_native_roundtrip"])
            reviewed=compare_owned_mlt_projects(edit,modified,root,root/"vault",
                                                 focus="picture:0")
            change=reviewed["selected_track"]["change"]
            self.assertEqual(change["source_frame_spans"],[])
            self.assertIn("grade",change["native_track_controls"]["after"])
            self.assertEqual(recover_original_mlt_plan(modified,root,root/"vault")[
                "plan"]["tracks"][0]["grade"]["keyframes"][0]["lift_g"],0.32)
            self.assertEqual(edit.read_bytes(),original)

    @unittest.skipUnless(shutil.which("melt"),"Real installed native MLT color engine required")
    def test_real_decoded_picture_changes_over_time_without_altering_authored_sources(self):
        from studio_next.body_mlt_render import render_owned_mlt
        from studio_next.test_body_mlt_transform import pictures,pixel
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan,file,graded=self._project(root)
            source=graded.read_bytes()
            baseline=copy.deepcopy(plan)
            for track in baseline["tracks"]:
                track.pop("grade",None)
            file.write_text(json.dumps(baseline))
            untouched=root/"ungraded.mlt"
            export_owned_mlt(file,root,root/"vault",untouched)
            no_grade=root/"ungraded.mp4"
            colored=root/"graded.mp4"
            render_owned_mlt(untouched,root,no_grade)
            render_owned_mlt(graded,root,colored)
            original_frames=pictures(no_grade)
            revised_frames=pictures(colored)
            # Outside delayed upper picture, the physical bottom red source is
            # unchanged; a model-selected green lift changes decoded RGB over
            # time, not merely the native XML. Input film frame 0 and frame 11
            # carry different authored lift levels on exactly this film clock.
            old_first=pixel(original_frames[0],2,2)
            old_last=pixel(original_frames[11],2,2)
            new_first=pixel(revised_frames[0],2,2)
            new_last=pixel(revised_frames[11],2,2)
            self.assertGreater(new_last[1],old_last[1]+30,
                               (old_last,new_last,"grade was inert"))
            self.assertGreater(new_last[1],new_first[1]+30,
                               (new_first,new_last,"animated grade was inert"))
            self.assertLess(abs(old_first[1]-old_last[1]),15)
            # The upper blue original starts at film frame 4. Its independent
            # gain wheel darkens only that source; no LUT or prescribed look
            # is applied to the bottom source or owner-original files.
            untouched_blue=pixel(original_frames[6],32,24)
            graded_blue=pixel(revised_frames[6],32,24)
            self.assertGreater(untouched_blue[2],210)
            self.assertLess(graded_blue[2],untouched_blue[2]-30,
                            (untouched_blue,graded_blue,"upper RGB gain was inert"))
            # If the native filter disappears, never silently render a look
            # different from the one the AI authored.
            with patch("studio_next.body_mlt_render._require_native_grade",
                       side_effect=RuntimeError("missing native color grade")):
                with self.assertRaisesRegex(RuntimeError,"missing native color grade"):
                    render_owned_mlt(graded,root,root/"inert-color.mp4")
            self.assertFalse((root/"inert-color.mp4").exists())
            self.assertEqual(graded.read_bytes(),source)


if __name__=="__main__":
    unittest.main()
