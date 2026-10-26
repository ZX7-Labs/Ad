import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_next.film_revision import FilmRevisionBrain,preserve_artistic_revision
from studio_next.providers import LocalModelSettings


def evidence():
    return {"frames":[{"timestamp_seconds":0.7,"path":"actual/001.jpg",
                      "frame_sha256":"real-frame-hash"}],
            "ffprobe":{"seconds":4.75},
            "audio_reviewed":False,
            "video_fully_reviewed":False,"human_approval":False}

class OriginalFilmRevisionTests(unittest.TestCase):
    def test_preserve_original_and_factual_review_separately(self):
        class Artist:
            def rethink(self,original,review,owner,actual):
                self_ref=original
                assert "my original shot" in self_ref
                assert "causality" in review
                assert owner["facts"]=={"identity":"Actually supplied"}
                return "I rethink this work: the first image earns the sculpture."
        with tempfile.TemporaryDirectory() as root:
            outcome=preserve_artistic_revision(
                "my original shot", "Missing actual story causality",evidence(),
                {"request":"Original film","facts":{"identity":"Actually supplied"}},
                Artist(),root)
            self.assertFalse(outcome["revised_video_rendered"])
            self.assertFalse(outcome["independent_human_audience_approval"])
            self.assertEqual(outcome["real_frame_count"],1)
            self.assertEqual(Path(root,"director-original.txt").read_text(),"my original shot")
            self.assertIn("I rethink",Path(root,"director-revised.txt").read_text())

    def test_no_creative_effects_or_scene_count_formulas_passed_to_artist(self):
        with tempfile.TemporaryDirectory() as t:
            class Artist:
                def rethink(self,original,review,owner,actual):
                    return original+" renewed, with earned stillness rather than forced motion."
            for title in ["an experimental documentary","a live-action short","a true 3D epic"]:
                out=Path(t)/title.replace(" ","_")
                preserve_artistic_revision(title,"Composition lacks intention",
                  evidence(),{"request":title,"facts":{}},Artist(),out)
                self.assertIn(title,(out/"director-revised.txt").read_text())

    def test_never_invent_frames_or_human_approval(self):
        with tempfile.TemporaryDirectory() as t:
            class Artist:
                def rethink(self,*args):
                    raise AssertionError("Should not call model without real evidence")
            with self.assertRaises(ValueError):
                preserve_artistic_revision("original","review",{},{"facts":{}},Artist(),t)
            e=evidence();e["human_approval"]=True
            with self.assertRaises(ValueError):
                preserve_artistic_revision("original","review",e,{"facts":{}},Artist(),t)

    def test_one_brain_reviewer_identity_must_match_and_be_proven(self):
        class Artist:
            settings=type("Settings",(),{"model_id":"different-model"})()
            def rethink(self,*args):
                raise AssertionError("Do not use a different brain's aesthetic verdict")
        visual=evidence()
        visual["reviewer_model_id"]="original-reviewer"
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError,"Different film model"):
                preserve_artistic_revision("original film","seen a weak composition",
                    visual,{"facts":{}},Artist(),folder)

    def test_prototype_comparison_never_claims_actual_own_film_was_watched(self):
        class Reply:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,limit):
                return json.dumps({"choices":[{"finish_reason":"stop",
                    "message":{"content":"This old demo is not my new film."}}]}).encode()
        def fake(request,timeout):
            payload=json.loads(request.data)
            system=payload["messages"][0]["content"]
            self.assertIn("UNRELATED archived technical",system)
            context=json.loads(payload["messages"][1]["content"])
            self.assertTrue(context["observation_scope"]["not_actual_render_of_original_story"])
            return Reply()
        e=evidence()
        e["reference_prototype"]=True
        brain=FilmRevisionBrain(LocalModelSettings(model_id="one-film-director"))
        with patch("studio_next.film_revision.urlopen",fake):
            revised=brain.rethink("Brand-new film idea","Technical sample lacks a human",
                {"request":"New film","facts":{}},e)
            self.assertIn("not my new film",revised)
        with tempfile.TemporaryDirectory() as d:
            class Artist:
                def rethink(self,*args):return "Original revised artistic idea"
            result=preserve_artistic_revision("Original art idea","Reference visual",
                e,{"request":"Film","facts":{}},Artist(),d)
            self.assertTrue(result["reference_was_unrelated_technical_clip"])
            self.assertFalse(result["revised_new_movie_was_actually_criticized"])

    def test_model_receives_visual_scope_and_only_local_no_json_mode(self):
        class Reply:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,max_len):
                return json.dumps({"choices":[{"finish_reason":"stop",
                    "message":{"content":"I preserve the first motif."}}]}).encode()
        def fake(req,timeout):
            payload=json.loads(req.data)
            self.assertNotIn("response_format",payload)
            self.assertEqual(payload["model"],"one-film-director")
            original=json.loads(payload["messages"][1]["content"])
            self.assertTrue(original["observation_scope"]["audio_was_not_reliably_reviewed"])
            self.assertEqual(original["observation_scope"]["observed_frame_timestamps_seconds"],[0.7])
            return Reply()
        brain=FilmRevisionBrain(LocalModelSettings(model_id="one-film-director"))
        with patch("studio_next.film_revision.urlopen",fake):
            actual=brain.rethink("film vision","observed camera issue",
                {"request":"Film","facts":{}},evidence())
            self.assertIn("preserve",actual)

if __name__=="__main__":unittest.main()
