"""Independently render AND assemble genuine 3D and 2D creative tools.

Technical fixture only: does not claim a general film-brain created these
visuals. Proves one resumable body graph can render both distinct installed
engines, mix sound, make an editable cut and verify the resulting actual MP4.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from .body_integration import run_body_project
from .delivery_audit import audit_delivered_movie


def native_original_body_proof(output):
    root=Path(output)
    if root.exists() and any(root.iterdir()):
        raise FileExistsError("Never overwrite a previous production proof")
    root.mkdir(parents=True,exist_ok=True)
    fixture=Path(__file__).resolve().parent/"fixtures"
    shutil.copyfile(fixture/"three_dimensional_shot.json",root/"original-3d-scene.json")
    shutil.copyfile(fixture/"vector_two_scene_film_ir.json",root/"original-motion-ir.json")
    shutil.copyfile(fixture/"mixed_engine_timeline.json",root/"edit.json")
    ir={"project":{"creative_intent":
           "Test original camera, 2D/3D engines, sound and actually encoded editable timeline"},
        "assets":[],"shots":[
          {"id":"verified_original_body","purpose":"Technical multi-engine body proof",
           "duration_seconds":4.75}],
        "tool_graph":[
          {"id":"blender","tool_id":"body.blender3d","purpose":"Real original Cycles CPU 3D shot",
           "inputs":{"scene_json":"original-3d-scene.json",
                     "out":"zx7-real-3d/scene-3d.mp4"},"depends_on":[]},
          {"id":"animation","tool_id":"body.motion2d",
           "purpose":"Actual directed vector animation with scene audio",
           "inputs":{"original_film_ir":"original-motion-ir.json",
                     "out":"zx7-2d/sample.mp4","width":320,"fps":12},"depends_on":[]},
          {"id":"finish","tool_id":"body.render_edit",
           "purpose":"Measured 2D plus 3D original audiovisual edit",
           "inputs":{"edit":"edit.json","out":"actual-full-mixed-film.mp4"},
           "depends_on":["animation","blender"]},
          {"id":"editable","tool_id":"body.otio",
           "purpose":"Open professional source-linked timeline project",
           "inputs":{"edit":"edit.json","out":"actual-full-mixed-film.otio"},
           "depends_on":["animation","blender"]},
          {"id":"thumbnail","tool_id":"body.film_thumbnail",
           "purpose":"Film-director-selected frame with original source checksum",
           "inputs":{"source_film":"actual-full-mixed-film.mp4",
                     "out":"actual-director-frame.png","time_seconds":1.2},
           "depends_on":["finish"]},
          {"id":"complete-film-decode","tool_id":"body.full_decode",
           "purpose":"Decode the ENTIRE real original edit and soundtrack, not two sampled frames",
           "inputs":{"source":"actual-full-mixed-film.mp4",
                     "expected":{"require_audio":True}},
           "depends_on":["finish"]},
          # Legacy body.render_edit is retained only as a technical
          # multi-engine compositor test. Its unverified license string
          # is NOT qualified to mint generated-original MediaVault rights.
          # The separate body.render_edit_owned uses real CAS attestations.
          ]}
    (root/"original-tool-graph.json").write_text(json.dumps(ir,indent=2)+"\n")
    first=run_body_project(ir,root)
    if first["status"]!="all_tool_results_verified":
        raise RuntimeError("Genuinely rendered multi-engine tool graph failed: "+
                           json.dumps(first["errors"]))
    second=run_body_project(ir,root)
    if second["status"]!="all_tool_results_verified" or len(second["reused"])!=len(ir["tool_graph"]):
        raise RuntimeError("Real 3D and 2D media did not resume unchanged")
    original=json.loads((root/"edit.json").read_text())
    meta=audit_delivered_movie(root/"actual-full-mixed-film.mp4",output=root/"measured",
        expected={"width":original["format"]["width"],
                  "height":original["format"]["height"],
                  "audio_required":True},
        decode_sample_timestamps=[.7,3.5])
    if not meta["render_contract_verified"]:
        raise RuntimeError("Actual original film delivery violates director's output format")
    report={"real_3d_rendered":True,"real_2d_rendered":True,
        "editable_otio_produced":True,"real_audio_and_video_verified":True,
        "real_original_source_frames_preserved":True,
        "exact_all_nodes_resumed":True,
        "human_premium_art_quality_proven":False,
        "independent_film_brain_tested":False,
        "source_engines":["Blender Cycles CPU","2D/2.5D compositor","FFmpeg"],
        "real_mp4":str(root/"actual-full-mixed-film.mp4"),
        "reused_scene_nodes":second["reused"]}
    (root/"verified-native-body-result.json").write_text(
        json.dumps(report,indent=2)+"\n")
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    print(json.dumps(native_original_body_proof(args.out),indent=2))


if __name__=="__main__":main()
