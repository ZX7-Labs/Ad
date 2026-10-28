"""Native contrast/saturation must survive model revisions and alter real pixels."""
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

from studio_next.body_mlt_tone import encode_tone,decode_tone,decode_tone_service,rekey_tone
from studio_next.body_document_schemas import validate_document,document_contract
from studio_next.body_mlt_editor import export_owned_mlt,verify_owned_mlt_project
from studio_next.body_mlt_roundtrip import recover_original_mlt_plan
from studio_next.body_mlt_linked_actions import apply_linked_editor_actions
from studio_next.test_body_mlt_linked_actions import original_project,value_at,action
from studio_next import test_body_mlt_editor as source_fixtures


def tone_key(frame,contrast=.5,saturation=.125):
    return {"frame":frame,"contrast":contrast,"saturation":saturation}


def tone(*keys,order=("contrast","saturation")):
    return {"order":list(order),"keyframes":list(keys or [tone_key(0)])}


def props(node):
    return {p.get("name"):p.text for p in node.findall("property")}


class NativeToneMath(unittest.TestCase):
    def test_full_precision_director_effect_order_and_hostile_expressions(self):
        chosen=tone(tone_key(0,contrast=.12345678901234568),
                    tone_key(11,saturation=.9876543210987654),
                    order=("saturation","contrast"))
        filters=[{"track":"0",**row} for row in encode_tone(chosen,12)]
        self.assertEqual([x["mlt_service"] for x in filters],
                         ["frei0r.saturat0r","frei0r.contrast0r"])
        self.assertEqual(decode_tone(filters,12),chosen)
        for bad in (tone(tone_key(1)),tone(tone_key(0),tone_key(0)),
                    tone(tone_key(0),tone_key(12)),
                    tone(tone_key(0,contrast=math.nan)),
                    tone(tone_key(0,saturation=True)),
                    tone(tone_key(0,saturation=1.2)),
                    tone(tone_key(0,contrast=-.5)),
                    tone(order=("contrast","contrast")),
                    {"order":["contrast"],"keyframes":[tone_key(0)]},
                    {"order":["contrast","saturation"],"keyframes":[tone_key(0)],
                     "extra":"execute"}):
            with self.subTest(invalid=bad),self.assertRaises(ValueError):
                encode_tone(bad,12)
        for service,value in (("frei0r.saturat0r","0=0.125;11=exec"),
                              ("frei0r.saturat0r","0=0.125;11=nan"),
                              ("frei0r.contrast0r","0=0.5;12=0.5"),
                              ("frei0r.contrast0r","0=0.5;11=999"),
                              ("frei0r.contrast0r","0=0.5;11=-0.1")):
            with self.subTest(service=service,value=value),self.assertRaises(ValueError):
                decode_tone_service({"track":"0","mlt_service":service,"0":value},12)
        for bad in (
            [filters[0]], [filters[0],filters[0]],
            [{**filters[0],"track":"1"},filters[1]],
            [{**filters[0],"0":"0=0.125;10=0.2"},filters[1]],
            [{**filters[0],"0":"0=0.125;11=0.2","0_duplicate":"1"},filters[1]],
        ):
            with self.subTest(native=bad),self.assertRaises(ValueError):
                decode_tone(bad,12)

    def test_model_can_discover_independent_controls_not_a_preset(self):
        plan=original_project();plan.pop("audio_tracks",None)
        plan["tracks"][0]["tone"]=tone(tone_key(0))
        self.assertTrue(validate_document("body.mlt_owned_export",plan))
        schema=document_contract("body.mlt_owned_export")["json_schema"]
        props=schema["properties"]["tracks"]["items"]["properties"]
        self.assertEqual(set(props["tone"]["properties"]),{"order","keyframes"})
        self.assertEqual(set(props["tone"]["properties"]["keyframes"]["items"]["properties"]),
                         {"frame","contrast","saturation"})
        plan["tracks"][0]["tone"]["style"]="cinematic preset"
        with self.assertRaises(ValueError):validate_document("body.mlt_owned_export",plan)

    def test_random_director_curves_survive_source_preserving_ripple(self):
        rng=random.Random(605601)
        for sample in range(100):
            film=original_project()
            film["tracks"][1].pop("opacity_keyframes",None)
            film["tracks"][1]["clips"][0].update(first_frame=0,end_frame=12,position_frame=0)
            positions=[0]+sorted(rng.sample(range(1,12),4))
            original=[tone_key(f,contrast=rng.random(),saturation=rng.random())
                      for f in positions]
            film["tracks"][1]["tone"]=tone(*original,order=("saturation","contrast"))
            before=copy.deepcopy(film)
            at=rng.randrange(0,10);length=rng.randrange(1,12-at)
            for operation in ("ripple_insert","ripple_delete"):
                new,receipt=apply_linked_editor_actions(film,{
                    "edits":[action(operation,at,duration=length)]})
                curve=new["tracks"][1]["tone"]["keyframes"]
                self.assertEqual(new["tracks"][1]["tone"]["order"],
                                 ["saturation","contrast"])
                for t in range(12):
                    if operation=="ripple_delete" and at<=t<at+length:continue
                    destination=t+length if operation=="ripple_insert" and t>=at else (
                        t-length if operation=="ripple_delete" and t>=at+length else t)
                    for name in ("contrast","saturation"):
                        self.assertAlmostEqual(value_at(original,t,name),
                                               value_at(curve,destination,name),
                                               delta=1e-9,msg=str((sample,operation,t,name)))
                self.assertEqual(receipt["largest_interpolated_key_rounding"],0)
            self.assertEqual(film,before)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "Actual original-source media required")
