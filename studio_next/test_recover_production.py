import json
import tempfile
import unittest
from pathlib import Path

from studio_next.recover_production import recover_saved_original


def shot(sid):
    return {"id":sid,"purpose":"The filmmaker's authored dramatic purpose",
            "visual":"A particular live-action hand and actor in actual transit",
            "duration_seconds":3.0,"narration":"","fact_refs":["identity"],
            "assets_needed":["Actual human performance or honest gap"]}


class Specialist:
    settings=type("Settings",(),{"model_id":"same-original-film-mind"})()
    def __init__(self):
        self.contexts=[]
    def decide(self,context):
        self.contexts.append(context)
        s=context["immutable_original_shot"]
        return {"shot_id":s["id"],"engine":"unresolved",
                "creative_rationale":"The original actor and live footage matter",
                "continuity":"Continue the original motion and character identity",
                "scene_job":{},
                "desired_capabilities":["authentic rights-cleared actor performance"],
                "production_gap":"Actual filmed actor and live-action rights missing"}


class ArchivedFilmRecoveryTests(unittest.TestCase):
    def fixture(self,root):
        root=Path(root)
        d=root/"original"/"director"
        (d/"original-vision").mkdir(parents=True)
        (d/"designs").mkdir()
        t={"title":"My own real film","voice":{"choice":"M3","why":"A directed voice"},
           "scenes":[shot("first"),shot("second")]}
        (d/"director-translation.json").write_text(json.dumps(t))
        (d/"original-vision"/"director-original.txt").write_text(
            "An original artistic film that requires actual human performance")
        for n,s in enumerate(t["scenes"],1):
            (d/"designs"/f"design-{n:03d}.json").write_text(json.dumps({
                "scene_id":s["id"],"model_response":{
                    "shot_id":s["id"],"engine":"blender3d",
                    "creative_rationale":"Bespoke original shot",
                    "continuity":"The authored actor continues",
                    "scene_job":{"unrealistic":"free magical actor"},
                    "desired_capabilities":[],"production_gap":""},
                "verification":{"executable":False,
                                "reason":"Invalid3DShot: invalid real geometry"}
            }))
        (d/"designs"/"delivery.json").write_text(json.dumps(
            {"format":{"width":900,"height":1600,"fps":24,
                       "framing":"fit","background":"#000000"},
             "voice":"M3","reason":"Director's original delivery"}))
        brief=root/"brief.json"
        brief.write_text(json.dumps({"request":"A compelling original film",
                                     "facts":{"identity":"Actual paper notebook"}}))
        return d,brief

    def test_actual_saved_story_preserved_even_when_model_admits_missing_media(self):
        with tempfile.TemporaryDirectory() as tmp:
            d,brief=self.fixture(tmp)
            original=(d/"director-translation.json").read_bytes()
            original_vision=(d/"original-vision"/"director-original.txt").read_bytes()
            model=Specialist()
            result=recover_saved_original(d,brief,model,Path(tmp)/"corrected")
            self.assertEqual(len(model.contexts),2)
            self.assertEqual(model.contexts[0]["actual_validator_result"],
                             "Invalid3DShot: invalid real geometry")
            self.assertIn("validation_code_sha256",model.contexts[0]["actual_renderer_contract"])
            self.assertIn("blender3d",model.contexts[0]["actual_renderer_contract"])
            self.assertNotIn("blender_validator_source",model.contexts[0]["actual_renderer_contract"])
            self.assertTrue(result["original_film_story_unchanged"])
            self.assertFalse(result["all_designs_executable"])
            self.assertFalse(result["movie_rendered"])
            self.assertEqual(result["status"],"BLOCKED_BY_VERIFIED_PRODUCTION_REQUIREMENTS")
            self.assertEqual((d/"director-translation.json").read_bytes(),original)
            self.assertEqual((Path(tmp)/"corrected"/"original-preserved"/
                              "director-original.txt").read_bytes(),original_vision)
            self.assertEqual(len(list((Path(tmp)/"corrected").glob("reviewed-design-*.json"))),2)

    def test_scene_recovery_restarts_from_saved_exact_model_decisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            d,brief=self.fixture(tmp)
            out=Path(tmp)/"recovered"
            artist=Specialist()
            first=recover_saved_original(d,brief,artist,out)
            self.assertEqual(len(artist.contexts),2)
            self.assertFalse(first["movie_rendered"])
            self.assertEqual(len(list((out/"verified-technical-checkpoints").glob("scene_*.json"))),2)
            class NoMoreModelCalls(Specialist):
                def decide(self,context):
                    raise AssertionError("Expensive film-brain call repeated on same scene")
            recovered=recover_saved_original(d,brief,NoMoreModelCalls(),out)
            self.assertEqual(recovered["original_scene_count"],2)
            self.assertTrue(all("checkpoint" in x["attempted"] for x in recovered["designs"]))
            self.assertFalse(recovered["all_designs_executable"])
            # Changing the source artistic screenplay invalidates old scene work.
            target=d/"director-translation.json"
            film=json.loads(target.read_text())
            film["scenes"][0]["visual"]="A changed actual director shot"
            target.write_text(json.dumps(film))
            with self.assertRaisesRegex(AssertionError,"repeated"):
                recover_saved_original(d,brief,NoMoreModelCalls(),out)

    def test_an_invented_renderer_schema_never_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            d,brief=self.fixture(tmp)
            class FalseFilm(Specialist):
                def decide(self,ctx):
                    response=super().decide(ctx)
                    response.update(engine="blender3d",
                        scene_job={"shot_id":ctx["immutable_original_shot"]["id"],"__python__":"create actor by magic"},
                        desired_capabilities=[],production_gap="")
                    return response
            res=recover_saved_original(d,brief,FalseFilm(),Path(tmp)/"trial")
            self.assertFalse(res["all_designs_executable"])
            self.assertIn("Invalid3DShot",res["designs"][0]["real_gap"])

    def test_original_archive_scene_id_must_match_source_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            d,brief=self.fixture(tmp)
            p=d/"designs"/"design-002.json"
            data=json.loads(p.read_text())
            data["scene_id"]="other movie"
            p.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"mixes up"):
                recover_saved_original(d,brief,Specialist(),Path(tmp)/"trial")


if __name__=="__main__":
    unittest.main()
