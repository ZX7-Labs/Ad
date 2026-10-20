import json
import tempfile
import unittest
from pathlib import Path
from studio_next.silent_audio import make_silent_timing


class SilentAudioTests(unittest.TestCase):
    def test_only_explicit_silence_is_allowed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            p=root/"project.json"
            project={"voice":"no_voice","scenes":[
                {"id":"intro","narration":"","min_seconds":1.3},
                {"id":"end","narration":"","min_seconds":.8}]}
            p.write_text(json.dumps(project))
            results=make_silent_timing(p,root/"audio")
            self.assertEqual(len(results),2)
            self.assertTrue((root/"audio"/"voice-01.wav").is_file())
            project["scenes"][0]["narration"]="Hello"
            p.write_text(json.dumps(project))
            with self.assertRaisesRegex(ValueError,"Cannot silently"):
                make_silent_timing(p,root/"disallowed")
            project["scenes"][0]["narration"]=""
            project["voice"]="M3"
            p.write_text(json.dumps(project))
            with self.assertRaisesRegex(ValueError,"director-selected"):
                make_silent_timing(p,root/"disallowed")


if __name__ == "__main__":
    unittest.main()
