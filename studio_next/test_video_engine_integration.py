import unittest
from unittest.mock import patch

from studio_next.production_handoff import validate_visual_design
from studio_next.visual_engine_hub import resolve_visual_engine


def scene():
    return {"id":"scene_01","duration_seconds":4.1,
            "narration":"","visual":"A truthful filmed human gesture",
            "fact_refs":[]}


def external():
    return {"shot_id":"scene_01","engine":"studio_color_grading",
            "creative_rationale":"Actual director calls for graded natural light",
            "continuity":"Maintain the actor's single physical gesture",
            "scene_job":{"original_media":"signed_original.mp4"},
            "desired_capabilities":["original_media_review"],
            "production_gap":""}


class ExtensibleFilmEngineTests(unittest.TestCase):
    def test_unknown_video_tools_are_not_fake_runtime(self):
        with self.assertRaisesRegex(ValueError,"installed adapter"):
            validate_visual_design(scene(),external(),{})

    def test_explicit_registered_engine_owns_validation_not_creative_style(self):
        class InstalledEngine:
            engine_id="studio_color_grading"
            def validate(self,shot,design,facts):
                self.assertion=(shot["id"],design["engine"],len(facts))
                return {"engine":"studio_color_grading","executable":True,
                        "audio_required":False}
        engine=InstalledEngine()
        with patch("studio_next.production_handoff.resolve_visual_engine",return_value=engine):
            result=validate_visual_design(scene(),external(),{})
        self.assertTrue(result["executable"])
        self.assertEqual(engine.assertion,("scene_01","studio_color_grading",0))

    def test_pretend_video_adapter_cannot_claim_executable_without_real_validation(self):
        class FalseEngine:
            engine_id="studio_color_grading"
            def validate(self,*args):
                return {"engine":self.engine_id,"executable":False}
        with patch("studio_next.production_handoff.resolve_visual_engine",
                   return_value=FalseEngine()):
            with self.assertRaisesRegex(ValueError,"did not prove"):
                validate_visual_design(scene(),external(),{})

    def test_builtin_local_comfy_engine_requires_real_video_service(self):
        inst=resolve_visual_engine("comfy_video")
        self.assertIsNotNone(inst)
        text_to_video={"shot_id":"scene_01","engine":"comfy_video",
          "creative_rationale":"A moving human face serves this exact scene",
          "continuity":"Match authentic original gesture",
          "scene_job":{"model_id":"wan21-t2v-13b",
              "prompt":"A person in natural rain really writes in a pocket notebook",
              "negative_prompt":"","width":832,"height":480,"frames":41,
              "fps":10,"seed":42},
          "desired_capabilities":["text_to_video"],"production_gap":""}
        with patch.dict("os.environ",{"ZX7_COMFY_API":""}):
            with self.assertRaisesRegex(ValueError,"self-hosted"):
                validate_visual_design(scene(),text_to_video,{})


if __name__=="__main__":
    unittest.main()
