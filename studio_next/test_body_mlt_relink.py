"""Actual cross-workspace native edit recovery, original loss and hostile inputs."""
import copy
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from studio_next import test_body_mlt_editor as original_fixtures
from studio_next.body_archive import create_body_archive,restore_body_archive
from studio_next.body_mlt_editor import export_owned_mlt
from studio_next.body_mlt_relink import relink_owned_mlt_project,inspect_relocated_mlt
from studio_next.body_mlt_roundtrip import recover_original_mlt_plan
from studio_next.body_mlt_transform import encode_transform
from studio_next.media_vault import MediaVault,sha256_file
from studio_next.test_body_mlt_transform import geometry,transform,pictures


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"Native source custody needs real decoders")
class NativeCrossHostRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.base=Path(self.temporary.name)
        self.old=self.base/"former-host";self.old.mkdir()
        self.new=self.base/"restored-host"
        self.plan,file=original_fixtures.VerifiedMLTEditorialTests()._case(self.old)
        self.plan["tracks"][1]["transform"]=transform(geometry(x=16,y=12),
            geometry(frame=11,x=32,y=0,rotation_degrees=45))
        self.plan["tracks"][1]["mask"]={"keyframes":[{
            "frame":0,"x":0,"y":0,"width":64,"height":48,"rounding":.25}]}
        sound=self.old/"original-stereo.wav"
        subprocess.run(["ffmpeg","-v","error","-nostdin","-f","lavfi","-i",
            "sine=frequency=713:sample_rate=48000:duration=1","-ac","2",
            "-c:a","pcm_s16le",str(sound)],check=True,timeout=40)
        rec=MediaVault(self.old/"vault").ingest(sound,mime="audio/wav",rights="owner_supplied",
            source_type="owner_upload",source_id="original-stereo-fixture",
            evidence="Actual generated PCM fixture",owner_or_generator="test")
        self.plan["audio_tracks"]=[{"gain_db":-6,"pan":.25,"clips":[{
            "source":"zx7:sha256:"+rec["asset_id"],"asset_id":rec["asset_id"],
            "attestation_id":rec["attestation_id"],"position_frame":0,"first_frame":0,"end_frame":12}]}]
        file.write_text(json.dumps(self.plan));self.source=self.old/"latest.mlt"
        export_owned_mlt(file,self.old,self.old/"vault",self.source)
        self.original=self.source.read_bytes()
        self.saved=create_body_archive(self.old,self.base/"verified.tar.gz")
        restore_body_archive(self.saved["archive"],self.new,expected_sha256=self.saved["sha256"],relocate=True)
        self.source=self.new/"latest.mlt";self.target=self.new/"relinked.mlt"

    def tearDown(self):self.temporary.cleanup()

    def run_relink(self):return relink_owned_mlt_project(self.source,self.new,self.old,self.target)

    def test_removed_former_host_preserves_every_edit_and_new_model_tool_source_fingerprint(self):
        from studio_next.body_integration import body_catalog,validate_witness
        from studio_next.body_materials import fingerprint_physical_inputs
        shutil.rmtree(self.old)
        body=body_catalog(self.new)
        row=next(r for r in body.discover() if r["id"]=="body.mlt_owned_relink")
        self.assertEqual(row["schema"]["required"],["edit","old_workspace","out"])
        inputs={"edit":"latest.mlt","old_workspace":str(self.old),"out":"relinked.mlt"}
        fingerprint=fingerprint_physical_inputs("body.mlt_owned_relink",inputs,self.new)
        from studio_next.body_affordances import BodyAffordanceSurface
        preflight=BodyAffordanceSurface(body).preflight("body.mlt_owned_relink",inputs,allowed_access={"write"})
        self.assertEqual(preflight["readiness"],"preflight_checked_not_executed")
        self.assertFalse(self.target.exists());self.assertFalse(self.old.exists())
        output=body.invoke("body.mlt_owned_relink",inputs,allowed_access={"write"})
        self.assertTrue(validate_witness("body.mlt_owned_relink",output))
        self.assertTrue(output["original_native_project_untouched"])
        self.assertFalse(output["old_host_sources_opened"])
        self.assertFalse(output["prior_host_render_jobs_reused"])
        self.assertEqual(recover_original_mlt_plan(self.target,self.new,self.new/"vault")["plan"],self.plan)
        self.assertEqual(self.source.read_bytes(),self.original)
        self.assertFalse(self.old.exists(),"No old-host vault or source may be opened/created")
        self.assertEqual(fingerprint_physical_inputs("body.mlt_owned_relink",inputs,self.new),fingerprint)
        with self.assertRaises(FileExistsError):self.run_relink()

    def test_wrong_host_missing_receipt_forged_paths_or_plugins_never_publish(self):
        for kind in ("wrong-host","no-report","source-outside","plugin","entity"):
            report=self.new/".zx7-relocation-report.json";receipt=report.read_bytes()
            xml=ET.fromstring(self.original)
            if kind=="source-outside":
                next(p for p in xml.find("producer") if p.get("name")=="resource").text="/other-owner/vault/objects/aa/"+"a"*64
            elif kind=="plugin":
                next(p for p in xml.find("./tractor/filter") if p.get("name")=="mlt_service").text="arbitrary-executable"
            elif kind=="no-report":report.unlink()
            self.source.write_bytes(ET.tostring(xml))
            if kind=="entity":self.source.write_bytes(b'<!DOCTYPE mlt [<!ENTITY x SYSTEM "file:///etc/passwd">]>'+self.source.read_bytes())
            old=self.base/"fake-host" if kind=="wrong-host" else self.old
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                relink_owned_mlt_project(self.source,self.new,old,self.target)
            self.assertFalse(self.target.exists())
            self.source.write_bytes(self.original);report.write_bytes(receipt)

    def test_changed_cas_or_removed_exact_rights_cannot_be_relinked_or_cached(self):
        prepared=inspect_relocated_mlt(self.source,self.new,self.old)
        rec=prepared["references"][0];file=rec["path"];original=file.read_bytes()
        file.write_bytes(original+b"altered original picture")
        with self.assertRaises(ValueError):self.run_relink()
        self.assertFalse(self.target.exists());file.write_bytes(original)
        with sqlite3.connect(self.new/"vault"/"assets.sqlite3") as db:
            db.execute("DELETE FROM attestations WHERE digest=? AND attestation_id=?",(rec["digest"],rec["attestation"]))
        with self.assertRaises(ValueError):self.run_relink()
        from studio_next.body_materials import fingerprint_physical_inputs
        with self.assertRaises(ValueError):
            fingerprint_physical_inputs("body.mlt_owned_relink",{
                "edit":"latest.mlt","old_workspace":str(self.old),"out":"relinked.mlt"},self.new)
        self.assertFalse(self.target.exists());self.assertEqual(self.source.read_bytes(),self.original)

    def test_missing_vault_custody_never_creates_a_new_rights_database(self):
        database=self.new/"vault"/"assets.sqlite3"
        database.unlink()
        with self.assertRaisesRegex(ValueError,"missing source custody"):self.run_relink()
        self.assertFalse(database.exists());self.assertFalse(self.target.exists())

    def test_last_moment_edit_change_and_competing_publication_preserve_existing_work(self):
        from studio_next import body_mlt_relink as links
        recover=links.recover_original_mlt_plan
        def mutate(*args,**kwargs):
            result=recover(*args,**kwargs);self.source.write_bytes(self.original+b"changed")
            return result
        with patch.object(links,"recover_original_mlt_plan",side_effect=mutate):
            with self.assertRaisesRegex(RuntimeError,"changed before publication"):self.run_relink()
        self.assertFalse(self.target.exists());self.source.write_bytes(self.original)
        winner=b"another operator's accepted native project"
        native_link=os.link
        def race(source,dest,*args,**kwargs):
            if Path(dest)==self.target:self.target.write_bytes(winner)
            return native_link(source,dest,*args,**kwargs)
        with patch.object(links.os,"link",side_effect=race):
            with self.assertRaises(FileExistsError):self.run_relink()
        self.assertEqual(self.target.read_bytes(),winner)
        self.assertEqual(self.source.read_bytes(),self.original)

    @unittest.skipUnless(shutil.which("melt"),"Physical restored project must render actual picture and audio")
    def test_relocated_native_project_renders_the_same_decoded_picture_and_sound_after_host_loss(self):
        from studio_next.body_mlt_render import render_owned_mlt
        render_owned_mlt(self.old/"latest.mlt",self.old,self.old/"before.mp4")
        before=pictures(self.old/"before.mp4")
        pcm=subprocess.check_output(["ffmpeg","-v","error","-i",str(self.old/"before.mp4"),
            "-vn","-f","f32le","-acodec","pcm_f32le","-ar","48000","-ac","2","-"],timeout=60)
        shutil.rmtree(self.old)
        result=self.run_relink();self.assertFalse(result["new_host_execution_evidence"])
        render_owned_mlt(self.target,self.new,self.new/"after.mp4")
        self.assertEqual(pictures(self.new/"after.mp4"),before)
        after_pcm=subprocess.check_output(["ffmpeg","-v","error","-i",str(self.new/"after.mp4"),
            "-vn","-f","f32le","-acodec","pcm_f32le","-ar","48000","-ac","2","-"],timeout=60)
        self.assertEqual(after_pcm,pcm)
        self.assertFalse(self.old.exists());self.assertEqual(self.source.read_bytes(),self.original)


if __name__=="__main__":unittest.main()
