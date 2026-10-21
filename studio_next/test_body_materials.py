import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_next.body_materials import fingerprint_physical_inputs


class FilmSourceBytesInvalidateOutdatedArtTests(unittest.TestCase):
    def test_installed_font_replacement_invalidates_unchanged_art_source(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as fonts:
            base=Path(root)
            font=Path(fonts)/"original-typeface.ttf"
            font.write_bytes(b"original installed font bytes")
            (base/"art.json").write_text(json.dumps({"assets":[{"artwork":{
                "items":[{"type":"text","font":"Artist Selected Family","text":"Title"}]}}]}))
            with patch("studio_next.body_materials.resolve_artist_font",return_value=font):
                before=fingerprint_physical_inputs("body.motion2d",
                    {"original_film_ir":"art.json"},base)
                font.write_bytes(b"different installed font bytes")
                after=fingerprint_physical_inputs("body.motion2d",
                    {"original_film_ir":"art.json"},base)
            self.assertNotEqual(before,after)
            self.assertEqual(before[0],after[0])

    def test_actual_motion_renderer_source_change_invalidates_native_tool_revision(self):
        import shutil
        from studio_next.body_integration import _trusted_body_revision
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            self.skipTest("Actual media executables needed for cache revision")
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary)
            repository=Path(__file__).resolve().parents[1]
            for name in ("studio_next","motion_studio"):
                shutil.copytree(repository/name,base/name)
            with patch("studio_next.body_integration.__file__",str(base/"studio_next/body_integration.py")):
                before=_trusted_body_revision("body.motion2d")
                renderer=base/"motion_studio/render.py"
                renderer.write_text(renderer.read_text()+"\n# distinct actually installed renderer revision\n")
                after=_trusted_body_revision("body.motion2d")
            self.assertNotEqual(before,after)

    def test_changed_original_footage_always_invalidates_edit(self):
        with tempfile.TemporaryDirectory() as root:
            base=Path(root)
            film=base/"camera.mp4"
            film.write_bytes(b"camera scene A")
            cut=base/"editor.json"
            cut.write_text(json.dumps({"clips":[{"source":"camera.mp4"}]}))
            first=fingerprint_physical_inputs("body.render_edit",{"edit":"editor.json"},base)
            self.assertEqual(len(first),2)
            film.write_bytes(b"other filmed acting")
            changed=fingerprint_physical_inputs("body.render_edit",{"edit":"editor.json"},base)
            self.assertNotEqual(first,changed)
            self.assertEqual(first[0]["relative"],"camera.mp4")

    def test_original_audio_and_multilayer_composite_bytes_are_bound(self):
        with tempfile.TemporaryDirectory() as root:
            base=Path(root)
            for p in ("actor.mov","music.wav"):
                (base/p).write_bytes(p.encode()*30)
            plan={"video_layers":[{"source":"actor.mov"}],
                  "audio_tracks":[{"source":"music.wav"}]}
            (base/"composite.json").write_text(json.dumps(plan))
            proof=fingerprint_physical_inputs("body.composite_mix",
                       {"plan":"composite.json","out":"will-not-exist.mp4"},base)
            self.assertEqual({x["relative"] for x in proof},
                {"actor.mov","music.wav","composite.json"})

    def test_changed_font_audio_blender_assets_propagate(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)
            assets=p/"assets";assets.mkdir()
            (assets/"actor.glb").write_bytes(b"original 3D mesh"*100)
            (p/"scene.json").write_text(json.dumps({"object":"Original"})
)
            a=fingerprint_physical_inputs("body.blender3d",
                         {"scene_json":"scene.json","assets_root":"assets"},p)
            (assets/"actor.glb").write_bytes(b"new 3D mesh"*100)
            b=fingerprint_physical_inputs("body.blender3d",
                         {"scene_json":"scene.json","assets_root":"assets"},p)
            self.assertNotEqual(a,b)

    def test_missing_source_or_path_traversal_never_passes(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError,"escape"):
                fingerprint_physical_inputs("body.asset_vault",
                   {"source":"../secret.mp4"},root)
            with self.assertRaisesRegex(ValueError,"Missing"):
                fingerprint_physical_inputs("body.asset_vault",
                   {"source":"nonexistent.mp4"},root)
            with self.assertRaisesRegex(ValueError,"needs trusted"):
                fingerprint_physical_inputs("unknown.untrusted",
                   {"source":"secret.mp4"},root)

if __name__=="__main__":
    unittest.main()
