import tempfile
import unittest
from pathlib import Path
from studio_next.edit_timeline import validate_edit, edit_ffmpeg_command


def sample():
    return {"format":{"width":720,"height":1280,"fps":24,"framing":"fit",
                      "background":"#101923"},
            "clips":[{"id":"vector","source":"vector.mp4",
                      "rights":"generated_original","audio":"preserve_source"},
                     {"id":"actual3d","source":"real3d.mp4",
                      "rights":"generated_original","audio":"intentional_silence"}]}


class MultiEngineTimelineTests(unittest.TestCase):
    def test_3d_and_2d_clips_retain_order_and_audio_intent(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/"vector.mp4").touch();(root/"real3d.mp4").touch()
            s=sample()
            self.assertIs(validate_edit(s,root),s)
            cmd=edit_ffmpeg_command(s,root,root/"film.mp4",
                                    source_info=[{"seconds":18.2,"audio":True},
                                                 {"seconds":31.7,"audio":False}])
            self.assertEqual(cmd[0],"ffmpeg")
            self.assertIn("concat=n=2:v=1:a=1"," ".join(cmd))
            self.assertIn("anullsrc"," ".join(cmd))
            self.assertIn("preserve_source",str(s))

    def test_not_forced_to_vertical_or_short_template(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/"vector.mp4").touch();(root/"real3d.mp4").touch()
            s=sample();s["format"].update(width=3840,height=1600,fps=48)
            self.assertIs(validate_edit(s,root),s)
            s["clips"]=[dict(original, id=f"unique{i}")
                        for i, original in enumerate(s["clips"]*20)]
            self.assertEqual(len(validate_edit(s,root)["clips"]),40)

    def test_no_unverified_external_or_malicious_paths(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);s=sample()
            s["clips"][0]["source"]="../../secrets.mp4"
            with self.assertRaises(ValueError):validate_edit(s,root,check_sources=False)
            s=sample();s["clips"][0]["source"]="/tmp/file.mp4"
            with self.assertRaises(ValueError):validate_edit(s,root,check_sources=False)

    def test_no_silent_removal_of_spoken_audio(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/"vector.mp4").touch();(root/"real3d.mp4").touch()
            s=sample()
            with self.assertRaisesRegex(ValueError,"cannot pretend narration"):
                edit_ffmpeg_command(s,root,root/"film.mp4",
                                    source_info=[{"seconds":4,"audio":False},
                                                 {"seconds":5,"audio":False}])

    def test_rights_unknown_and_invalid_structure_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            s=sample();s["clips"][0]["rights"]="found online"
            with self.assertRaises(ValueError):validate_edit(s,d,check_sources=False)
            s=sample();s["format"]["framing"]="whatever"
            with self.assertRaises(ValueError):validate_edit(s,d,check_sources=False)

    def test_unsupported_model_shell_not_forwarded(self):
        with tempfile.TemporaryDirectory() as d:
            s=sample();s["cmd"]="do something"
            with self.assertRaises(ValueError):validate_edit(s,d,check_sources=False)


if __name__ == "__main__":unittest.main()
