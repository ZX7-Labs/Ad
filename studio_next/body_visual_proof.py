"""Installed-package native pixels, float EXR and durable reuse acceptance.

All artistic values here are technical fixture data, never engine defaults.
No creative LLM inference or aesthetic/professional-quality approval is claimed.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
from .body_integration import run_body_project
from .body_visual_graph import VisualBudget,VisualGraph
from .body_visual_exr import read_float_rgba
from .media_vault import MediaVault,sha256_file


def native_visual_proof(output):
    import numpy as np
    root=Path(output).resolve()
    if root.exists() and any(root.iterdir()):raise FileExistsError("Use a new native proof workspace")
    root.mkdir(parents=True,exist_ok=True)
    document={"version":"zx7-visual-graph/1","canvas":{"width":160,"height":96,
        "frame_rate":{"numerator":24,"denominator":1},"frames":12,"working_space":"linear_srgb"},
        "nodes":[{"id":"original_pixels","op":"expression","inputs":{},"params":{
            "channels":{"r":"4*u","g":"-.2+v","b":"1+sin(u*9+time)","a":".2+.7*u"},"uniforms":{}}}],
        "output":"original_pixels","render":{"first_frame":0,"frame_count":12,"format":"rgba_mov",
            "rgb_range":"clip_to_sdr","audio":"separate_tracks"}}
    full=copy.deepcopy(document)
    excerpt=copy.deepcopy(document);excerpt["render"].update(first_frame=5,frame_count=3)
    floating=copy.deepcopy(document);floating["render"].update(first_frame=8,frame_count=1,format="exr32",rgb_range="preserve_float")
    preview=copy.deepcopy(document);preview["render"].update(first_frame=8,frame_count=1,format="png")
    graph=[]
    for name,doc,suffix in (("whole",full,"mov"),("excerpt",excerpt,"mov"),("floating",floating,"exr"),("preview",preview,"png")):
        (root/(name+".json")).write_text(json.dumps(doc,indent=2))
        graph.extend([{"id":name,"tool_id":"body.visual_graph","purpose":"Native technical project data",
            "inputs":{"plan":name+".json","out":name+"."+suffix},"depends_on":[]},
            {"id":name+"_custody","tool_id":"body.asset_vault","purpose":"Actual generated source custody",
             "inputs":{"source_witness":{"$node_output":name}},"depends_on":[name]}])
    ir={"project":{"creative_intent":"Verify native editable pixel controls and original clock"},
        "shots":[{"id":"source","purpose":"Technical float/alpha/motion proof"}],"tool_graph":graph}
    (root/"body-project.json").write_text(json.dumps(ir,indent=2))
    first=run_body_project(ir,root)
    if first["status"]!="all_tool_results_verified":raise RuntimeError(str(first["errors"]))
    second=run_body_project(ir,root)
    if second["status"]!="all_tool_results_verified" or len(second["reused"])!=len(graph):
        raise RuntimeError("Native pixel graph did not reuse every physically verified output")
    def decode(name):
        return subprocess.check_output(["ffmpeg","-hide_banner","-loglevel","error","-xerror","-nostdin",
            "-i",str(root/name),"-map","0:v:0","-vsync","0","-f","rawvideo","-pix_fmt","rgba","-"],timeout=60)
    whole,part=decode("whole.mov"),decode("excerpt.mov");size=160*96*4
    if len(whole)!=size*12 or part!=whole[5*size:8*size]:raise RuntimeError("Original-clock excerpt RGBA differs")
    decoded=read_float_rgba(root/"floating.exr",budget=VisualBudget(),alpha_mode="associated")
    expected=VisualGraph(floating).frame(8)
    if decoded.tobytes()!=expected.tobytes() or not np.any(decoded[...,:3]>1) or not np.any(decoded[...,:3]<0):
        raise RuntimeError("Floating master clipped or changed actual authored values")
    vault=MediaVault(root/"vault");record=vault.inspect(sha256_file(root/"floating.exr"))
    if not record["rights_attestations"] or record["mime"]!="image/x-exr":raise RuntimeError("No genuine float source custody")
    report={"all_checks_passed":True,"original_clock_excerpt_rgba_identical":True,
        "float32_rgba_exact":True,"extended_and_negative_rgb_retained":True,
        "generated_float_source_custody_verified":True,"reused_verified_stages":len(second["reused"]),
        "full_motion_rgba_sha256":hashlib.sha256(whole).hexdigest(),"float_rgba_sha256":hashlib.sha256(decoded.tobytes()).hexdigest(),
        "model_inference_performed":False,"artistic_quality_approved":False,
        "files":[{"path":p.name,"bytes":p.stat().st_size,"sha256":sha256_file(p)}
                 for p in sorted(root.iterdir()) if p.is_file() and p.suffix in (".mov",".exr",".png",".json")]}
    (root/"visual-proof.json").write_text(json.dumps(report,indent=2)+"\n")
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--workspace",type=Path,required=True)
    args=parser.parse_args();print(json.dumps(native_visual_proof(args.workspace),indent=2))


if __name__=="__main__":main()
