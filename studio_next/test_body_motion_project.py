"""Native project ABI, custody and transaction boundary regression checks."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from studio_next.body_motion_project import VERSION,validate_motion_job,verify_motion_bundle,motion_runtime_ready,export_motion_media
from studio_next.body_motion_proof import fixture_job
from studio_next.body_document_schemas import validate_document
from studio_next.body_materials import fingerprint_physical_inputs
from studio_next.body_publication import require_published_source


class NativeMotionProjectTests(unittest.TestCase):
    def test_machine_contract_and_native_actions_agree(self):
        job=fixture_job()
        self.assertTrue(validate_document("body.motion_project",job))
        self.assertEqual(validate_motion_job(job),job)

    def test_invalid_reference_methods_and_nonfinite_arguments_rejected(self):
        invalid=[]
        for path in (["app"],["scene","__class__"],["data",True],[],["refs","_private"]):
            job=fixture_job();job["actions"]=[{"op":"read","path":path}];invalid.append(job)
        job=fixture_job();job["actions"]=[{"op":"call","path":["scene"],"method":"exec","args":[],"kwargs":{},"as":None}];invalid.append(job)
        job=fixture_job();job["actions"]=[{"op":"set","path":["scene","frame_start"],"value":float("nan")}];invalid.append(job)
        job=fixture_job();job["actions"]=[{"op":"set","path":["scene","camera"],"value":{"script":"bad"}}];invalid.append(job)
        for job in invalid:
            with self.subTest(action=job["actions"]),self.assertRaises(ValueError):validate_motion_job(job)

    def test_native_collection_pages_have_explicit_budgets(self):
        for offset,limit in ((-1,3),(0,257),(True,4),(0,0)):
            job=fixture_job();job["actions"]=[{"op":"list","path":["data","objects"],"offset":offset,"limit":limit}]
            with self.assertRaises(ValueError):validate_motion_job(job)

    def test_parent_native_project_bytes_invalidate_material_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);job=fixture_job();job["project"]="parent.zxmotion"
            (root/"job.json").write_text(json.dumps(job));(root/"parent.zxmotion").write_bytes(b"one")
            first=fingerprint_physical_inputs("body.motion_project",{"plan":"job.json"},root)
            (root/"parent.zxmotion").write_bytes(b"two")
            self.assertNotEqual(first,fingerprint_physical_inputs("body.motion_project",{"plan":"job.json"},root))

    def test_bundle_rejects_mutation_and_unsafe_member(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);bundle=root/"native.zxmotion";native=b"BLENDER-v405"+b"technical fixture"*20
            report={"version":VERSION,"engine_version":"4.5.15 LTS","members":{"project.blend":hashlib.sha256(native).hexdigest()}}
            with zipfile.ZipFile(bundle,"w") as archive:
                archive.writestr("project.blend",native);archive.writestr("receipt.json",json.dumps(report))
            self.assertEqual(verify_motion_bundle(bundle)["engine_version"],"4.5.15 LTS")
            with zipfile.ZipFile(bundle,"w") as archive:
                archive.writestr("project.blend",native+b"changed");archive.writestr("receipt.json",json.dumps(report))
            with self.assertRaises(ValueError):verify_motion_bundle(bundle)
            with zipfile.ZipFile(bundle,"a") as archive:archive.writestr("../escaped",b"no")
            with self.assertRaises(ValueError):verify_motion_bundle(bundle)

    def test_absent_blender_is_needs_setup(self):
        with patch("studio_next.body_motion_project.shutil.which",return_value=None):
            self.assertFalse(motion_runtime_ready())

    def test_bundle_manifest_alone_cannot_certify_generated_media(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/"external.zxmotion";source.write_bytes(b"model asserted native data")
            with self.assertRaises(ValueError):require_published_source(source,"body.motion_project")
            with self.assertRaises(ValueError):export_motion_media(source,Path(tmp)/"out.mp4",fps=24)


    def test_native_project_publication_does_not_expose_partial_versions(self):
        from studio_next.body_motion_project import run_motion_project
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);request=root/"request.json";target=root/"original.zxmotion"
            request.write_text(json.dumps({"version":VERSION,"project":None,"actions":[],"renders":[]}))
            def blender_runner(argv,**kwargs):
                out=Path(argv[-1])
                (out/"project.blend").write_bytes(b"BLENDER-v405"+b"fixture" * 30)
                (out/"native.json").write_text(json.dumps({
                    "engine_version":"4.5.15 LTS","renders":[],"actions":[]}))
                return subprocess.CompletedProcess(argv,0,stdout="Blender mock finished")
            with patch("studio_next.body_motion_project.shutil.which",return_value="blender"), \
                 patch("studio_next.body_motion_project.subprocess.check_output",
                       return_value="Blender 4.5.15 LTS\\n"), \
                 patch("studio_next.body_motion_project.subprocess.run",
                       side_effect=blender_runner):
                result=run_motion_project(request,root,target)
            self.assertEqual(result["engine_version"],"4.5.15 LTS")
            self.assertEqual(verify_motion_bundle(target)["job_sha256"],
                             hashlib.sha256(request.read_bytes()).hexdigest())
            self.assertFalse(list(root.glob(".zx7-native-publish-*")))
            self.assertTrue(target.is_file())

    def test_native_project_publication_partial_copy_fails_without_visible_target(self):
        from studio_next.body_motion_project import run_motion_project
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);request=root/"request.json";target=root/"film.zxmotion"
            request.write_text(json.dumps({"version":VERSION,"project":None,"actions":[],"renders":[]}))
            def blender_runner(argv,**kwargs):
                out=Path(argv[-1])
                (out/"project.blend").write_bytes(b"BLENDER-v405"+b"fixture" * 30)
                (out/"native.json").write_text(json.dumps({
                    "engine_version":"4.5.15 LTS","renders":[]}))
                return subprocess.CompletedProcess(argv,0,stdout="Blender mock finished")
            def broken_copy(source,dest,**kwargs):
                dest.write(b"only a partial archive")
                raise OSError("interrupted native publication")
            with patch("studio_next.body_motion_project.shutil.which",return_value="blender"), \
                 patch("studio_next.body_motion_project.subprocess.check_output",
                       return_value="Blender 4.5.15 LTS\\n"), \
                 patch("studio_next.body_motion_project.subprocess.run",
                       side_effect=blender_runner), \
                 patch("studio_next.body_motion_project.shutil.copyfileobj",
                       side_effect=broken_copy):
                with self.assertRaisesRegex(OSError,"interrupted native publication"):
                    run_motion_project(request,root,target)
            self.assertFalse(target.exists())
            self.assertFalse(list(root.glob(".zx7-native-publish-*")))

    @staticmethod
    def _export_fixture(root):
        bundle=root/"valid-native.zxmotion"
        blend=b"BLENDER-v405"+b"fixture data"*20
        frame=bytes.fromhex("89504e470d0a1a0a")+b"mocked original pixel fixture"
        members={"project.blend":hashlib.sha256(blend).hexdigest(),
                 "render_000000.png":hashlib.sha256(frame).hexdigest()}
        report={"version":VERSION,"engine_version":"4.5.15 LTS",
                "members":members,"native":{"renders":[
                    {"scene":"Scene","frame":1,"format":"png","file":"render_000000.png"}]}}
        with zipfile.ZipFile(bundle,"w") as archive:
            archive.writestr("project.blend",blend)
            archive.writestr("render_000000.png",frame)
            archive.writestr("receipt.json",json.dumps(report))
        return bundle,hashlib.sha256(bundle.read_bytes()).hexdigest(),frame

    def test_native_export_encoder_failure_leaves_no_partial_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);bundle,source_sha,_=self._export_fixture(root)
            target=root/"original.mp4"
            def interrupted_encoder(argv,**kwargs):
                Path(argv[-1]).write_bytes(b"interrupted partial H264")
                raise RuntimeError("encoder died after writing a partial movie")
            with patch("studio_next.body_publication.require_published_source",return_value=source_sha):
                with patch("studio_next.body_motion_project.subprocess.run",side_effect=interrupted_encoder):
                    with self.assertRaisesRegex(RuntimeError,"encoder died"):
                        export_motion_media(bundle,target,fps=24)
            self.assertFalse(target.exists())
            self.assertEqual(list(root.glob(".zx7-motion-export-*")),[])

    def test_native_export_png_publishes_complete_bytes_exclusively(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);bundle,source_sha,frame=self._export_fixture(root)
            target=root/"original.png"
            with patch("studio_next.body_publication.require_published_source",return_value=source_sha):
                export_motion_media(bundle,target,fps=24)
                self.assertEqual(target.read_bytes(),frame)
                with self.assertRaises(FileExistsError):
                    export_motion_media(bundle,target,fps=24)
            self.assertEqual(target.read_bytes(),frame)
            self.assertEqual(list(root.glob(".zx7-motion-export-*")),[])

    def test_native_export_concurrent_writer_is_never_removed_or_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);bundle,source_sha,_=self._export_fixture(root)
            target=root/"film.mp4"
            def competing_encoder(argv,**kwargs):
                Path(argv[-1]).write_bytes(b"fully encoded test movie")
                target.write_bytes(b"independent other writer's bytes")
            with patch("studio_next.body_publication.require_published_source",return_value=source_sha):
                with patch("studio_next.body_motion_project.subprocess.run",side_effect=competing_encoder):
                    with self.assertRaises(FileExistsError):
                        export_motion_media(bundle,target,fps=24)
            self.assertEqual(target.read_bytes(),b"independent other writer's bytes")
            self.assertEqual(list(root.glob(".zx7-motion-export-*")),[])


if __name__=="__main__":unittest.main()
