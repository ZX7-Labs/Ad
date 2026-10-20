import tempfile
import unittest
from pathlib import Path
from studio_next.production_handoff import (
    author_production,validate_visual_design,_scenes)

def story():
    return {"title":"Original idea","creative_intent":"A question changes the view",
        "scenes":[{"id":"first","purpose":"Honest question","duration_seconds":2.0,
                   "narration":"","visual":"A tiny 3D metallic idea unfolds","fact_refs":[]}]}

def three_d():
    return {"shot_id":"first","engine":"blender3d","creative_rationale":
       "Moving physical sculpture corresponds to this scene's change",
       "continuity":"Camera movement follows unfinished line",
       "desired_capabilities":["visual.true_3d"],"production_gap":"",
       "scene_job":{"shot_id":"first","width":320,"height":320,"fps":12,"frames":24,
       "camera":{"location":[3,-5,4],"target":[0,0,0],"lens_mm":40},
       "world":{"color":[.1,.1,.1],"strength":.8},
       "materials":[{"id":"metal","color":[1,.6,.2,1],"roughness":.25,"metallic":.7}],
       "objects":[{"id":"idea","type":"torus","material":"metal",
                   "location":[0,0,0],"rotation_degrees":[0,0,0],"scale":[1,1,1]}],
       "lights":[{"id":"key","type":"AREA","location":[2,-4,3],
                  "rotation_degrees":[0,0,0],"energy":850,"color":[1,1,1]}]}}

class FakeBrain:
    def __init__(self, value): self.value=value;self.inputs=[]
    def decide(self,context):self.inputs.append(context);return self.value

class ProductionHandoffTests(unittest.TestCase):
    def test_3d_stays_3d_with_directed_length_and_camera(self):
        d=three_d()
        result=validate_visual_design(story()["scenes"][0],d,{})
        self.assertTrue(result["executable"])
        self.assertEqual(result["engine"],"blender3d")

    def test_inconsistent_scene_and_time_rejected(self):
        d=three_d();d["scene_job"]["frames"]=8
        with self.assertRaisesRegex(ValueError,"timing|duration"):
            validate_visual_design(story()["scenes"][0],d,{})
        d=three_d();d["shot_id"]="other"
        with self.assertRaisesRegex(ValueError,"unchanged shot"):
            validate_visual_design(story()["scenes"][0],d,{})

    def test_missing_realism_is_preserved_not_simulated(self):
        d=three_d();d.update(engine="unresolved",scene_job={},production_gap=
           "Real street documentary footage has not been supplied",
           desired_capabilities=["visual.verified_live_footage"])
        a=validate_visual_design(story()["scenes"][0],d,{})
        self.assertFalse(a["executable"])
        self.assertIn("street documentary",a["reason"])

    def test_untrusted_model_cannot_execute_commands(self):
        d=three_d();d["scene_job"]["__python"]="import os"
        with self.assertRaises(ValueError):validate_visual_design(story()["scenes"][0],d,{})

    def test_brief_and_all_scenes_available_to_director(self):
        with tempfile.TemporaryDirectory() as d:
            model=FakeBrain(three_d())
            report=author_production(story(),{"identity":"owner says nothing else"},
                                     model,Path(d))
            self.assertTrue(report["all_designs_executable"])
            self.assertEqual(model.inputs[0]["owner_facts"]["identity"],
                             "owner says nothing else")
            self.assertEqual(model.inputs[0]["all_shots"][0]["id"],"first")
            self.assertTrue((Path(d)/"design-001.json").is_file())
            self.assertTrue((Path(d)/"production-manifest.json").is_file())

    def test_failing_design_not_silently_deleted(self):
        with tempfile.TemporaryDirectory() as d:
            x=three_d();x["engine"]="pretend"
            report=author_production(story(),{},FakeBrain(x),Path(d))
            self.assertFalse(report["all_designs_executable"])
            self.assertEqual(report["original_scene_ids"],["first"])

    def test_authored_shot_count_not_held_to_any_template(self):
        for n in (1,12,68):
            x=story()
            x["scenes"]=[dict(x["scenes"][0],id=f"scene_{i}") for i in range(n)]
            self.assertEqual(len(_scenes(x)),n)


if __name__=="__main__":
    unittest.main()
