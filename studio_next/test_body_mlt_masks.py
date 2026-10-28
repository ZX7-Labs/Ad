"""Native alpha apertures retain source space, rights and reversible motion."""
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

from studio_next.body_mlt_transform import encode_mask,decode_mask,MASK_FIELDS
from studio_next.body_mlt_editor import export_owned_mlt,verify_owned_mlt_project
from studio_next.body_mlt_roundtrip import recover_original_mlt_plan
from studio_next.body_mlt_linked_actions import apply_linked_editor_actions
from studio_next.test_body_mlt_linked_actions import original_project,value_at,action
from studio_next.test_body_mlt_transform import geometry,transform,pictures,pixel
from studio_next import test_body_mlt_editor as original_fixtures


def aperture(**values):
    return {"frame":0,"x":0,"y":0,"width":32,"height":48,"rounding":0,**values}


class NativeMaskMathTests(unittest.TestCase):
    def test_only_finite_typed_source_windows_can_enter_the_native_cropper(self):
        mask={"keyframes":[aperture(rounding=.12345678901234568),aperture(frame=11,x=32)]}
        native={"track":"1",**encode_mask(mask,12)}
        self.assertEqual(decode_mask(native,12),mask)
        for field,value in (("rounding",1.01),("rounding",True),("rounding",math.nan),
                           ("x","0;exec"),("width",0)):
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                encode_mask({"keyframes":[aperture(**{field:value})]},12)
        for name,value in (("color","#ffffffff"),("circle","1"),
                           ("radius","0=0;11=2"),("resource","/etc/passwd"),
                           ("rect","0=0 0 32 48 0")):
            with self.subTest(native=name),self.assertRaises(ValueError):
                decode_mask({**native,name:value},12)

    def test_100_arbitrary_aperture_curves_survive_insert_delete_at_every_source_frame(self):
        rng=random.Random(851623)
        for _ in range(100):
            plan=original_project();plan["tracks"][1].pop("opacity_keyframes")
            plan["tracks"][1]["clips"][0].update(first_frame=0,end_frame=12,position_frame=0)
            curve=[aperture(frame=f,x=rng.uniform(-16,64),y=rng.uniform(-12,48),
                width=rng.uniform(1,96),height=rng.uniform(1,72),rounding=rng.random())
                for f in [0]+sorted(rng.sample(range(1,12),4))]
            plan["tracks"][1]["mask"]={"keyframes":curve}
            at=rng.randrange(0,10);count=rng.randrange(1,12-at)
            for kind in ("ripple_insert","ripple_delete"):
                revised,_=apply_linked_editor_actions(plan,{"edits":[action(kind,at,duration=count)]})
                now=revised["tracks"][1]["mask"]["keyframes"]
                for t in range(12):
                    if kind=="ripple_delete" and at<=t<at+count:continue
                    moved=t+(count if t>=at else 0) if kind=="ripple_insert" else t-(count if t>=at+count else 0)
                    for field in MASK_FIELDS:
                        self.assertAlmostEqual(value_at(curve,t,field),value_at(now,moved,field),delta=1e-9)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"Actual owner media required")
