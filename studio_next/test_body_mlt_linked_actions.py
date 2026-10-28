"""Source-clock algebra proof for model-authored linked native NLE operations.

These tests never substitute invented footage for the real render acceptance:
the independent native MLT/FFmpeg suite physically verifies encoded media.
"""
import copy
import random
import unittest

from studio_next.body_mlt_linked_actions import apply_linked_editor_actions
from studio_next.body_document_schemas import validate_document,document_contract


def original_project():
    def video(name,first,end,position):
        return {"source":"zx7:sha256:"+name,"asset_id":name,
                "attestation_id":"rights-"+name,"position_frame":position,
                "first_frame":first,"end_frame":end,
                "audio":"intentional_silence"}
    def sound(first,end,position):
        return {"source":"zx7:sha256:sound","asset_id":"sound",
                "attestation_id":"rights-sound","position_frame":position,
                "first_frame":first,"end_frame":end}
    return {"frame_rate":{"numerator":12,"denominator":1},
        "frame_size":{"width":64,"height":48},
        "tracks":[
            {"clips":[video("red",0,12,0)]},
            {"clips":[video("blue",2,8,4)],
             "opacity_keyframes":[{"frame":0,"opacity":.2},
                                  {"frame":11,"opacity":.8}]}
        ],
        "audio_tracks":[{"clips":[sound(0,12,0)],
            "gain_keyframes":[{"frame":0,"gain_db":-18},
                              {"frame":11,"gain_db":0}]}]}


def time_source(plan,key,index):
    mapped={}
    for clip in plan[key][index]["clips"]:
        for offset in range(clip["end_frame"]-clip["first_frame"]):
            at=clip["position_frame"]+offset
            if at in mapped:raise AssertionError("Source overlap was invented")
            mapped[at]=(clip["asset_id"],clip["first_frame"]+offset)
    return mapped


def value_at(keys,frame,field):
    if frame<=keys[0]["frame"]:return keys[0][field]
    for a,b in zip(keys,keys[1:]):
        if frame<=b["frame"]:
            n=(frame-a["frame"])/(b["frame"]-a["frame"])
            return a[field]+(b[field]-a[field])*n
    return keys[-1][field]


def action(kind,frame,*,duration=None):
    cmd={"kind":kind,"frame":frame,"picture_tracks":[0,1],
         "audio_tracks":[0]}
    if duration is not None:
        cmd.update({"frames":duration,
                    "automation":"preserve_source_frame_values"})
    return cmd


