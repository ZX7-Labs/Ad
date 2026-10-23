"""Real Blender/EXR power-interruption test: reuse decoded 32f original frames.

A production frame must not become an accepted result solely because its
filename exists. The exact source script, Blender version, SHA256 and decoded
RGBA/depth/normal/vector passes are checked at every restart.
"""
from __future__ import annotations

import fcntl
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from studio_next.blender_scene import Invalid3DShot,render_blender_shot
from studio_next.body_exr_passes import inspect_real_exr_frame,verify_exr_bundle
from studio_next.body_frame_resume import render_resumable_exr_passes,_store_state
from studio_next.body_integration import body_catalog
from studio_next.body_materials import fingerprint_physical_inputs
from studio_next.media_vault import sha256_file
from studio_next.test_blender_scene import sample

def _source_scene(root):
    # Import the pure authored-scene fixture, NOT a unittest.TestCase class.
    # unittest.discover registers exposed TestCase imports and would rerun
    # their unrelated physical render + archive publication a second time.
    film=sample()
    film["shot_id"]="verified-resumable-independent-camera"
    film["frames"]=2
    film["fps"]=12
    film["width"]=96
    film["height"]=64
    film["samples"]=2
    film["camera"]["animate_location"][-1]["frame"]=2
    for obj in film["objects"]:
        for curve in obj.get("animate",{}).values():
            if curve:
                curve[-1]["frame"]=2
    source=Path(root)/"resumable-original-scene.json"
    source.write_text(json.dumps(film),encoding="utf-8")
    return source,film



