import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest
from studio_next.test_body_visual_graph import plan,field


@unittest.skipUnless(importlib.util.find_spec("OpenEXR") and importlib.util.find_spec("numpy"),"Actual float EXR decoder required")
class FloatVisualGraphTests(unittest.TestCase):
    def document(self):
        doc=plan([field("hdr","4*u","-.2","2",".5")])
        doc["render"].update(format="exr32",rgb_range="preserve_float")
        return doc

    def test_float_export_keeps_negative_and_over_one_values_exactly(self):
        import numpy as np
        from studio_next.body_visual_render import render_visual_graph
        from studio_next.body_visual_exr import read_float_rgba
        from studio_next.body_visual_graph import VisualBudget
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/"original.json";p.write_text(json.dumps(self.document()))
            result=render_visual_graph(p,root,root/"vault",root/"master.exr")
            data=read_float_rgba(root/"master.exr",budget=VisualBudget(),alpha_mode="associated")
            self.assertEqual(data.dtype,np.float32)
            self.assertTrue(result["decoded_rgba_exact"])
            self.assertEqual(result["explicitly_clipped_rgb_components"],0)
            np.testing.assert_array_equal(data[0,0],np.array([.03125,-.1,1,.5],dtype=np.float32))
            np.testing.assert_array_equal(data[0,-1],np.array([1.96875,-.1,1,.5],dtype=np.float32))

    def test_float_source_roundtrip_preserves_hdr_and_custody(self):
        from studio_next.body_visual_render import render_visual_graph
        from studio_next.media_vault import MediaVault
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);original=root/"original.json";original.write_text(json.dumps(self.document()))
            first=render_visual_graph(original,root,root/"vault",root/"source.exr")
            ref=MediaVault(root/"vault").ingest(root/"source.exr",mime="image/x-exr",rights="owner_supplied",
                source_type="owner_upload",source_id="float-fixture",evidence="Original exact float pixel test",owner_or_generator="test-owner")
            doc=self.document();doc["nodes"]=[{"id":"source","op":"source","inputs":{},"params":{
                "media":{"source":"source.exr","asset_id":ref["asset_id"],"attestation_id":ref["attestation_id"]},
                "kind":"image","color_space":"linear_srgb","alpha_mode":"associated","frame":0}}]
            doc["output"]="source";p=root/"reimport.json";p.write_text(json.dumps(doc))
            second=render_visual_graph(p,root,root/"vault",root/"reimport.exr")
            self.assertEqual(first["rendered_frame_pixel_sha256"],second["rendered_frame_pixel_sha256"])
            self.assertEqual(second["source_assets"],1)

    def test_channel_selection_alpha_and_memory_budget_are_explicit(self):
        import OpenEXR,numpy as np
        from studio_next.body_visual_exr import read_float_rgba
        from studio_next.body_visual_graph import VisualBudget
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"passes.exr"
            channels={"Beauty.R":np.full((4,5),4,np.float32),"Beauty.G":np.full((4,5),.2,np.float32),
                      "Beauty.B":np.full((4,5),-1,np.float32),"Coverage":np.full((4,5),.25,np.float32)}
            with OpenEXR.File({"compression":OpenEXR.ZIP_COMPRESSION,"type":OpenEXR.scanlineimage},channels) as f:f.write(str(p))
            mapping=dict(zip("rgba",("Beauty.R","Beauty.G","Beauty.B","Coverage")))
            values=read_float_rgba(p,budget=VisualBudget(),alpha_mode="straight",channels=mapping)
            np.testing.assert_allclose(values[0,0],[1,.05,-.25,.25])
            with self.assertRaisesRegex(ValueError,"budget"):
                read_float_rgba(p,budget=VisualBudget(max_live_bytes=1),alpha_mode="straight",channels=mapping)
            with self.assertRaisesRegex(ValueError,"absent"):
                read_float_rgba(p,budget=VisualBudget(),alpha_mode="straight")

    def test_public_model_interface_generates_and_attests_actual_exr(self):
        from studio_next.body_service import LocalBodyCoordinator
        from studio_next.body_signal import BodyAuthority,LiveBodySignal
        from studio_next.media_vault import verify_media_container
        with tempfile.TemporaryDirectory() as home:
            c=LocalBodyCoordinator(home)
            try:
                root=c._workspace("float-project");root.mkdir(parents=True,exist_ok=True)
                signal=LiveBodySignal(c,authority=BodyAuthority(workspace_ids=frozenset({"float-project"}),
                    operations=frozenset({"author_plan","submit"}),tool_access=frozenset({"read","write"})))
                authored=signal.command("author_plan",{"workspace_id":"float-project","tool_id":"body.visual_graph","document":self.document()})
                ir={"project":{"creative_intent":"Original floating pixel data, no HDR display claim"},
                    "shots":[{"id":"float","purpose":"Keep extended original pixel values"}],"tool_graph":[
                    {"id":"image","tool_id":"body.visual_graph","purpose":"Render native float",
                     "inputs":{"plan":authored["path"],"out":"master.exr"},"depends_on":[]},
                    {"id":"custody","tool_id":"body.asset_vault","purpose":"Record real native output",
                     "inputs":{"source_witness":{"$node_output":"image"}},"depends_on":["image"]}]}
                job=signal.command("submit",{"workspace_id":"float-project","film_ir":ir});deadline=time.monotonic()+30
                while time.monotonic()<deadline:
                    observed=signal.observe(job["job_id"])
                    if observed["job_state"] in ("completed","failed","blocked"):break
                    time.sleep(.04)
                self.assertEqual(observed["job_state"],"completed",observed)
                verify_media_container(root/"master.exr","image/x-exr")
            finally:c.close()
