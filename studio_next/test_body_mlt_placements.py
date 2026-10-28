"""Falsifiable source-custody, atomicity and frame placement invariants.

These are pure semantic checks; real FFmpeg/MLT output is separately measured
by the project's native renderer gate. No fixed creative cut or styling policy.
"""
import copy
import random
import unittest

from studio_next.body_mlt_placements import apply_native_source_placements
from studio_next.body_mlt_linked_actions import apply_linked_editor_actions
from studio_next.body_document_schemas import validate_document, document_contract


def clip(name,first,last,position,sound=False):
    item={"source":"zx7:sha256:"+name,"asset_id":name,
          "attestation_id":"owner-rights-"+name,
          "first_frame":first,"end_frame":last,
          "position_frame":position}
    if not sound:
        item["audio"]="intentional_silence"
    return item


def sample():
    return {"frame_rate":{"numerator":12,"denominator":1},
            "frame_size":{"width":64,"height":48},
            "tracks":[
                {"clips":[clip("red",0,3,0),clip("blue",3,7,4)],
                 "opacity_keyframes":[{"frame":0,"opacity":.3},
                                      {"frame":11,"opacity":.8}]},
                {"clips":[clip("green",0,4,0),clip("yellow",4,8,4)],
                 "blend_mode":"multiply"}],
            "audio_tracks":[
                {"clips":[clip("sound1",0,4,0,True),
                          clip("sound1",4,8,4,True)],
                 "gain_keyframes":[{"frame":0,"gain_db":-19},
                                   {"frame":11,"gain_db":-2}]},
                {"clips":[clip("sound2",0,4,0,True),
                          clip("sound2",4,8,4,True)],
                 "gain_db":-3}]}


def placement(domain,fi,ci,ti,when):
    return {"domain":domain,"from_track":fi,"clip":ci,
            "to_track":ti,"at_frame":when}


def action(*moves):
    return {"kind":"place","placements":list(moves),
            "effects":"inherit_destination_track_at_film_time"}


def source_labels(plan,key):
    return sorted((c["asset_id"],c["source"],c["attestation_id"],
                   c["first_frame"],c["end_frame"])
                  for t in plan.get(key,[]) for c in t["clips"])


