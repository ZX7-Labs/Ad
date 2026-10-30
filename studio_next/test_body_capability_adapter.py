"""Physical trusted BODY catalog through universal small/large brain interface."""
import tempfile
import unittest

from studio_next.body_capability_adapter import (
    InstalledBodyAdapter, connect_installed_zx7_body)
from studio_next.capability_gateway import CapabilityExecutionError
from studio_next.capability_fabric import CapabilityContractError


class InstalledBodyGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_installed_timecode_is_found_and_executed_without_manual(self):
        with tempfile.TemporaryDirectory() as root:
            gateway = await connect_installed_zx7_body(root, allowed_access=("read", "write"))
            state = gateway._current().overview()
            self.assertGreater(state["operation_count"], 0)
            options = gateway.search("timecode format", limit=8)["matches"]
            self.assertTrue(options)
            target = next(x for x in options if x["id"].endswith("body.timecode_format"))
            contract = gateway.describe(target["id"], revision=state["revision"])
            self.assertEqual(contract["input_schema"]["properties"]["frame_index"]["type"],
                             "integer")
            arguments = {"frame_index": 48, "numerator": 24, "denominator": 1,
                         "drop_frame": False}
            actual = await gateway.invoke(target["id"], revision=state["revision"],
                                          inputs=arguments)
            self.assertEqual(actual["state"], "host_reported_success_unverified")
            self.assertEqual(actual["operation_id"], target["id"])
            self.assertTrue(actual["native_result"].content[0].text)
            self.assertEqual(gateway.evidence()[0]["access"], "read")

    async def test_read_grant_cannot_execute_write_tools(self):
        with tempfile.TemporaryDirectory() as root:
            gateway = await connect_installed_zx7_body(root, allowed_access=("read",))
            state = gateway._current().overview()
            options = gateway.search("asset vault", limit=8)["matches"]
            self.assertFalse(any(x["access"] == "write" for x in options))
            with self.assertRaises(CapabilityContractError):
                await gateway.invoke("zx7/body.asset_vault", revision=state["revision"],
                                     inputs={"source_witness": {"fake": True}})
            self.assertFalse(gateway.evidence())

    async def test_actual_body_works_without_exposing_uninstalled_renderers(self):
        with tempfile.TemporaryDirectory() as root:
            adapter = InstalledBodyAdapter(root, allowed_access=("read", "write"))
            grants = adapter.trusted_grants()
            real = await adapter.list_tools()
            self.assertEqual({t.name for t in real.tools}, set(grants))
            self.assertTrue(all(grant in ("read", "write") for grant in grants.values()))
            self.assertNotIn("body.invented_capability", grants)
            self.assertFalse(any("Markdown" in str(t) for t in real.tools))
            self.assertIsNone(real.nextCursor)


if __name__ == "__main__":
    unittest.main()