class PhysicalFrameRangeContracts(unittest.TestCase):
    def test_half_written_checkpoint_receipt_recovers_only_committed_state(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            committed=root/"checkpoint.json"
            _store_state(committed,{"schema":1,"frames":{"1":"original-sha"}})
            self.assertEqual(json.loads(committed.read_text())["frames"]["1"],
                             "original-sha")
            orphan=root/".checkpoint.json.uncommitted"
            orphan.write_bytes(b'{"frames": incomplete')
            _store_state(committed,{"schema":1,"frames":{"1":"original-sha",
                                                       "2":"new-sha"}})
            self.assertFalse(orphan.exists())
            self.assertEqual(json.loads(committed.read_text())["frames"],
                             {"1":"original-sha","2":"new-sha"})
            orphan.symlink_to(committed)
            with self.assertRaisesRegex(ValueError,"journal entry"):
                _store_state(committed,{"schema":1,"frames":{}})
            self.assertEqual(json.loads(committed.read_text())["frames"]["1"],
                             "original-sha")

    def test_invalid_absolute_blender_frame_ranges_before_executable_import(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            source,scene=_source_scene(root)
            for a,b in ((0,1),(-1,2),(2,1),(1,99),(True,1),(1,False),(1,None)):
                with self.subTest(range=(a,b)):
                    with self.assertRaises(Invalid3DShot):
                        render_blender_shot(scene,root/"frames",
                            original_exr_passes=True,frame_start=a,frame_end=b)
            # No real Blender or output folder needed to prove invalid early.
            self.assertFalse((root/"frames").exists())


@unittest.skipUnless(shutil.which("blender") and importlib.util.find_spec("OpenEXR"),
                    "Native Blender CPU plus actual OpenEXR 3.3+ must exist")
class ActualResumableCyclesOriginalFrames(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        source,scene=_source_scene(self.root)
        self.source=source
        scene["frames"]=3
        scene["camera"]["animate_location"][-1]["frame"]=3
        for item in scene["objects"]:
            for curve in item.get("animate",{}).values():
                if curve:
                    curve[-1]["frame"]=3
        self.source.write_text(json.dumps(scene),encoding="utf-8")
        self.output=self.root/"frames-resumed-original.zip"

    def tearDown(self):
        self.temp.cleanup()

    def _checkout(self):
        matches=list((self.root/".zx7-frame-checkpoints").glob("*"))
        self.assertEqual(len(matches),1)
        return matches[0]

    def _fail_after_first_real_frame(self):
        calls=[]
        def intermittent_renderer(command,**opts):
            calls.append(command)
            if len(calls)==2:
                raise RuntimeError("Real host power loss after first independently decoded EXR")
            return subprocess.run(command,**opts)
        with self.assertRaisesRegex(RuntimeError,"power loss"):
            render_resumable_exr_passes(
                self.source,self.root,self.output,
                chunk_frames=1,runner=intermittent_renderer)
        self.assertFalse(self.output.exists())
        self.assertEqual(len(calls),2)
        return calls

    def test_two_host_process_iterations_recover_only_missing_real_exr_frames(self):
        calls=self._fail_after_first_real_frame()
        stored=self._checkout()/"frames/frame_0001.exr"
        saved_sha=sha256_file(stored)
        self.assertEqual(inspect_real_exr_frame(stored)["decoded_float_precision_bits"],32)
        seen=[]
        def observed_renderer(command,**options):
            seen.append(command)
            return subprocess.run(command,**options)
        receipt=render_resumable_exr_passes(
            self.source,self.root,self.output,
            chunk_frames=1,runner=observed_renderer)
        self.assertEqual(receipt["reused_absolute_frames"],[1])
        self.assertEqual(receipt["rendered_absolute_frames"],[2,3])
        self.assertEqual(len(seen),2)
        self.assertEqual([x[x.index("--frame-start")+1] for x in seen],["2","3"])
        self.assertEqual(sha256_file(stored),saved_sha)
        self.assertEqual(receipt["newly_rendered_frame_count"],2)
        self.assertEqual(verify_exr_bundle(self.output)["original_frame_count"],3)
        with zipfile.ZipFile(self.output) as archive:
            self.assertEqual(hashlib.sha256(
                archive.read("frames/frame_0001.exr")).hexdigest(),saved_sha)
            manifest=json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["checkpoint_frame_signature"],
                 json.loads((self._checkout()/"checkpoint.json").read_text())["job_signature"])
            self.assertFalse(manifest["ACES_transform_certified"])
        with self.assertRaises(ValueError):
            render_resumable_exr_passes(self.source,self.root,self.output)

    def test_actual_blender_decodes_private_unchanged_scene_during_working_source_swap(self):
        original=self.source.read_bytes()
        before=sha256_file(self.source)
        altered=json.loads(original)
        altered["world"]["strength"]=altered["world"]["strength"]*1.5
        hostile=json.dumps(altered).encode("utf-8")
        observed=[]
        def swapped_working_scene(command,**options):
            selected=Path(command[command.index("--scene")+1])
            self.assertNotEqual(selected.resolve(),self.source.resolve())
            self.assertIn(".zx7-scene-seal-",str(selected))
            self.assertEqual(sha256_file(selected),before)
            self.assertFalse(selected.stat().st_mode & 0o222)
            observed.append(selected)
            self.source.write_bytes(hostile)
            try:
                return subprocess.run(command,**options)
            finally:
                self.source.write_bytes(original)
        completed=render_resumable_exr_passes(
            self.source,self.root,self.output,
            chunk_frames=2,runner=swapped_working_scene)
        self.assertEqual(completed["newly_rendered_frame_count"],3)
        self.assertEqual(completed["verified_frame_reuse_count"],0)
        self.assertEqual(sha256_file(self.source),before)
        self.assertEqual(verify_exr_bundle(self.output)["original_frame_count"],3)
        self.assertEqual(len(observed),2)
        self.assertTrue(all(not file.exists() for file in observed))
        self.assertFalse(list((self.root/".zx7-frame-checkpoints").rglob(
            ".zx7-scene-seal-*")))

    def test_corrupted_reused_vfx_frame_is_recomputed_not_falsely_accepted(self):
        self._fail_after_first_real_frame()
        frame=self._checkout()/"frames/frame_0001.exr"
        frame.write_bytes(b"not a valid 32 bit VFX image")
        result=render_resumable_exr_passes(self.source,self.root,self.output,chunk_frames=2)
        self.assertEqual(result["verified_frame_reuse_count"],0)
        self.assertEqual(result["newly_rendered_frame_count"],3)
        self.assertTrue(verify_exr_bundle(self.output)["original_exr_passes_real"])

    def test_new_original_scene_cannot_reuse_different_author_camera_frames(self):
        self._fail_after_first_real_frame()
        film=json.loads(self.source.read_text())
        film["world"]["strength"]=film["world"]["strength"]*1.1
        self.source.write_text(json.dumps(film),encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"renderer differs"):
            render_resumable_exr_passes(self.source,self.root,self.output)
        self.assertFalse(self.output.exists())

    def test_concurrent_worker_cannot_write_same_original_frame_checkpoint(self):
        self._fail_after_first_real_frame()
        lock=self._checkout()/"owner-render.lock"
        with lock.open("a+") as file:
            fcntl.flock(file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaisesRegex(RuntimeError,"already rendering"):
                render_resumable_exr_passes(self.source,self.root,self.output)
            fcntl.flock(file.fileno(),fcntl.LOCK_UN)
        self.assertFalse(self.output.exists())

    def test_installed_body_tool_with_portable_checkpoint_real_rights_free_assets(self):
        status={tool["id"]:tool for tool in body_catalog(self.root).discover()}
        self.assertEqual(status["body.exr_checkpoint"]["status"],"installed")
        self.assertEqual(status["body.exr_checkpoint"]["schema"]["required"],
                         ["scene_json","out"])
        materials=fingerprint_physical_inputs("body.exr_checkpoint",
            {"scene_json":self.source.name,"out":"installed-original.zip"},self.root)
        self.assertEqual(materials[0]["sha256"],sha256_file(self.source))
        response=body_catalog(self.root).invoke("body.exr_checkpoint",
                  {"scene_json":self.source.name,"out":"installed-original.zip"},
                  allowed_access={"read","write"})
        self.assertEqual(response["sha256"],sha256_file(
                self.root/"installed-original.zip"))
        self.assertEqual(response["newly_rendered_frame_count"],3)
        self.assertTrue(verify_exr_bundle(
            self.root/"installed-original.zip")["original_exr_passes_real"])


if __name__=="__main__":
    unittest.main()
