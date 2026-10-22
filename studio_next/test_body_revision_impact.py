"""Original multishot film revision graph: exact dependency impact, no fake cache reuse."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from studio_next.body_revision_impact import plan_film_revision_impact


def original_film(root):
    a=root/"author-voice.wav";b=root/"original-camera.mp4"
    a.write_bytes(b"owner voice original");b.write_bytes(b"owned original filming")
    sources=[
        {"id":"a","status":"verified","rights":"owner_supplied","location":a.name},
        {"id":"b","status":"verified","rights":"owner_supplied","location":b.name}]
    return {
      "project":{"creative_intent":"Original independent dramatic edit"},
      "assets":sources,
      "shots":[
       {"id":"s1","purpose":"Intimate original character moment",
        "asset_refs":["a"],"duration_seconds":2.9},
       {"id":"s2","purpose":"Actual different original camera story",
        "asset_refs":["b"],"duration_seconds":3.1}],
      "tool_graph":[
       {"id":"render1","tool_id":"body.test",
        "purpose":"Real image and voice shot A", "shot_refs":["s1"],
        "inputs":{"source":"author-voice.wav"},"depends_on":[]},
       {"id":"render2","tool_id":"body.test",
        "purpose":"Real camera shot B","shot_refs":["s2"],
        "inputs":{"source":"original-camera.mp4"},"depends_on":[]},
       {"id":"audio_master","tool_id":"body.test",
        "purpose":"Master shot A audio","shot_refs":["s1"],
        "depends_on":["render1"],
        "inputs":{"sound":{"$node_output":"render1"}}},
       {"id":"final","tool_id":"body.test",
        "purpose":"Film finishing of complete story",
        "depends_on":["audio_master","render2"],
        "inputs":{"shot_a":{"$node_output":"audio_master"},
                  "shot_b":{"$node_output":"render2"}}}
      ]
    }


class OriginalFilmImpactTests(unittest.TestCase):
    def test_unrelated_shot_change_only_invalidates_affected_chain(self):
        with tempfile.TemporaryDirectory() as location:
            film=original_film(Path(location))
            next_=copy.deepcopy(film)
            next_["shots"][1]["duration_seconds"]=7.3
            report=plan_film_revision_impact(film,next_)
            self.assertEqual(report["original_unchanged_candidates"],
                             ["render1","audio_master"])
            self.assertEqual(report["new_or_changed_operations"],
                             ["render2","final"])
            self.assertEqual(report["directly_changed_operations"],["final","render2"])
            self.assertFalse(report["reusable_cached_bytes_proven"])

    def test_changing_only_audio_node_propagates_to_master_not_original_picture(self):
        with tempfile.TemporaryDirectory() as location:
            film=original_film(Path(location))
            next_=copy.deepcopy(film)
            next_["tool_graph"][2]["purpose"]="Master true dialogue with artist music"
            report=plan_film_revision_impact(film,next_)
            self.assertEqual(report["new_or_changed_operations"],
                             ["audio_master","final"])
            self.assertEqual(report["original_unchanged_candidates"],
                             ["render1","render2"])

    def test_unscoped_entire_film_respects_new_original_assets_and_global_brief(self):
        with tempfile.TemporaryDirectory() as location:
            film=original_film(Path(location))
            more=copy.deepcopy(film)
            more["assets"].append({"id":"extra","status":"verified",
                "rights":"owner_supplied","location":"licensed-extra.wav"})
            more["shots"][1]["asset_refs"].append("extra")
            result=plan_film_revision_impact(film,more)
            self.assertEqual(result["new_or_changed_operations"],
                             ["render2","final"])
            self.assertEqual(result["original_unchanged_candidates"],
                             ["render1","audio_master"])
            changed=copy.deepcopy(film)
            changed["project"]["creative_intent"]="Another film's entire original contract"
            impact=plan_film_revision_impact(film,changed)
            self.assertEqual(len(impact["new_or_changed_operations"]),4)

    def test_deleted_stage_or_new_graph_operation_requires_new_execution(self):
        with tempfile.TemporaryDirectory() as location:
            film=original_film(Path(location))
            # Old master is no longer on the artist's final mix; the final
            # scene must be recut even if its new graph looks independent.
            after=copy.deepcopy(film)
            after["tool_graph"]=[n for n in after["tool_graph"]
                                 if n["id"]!="audio_master"]
            after["tool_graph"][-1]["depends_on"]=["render1","render2"]
            after["tool_graph"][-1]["inputs"]["shot_a"]={"$node_output":"render1"}
            impact=plan_film_revision_impact(film,after)
            self.assertEqual(impact["deleted_original_operations"],["audio_master"])
            self.assertEqual(impact["new_or_changed_operations"],["final"])
            self.assertEqual(impact["original_unchanged_candidates"],
                             ["render1","render2"])

    def test_unchanged_artistry_is_only_candidate_not_certified_bytes(self):
        with tempfile.TemporaryDirectory() as location:
            film=original_film(Path(location))
            info=plan_film_revision_impact(film,copy.deepcopy(film))
            self.assertEqual(info["new_or_changed_operations"],[])
            self.assertEqual(len(info["original_unchanged_candidates"]),4)
            self.assertFalse(info["source_media_bytes_physically_rechecked"])
            self.assertTrue(info["requires_runtime_custody_validation"])
            self.assertFalse(info["creative_style_prescribed"])

    def test_bad_asset_rights_and_graph_structure_never_issue_reuse_advice(self):
        with tempfile.TemporaryDirectory() as location:
            film=original_film(Path(location))
            for bogus in ["not-listed",7]:
                bad=copy.deepcopy(film)
                bad["tool_graph"][1]["asset_refs"]=[bogus]
                with self.assertRaisesRegex(ValueError,"unsafe/unrenderable"):
                    plan_film_revision_impact(film,bad)
            bad=copy.deepcopy(film)
            bad["tool_graph"][0]["depends_on"]=["final"]
            with self.assertRaisesRegex(ValueError,"unsafe/unrenderable"):
                plan_film_revision_impact(film,bad)


if __name__=="__main__":unittest.main()
