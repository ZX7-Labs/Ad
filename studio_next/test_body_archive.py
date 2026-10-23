import hashlib
import sqlite3
import tarfile
import tempfile
import unittest
from pathlib import Path

from studio_next.body_archive import create_body_archive,restore_body_archive
from studio_next.media_vault import MediaVault


class PhysicalBodySnapshotTests(unittest.TestCase):
    def test_restore_solid_original_assets_sqlite_wal_and_crash_checkpoints(self):
        with tempfile.TemporaryDirectory() as root:
            base=Path(root)
            original=base/"actual-film-workspace";original.mkdir()
            (original/"scenes").mkdir()
            (original/"scenes"/"original-film.mp4").write_bytes(b"REAL encoded movie fixture"*120)
            MediaVault(original/"vault")
            with sqlite3.connect(original/"production.sqlite3") as conn:
                conn.execute("CREATE TABLE steps(id TEXT,value TEXT)")
                conn.execute("INSERT INTO steps VALUES('scene_001','completed')")
            saved=create_body_archive(original,base/"backup.tar.gz")
            self.assertTrue(len(saved["sha256"])==64)
            import shutil
            shutil.rmtree(original)
            restored=restore_body_archive(base/"backup.tar.gz",original,
                                          expected_sha256=saved["sha256"])
            self.assertEqual(restored["files"],3)
            self.assertTrue((original/"scenes"/"original-film.mp4").is_file())
            with sqlite3.connect(original/"production.sqlite3") as conn:
                self.assertEqual(conn.execute("SELECT value FROM steps").fetchone(),
                                 ("completed",))

    def test_tampered_archive_and_wrong_restore_path_cannot_impersonate_original(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)
            project=p/"original";project.mkdir()
            (project/"shot.mp4").write_bytes(b"film"*130)
            a=create_body_archive(project,p/"saved.tar.gz")
            import shutil
            shutil.rmtree(project)
            with self.assertRaisesRegex(ValueError,"Restore path differs"):
                restore_body_archive(p/"saved.tar.gz",p/"different",
                                     expected_sha256=a["sha256"])
            self.assertFalse((p/"different").exists())
            with self.assertRaisesRegex(ValueError,"SHA256"):
                restore_body_archive(p/"saved.tar.gz",project,
                                     expected_sha256="0"*64)
            with (p/"saved.tar.gz").open("ab") as f:f.write(b"unauthorized changes")
            with self.assertRaisesRegex(ValueError,"SHA256"):
                restore_body_archive(p/"saved.tar.gz",project,
                                     expected_sha256=a["sha256"])
            self.assertFalse(project.exists())

    def test_private_original_decoder_snapshots_never_escape_into_owner_backups(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)
            source=p/"original"
            source.mkdir()
            (source/"owner-plan.json").write_text('{"director":"original"}')
            transient=source/".zx7-owned-sources-private-execution"
            transient.mkdir()
            (transient/"owned-temporary-video.mp4").write_bytes(b"temporary original media")
            target=p/"backup.tar.gz"
            with self.assertRaisesRegex(ValueError,"in-flight original media"):
                create_body_archive(source,target)
            self.assertFalse(target.exists())
            import shutil
            shutil.rmtree(transient)
            preserved=create_body_archive(source,target)
            self.assertEqual(preserved["files"],1)
            # Even a previously signed attacker-authored archive may never
            # import an in-flight decoder snapshot as legitimate owner media.
            self.assertTrue(preserved["sha256"])
            import io,json,hashlib
            raw=p/"forged.tar.gz"
            snapshot_bytes=b"untrusted decoder snapshot"
            forged_name=".zx7-owned-sources-foreign/hidden.mp4"
            manifest={"kind":"ZX7-BODY-REAL-MEDIA-V1","schema":1,
                      "source_workspace":str(source),"files":[
                      {"path":forged_name,
                       "sha256":hashlib.sha256(snapshot_bytes).hexdigest(),
                       "bytes":len(snapshot_bytes)}]}
            with tarfile.open(raw,"w:gz") as forged:
                for name,blob in ((forged_name,snapshot_bytes),
                                  ("__zx7_body_snapshot_manifest__.json",
                                   json.dumps(manifest).encode())):
                    item=tarfile.TarInfo(name);item.size=len(blob)
                    forged.addfile(item,io.BytesIO(blob))
            import shutil
            shutil.rmtree(source)
            with self.assertRaisesRegex(ValueError,"Transient sealed cinema sources"):
                restore_body_archive(raw,source,
                    expected_sha256=hashlib.sha256(raw.read_bytes()).hexdigest())
            self.assertFalse(source.exists())

    def test_live_review_and_exr_render_staging_cannot_leak_into_backup(self):
        import shutil
        with tempfile.TemporaryDirectory() as sandbox:
            root=Path(sandbox)
            project=root/"original-cinema"
            project.mkdir()
            (project/"source.json").write_text('{"real":"director"}')
            for prefix in (".zx7-media-review-", ".zx7-original-exr-render-",
                           ".zx7-scene-seal-", ".zx7-temporal-", ".zx7-aces2-"):
                with self.subTest(prefix=prefix):
                    private=project/(prefix+"frozen-work")
                    private.mkdir()
                    (private/"actual-unapproved-media.bin").write_bytes(b"temporary material")
                    target=root/"backup.tar.gz"
                    with self.assertRaisesRegex(ValueError,"in-flight original media"):
                        create_body_archive(project,target)
                    self.assertFalse(target.exists())
                    shutil.rmtree(private)
            permitted=create_body_archive(project,root/"backup.tar.gz")
            self.assertEqual(permitted["files"],1)
            self.assertTrue(permitted["sha256"])

    def test_reject_nonempty_destination_and_archive_inside_workspace(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)
            original=p/"film";original.mkdir()
            (original/"movie.mp4").write_bytes(b"film"*120)
            with self.assertRaisesRegex(ValueError,"outside"):
                create_body_archive(original,original/"archive.tar.gz")
            a=create_body_archive(original,p/"safe.tar.gz")
            with self.assertRaises(FileExistsError):
                restore_body_archive(p/"safe.tar.gz",original,
                                     expected_sha256=a["sha256"])


if __name__=="__main__":unittest.main()
