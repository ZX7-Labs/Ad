"""Real native geometry, alpha isolation, reversible edits and hostile XML."""
import copy
import json
import math
import random
import shutil
import subprocess
import tempfile
import unittest
from array import array
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from studio_next.body_document_schemas import validate_document,document_contract
from studio_next.body_mlt_editor import export_owned_mlt,verify_owned_mlt_project,validate_mlt_edit
from studio_next.body_mlt_roundtrip import recover_original_mlt_plan
from studio_next.body_mlt_transform import encode_transform,decode_transform,TRANSFORM_FIELDS
from studio_next.body_mlt_linked_actions import apply_linked_editor_actions
from studio_next import test_body_mlt_editor as original_fixtures
from studio_next.test_body_mlt_linked_actions import original_project,value_at,action,time_source


def geometry(**values):
    return {"frame":0,"x":0,"y":0,"width":32,"height":24,
            "rotation_degrees":0,**values}


def transform(*keys,aspect="distort"):
    return {"aspect":aspect,"keyframes":list(keys or [geometry()])}


def props(node):
    return {p.get("name"):p.text for p in node.findall("property")}


def pictures(file,frames=12):
    raw=subprocess.check_output(["ffmpeg","-v","error","-nostdin","-xerror",
        "-i",str(file),"-f","rawvideo","-pix_fmt","rgb24","-"],timeout=60)
    if len(raw)!=frames*64*48*3:raise AssertionError("Decoded native frame count changed")
    return [raw[i:i+64*48*3] for i in range(0,len(raw),64*48*3)]


def pixel(frame,x,y):
    return tuple(frame[(y*64+x)*3:(y*64+x)*3+3])


class NativeTransformMathTests(unittest.TestCase):
    def test_typed_geometry_full_float_precision_and_hostile_native_rejection(self):
        authored=transform(geometry(x=-.12345678901234568,
            rotation_degrees=32.123456789012344),geometry(frame=11,x=32,y=24))
        encoded={"track":"1",**encode_transform(authored,12)}
        self.assertEqual(decode_transform(encoded,12),authored)
        for field,value in (("x",True),("y","3;exec"),("width",0),
                            ("height",math.inf),("rotation_degrees",math.nan)):
            bad=transform(geometry(**{field:value}))
            with self.subTest(field=field),self.assertRaises(ValueError):
                encode_transform(bad,12)
        for bad in (transform(geometry(frame=1)),
                    transform(geometry(),geometry(frame=0)),
                    transform(geometry(),geometry(frame=12)),
                    transform(geometry(width=16384,height=16384)),
                    transform(geometry(width=16384,height=4096),
                              geometry(frame=11,width=4096,height=16384)),
                    transform(geometry(x=10**1000)),
                    transform(geometry(),aspect="crop"),
                    {**authored,"background":"https://invalid/execute"}):
            with self.subTest(bad=bad),self.assertRaises(ValueError):encode_transform(bad,12)
        for name,value in (("background_color","/tmp/payload.mlt"),
                           ("rect","0=0 0 32 24 1;11~=32 24 32 24 1"),
                           ("rect","0=0 0 32 24 0.5"),
                           ("rotation","0=nan;11=0"),
                           ("rotation","0=0;10=0"),
                           ("distort","2"),
                           ("producer.resource","/etc/passwd")):
            with self.subTest(native=name),self.assertRaises(ValueError):
                decode_transform({**encoded,name:value},12)

    def test_discovery_exposes_editable_geometry_without_native_expressions(self):
        plan=original_project()
        plan.pop("audio_tracks")
        plan["tracks"][1]["transform"]=transform(geometry())
        self.assertTrue(validate_document("body.mlt_owned_export",plan))
        schema=document_contract("body.mlt_owned_export")["json_schema"]
        self.assertIn("transform",schema["properties"]["tracks"]["items"]["properties"])
        plan["tracks"][1]["transform"]["background"]="shell"
        with self.assertRaises(ValueError):validate_document("body.mlt_owned_export",plan)

    def test_200_arbitrary_curves_preserve_all_geometry_at_surviving_source_frames(self):
        rng=random.Random(721035)
        for case in range(200):
            plan=original_project()
            plan["tracks"][1].pop("opacity_keyframes")
            positions=[0]+sorted(rng.sample(range(1,12),rng.randrange(1,6)))
            plan["tracks"][1]["clips"][0].update(first_frame=0,end_frame=12,position_frame=0)
            curve=[geometry(frame=f,x=rng.uniform(-32,64),y=rng.uniform(-24,48),
                width=rng.uniform(1,128),height=rng.uniform(1,96),
                rotation_degrees=rng.uniform(-360,360)) for f in positions]
            plan["tracks"][1]["transform"]=transform(*curve)
            pristine=copy.deepcopy(plan)
            at=rng.randrange(0,11);amount=rng.randrange(1,8)
            for kind in ("ripple_insert","ripple_delete"):
                count=amount if kind=="ripple_insert" else min(amount,11-at)
                out,report=apply_linked_editor_actions(plan,{"edits":[action(kind,at,duration=count)]})
                new=out["tracks"][1]["transform"]["keyframes"]
                for old_frame in range(12):
                    if kind=="ripple_insert":now=old_frame+(count if old_frame>=at else 0)
                    else:
                        if at<=old_frame<at+count:continue
                        now=old_frame-(count if old_frame>=at+count else 0)
                    for field in TRANSFORM_FIELDS:
                        self.assertAlmostEqual(value_at(curve,old_frame,field),
                            value_at(new,now,field),delta=1e-9,
                            msg=str((case,kind,at,count,old_frame,field)))
                self.assertEqual(report["largest_interpolated_key_rounding"],0)
            self.assertEqual(plan,pristine)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"Real media custody needs decoders")
