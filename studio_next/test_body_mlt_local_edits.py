"""Falsifiable frame-exact roll/slip/slide NLE algebra over immutable media."""
import copy
import random
import unittest

from studio_next.body_mlt_local_edits import apply_local_window_action
from studio_next.body_mlt_linked_actions import apply_linked_editor_actions
from studio_next.body_document_schemas import validate_document


def _source(name,first,end,position,*,sound=False):
    base={"source":"zx7:sha256:"+name,"asset_id":name,
          "attestation_id":"owner-rights-"+name,
          "position_frame":position,"first_frame":first,
          "end_frame":end}
    if not sound:
        base["audio"]="intentional_silence"
    return base


def _project():
    return {
        "frame_rate":{"numerator":12,"denominator":1},
        "frame_size":{"width":64,"height":48},
        "tracks":[{
            "clips":[_source("red",2,5,0),_source("blue",4,7,3),
                     _source("red",6,12,6)],
            "opacity_keyframes":[{"frame":0,"opacity":.5},
                                 {"frame":11,"opacity":.9}]},
            {"clips":[_source("red",2,5,0),_source("blue",4,7,3),
                      _source("red",6,12,6)],"blend_mode":"multiply"}],
        "audio_tracks":[{
            "clips":[_source("sound",2,5,0,sound=True),
                     _source("sound",4,7,3,sound=True),
                     _source("sound",6,12,6,sound=True)],
            "gain_keyframes":[{"frame":0,"gain_db":-24},
                              {"frame":11,"gain_db":-4}]}]}


def _action(kind,delta,*,picture=None,audio=None):
    if picture is None:picture=[{"track":0,"clip":1 if kind!="roll" else 0},
                               {"track":1,"clip":1 if kind!="roll" else 0}]
    if audio is None:audio=[{"track":0,"clip":1 if kind!="roll" else 0}]
    return {"kind":kind,"delta_frames":delta,
        "picture_targets":picture,"audio_targets":audio,
        "automation":"lock_to_timeline"}


def _length(track):
    return max((c["position_frame"]+c["end_frame"]-c["first_frame"]
                for c in track["clips"]),default=0)


class NativeClipWindowMathTests(unittest.TestCase):
    def test_model_can_discover_authorable_signed_local_edits(self):
        for kind in ("roll","slip","slide"):
            command={"edits":[_action(kind,2)]}
            self.assertTrue(validate_document(
                "body.mlt_owned_revision",command,"operation"))
        for invalid in (
            {"edits":[_action("roll",1)|{"unsafe_xml":"filter"}]},
            {"edits":[_action("roll",1)|{"automation":"guess_artist_choice"}]},
            {"edits":[_action("unknown",1)]},
            {"edits":[_action("slip",1)|{"delta_frames":True}]},
        ):
            with self.assertRaises(ValueError):
                validate_document("body.mlt_owned_revision",invalid,"operation")

    def test_each_window_action_and_exact_inverse_restore_every_source(self):
        original=_project()
        for kind in ("roll","slip","slide"):
            for delta in (-1,1):
                with self.subTest(kind=kind,delta=delta):
                    edited,proof=apply_local_window_action(
                        original,_action(kind,delta))
                    self.assertEqual(original,_project())
                    for key in ("tracks","audio_tracks"):
                        for before,after in zip(original[key],edited[key]):
                            self.assertEqual(set(before),set(after))
                            for prop in ("opacity_keyframes","gain_keyframes",
                                         "blend_mode"):
                                self.assertEqual(before.get(prop),after.get(prop))
                            self.assertEqual(_length(before),_length(after))
                            for a,b in zip(before["clips"],after["clips"]):
                                self.assertEqual(a["asset_id"],b["asset_id"])
                                self.assertEqual(a["attestation_id"],b["attestation_id"])
                                self.assertEqual(a["source"],b["source"])
                    restored,inverted=apply_local_window_action(
                        edited,_action(kind,-delta))
                    self.assertEqual(restored,original)
                    self.assertEqual(proof["kind"],kind)
                    self.assertEqual(proof["effects_automation_policy"],
                                     "lock_to_timeline")
                    self.assertFalse(proof["independent_release_or_artist_certification"])
                    self.assertEqual(inverted["delta_frames"],-delta)

    def test_all_window_ops_can_compose_into_one_reversible_revision(self):
        source=_project()
        actions=[_action("roll",1),_action("slip",1),_action("slide",1)]
        changed,report=apply_linked_editor_actions(source,{"edits":actions})
        self.assertEqual(len(report["operations"]),3)
        self.assertEqual([x["kind"] for x in report["operations"]],
                         ["roll","slip","slide"])
        reversed_actions=[_action("slide",-1),_action("slip",-1),
                          _action("roll",-1)]
        recovered,back=apply_linked_editor_actions(changed,{
            "edits":reversed_actions})
        self.assertEqual(recovered,source)
        self.assertEqual(len(back["operations"]),3)

    def test_rejects_ambiguous_gaps_or_source_erasure_instead_of_inventing_video(self):
        source=_project()
        original=copy.deepcopy(source)
        rejected=[
            _action("roll",3),
            _action("roll",-4),
            _action("slide",3),
            _action("slide",-4),
            _action("slip",-5),
            _action("slip",0),
            _action("slip",1,picture=[],audio=[]),
            _action("slide",1,picture=[{"track":0,"clip":0}],audio=[]),
            _action("roll",1,picture=[{"track":0,"clip":2}],audio=[]),
            _action("roll",1,picture=[{"track":0,"clip":0},
                                      {"track":0,"clip":1}],audio=[]),
            _action("roll",1,picture=[{"track":1,"clip":0},
                                      {"track":0,"clip":0}],audio=[]),
            _action("roll",1,picture=[{"track":20,"clip":0}],audio=[]),
        ]
        for act in rejected:
            with self.subTest(action=act),self.assertRaises(ValueError):
                apply_local_window_action(source,act)
            self.assertEqual(source,original)
        broken=copy.deepcopy(source)
        broken["tracks"][0]["clips"][1]["position_frame"]=4
        with self.assertRaisesRegex(ValueError,"no gap"):
            apply_local_window_action(broken,_action("roll",1,
                picture=[{"track":0,"clip":0}],audio=[]))
        with self.assertRaisesRegex(ValueError,"contiguous"):
            apply_local_window_action(broken,_action("slide",1,
                picture=[{"track":0,"clip":1}],audio=[]))

    def test_500_random_finite_signed_frame_source_edits_are_inverse_operations(self):
        rng=random.Random(0x57D1)
        for sample in range(500):
            original=_project()
            delta=rng.choice((-1,1))
            kind=rng.choice(("roll","slip","slide"))
            target=_action(kind,delta)
            edited,_=apply_local_window_action(original,target)
            restored,_=apply_local_window_action(
                edited,_action(kind,-delta))
            self.assertEqual(restored,original,
                             msg=(sample,kind,delta))


if __name__=="__main__":
    unittest.main()
