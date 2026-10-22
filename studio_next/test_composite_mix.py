import json
import tempfile
import unittest
import shutil
import subprocess
import wave
from pathlib import Path

from studio_next.composite_mix import actual_composite_command,render_composition
from studio_next.media_vault import MediaVault


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),
                     'Native media decoder/encoder not installed; real integration runs separately')
class LayeredProductionCompositingTests(unittest.TestCase):
    def fixture(self,root):
        workspace=Path(root)
        vault=MediaVault(workspace/"vault")
        layers=[]
        for index in range(3):
            video=workspace/f"camera_{index}.mp4"
            subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
                "-f","lavfi","-i",f"color=c=0x{index+1}{index+2}3366:s=320x240:r=24:d=1.5",
                "-c:v","mpeg4","-q:v","5",str(video)],check=True,timeout=40)
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
        with wave.open(str(sound),"wb") as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000)
            wav.writeframes(bytes(2*16000*2))
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

    def test_physically_encoded_multilayer_movie_has_audio_and_rights(self):
        from studio_next.delivery_audit import _probe_details
        with tempfile.TemporaryDirectory() as root:
            plan,file,vault=self.fixture(root)
            # Deliberate modest actual media dimensions; no creative size preset.
            plan["canvas"].update(width=640,height=360,fps=24,duration=2)
            file.write_text(json.dumps(plan))
            destination=Path(root)/"physical-director-cut.mp4"
            result=render_composition(file,root,Path(root)/"vault",destination)
            proof=_probe_details(destination)
            self.assertTrue(result["verified_physically"])
            self.assertEqual((proof["width"],proof["height"]),(640,360))
            self.assertTrue(proof["audio_stream_present"])
            self.assertEqual(result["video_layers"],3)

    def test_original_keyframed_motion_and_alpha_are_derived_from_artist_frames(self):
        from studio_next.delivery_audit import _probe_details
        with tempfile.TemporaryDirectory() as root:
            film,source,vault=self.fixture(root)
            film["canvas"].update(width=640,height=360,fps=24,duration=2)
            graphic=film["video_layers"][1]
            # Isolate one moving artist-controlled layer so actual pixels
            # prove the object moved rather than merely encoding a filter.
            film["video_layers"]=[graphic]
            graphic["motion"]=[
                {"at_seconds":0,"x":12,"y":14},
                {"at_seconds":0.4,"x":90,"y":30},
                {"at_seconds":0.8,"x":180,"y":65}]
            graphic["fade_in_seconds"]=0.05
            graphic["fade_out_seconds"]=0.15
            command=actual_composite_command(film,root,vault,Path(root)/"keyframe-movie.mp4")
            graph=command[command.index("-filter_complex")+1]
            self.assertIn("if(lt(t,",graph)
            self.assertIn("fade=t=in",graph)
            self.assertIn("fade=t=out",graph)
            source.write_text(json.dumps(film))
            real=Path(root)/"keyframed-cinema.mp4"
            result=render_composition(source,root,Path(root)/"vault",real)
            meta=_probe_details(real)
            self.assertTrue(result["verified_physically"])
            self.assertEqual((meta["width"],meta["height"]),(640,360))
            self.assertTrue(meta["audio_stream_present"])
            def frame_pixel(t):
                pixels=subprocess.check_output([
                    "ffmpeg","-hide_banner","-loglevel","error",
                    "-ss",str(t),"-i",str(real),
                    "-frames:v","1","-f","rawvideo","-pix_fmt","rgb24","-"],
                    timeout=40)
                point=(40*640+40)*3
                return tuple(pixels[point:point+3])
            entering=frame_pixel(0.2)
            moved=frame_pixel(0.92)
            self.assertGreater(sum(abs(a-b) for a,b in zip(entering,moved)),20,
                "Keyframed scene did not visibly move in physically decoded movie frames")

    def test_invalid_keyframes_and_fake_model_effects_cannot_execute(self):
        with tempfile.TemporaryDirectory() as root:
            original,_,vault=self.fixture(root)
            layer=original["video_layers"][0]
            layer["motion"]=[{"at_seconds":0.8,"x":0,"y":0},
                             {"at_seconds":0.6,"x":100,"y":5}]
            with self.assertRaisesRegex(ValueError,"increasing"):
                actual_composite_command(original,root,vault,Path(root)/"invalid.mp4")
            layer["motion"]=[{"at_seconds":0,"x":0,"y":0}]
            layer["model_python"]="invent an actor with untrusted shell"
            with self.assertRaisesRegex(ValueError,"untrusted"):
                actual_composite_command(original,root,vault,Path(root)/"invalid.mp4")

    def test_mutable_checkout_swap_cannot_change_cas_sealed_camera_or_sound(self):
        from studio_next import composite_mix
        from studio_next.media_vault import sha256_file
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as root:
            plan,document,vault=self.fixture(root)
            plan["canvas"].update(width=320,height=240,fps=24,duration=2)
            document.write_text(json.dumps(plan),encoding="utf-8")
            original=Path(root)/"camera_0.mp4"
            saved=original.read_bytes()
            replacements=(Path(root)/"camera_1.mp4").read_bytes()
            hashes={layer["asset_id"] for layer in (
                plan["video_layers"]+plan["audio_tracks"])}
            actual_run=subprocess.run
            seen=[]
            def intercept(argv,**kwargs):
                if argv and argv[0]=="ffmpeg" and "-filter_complex" in argv:
                    files=[Path(argv[i+1]) for i,v in enumerate(argv[:-1])
                           if v=="-i"]
                    self.assertEqual(len(files),4)
                    for path in files:
                        self.assertIn(".zx7-owned-sources-",str(path))
                        self.assertFalse(path.stat().st_mode & 0o222)
                        self.assertIn(sha256_file(path),hashes)
                    seen.extend(files)
                    original.write_bytes(replacements)
                    try:
                        return actual_run(argv,**kwargs)
                    finally:
                        original.write_bytes(saved)
                return actual_run(argv,**kwargs)
            movie=Path(root)/"original-artist-mixed.mp4"
            with patch.object(composite_mix.subprocess,"run",side_effect=intercept):
                proof=render_composition(document,root,Path(root)/"vault",movie)
            self.assertTrue(proof["verified_physically"])
            self.assertTrue(proof["full_picture_and_sound_decoder_completed"])
            self.assertTrue(proof["sealed_original_cas_during_decode"])
            self.assertEqual(sha256_file(original),plan["video_layers"][0]["asset_id"])
            self.assertTrue(movie.is_file())
            self.assertEqual(len(seen),4)
            self.assertFalse(any(x.exists() for x in seen))
            self.assertFalse(list(Path(root).glob(".zx7-owned-sources-*")))

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
            self.assertFalse(result["verified_physically"])
            self.assertTrue(result["test_runner_or_probe_injected"])
            self.assertFalse(result["full_picture_and_sound_decoder_completed"])
            self.assertEqual(result["video_layers"],3)
            with self.assertRaises(ValueError):
                render_composition(file,root,Path(root)/"vault",output,
                 runner=fake_runner,probe=fake_probe)

if __name__=="__main__":unittest.main()
