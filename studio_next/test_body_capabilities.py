import tempfile
import unittest
from studio_next.body_capabilities import (
    operational_tool_summary,explain_operational_tool,concise_body_status)


class InteractiveBrainConnectedBodyTests(unittest.TestCase):
    def test_model_discovers_real_apps_from_short_typed_interface_not_long_md(self):
        with tempfile.TemporaryDirectory() as root:
            tools=operational_tool_summary(root)
            self.assertTrue(any(x["tool_id"]=="body.asset_vault" for x in tools))
            self.assertTrue(all(x["status"]=="genuinely_installed" for x in tools))
            self.assertFalse(any("markdown" in str(x).lower() for x in tools))

    def test_detailed_schema_is_lazy_only_for_selected_tool(self):
        with tempfile.TemporaryDirectory() as root:
            tool=explain_operational_tool(root,"body.asset_vault")
            self.assertEqual(tool["status"],"ready_for_execution_trial")
            self.assertIn("source",tool["operation_schema"]["required"])
            with self.assertRaises(ValueError):
                explain_operational_tool(root,"model_fake_hollywood")

    def test_billing_and_gpu_runtime_are_not_fabricated(self):
        with tempfile.TemporaryDirectory() as root:
            data=concise_body_status(root)
            self.assertIn("physically_enabled_generators",data)
            self.assertFalse(data["claimed_complete_premium_studio"])
            self.assertTrue(data["one_model_can_discover_and_choose_without_reading_documentation"])

if __name__=="__main__":unittest.main()
