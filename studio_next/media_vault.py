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
from .durable_sqlite import connect_durable_database

_DIGEST=re.compile(r"^[0-9a-f]{64}$")
_RIGHTS={"owner_supplied","generated_original","appropriately_licensed"}
_ALLOWED_MIME={"image/png","image/jpeg","image/webp","image/svg+xml",
 "image/x-exr","video/mp4","video/quicktime","video/webm",
 "audio/wav","audio/mpeg","audio/flac","font/ttf","font/otf",
 "model/gltf-binary","application/octet-stream",
 "application/x-zx7-exr-bundle"}
class MediaCustodyError(ValueError):
    pass


def verify_media_container(path,mime):
    """Physical decoder/magic check; provenance text alone cannot create a film."""
    path=Path(path)
    if mime.startswith("video/"):
        if shutil.which("ffprobe") is None:
            raise MediaCustodyError("Real video decoder not installed; refuse unverifiable source")
        from .delivery_audit import _probe_details
        import subprocess
        try:
            return _probe_details(path)
        except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as exc:
            # Source footage failures are an ordinary untrusted upload error,
            # not an uncaught internal server exception or valid asset.
            raise MediaCustodyError("Claimed video has no real decodable media stream") from exc
    if mime=="image/png":
        with path.open("rb") as f:
            first=f.read(24)
        if len(first)<24 or first[:8]!=bytes([137,80,78,71,13,10,26,10]) or (
             int.from_bytes(first[16:20],"big")<=0 or
             int.from_bytes(first[20:24],"big")<=0):
            raise MediaCustodyError("Original PNG image signature and dimensions are invalid")
        try:
            from PIL import Image
        except ImportError:
            # Do not mistake a leading PNG signature for real image pixels.
            # Production hosts with image tools have either Pillow or FFmpeg.
            if shutil.which("ffmpeg") is None:
                raise MediaCustodyError("A real PNG decoder is not installed")
            import subprocess
            decoded=subprocess.run(["ffmpeg","-hide_banner","-loglevel","error",
                      "-xerror","-nostdin","-i",str(path),
                      "-frames:v","1","-f","null","-"],
                      capture_output=True,timeout=90,check=False)
            if decoded.returncode!=0:
                raise MediaCustodyError("Claimed original PNG is not pixel-decodable")
        else:
            try:
                with Image.open(path) as image:
                    image.verify()
                with Image.open(path) as image:
                    image.load()
                    if image.width<=0 or image.height<=0:
                        raise MediaCustodyError("Empty original PNG image")
            except (OSError,ValueError,SyntaxError) as exc:
                raise MediaCustodyError("Claimed original PNG is not pixel-decodable") from exc
    elif mime=="audio/wav":
        import wave
        try:
            with wave.open(str(path),"rb") as audio:
                if audio.getnframes()<1 or audio.getframerate()<1:
                    raise MediaCustodyError("Decoded sound file has no actual samples")
        except wave.Error as exc:
            raise MediaCustodyError("WAV identity is not backed by actual PCM") from exc
    elif mime=="image/svg+xml":
        from .creative_asset_ops import validate_original_svg_art
        validate_original_svg_art(path)
    elif mime=="model/gltf-binary":
        with path.open("rb") as f:
            first=f.read(12)
        if len(first)!=12 or first[:4]!=b"glTF":
            raise MediaCustodyError("Claimed 3D GLB is not a real binary scene")
    elif mime=="application/x-zx7-exr-bundle":
        # Never grant trusted CG source rights to an arbitrary ZIP or opaque
        # binary. Real native OpenEXR re-decodes ALL physically rendered
        # float32 RGBA, depth, normal and motion passes on ingest.
        from .body_exr_passes import verify_exr_bundle
        import zipfile
        try:
            actual=verify_exr_bundle(path)
            if not (actual["original_exr_passes_real"] and
                    actual["reloaded_every_frame_and_sha256_verified"]):
                raise MediaCustodyError("Unverified original 32f EXR frame archive")
        except (ValueError,RuntimeError,TypeError,OSError,KeyError,
                zipfile.BadZipFile) as exc:
            raise MediaCustodyError(
                "Not a physically decoded and verified native 32f EXR bundle") from exc
    elif mime in ("audio/mpeg","audio/flac"):
        import subprocess
        try:
            data=json.loads(subprocess.check_output(["ffprobe","-v","error",
                  "-show_entries","stream=codec_type","-of","json",str(path)],timeout=60))
        except (OSError,ValueError,subprocess.SubprocessError) as exc:
            raise MediaCustodyError("Claimed audio does not contain a decodable stream") from exc
        if not any(x.get("codec_type")=="audio" for x in data.get("streams",[])):
            raise MediaCustodyError("No original decoded source sound")
    elif mime.startswith("image/"):
        try:
            from PIL import Image
            with Image.open(path) as image:
                image.verify()
        except (ImportError,OSError,ValueError) as exc:
            raise MediaCustodyError("No decoded original graphic available") from exc
    # font/ttf, font/otf and binary originals require trusted import provenance
    # and specialized renderers inspect them before use; never call them video.
    return {"actual_file_bytes_checked":True}


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
        db=connect_durable_database(self.db)
        db.execute("PRAGMA foreign_keys=ON")
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
        verify_media_container(path,mime)
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
                os.link(tmp,dest)
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
