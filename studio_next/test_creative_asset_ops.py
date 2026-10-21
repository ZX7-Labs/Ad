import tempfile
import unittest
from pathlib import Path
from studio_next.creative_asset_ops import validate_original_svg_art,rasterize_original_svg


class DesignerOriginalThumbnailOpsTests(unittest.TestCase):
    def test_no_style_hardcode_and_safely_parse_complex_original_art(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"custom.svg"
            p.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 3840 2160">'
              '<defs><linearGradient id="original"><stop stop-color="#ff03a0"/></linearGradient></defs>'
              '<path d="M 0 100 L 300 250" fill="url(#original)"/>'
              '<text x="50" y="100">Unique artist headline</text></svg>')
            # Reusing a local symbolic gradient is art, not fetching a remote file.
            # The standalone SVG source passes if no external deps exist.
            with self.assertRaises(ValueError):
                validate_original_svg_art(p)
            p.write_text('<svg xmlns="http://www.w3.org/2000/svg">'
                  '<path d="M 0 100 L 300 250" fill="#ff03a0"/>'
                  '<text x="50" y="100">Unique artist headline</text></svg>')
            self.assertTrue(validate_original_svg_art(p)["self_contained"])

    def test_external_art_svg_script_and_network_fetch_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"unsafe.svg"
            for content in (
                '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
                '<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.org/unknown.png"/></svg>',
                '<svg xmlns="http://www.w3.org/2000/svg" onclick="hack()"/>',
                '<!DOCTYPE svg [<!ENTITY a SYSTEM "file:///etc/passwd">]><svg xmlns="http://www.w3.org/2000/svg"/>'):
                p.write_text(content)
                with self.assertRaises(ValueError):
                    validate_original_svg_art(p)

    def test_no_unsupported_invented_svg_renderer_or_overwrite(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"fine.svg"
            p.write_text('<svg xmlns="http://www.w3.org/2000/svg"><circle r="50"/></svg>')
            with self.assertRaisesRegex(RuntimeError,"Inkscape"):
                rasterize_original_svg(p,Path(root)/"result.png",width=500,
                  height=800,finder=lambda tool:None)
            with self.assertRaises(ValueError):
                rasterize_original_svg(p,Path(root)/"result.png",width=0,
                  height=800,finder=lambda tool:"/fake/inkscape")

if __name__=="__main__":unittest.main()
