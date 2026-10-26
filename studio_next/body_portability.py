"""Fail-closed portable BODY workspace import for a *new* compute host.

Archived media bytes and owner rights remain immutable. Old completed/running
jobs and absolute-path publication receipts must never turn into executable
cache hits at a different workspace path. Such host-bound operational state is
preserved under an inert historical namespace, not silently thrown away or
rewritten to claim that a previous effect ran on the new machine.

This prepares a verified staging tree BEFORE atomic restoration. It is called
only after an operator-supplied digest verified the entire original archive
and every member has independently matched the archive's SHA manifest.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

_HISTORY = ".zx7-relocated-history"
_REPORT = ".zx7-relocation-report.json"
_OPERATIVE = {"body-service.lock"}
_DIGEST = set("0123456789abcdef")


def _historical_runtime(rel: Path) -> bool:
    """Identify old host-bound execution controls, not artistic source."""
    pieces=rel.parts
    if ".zx7-publications" in pieces or ".zx7-frame-checkpoints" in pieces:
        # Render-checkpoint identities bind executable/tool version and host
        # locks. They belong to the original machine, not the artist source
        # files; keep their bytes for review but never activate on new host.
        return True
    if rel.name.startswith(".zx7-uncommitted-"):
        return True
    if rel.name in _OPERATIVE:
        return True
    if rel.suffix.lower() in (".sqlite3",".db"):
        # This is a content-addressed MediaVault database. It records digest,
        # size and rights attestations; *not* the original host absolute path.
        return pieces[-2:] not in (("vault","assets.sqlite3"),)
    # SQLite journals/shm are already excluded from the archive writer.
    return False


def prepare_relocated_workspace(staging, *, old_root, destination, archive_sha256):
    """Quarantine unsafe old execution metadata, retain all original bytes.

    Do not edit job JSON, OTIO references, checkpoint fingerprints or historical
    publication receipts. An imported film can start a *new* production job after
    its sources, host tools, and any path-bound visual references are reviewed.
    """
    root=Path(staging).resolve()
    dest=Path(destination).resolve()
    old=Path(old_root)
    if not old.is_absolute() or str(old.resolve())==str(dest):
        raise ValueError("Relocation requires a different original absolute workspace")
    if not isinstance(archive_sha256,str) or len(archive_sha256)!=64 or any(
            c not in _DIGEST for c in archive_sha256):
        raise ValueError("Portable import requires exact verified archive SHA256")

    # Never allow source content to impersonate the newly generated report or
    # collision-safe historical storage, even inside a nested source folder.
    source_files=sorted(p for p in root.rglob("*") if p.is_file())
    for item in source_files:
        relative=item.relative_to(root)
        if (_HISTORY in relative.parts or relative==Path(_REPORT) or
                any(p.is_symlink() for p in [item,*item.parents] if p!=root
                    and p.is_relative_to(root))):
            raise ValueError("Untrusted source collides with relocated state")

    history=root/_HISTORY
    moved=[]
    for item in source_files:
        relative=item.relative_to(root)
        if not _historical_runtime(relative):
            continue
        target=history/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():
            raise FileExistsError("Imported original state collides with history")
        os.replace(item,target)
        moved.append(relative.as_posix())

    # Only historical receipts/frames are permitted at the destination.
    # Remove the now-empty old-host checkpoint folder itself: otherwise an
    # unrelated new local worker could mistake its existence for initialized
    # runtime state despite all actual frame files being quarantined.
    stale_roots=[p for p in root.rglob(".zx7-frame-checkpoints")
                 if _HISTORY not in p.relative_to(root).parts and p.is_dir()]
    for stale in stale_roots:
        for folder in sorted((p for p in stale.rglob("*") if p.is_dir()),
                             key=lambda p:len(p.parts),reverse=True):
            folder.rmdir()
        stale.rmdir()

    # A portably retained asset vault is still subject to MediaVault's normal
    # content digest + attestation verification on every checkout/invocation.
    media_files=sum(
        1 for item in source_files
        if not _historical_runtime(item.relative_to(root)))
    report={
        "schema":1,
        "recovery_mode":"relocated_media_and_historical_state",
        "verified_original_archive_sha256":archive_sha256,
        "original_workspace_sha256":hashlib.sha256(str(old).encode()).hexdigest(),
        "destination_workspace":str(dest),
        "original_source_bytes_preserved":True,
        "media_vault_custody_retained":True,
        "historical_metadata_moved":sorted(moved),
        "historical_metadata_count":len(moved),
        "media_and_original_project_files":media_files,
        "old_job_queues_not_restarted":True,
        "old_graph_and_publication_caches_not_reused":True,
        "original_editable_timelines_may_have_absolute_media_references":True,
        "rebind_and_rerun_required":True,
        "ready_to_autonomously_resume_original_jobs":False,
        "technical_claim":"Relocated project is an immutable-source import, NOT an old film execution proof"
    }
    receipt=root/_REPORT
    with receipt.open("x",encoding="utf-8") as f:
        json.dump(report,f,sort_keys=True,ensure_ascii=False,indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    return report
