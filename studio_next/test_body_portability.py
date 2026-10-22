"""Actual cross-host recovery proof: verified media, rights and old-job isolation."""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tempfile
import unittest
import wave
from pathlib import Path

from studio_next.body_archive import create_body_archive, restore_body_archive, save_body_archive_offline
from studio_next.durable_graph import DurableFilmGraph
from studio_next.media_vault import MediaVault,sha256_file
from studio_next.body_portability import prepare_relocated_workspace


class PortableWorkspaceTests(unittest.TestCase):
    def build(self,base):
        root=base/"hostA"/"body"
        root.mkdir(parents=True)
        (root/"body-service.lock").write_bytes(b"")
        project=root/"projects"/"scene_01"
        project.mkdir(parents=True)
        clip=project/"director_original.wav"
        with wave.open(str(clip),"wb") as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000)
            wav.writeframes(bytes(32000))
        original_sha=sha256_file(clip)
        vault=MediaVault(project/"vault")
        evidence=vault.ingest(clip,mime="audio/wav",rights="owner_supplied",
            source_type="owner_upload",source_id="operator-a-original",
            evidence="User created and owns this original audio",
            owner_or_generator="owner")
        timeline=project/"original_edit.otio"
        timeline.write_text(json.dumps({"media_reference":{"target_url":clip.as_uri()},
            "artistic_director_story":"original, not rewritten"}),encoding="utf-8")
        with sqlite3.connect(root/"body-jobs.sqlite3") as conn:
            conn.execute("CREATE TABLE jobs (id TEXT,status TEXT)")
            conn.execute("INSERT INTO jobs VALUES('old-running','running')")
        graph=DurableFilmGraph(project/"production.sqlite3")
        status,_,owner=graph.start_or_reuse("film","original-shot","fingerprint",
             trusted_idempotent=True,existing_result_verifier=lambda x:True,
             lease_seconds=3600)
        self.assertEqual(status,"execute")
        graph.complete("film","original-shot","fingerprint",owner,
                       {"path":str(clip),"sha256":original_sha})
        receipt=project/".zx7-publications"/"old-host.json"
        receipt.parent.mkdir()
        receipt.write_text(json.dumps({"output":str(clip),
            "sha256":original_sha}),encoding="utf-8")
        archive=base/"trusted-snapshot.tar.gz"
        saved=create_body_archive(root,archive)
        return root,project,saved,evidence,original_sha,timeline.read_bytes()

    def test_relocated_real_owner_sound_media_custody_and_quarantined_jobs(self):
        with tempfile.TemporaryDirectory() as path:
            base=Path(path)
            original,project,saved,evidence,original_sha,original_timeline=self.build(base)
            target=base/"hostB"/"body"
            receipt=restore_body_archive(saved["archive"],target,
                expected_sha256=saved["sha256"],relocate=True)
            self.assertTrue(receipt["relocated"])
            self.assertFalse(receipt["old_jobs_auto_resumable"])
            self.assertEqual(sha256_file(target/"projects/scene_01/director_original.wav"),
                             original_sha)
            migrated=target/"projects"/"scene_01"
            self.assertEqual((migrated/"original_edit.otio").read_bytes(),original_timeline)
            vault=MediaVault(migrated/"vault")
            record=vault.inspect(evidence["asset_id"],
                attestation_id=evidence["attestation_id"])
            self.assertEqual(record["asset_id"],original_sha)
            self.assertEqual(record["rights_attestations"][0]["rights"],"owner_supplied")
            self.assertTrue(Path(record["path"]).is_relative_to(target))
            self.assertFalse((migrated/"production.sqlite3").exists())
            self.assertFalse((target/"body-jobs.sqlite3").exists())
            self.assertFalse((target/"body-service.lock").exists())
            history=target/".zx7-relocated-history"
            self.assertTrue((history/"body-jobs.sqlite3").is_file())
            self.assertTrue((history/"projects/scene_01/production.sqlite3").is_file())
            self.assertTrue((history/"projects/scene_01/.zx7-publications/old-host.json").is_file())
            with sqlite3.connect(history/"projects/scene_01/production.sqlite3") as db:
                stored=db.execute("SELECT output_json,node_state FROM node_results").fetchone()
            self.assertEqual(stored[1],"completed")
            self.assertIn(str(project),stored[0])
            graph=DurableFilmGraph(migrated/"production.sqlite3")
            self.assertEqual(graph.inspect("film"),[])
            report=json.loads((target/".zx7-relocation-report.json").read_text())
            self.assertTrue(report["rebind_and_rerun_required"])
            self.assertFalse(report["ready_to_autonomously_resume_original_jobs"])
            self.assertEqual(report["verified_original_archive_sha256"],saved["sha256"])
            self.assertTrue(original.is_dir(), "Import must never delete source project")

    def test_fail_closed_wrong_hash_and_default_host_move_refused(self):
        with tempfile.TemporaryDirectory() as path:
            base=Path(path)
            _,_,saved,_,_,_=self.build(base)
            destination=base/"hostB"/"body"
            with self.assertRaisesRegex(ValueError,"Restore path differs"):
                restore_body_archive(saved["archive"],destination,
                                     expected_sha256=saved["sha256"])
            self.assertFalse(destination.exists())
            with self.assertRaisesRegex(ValueError,"SHA256"):
                restore_body_archive(saved["archive"],destination,
                                     expected_sha256="0"*64,relocate=True)
            self.assertFalse(destination.exists())
            with self.assertRaises(ValueError):
                restore_body_archive(saved["archive"],destination,
                                     expected_sha256=saved["sha256"],relocate=1)
            self.assertFalse(destination.exists())

    def test_original_host_restore_policy_and_new_host_nonresume(self):
        with tempfile.TemporaryDirectory() as path:
            base=Path(path)
            original,_,saved,_,_,_=self.build(base)
            with self.assertRaises(FileExistsError):
                restore_body_archive(saved["archive"],original,
                    expected_sha256=saved["sha256"],relocate=True)
            shutil.rmtree(original)
            with self.assertRaisesRegex(ValueError,"unchanged"):
                restore_body_archive(saved["archive"],original,
                    expected_sha256=saved["sha256"],relocate=True)
            result=restore_body_archive(saved["archive"],original,
                expected_sha256=saved["sha256"])
            self.assertFalse(result["relocated"])
            self.assertTrue(result["old_jobs_auto_resumable"])
            self.assertTrue((original/"body-jobs.sqlite3").exists())

    def test_operator_offline_backup_blocks_running_jobs_and_host_lock(self):
        import fcntl
        with tempfile.TemporaryDirectory() as path:
            base=Path(path)
            original=base/"host";original.mkdir()
            (original/"real_source.txt").write_text("The owner's untouched notes")
            with sqlite3.connect(original/"body-jobs.sqlite3") as conn:
                conn.execute("CREATE TABLE jobs(id TEXT,status TEXT)")
                conn.execute("INSERT INTO jobs VALUES('live','running')")
            dest=base/"out.tar.gz"
            with self.assertRaisesRegex(RuntimeError,"unresolved active"):
                save_body_archive_offline(original,dest)
            self.assertFalse(dest.exists())
            with sqlite3.connect(original/"body-jobs.sqlite3") as conn:
                conn.execute("UPDATE jobs SET status='completed'")
            gate=(original/"body-service.lock").open("a+")
            try:
                fcntl.flock(gate.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
                with self.assertRaisesRegex(RuntimeError,"service running"):
                    save_body_archive_offline(original,dest)
            finally:
                fcntl.flock(gate.fileno(),fcntl.LOCK_UN)
                gate.close()
            result=save_body_archive_offline(original,dest)
            self.assertTrue(dest.is_file())
            self.assertEqual(result["sha256"],sha256_file(dest))

    def test_operator_backup_blocks_half_uploaded_owner_media(self):
        with tempfile.TemporaryDirectory() as path:
            base=Path(path)
            original=base/"host";original.mkdir()
            (original/"owner.mp4").write_bytes(b"original original bytes")
            (original/".zx7-import-xyz.tmp").write_bytes(b"partial media")
            with self.assertRaisesRegex(RuntimeError,"transfer is incomplete"):
                save_body_archive_offline(original,base/"backup.tar.gz")
            (original/".zx7-import-xyz.tmp").unlink()
            result=save_body_archive_offline(original,base/"backup.tar.gz")
            self.assertTrue(result["sha256"])

    def test_original_machine_frame_checkpoints_are_inert_after_host_move(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            original=root/"compute-one"/"film"
            frames=original/".zx7-frame-checkpoints"/"sceneA"/"frames"
            frames.mkdir(parents=True)
            (frames/"frame_0001.exr").write_bytes(
                b"Original host had CPU-rendered VFX frames, not portable job authority")
            (frames.parent/"checkpoint.json").write_text(json.dumps({
                "schema":1,"job_signature":"old-machine-render-version",
                "frame_count":2,"frames":{"1":{"sha256":"0"*64}}}))
            (frames.parent/"owner-render.lock").write_bytes(b"")
            (original/"artist-scene.json").write_text(
                '{"shot_id":"original-owner-scene","artistic_intent":"preserved"}')
            archive=create_body_archive(original,root/"signed-owner.tar.gz")
            new=root/"compute-two"/"film"
            result=restore_body_archive(archive["archive"],new,
                       expected_sha256=archive["sha256"],relocate=True)
            self.assertTrue(result["old_execution_state_quarantined"])
            self.assertFalse((new/".zx7-frame-checkpoints").exists())
            history=new/".zx7-relocated-history"/".zx7-frame-checkpoints"
            self.assertEqual((history/"sceneA/frames/frame_0001.exr").read_bytes(),
                b"Original host had CPU-rendered VFX frames, not portable job authority")
            self.assertEqual((new/"artist-scene.json").read_text(),
                 (original/"artist-scene.json").read_text())
            report=json.loads((new/".zx7-relocation-report.json").read_text())
            self.assertTrue(any(".zx7-frame-checkpoints" in p
                      for p in report["historical_metadata_moved"]))
            self.assertFalse(report["ready_to_autonomously_resume_original_jobs"])

    def test_reject_archived_forged_rel_location_and_history_names(self):
        with tempfile.TemporaryDirectory() as path:
            base=Path(path)
            old=base/"film"
            old.mkdir()
            (old/".zx7-relocation-report.json").write_text("owner-bad-report")
            saved=create_body_archive(old,base/"data.tar.gz")
            target=base/"migrated"
            with self.assertRaisesRegex(ValueError,"collides"):
                restore_body_archive(saved["archive"],target,
                    expected_sha256=saved["sha256"],relocate=True)
            self.assertFalse(target.exists())

    def test_cross_host_creates_no_fake_complete_job_if_new_service_started(self):
        from studio_next.body_service import LocalBodyCoordinator
        with tempfile.TemporaryDirectory() as path:
            base=Path(path)
            _,_,saved,_,_,_=self.build(base)
            dest=base/"machine-two"/"body"
            restore_body_archive(saved["archive"],dest,
                                 expected_sha256=saved["sha256"],relocate=True)
            engine=LocalBodyCoordinator(dest,workers=1,execute=lambda ir,root:{"ok":True})
            try:
                self.assertEqual(engine.list_jobs()["jobs"],[])
            finally:
                engine.close()


if __name__=="__main__":
    unittest.main()
