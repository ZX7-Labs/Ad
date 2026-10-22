"""Real Blender Cycles CPU scene-linear RGB/alpha/depth/vector/normal VFX proof."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from studio_next.body_exr_passes import (
    render_original_exr_passes,verify_exr_bundle,inspect_real_exr_frame)
from studio_next.body_integration import body_catalog
from studio_next.media_vault import sha256_file
from studio_next.body_materials import fingerprint_physical_inputs
from studio_next.test_blender_scene import sample


class ExrSceneContracts(unittest.TestCase):
    def test_exr_rejects_fake_zip_path_and_empty_bundle(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            forged=root/"not-original.zip"
            with zipfile.ZipFile(forged,"w") as z:
                z.writestr("../../stolen.exr",b"camera fake")
                z.writestr("manifest.json",'{"schema":1,"frames":[{"file":"../../stolen.exr","sha256":"0","bytes":0,"channels":[]}]}')
            with self.assertRaises(ValueError):
                verify_exr_bundle(forged)
            bare=root/"empty.zip"
            with zipfile.ZipFile(bare,"w") as z:
                z.writestr("manifest.json",'{"schema":1,"frames":[]}')
            with self.assertRaises(ValueError):
                verify_exr_bundle(bare)

    def test_duplicate_or_unlisted_frame_cannot_pretend_reusable_VFX_proof(self):
        with tempfile.TemporaryDirectory() as d:
            destination=Path(d)/"misleading-vfx.zip"
            invalid={"schema":1,"frames":[
                {"file":"frames/frame_0001.exr","sha256":"0"*64,
                 "bytes":15,"channels":["Combined.R"]},
                {"file":"frames/frame_0001.exr","sha256":"0"*64,
                 "bytes":15,"channels":["Combined.R"]}]}
            with zipfile.ZipFile(destination,"w") as bundle:
                bundle.writestr("manifest.json",json.dumps(invalid))
                bundle.writestr("frames/frame_0001.exr",b"fake scene no real pixels")
                bundle.writestr("frames/frame_0002.exr",b"hidden unlisted unlicensed frame")
            with self.assertRaisesRegex(ValueError,"duplicate or unverified"):
                verify_exr_bundle(destination)

    def test_absent_real_openexr_decoder_does_not_claim_a_ready_film_tool(self):
        with tempfile.TemporaryDirectory() as d:
            installed={tool["id"]:tool for tool in body_catalog(d).discover()}
            exr=installed["body.exr_passes"]
            if importlib.util.find_spec("OpenEXR") is None or shutil.which("blender") is None:
                self.assertEqual(exr["status"],"needs_setup")
            else:
                self.assertEqual(exr["status"],"installed")
            self.assertFalse(bool(exr["license"]=="free GPU cloud"))


@unittest.skipUnless(shutil.which("blender") and
                     importlib.util.find_spec("OpenEXR"),
                     "OpenEXR and actual Blender render engine required")
class Real32FloatMultiPassVfx(unittest.TestCase):
    def scene(self,root):
        film=sample()
        film["shot_id"]="original-independent-float-vfx"
        film["frames"]=2
        film["fps"]=12
        film["width"]=96
        film["height"]=64
        film["samples"]=2
        film["camera"]["animate_location"][-1]["frame"]=2
        for item in film["objects"]:
            for curve in item.get("animate",{}).values():
                if curve:
                    curve[-1]["frame"]=2
        source=root/"own-original-camera-lighting.json"
        source.write_text(json.dumps(film),encoding="utf-8")
        return source,film

    def test_actual_author_3d_frames_are_32_float_exr_not_toy_png(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            source,original=self.scene(root)
            original_hash=sha256_file(source)
            output=root/"original_linear_scene_passes.zip"
            result=render_original_exr_passes(source,root,output)
            self.assertTrue(result["actual_32bit_float_VFX_passes"])
            self.assertEqual(result["original_scene_frames"],2)
            self.assertEqual(result["original_scene_sha256"],original_hash)
            self.assertFalse(result["ACES_color_grade_proven"])
            self.assertEqual(sha256_file(source),original_hash)
            self.assertTrue(verify_exr_bundle(output)["original_exr_passes_real"])
            with zipfile.ZipFile(output) as z:
                files=z.namelist()
                self.assertIn("frames/frame_0001.exr",files)
                self.assertIn("frames/frame_0002.exr",files)
                manifest=json.loads(z.read("manifest.json"))
                self.assertEqual(manifest["artist_frames_requested"],2)
                self.assertEqual(manifest["width"],96)
                self.assertEqual(manifest["height"],64)
                self.assertTrue(all(item["bytes"]>500 for item in manifest["frames"]))
                frame=root/"actual-original-frame.exr"
                frame.write_bytes(z.read("frames/frame_0001.exr"))
            physical=inspect_real_exr_frame(frame)
            self.assertEqual(physical["decoded_float_precision_bits"],32)
            names=physical["actual_channel_names"]
            self.assertTrue(any(name.endswith("Depth.Z") for name in names))
            self.assertTrue(any(name.endswith("Vector.X") for name in names))
            self.assertTrue(any(name.endswith("Normal.X") for name in names))
            self.assertTrue(any(name.endswith("Combined.A") for name in names))
            self.assertEqual((physical["width"],physical["height"]),(96,64))

            # The actual registered BODY instrument publishes the encoded
            # archive atomically, with the same trusted renderer/code digest.
            tools=body_catalog(root)
            contracts={v["id"]:v for v in tools.discover()}
            self.assertEqual(contracts["body.exr_passes"]["status"],"installed")
            self.assertEqual(contracts["body.exr_passes"]["schema"]["required"],
                             ["scene_json","out"])
            data=fingerprint_physical_inputs("body.exr_passes",
                 {"scene_json":source.name,"out":"nested-pass-proof.zip"},root)
            self.assertEqual(data[0]["sha256"],original_hash)
            final=tools.invoke("body.exr_passes",{
                "scene_json":source.name,"out":"nested-pass-proof.zip"},
                 allowed_access={"read","write"})
            self.assertEqual(final["sha256"],sha256_file(root/"nested-pass-proof.zip"))
            self.assertTrue(verify_exr_bundle(root/"nested-pass-proof.zip")
                            ["original_exr_passes_real"])
            store=os.environ.get("ZX7_EXR_VFX_PROOF")
            if store:
                output_dir=Path(store).resolve()
                output_dir.mkdir(parents=True,exist_ok=True)
                import shutil as actual_copy
                receipts=[]
                for movie in (output,root/"nested-pass-proof.zip"):
                    original_render=output_dir/movie.name
                    if original_render.exists():
                        raise FileExistsError("Do not overwrite previously accepted EXR art proof")
                    actual_copy.copyfile(movie,original_render)
                    receipts.append({"file":movie.name,
                                     "sha256":sha256_file(original_render),
                                     "bytes":original_render.stat().st_size,
                                     "decoded_every_original_frame":verify_exr_bundle(
                                         original_render)["original_exr_passes_real"]})
                first=output_dir/"real-scene-linear-first-frame.exr"
                if first.exists():
                    raise FileExistsError("Never overwrite original scene linear art")
                with zipfile.ZipFile(output) as packed:
                    first.write_bytes(packed.read("frames/frame_0001.exr"))
                original=inspect_real_exr_frame(first)
                (output_dir/"real-32float-exr-evidence.json").write_text(json.dumps({
                     "schema":1,"verified_studio_brain_not_changed":True,
                     "genuine_Blender_CPU_exr":True,
                     "actual_float_channel_precision_bits":original["decoded_float_precision_bits"],
                     "channels":original["actual_channel_names"],
                     "actual_verified_height":original["height"],
                     "actual_verified_width":original["width"],
                     "archive_receipts":receipts,
                     "ACES_color_config_claimed":False,
                     "film_ready_without_further_compositing":False,
                     "independent_human_quality_approval":False},indent=2)+"\n",
                     encoding="utf-8")


    def test_non_authorized_external_GLB_only_claims_are_not_vfx_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            src,scene=self.scene(root)
            mesh=scene["objects"][0]
            mesh["type"]="licensed_glb"
            mesh["asset"]="unverified.glb"
            mesh["rights"]="owner_supplied"
            mesh.pop("vertices")
            mesh.pop("faces")
            src.write_text(json.dumps(scene),encoding="utf-8")
            with self.assertRaises(ValueError):
                render_original_exr_passes(src,root,root/"blocked.zip")


if __name__=="__main__":
    unittest.main()
