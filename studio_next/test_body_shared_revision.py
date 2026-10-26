"""CAS decoder implementation changes must invalidate every affected exact render stage."""
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_next.body_integration import _trusted_body_revision

SEALED_RENDER_TOOLS=(
    "body.retime","body.sequence_cuts","body.timeline_revision",
    "body.otio_owned_export","body.otio_owned_import",
    "body.composite_mix","body.film_finish","body.color_lut",
    "body.loudness"
)
COMPLETE_DECODE_RENDER_TOOLS=(
    "body.render_edit_owned","body.retime","body.sequence_cuts",
    "body.timeline_revision","body.composite_mix","body.film_finish",
    "body.color_lut"
)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                    "Versioned real codec and probe binaries required")
class SharedSourceCodecRevisionProof(unittest.TestCase):
    def _assert_native_cache_invalidation(self,name,codec_module):
        original=_trusted_body_revision(name)
        real=Path.read_bytes
        def altered(path):
            content=real(path)
            if path.name==codec_module:
                return content+b"\n# changed shared native source verification ABI\n"
            return content
        with patch.object(Path,"read_bytes",altered):
            invalidated=_trusted_body_revision(name)
        self.assertNotEqual(original,invalidated,
            name+" would replay a stale previously verified movie after "+codec_module+" changed")

    def test_every_shared_cas_reader_change_invalidates_associated_editor_and_sound(self):
        for tool in SEALED_RENDER_TOOLS:
            with self.subTest(tool=tool):
                self._assert_native_cache_invalidation(tool,"composite_mix.py")

    def test_critical_full_decoder_change_invalidates_exact_native_witnesses(self):
        for tool in COMPLETE_DECODE_RENDER_TOOLS:
            with self.subTest(tool=tool):
                self._assert_native_cache_invalidation(tool,"production_qc.py")

if __name__=="__main__":
    unittest.main()
