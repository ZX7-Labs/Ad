"""Bind each vision payload to the physical source it represents.

OpenAI-compatible requests retain ordered content parts; each image must follow
a provenance label for that exact artifact. A swapped before/after frame is a
hard error, not a silent model-visible misassociation.
"""
import base64
import hashlib
import importlib.util
import io
import json
import unittest
from unittest.mock import patch

from studio_next.providers import LocalCreativeModel,LocalModelSettings


@unittest.skipUnless(importlib.util.find_spec("PIL") is not None,
                     "Real encoded PNG fixtures require Pillow")
class LocalModelVerifiedVisionTests(unittest.TestCase):
    @staticmethod
    def _picture(seed):
        from PIL import Image
        pixels=bytes((x*13+seed)%256 for x in range(32*32*3))
        picture=Image.frombytes("RGB",(32,32),pixels)
        stream=io.BytesIO()
        picture.save(stream,format="PNG")
        raw=stream.getvalue()
        assert len(raw)>=100 and raw.startswith(b"\x89PNG")
        return raw

    def test_per_image_labels_bind_original_and_revision_to_exact_binary_bytes(self):
        originals=[self._picture(seed) for seed in (1,2)]
        labels=[{"job_id":"original-job","path":"first.png",
                 "sha256":hashlib.sha256(originals[0]).hexdigest()},
                {"job_id":"revision-job","path":"second.png",
                 "sha256":hashlib.sha256(originals[1]).hexdigest()}]
        model=LocalCreativeModel(LocalModelSettings(model_id="bounded-local-fixture"))
        captured=[]
        class MockResponse:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,size):
                return json.dumps({"choices":[{"finish_reason":"stop",
                    "message":{"content":json.dumps({"action":"finish",
                        "arguments":{"summary":"Protocol-only picture mapping"},
                        "reason":"Fixture result, no artistic acceptance"})}}]}).encode()
        def intercept(request,*,timeout):
            captured.append(json.loads(request.data.decode("utf-8")))
            return MockResponse()
        context={"owner_brief":"Compare source and revised real pixels",
                 "picture_evidence":labels}
        with patch("studio_next.providers.urlopen",side_effect=intercept):
            result=model.decide_with_images(context,[("image/png",raw) for raw in originals])
            self.assertEqual(result["action"],"finish")
            self.assertEqual(len(captured),1)
            parts=captured[0]["messages"][1]["content"]
            self.assertEqual([p["type"] for p in parts],
                             ["text","text","image_url","text","image_url"])
            for index in range(2):
                caption=json.loads(parts[1+index*2]["text"])
                self.assertEqual(caption["image_index"],index)
                self.assertEqual(caption["job_id"],labels[index]["job_id"])
                self.assertEqual(caption["path"],labels[index]["path"])
                self.assertEqual(caption["sha256"],labels[index]["sha256"])
                uri=parts[2+index*2]["image_url"]["url"]
                self.assertEqual(uri.split(",",1)[0],"data:image/png;base64")
                self.assertEqual(base64.b64decode(uri.split(",",1)[1]),originals[index])
            with self.assertRaisesRegex(ValueError,"identity mismatch"):
                model.decide_with_images(context,[("image/png",originals[1]),
                                                  ("image/png",originals[0])])
            with self.assertRaisesRegex(ValueError,"count differs"):
                model.decide_with_images(context,[("image/png",originals[0])])
            self.assertEqual(len(captured),1)

    def test_generic_vision_without_a_creative_session_is_backward_compatible(self):
        raw=self._picture(3)
        model=LocalCreativeModel(LocalModelSettings(model_id="local-fixture"))
        class MockResponse:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,size):
                return b'{"choices":[{"finish_reason":"stop","message":{"content":"{}"}}]}'
        requests=[]
        def intercept(request,*,timeout):
            requests.append(json.loads(request.data.decode()))
            return MockResponse()
        with patch("studio_next.providers.urlopen",side_effect=intercept):
            self.assertEqual(model.decide_with_images({"task":"inspect"},[("image/png",raw)]),{})
        parts=requests[0]["messages"][1]["content"]
        self.assertEqual(json.loads(parts[1]["text"]),{"image_index":0,"image_mime":"image/png"})
        self.assertEqual(base64.b64decode(parts[2]["image_url"]["url"].split(",",1)[1]),raw)


    def test_real_tiny_png_is_not_rejected_by_an_arbitrary_size_floor(self):
        from PIL import Image
        stream=io.BytesIO()
        Image.new("RGB",(1,1),(12,23,34)).save(stream,format="PNG")
        pixel=stream.getvalue()
        self.assertLess(len(pixel),100)
        self.assertTrue(pixel.startswith(b"\x89PNG\r\n\x1a\n"))
        client=LocalCreativeModel(LocalModelSettings(model_id="tiny-frame-fixture"))
        class Reply:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,size):
                return b'{"choices":[{"finish_reason":"stop","message":{"content":"{}"}}]}'
        captured=[]
        def intercept(request,*,timeout):
            captured.append(json.loads(request.data.decode()))
            return Reply()
        with patch("studio_next.providers.urlopen",side_effect=intercept):
            self.assertEqual(client.decide_with_images({"frame":"one actual pixel"},
                [("image/png",pixel)]),{})
            with self.assertRaisesRegex(ValueError,"declared media type"):
                client.decide_with_images({},[("image/png",b"invalid"*20)])
            with self.assertRaisesRegex(ValueError,"declared media type"):
                client.decide_with_images({},[("image/jpeg",pixel)])
        self.assertEqual(len(captured),1)


if __name__=="__main__":
    unittest.main()
