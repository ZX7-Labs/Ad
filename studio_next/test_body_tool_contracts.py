import tempfile
import unittest
from studio_next.body_tool_contracts import real_operation_schema
from studio_next.contracts import ToolSpec
from studio_next.registry import ToolCatalog


class ShortOnDemandRealCreativeToolContractsTests(unittest.TestCase):
    def test_editor_reads_only_specific_tool_abi_not_full_markdown(self):
        schema=real_operation_schema("body.composite_mix",["plan","out"])
        self.assertEqual(set(schema["properties"]),{"plan","out"})
        self.assertEqual(schema["properties"]["plan"]["type"],"string")
        self.assertFalse(schema["additionalProperties"])
        self.assertNotIn("default",str(schema))

    def test_runtime_rejects_wrong_argument_types_and_unapproved_shell_keys(self):
        catalog=ToolCatalog()
        schema=real_operation_schema("body.render_edit",["edit","out"])
        actual=[]
        catalog.register(ToolSpec("body.render_edit","Creative editing",
            "Headless installed film editor","write",operation_schema=schema),
            lambda data:actual.append(data) or {"checked":True})
        for forged in (
            {"edit":"original.json","out":"final.mp4","shell":"rm -rf /"},
            {"edit":13,"out":"film.mp4"},
            {"edit":"project.json","out":False},
            {"edit":"project.json"}):
            with self.assertRaises((ValueError,TypeError)):
                catalog.invoke("body.render_edit",forged,allowed_access={"write"})
        self.assertEqual(actual,[])
        self.assertTrue(catalog.invoke("body.render_edit",
            {"edit":"original.json","out":"film.mp4"},
            allowed_access={"write"})["checked"])

    def test_optional_physical_original_assets_are_explicitly_typed(self):
        three=real_operation_schema("body.blender3d",["scene_json","out"])
        self.assertIn("assets_root",three["properties"])
        audio=real_operation_schema("body.full_decode",["source"])
        self.assertEqual(audio["properties"]["expected"]["type"],"object")
        with self.assertRaisesRegex(ValueError,"unknown"):
            real_operation_schema("body.false",["arbitrary_ai_shell"])

if __name__=="__main__":unittest.main()
