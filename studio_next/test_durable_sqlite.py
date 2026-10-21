import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_next.durable_sqlite import connect_durable_database


class PhysicalDatabasePolicyTests(unittest.TestCase):
    def test_acknowledged_writes_are_full_synced_on_patched_and_older_runtimes(self):
        for version, mode in [((3, 40, 1), 'delete'), ((3, 51, 2), 'delete'),
                              ((3, 44, 6), 'wal'), ((3, 50, 7), 'wal'),
                              ((3, 51, 3), 'wal'), ((3, 53, 1), 'wal')]:
            with self.subTest(version=version), tempfile.TemporaryDirectory() as root:
                with patch.object(sqlite3, 'sqlite_version_info', version):
                    with connect_durable_database(Path(root) / 'original.sqlite3') as db:
                        self.assertEqual(db.execute('PRAGMA journal_mode').fetchone()[0], mode)
                        self.assertEqual(db.execute('PRAGMA synchronous').fetchone()[0], 2)
                        db.execute('CREATE TABLE originals (evidence TEXT)')
                        db.execute('INSERT INTO originals VALUES (?)', ('मूल निर्देशन',))
                    with self.assertRaises(sqlite3.ProgrammingError):
                        db.execute('SELECT 1')
                    with sqlite3.connect(Path(root) / 'original.sqlite3') as reader:
                        self.assertEqual(reader.execute('SELECT * FROM originals').fetchone(),
                                         ('मूल निर्देशन',))


if __name__ == '__main__':
    unittest.main()
