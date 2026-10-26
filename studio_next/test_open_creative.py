import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_next.open_creative import (
    FreeformFilmBrain,preserve_original_direction)
from studio_next.providers import LocalModelSettings


class OpenCinematicImaginationTests(unittest.TestCase):
    def test_original_free_prose_not_forced_into_shot_json(self):
        class Brain:
            def compose(self,brief):
                return "A street loses its sound. A single original thought changes everything."
        with tempfile.TemporaryDirectory() as t:
            b={"request":"A completely new idea","facts":{}}
            m=preserve_original_direction(b,Brain(),t)
            self.assertFalse(m["render_ready"])
            self.assertFalse(m["human_creative_quality_approved"])
            self.assertEqual((Path(t)/"director-original.txt").read_text(),
                "A street loses its sound. A single original thought changes everything.")

    def test_no_default_medium_length_or_artist_dictated(self):
        class Brain:
            def compose(self,b):
                return b["request"]
        with tempfile.TemporaryDirectory() as t:
            ideas=["A silent experimental feature film lasting 110 minutes",
                "A sharply edited documentary", "An immersive 3D narrative"]
            for i,idea in enumerate(ideas):
                out=Path(t)/str(i)
                preserve_original_direction({"request":idea,"facts":{}},Brain(),out)
                self.assertEqual((out/"director-original.txt").read_text(),idea)

    def test_freeform_does_not_accept_remote_model_endpoints(self):
        with self.assertRaises(ValueError):
            FreeformFilmBrain(LocalModelSettings(base_url="https://paid.example.com",
                         model_id="not_allowed"))

    def test_local_request_has_no_json_response_format(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self,*args):return False
            def read(self,limit):
                return json.dumps({"choices":[{"finish_reason":"stop",
                    "message":{"content":"I see a genuinely original film image"}}]}).encode()
        def fake_request(req,timeout):
            payload=json.loads(req.data)
            self.assertNotIn("response_format",payload)
            self.assertFalse("scene_count" in payload)
            self.assertEqual(payload["messages"][0]["role"],"system")
            self.assertEqual(req.full_url,"http://127.0.0.1:8085/v1/chat/completions")
            return Response()
        brain=FreeformFilmBrain(LocalModelSettings(base_url="http://127.0.0.1:8085",
                                                    model_id="creative-candidate"))
        with patch("studio_next.open_creative.urlopen",fake_request):
            self.assertIn("original",brain.compose({"request":"A film","facts":{}}))

    def test_refuse_to_pretend_truncated_creative_text_is_finished(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,limit):
                return json.dumps({"choices":[{"finish_reason":"length",
                     "message":{"content":"Half a story"}}]}).encode()
        brain=FreeformFilmBrain(LocalModelSettings(model_id="test"))
        with patch("studio_next.open_creative.urlopen",lambda *args,**kw: Response()):
            with self.assertRaisesRegex(ValueError,"truncated"):
                brain.compose({"request":"A film","facts":{}})


if __name__=="__main__":
    unittest.main()
