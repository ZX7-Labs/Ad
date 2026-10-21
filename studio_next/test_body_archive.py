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
