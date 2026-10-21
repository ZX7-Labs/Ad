import json
import tempfile
import unittest
from pathlib import Path

from studio_next.composite_mix import actual_composite_command,render_composition
from studio_next.media_vault import MediaVault


class LayeredProductionCompositingTests(unittest.TestCase):
    def fixture(self,root):
        workspace=Path(root)
        vault=MediaVault(workspace/"vault")
        layers=[]
        for index in range(3):
            video=workspace/f"camera_{index}.mp4"
            video.write_bytes(b"actual source footage"*200+bytes([index]))
            ref=vault.ingest(video,mime="video/mp4",rights="owner_supplied",
                source_type="owner_upload",source_id=f"owner-{index}",
                evidence="Original owner source fixture",
                owner_or_generator="owner")
            layers.append({"id":f"layer_{index}","source":video.name,
                "asset_id":ref["asset_id"],"attestation_id":ref["attestation_id"],
                "start":index*0.125,"source_in":0,"duration":1,
                "x":index*70,"y":-index*20,"width":200,"height":140,
                "opacity":1-index*.25})
        sound=workspace/"narration.wav"
        sound.write_bytes(b"recorded owner voice"*80)
        sound_ref=vault.ingest(sound,mime="audio/wav",rights="owner_supplied",
            source_type="owner_upload",source_id="owner_audio",
            evidence="Owner supplied this real voice track",owner_or_generator="owner")
        edit={"canvas":{"width":1080,"height":1920,"fps":24,
               "duration":2,"background":"#142A34"},
              "video_layers":layers,
              "audio_tracks":[{"id":"voice","source":sound.name,
                   "asset_id":sound_ref["asset_id"],
                   "attestation_id":sound_ref["attestation_id"],
                   "start":0.45,"source_in":0,"duration":1.0,"gain_db":-6.1}]}
        file=workspace/"composite.json"
        file.write_text(json.dumps(edit))
        return edit,file,vault

    def test_creative_engine_chooses_layers_style_camera_and_audio(self):
        with tempfile.TemporaryDirectory() as root:
            plan,_,vault=self.fixture(root)
            cmd=actual_composite_command(plan,root,vault,Path(root)/"film.mp4")
            graph=cmd[cmd.index("-filter_complex")+1]
            self.assertIn("overlay=x=140:y=-40",graph)
            self.assertIn("colorchannelmixer=aa=0.5",graph)
            self.assertIn("volume=-6.1dB",graph)
            self.assertIn("adelay=450|450",graph)
            self.assertEqual(cmd[0],"ffmpeg")

    def test_one_unverified_clip_or_changed_byte_blocks_edit(self):
        with tempfile.TemporaryDirectory() as root:
            plan,_,vault=self.fixture(root)
            f=Path(root)/"camera_1.mp4"
            f.write_bytes(b"corrupted")
            with self.assertRaisesRegex(ValueError,"Source bytes differ"):
                actual_composite_command(plan,root,vault,Path(root)/"render.mp4")

    def test_director_decides_34_visual_layers_not_template_limit(self):
        with tempfile.TemporaryDirectory() as root:
            plan,_,vault=self.fixture(root)
            plan["video_layers"]=[dict(plan["video_layers"][index%3],
                                  id=f"actual_artist_layer_{index}") for index in range(34)]
            command=actual_composite_command(plan,root,vault,Path(root)/"cinema.mp4")
            self.assertIn("overlay=",command[command.index("-filter_complex")+1])
            self.assertEqual(command[command.index("-filter_complex")+1].count("]overlay="),34)

    def test_real_mixer_output_must_match_movie_bytes(self):
        with tempfile.TemporaryDirectory() as root:
            plan,file,vault=self.fixture(root)
            output=Path(root)/"unique.mp4"
            def fake_runner(argv,check,timeout):
                Path(argv[-1]).write_bytes(b"encoded bytes"*100)
            def fake_probe(path):
                self.assertTrue(path.is_file())
                return {"width":1080,"height":1920,
                        "duration_seconds":2.0,"audio_stream_present":True}
            result=render_composition(file,root,Path(root)/"vault",output,
                 runner=fake_runner,probe=fake_probe)
            self.assertTrue(result["verified_physically"])
            self.assertEqual(result["video_layers"],3)
            with self.assertRaises(ValueError):
                render_composition(file,root,Path(root)/"vault",output,
                 runner=fake_runner,probe=fake_probe)

if __name__=="__main__":unittest.main()
