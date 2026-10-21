"""Exact immutable HTTP byte snapshot for owner-authorized BODY artifacts.

The same closed physical bytes whose SHA256/length were verified are delivered.
A sender must NEVER hash one media path and later reopen that path for serving:
another renderer/process can replace or mutate it between verification and
send, even when the HTTP ticket itself was valid.

TemporaryFile is disk-backed on normal Linux, never a full memory buffer.
Opening originals uses O_NOFOLLOW, regular-file fstat and a bounded scratch
space preflight. No source file is modified and no model receives shell access.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path

_DIGEST=re.compile(r"^[0-9a-f]{64}$")
_CHUNK=1024*1024
_RESERVED_BYTES=16*1024*1024


@contextmanager
def verified_artifact_snapshot(media,*,scratch=None,free_space=None):
    """Copy + verify whole source BEFORE sending 200/Content-Length headers.

    Reject source alteration, link exchange, truncated/extended media and
    insufficient scratch disk, even if the file changed after inspect_media
    or a downloader already consumed its one-use URL.
    """
    if not isinstance(media,dict):
        raise ValueError("Physical BODY artifact evidence required")
    path=media.get("path")
    digest=media.get("sha256")
    length=media.get("bytes")
    if not isinstance(path,(str,Path)) or not isinstance(digest,str) or (
            not _DIGEST.fullmatch(digest) or type(length) is not int or length<=0):
        raise ValueError("Actual artifact hash, byte size and path required")
    location=Path(scratch or tempfile.gettempdir())
    if not location.is_dir() or location.is_symlink():
        raise ValueError("Unsafe original media transfer staging directory")
    free=(shutil.disk_usage(location).free if free_space is None else free_space)
    if type(free) is not int or free<0:
        raise ValueError("Invalid real host storage capacity measurement")
    # Refuse a snapshot that could exhaust host disk. This is a resource gate,
    # NOT a creative format/duration/resolution limit.
    if free<length+_RESERVED_BYTES:
        raise RuntimeError("Insufficient physical host disk for verified media delivery")
    flags=os.O_RDONLY|getattr(os,"O_CLOEXEC",0)|getattr(os,"O_NOFOLLOW",0)
    fd=os.open(path,flags)
    try:
        with os.fdopen(fd,"rb") as original, tempfile.TemporaryFile(
                mode="w+b",dir=location) as delivery:
            fd=-1
            actual_stat=os.fstat(original.fileno())
            if not stat.S_ISREG(actual_stat.st_mode):
                raise ValueError("Only regular immutable media artifacts may be downloaded")
            if actual_stat.st_size!=length:
                raise ValueError("Original artifact size differs from authorized evidence")
            computed=hashlib.sha256()
            count=0
            while True:
                data=original.read(_CHUNK)
                if not data:
                    break
                count+=len(data)
                if count>length:
                    raise ValueError("Original media grew during proof snapshot")
                delivery.write(data)
                computed.update(data)
            if count!=length or computed.hexdigest()!=digest:
                raise ValueError("Original media bytes differ from authorized SHA256 evidence")
            delivery.flush()
            delivery.seek(0)
            yield delivery
    finally:
        if fd>=0:
            os.close(fd)
