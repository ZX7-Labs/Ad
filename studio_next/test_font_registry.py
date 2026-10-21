import tempfile
import unittest
from pathlib import Path
from studio_next.font_registry import resolve_artist_font


class TrulyInstalledArtisticTypographyTests(unittest.TestCase):
    def test_can_choose_arbitrary_specific_installed_font(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"CustomDirector.otf"
            path.write_bytes(b"test font asset")
            result=resolve_artist_font("Custom Director",which=lambda name:"/usr/bin/fc-match",
                match=lambda call:"Custom Director\n"+str(path)+"\n")
            self.assertEqual(result,str(path))

    def test_do_not_replace_original_typeface_without_consent(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"WrongFont.ttf"
            path.write_bytes(b"test different typeface")
            with self.assertRaisesRegex(RuntimeError,"do not silently substitute"):
                resolve_artist_font("Premium Custom",which=lambda name:"/usr/bin/fc-match",
                     match=lambda call:"Wrong Family\n"+str(path)+"\n")

    def test_model_cannot_supply_untrusted_font_paths_or_subprocess(self):
        for name in ("../../etc/passwd","$(curl evil)","", "/tmp/arbitrary.ttf"):
            with self.assertRaises(ValueError):
                resolve_artist_font(name,which=lambda _:None)

if __name__=="__main__":unittest.main()
