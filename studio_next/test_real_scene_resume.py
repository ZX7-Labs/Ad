import tempfile
import unittest
from pathlib import Path

from studio_next.execute_film import (
    _scene_clip_signature,_persist_verified_visual,_resume_verified_visual)
from studio_next.stage_checkpoint import DurableStageStore


class RealRenderedSceneResumeTests(unittest.TestCase):
    def test_existing_film_clip_skips_rebuild_only_when_exact_hashes_match(self):
        with tempfile.TemporaryDirectory() as root:
            scene=Path(root)/"scene-001"
            scene.mkdir()
            clip=scene/"actual-camera.mp4"
            clip.write_bytes(b"verified-real-encoded-movie-evidence"*20)
            store=DurableStageStore(Path(root)/"checkpoints")
            input_=_scene_clip_signature(
                {"id":"real_scene","duration_seconds":4.2},
                {"engine":"actual_visual_generator","scene_job":{"visual":"true"}},
                {"format":{"width":1080,"height":1920},"voice":"M3"},
                {"identity":"Real note"},"physical_tool_revision")
            _persist_verified_visual(store,"s1",input_,scene,clip,
                {"seconds":4.2,"audio":False},"intentional_silence")
            def actual_probe(path):
                self.assertEqual(path,clip.resolve())
                return {"seconds":4.2,"audio":False}
            restored=_resume_verified_visual(store,"s1",input_,scene,probe=actual_probe)
            self.assertEqual(restored["seconds"],4.2)
            self.assertEqual(restored["clip"],clip.resolve())
            different=dict(input_,installed_renderer_code_revision="changed")
            self.assertIsNone(_resume_verified_visual(store,"s1",different,
                                                      scene,probe=actual_probe))

    def test_reject_tampered_movie_instead_of_reusing_wrong_clip(self):
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root)/"scene";folder.mkdir()
            clip=folder/"same.mp4"
            clip.write_bytes(b"verified clip"*100)
            store=DurableStageStore(Path(root)/"checkpoints")
            stage={"true_film":"same"}
            _persist_verified_visual(store,"s",stage,folder,clip,
                {"seconds":1.0,"audio":True},"original narrator")
            clip.write_bytes(b"different movie bytes"*100)
            with self.assertRaisesRegex(ValueError,"bytes changed"):
                _resume_verified_visual(store,"s",stage,folder,
                                       probe=lambda _:{"seconds":1.0,"audio":True})

    def test_real_media_attributes_checked_after_resume(self):
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root)/"shot";folder.mkdir()
            p=folder/"clip.mp4";p.write_bytes(b"original clip"*100)
            store=DurableStageStore(Path(root)/"save")
            _persist_verified_visual(store,"one",{"shot":"original"},
                folder,p,{"seconds":5.0,"audio":True},"M3")
            with self.assertRaisesRegex(ValueError,"physical encoder evidence"):
                _resume_verified_visual(store,"one",{"shot":"original"},folder,
                    probe=lambda _:{"seconds":3.0,"audio":False})


if __name__=="__main__":
    unittest.main()
