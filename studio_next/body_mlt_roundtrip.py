"""Reversible, source-attested native MLT editing -> typed BODY timeline.

Read an original MLT document only after strict allowlist and physical source
verification. Unsupported native effects/metadata are NEVER silently flattened.
The recovered creative plan is portable by CAS identities, not host path strings.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

from .body_document_schemas import validate_document
from .body_mlt_editor import (
    _verify_native_opacity, _verify_native_gain, _verify_native_pan,
    build_mlt_xml, validate_mlt_edit,
    verify_owned_mlt_project,
)
from .media_vault import sha256_file
from .body_mlt_transform import decode_transform,decode_mask
from .body_mlt_grade import decode_grade


def recover_original_mlt_plan(edit, workspace, vault_root):
    """Reconstruct one exact director-owned plan from the verified MLT native graph."""
    root = Path(workspace).resolve()
    source = Path(edit).absolute()
    if (source.is_symlink() or not source.is_file()
            or source.suffix.lower() != ".mlt"
            or not source.is_relative_to(root)
            or not source.resolve().is_relative_to(root)):
        raise ValueError("Original native MLT edit must belong to the trusted workspace")
    original = source.read_bytes()
    identity = hashlib.sha256(original).hexdigest()
    verified = verify_owned_mlt_project(source)
    if sha256_file(source) != identity:
        raise ValueError("Native MLT timeline changed during original source verification")
    xml = ET.fromstring(original)
    profile = xml.find("profile")
    tractor = xml.find("tractor")
    fps = Fraction(int(profile.get("frame_rate_num")),
                   int(profile.get("frame_rate_den")))
    frames = int(tractor.get("out")) + 1
    count = verified["verified_mlt_tracks"]
    sound_count = verified["verified_audio_tracks"]

    producers = {}
    for producer in xml.findall("producer"):
        props = {p.get("name"): p.text for p in producer.findall("property")}
        digest = props["zx7.original_sha256"]
        attestation = props["zx7.attestation_id"]
        producers[producer.get("id")] = {
            "source": "zx7:sha256:" + digest,
            "asset_id": digest,
            "attestation_id": attestation,
            "audio": producer.get("id").startswith("audio-source-"),
        }

    playlists = xml.findall("playlist")
    if len(playlists) != count + sound_count:
        raise ValueError("Native MLT source contains an unrepresentable track count")
    tracks = []
    sounds = []
    for i, playlist in enumerate(playlists):
        is_sound = i >= count
        at = 0
        clips = []
        for item in playlist:
            if item.tag == "blank":
                at += int(item.get("length"))
                continue
            media = producers.get(item.get("producer"))
            if media is None or media["audio"] != is_sound:
                raise ValueError("Native cut cannot recover original picture/audio ownership")
            clip = {
                "source": media["source"],
                "asset_id": media["asset_id"],
                "attestation_id": media["attestation_id"],
                "position_frame": at,
                "first_frame": int(item.get("in")),
                "end_frame": int(item.get("out")) + 1,
            }
            if not is_sound:
                clip["audio"] = "intentional_silence"
            clips.append(clip)
            at += clip["end_frame"] - clip["first_frame"]
        if at != frames or (not clips and (i==0 or is_sound)):
            raise ValueError("Original MLT bottom picture/sound must retain its source span")
        (sounds if is_sound else tracks).append({"clips": clips})

    visual_transitions = tractor.findall("transition")[:max(0, count-1)]
    if len(visual_transitions) != max(0, count-1):
        raise ValueError("Native MLT visual blend graph cannot be represented")
    for i, transition in enumerate(visual_transitions, start=1):
        props = {p.get("name"): p.text for p in transition.findall("property")}
        if props["mlt_service"] == "qtblend":
            continue
        if props["mlt_service"] != "frei0r.cairoblend":
            raise ValueError("Original NLE blend plugin cannot be losslessly recovered")
        mode = props["1"]
        encoded = _verify_native_opacity(props["0"], frames)
        if mode != "normal":
            tracks[i]["blend_mode"] = mode
        if "=" in encoded:
            tracks[i]["opacity_keyframes"] = [
                {"frame": int(piece.split("=")[0]),
                 "opacity": float(piece.split("=")[1])}
                for piece in encoded.split(";")
            ]
        elif encoded != "1":
            tracks[i]["opacity"] = float(encoded)

    plan = {
        "frame_rate": {"numerator": fps.numerator, "denominator": fps.denominator},
        "frame_size": {
            "width": int(profile.get("width")),
            "height": int(profile.get("height")),
        },
        "tracks": tracks,
    }
    for filt in tractor.findall("filter"):
        properties={p.get("name"):p.text for p in filt.findall("property")}
        if properties["mlt_service"] in ("lift_gamma_gain","qtcrop","qtblend"):
            ti=int(properties["track"])
            if properties["mlt_service"]=="lift_gamma_gain":
                tracks[ti]["grade"]=decode_grade(properties,frames)
            elif properties["mlt_service"]=="qtcrop":
                tracks[ti]["mask"]=decode_mask(properties,frames)
            else:tracks[ti]["transform"]=decode_transform(properties,frames)
    if sounds:
        for filt in tractor.findall("filter"):
            properties={p.get("name"):p.text for p in filt.findall("property")}
            if properties["mlt_service"] in ("lift_gamma_gain","qtcrop","qtblend"):
                continue
            ti=int(properties["track"])-count
            if not 0<=ti<len(sounds):
                raise ValueError("Native audio filter lost its original source identity")
            if properties["mlt_service"]=="volume":
                encoded=_verify_native_gain(properties["level"],frames)
                name="gain_db"
                target="gain_keyframes"
                neutral="0"
            elif properties["mlt_service"]=="panner":
                encoded=_verify_native_pan(properties["split"],frames)
                name="pan"
                target="pan_keyframes"
                neutral="0.5"
            else:
                raise ValueError("Unrecognized original sound editor control")
            if "=" in encoded:
                sounds[ti][target]=[
                    {"frame":int(key.split("=")[0]),
                     name:float(key.split("=")[1])}
                    for key in encoded.split(";")]
            else:
                # A present neutral filter is an explicit owner edit.
                # Skipping it would silently erase artist-intent metadata.
                sounds[ti][name]=float(encoded)
        plan["audio_tracks"] = sounds
    validate_document("body.mlt_owned_export", plan)
    checked = validate_mlt_edit(plan, root, vault_root)
    if checked["frames"] != frames:
        raise ValueError("Recovering native MLT would alter its physical film length")

    # Validate a *complete canonical rebuild*, not just a shallow scene count:
    # track gaps, original audio stream indices, blend modes, keyframes and all
    # source attestation properties must survive the reverse translation.
    replay = ET.fromstring(build_mlt_xml(plan, checked))
    if verified["legacy_postmix_audio_filters"]:
        # Reconstruct the historical representation for exact custody
        # comparison. New exports intentionally place independent controls
        # before mixing. Preserve old bytes and disclose that migration.
        legacy_tractor=replay.find("tractor")
        for filt in legacy_tractor.findall("filter"):
            legacy_tractor.remove(filt)
            legacy_tractor.append(filt)
    canonical = lambda node: ET.canonicalize(
        ET.tostring(node, encoding="unicode"), strip_text=True)
    if canonical(replay) != canonical(xml):
        raise ValueError("Native MLT contains an edit that cannot roundtrip without loss")
    if sha256_file(source) != identity:
        raise ValueError("Native MLT was changed while recovering the editable plan")
    return {
        "plan": plan,
        "source_mlt_sha256": identity,
        "original_picture_tracks": count,
        "original_sound_tracks": sound_count,
        "frames": frames,
        "fully_verified_rights": True,
        "lossless_typed_native_roundtrip": True,
        "legacy_audio_bus_order_requires_migration":verified["legacy_postmix_audio_filters"],
        "creative_quality_approved": False,
    }


def import_owned_mlt_project(edit, workspace, vault_root, output):
    """Atomically publish exact, reproducible JSON for future artist revisions."""
    root = Path(workspace).resolve()
    target = Path(output).absolute()
    if (not target.is_relative_to(root)
            or not target.resolve().is_relative_to(root)
            or target.suffix.lower() != ".json"):
        raise ValueError("Recovered MLT plan requires a workspace-owned JSON destination")
    if target.exists() or target.is_symlink():
        raise FileExistsError("Never overwrite original recovered native editor decisions")
    recovered = recover_original_mlt_plan(edit, root, vault_root)
    contents = (json.dumps(recovered["plan"], ensure_ascii=False,
                           sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".zx7-mlt-recover-", dir=target.parent) as tmp:
        prepared = Path(tmp) / "fully-recovered.json"
        with prepared.open("xb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        if sha256_file(prepared) != hashlib.sha256(contents).hexdigest():
            raise ValueError("Recovered native source plan changed during publication")
        os.link(prepared, target)
    return {
        "path": str(target),
        "sha256": sha256_file(target),
        "bytes": len(contents),
        "source_mlt_sha256": recovered["source_mlt_sha256"],
        "verified_original_picture_tracks": recovered["original_picture_tracks"],
        "verified_original_sound_tracks": recovered["original_sound_tracks"],
        "verified_original_frames": recovered["frames"],
        "lossless_typed_native_roundtrip": True,
        "legacy_audio_bus_order_requires_migration":recovered["legacy_audio_bus_order_requires_migration"],
        "creative_quality_approved": False,
    }
