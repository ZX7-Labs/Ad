"""Real installed OCIO2.5 ACES2.0 32f Blender scene -> measured SDR PNG."""
from __future__ import annotations
import importlib.util
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_next.body_aces2_preview import (
    render_aces_2_sdr_preview,OCIO_BUILTIN,SOURCE_COLOR,DISPLAY,VIEW)
from studio_next.body_integration import body_catalog,validate_witness
from studio_next.body_exr_passes import render_original_exr_passes
from studio_next.media_vault import MediaVault,sha256_file
from studio_next.body_publication import physical_tool_attempt
from studio_next.test_blender_scene import sample

_NATIVE_READY=(shutil.which("blender") is not None
    and importlib.util.find_spec("OpenEXR") is not None
    and importlib.util.find_spec("PyOpenColorIO") is not None
    and importlib.util.find_spec("PIL") is not None)


@unittest.skipUnless(_NATIVE_READY,"Installed Blender 32f and OCIO2.5 native libs required")
class RealOwnerACES2SceneColorProof(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.vault=MediaVault(self.root/"vault")
        film=sample()
        film["shot_id"]="licensed-scene-linear-color-engine"
        film["frames"]=2
        film["fps"]=12
        film["width"]=96
        film["height"]=64
        film["samples"]=2
        film["camera"]["animate_location"][-1]["frame"]=2
        for item in film["objects"]:
            for curve in item.get("animate",{}).values():
                if curve:curve[-1]["frame"]=2
        self.scene=self.root/"owned-scene.json"
        self.scene.write_text(json.dumps(film))
        self.exr=self.root/"licensed-float-exr.zip"
        result=render_original_exr_passes(self.scene,self.root,self.exr)
        self.assertTrue(result["actual_32bit_float_VFX_passes"])
        # This is the real registered, model-facing BODY generated-source
        # custody instrument, not a test-written license or hand-made ID.
        # The trusted graph, not LLM JSON, establishes renderer authority.
        original_output={"path":str(self.exr),"sha256":sha256_file(self.exr),
                         "bytes":self.exr.stat().st_size}
        with physical_tool_attempt("real-native-cg","original-exr-custody",
                                   "verified-actual-blender", "body.asset_vault"):
            self.proof=body_catalog(self.root).invoke("body.asset_vault",
                {"source_witness":original_output},
                allowed_access={"read","write"})
        self.assertEqual(self.vault.inspect(
            self.proof["asset_id"],attestation_id=self.proof["attestation_id"])["mime"],
            "application/x-zx7-exr-bundle")
        self.plan={
            "source":{"source":"zx7:sha256:"+self.proof["asset_id"],
                      "asset_id":self.proof["asset_id"],
                      "attestation_id":self.proof["attestation_id"]},
            "frame_index":1,"source_color_space":SOURCE_COLOR,
            "alpha_association":"associated_scene_linear",
            "scene_linear_background_rgb":[.07,.09,.14],
            "display":DISPLAY,"view":VIEW}
        self.planfile=self.root/"author-aces2-intent.json"
        self.planfile.write_text(json.dumps(self.plan))
    def tearDown(self):self.temp.cleanup()

    def test_actual_installed_aces2_native_processor_colors_original_exr_pixel(self):
        from PIL import Image
        import numpy as np
        from studio_next.body_materials import fingerprint_physical_inputs
        listed={c["id"]:c for c in body_catalog(self.root).discover()}
        self.assertEqual(listed["body.aces2_preview"]["status"],"installed")
        args={"plan":self.planfile.name,"out":"ACES2-review.png"}
        material=fingerprint_physical_inputs("body.aces2_preview",args,self.root)
        self.assertIn(self.proof["asset_id"],[x["sha256"] for x in material])
        original_hash=sha256_file(self.exr)
        witness=body_catalog(self.root).invoke("body.aces2_preview",args,
                                              allowed_access={"read","write"})
        self.assertTrue(validate_witness("body.aces2_preview",witness))
        with Image.open(self.root/"ACES2-review.png") as viewed:
            viewed.load()
            self.assertEqual(viewed.mode,"RGB")
            self.assertEqual(viewed.size,(96,64))
            self.assertEqual(viewed.info["zx7_ocio_builtin_config"],OCIO_BUILTIN)
            self.assertEqual(viewed.info["zx7_actual_view"],VIEW)
            self.assertEqual(viewed.info["zx7_original_archive_sha256"],
                             original_hash)
            self.assertGreater(np.unique(
                np.asarray(viewed).reshape(-1,3),axis=0).shape[0],5)
        self.assertEqual(sha256_file(self.exr),original_hash)

    def test_full_native_film_graph_creates_real_exr_rights_then_aces2_display(self):
        """Actual graph-produced licensed pixels, not a hand-authored license."""
        from PIL import Image
        from studio_next.body_integration import run_body_project
        from studio_next.media_vault import sha256_file
        source_before=sha256_file(self.scene)
        ir={
            "project":{"creative_intent":
                       "Original physically rendered VFX shot color-managed for review"},
            "shots":[{"id":"actual-cg-shot",
                      "purpose":"Render protected 3D scene to linear RGBA and real passes",
                      "duration_seconds":2/12}],
            "assets":[],
            "tool_graph":[
                {"id":"native-exr","tool_id":"body.exr_passes",
                 "purpose":"Actual Blender-generated 32float VFX multilayer original",
                 "inputs":{"scene_json":self.scene.name,
                           "out":"native-directed-exr.zip"},
                 "depends_on":[]},
                {"id":"licensed-exr","tool_id":"body.asset_vault",
                 "purpose":"Bind original procedural scene to real BODY producer evidence",
                 "inputs":{"source_witness":{"$node_output":"native-exr"}},
                 "depends_on":["native-exr"]}
            ]
        }
        first=run_body_project(ir,self.root)
        self.assertEqual(first["status"],"all_tool_results_verified",first)
        self.assertEqual(first["completed"],["native-exr","licensed-exr"])
        produced=self.root/"native-directed-exr.zip"
        digest=sha256_file(produced)
        stored=self.vault.inspect(digest)
        self.assertEqual(stored["mime"],"application/x-zx7-exr-bundle")
        attestations=[x for x in stored["rights_attestations"]
                      if x["rights"]=="generated_original"
                      and x["source_type"]=="trusted_renderer"]
        self.assertTrue(attestations)
        plan={
            "source":{"source":"zx7:sha256:"+digest,
                      "asset_id":digest,
                      "attestation_id":attestations[0]["attestation_id"]},
            "frame_index":2,
            "source_color_space":SOURCE_COLOR,
            "alpha_association":"associated_scene_linear",
            "scene_linear_background_rgb":[.025,.06,.11],
            "display":DISPLAY,"view":VIEW
        }
        planfile=self.root/"actual-graph-ACES2.json"
        planfile.write_text(json.dumps(plan))
        viewed=body_catalog(self.root).invoke("body.aces2_preview",
            {"plan":planfile.name,"out":"actual-graph-ACES2.png"},
            allowed_access={"read","write"})
        self.assertTrue(validate_witness("body.aces2_preview",viewed))
        with Image.open(self.root/"actual-graph-ACES2.png") as image:
            image.load()
            self.assertEqual(image.mode,"RGB")
            self.assertEqual(image.info["zx7_original_archive_sha256"],digest)
            self.assertEqual(image.info["zx7_actual_view"],VIEW)
        again=run_body_project(ir,self.root)
        self.assertEqual(again["status"],"all_tool_results_verified",again)
        self.assertEqual(again["reused"],["native-exr","licensed-exr"])
        self.assertEqual(sha256_file(produced),digest)
        self.assertEqual(sha256_file(self.scene),source_before)
        self.assertFalse(list(self.root.glob(".zx7-aces2-*")))

    def test_wrong_input_color_rights_or_frame_are_refused_before_png(self):
        import copy
        for changes in (
            {"frame_index":3},
            {"source_color_space":"ACEScg"},
            {"alpha_association":"unknown"},
            {"source":{**self.plan["source"],"attestation_id":"fake"}},
        ):
            plan=copy.deepcopy(self.plan);plan.update(changes)
            self.planfile.write_text(json.dumps(plan))
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                render_aces_2_sdr_preview(self.planfile,self.root,self.root/"vault",
                                          self.root/"bad-output.png")
            self.assertFalse((self.root/"bad-output.png").exists())

    def test_concurrent_artist_original_aces_png_is_never_truncated(self):
        self.planfile.write_text(json.dumps(self.plan))
        previous=self.root/"approved-aces2.png"
        render_aces_2_sdr_preview(self.planfile,self.root,self.root/"vault",previous)
        digest=sha256_file(previous)
        target=self.root/"competing-artist-review.png"
        original_link=os.link
        did=False
        from studio_next import body_aces2_preview as module
        def earlier_artist_won(stage,out,*args,**kwargs):
            nonlocal did
            if Path(out)==target:
                shutil.copyfile(previous,target)
                did=True
            return original_link(stage,out,*args,**kwargs)
        with patch.object(module.os,"link",side_effect=earlier_artist_won):
            with self.assertRaises(FileExistsError):
                render_aces_2_sdr_preview(self.planfile,self.root,
                                          self.root/"vault",target)
        self.assertTrue(did)
        self.assertEqual(sha256_file(target),digest)
        self.assertFalse(list(self.root.glob(".zx7-aces2-*")))


if __name__=="__main__":
    unittest.main()
