"""Rebind an archived native MLT edit to restored CAS without touching old paths.

Only resource properties change. Source hashes, precise attestation identities,
all picture/audio clocks and editable effects survive exact native roundtrip.
Old job receipts stay inert; a relinked project requires fresh execution proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from .body_asset_links import _inside,_verified_relocation_report
from .body_mlt_editor import _verify_exact_mlt_xml_tree,verify_owned_mlt_project
from .body_mlt_roundtrip import recover_original_mlt_plan
from .media_vault import MediaVault,sha256_file


def inspect_relocated_mlt(edit,workspace,old_workspace):
    """Validate a sealed XML value and freshly restored physical source custody.

    This never parses the former source location as an executable XML producer
    or opens an old-host file. It is also the dependency-fingerprint preflight.
    """
    root=Path(workspace).resolve();old=Path(old_workspace)
    report,report_file,report_sha=_verified_relocation_report(root,old)
    source=_inside(root,edit)
    if source.suffix.lower()!=".mlt" or not 100<=source.stat().st_size<=2*1024*1024:
        raise ValueError("Relocation requires a bounded workspace-owned native MLT edit")
    raw=source.read_bytes();identity=hashlib.sha256(raw).hexdigest()
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("Native relocation cannot contain executable XML entities")
    try:xml=ET.fromstring(raw)
    except ET.ParseError as exc:raise ValueError("Native relocation source XML is corrupt") from exc
    _verify_exact_mlt_xml_tree(xml)
    references=[]
    for producer in xml.findall("producer"):
        p={p.get("name"):p for p in producer.findall("property")}
        digest=p["zx7.original_sha256"].text;att=p["zx7.attestation_id"].text
        if any(not isinstance(v,str) or not re.fullmatch("[0-9a-f]{64}",v) for v in (digest,att)):
            raise ValueError("Relocation needs exact original source and attestation identities")
        previous=p["resource"].text;path=Path(previous)
        if (not path.is_absolute() or str(path)!=previous or ".." in path.parts
                or not path.is_relative_to(old) or path==old):
            raise ValueError("Native original source points outside its verified former workspace")
        relative=path.relative_to(old)
        current=_inside(root,root/relative)
        if (current.name!=digest or current.parent.name!=digest[:2] or
                current.parent.parent.name!="objects"):
            raise ValueError("Native relink source is not an exact restored CAS location")
        database=current.parents[2]/"assets.sqlite3"
        if not database.is_file() or database.is_symlink():
            raise ValueError("Native relink cannot create or invent missing source custody")
        record=MediaVault(current.parents[2]).inspect(digest,attestation_id=att)
        if Path(record["path"])!=current:
            raise ValueError("Restored native source has no matching physical custody")
        p["resource"].text=str(current)
        references.append({"path":current,"digest":digest,"attestation":att})
    if sha256_file(source)!=identity or sha256_file(report_file)!=report_sha:
        raise RuntimeError("Native edit or relocation identity changed during inspection")
    return {"xml":xml,"source":source,"source_sha256":identity,
            "references":references,"report":report,"report_path":report_file,
            "report_sha256":report_sha,"original_bytes":raw}


def _without_resource(xml):
    clone=ET.fromstring(ET.tostring(xml,encoding="utf-8"))
    for node in clone.findall("./producer/property"):
        if node.get("name")=="resource":node.text="<verified-restored-CAS>"
    return ET.canonicalize(ET.tostring(clone,encoding="unicode"),strip_text=True)


def relink_owned_mlt_project(edit,workspace,old_workspace,output):
    """Publish a NEW native edit, after full native/source roundtrip validation."""
    root=Path(workspace).resolve();destination=_inside(root,output,exists=False)
    if destination.suffix.lower()!=".mlt" or Path(output).is_symlink():
        raise ValueError("Relink destination must be a fresh workspace-owned MLT file")
    if destination.exists():raise FileExistsError("Never overwrite an original native edit")
    prepared=inspect_relocated_mlt(edit,root,old_workspace)
    xml=prepared["xml"];original=prepared["source"]
    original_semantics=_without_resource(ET.fromstring(prepared["original_bytes"]))
    if _without_resource(xml)!=original_semantics:
        raise ValueError("Relocation would change an original native creative decision")
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".zx7-verified-relink-",dir=destination.parent) as temp:
        candidate=Path(temp)/"rebound.mlt"
        ET.indent(xml,space="  ")
        with candidate.open("xb") as stream:
            stream.write(ET.tostring(xml,encoding="utf-8",xml_declaration=True)+b"\n")
            stream.flush();os.fsync(stream.fileno())
        native=verify_owned_mlt_project(candidate)
        recovered=recover_original_mlt_plan(candidate,root,root/"vault")
        if not recovered["lossless_typed_native_roundtrip"]:
            raise ValueError("Rebound native edit cannot preserve all artistic decisions")
        if _without_resource(ET.fromstring(candidate.read_bytes()))!=original_semantics:
            raise ValueError("Rebound native file changed a source window, effect or audio decision")
        if (sha256_file(original)!=prepared["source_sha256"] or
                sha256_file(prepared["report_path"])!=prepared["report_sha256"]):
            raise RuntimeError("Native edit or relocation identity changed before publication")
        for reference in prepared["references"]:
            record=MediaVault(reference["path"].parents[2]).inspect(
                reference["digest"],attestation_id=reference["attestation"])
            if Path(record["path"])!=reference["path"]:
                raise ValueError("Native original custody changed before relink publication")
        os.link(candidate,destination)
    directory=os.open(destination.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(directory)
    finally:os.close(directory)
    return {"path":str(destination),"sha256":sha256_file(destination),
            "bytes":destination.stat().st_size,
            "prior_mlt_sha256":prepared["source_sha256"],
            "verified_original_archive_sha256":prepared["report"]["verified_original_archive_sha256"],
            "verified_original_source_producers":native["verified_original_sources"],
            "picture_tracks":native["verified_mlt_tracks"],"audio_tracks":native["verified_audio_tracks"],
            "lossless_typed_native_roundtrip":True,"original_native_project_untouched":True,
            "old_host_sources_opened":False,"prior_host_render_jobs_reused":False,
            "new_host_execution_evidence":False,"creative_or_professional_release_approved":False}


def main(argv=None):
    parser=argparse.ArgumentParser(description="Rebind verified relocated native MLT media without modifying original projects")
    for name in ("workspace","old-workspace","source","out"):
        parser.add_argument("--"+name,required=True,type=Path)
    args=parser.parse_args(argv)
    print(json.dumps(relink_owned_mlt_project(args.source,args.workspace,args.old_workspace,args.out),sort_keys=True,indent=2))


if __name__=="__main__":main()
