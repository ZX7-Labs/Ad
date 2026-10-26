"""Durable local databases without depending on vulnerable WAL runtimes.

SQLite's primary WAL documentation identifies the WAL-reset fix in 3.51.3,
and backports 3.44.6/3.50.7. Older/unknown branches use rollback journaling.
https://www.sqlite.org/wal.html#the_wal_reset_bug
"""
from __future__ import annotations

import sqlite3


class _ClosingConnection(sqlite3.Connection):
    def __exit__(self, *exception):
        try:
            return super().__exit__(*exception)
        finally:
            # sqlite3's ordinary context manager commits but leaves the
            # connection open. Long film/status sessions must release it now.
            self.close()


def _safe_wal(version):
    version = tuple(version)
    return (version >= (3, 51, 3) or
            ((3, 44, 6) <= version < (3, 45, 0)) or
            ((3, 50, 7) <= version < (3, 51, 0)))


def connect_durable_database(path):
    database = sqlite3.connect(path, timeout=30, isolation_level=None,
                               factory=_ClosingConnection)
    try:
        database.execute("PRAGMA busy_timeout=30000")
        # No write-buffer admission gap: acknowledged job/checkpoint data
        # uses FULL synchronization on every production connection.
        mode = "WAL" if _safe_wal(sqlite3.sqlite_version_info) else "DELETE"
        actual = database.execute("PRAGMA journal_mode=" + mode).fetchone()[0]
        if actual.lower() != mode.lower():
            raise RuntimeError("Studio database could not enable durable journal policy")
        database.execute("PRAGMA synchronous=FULL")
        return database
    except BaseException:
        database.close()
        raise
