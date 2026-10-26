"""Native project ABI, custody and transaction boundary regression checks."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from studio_next.body_motion_project import VERSION,validate_motion_job,verify_motion_bundle,motion_runtime_ready,export_motion_media
from studio_next.body_motion_proof import fixture_job
from studio_next.body_document_schemas import validate_document
from studio_next.body_materials import fingerprint_physical_inputs


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


if __name__=="__main__":unittest.main()
