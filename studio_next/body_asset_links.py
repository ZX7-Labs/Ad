"""Verified, loss-free media-reference relink on a *new* ZX7 BODY host.

Existing OpenTimelineIO edits store absolute local file:// URLs and original
source SHA256 in their per-clip metadata. Restoring their project to another
machine must not silently make the edit point at old/disappeared or attacker-
replaced footage. This operator-only adapter resolves by the old workspace
prefix, physical source digest AND a verified MediaVault rights attestation.

The artist's prior timeline/track/clip order, timings, effects, original voice,
silences and notes are retained. We publish a different .otio file, never edit
the archived original, and never reinterpret old render jobs as completed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from .media_vault import MediaVault, sha256_file

_SHA = re.compile(r"^[0-9a-f]{64}$")
_RIGHTS = frozenset(("owner_supplied","generated_original","appropriately_licensed"))


def _inside(root, candidate, *, exists=True):
    """Require a regular file physically inside the designated workspace."""
    root=Path(root).resolve()
    path=Path(candidate)
    if any(p in ("..",) for p in path.parts):
        raise ValueError("Media reference contains upward traversal")
    candidate=path.resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("Media must stay inside the physically restored workspace")
    if exists and (not candidate.is_file() or path.is_symlink()):
        raise ValueError("Referenced original media does not exist as a regular file")
    return candidate


def _old_file_ref(url,old_workspace):
    if not isinstance(url,str) or len(url)>10000:
        raise ValueError("Editor source must be a bounded local file URL")
    parsed=urlsplit(url)
    if parsed.scheme!="file" or parsed.netloc not in ("","localhost") or (
            parsed.query or parsed.fragment):
        raise ValueError("Only original local file media references can be rebound")
    encoded=parsed.path
    if not encoded.startswith("/") or re.search(r"%2f|%5c|%00",encoded,re.I):
        raise ValueError("Untrusted encoded source path")
    path=unquote(encoded,encoding="utf-8",errors="strict")
    if any(x in (".","..") for x in PurePosixPath(path).parts) or chr(0) in path:
        raise ValueError("Untrusted original media path traversal")
    old=Path(old_workspace)
    if not old.is_absolute() or ".." in old.parts:
        raise ValueError("Owner must provide former absolute workspace location")
    source=Path(path)
    if not source.is_absolute() or not source.is_relative_to(old):
        raise ValueError("Original OTIO points outside the saved owner's workspace")
    rel=source.relative_to(old)
    if not rel.parts:
        raise ValueError("Original media reference points at workspace directory")
    return rel


def _original_custody_for(dest,workspace,expected_sha,rights):
    # Same project can have several independent shot-level MediaVaults.
    # Find the *nearest* enclosing vault; do not trust a differently named
    # global vault or accept an unbacked rights label inside model text.
    root=Path(workspace).resolve()
    place=Path(dest).parent
    while place.is_relative_to(root):
        db=place/"vault"/"assets.sqlite3"
        if db.is_file() and not db.is_symlink():
            vault=MediaVault(place/"vault")
            record=vault.inspect(expected_sha)
            if any(att["rights"]==rights for att in record["rights_attestations"]):
                return record
            raise ValueError("Physical media rights differ from original clip assertion")
        if place==root:
            break
        place=place.parent
    raise ValueError("Original media is not backed by a verified local MediaVault")


def _except_external_urls(value):
    """Loss-audit serialized OTIO: media URLs are the ONLY permitted edits."""
    if isinstance(value,list):
        return [_except_external_urls(item) for item in value]
    if isinstance(value,dict):
        return {key:("<verified-original-url>" if key=="target_url" else
                     _except_external_urls(item)) for key,item in value.items()}
    return value


def relink_verified_otio(source,workspace,old_workspace,output):
    """Create a separately editable OTIO after verifying every video/audio ref.

    Caller must be the project owner/operator: this function deliberately does
    not execute or re-run any creative scene from the old host.
    """
    try:
        import opentimelineio as otio
    except ImportError as exc:
        raise RuntimeError("Actual OpenTimelineIO is required") from exc
    root=Path(workspace).resolve()
    old=Path(old_workspace)
    if not old.is_absolute() or ".." in old.parts:
        raise ValueError("Former host root must be an explicit absolute path")
    original=_inside(root,source)
    destination=_inside(root,output,exists=False)
    if original.suffix.lower()!=".otio" or destination.suffix.lower()!=".otio":
        raise ValueError("Original and relinked projects must both be genuine OTIO")
    if destination.exists():
        raise FileExistsError("No replacement of previous or original editorial project")
    if destination==original:
        raise ValueError("Original creative project must remain unchanged")
    report_file=root/".zx7-relocation-report.json"
    if not report_file.is_file() or report_file.is_symlink():
        raise ValueError("A verified cross-host archive relocation is required")
    report=json.loads(report_file.read_text(encoding="utf-8"))
    if (report.get("schema")!=1 or
        report.get("recovery_mode")!="relocated_media_and_historical_state" or
        report.get("destination_workspace")!=str(root) or
        report.get("original_workspace_sha256")!=hashlib.sha256(
            str(old).encode("utf-8")).hexdigest() or
        not report.get("rebind_and_rerun_required")):
        raise ValueError("Original host identity does not match verified relocation")
    original_sha=sha256_file(original)
    with tempfile.TemporaryDirectory(
            prefix=".zx7-relink-seal-",dir=root) as private:
        sealed=Path(private)/"director-original.otio"
        with original.open("rb") as inp,sealed.open("xb") as out:
            shutil.copyfileobj(inp,out,1024*1024)
            out.flush()
            os.fsync(out.fileno())
        if sha256_file(sealed)!=original_sha or sha256_file(original)!=original_sha:
            raise RuntimeError("Original artistic timeline changed while sealing")
        os.chmod(sealed,0o400)
        timeline=otio.adapters.read_from_file(str(sealed))
    if not isinstance(timeline,otio.schema.Timeline):
        raise ValueError("Source is not an editable OTIO timeline")
    original_semantics=_except_external_urls(json.loads(
        otio.adapters.write_to_string(timeline,adapter_name="otio_json")))
    clips=list(timeline.find_clips())
    if not clips:
        raise ValueError("Empty timeline has no proven source footage")
    relinked=[]
    for clip in clips:
        if not isinstance(clip,otio.schema.Clip) or not isinstance(
                clip.media_reference,otio.schema.ExternalReference):
            raise ValueError("Unknown media reference requires separate reviewed adapter")
        reference=clip.media_reference
        previous=_old_file_ref(reference.target_url,old)
        metadata=clip.metadata.get("zx7")
        # OTIO serializes a nested mapping into its own native AnyDictionary,
        # which implements .get but does not inherit Python dict.
        if metadata is None or not callable(getattr(metadata,"get",None)):
            raise ValueError("Clip is missing original ZX7 media identity metadata")
        declared_hash=metadata.get("source_artifact_sha256")
        rights=metadata.get("rights_class")
        source_path=metadata.get("source_path")
        if not isinstance(declared_hash,str) or not _SHA.fullmatch(declared_hash):
            raise ValueError("Original edit has no valid media source checksum")
        if rights not in _RIGHTS:
            raise ValueError("Archived edit has no verified rights class")
        if not isinstance(source_path,str) or not source_path or (
                Path(source_path).is_absolute() or ".." in Path(source_path).parts):
            raise ValueError("Archived clip has invalid original relative source location")
        if (tuple(previous.parts[-len(Path(source_path).parts):]) !=
                tuple(Path(source_path).parts)):
            raise ValueError("Original clip identity disagrees with its source file URL")
        new_source=_inside(root,root/previous)
        if sha256_file(new_source)!=declared_hash:
            raise ValueError("Reconstructed footage differs from original editor SHA256")
        _original_custody_for(new_source,root,declared_hash,rights)
        reference.target_url=new_source.as_uri()
        relinked.append({
            "name":clip.name,"source_sha256":declared_hash,
            "original_path":previous.as_posix(),
            "linked_path":new_source.relative_to(root).as_posix(),
            "rights_verified":True
        })

    revised_semantics=_except_external_urls(json.loads(
        otio.adapters.write_to_string(timeline,adapter_name="otio_json")))
    if revised_semantics!=original_semantics:
        raise RuntimeError("Media migration would silently modify original creative edit")
    # Never overwrite a prior edit even on concurrent operator sessions.
    destination.parent.mkdir(parents=True,exist_ok=True)
    fd,temp_name=tempfile.mkstemp(prefix=".zx7-verified-relink-",suffix=".otio",
                                  dir=destination.parent)
    os.close(fd)
    temporary=Path(temp_name)
    try:
        otio.adapters.write_to_file(timeline,str(temporary))
        checked=otio.adapters.read_from_file(str(temporary))
        verified_clips=list(checked.find_clips())
        persisted_semantics=_except_external_urls(json.loads(
            otio.adapters.write_to_string(checked,adapter_name="otio_json")))
        if persisted_semantics!=original_semantics:
            raise RuntimeError("Professional edit failed lossless post-write roundtrip")
        if len(verified_clips)!=len(clips) or any(
                checked_clip.media_reference.target_url !=
                    original_clip.media_reference.target_url
                for original_clip,checked_clip in zip(clips,verified_clips)):
            raise RuntimeError("Re-linked physical timeline failed actual OTIO roundtrip")
        # Re-verify original artist timeline at the last trusted instant,
        # BEFORE exposing any new edit. Never delete a competing artist's
        # approved relink on a lost publication race.
        if sha256_file(original)!=original_sha:
            raise RuntimeError("Original artistic timeline was changed during relocation")
        # Lexical link creation is atomic, unlike overwriting a pre-existing
        # accepted director cut with os.replace.
        os.link(temporary,destination,follow_symlinks=False)
        with destination.open("rb") as new_file:
            os.fsync(new_file.fileno())
        directory_fd=os.open(destination.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(directory_fd)
        finally:os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "original_otio_sha256":original_sha,
        "relinked_otio_sha256":sha256_file(destination),
        "relinked_otio":str(destination),
        "source_clips":len(clips),
        "verified_media_links":relinked,
        "unmodified_original_editorial_project":True,
        "original_rights_verified_through_media_vault":True,
        "prior_host_render_jobs_reused":False,
        "all_original_timings_effects_and_edit_tracks_retained":True,
        "new_host_execution_evidence":False
    }


def main(argv=None):
    p=argparse.ArgumentParser(description="Relink original audio/video in verified relocated OTIO, without rewriting owner project")
    p.add_argument("--workspace",required=True,type=Path)
    p.add_argument("--old-workspace",required=True,type=Path)
    p.add_argument("--source",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    args=p.parse_args(argv)
    print(json.dumps(relink_verified_otio(
        args.source,args.workspace,args.old_workspace,args.out),
        sort_keys=True,indent=2,ensure_ascii=False))


if __name__=="__main__":
    main()