class NativeToneOwnedProject(unittest.TestCase):
    def setup_film(self,root):
        plan,file=source_fixtures.VerifiedMLTEditorialTests()._case(root)
        plan["tracks"][0]["tone"]=tone(tone_key(0,contrast=.5,saturation=0),
                                        tone_key(11,contrast=.5,saturation=.125),
                                        order=("saturation","contrast"))
        plan["tracks"][1]["tone"]=tone(tone_key(0,contrast=.5,saturation=.0))
        file.write_text(json.dumps(plan))
        owned=root/"tone-owned.mlt"
        export_owned_mlt(file,root,root/"vault",owned)
        return plan,file,owned

    def test_roundtrip_revision_comparison_and_untrusted_mlt_refused(self):
        from studio_next.body_mlt_revision import revise_owned_mlt_project
        from studio_next.body_mlt_compare import compare_owned_mlt_projects
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan,_,film=self.setup_film(root)
            before=film.read_bytes()
            self.assertEqual(recover_original_mlt_plan(film,root,root/"vault")["plan"],plan)
            for name in ("missing","duplicate","wrong_track","untrusted","wrong_frame","reordered","incomplete"):
                xml=ET.fromstring(before);tractor=xml.find("tractor")
                tones=[n for n in tractor.findall("filter") if props(n).get(
                    "mlt_service") in ("frei0r.contrast0r","frei0r.saturat0r")]
                first=tones[0]
                fields={p.get("name"):p for p in first.findall("property")}
                if name=="missing":tractor.remove(first)
                elif name=="duplicate":tractor.insert(2,copy.deepcopy(first))
                elif name=="wrong_track":fields["track"].text="9"
                elif name=="untrusted":ET.SubElement(first,"property",{"name":"resource"}).text="/etc/passwd"
                elif name=="wrong_frame":fields["0"].text="0=0;12=0.5"
                elif name=="reordered":tractor.remove(first);tractor.append(first)
                elif name=="incomplete":tractor.remove(tones[1])
                forged=root/(name+".mlt");forged.write_bytes(ET.tostring(xml))
                with self.subTest(attack=name),self.assertRaises(ValueError):
                    verify_owned_mlt_project(forged)
            changes=root/"director-revision.json"
            changes.write_text(json.dumps({"operations":[{
                "op":"replace","path":"/tracks/0/tone/keyframes/0/saturation",
                "value":.0654321987654321}]}))
            revised=root/"director-tone-revision.mlt"
            receipt=revise_owned_mlt_project(film,changes,root,root/"vault",revised)
            self.assertTrue(receipt["lossless_typed_native_roundtrip"])
            review=compare_owned_mlt_projects(film,revised,root,root/"vault",
                                               focus="picture:0")
            track=review["selected_track"]["change"]
            self.assertEqual(track["source_frame_spans"],[])
            self.assertIn("tone",track["native_track_controls"]["after"])
            self.assertEqual(recover_original_mlt_plan(revised,root,root/"vault")[
                "plan"]["tracks"][0]["tone"]["keyframes"][0]["saturation"],
                .0654321987654321)
            self.assertEqual(film.read_bytes(),before)

    @unittest.skipUnless(shutil.which("melt"),"Installed native MLT source filter required")
    def test_real_film_pixels_prove_different_color_and_director_animation(self):
        from studio_next.body_mlt_render import render_owned_mlt
        from studio_next.test_body_mlt_transform import pictures,pixel
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan,file,graded=self.setup_film(root)
            original=graded.read_bytes()
            neutral=copy.deepcopy(plan)
            for layer in neutral["tracks"]:layer.pop("tone",None)
            file.write_text(json.dumps(neutral))
            baseline=root/"baseline.mlt"
            export_owned_mlt(file,root,root/"vault",baseline)
            original_movie=root/"original.mp4"
            toned_movie=root/"graded.mp4"
            render_owned_mlt(baseline,root,original_movie)
            render_owned_mlt(graded,root,toned_movie)
            frames=pictures(toned_movie)
            originals=pictures(original_movie)
            first=pixel(frames[0],2,2)
            last=pixel(frames[11],2,2)
            red_original=pixel(originals[0],2,2)
            # At zero saturation, actual red decoded source must become
            # near-monochrome; by film frame eleven the model chose to
            # restore the documented native neutral saturation.
            self.assertGreater(red_original[0],red_original[1]+120)
            self.assertLess(max(first)-min(first),65,(red_original,first))
            self.assertGreater(last[0],last[1]+95,(first,last))
            # The upper blue source is graded independently, and only
            # exists from film frames four to nine.
            blue=pixel(frames[6],32,24)
            self.assertLess(max(blue)-min(blue),65,blue)
            # Physically prove the second native contrast filter also
            # controls pixels rather than accepting inert XML.
            contrast=copy.deepcopy(plan)
            contrast["tracks"][0]["tone"]=tone(tone_key(0,contrast=0,saturation=.125))
            contrast["tracks"][1].pop("tone")
            file.write_text(json.dumps(contrast))
            contrast_mlt=root/"contrast.mlt"
            export_owned_mlt(file,root,root/"vault",contrast_mlt)
            contrast_movie=root/"contrast.mp4"
            render_owned_mlt(contrast_mlt,root,contrast_movie)
            other=pixel(pictures(contrast_movie)[11],2,2)
            self.assertGreater(max(abs(a-b) for a,b in zip(
                other,pixel(originals[11],2,2))),25,(other,originals[11][:9]))
            with patch("studio_next.body_mlt_render._require_native_tone",
                       side_effect=RuntimeError("missing native source tone")):
                with self.assertRaisesRegex(RuntimeError,"missing native"):
                    render_owned_mlt(graded,root,root/"unapproved.mp4")
            self.assertFalse((root/"unapproved.mp4").exists())
            self.assertEqual(graded.read_bytes(),original)


if __name__=="__main__":
    unittest.main()
