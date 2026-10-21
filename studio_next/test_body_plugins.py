import unittest
from types import SimpleNamespace
from studio_next.body_plugins import discover_enabled_body_plugins
from studio_next.contracts import ToolSpec

class BodyPluginsBoundaryTests(unittest.TestCase):
    def test_no_accidental_or_model_authorized_installation(self):
        self.assertEqual(discover_enabled_body_plugins(approved=[],entry_source=[]),[])

    def test_trusted_adapter_registers_only_after_admin_consent_and_probe(self):
        spec=ToolSpec("artist.procedural","real geometry","Independent full 3D engine","write")
        class Plugin:
            revision="actual-software-and-source-sha"
            idempotent=True
            def probe(self):return True
            def run(self,inputs):return {"real":inputs}
        Plugin.spec=spec
        entry=SimpleNamespace(name="artist.procedural",load=lambda:Plugin)
        results=discover_enabled_body_plugins(
            approved=["artist.procedural"],entry_source=[entry])
        self.assertEqual(len(results),1)
        self.assertTrue(results[0][4])
        self.assertEqual(results[0][1]({"scene":"genuine"}),{"real":{"scene":"genuine"}})

    def test_missing_installed_software_fails_without_falsely_exposing_body(self):
        with self.assertRaisesRegex(ValueError,"uninstalled"):
            discover_enabled_body_plugins(
                approved=["artist.notinstalled"],entry_source=[])

    def test_invalid_id_and_mismatched_adapter_cannot_run(self):
        with self.assertRaisesRegex(ValueError,"Unsafe"):
            discover_enabled_body_plugins(approved=["../../untrusted"],entry_source=[])
        class Impostor:
            spec=ToolSpec("different.id","video","Other tool","write")
            revision="claimed-source"
            idempotent=True
            def probe(self):return True
            def run(self,data):return data
        e=SimpleNamespace(name="artist.wrong",load=lambda:Impostor)
        with self.assertRaisesRegex(ValueError,"false tool"):
            discover_enabled_body_plugins(approved=["artist.wrong"],entry_source=[e])

if __name__=="__main__":unittest.main()
