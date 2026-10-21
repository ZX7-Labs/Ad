"""Actual professional compositor source by immutable cross-host media identity."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from studio_next.composite_mix import actual_composite_command,render_composition
from studio_next.film_finishing import finish_authorized_movie
from studio_next.body_materials import fingerprint_physical_inputs
from studio_next.media_vault import MediaVault
from studio_next.test_composite_mix import LayeredProductionCompositingTests
from studio_next.delivery_audit import _probe_details


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "Actual encoding and decoding needed for original media production")
class StableOriginalMediaURIIntegrationTests(unittest.TestCase):
    def test_original_multi_layer_and_music_edit_renders_from_same_asset_uris_on_machine(self):
        with tempfile.TemporaryDirectory() as workspace:
            root=Path(workspace)
            film,source,vault=LayeredProductionCompositingTests().fixture(root)
            film["canvas"].update(width=320,height=180,fps=24,duration=2)
            for layer in film["video_layers"]+film["audio_tracks"]:
                layer["source"]="zx7:sha256:"+layer["asset_id"]
            source.write_text(json.dumps(film),encoding="utf-8")
            output=root/"cas-edit.mp4"
            command=actual_composite_command(film,root,vault,output)
            self.assertEqual(command[0],"ffmpeg")
            self.assertNotIn("zx7:sha256:", " ".join(command))
            materials=fingerprint_physical_inputs("body.composite_mix",
                              {"plan":source.name,"out":output.name},root)
            physical={x["relative"] for x in materials}
            self.assertTrue(any(x.startswith("vault/objects/") for x in physical))
            self.assertIn(source.name,physical)
            result=render_composition(source,root,root/"vault",output)
            self.assertTrue(result["verified_physically"])
            probe=_probe_details(output)
            self.assertTrue(probe["audio_stream_present"])
            self.assertEqual(probe["width"],320)

    def test_invalid_media_uri_never_selects_unlicensed_video(self):
        with tempfile.TemporaryDirectory() as workspace:
            root=Path(workspace)
            film,source,vault=LayeredProductionCompositingTests().fixture(root)
            film["video_layers"][0]["source"]="zx7:sha256:"+("0"*64)
            with self.assertRaises(ValueError):
                actual_composite_command(film,root,vault,root/"invalid.mp4")
            source.write_text(json.dumps(film),encoding="utf-8")
            with self.assertRaises(ValueError):
                fingerprint_physical_inputs("body.composite_mix",
                    {"plan":source.name},root)
            self.assertFalse((root/"invalid.mp4").exists())

    def test_real_finishing_accepts_same_verified_cas_without_absolute_paths(self):
        with tempfile.TemporaryDirectory() as workspace:
            root=Path(workspace)
            film,source,vault=LayeredProductionCompositingTests().fixture(root)
            film["canvas"].update(width=320,height=180,fps=24,duration=2)
            source.write_text(json.dumps(film),encoding="utf-8")
            raw=root/"original_picture_and_sound.mp4"
            render_composition(source,root,root/"vault",raw)
            evidence=vault.ingest(raw,mime="video/mp4",
                rights="generated_original",source_type="trusted_renderer",
                source_id="actual-rendered-cas-test-original",
                evidence="Real original composed file tested by FFmpeg",
                owner_or_generator="installed-verified-original-renderer")
            spec={"media":{"source":"zx7:sha256:"+evidence["asset_id"],
                           "asset_id":evidence["asset_id"],
                           "attestation_id":evidence["attestation_id"]},
                  "ops":{"video_ops":[{"kind":"color_eq",
                                      "brightness":0.03,"contrast":1.1,
                                      "saturation":1.05,"gamma":1.0}],
                         "audio_ops":[]}}
            setting=root/"finish.json";setting.write_text(json.dumps(spec),encoding="utf-8")
            new=root/"final-master.mp4"
            report=finish_authorized_movie(setting,root,root/"vault",new)
            self.assertTrue(report["actual_encoded_movie_created"])
            self.assertTrue(_probe_details(new)["audio_stream_present"])
            materials=fingerprint_physical_inputs("body.film_finish",
                {"plan":"finish.json"},root)
            self.assertTrue(any(x["relative"].startswith("vault/objects/")
                                for x in materials))


if __name__=="__main__":
    unittest.main()
