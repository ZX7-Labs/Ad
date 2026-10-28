"""Non-destructive, rights-attested native video editor revisions.

The director may change any *currently supported* typed visual/sound edit
through guarded JSON Pointer operations, rather than one hardcoded sequence
of creative gestures. Every revision is a new native editable MLT project.
Unrecognized native effects fail closed on import; no rights/clock is invented.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from .body_document_schemas import validate_document
from .body_mlt_editor import export_owned_mlt, validate_mlt_edit
from .body_mlt_roundtrip import recover_original_mlt_plan
from .body_project_revision import revise_document
from .media_vault import sha256_file


def _owner_file(root, value, suffix):
    candidate=Path(value)
    if not candidate.is_absolute():
        candidate=root/candidate
    candidate=candidate.absolute()
    if (candidate.suffix.lower()!=suffix or candidate.is_symlink() or
            not candidate.is_file() or not candidate.resolve().is_relative_to(root)):
        raise ValueError("Original editorial input must be a workspace-owned "+suffix+" file")
    return candidate


def _unique_json(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ValueError("Duplicate native editorial revision property")
        result[key]=value
    return result


def _no_nonfinite(value):
    raise ValueError("Native editorial revision cannot contain nonfinite values")


def revise_owned_mlt_project(edit, operations, workspace, vault_root, output):
    """Publish a complete new native project iff the authored patch really survives.

    Applies an arbitrary sequence of typed JSON Pointer add/remove/replace/test
    operations to the exact native project recovered from real original media.
    Security, permission and host constraints are handled by the existing
    MediaVault/editor schemas, *not* relaxed by generalized creative controls.
    """
    root=Path(workspace).resolve()
    prior=_owner_file(root,edit,".mlt")
    changes=_owner_file(root,operations,".json")
    target=Path(output)
    if not target.is_absolute():
        target=root/target
    target=target.absolute()
    if (target.suffix.lower()!=".mlt" or not target.is_relative_to(root)
            or not target.resolve().is_relative_to(root)
            or target.is_symlink() or target.exists()
            or target==prior or target==changes):
        raise ValueError("Revision must publish a fresh workspace-owned native project")
    if changes.stat().st_size>262144:
        raise ValueError("Director-authored revision exceeds available host budget")

    original_sha=sha256_file(prior)
    instruction_sha=sha256_file(changes)
    raw=changes.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=instruction_sha:
        raise ValueError("Native editorial revision commands changed during read")
    try:
        command=json.loads(raw,object_pairs_hook=_unique_json,
                           parse_constant=_no_nonfinite)
    except (UnicodeError,json.JSONDecodeError,RecursionError) as exc:
        raise ValueError("Native revision must be a valid finite JSON document") from exc
    if not isinstance(command,dict) or set(command)!={"operations"}:
        raise ValueError("Revision must contain only the director-authored operations")
    recovered=recover_original_mlt_plan(prior,root,vault_root)
    if recovered["source_mlt_sha256"]!=original_sha:
        raise ValueError("Original native timeline identity drifted during recovery")
    candidate=revise_document(recovered["plan"],command["operations"])
    if candidate==recovered["plan"]:
        raise ValueError("Native revision must change at least one actual creative decision")
    validate_document("body.mlt_owned_export",candidate)
    checked=validate_mlt_edit(candidate,root,vault_root)
    if not isinstance(checked["frames"],int) or checked["frames"]<1:
        raise ValueError("Original revision has no verified video frame clock")

    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.parent.resolve().is_relative_to(root):
        raise ValueError("Original editor output parent escaped the owned workspace")
    with tempfile.TemporaryDirectory(dir=target.parent,
                                     prefix=".zx7-native-revision-") as temporary:
        stage=Path(temporary)
        authored=stage/"director-source-verified.json"
        with authored.open("xb") as output_stream:
            output_stream.write((json.dumps(candidate,ensure_ascii=False,
                           sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode())
            output_stream.flush()
            os.fsync(output_stream.fileno())
        native=stage/"revised.mlt"
        export_owned_mlt(authored,root,vault_root,native)
        proof=recover_original_mlt_plan(native,root,vault_root)
        if proof["plan"]!=candidate or not proof["lossless_typed_native_roundtrip"]:
            raise ValueError("Native editing would discard an authenticated creative decision")
        # Confirm the complete native graph is still source-identical; no other
        # process may change our old revision or instruction during publication.
        if sha256_file(prior)!=original_sha or sha256_file(changes)!=instruction_sha:
            raise ValueError("Original timeline or author edits changed before publication")
        for digest,item in {**checked["sources"],
                            **checked["audio_sources"]}.items():
            if sha256_file(item["path"])!=digest:
                raise ValueError("Original video or audio custody changed before publication")
        os.link(native,target)
        digest=sha256_file(target)
        if digest!=sha256_file(native):
            raise ValueError("New native revision is not source-identical")
    return {
        "path":str(target),"sha256":digest,
        "prior_mlt_sha256":original_sha,
        "director_operations_sha256":instruction_sha,
        "picture_tracks":proof["original_picture_tracks"],
        "sound_tracks":proof["original_sound_tracks"],
        "frames":proof["frames"],
        "lossless_typed_native_roundtrip":True,
        "original_media_rights_rechecked":True,
        "prior_native_project_untouched":True,
        "creative_or_professional_release_approved":False,
    }