class NativeTransformProjectTests(unittest.TestCase):
    def _case(self,root):
        plan,file=original_fixtures.VerifiedMLTEditorialTests()._case(root)
        plan["tracks"][1]["transform"]=transform(geometry(x=-.12345678901234568),
            geometry(frame=11,x=32,y=24,rotation_degrees=90))
        file.write_text(json.dumps(plan))
        edit=root/"original.mlt"
        export_owned_mlt(file,root,root/"vault",edit)
        return plan,file,edit

    def test_source_verified_roundtrip_revision_comparison_and_original_bytes(self):
        from studio_next.body_mlt_revision import revise_owned_mlt_project
        from studio_next.body_mlt_compare import compare_owned_mlt_projects
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan,file,edit=self._case(root)
            old=edit.read_bytes()
            self.assertEqual(recover_original_mlt_plan(edit,root,root/"vault")["plan"],plan)
            change=root/"change.json"
            change.write_text(json.dumps({"operations":[{"op":"replace",
                "path":"/tracks/1/transform/keyframes/0/x","value":7}]}))
            target=root/"revised.mlt"
            result=revise_owned_mlt_project(edit,change,root,root/"vault",target)
            self.assertTrue(result["lossless_typed_native_roundtrip"])
            recovered=recover_original_mlt_plan(target,root,root/"vault")["plan"]
            self.assertEqual(recovered["tracks"][1]["transform"]["keyframes"][0]["x"],7)
            review=compare_owned_mlt_projects(edit,target,root,root/"vault",focus="picture:1")
            change=review["selected_track"]["change"]
            self.assertEqual(change["source_frame_spans"],[])
            self.assertIn("transform",change["native_track_controls"]["after"])
            self.assertEqual(edit.read_bytes(),old)
            # Reversibility is an exact preserved original, without mutating it.
            self.assertEqual(recover_original_mlt_plan(edit,root,root/"vault")["plan"],plan)

    def test_native_xml_rejects_reordered_duplicate_or_untrusted_transform_services(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan,file,edit=self._case(root)
            original=edit.read_bytes()
            for kind in ("background","late","duplicate","bottom","resource","clock","rotation"):
                xml=ET.fromstring(original);tractor=xml.find("tractor");filt=tractor.find("filter")
                nodes={p.get("name"):p for p in filt.findall("property")}
                if kind=="background":nodes["background_color"].text="avformat:/etc/passwd"
                elif kind=="late":tractor.remove(filt);tractor.append(filt)
                elif kind=="duplicate":tractor.insert(1,copy.deepcopy(filt))
                elif kind=="bottom":nodes["track"].text="0"
                elif kind=="resource":ET.SubElement(filt,"property",{"name":"producer.resource"}).text="/tmp/media"
                elif kind=="clock":nodes["rect"].text="0=0 0 32 24 1;12=32 24 32 24 1"
                elif kind=="rotation":nodes["rotation"].text="0=0;11=nan"
                forged=root/(kind+".mlt");forged.write_bytes(ET.tostring(xml))
                with self.subTest(kind=kind),self.assertRaises(ValueError):verify_owned_mlt_project(forged)
            bad=copy.deepcopy(plan);bad["tracks"][0]["transform"]=transform(geometry())
            with self.assertRaisesRegex(ValueError,"bottom"):validate_mlt_edit(bad,root,root/"vault")
            self.assertEqual(edit.read_bytes(),original)

    @unittest.skipUnless(shutil.which("melt"),"Actual native MLT geometry required")
    def test_delayed_cut_geometry_uses_film_clock_and_real_transparent_layer_pixels(self):
        from studio_next.body_mlt_render import render_owned_mlt
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan,file,edit=self._case(root)
            # Original source frames 2..7 begin at film frame 4. Transform
            # moves on the film clock, independent of the trimmed source clock.
            plan["tracks"][1]["transform"]=transform(geometry(),geometry(frame=11,x=32,y=24))
            file.write_text(json.dumps(plan));native=root/"moving.mlt"
            export_owned_mlt(file,root,root/"vault",native)
            original=native.read_bytes()
            out=root/"moving.mp4";render_owned_mlt(native,root,out)
            frames=pictures(out)
            for index in (0,3,10,11):
                self.assertGreater(pixel(frames[index],32,24)[0],200)
            for index in range(4,10):
                x=round(32*index/11)+12;y=round(24*index/11)+10
                self.assertGreater(pixel(frames[index],x,y)[2],180,(index,x,y))
                self.assertGreater(pixel(frames[index],2,2)[0],200)
            with patch("studio_next.body_mlt_render._require_native_transform",
                       side_effect=RuntimeError("native transform unavailable")):
                with self.assertRaisesRegex(RuntimeError,"transform unavailable"):
                    render_owned_mlt(native,root,root/"untrusted.mp4")
            self.assertFalse((root/"untrusted.mp4").exists())
            self.assertEqual(native.read_bytes(),original)

    @unittest.skipUnless(shutil.which("melt"),"Actual native MLT geometry required")
    def test_aspect_fit_negative_coordinates_and_native_load_failure_are_physically_verified(self):
        from studio_next.body_mlt_render import render_owned_mlt
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan,file=original_fixtures.VerifiedMLTEditorialTests()._case(root)
            plan["tracks"][1]["clips"][0].update(position_frame=0,first_frame=0,end_frame=12)
            for aspect in ("preserve","distort"):
                plan["tracks"][1]["transform"]=transform(geometry(x=8,y=8,width=24,height=24),aspect=aspect)
                file.write_text(json.dumps(plan));native=root/(aspect+".mlt")
                export_owned_mlt(file,root,root/"vault",native)
                out=root/(aspect+".mp4");render_owned_mlt(native,root,out)
                frame=pictures(out)[0]
                self.assertGreater(pixel(frame,20,20)[2],180)
                # 4:3 original fits centered into a square: top/bottom margins
                # are transparent. Distort explicitly stretches to fill.
                if aspect=="preserve":self.assertLess(pixel(frame,20,9)[2],30)
                else:self.assertGreater(pixel(frame,20,9)[2],180)
            plan["tracks"][1]["transform"]=transform(geometry(x=-16,y=-12))
            file.write_text(json.dumps(plan));native=root/"offscreen.mlt"
            export_owned_mlt(file,root,root/"vault",native)
            out=root/"offscreen.mp4";render_owned_mlt(native,root,out)
            frame=pictures(out)[0]
            self.assertGreater(pixel(frame,4,4)[2],180)
            self.assertLess(pixel(frame,24,20)[2],30)
            actual_run=subprocess.run
            def missing_service(cmd,*args,**kwargs):
                if cmd[0]=="melt" and "-consumer" in cmd:
                    return subprocess.CompletedProcess(cmd,0,"",'[producer_xml] failed to load filter "qtblend"')
                return actual_run(cmd,*args,**kwargs)
            with patch("studio_next.body_mlt_render.subprocess.run",side_effect=missing_service):
                with self.assertRaisesRegex(RuntimeError,"did not load an authored service"):
                    render_owned_mlt(native,root,root/"inert-service.mp4")
            self.assertFalse((root/"inert-service.mp4").exists())

    @unittest.skipUnless(shutil.which("melt"),"Actual MLT Qt transform plus Cairo blending required")
    def test_three_layers_geometry_blend_and_rotation_change_only_the_authored_upper_picture(self):
        from studio_next.media_vault import MediaVault
        from studio_next.body_mlt_render import render_owned_mlt
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan,file=original_fixtures.VerifiedMLTEditorialTests()._case(root)
            plan["tracks"][1]["clips"][0].update(position_frame=0,first_frame=0,end_frame=12)
            plan["tracks"][1].update(opacity=.5,transform=transform(geometry(x=8,y=8,width=24,height=12)))
            plan["tracks"][1]["mask"]={"keyframes":[{
                "frame":0,"x":0,"y":0,"width":64,"height":48,"rounding":1}]}
            green=root/"green.mp4";original_fixtures._movie(green,"lime")
            rec=MediaVault(root/"vault").ingest(green,mime="video/mp4",rights="owner_supplied",
                source_type="owner_upload",source_id="green-fixture",evidence="FFmpeg generated fixture",
                owner_or_generator="test")
            clip={**plan["tracks"][1]["clips"][0],"asset_id":rec["asset_id"],
                  "attestation_id":rec["attestation_id"],"source":"zx7:sha256:"+rec["asset_id"]}
            plan["tracks"].append({"clips":[clip],"transform":transform(geometry(x=40,y=28,width=16,height=12))})
            sound=root/"stereo.wav"
            subprocess.run(["ffmpeg","-v","error","-nostdin","-f","lavfi","-i",
                "sine=frequency=620:sample_rate=48000:duration=1","-ac","2",
                "-c:a","pcm_s16le",str(sound)],check=True,timeout=30)
            rec=MediaVault(root/"vault").ingest(sound,mime="audio/wav",rights="owner_supplied",
                source_type="owner_upload",source_id="stereo-fixture",evidence="FFmpeg generated PCM",
                owner_or_generator="test")
            audio={"source":"zx7:sha256:"+rec["asset_id"],"asset_id":rec["asset_id"],
                "attestation_id":rec["attestation_id"],"position_frame":0,"first_frame":0,"end_frame":12}
            plan["audio_tracks"]=[{"clips":[dict(audio)],"pan":0,"gain_db":0},
                                  {"clips":[dict(audio)],"pan":1,"gain_db":-6}]
            previous_levels=None
            for angle in (0,90):
                plan["tracks"][1]["transform"]["keyframes"][0]["rotation_degrees"]=angle
                file.write_text(json.dumps(plan));native=root/(str(angle)+".mlt")
                export_owned_mlt(file,root,root/"vault",native)
                out=root/(str(angle)+".mp4");render_owned_mlt(native,root,out)
                frame=pictures(out)[6]
                self.assertGreater(pixel(frame,48,34)[1],180) # independent green layer
                self.assertGreater(pixel(frame,2,2)[0],200) # unchanged bottom red
                center=pixel(frame,20,14)
                self.assertGreater(center[0],90,(angle,center))
                self.assertGreater(center[2],90,(angle,center))
                # A 24x12 rectangle rotates around (20,14): side and top swap.
                inside=(11,14) if angle==0 else (20,5)
                outside=(20,5) if angle==0 else (11,14)
                self.assertGreater(pixel(frame,*inside)[2],80,(angle,inside))
                self.assertLess(pixel(frame,*outside)[2],30,(angle,outside))
                self.assertEqual(recover_original_mlt_plan(native,root,root/"vault")["plan"],plan)
                pcm=array("f",subprocess.check_output(["ffmpeg","-v","error","-i",str(out),
                    "-vn","-f","f32le","-acodec","pcm_f32le","-ar","48000","-ac","2","-"],timeout=60))
                levels=[math.sqrt(sum(v*v for v in pcm[19200+ch:67200:2])/24000) for ch in (0,1)]
                self.assertGreater(levels[0],.02)
                self.assertGreater(levels[1]/levels[0],.4)
                self.assertLess(levels[1]/levels[0],.6)
                if previous_levels:
                    for prior,current in zip(previous_levels,levels):
                        self.assertAlmostEqual(prior,current,delta=.002)
                previous_levels=levels

    @unittest.skipUnless(shutil.which("melt"),"Actual native Qt geometry and source-frame ripple required")
    def test_registry_ripple_preserves_physical_geometry_with_private_matte_and_undo(self):
        from studio_next.body_integration import body_catalog
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan,file=original_fixtures.VerifiedMLTEditorialTests()._case(root)
            plan["tracks"][1]["clips"][0].update(position_frame=0,first_frame=0,end_frame=12)
            plan["tracks"][1]["transform"]=transform(geometry(width=16,height=12),
                geometry(frame=11,x=32,y=24,width=24,height=12,rotation_degrees=90))
            file.write_text(json.dumps(plan));body=body_catalog(root)
            def run(tool,**args):return body.invoke(tool,args,allowed_access={"write"})
            run("body.mlt_owned_export",plan=file.name,out="before.mlt")
            prior=(root/"before.mlt").read_bytes()
            run("body.mlt_owned_render",edit="before.mlt",out="before.mp4")
            before=pictures(root/"before.mp4")
            change=root/"ripple.json"
            cmd=action("ripple_insert",5,duration=2);cmd["audio_tracks"]=[]
            change.write_text(json.dumps({"edits":[cmd]}))
            run("body.mlt_owned_revision",edit="before.mlt",operation=change.name,out="after.mlt")
            run("body.mlt_owned_render",edit="after.mlt",out="after.mp4",gap_color="#000000")
            after=pictures(root/"after.mp4",14)
            for at,original in enumerate(before):
                actual=after[at if at<5 else at+2]
                errors=[abs(a-b) for a,b in zip(actual,original)]
                self.assertLess(sum(errors)/len(errors),3,(at,"average codec difference"))
                self.assertLess(sum(e>18 for e in errors)/len(errors),.03,(at,"geometry changed"))
            self.assertLess(max(after[5]),18);self.assertLess(max(after[6]),18)
            cmd["kind"]="ripple_delete";change=root/"undo.json"
            change.write_text(json.dumps({"edits":[cmd]}))
            run("body.mlt_owned_revision",edit="after.mlt",operation=change.name,out="undo.mlt")
            restored=recover_original_mlt_plan(root/"undo.mlt",root,root/"vault")["plan"]
            self.assertEqual(time_source(restored,"tracks",1),time_source(plan,"tracks",1))
            curve=restored["tracks"][1]["transform"]["keyframes"]
            for t in range(12):
                for field in TRANSFORM_FIELDS:
                    self.assertAlmostEqual(value_at(curve,t,field),value_at(
                        plan["tracks"][1]["transform"]["keyframes"],t,field),delta=1e-9)
            self.assertEqual((root/"before.mlt").read_bytes(),prior)

    @unittest.skipUnless(shutil.which("melt"),"Native transparent compositing over authored backing required")
    def test_active_transparent_picture_over_bottom_gap_requires_and_renders_authored_backing(self):
        from studio_next.body_mlt_render import render_owned_mlt
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan,file=original_fixtures.VerifiedMLTEditorialTests()._case(root)
            original=plan["tracks"][0]["clips"][0]
            plan["tracks"][0]["clips"]=[{**original,"end_frame":4},
                {**original,"position_frame":8,"first_frame":4,"end_frame":8}]
            plan["tracks"][1]["transform"]=transform(geometry(x=16,y=12,width=32,height=24))
            plan["tracks"][1]["opacity"]=.5
            file.write_text(json.dumps(plan));native=root/"alpha-gap.mlt"
            export_owned_mlt(file,root,root/"vault",native);preserved=native.read_bytes()
            with self.assertRaisesRegex(ValueError,"explicit director-authored"):
                render_owned_mlt(native,root,root/"unapproved-background.mp4")
            out=root/"approved-background.mp4"
            report=render_owned_mlt(native,root,out,gap_color="#204020")
            self.assertTrue(report["authored_transparent_backing_applied"])
            self.assertEqual(report["uncovered_picture_intervals_detected"],0)
            frame=pictures(out)[6]
            for desired,actual in zip((32,64,32),pixel(frame,2,2)):
                self.assertAlmostEqual(desired,actual,delta=18)
            center=pixel(frame,32,24)
            self.assertGreater(center[2],100);self.assertLess(center[1],50)
            self.assertGreater(pixel(pictures(out)[2],2,2)[0],200)
            self.assertEqual(native.read_bytes(),preserved)


if __name__=="__main__":unittest.main()
