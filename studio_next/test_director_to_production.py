import json
import tempfile
import unittest
from pathlib import Path

from studio_next.director_to_production import (
    handoff_single_brain,validate_translation)


def owner():
    return {"request":"A truly original cinema concept across any media",
            "facts":{"identity":"An actual paper notebook"}}


def treatment(n=2):
    return {"title":"An impossible question",
            "creative_intent":"Make the audience doubt familiar assumptions",
            "story":"One honest action changes the viewer's understanding",
            "voice":{"choice":"no_voice","why":"Spatial sound and silence"},
            "scenes":[{"id":f"shot_{i+1}",
                       "purpose":"Each scene changes the relationship to a real thought",
                       "duration_seconds":2.5+i,
                       "visual":"Actor and space in a motivated full-3D film image",
                       "motion":"A uniquely directed spatial camera movement",
                       "edit":"A consequential action links the images",
                       "audio":"Environmental sound is purposeful",
                       "narration":"","fact_refs":["identity"],
                       "assets_needed":["Actual actor footage, not yet licensed"]}
                      for i in range(n)],
            "unresolved_production_needs":["Original actor footage is not yet available"]}


class AModel:
    def __init__(self,name="one-director"):
        self.settings=type("Settings",(),{"model_id":name})()
        self.prompts=[]
    def compose(self,brief):
        return "My original director's film: a real actor moves through space."
    def decide(self,context):
        self.prompts.append(context)
        if "original_cinematic_direction" in context:
            return treatment(4)
        if "current_shot" in context:
            return {"shot_id":context["current_shot"]["id"],
                    "engine":"unresolved",
                    "creative_rationale":"Real actor movement is essential",
                    "continuity":"Continue the physical story",
                    "scene_job":{},
                    "desired_capabilities":["rights-cleared_actor_footage"],
                    "production_gap":"No authentic footage yet"}
        return {"format":{"width":1600,"height":900,"fps":25,
                          "framing":"fit","background":"#111111"},
                "voice":"no_voice","reason":"The film needs a composed landscape image"}


class FilmHandoffTests(unittest.TestCase):
    def test_director_can_choose_unbounded_original_scenes_and_timing(self):
        for n in (1,4,39):
            x=treatment(n)
            result=validate_translation(x,owner()["facts"])
            self.assertEqual(result["scenes"],n)
            self.assertFalse(result["format_preselected"])
            self.assertFalse(result["artistic_quality_approved"])

    def test_no_unverified_fact_or_fake_narrator_disappearance(self):
        x=treatment(1)
        x["scenes"][0]["fact_refs"]=["unverified_product_spec"]
        with self.assertRaisesRegex(ValueError,"Invented owner"):
            validate_translation(x,owner()["facts"])
        x=treatment(1);x["scenes"][0]["narration"]="Please listen"
        with self.assertRaisesRegex(ValueError,"discard spoken"):
            validate_translation(x,owner()["facts"])

    def test_same_model_preserves_director_vision_and_unbuildable_scenes(self):
        with tempfile.TemporaryDirectory() as t:
            brain,editor,producer,delivery=[AModel() for _ in range(4)]
            out=Path(t)/"film"
            result=handoff_single_brain(owner(),brain,editor,producer,delivery,out)
            self.assertTrue(result["original_vision_preserved"])
            self.assertEqual(result["translation_validated"]["scenes"],4)
            self.assertEqual(len(result["production"]["designs"]),4)
            self.assertFalse(result["production"]["all_designs_executable"])
            self.assertFalse(result["ready_for_possible_render"])
            self.assertFalse(result["film_rendered"])
            self.assertTrue((out/"original-vision"/"director-original.txt").is_file())
            self.assertIn("real actor", (out/"original-vision"/"director-original.txt").read_text())
            self.assertEqual(json.loads((out/"director-translation.json").read_text())["scenes"][0]["id"],"shot_1")
            self.assertEqual(len(list((out/"designs").glob("design-*.json"))),4)
            self.assertEqual(delivery.prompts[0]["treatment"]["title"],"An impossible question")
            delivery_file=out/"designs"/"delivery.json"
            self.assertEqual(json.loads(delivery_file.read_text())["voice"],"no_voice")
            self.assertTrue(json.loads((out/"designs"/"production-manifest.json").read_text())["all_designs_executable"] is False)

    def test_cannot_silently_change_model_brain(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaisesRegex(ValueError,"Single cohesive"):
                handoff_single_brain(owner(),AModel(),AModel("second-persona"),
                        AModel(),AModel(),t)
            self.assertFalse((Path(t)/"original-vision"/"director-original.txt").exists())

    def test_invalid_translated_story_keeps_immutable_original_director_vision(self):
        with tempfile.TemporaryDirectory() as t:
            class InvalidDirector(AModel):
                def decide(self,context):
                    return {"title":"a title only"}
            out=Path(t)/"film"
            result=handoff_single_brain(owner(),AModel(),InvalidDirector(),
                                         AModel(),AModel(),out)
            self.assertFalse(result["ready_for_possible_render"])
            self.assertIn("translation_rejected",result)
            self.assertTrue((out/"original-vision"/"director-original.txt").exists())
            self.assertTrue((out/"director-translation-raw.json").exists())


if __name__=="__main__":
    unittest.main()
