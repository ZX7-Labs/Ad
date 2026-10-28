"""Real-byte multi-frame visual selection for model-directed revision review.

Selection permits before/after and temporal frame comparison without treating
pixel inputs as proof that an LLM understands motion or cinematic quality.
"""
import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_next.body_service import LocalBodyCoordinator


@unittest.skipUnless(importlib.util.find_spec("PIL") is not None,
                     "Pillow is required for physically encoded PNG fixtures")
class CreativePictureSelectionTests(unittest.TestCase):
    def setUp(self):
        from PIL import Image
        self.temp=tempfile.TemporaryDirectory()
        self.coordinator=LocalBodyCoordinator(self.temp.name,creative_model=object())
        folder=self.coordinator._workspace("film")
        folder.mkdir(parents=True,exist_ok=True)
        self.paths={}
        for index in range(6):
            path=folder/("frame-"+str(index)+".png")
            Image.new("RGB",(20,16),(index*37,10,170-index*15)).save(path)
            self.paths[path.name]=path
        self.state={"workspace_id":"film","pictures":[]}
        self.signal=type("ReadOnlySignal",(),{"observe":lambda _self,identity: {"job_id":identity}})()

    def tearDown(self):
        self.coordinator.close()
        self.temp.cleanup()

    def _inspect(self,job):
        return {"job_id":job,"workspace_id":"other" if job=="foreign" else "film"}

    def _media(self,job,name):
        path=self.paths[name]
        data=path.read_bytes()
        return {"path":path,"mime":"image/png","bytes":len(data),
                "sha256":hashlib.sha256(data).hexdigest()}

    def _read(self,job,name):
        return self.coordinator.creative_sessions._dispatch(
            self.state,self.signal,{"action":"read_picture",
                "arguments":{"job_id":job,"path":name},
                "reason":"Select an authenticated before/after frame"})

    def test_four_real_frames_can_be_compared_with_eviction_and_deduplication(self):
        with patch.object(self.coordinator,"inspect",side_effect=self._inspect),\
             patch.object(self.coordinator,"inspect_media",side_effect=self._media):
            for index in range(5):
                result=self._read("original" if index<3 else "revised",
                                  "frame-"+str(index)+".png")
            self.assertEqual(result["selected_picture_count"],4)
            self.assertEqual(result["evicted_previous_selections"],
                             [{"job_id":"original","path":"frame-0.png"}])
            self.assertEqual([p["path"] for p in self.state["pictures"]],
                             ["frame-1.png","frame-2.png","frame-3.png","frame-4.png"])
            images=self.coordinator.creative_sessions._pictures(self.state)
            self.assertEqual(len(images),4)
            self.assertTrue(all(mime=="image/png" and data.startswith(b"\\x89PNG")
                                for mime,data in images))
            duplicate=self._read("original","frame-2.png")
            self.assertEqual(duplicate["selected_picture_count"],4)
            self.assertEqual(duplicate["evicted_previous_selections"],[])
            self.assertEqual([p["path"] for p in self.state["pictures"]],
                             ["frame-1.png","frame-3.png","frame-4.png","frame-2.png"])

    def test_mutated_frame_or_foreign_workspace_never_replaces_provenance(self):
        with patch.object(self.coordinator,"inspect",side_effect=self._inspect),\
             patch.object(self.coordinator,"inspect_media",side_effect=self._media):
            self._read("original","frame-0.png")
            self._read("revised","frame-1.png")
            original=list(self.state["pictures"])
            with self.assertRaisesRegex(PermissionError,"another session workspace"):
                self._read("foreign","frame-2.png")
            self.assertEqual(self.state["pictures"],original)
            # A valid new source cannot hide a modified earlier witness.
            self.paths["frame-0.png"].write_bytes(b"tampered-original-pixels")
            with self.assertRaisesRegex(ValueError,"Observed picture bytes changed"):
                self._read("revised","frame-3.png")
            self.assertEqual(self.state["pictures"],original)
            with self.assertRaisesRegex(ValueError,"Previously observed picture identity changed"):
                self._read("original","frame-0.png")
            self.assertEqual(self.state["pictures"],original)


if __name__=="__main__":
    unittest.main()
