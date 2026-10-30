"""Adversarial tests of domain-independent discovery; no neural creativity claims."""
import json
from types import SimpleNamespace
import unittest

from studio_next.capability_fabric import CapabilityFabric, CapabilityContractError


def tool(name, desc="", properties=None, **extra):
    return SimpleNamespace(name=name, description=desc,
        input_schema={"type": "object", "properties": properties or {}, **extra})


class CapabilityFabricTests(unittest.TestCase):
    def test_unbounded_future_domains_share_one_typed_interface(self):
        fabric = CapabilityFabric({
            "video": ([tool("create_project", "Create an editable native project",
                            {"name": {"type": "string"}}),
                       tool("trim_clip", "Trim video timeline clip")],
                      {"create_project": "write", "trim_clip": "write"}),
            "motion": ([tool("keyframe_curve", "Animate curves for 3D motion")],
                       {"keyframe_curve": "write"}),
            "photo": ([tool("mask_layer", "Create photo mask and design layers")],
                      {"mask_layer": "write"}),
        })
        self.assertEqual(fabric.count, 4)
        status = fabric.overview()
        self.assertEqual(status["sources"], {"motion": 1, "photo": 1, "video": 2})
        self.assertNotIn("input_schema", json.dumps(status))
        r = fabric.search("project create")
        self.assertEqual(r["matches"][0]["id"], "video/create_project")
        contract = fabric.describe("video/create_project", revision=r["revision"])
        self.assertEqual(contract["input_schema"]["properties"]["name"]["type"], "string")
        self.assertEqual(fabric.search("3D motion")["matches"][0]["id"],
                         "motion/keyframe_curve")
        self.assertFalse(fabric.search("imaginary teleportation")["matches"])

    def test_only_actual_installed_and_host_granted_apis_can_be_exposed(self):
        f = CapabilityFabric({
            "video": ([tool("open_project", "Open real native project"),
                       tool("delete_entire_project", "Destructive project deletion")],
                      {"open_project": "write"}),
        })
        self.assertEqual(f.count, 1)
        self.assertEqual(f.search("delete")["matches"], [])
        with self.assertRaisesRegex(CapabilityContractError, "Unknown or ungranted"):
            f.describe("video/delete_entire_project", revision=f.revision)

    def test_catalog_identity_changes_when_tools_or_permissions_change(self):
        old = CapabilityFabric({"video": ([tool("export_media", "Export final film",
                                            {"format": {"type": "string"}})],
                                         {"export_media": "write"})})
        updated = CapabilityFabric({"video": ([tool("export_media", "Export final film",
                                            {"format": {"type": "number"}}),
                                              tool("new_effect", "Color effect")],
                                             {"export_media": "read",
                                              "new_effect": "write"})})
        self.assertNotEqual(old.revision, updated.revision)
        self.assertEqual(updated.search("new effect")["matches"][0]["id"],
                         "video/new_effect")
        with self.assertRaisesRegex(CapabilityContractError, "Stale"):
            updated.describe("video/export_media", revision=old.revision)
        with self.assertRaisesRegex(CapabilityContractError, "Stale"):
            updated.resolve("video/export_media", revision=old.revision)

    def test_1000_tool_catalog_is_only_short_result_not_1000_md_pages(self):
        tools = [tool(f"operation_{i:04d}", f"Color grade and geometry control {i}",
                      {f"native_value_{i}": {"type": "number"}})
                 for i in range(1000)]
        fabric = CapabilityFabric({"future": (tools, {t.name: "write" for t in tools})})
        self.assertEqual(fabric.count, 1000)
        overview = json.dumps(fabric.overview(), separators=(",", ":"))
        self.assertLess(len(overview), 220)
        result = fabric.search("color grade", limit=6)
        self.assertEqual(len(result["matches"]), 6)
        self.assertTrue(result["has_more"])
        self.assertLess(len(json.dumps(result)), 1600)
        self.assertEqual(result, fabric.search("color grade", limit=6))

    def test_collision_and_ambiguous_source_are_rejected(self):
        with self.assertRaisesRegex(CapabilityContractError, "Duplicate"):
            CapabilityFabric({"a": ([tool("same"), tool("same")], {"same": "read"})})
        with self.assertRaisesRegex(CapabilityContractError, "Source"):
            CapabilityFabric({"../host": ([tool("read")], {"read": "read"})})

    def test_same_tool_name_in_separate_engines_is_not_ambiguous(self):
        f = CapabilityFabric({"video": ([tool("render", "Render movie")],
                                      {"render": "write"}),
                              "vector": ([tool("render", "Render vector image")],
                                         {"render": "write"})})
        self.assertEqual(f.count, 2)
        ids = [r["id"] for r in f.search("render", limit=8)["matches"]]
        self.assertEqual(set(ids), {"video/render", "vector/render"})

    def test_fail_closed_on_invented_ids_stale_revisions_and_untrusted_schema(self):
        f = CapabilityFabric({"video": ([tool("timeline", "Inspect current edit")],
                                      {"timeline": "read"})})
        for ident, rev in (("shell_exec", f.revision),
                           ("video/fake", f.revision),
                           ("video/timeline", "f" * 64)):
            with self.subTest(ident=ident):
                with self.assertRaises(CapabilityContractError):
                    f.resolve(ident, revision=rev)
        with self.assertRaisesRegex(CapabilityContractError, "schema"):
            CapabilityFabric({"video": ([
                SimpleNamespace(name="bad", description="Bad",
                                input_schema={"type": "object", "x": object()})],
                {"bad": "read"})})

    def test_bounded_query_and_exact_parameter_names(self):
        f = CapabilityFabric({"visual": ([tool("complex_design",
            "Advanced arbitrary color composition", {f"p{i}": {"type": "number"}
                                                    for i in range(50)})],
            {"complex_design": "write"})})
        params = f.search("composition")["matches"][0]["parameters_sample"]
        self.assertEqual(params, [f"p{i}" for i in range(6)])
        with self.assertRaisesRegex(CapabilityContractError, "bounded"):
            f.search("composition " * 30)
        with self.assertRaisesRegex(CapabilityContractError, "bounded"):
            f.search("visual", limit=100)

    def test_giant_schema_uses_explicit_safe_refusal_not_a_truncated_abi(self):
        f = CapabilityFabric({"video": ([tool("deep_fx", "Native transform",
            {"expression": {"type": "string", "description": "x" * 25000}})],
            {"deep_fx": "write"})})
        result = f.describe("video/deep_fx", revision=f.revision)
        self.assertTrue(result["schema_too_large"])
        self.assertNotIn("input_schema", result)

    def test_unicode_and_source_catalog_determinism(self):
        entry = tool("add_title", "हिन्दी शीर्षक बनाएं")
        f = CapabilityFabric({"video": ([entry], {"add_title": "write"})})
        g = CapabilityFabric({"video": ([entry], {"add_title": "write"})})
        self.assertEqual(f.revision, g.revision)
        self.assertEqual(f.search("शीर्षक")["matches"][0]["id"],
                         "video/add_title")


if __name__ == "__main__":
    unittest.main()
