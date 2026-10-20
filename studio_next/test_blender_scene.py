import copy
import json
import tempfile
import unittest
from pathlib import Path
from studio_next.blender_scene import validate_blender_shot, Invalid3DShot


def sample():
    return json.loads((Path(__file__).parent/"fixtures"/"three_dimensional_shot.json").read_text())


class BlenderContractTests(unittest.TestCase):
    def test_original_3d_camera_lighting_and_animation(self):
        s=sample()
        self.assertIs(validate_blender_shot(s),s)
        self.assertEqual(s["objects"][0]["type"],"custom_mesh")
        self.assertEqual(s["camera"]["animate_location"][-1]["frame"],s["frames"])

    def test_no_forced_2d_or_fixed_scene_length(self):
        s=sample()
        s["frames"]=3600
        s["camera"]["animate_location"][-1]["frame"]=3600
        s["objects"][1]["animate"]["rotation_degrees"][-1]["frame"]=3600
        self.assertIs(validate_blender_shot(s),s)

    def test_render_code_injection_is_not_scene_data(self):
        s=sample();s["__import__"]="os.system('rm -rf /')"
        with self.assertRaises(Invalid3DShot):validate_blender_shot(s)
        s=sample();s["objects"][0]["script"]="danger"
        with self.assertRaises(Invalid3DShot):validate_blender_shot(s)

    def test_camera_cannot_point_at_itself(self):
        s=sample();s["camera"]["target"]=s["camera"]["location"]
        with self.assertRaisesRegex(Invalid3DShot,"own origin"):validate_blender_shot(s)

    def test_mesh_faces_must_be_valid(self):
        s=sample();s["objects"][0]["faces"]=[[0,1,999]]
        with self.assertRaisesRegex(Invalid3DShot,"invalid polygon"):validate_blender_shot(s)

    def test_model_asset_requires_rights_and_local_existing_file(self):
        s=sample();s["objects"][0].update(type="licensed_glb",asset="../../keys.glb",rights="owner_supplied")
        s["objects"][0].pop("vertices");s["objects"][0].pop("faces")
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(Invalid3DShot):validate_blender_shot(s,verified_assets_root=d)
            s["objects"][0]["asset"]="missing.glb"
            with self.assertRaises(Invalid3DShot):validate_blender_shot(s,verified_assets_root=d)

    def test_keyframes_are_strict_and_in_shot(self):
        s=sample();s["objects"][1]["animate"]["rotation_degrees"][1]["frame"]=1
        with self.assertRaisesRegex(Invalid3DShot,"increasing"):validate_blender_shot(s)
        s=sample();s["camera"]["animate_location"][-1]["frame"]=s["frames"]+1
        with self.assertRaisesRegex(Invalid3DShot,"within shot"):validate_blender_shot(s)

    def test_finite_values_and_real_materials(self):
        s=sample();s["objects"][0]["location"][0]=float("nan")
        with self.assertRaises(Invalid3DShot):validate_blender_shot(s)
        s=sample();s["objects"][0]["material"]="imaginary_product"
        with self.assertRaisesRegex(Invalid3DShot,"unknown material"):validate_blender_shot(s)

    def test_can_use_new_geometry_and_light_combinations(self):
        s=sample()
        s["objects"][0]["type"]="cube"
        s["objects"][0].pop("vertices")
        s["objects"][0].pop("faces")
        s["lights"].append({"id":"accent","type":"SPOT","location":[0,2,3],
            "rotation_degrees":[0,0,0],"energy":300,"color":[1,.5,.3]})
        self.assertIs(validate_blender_shot(s),s)


if __name__=="__main__":
    unittest.main()
