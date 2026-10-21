import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from studio_next.film_eye import VisualFilmDirector
from studio_next.providers import LocalModelSettings


class FilmVisualReviewTests(unittest.TestCase):
    def test_same_one_local_director_evaluates_actual_decoded_images(self):
        tiny_jpeg=b"\xff\xd8\xff"+bytes(range(110))+b"\xff\xd9"
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"real.jpg";path.write_bytes(tiny_jpeg)
            frames=[{"path":str(path),"timestamp_seconds":1.0,
                     "frame_sha256":hashlib.sha256(tiny_jpeg).hexdigest()}]
            class Response:
                def __enter__(self):return self
                def __exit__(self,*args):return False
                def read(self,limit):
                    return json.dumps({"choices":[{"finish_reason":"stop",
                        "message":{"content":"The subject is not visually clear"}}]}).encode()
            def server(req,timeout):
                obj=json.loads(req.data)
                self.assertEqual(obj["model"],"single-film-brain")
                c=obj["messages"][1]["content"]
                self.assertTrue(any(x.get("type")=="image_url" for x in c))
                self.assertIn("data:image/jpeg;base64,",json.dumps(c))
                self.assertNotIn("response_format",obj)
                return Response()
            brain=VisualFilmDirector(LocalModelSettings(model_id="single-film-brain"))
            with patch("studio_next.film_eye.urlopen",server):
                self.assertIn("subject",brain.evaluate("The director imagines a meaningful story",frames))

    def test_real_media_provenance_required_no_fake_frame_paths(self):
        brain=VisualFilmDirector(LocalModelSettings(model_id="test"))
        with self.assertRaises(ValueError):
            brain.evaluate("Original scene goal",[])
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"not-an-image.jpg";f.write_bytes(b"A"*256)
            with self.assertRaisesRegex(ValueError,"decoded JPEG"):
                brain.evaluate("Original goal",[{"path":str(f),"timestamp_seconds":0,
                    "frame_sha256":"untrusted"}])


if __name__=="__main__":unittest.main()
