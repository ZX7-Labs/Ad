import json
import tempfile
import unittest
from pathlib import Path

from studio_next.film_finishing import build_finishing_filters,finish_authorized_movie
from studio_next.media_vault import MediaVault


class IndependentFilmFinishingTests(unittest.TestCase):
    def test_creative_artist_controls_numeric_color_grade_and_audio_loudness(self):
        directions={"video_ops":[{"kind":"color_eq","brightness":.03,
                "contrast":1.25,"saturation":1.48,"gamma":1.2},
                {"kind":"sharpen","strength":.22}],
            "audio_ops":[{"kind":"gain","db":-3.2},
                {"kind":"loudnorm","integrated_lufs":-18,
                 "true_peak_dbfs":-1.5,"loudness_range":12}]}
        v,a=build_finishing_filters(directions,has_audio=True)
        self.assertEqual(len(v),2)
        self.assertIn("contrast=1.25",v[0])
        self.assertIn("I=-18.0:TP=-1.5:LRA=12.0",a[1])

    def test_no_model_supplied_filter_strings_or_sound_hallucinations(self):
        with self.assertRaisesRegex(ValueError,"Unregistered"):
            build_finishing_filters({"video_ops":[
                {"kind":"shell","command":"rm -rf /"}],"audio_ops":[]},has_audio=False)
        with self.assertRaisesRegex(ValueError,"Cannot create"):
            build_finishing_filters({"video_ops":[],"audio_ops":[
                {"kind":"gain","db":5}]},has_audio=False)

    def test_real_source_is_a_verified_media_vault_object(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"original.mp4"
            p.write_bytes(b"sample source bytes"*100)
            # This test bypasses expensive actual ffprobe only through a
            # trusted injected physical probe; real integration never does.
            from unittest.mock import patch
            with patch("studio_next.media_vault.verify_media_container",return_value={}):
                rights=MediaVault(Path(root)/"vault")
                ref=rights.ingest(p,mime="video/mp4",rights="owner_supplied",
                   source_type="owner_upload",source_id="owner",
                   evidence="Owner-supplied original",
                   owner_or_generator="owner")
            config={"media":{"source":p.name,
                "asset_id":ref["asset_id"],"attestation_id":ref["attestation_id"]},
                "ops":{"video_ops":[{"kind":"sharpen","strength":.35}],
                       "audio_ops":[]}}
            f=Path(root)/"finish.json"
            f.write_text(json.dumps(config))
            result_path=Path(root)/"final.mp4"
            def fake_probe(file):
                return {"width":400,"height":300,"duration_seconds":5.0,
                        "audio_stream_present":False}
            def fake_runner(cmd,check,timeout):
                Path(cmd[-1]).write_bytes(b"test encoded output"*100)
            result=finish_authorized_movie(f,root,Path(root)/"vault",result_path,
                                          runner=fake_runner,probe=fake_probe)
            self.assertTrue(result["actual_encoded_movie_created"])
            self.assertTrue(result_path.exists())

if __name__=="__main__":
    unittest.main()
