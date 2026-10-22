"""An independently rights-attested use of the existing mixed-source FFmpeg editor.

Unlike legacy body.render_edit, no owner/model-provided 'rights' label is
accepted as source custody. Every actual input is bound to an immutable
MediaVault blob and the *exact* attestation, before and after real encoding.
No changes to the original director cut, frame choices, source or soundtrack.
This remains a fit/fill sequential-cut adapter, not a full NLE.
"""
from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

from .edit_timeline import validate_edit, edit_ffmpeg_command, probe_media, _path_within
from .media_vault import MediaVault, sha256_file


def validate_owned_edit(plan, workspace, vault_root):
    """Return a plain editor plan and frozen source identities; no write."""
    root=Path(workspace).resolve()
    if not isinstance(plan,dict) or set(plan)!={"format","clips"} or (
            not isinstance(plan["clips"],list) or not 1<=len(plan["clips"])<=128):
        raise ValueError("Source-attested original edit needs a bounded director timeline")
    vault=MediaVault(vault_root)
    cleaned=copy.deepcopy(plan)
    originals={}
    for index,clip in enumerate(plan["clips"]):
        if not isinstance(clip,dict) or set(clip)!={
                "id","source","rights","audio","asset_id","attestation_id"}:
            raise ValueError(f"Source-attested clip {index} lacks custody")
        cleaned["clips"][index].pop("asset_id")
        cleaned["clips"][index].pop("attestation_id")
        if not isinstance(clip["asset_id"],str) or not isinstance(clip["attestation_id"],str):
            raise ValueError("Original input needs exact content digest and attestation")
        file=_path_within(root,clip["source"],exists=True)
        if (root/clip["source"]).is_symlink():
            raise ValueError("Linked original shot is not trusted")
        observed=vault.inspect(clip["asset_id"],attestation_id=clip["attestation_id"])
        proofs=observed["rights_attestations"]
        if (observed["mime"] not in ("video/mp4","video/quicktime","video/webm") or
                len(proofs)!=1 or proofs[0]["rights"]!=clip["rights"]):
            raise ValueError("Original editor source rights or type differ from stored evidence")
        if sha256_file(file)!=clip["asset_id"]:
            raise ValueError("Original frame source differs from stored content")
        originals[str(file)]=clip["asset_id"]
    validate_edit(cleaned,root)
    return cleaned,originals


def render_verified_owned_edit(plan_file, workspace, vault_root, output):
    root=Path(workspace).resolve()
    plan_file=Path(plan_file).resolve()
    output=Path(output).resolve()
    if (not plan_file.is_relative_to(root) or not plan_file.is_file() or
            plan_file.is_symlink() or not output.is_relative_to(root)
            or output.suffix.lower()!=".mp4" or output.exists()):
        raise ValueError("Original editor needs owner-controlled plan and new MP4")
    before=sha256_file(plan_file)
    plan=json.loads(plan_file.read_text(encoding="utf-8"))
    if sha256_file(plan_file)!=before:
        raise ValueError("Original editor plan changed before custody inspection")
    clean,originals=validate_owned_edit(plan,root,vault_root)
    sources=[probe_media(_path_within(root,c["source"],exists=True))
             for c in clean["clips"]]
    # Probe cannot convey custody authority; the attested CAS check above can.
    if sha256_file(plan_file)!=before or any(
            sha256_file(path)!=digest for path,digest in originals.items()):
        raise ValueError("Original source or plan changed before the actual encoder")
    output.parent.mkdir(parents=True,exist_ok=True)
    try:
        command=edit_ffmpeg_command(clean,root,output,source_info=sources)
        # No arbitrary owner/model shell commands. No unverified auto downloads.
        complete=subprocess.run(command,capture_output=True,text=True,timeout=3600)
        if complete.returncode:
            raise RuntimeError("Source-attested native editor failed: "+complete.stderr[-1400:])
        final=probe_media(output)
        if not final["audio"]:
            raise RuntimeError("Encoded film lacks independently decoded soundtrack")
        if sha256_file(plan_file)!=before or any(
                sha256_file(path)!=digest for path,digest in originals.items()):
            raise ValueError("Original footage or director cut changed while encoding")
        return {"source_custody_count":len(clean["clips"]),
                "distinct_originals":len(originals),
                "plan_sha256":before,
                "encoded_media_probe":final,
                "original_footage_unchanged":True,
                "ownership_independently_legally_certified":False,
                "artistic_quality_certified":False}
    except BaseException:
        output.unlink(missing_ok=True)
        raise
