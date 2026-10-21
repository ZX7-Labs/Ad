import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from studio_next.body_integration import body_catalog,validate_witness,_require_authentic_generated_media_lineage


class TrustedCreativeBodyToolTests(unittest.TestCase):
    def test_true_apps_discovered_not_fake_installation(self):
        with tempfile.TemporaryDirectory() as root:
            c=body_catalog(root)
            tools={x["id"]:x for x in c.discover()}
            self.assertIn("body.inspect",tools)
            self.assertIn("body.render_edit",tools)
            self.assertIn("body.otio",tools)
            self.assertIn("body.vector_png",tools)
            self.assertIn("body.asset_vault",tools)
            self.assertNotIn("body.nonexistent",tools)
            self.assertEqual(tools["body.asset_vault"]["status"],"installed")

    def test_physical_media_witness_required_even_after_graph_recovery(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"artwork.png"
            p.write_bytes(b"\x89PNG\r\n\x1a\n"+b"x"*300)
            import hashlib
            result={"path":str(p),"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),
                    "bytes":p.stat().st_size}
            self.assertTrue(validate_witness("body.vector_png",result))
            p.write_bytes(b"not same artwork"*100)
            self.assertFalse(validate_witness("body.vector_png",result))

    def test_model_cannot_issue_rights_certificate_for_arbitrary_file(self):
        original={"id":"old","tool_id":"body.asset_vault","depends_on":[],
                  "inputs":{"source":"found-online.mp4","rights":"generated_original",
                            "evidence":"trust me"}}
        with self.assertRaisesRegex(ValueError,"cannot invent license"):
            _require_authentic_generated_media_lineage({"tool_graph":[original]})
        fabricated={"id":"vault","tool_id":"body.asset_vault",
                    "depends_on":["inspect"],
                    "inputs":{"source_witness":{"$node_output":"inspect"}}}
        read={"id":"inspect","tool_id":"body.inspect",
              "inputs":{"source":"unauthorized.mp4"},"depends_on":[]}
        with self.assertRaisesRegex(ValueError,"trusted renderer dependency"):
            _require_authentic_generated_media_lineage(
                {"tool_graph":[read,fabricated]})
        trusted={"id":"edit","tool_id":"body.render_edit","inputs":{},
                 "depends_on":[]}
        valid={"id":"vault","tool_id":"body.asset_vault",
               "depends_on":["edit"],
               "inputs":{"source_witness":{"$node_output":"edit"}}}
        self.assertIsNone(_require_authentic_generated_media_lineage(
            {"tool_graph":[trusted,valid]}))

    def test_no_model_supplied_shell_or_untrusted_media_rights(self):
        with tempfile.TemporaryDirectory() as root:
            c=body_catalog(root)
            with self.assertRaises(ValueError):
                c.invoke("body.asset_vault",{"source":"../../../private.mp4",
                    "mime":"video/mp4","rights":"found online",
                    "source_type":"licensed_library","source_id":"lie",
                    "evidence":"no","issuer":"model"},allowed_access={"write"})

if __name__=="__main__":unittest.main()