class NativeMaskSourceTests(unittest.TestCase):
    def _case(self,root):
        plan,file=original_fixtures.VerifiedMLTEditorialTests()._case(root)
        plan["tracks"][1]["clips"][0].update(position_frame=0,first_frame=0,end_frame=12)
        plan["tracks"][1]["mask"]={"keyframes":[aperture()]}
        return plan,file

    def test_mask_roundtrip_immutable_revision_and_native_filter_order_are_strict(self):
        from studio_next.body_mlt_revision import revise_owned_mlt_project
        from studio_next.body_mlt_compare import compare_owned_mlt_projects
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan,file=self._case(root)
            plan["tracks"][1]["transform"]=transform(geometry(x=32,y=0,width=32,height=48))
            file.write_text(json.dumps(plan));native=root/"original.mlt"
            export_owned_mlt(file,root,root/"vault",native);original=native.read_bytes()
            self.assertEqual(recover_original_mlt_plan(native,root,root/"vault")["plan"],plan)
            cmd=root/"revise.json";cmd.write_text(json.dumps({"operations":[{
                "op":"replace","path":"/tracks/1/mask/keyframes/0/rounding","value":1}]}))
            revised=root/"round.mlt";revise_owned_mlt_project(native,cmd,root,root/"vault",revised)
            review=compare_owned_mlt_projects(native,revised,root,root/"vault",focus="picture:1")
            self.assertEqual(review["selected_track"]["change"]["source_frame_spans"],[])
            self.assertEqual(review["selected_track"]["change"]["native_track_controls"]["after"]["mask"]["keyframes"][0]["rounding"],1)
            for kind in ("color","order","duplicate","circle"):
                xml=ET.fromstring(original);tractor=xml.find("tractor");mask=tractor.find("filter")
                if kind=="order":tractor.remove(mask);tractor.insert(2,mask)
                elif kind=="duplicate":tractor.insert(1,copy.deepcopy(mask))
                else:
                    for prop in mask:
                        if prop.get("name")==kind:prop.text="#ffffffff" if kind=="color" else "1"
                forged=root/(kind+".mlt");forged.write_bytes(ET.tostring(xml))
                with self.subTest(kind=kind),self.assertRaises(ValueError):verify_owned_mlt_project(forged)
            self.assertEqual(native.read_bytes(),original)

    @unittest.skipUnless(shutil.which("melt"),"Native Qt alpha-window renderer required")
    def test_real_source_space_mask_precedes_geometry_and_rounding_reveals_lower_layer(self):
        from studio_next.body_mlt_render import render_owned_mlt
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan,file=self._case(root)
            plan["tracks"][1]["transform"]=transform(geometry(x=32,y=0,width=32,height=48))
            for rounding in (0,1):
                plan["tracks"][1]["mask"]["keyframes"][0]["rounding"]=rounding
                file.write_text(json.dumps(plan));native=root/(str(rounding)+".mlt")
                export_owned_mlt(file,root,root/"vault",native)
                out=root/(str(rounding)+".mp4");render_owned_mlt(native,root,out)
                frame=pictures(out)[6]
                self.assertGreater(pixel(frame,40,24)[2],180)
                self.assertLess(pixel(frame,24,24)[2],30)
                self.assertLess(pixel(frame,56,24)[2],30)
                if rounding:self.assertLess(pixel(frame,33,2)[2],30)
                else:self.assertGreater(pixel(frame,33,2)[2],180)
                self.assertEqual(recover_original_mlt_plan(native,root,root/"vault")["plan"],plan)
            with patch("studio_next.body_mlt_render._require_native_transform",
                       side_effect=RuntimeError("actual cropper unavailable")):
                with self.assertRaisesRegex(RuntimeError,"cropper unavailable"):
                    render_owned_mlt(native,root,root/"untrusted.mp4")
            self.assertFalse((root/"untrusted.mp4").exists())

    @unittest.skipUnless(shutil.which("melt"),"Native masks must be tested on repeated real sources")
    def test_shared_original_has_independent_masks_and_film_time_aperture_animation(self):
        from studio_next.body_mlt_render import render_owned_mlt
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan,file=self._case(root)
            plan["tracks"][1]["transform"]=transform(geometry(width=32,height=48))
            other=copy.deepcopy(plan["tracks"][1]);other["transform"]["keyframes"][0]["x"]=32
            other["mask"]["keyframes"][0]["x"]=32
            plan["tracks"].append(other)
            file.write_text(json.dumps(plan));native=root/"shared.mlt"
            export_owned_mlt(file,root,root/"vault",native)
            out=root/"shared.mp4";render_owned_mlt(native,root,out);frame=pictures(out)[6]
            for x in (8,56):self.assertGreater(pixel(frame,x,24)[2],180)
            for x in (24,40):self.assertLess(pixel(frame,x,24)[2],30)
            plan["tracks"].pop();plan["tracks"][1].pop("transform")
            plan["tracks"][1]["mask"]={"keyframes":[aperture(width=16),aperture(frame=11,x=48,width=16)]}
            file.write_text(json.dumps(plan));native=root/"animated.mlt"
            export_owned_mlt(file,root,root/"vault",native)
            out=root/"animated.mp4";render_owned_mlt(native,root,out);frames=pictures(out)
            self.assertGreater(pixel(frames[0],8,24)[2],180)
            self.assertLess(pixel(frames[0],56,24)[2],30)
            self.assertGreater(pixel(frames[11],56,24)[2],180)
            self.assertLess(pixel(frames[11],8,24)[2],30)
            original=plan["tracks"][0]["clips"][0]
            plan["tracks"][0]["clips"]=[{**original,"end_frame":4},
                {**original,"position_frame":8,"first_frame":4,"end_frame":8}]
            file.write_text(json.dumps(plan));native=root/"masked-gap.mlt"
            export_owned_mlt(file,root,root/"vault",native)
            with self.assertRaisesRegex(ValueError,"explicit director-authored"):
                render_owned_mlt(native,root,root/"unapproved-masked-gap.mp4")
            out=root/"masked-gap.mp4";render_owned_mlt(native,root,out,gap_color="#204020")
            for expected,actual in zip((32,64,32),pixel(pictures(out)[6],2,2)):
                self.assertAlmostEqual(expected,actual,delta=18)


if __name__=="__main__":unittest.main()
