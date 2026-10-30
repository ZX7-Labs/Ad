"""Adversarial tests of domain-independent discovery; no neural creativity claims."""
import json
from types import SimpleNamespace
import unittest

from studio_next.capability_fabric import (
    CapabilityFabric, CapabilityContractError, LiveCapabilityRegistry)


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

    def test_actual_2b_single_word_create_query_does_not_choose_wrong_project_api(self):
        source = [
            tool("create_asset_folder", "Preview or create native asset-panel folders"),
            tool("create_project", "Create a real editable native project"),
            tool("create_timeline", "Create a video timeline inside an open project"),
        ]
        f = CapabilityFabric({"editor": (source, {x.name: "write" for x in source})})
        broad = f.search("create", limit=1)
        self.assertTrue(broad["requires_refinement"])
        self.assertFalse(broad["matches"])
        self.assertIn("editor/create_project",
                      [x["id"] for x in broad["candidate_examples"]])
        specific = f.search("create project", limit=3)
        self.assertFalse(specific.get("requires_refinement", False))
        self.assertEqual(specific["matches"][0]["id"], "editor/create_project")

    def test_1000_tools_use_inverted_postings_not_full_catalog_scan(self):
        tools = [tool(f"job_{idx:04d}",
                      "Render creative composition" if idx != 911
                      else "Private specialty foobar_only_native_capability")
                 for idx in range(1000)]
        f = CapabilityFabric({"studio": (tools, {x.name: "read" for x in tools})})
        focused = f.search("foobar_only_native_capability", limit=1)
        self.assertEqual(len(focused["matches"]), 1)
        self.assertEqual(focused["matches"][0]["id"], "studio/job_0911")
        self.assertEqual(focused["candidates_examined"], 1)
        self.assertLess(len(json.dumps(focused)), 800)
        broad = f.search("render", limit=6)
        self.assertEqual(broad["candidates_examined"], 999)
        self.assertTrue(broad["has_more"])
        self.assertEqual(broad, f.search("render", limit=6))

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


    def test_explicit_trusted_state_preconditions_not_model_guessing(self):
        sources = {"motion": ([tool("create_motion", "Create keyframe animation"),
                               tool("render_animation", "Render animation output")],
                              {"create_motion": "write", "render_animation": "write"},
                              {"render_animation": ["project_open", "assets_cleared"]})}
        f = CapabilityFabric(sources)
        entry = f.search("render animation")["matches"][0]
        self.assertEqual(entry["requires"], ["project_open", "assets_cleared"])
        status = f.check_prerequisites(entry["id"], revision=f.revision,
                                      trusted_facts={"project_open": False})
        self.assertFalse(status["admissible"])
        self.assertEqual(status["unsatisfied"], ["project_open"])
        self.assertEqual(status["unknown_state"], ["assets_cleared"])
        approved = f.check_prerequisites(entry["id"], revision=f.revision,
            trusted_facts={"project_open": True, "assets_cleared": True})
        self.assertTrue(approved["admissible"])
        changed = CapabilityFabric({"motion": (sources["motion"][0],
            sources["motion"][1], {"render_animation": ["project_open"]})})
        self.assertNotEqual(changed.revision, f.revision)

    def test_untrusted_or_invalid_precondition_metadata_fails_closed(self):
        operations = [tool("export", "Export movie")]
        grants = {"export": "write"}
        for bad in ({"export": [["fake"]]}, {"export": ["project_open", "project_open"]},
                    {"export": ["not a fact"]}, {"unknown": ["project_open"]}):
            with self.subTest(value=bad), self.assertRaises(CapabilityContractError):
                CapabilityFabric({"video": (operations, grants, bad)})
        f = CapabilityFabric({"video": (operations, grants, {"export": ["project_open"]})})
        for facts in ({"project_open": "yes"}, {"project_open": 1}, [True]):
            with self.subTest(facts=facts), self.assertRaises(CapabilityContractError):
                f.check_prerequisites("video/export", revision=f.revision, trusted_facts=facts)

    def test_tool_schema_snapshot_does_not_mutate_if_source_or_brain_changes_it(self):
        properties = {"name": {"type": "string"}}
        native = tool("create", "Make project", properties)
        fabric = CapabilityFabric({"video": ([native], {"create": "write"})})
        revision = fabric.revision
        properties["name"]["type"] = "number"
        one = fabric.describe("video/create", revision=revision)
        self.assertEqual(one["input_schema"]["properties"]["name"]["type"], "string")
        one["input_schema"]["properties"]["name"]["type"] = "integer"
        again = fabric.describe("video/create", revision=revision)
        self.assertEqual(again["input_schema"]["properties"]["name"]["type"], "string")
        self.assertEqual(fabric.revision, revision)


class LiveMachineDiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_new_software_operation_is_seen_from_real_live_discovery_next_refresh(self):
        class Machine:
            def __init__(self):
                self.tools = [tool("create_project", "Create actual native project")]
            async def list_tools(self):
                return SimpleNamespace(tools=self.tools, nextCursor=None)
        session = Machine()
        binding = {"video": (session, {"create_project": "write"})}
        before = await CapabilityFabric.from_connections(binding)
        self.assertEqual(before.count, 1)
        session.tools.append(tool("new_vector_effect", "Vector graphic motion effect"))
        binding["video"] = (session, {"create_project": "write",
                                     "new_vector_effect": "write"})
        after = await CapabilityFabric.from_connections(binding)
        self.assertEqual(after.count, 2)
        self.assertNotEqual(after.revision, before.revision)
        self.assertEqual(after.search("graphic motion")["matches"][0]["id"],
                         "video/new_vector_effect")
        with self.assertRaisesRegex(CapabilityContractError, "Stale"):
            after.describe("video/create_project", revision=before.revision)

    async def test_versioned_mcp_complete_envelope_is_supported_without_false_tools(self):
        class Latest:
            async def list_tools(self):
                return SimpleNamespace(result={
                    "resultType": "complete",
                    "tools": [tool("apply_motion", "Animate original motion")],
                    "requestState": "opaque-cursor-custody-not-a-model-tool"})
        f = await CapabilityFabric.from_connections({
            "motion": (Latest(), {"apply_motion": "write"})})
        self.assertEqual(f.count, 1)
        self.assertEqual(f.search("animate motion")["matches"][0]["id"],
                         "motion/apply_motion")
        self.assertNotIn("requestState", json.dumps(f.overview()))

    async def test_versioned_noncomplete_mcp_tool_result_never_exposes_partial_grants(self):
        class Partial:
            async def list_tools(self):
                return SimpleNamespace(result={"resultType": "incomplete",
                    "tools": [tool("fake_early")], "requestState": "not-finished"})
        with self.assertRaisesRegex(CapabilityContractError, "not a completed"):
            await CapabilityFabric.from_connections({
                "motion": (Partial(), {"fake_early": "write"})})

    async def test_paginated_or_ungranted_sources_never_claim_complete_discovery(self):
        class Paged:
            async def list_tools(self):
                return SimpleNamespace(tools=[tool("first")], nextCursor="another-page")
        with self.assertRaisesRegex(CapabilityContractError, "paginated"):
            await CapabilityFabric.from_connections({"video": (Paged(), {"first": "read"})})


class AtomicCapabilityRegistryTests(unittest.IsolatedAsyncioTestCase):
    async def test_unannounced_future_tool_appears_on_host_refresh_not_in_model_prose(self):
        class Runtime:
            def __init__(self, name):
                self.operations = [tool("render", "Render actual native output")]
            async def list_tools(self):
                return SimpleNamespace(tools=self.operations)
        video, vfx = Runtime("video"), Runtime("vfx")
        registry = LiveCapabilityRegistry({"video": (video, {"render": "write"})})
        with self.assertRaises(CapabilityContractError):
            registry.snapshot()
        before = await registry.refresh()
        old_revision = before["revision"]
        self.assertEqual(before["sources"], {"video": 1})
        vfx.operations.append(tool("particle_simulation", "Simulate dynamic VFX particles"))
        new = await registry.refresh(host_connections={
            "video": (video, {"render": "write"}),
            "vfx": (vfx, {"render": "write", "particle_simulation": "write"})})
        self.assertEqual(new["sources"], {"vfx": 2, "video": 1})
        self.assertNotEqual(new["revision"], old_revision)
        self.assertEqual(registry.snapshot().search("particles")["matches"][0]["id"],
                         "vfx/particle_simulation")
        with self.assertRaisesRegex(CapabilityContractError, "Stale"):
            registry.select("video/render", revision=old_revision)

    async def test_failed_refresh_does_not_erase_existing_working_capabilities(self):
        class Engine:
            def __init__(self):
                self.fail = False
            async def list_tools(self):
                if self.fail:
                    raise ConnectionError("Native process unavailable")
                return SimpleNamespace(tools=[tool("create", "Create project")])
        engine = Engine()
        registry = LiveCapabilityRegistry({"video": (engine, {"create": "write"})})
        before = await registry.refresh()
        engine.fail = True
        with self.assertRaises(ConnectionError):
            await registry.refresh()
        self.assertEqual(registry.snapshot().revision, before["revision"])
        self.assertEqual(registry.snapshot().count, 1)
        with self.assertRaises(CapabilityContractError):
            await registry.refresh(host_connections={})
        self.assertEqual(registry.snapshot().revision, before["revision"])



if __name__ == "__main__":
    unittest.main()