class NativeAtomicSourcePlacementsTests(unittest.TestCase):
    def test_model_can_discover_authorized_atomic_picture_sound_move(self):
        contract=document_contract("body.mlt_owned_revision")
        self.assertEqual(contract["input_name"],"operation")
        d={"edits":[action(
            placement("picture",0,1,1,8),
            placement("sound",0,1,1,8))]}
        self.assertTrue(validate_document("body.mlt_owned_revision",d,"operation"))
        for bad in (
            {"edits":[action(placement("executable",0,1,1,8))]},
            {"edits":[action(placement("picture",0,1,1,True))]},
            {"edits":[action(placement("picture",0,1,1,8))|{
                "effects":"execute_frei0r"}]},
            {"edits":[action(placement("picture",0,1,1,8))|{
                "arbitrary_mlt_xml":"not allowed"}]},
            {"edits":[{"kind":"place","placements":[],"effects":
                       "inherit_destination_track_at_film_time"}]},
        ):
            with self.subTest(decision=bad),self.assertRaises(ValueError):
                validate_document("body.mlt_owned_revision",bad,"operation")

    def test_grouped_move_is_atomic_source_exact_and_inherits_destination_effects(self):
        original=sample()
        old=copy.deepcopy(original)
        action1=action(placement("picture",0,1,1,8),
                       placement("sound",0,1,1,8))
        revised,proof=apply_native_source_placements(original,action1)
        self.assertEqual(original,old)
        self.assertEqual(source_labels(revised,"tracks"),
                         source_labels(original,"tracks"))
        self.assertEqual(source_labels(revised,"audio_tracks"),
                         source_labels(original,"audio_tracks"))
        self.assertEqual(len(proof["placements"]),2)
        self.assertFalse(proof["professional_or_artistic_quality_certified"])
        self.assertTrue(proof["full_native_and_physical_reverification_required"])
        self.assertEqual(revised["tracks"][1]["blend_mode"],"multiply")
        self.assertEqual(revised["audio_tracks"][1]["gain_db"],-3)
        self.assertEqual(revised["tracks"][0]["opacity_keyframes"],
                         original["tracks"][0]["opacity_keyframes"])
        self.assertEqual(revised["audio_tracks"][0]["gain_keyframes"],
                         original["audio_tracks"][0]["gain_keyframes"])
        self.assertEqual([c["position_frame"] for c in revised["tracks"][1]["clips"]],
                         [0,4,8])
        self.assertEqual([c["position_frame"] for c in revised["audio_tracks"][1]["clips"]],
                         [0,4,8])
        undone,back=apply_native_source_placements(revised,action(
            placement("picture",1,2,0,4),placement("sound",1,2,0,4)))
        self.assertEqual(undone,original)
        self.assertEqual(len(back["placements"]),2)

    def test_simultaneous_swap_is_legal_without_transient_overlaps(self):
        before=sample()
        action1=action(placement("picture",0,1,1,4),
                       placement("picture",1,1,0,4),
                       placement("sound",0,1,1,4),
                       placement("sound",1,1,0,4))
        after,proof=apply_native_source_placements(before,action1)
        self.assertEqual(len(proof["placements"]),4)
        self.assertEqual(after["tracks"][0]["clips"][1]["asset_id"],"yellow")
        self.assertEqual(after["tracks"][1]["clips"][1]["asset_id"],"blue")
        self.assertEqual(after["audio_tracks"][0]["clips"][1]["asset_id"],"sound2")
        self.assertEqual(after["audio_tracks"][1]["clips"][1]["asset_id"],"sound1")
        reversed_plan,_=apply_native_source_placements(after,action1)
        self.assertEqual(reversed_plan,before)
        composed,_=apply_linked_editor_actions(before,{"edits":[action1]})
        self.assertEqual(composed,after)

    def test_rejects_all_overlaps_duplicates_collisions_and_erasure(self):
        original=sample()
        pristine=copy.deepcopy(original)
        problems=[
            action(placement("picture",0,1,1,2)),
            action(placement("sound",0,1,1,3)),
            action(placement("picture",0,1,1,1000000)),
            action(placement("picture",0,1,9,8)),
            action(placement("picture",0,4,1,8)),
            action(placement("picture",0,1,0,4)),
            action(placement("picture",0,1,1,8),
                   placement("picture",0,1,1,10)),
            action(placement("picture",0,0,1,8),
                   placement("picture",0,1,1,12)),
            action(placement("picture",0,1,1,8),
                   placement("picture",1,1,1,8)),
            action(placement("sound",0,1,1,8),
                   placement("sound",1,1,1,8)),
            action({"domain":"picture","from_track":0,"clip":1,
                    "to_track":1,"at_frame":"8;exec shell"}),
        ]
        for invalid in problems:
            with self.subTest(rejected=invalid),self.assertRaises(ValueError):
                apply_native_source_placements(original,invalid)
            self.assertEqual(original,pristine)
        no_other=sample()
        no_other["tracks"][0]["clips"]=no_other["tracks"][0]["clips"][:1]
        with self.assertRaisesRegex(ValueError,"erase"):
            apply_native_source_placements(no_other,
                action(placement("picture",0,0,1,8)))
        with self.assertRaises(ValueError):
            apply_native_source_placements(original,
                {"kind":"place","placements":[
                    placement("picture",0,1,1,8)],
                 "effects":"guess_artist_effect_routing"})

    def test_randomized_exact_source_placement_inverse(self):
        rng=random.Random(71829)
        for case in range(500):
            before=sample()
            a=rng.choice((0,1))
            b=1-a
            # Place the second original clip on the opposing track beyond
            # that track's existing end. A real original remains on source.
            at=rng.randrange(8,500)
            operation=action(placement("picture",a,1,b,at),
                             placement("sound",a,1,b,at))
            revised,_=apply_native_source_placements(before,operation)
            self.assertEqual(source_labels(revised,"tracks"),
                             source_labels(before,"tracks"),
                             msg=case)
            self.assertEqual(source_labels(revised,"audio_tracks"),
                             source_labels(before,"audio_tracks"),
                             msg=case)
            undo=action(placement("picture",b,2,a,4),
                        placement("sound",b,2,a,4))
            restored,_=apply_native_source_placements(revised,undo)
            self.assertEqual(restored,before,msg=(case,a,b,at))


if __name__=="__main__":
    unittest.main()
