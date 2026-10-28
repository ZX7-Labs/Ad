"""Native project ABI, custody and transaction boundary regression checks."""
import hashlib
import json
from pathlib import Path
import subprocess
import shutil
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
            original_copy=shutil.copyfileobj
            def broken_copy(source,dest,length=0):
                if ".zx7-native-publish-" in str(getattr(dest,"name","")):
                    dest.write(b"only a partial archive")
                    raise OSError("interrupted native publication")
                return original_copy(source,dest,length)
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

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                         "Real FFmpeg and FFprobe required for actual native media encoding")
    def test_native_export_actual_mp4_decodes_with_expected_frames(self):
        from io import BytesIO
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);bundle=root/"source.zxmotion";target=root/"render.mp4"
            picture=BytesIO()
            Image.new("RGBA",(64,48),(15,84,141,255)).save(picture,format="PNG")
            png=picture.getvalue()
            blend=b"BLENDER-v405"+b"synthetic publication fixture" * 16
            contents={"project.blend":blend,"render_000000.png":png,
                      "render_000001.png":png}
            receipt={"version":VERSION,"engine_version":"mock-fixture, not Blender acceptance",
                     "members":{n:hashlib.sha256(raw).hexdigest() for n,raw in contents.items()},
                     "native":{"renders":[
                       {"scene":"Scene","frame":i,"format":"png","file":f"render_{i:06d}.png"}
                       for i in range(2)]}}
            with zipfile.ZipFile(bundle,"w") as archive:
                for name,raw in contents.items():archive.writestr(name,raw)
                archive.writestr("receipt.json",json.dumps(receipt))
            source_sha=hashlib.sha256(bundle.read_bytes()).hexdigest()
            with patch("studio_next.body_publication.require_published_source",
                       return_value=source_sha):
                export_motion_media(bundle,target,fps=12)
            probe=json.loads(subprocess.check_output([
                "ffprobe","-v","error","-select_streams","v:0",
                "-show_entries","stream=width,height,nb_frames,codec_name",
                "-of","json",str(target)],text=True))
            track=probe["streams"][0]
            self.assertEqual((track["width"],track["height"]),(64,48))
            self.assertEqual(int(track["nb_frames"]),2)
            subprocess.run(["ffmpeg","-v","error","-xerror","-i",str(target),
                            "-f","null","-"],capture_output=True,check=True,timeout=30)
            self.assertFalse(list(root.glob(".zx7-motion-export-*")))

    @staticmethod
    def _export_fixture(root):
        bundle=root/"valid-native.zxmotion"
        blend=b"BLENDER-v405"+b"fixture data"*20
        from io import BytesIO
        from PIL import Image
        image=BytesIO()
        Image.new("RGBA",(64,48),(10,82,155,255)).save(image,format="PNG")
        frame=image.getvalue()
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
            actual_encoder=subprocess.run
            def competing_encoder(argv,**kwargs):
                # Produce an actual, completely decoded MP4 before testing
                # the exclusive final publication race against another writer.
                actual_encoder(argv,**kwargs)
                target.write_bytes(b"independent other writer's bytes")
            with patch("studio_next.body_publication.require_published_source",return_value=source_sha):
                with patch("studio_next.body_motion_project.subprocess.run",side_effect=competing_encoder):
                    with self.assertRaises(FileExistsError):
                        export_motion_media(bundle,target,fps=24)
            self.assertEqual(target.read_bytes(),b"independent other writer's bytes")
            self.assertEqual(list(root.glob(".zx7-motion-export-*")),[])


    def test_encoder_claims_success_but_corrupt_bytes_are_never_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);bundle,source_sha,_=self._export_fixture(root)
            target=root/"corrupt.mp4"
            def fake_success(argv,**kwargs):
                Path(argv[-1]).write_bytes(b"invalid nonempty H264 fake movie")
                return subprocess.CompletedProcess(argv,0)
            with patch("studio_next.body_publication.require_published_source",return_value=source_sha):
                with patch("studio_next.body_motion_project.subprocess.run",
                           side_effect=fake_success):
                    with self.assertRaisesRegex(ValueError,"real decode proof"):
                        export_motion_media(bundle,target,fps=24)
            self.assertFalse(target.exists())
            self.assertFalse(list(root.glob(".zx7-motion-export-*")))

if __name__=="__main__":unittest.main()
