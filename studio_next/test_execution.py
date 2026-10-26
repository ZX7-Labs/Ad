import copy
import unittest

from studio_next.contracts import ToolSpec
from studio_next.execution import execute_graph
from studio_next.registry import ToolCatalog


def film():
    return {
        "project": {"creative_intent": "An unhurried original travel scene"},
        "assets": [{"id": "clip", "status": "verified",
                    "rights": "owner_supplied", "location": "asset://verified/clip"}],
        "shots": [{"id": "scene_a", "purpose": "Convey a real detail",
                   "asset_refs": ["clip"], "fact_refs": ["paper"],
                   "duration_seconds": 31.5}],
        "tool_graph": [
            {"id": "make", "tool_id": "safe.make", "purpose": "Create a scene asset",
             "inputs": {"scene": "scene_a"}, "depends_on": []},
            {"id": "finish", "tool_id": "safe.finish", "purpose": "Assemble edit",
             "inputs": {"media": {"$node_output": "make"}}, "depends_on": ["make"]},
        ],
    }


def catalog(calls, *, final_failure=False, paid=False):
    tools = ToolCatalog()
    def make(data):
        calls.append(("make", data))
        return {"asset": "generated_original", "count": 1}
    def finish(data):
        calls.append(("finish", data))
        if final_failure:
            raise RuntimeError("encoder failed")
        return {"result": data["media"]}
    tools.register(ToolSpec("safe.make", "scene create", "Installed test action", "read"),
                   make)
    tools.register(ToolSpec("safe.finish", "edit finishing", "Installed test action",
                            "paid" if paid else "read"), finish)
    return tools


class ExecutionTests(unittest.TestCase):
    def run_graph(self, ir, tools, **kw):
        return execute_graph(ir, tools, fact_ids={"paper"}, **kw)

    def test_dependent_outputs_flow_through_registered_tools(self):
        calls = []
        result = self.run_graph(film(), catalog(calls))
        self.assertEqual(result.status, "graph_steps_completed")
        self.assertEqual(result.completed_steps, ["make", "finish"])
        self.assertEqual(calls[1][1]["media"], {"asset": "generated_original", "count": 1})
        self.assertEqual(len(result.output_digests["finish"]), 64)
        self.assertIn("not verified video", result.claim)

    def test_reference_to_undeclared_node_blocks_before_any_tool_runs(self):
        calls = []
        ir = film()
        ir["tool_graph"][1]["depends_on"] = []
        outcome = self.run_graph(ir, catalog(calls))
        self.assertEqual(outcome.status, "blocked")
        self.assertEqual(calls, [])

    def test_reference_object_cannot_smuggle_extra_model_data(self):
        calls = []
        ir = film()
        ir["tool_graph"][1]["inputs"]["media"]["__model_command"] = "rm -rf /"
        result = self.run_graph(ir, catalog(calls))
        self.assertEqual(result.status, "blocked")
        self.assertEqual(calls, [])

    def test_nested_reference_and_independent_steps(self):
        calls = []
        ir = film()
        ir["tool_graph"][1]["inputs"] = {"layers": [
            {"asset": {"$node_output": "make"}, "style": {"zoom": 1.2}}]}
        result = self.run_graph(ir, catalog(calls))
        # A real trusted adapter must validate its own schema: here the test
        # finisher expects media, demonstrating a safe partial failure.
        self.assertEqual(result.status, "failed_partial")
        self.assertEqual(result.completed_steps, ["make"])

    def test_paid_tool_not_available_without_grant(self):
        calls = []
        result = self.run_graph(film(), catalog(calls, paid=True))
        self.assertEqual(result.status, "blocked")
        self.assertEqual(calls, [])

    def test_budget_blocks_every_side_effect(self):
        calls = []
        result = self.run_graph(film(), catalog(calls), max_steps=1)
        self.assertEqual(result.status, "blocked")
        self.assertEqual(calls, [])

    def test_failure_does_not_continue_or_claim_finished_film(self):
        calls = []
        result = self.run_graph(film(), catalog(calls, final_failure=True))
        self.assertEqual(result.status, "failed_partial")
        self.assertEqual(result.completed_steps, ["make"])
        self.assertNotIn("finish", result.output_digests)

    def test_cycle_and_unknown_fact_block_before_execution(self):
        for mutation in ("cycle", "invented_fact"):
            calls = []
            ir = film()
            if mutation == "cycle":
                ir["tool_graph"][0]["depends_on"] = ["finish"]
            else:
                ir["shots"][0]["fact_refs"] = ["invented_sales_claim"]
            result = self.run_graph(ir, catalog(calls))
            self.assertEqual(result.status, "blocked")
            self.assertEqual(calls, [])

    def test_unavailable_runner_is_not_assumed_installed(self):
        calls = []
        tools = catalog(calls)
        tools.register(ToolSpec("needs.3d", "render 3d", "GPU", "read",
                                status="needs_setup"), None)
        ir = film()
        ir["tool_graph"][1]["tool_id"] = "needs.3d"
        result = self.run_graph(ir, tools)
        self.assertEqual(result.status, "blocked")
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
