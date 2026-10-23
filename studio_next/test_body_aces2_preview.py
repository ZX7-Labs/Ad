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
        self.proof=self.vault.ingest(self.exr,mime="application/octet-stream",
            rights="generated_original",source_type="trusted_renderer",
            source_id="actual-Blender-native-owner-vfx",
            evidence="True real Blender Cycles original scene-linear OpenEXR result",
            owner_or_generator="ZX7 verified 3D renderer")
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
            self.assertGreater(len(set(viewed.getdata())),5)
        self.assertEqual(sha256_file(self.exr),original_hash)

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
