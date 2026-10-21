import json
import tempfile
import unittest
from pathlib import Path
from studio_next.creative_tool_registry import (
    probe_creative_tools,creative_tool_inventory,write_inventory)


class AutonomousArtToolDiscoveryTests(unittest.TestCase):
    def test_installed_tools_are_measured_not_claimed(self):
        finder=lambda app:{'blender':'/usr/bin/blender','ffmpeg':'/usr/bin/ffmpeg',
                           'ffprobe':'/usr/bin/ffprobe','krita':'/opt/krita'}.get(app)
        inventory=creative_tool_inventory(finder=finder)
        available={s["tool_id"]:s for s in inventory["actual_installed_tools"]}
        self.assertIn("blender",available)
        self.assertIn("ffmpeg",available)
        self.assertIn("krita",available)
        self.assertTrue(available["blender"]["can_render_in_zx7_now"])
        self.assertFalse(available["krita"]["can_render_in_zx7_now"])
        self.assertFalse(any(s["tool_id"]=="inkscape" for s in available))
        self.assertTrue(inventory["creative_scope_not_restricted_to_catalog"])

    def test_binary_present_does_not_claim_artist_or_full_generation(self):
        entries=probe_creative_tools(finder=lambda item:"/usr/bin/"+item)
        self.assertTrue(all(entry["installed_on_current_machine"] for entry in entries))
        self.assertFalse(any(x["can_make_arbitrary_cinematic_output"] for x in entries))
        self.assertTrue(all(x["requires_authorized_assets_and_production_validation"] for x in entries))

    def test_no_tool_presence_implies_no_tool_can_render(self):
        entries=creative_tool_inventory(finder=lambda name:None)
        self.assertEqual(entries["actual_installed_tools"],[])
        self.assertFalse(any(t["can_render_in_zx7_now"] for t in entries["not_installed_tools"]))

    def test_honest_capabilities_saved_for_one_brain(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"tools.json"
            write_inventory(path,finder=lambda name:"/usr/bin/"+name if name=="inkscape" else None)
            record=json.loads(path.read_text())
            available=record["actual_installed_tools"]
            self.assertEqual([x["tool_id"] for x in available],["inkscape"])
            self.assertFalse(available[0]["can_render_in_zx7_now"])
            self.assertIn("thumbnails",available[0]["creative_capabilities"])

    def test_tool_catalog_is_not_an_advertised_render_pipeline(self):
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            probe_creative_tools(finder=lambda x:None,specs=(
                {"id":"blender","executables":["blender"],"craft":[],"license":"GPL"},
                {"id":"blender","executables":["blender"],"craft":[],"license":"GPL"}))


if __name__=="__main__":
    unittest.main()
