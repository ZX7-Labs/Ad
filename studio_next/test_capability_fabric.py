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

    async def test_complete_cursor_paged_catalog_supports_late_future_capability(self):
        class Paged:
            async def list_tools(self, *, cursor=None):
                if cursor is None:
                    return SimpleNamespace(tools=[tool("first", "Native render")],
                                           nextCursor="opaque-stage-1")
                if cursor == "opaque-stage-1":
                    return SimpleNamespace(tools=[tool("future_fx", "Native future VFX")],
                                           nextCursor=None)
                raise AssertionError("Caller invented a cursor")
        state = await CapabilityFabric.from_connections({
            "video": (Paged(), {"first": "read", "future_fx": "write"})})
        self.assertEqual(state.count, 2)
        self.assertEqual(state.search("future VFX")["matches"][0]["id"], "video/future_fx")

    async def test_cursorless_adapter_and_repeated_cursor_fail_closed(self):
        class NonPaging:
            async def list_tools(self):
                return SimpleNamespace(tools=[tool("first")], nextCursor="next")
        class Cycling:
            async def list_tools(self, *, cursor=None):
                return SimpleNamespace(tools=[tool("first")], nextCursor="same-token")
        for session in (NonPaging(), Cycling()):
            with self.subTest(session=type(session).__name__), self.assertRaises(
                CapabilityContractError):
                await CapabilityFabric.from_connections({
                    "video": (session, {"first": "read"})})

    async def test_large_paged_catalog_rejects_unbounded_page_stream(self):
        class Giant:
            async def list_tools(self, *, cursor=None):
                return SimpleNamespace(tools=[
                    tool(f"tool_{cursor or 0}_{i}") for i in range(3000)],
                    nextCursor="next" if cursor is None else None)
        with self.assertRaisesRegex(CapabilityContractError, "budget"):
            await CapabilityFabric.from_connections({
                "video": (Giant(), {})})



    def test_trusted_machine_effect_frontier_is_cross_domain_and_not_autoplay(self):
        photo = [tool("new_canvas", "Create a layered original photo canvas"),
                 tool("paint", "Paint pixels on an editable canvas")]
        motion = [tool("new_scene", "Create a 3D animation scene"),
                  tool("keyframe", "Animate native object motion")]
        f = CapabilityFabric({
            "photo": (photo, {"new_canvas": "write", "paint": "write"},
                      {"paint": ["document_open"]},
                      {"new_canvas": ["document_open"]}),
            "motion": (motion, {"new_scene": "write", "keyframe": "write"},
                       {"keyframe": ["document_open"]},
                       {"new_scene": ["document_open"]}),
        })
        possible = f.affordance_frontier(trusted_facts={"document_open": False},
                                        namespace="motion")
        self.assertEqual([x["id"] for x in possible["matches"]],
                         ["motion/new_scene"])
        self.assertTrue(possible["effects_are_possibilities_not_verified_results"])
        self.assertTrue(possible["facts_are_host_attested"])
        self.assertFalse(any("keyframe" in x["id"] for x in possible["matches"]))
        self.assertEqual(f.affordance_frontier(
            trusted_facts={"document_open": True})["matches"], [])

    def test_future_effect_contracts_are_versioned_and_untrusted_claims_rejected(self):
        ops = [tool("make", "Make editable project")]
        grants = {"make": "write"}
        before = CapabilityFabric({"graphics": (ops, grants)})
        after = CapabilityFabric({"graphics": (
            ops, grants, {}, {"make": ["project_open"]})})
        self.assertNotEqual(before.revision, after.revision)
        for effects in ({"missing": ["project_open"]},
                        {"make": ["not a valid fact"]},
                        {"make": ["project_open", "project_open"]},
                        {"make": [["not_a_string"]]}):
            with self.subTest(effects=effects), self.assertRaises(CapabilityContractError):
                CapabilityFabric({"graphics": (ops, grants, {}, effects)})


if __name__ == "__main__":
    unittest.main()