class LinkedNativeTimelineMathTests(unittest.TestCase):
    def test_director_matte_worker_is_private_ordered_and_preserves_audio_mix(self):
        """No hidden white card and no source-track or native bus remapping."""
        import copy
        import xml.etree.ElementTree as ET
        from studio_next.body_mlt_render import _worker_art_directed_matte
        root=ET.Element("mlt",{"version":"7"})
        ET.SubElement(root,"profile")
        for i in range(3):
            ET.SubElement(root,"producer",{"id":f"p{i}"})
        for i in range(3):
            ET.SubElement(root,"playlist",{"id":f"track-{i}"})
        tractor=ET.SubElement(root,"tractor")
        mixer=ET.SubElement(tractor,"multitrack")
        for i in range(3):
            ET.SubElement(mixer,"track",{"producer":f"track-{i}"})
        for a,b in ((0,1),(0,2)):
            trans=ET.SubElement(tractor,"transition")
            ET.SubElement(trans,"property",{"name":"a_track"}).text=str(a)
            ET.SubElement(trans,"property",{"name":"b_track"}).text=str(b)
        filt=ET.SubElement(tractor,"filter")
        ET.SubElement(filt,"property",{"name":"track"}).text="2"
        before=ET.tostring(root)
        changed=_worker_art_directed_matte(
            copy.deepcopy(root),12,"#a5390f",2)
        self.assertEqual(ET.tostring(root),before)
        self.assertEqual(changed.findall("producer")[-1].get("id"),
                         "zx7-worker-directed-matte")
        props={p.get("name"):p.text for p in changed.findall(
            "producer")[-1].findall("property")}
        self.assertEqual(props["mlt_service"],"colour")
        self.assertEqual(props["resource"],"0xa5390fff")
        self.assertEqual(changed.findall("playlist")[0].get("id"),
                         "zx7-worker-matte-track")
        self.assertEqual(len(changed.findall("playlist")),4)
        self.assertEqual(len(changed.find("tractor/multitrack")),4)
        self.assertEqual(changed.find("tractor/multitrack")[0].get(
            "producer"),"zx7-worker-matte-track")
        seen=[]
        for transition in changed.findall("tractor/transition"):
            values={p.get("name"):p.text
                    for p in transition.findall("property")}
            seen.append((values["a_track"],values["b_track"]))
        self.assertEqual(seen,[("1","2"),("1","3")])
        self.assertEqual(changed.find(
            "tractor/filter/property").text,"3")
        for color in ("black","0x000000ff","#ffffff;exec",
                      "#0000",None):
            with self.subTest(color=color),self.assertRaises(ValueError):
                _worker_art_directed_matte(copy.deepcopy(root),12,color,2)
        self.assertEqual(ET.tostring(root),before)

    def test_new_native_semantic_contract_is_discoverable_without_style_templates(self):
        contract=document_contract("body.mlt_owned_revision")
        self.assertEqual(contract["input_name"],"operation")
        self.assertTrue(contract["native_source_and_semantic_preflight_required"])
        for decision in (
            {"operations":[{"op":"test","path":"/tracks/0","value":{}}]},
            {"edits":[action("blade",6)]},
            {"edits":[action("ripple_insert",6,duration=3)]},
            {"edits":[action("ripple_delete",6,duration=3)]},
        ):
            self.assertTrue(validate_document("body.mlt_owned_revision",
                                             decision,"operation"))
        for rejected in (
            {"edits":[]},
            {"edits":[{"kind":"shell","frame":5,"picture_tracks":[0],
                       "audio_tracks":[]}]},
            {"edits":[{"kind":"blade","frame":5,
                       "picture_tracks":[0],"audio_tracks":[],
                       "unsafe_plugin":"arbitrary"}]},
            {"edits":[{"kind":"ripple_delete","frame":4,
                       "frames":0,"picture_tracks":[0],
                       "audio_tracks":[],
                       "automation":"preserve_source_frame_values"}]},
        ):
            with self.subTest(decision=rejected),self.assertRaises(ValueError):
                validate_document("body.mlt_owned_revision",rejected,"operation")

    def test_linked_blade_gap_and_delete_restore_every_original_media_frame(self):
        original=original_project()
        pristine=copy.deepcopy(original)
        expected={ (key,index):time_source(original,key,index)
            for key,count in (("tracks",2),("audio_tracks",1))
            for index in range(count)}
        output,report=apply_linked_editor_actions(original,{"edits":[
            action("blade",6),action("ripple_insert",6,duration=3),
            action("ripple_delete",6,duration=3)]})
        self.assertEqual(original,pristine)
        self.assertEqual(len(report["operations"]),3)
        self.assertEqual(max(time_source(output,"tracks",0))+1,12)
        for (key,index),mapping in expected.items():
            self.assertEqual(time_source(output,key,index),mapping)
        self.assertEqual(len(output["tracks"][0]["clips"]),2)
        for key,index,prop,field in (
            ("tracks",1,"opacity_keyframes","opacity"),
            ("audio_tracks",0,"gain_keyframes","gain_db"),
        ):
            for t in expected[(key,index)]:
                self.assertAlmostEqual(
                    value_at(original[key][index][prop],t,field),
                    value_at(output[key][index][prop],t,field),
                    delta=1e-9)
        self.assertLess(report["largest_interpolated_key_rounding"],1e-9)

    def test_inserted_silence_and_picture_gap_preserve_before_and_after_clocks(self):
        plan=original_project()
        new,proof=apply_linked_editor_actions(plan,{"edits":[
            action("ripple_insert",6,duration=3)]})
        for key,index in (("tracks",0),("tracks",1),("audio_tracks",0)):
            old=time_source(plan,key,index)
            shifted={t if t<6 else t+3:sample
                     for t,sample in old.items()}
            self.assertEqual(time_source(new,key,index),shifted)
        for key,index,prop,field in (
            ("tracks",1,"opacity_keyframes","opacity"),
            ("audio_tracks",0,"gain_keyframes","gain_db")):
            for old_t in time_source(plan,key,index):
                new_t=old_t if old_t<6 else old_t+3
                self.assertAlmostEqual(
                    value_at(plan[key][index][prop],old_t,field),
                    value_at(new[key][index][prop],new_t,field),
                    delta=1e-9)
        self.assertEqual(len(proof["operations"]),1)
        self.assertFalse(proof["native_renderer_precision_and_artistic_fidelity_approved"])

    def test_delete_source_interval_only_removes_author_selected_source_frames(self):
        before=original_project()
        after,_=apply_linked_editor_actions(before,{"edits":[
            action("ripple_delete",4,duration=3)]})
        for key,index in (("tracks",0),("tracks",1),("audio_tracks",0)):
            old=time_source(before,key,index)
            expected={t if t<4 else t-3:src for t,src in old.items()
                      if not 4<=t<7}
            self.assertEqual(time_source(after,key,index),expected)
        for key,index,prop,field in (
            ("tracks",1,"opacity_keyframes","opacity"),
            ("audio_tracks",0,"gain_keyframes","gain_db")):
            for old_t in time_source(before,key,index):
                if 4<=old_t<7:continue
                new_t=old_t if old_t<4 else old_t-3
                self.assertAlmostEqual(
                    value_at(before[key][index][prop],old_t,field),
                    value_at(after[key][index][prop],new_t,field),
                    delta=1e-9)

    def test_thousands_of_independent_animator_curves_keep_exact_surviving_source_values(self):
        """Adversarial source-to-timeline property test of keyframe boundaries.

        No aesthetic/speed/gain defaults are supplied: each run has different
        authored curves and different source frame edit positions.
        """
        rng=random.Random(20261028)
        checked=0
        for case in range(1400):
            plan=original_project()
            # Give both picture and soundtrack full underlying frame ranges.
            upper=plan["tracks"][1]["clips"][0]
            upper["position_frame"]=0
            upper["first_frame"]=0
            upper["end_frame"]=12
            sound=plan["audio_tracks"][0]["clips"][0]
            sound["position_frame"]=0
            sound["first_frame"]=0
            sound["end_frame"]=12
            for track,prop,field,low,high in (
                (plan["tracks"][1],"opacity_keyframes","opacity",0.0,1.0),
                (plan["audio_tracks"][0],"gain_keyframes","gain_db",-90.0,20.0)):
                authored_frames=[0]+sorted(rng.sample(range(1,12),
                                              rng.randrange(1,8)))
                track[prop]=[{"frame":frame,field:rng.uniform(low,high)}
                              for frame in authored_frames]
            kind=rng.choice(("ripple_insert","ripple_delete"))
            at=rng.randrange(0,11)
            # Preserve at least one genuine source frame on every selected
            # native track; deleting the entire picture is correctly refused.
            amount=rng.randrange(1,12-at)
            revised,details=apply_linked_editor_actions(plan,{
                "edits":[action(kind,at,duration=amount)]})
            self.assertEqual(len(details["operations"]),1)
            for key,ind in (("tracks",0),("tracks",1),("audio_tracks",0)):
                original=time_source(plan,key,ind)
                expected={}
                for t,src in original.items():
                    if kind=="ripple_delete" and at<=t<at+amount:
                        continue
                    mapped=t if t<at else (
                        t+amount if kind=="ripple_insert" else t-amount)
                    expected[mapped]=src
                self.assertEqual(time_source(revised,key,ind),expected,
                                 msg=(case,kind,at,amount,key,ind))
            for key,ind,prop,field in (
                ("tracks",1,"opacity_keyframes","opacity"),
                ("audio_tracks",0,"gain_keyframes","gain_db")):
                previous=plan[key][ind][prop]
                updated=revised[key][ind]
                if prop in updated:
                    new_curve=updated[prop]
                    self.assertGreaterEqual(len(new_curve),2)
                    self.assertEqual(new_curve[0]["frame"],0)
                    self.assertEqual([x["frame"] for x in new_curve],
                                     sorted({x["frame"] for x in new_curve}))
                for old_t in time_source(plan,key,ind):
                    if kind=="ripple_delete" and at<=old_t<at+amount:
                        continue
                    new_t=old_t if old_t<at else (
                        old_t+amount if kind=="ripple_insert" else old_t-amount)
                    actual=(value_at(updated[prop],new_t,field)
                            if prop in updated else updated.get(
                                field,1 if key=="tracks" else 0))
                    expected=value_at(previous,old_t,field)
                    self.assertAlmostEqual(expected,actual,delta=1e-8,
                        msg=(case,kind,at,amount,key,old_t,expected,actual))
                    checked+=1
        self.assertGreater(checked,20000)

    def test_reject_unsafe_blades_selectors_metadata_and_entire_track_erasure(self):
        prior=original_project()
        exact=copy.deepcopy(prior)
        errors=[
            {"kind":"blade","frame":0,"picture_tracks":[0],"audio_tracks":[]},
            {"kind":"blade","frame":5,"picture_tracks":[0,0],"audio_tracks":[]},
            {"kind":"blade","frame":5,"picture_tracks":[1,0],"audio_tracks":[]},
            {"kind":"blade","frame":5,"picture_tracks":[7],"audio_tracks":[]},
            {"kind":"blade","frame":5,"picture_tracks":[],"audio_tracks":[]},
            {"kind":"blade","frame":True,"picture_tracks":[0],"audio_tracks":[]},
            {"kind":"blade","frame":13,"picture_tracks":[0],"audio_tracks":[]},
            {"kind":"ripple_insert","frame":6,"frames":0,
             "picture_tracks":[0],"audio_tracks":[],
             "automation":"preserve_source_frame_values"},
            {"kind":"ripple_delete","frame":10,"frames":8,
             "picture_tracks":[0],"audio_tracks":[],
             "automation":"preserve_source_frame_values"},
            {"kind":"ripple_delete","frame":0,"frames":12,
             "picture_tracks":[0],"audio_tracks":[],
             "automation":"preserve_source_frame_values"},
            {"kind":"ripple_insert","frame":5,"frames":2,
             "picture_tracks":[0],"audio_tracks":[],
             "automation":"silently_discard_artist_keyframes"},
            {"kind":"ripple_insert","frame":5,"frames":2,
             "picture_tracks":[0],"audio_tracks":[],"unexpected":True,
             "automation":"preserve_source_frame_values"},
        ]
        for problem in errors:
            with self.subTest(error=problem),self.assertRaises(ValueError):
                apply_linked_editor_actions(prior,{"edits":[problem]})
            self.assertEqual(prior,exact)

    def test_deterministic_property_check_blade_insert_delete_is_source_reversible(self):
        rng=random.Random(0x7A7)
        for case in range(128):
            first=rng.randrange(1,11)
            gap=rng.randrange(1,12)
            before=original_project()
            original={ (key,index):time_source(before,key,index)
                for key,count in (("tracks",2),("audio_tracks",1))
                for index in range(count)}
            cmds=[action("ripple_insert",first,duration=gap),
                  action("ripple_delete",first,duration=gap)]
            after,proof=apply_linked_editor_actions(before,{"edits":cmds})
            for k,expected in original.items():
                self.assertEqual(time_source(after,*k),expected,
                                 msg=(case,k,first,gap))
            for key,index,prop,field in (
                    ("tracks",1,"opacity_keyframes","opacity"),
                    ("audio_tracks",0,"gain_keyframes","gain_db")):
                for f in original[(key,index)]:
                    self.assertAlmostEqual(
                        value_at(before[key][index][prop],f,field),
                        value_at(after[key][index][prop],f,field),
                        delta=1e-9,msg=(case,key,first,gap))
            self.assertLess(proof["largest_interpolated_key_rounding"],1e-9)


if __name__=="__main__":
    unittest.main()
