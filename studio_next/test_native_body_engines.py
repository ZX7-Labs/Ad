import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_next.native_body_engines import render_original_blender


class DirectNativeBodyEngineTests(unittest.TestCase):
    def test_refuses_uninstalled_renderer_even_for_valid_art(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"original.json";p.write_text("{}")
            with patch("studio_next.native_body_engines.shutil.which",return_value=None):
                with self.assertRaisesRegex(RuntimeError,"Real Blender"):
                    render_original_blender(p,Path(root)/"movie.mp4")

    def test_rejects_model_suggested_commands_unrelated_to_3d_scene(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"malicious.json"
            p.write_text('{"__python__":"rm -rf /", "art":"incorrect"}')
            with patch("studio_next.native_body_engines.shutil.which",
                       return_value="/usr/bin/installed"):
                with self.assertRaises(ValueError):
                    render_original_blender(p,Path(root)/"original.mp4")

if __name__=="__main__":unittest.main()
