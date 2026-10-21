"""Durable rights-checked content-addressed asset vault for all creative media.

The model can request an image, sound, font, mesh, footage, thumbnail or film,
but cannot turn an arbitrary internet URL, imagined asset or unlicensed material
into studio media. The bytes, provenance and usage authorization are separately
tracked. This is technical custody, not a creative style or story prompt.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path

_DIGEST=re.compile(r"^[0-9a-f]{64}$")
_RIGHTS={"owner_supplied","generated_original","appropriately_licensed"}
_ALLOWED_MIME={"image/png","image/jpeg","image/webp","image/svg+xml",
 "image/x-exr","video/mp4","video/quicktime","video/webm",
 "audio/wav","audio/mpeg","audio/flac","font/ttf","font/otf",
 "model/gltf-binary","application/octet-stream"}
class MediaCustodyError(ValueError):
    pass


def sha256_file(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle,"sha256").hexdigest()


class MediaVault:
    """SQLite WAL + atomic immutable blobs; empty results are never delivered."""
    def __init__(self,root):
        self.root=Path(root).resolve()
        self.objects=self.root/"objects"
        self.db=self.root/"assets.sqlite3"
        self.objects.mkdir(parents=True,exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS blobs(
              digest TEXT PRIMARY KEY, size_bytes INTEGER NOT NULL,
              mime TEXT NOT NULL, created_at REAL NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS attestations(
              digest TEXT NOT NULL, attestation_id TEXT NOT NULL,
              rights TEXT NOT NULL, source_type TEXT NOT NULL,
              source_id TEXT NOT NULL, evidence TEXT NOT NULL,
              owner_or_generator TEXT NOT NULL, created_at REAL NOT NULL,
              PRIMARY KEY(digest,attestation_id),
              FOREIGN KEY(digest) REFERENCES blobs(digest))""")
            db.execute("CREATE INDEX IF NOT EXISTS attested_digest ON attestations(digest)")

    def _connect(self):
        db=sqlite3.connect(self.db,timeout=30,isolation_level=None)
        db.execute("PRAGMA busy_timeout=30000")
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def _loc(self,digest):
        if not isinstance(digest,str) or not _DIGEST.fullmatch(digest):
            raise MediaCustodyError("Unsafe media content digest")
        return self.objects/digest[:2]/digest

    def ingest(self,source,*,mime,rights,source_type,source_id,evidence,
               owner_or_generator):
        """Attest real file source and rights; never infer rights from an extension."""
        if mime not in _ALLOWED_MIME or rights not in _RIGHTS:
            raise MediaCustodyError("Unsupported media type or unverified rights class")
        for value in (source_type,source_id,evidence,owner_or_generator):
            if not isinstance(value,str) or not value.strip():
                raise MediaCustodyError("Explicit original source and media rights evidence required")
        if source_type not in ("owner_upload","trusted_renderer","licensed_library"):
            raise MediaCustodyError("No authenticated source class for media")
        expected={"owner_upload":"owner_supplied",
                  "trusted_renderer":"generated_original",
                  "licensed_library":"appropriately_licensed"}[source_type]
        if rights!=expected:
            raise MediaCustodyError("Declared rights disagree with original media source")
        path=Path(source)
        if not path.is_file() or path.stat().st_size==0:
            raise MediaCustodyError("Asset has no actual file bytes")
        size=path.stat().st_size
        digest=sha256_file(path)
        dest=self._loc(digest)
        dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.is_file():
            fd,tmp=tempfile.mkstemp(prefix="."+digest[:10]+"-",dir=dest.parent)
            try:
                with os.fdopen(fd,"wb") as handle, path.open("rb") as stream:
                    shutil.copyfileobj(stream,handle,1024*1024)
                    handle.flush();os.fsync(handle.fileno())
                if sha256_file(tmp)!=digest:raise MediaCustodyError("Source changed while ingesting")
                os.replace(tmp,dest)
            finally:
                if os.path.exists(tmp):os.unlink(tmp)
        elif sha256_file(dest)!=digest:
            raise MediaCustodyError("Previously saved media content is corrupted")
        if dest.stat().st_size!=size:
            raise MediaCustodyError("Mismatch in bytes of durable creative media")
        attestation={
            "rights":rights,"source_type":source_type,"source_id":source_id,
            "evidence":evidence,"owner_or_generator":owner_or_generator,
            "digest":digest}
        encoded=json.dumps(attestation,sort_keys=True,ensure_ascii=False).encode()
        att_id=hashlib.sha256(encoded).hexdigest()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old=db.execute("SELECT size_bytes,mime FROM blobs WHERE digest=?",(digest,)).fetchone()
            if old is not None and tuple(old)!=(size,mime):
                db.execute("ROLLBACK")
                raise MediaCustodyError("Contradictory MIME or file size for same content")
            db.execute("INSERT OR IGNORE INTO blobs VALUES(?,?,?,?)",
                       (digest,size,mime,time.time()))
            db.execute("INSERT OR IGNORE INTO attestations VALUES(?,?,?,?,?,?,?,?)",
                 (digest,att_id,rights,source_type,source_id,evidence,owner_or_generator,time.time()))
            db.execute("COMMIT")
        return {"asset_id":digest,"attestation_id":att_id,"mime":mime,
                "rights":rights,"size_bytes":size,"verified_bytes":True}

    def inspect(self,digest,*,attestation_id=None):
        path=self._loc(digest)
        with self._connect() as db:
            blob=db.execute("SELECT size_bytes,mime FROM blobs WHERE digest=?",(digest,)).fetchone()
            if blob is None:raise MediaCustodyError("Unknown media reference")
            if attestation_id is None:
                rows=db.execute("SELECT attestation_id,rights,source_type,source_id,evidence,owner_or_generator FROM attestations WHERE digest=?",
                              (digest,)).fetchall()
            else:
                rows=db.execute("SELECT attestation_id,rights,source_type,source_id,evidence,owner_or_generator FROM attestations WHERE digest=? AND attestation_id=?",
                               (digest,attestation_id)).fetchall()
        if not rows or not path.is_file() or path.stat().st_size!=blob[0] or sha256_file(path)!=digest:
            raise MediaCustodyError("Missing or altered stored media and provenance")
        return {"asset_id":digest,"size_bytes":blob[0],"mime":blob[1],
                "path":str(path),"rights_attestations":[{
                    "attestation_id":a,"rights":b,"source_type":c,
                    "source_id":d,"evidence":e,"owner_or_generator":f}
                    for a,b,c,d,e,f in rows]}

    def checkout(self,digest,attestation_id,destination):
        """Restore verified bytes into a working scene and keep original immutable."""
        record=self.inspect(digest,attestation_id=attestation_id)
        dest=Path(destination)
        if dest.exists():raise MediaCustodyError("Never overwrite earlier creative work")
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(record["path"],dest)
        if sha256_file(dest)!=digest:
            dest.unlink(missing_ok=True)
            raise MediaCustodyError("Copied creative media differs from immutable source")
        return record
