import json
import tempfile
import unittest
from pathlib import Path

from studio_next.editorial_interchange import export_editable_timeline


class IndustryEditableTimelineTests(unittest.TestCase):
    def test_real_open_timeline_io_roundtrip_if_tool_installed(self):
        try:import opentimelineio as otio
        except ImportError:self.skipTest("Optional actual OpenTimelineIO not yet installed")
        with tempfile.TemporaryDirectory() as root:
            base=Path(root)
            assets=[]
            for i in range(18):
                p=base/f"director-shot-{i}.mp4"
                p.write_bytes(("artist original "+str(i)).encode()*100)
                assets.append({"id":f"shot-{i}","source":p.name,
                    "rights":"generated_original","audio":"intentional_silence"})
            spec={"format":{"width":2048,"height":858,"fps":48,
                            "framing":"fill","background":"#0a0b0c"},
                  "clips":assets}
            (base/"edit.json").write_text(json.dumps(spec))
            actual=export_editable_timeline(base/"edit.json",base,base/"cut.otio",
                            probe=lambda _:{"seconds":2.33,"audio":False})
            self.assertEqual(len(actual["clips"]),18)
            project=otio.adapters.read_from_file(str(base/"cut.otio"))
            self.assertEqual(project.metadata["zx7"]["director_delivery"]["width"],2048)
            self.assertEqual(len(project.video_tracks()[0]),18)
            self.assertEqual(len(project.audio_tracks()),1)
            self.assertEqual(len(project.audio_tracks()[0]),18)
            self.assertTrue(all(isinstance(item,otio.schema.Gap)
                for item in project.audio_tracks()[0]))
            self.assertTrue(all("source_artifact_sha256" in x.metadata["zx7"]
                               for x in project.video_tracks()[0]))
            with self.assertRaises(FileExistsError):
                export_editable_timeline(base/"edit.json",base,base/"cut.otio",
                                         probe=lambda _:{"seconds":2.33,"audio":False})

    def test_genuine_production_audio_remains_editable_not_discarded(self):
        try:import opentimelineio as otio
        except ImportError:self.skipTest("Optional actual OpenTimelineIO not yet installed")
        with tempfile.TemporaryDirectory() as root:
            base=Path(root)
            source=base/"camera-performance.mp4"
            source.write_bytes(b"actual-video-asset-fixture"*40)
            original={"format":{"width":1080,"height":1920,"fps":30,
                  "framing":"fit","background":"#0a0b0c"},
                  "clips":[{"id":"human-performance","source":source.name,
                        "rights":"appropriately_licensed","audio":"preserve_source"}]}
            (base/"source.json").write_text(json.dumps(original))
            export_editable_timeline(base/"source.json",base,base/"picture-and-sound.otio",
                           probe=lambda _:{"seconds":3.0,"audio":True})
            project=otio.adapters.read_from_file(str(base/"picture-and-sound.otio"))
            recorded=project.audio_tracks()[0][0]
            self.assertIsInstance(recorded,otio.schema.Clip)
            self.assertEqual(recorded.metadata["zx7"]["audio_director_choice"],
                             "preserve_source")
            self.assertEqual(recorded.media_reference.target_url,source.as_uri())

    def test_refuse_fake_nonindustry_extension_and_unverified_license(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"source.mp4";p.write_bytes(b"media"*300)
            spec={"format":{"width":1920,"height":1080,"fps":25,
                "framing":"fit","background":"#010101"},
                  "clips":[{"id":"a","source":p.name,
                            "audio":"intentional_silence","rights":"found on internet"}]}
            (Path(root)/"input.json").write_text(json.dumps(spec))
            with self.assertRaises((ValueError,RuntimeError)):
                export_editable_timeline(Path(root)/"input.json",root,Path(root)/"export.otio",
                                         probe=lambda _:{"seconds":5,"audio":False})

if __name__=="__main__":unittest.main()
