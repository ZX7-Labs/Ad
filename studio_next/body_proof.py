"""Real complete technical body interoperation acceptance fixture, NOT an AI film.

From actual previously rendered 2D and Blender 3D MP4s, this proves:
local media detection -> rights provenance -> concurrent dependency graph ->
real FFmpeg cut -> OpenTimelineIO editable cut -> genuine thumbnail and
Inkscape vector art -> exact node resume -> objective audiovisual QA.

It does not demonstrate a photoreal AI actor, original scene-creation model,
premium editing judgement or a finished consumer ZX7 application.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from .body_integration import run_body_project
from .delivery_audit import audit_delivered_movie
from .edit_timeline import probe_media


def _one(root,name):
    found=[f for f in root.rglob(name) if f.is_file()]
    if len(found)!=1:
        raise ValueError("A genuine unique archived creative media source is required: "+name)
    return found[0]


def assemble_body_evidence(archived,folder):
    base=Path(folder).resolve()
    if base.exists() and any(base.iterdir()):
        raise FileExistsError("Do not overwrite earlier original multi-engine proof")
    base.mkdir(parents=True,exist_ok=True)
    original=Path(archived)
    for filename,dest in (("sample.mp4","zx7-2d/sample.mp4"),
                          ("scene-3d.mp4","zx7-real-3d/scene-3d.mp4")):
        src=_one(original,filename)
        target=base/dest
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(src,target)
    # The registered body tech proof has this fixture: no fixed style imposed
    # on arbitrary user films or their actual independent artistic work.
    fixture=Path(__file__).resolve().parent/"fixtures"/"mixed_engine_timeline.json"
    shutil.copyfile(fixture,base/"original-edit.json")
    sample=base/"original-edit.json"
    total=sum(probe_media(base/c["source"])["seconds"]
              for c in json.loads(sample.read_text())["clips"])
    art=base/"designer-original"
    art.mkdir()
    (art/"artwork.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
        '<defs><linearGradient id="texture"><stop stop-color="#141423"/>'
        '<stop offset="1" stop-color="#6fb4bd"/></linearGradient></defs>'
        '<rect width="1280" height="720" fill="url(#texture)"/>'
        '<text x="110" y="320" fill="#ffffff" font-size="84">ZX7 BODY PROOF</text>'
        '<text x="114" y="420" fill="#ffffff" font-size="32">'
        'Real tools. Actual audiovisual media. Not an AI-created film.</text></svg>',
        encoding="utf-8")
    # Technical proof only, model-authored commissions choose different art,
    # scene count, video dimensions, timings, tools and creative purpose.
    specs=[
        ("vector","body.vector_png",{"source_svg":"designer-original/artwork.svg",
            "out":"designed-original.png","width":1280,"height":720},[]),
        ("inspect-2d","body.inspect",{"source":"zx7-2d/sample.mp4"},[]),
        ("inspect-3d","body.inspect",{"source":"zx7-real-3d/scene-3d.mp4"},[]),
        ("edit","body.render_edit",{"edit":"original-edit.json",
            "out":"finished-actual-film.mp4"},["inspect-2d","inspect-3d"]),
        ("editable","body.otio",{"edit":"original-edit.json",
            "out":"finished-actual-film.otio"},["inspect-2d","inspect-3d"]),
        ("thumbnail","body.film_thumbnail",{"source_film":"finished-actual-film.mp4",
            "out":"thumbnail.png","time_seconds":min(1.0,total/2)},["edit"]),
        ("full-decode","body.full_decode",
            {"source":"finished-actual-film.mp4",
             "expected":{"width":320,"height":180,"require_audio":True}},["edit"]),
        ("custody","body.asset_vault",
            {"source_witness":{"$node_output":"edit"}},["edit"]),
    ]
    ir={"project":{"creative_intent":"Evidence of actual independent creative body tool interoperation, not an original AI cinema work"},
        "owner_facts":{},"assets":[],
        "shots":[{"id":"owner_original_cut_technical_proof",
            "purpose":"Verify real editable 2D and 3D audiovisual media end to end",
            "duration_seconds":total}],
        "tool_graph":[{"id":id,"tool_id":tool,"purpose":"Demonstrate physical tool "+tool,
             "inputs":inp,"depends_on":dep}
            for id,tool,inp,dep in specs]}
    (base/"film-body-ir.json").write_text(json.dumps(ir,indent=2)+"\n")
    first=run_body_project(ir,base)
    if first["status"]!="all_tool_results_verified":
        raise RuntimeError("Real body tools did not complete: "+json.dumps(first["errors"]))
    second=run_body_project(ir,base)
    if second["status"]!="all_tool_results_verified" or (
            len(second["reused"])!=len(specs)):
        raise RuntimeError("Actual original creative media did not survive crash/restart test")
    measured=audit_delivered_movie(base/"finished-actual-film.mp4",
        output=base/"delivery-evidence",
        expected={"width":320,"height":480,"audio_required":True,
                  "duration_seconds":total,"time_tolerance_seconds":.3},
        decode_sample_timestamps=[min(.7,total/3),min(total-.1,total*.8)])
    if not measured["render_contract_verified"]:
        raise RuntimeError("Actual filmmaker delivery differs from real original media")
    result={"body_tools_real_video_verified":True,
            "body_persistent_all_stage_resume_verified":True,
            "independent_creative_film_produced":False,
            "human_premium_art_quality_approved":False,
            "ran_steps":len(specs),"reused_steps":len(second["reused"]),
            "original_real_2d_and_3d_source_preserved":True,
            "otio_real_editable_project_created":(base/"finished-actual-film.otio").is_file(),
            "vector_artist_graphic_rasterized":(base/"designed-original.png").is_file(),
            "decoded_original_thumbnail":(base/"thumbnail.png").is_file(),
            "media_vault_sqlite":(base/"vault"/"assets.sqlite3").is_file(),
            "real_verified_edited_mp4":str(base/"finished-actual-film.mp4"),
            "original_multi_engine_footage_seconds":total}
    (base/"verified-body-result.json").write_text(json.dumps(result,indent=2)+"\n")
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archived",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(assemble_body_evidence(a.archived,a.out),indent=2))


if __name__=="__main__":main()
