"""Real public BODY native Blender project/revision/Geometry Nodes acceptance.

Fixture artwork is a control probe, never a creative preset or quality verdict.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .body_integration import run_body_project
from .body_motion_project import VERSION,digest,verify_motion_bundle,run_motion_project


def fixture_job():
    actions=[]
    def call(path,method,args=(),kwargs=None,alias=None):
        actions.append({"op":"call","path":path,"method":method,"args":list(args),"kwargs":kwargs or {},"as":alias})
    def set_(path,value):actions.append({"op":"set","path":path,"value":value})
    def ref(name):return {"$ref":["refs",name]}
    def object_(name,data):
        call(["data","objects"],"new",[name,ref(data)],alias=name)
        call(["scene","collection","objects"],"link",[ref(name)])
    set_(["scene","render","engine"],"CYCLES")
    set_(["scene","cycles","device"],"CPU");set_(["scene","cycles","samples"],4)
    set_(["scene","cycles","use_denoising"],False)
    for key,val in (("resolution_x",96),("resolution_y",64),("resolution_percentage",100),("fps",12)):
        set_(["scene","render",key],val)
    call(["data","cameras"],"new",["CameraData"],alias="camera_data")
    object_("Camera","camera_data");set_(["refs","Camera","location"],[0,0,6])
    set_(["refs","camera_data","type"],"ORTHO");set_(["refs","camera_data","ortho_scale"],6)
    set_(["scene","camera"],ref("Camera"))
    call(["data","materials"],"new",["Orange"],alias="material")
    set_(["refs","material","use_nodes"],True)
    shader=["refs","material","node_tree","nodes","Principled BSDF","inputs"]
    set_(shader+["Emission Color","default_value"],[.8,.06,.01,1])
    set_(shader+["Emission Strength","default_value"],2)
    call(["data","curves"],"new",["Typography"],{"type":"FONT"},"type")
    for key,val in (("body","BODY"),("align_x","CENTER"),("size",.8),("extrude",.025)):
        set_(["refs","type",key],val)
    object_("Title","type")
    # Native material slots are a collection; append is an RNA data operation.
    call(["refs","type","materials"],"append",[ref("material")])
    set_(["refs","Title","location"],[-.6,0,0])
    call(["refs","Title"],"keyframe_insert",kwargs={"data_path":"location","frame":1})
    set_(["refs","Title","location"],[.6,0,0])
    call(["refs","Title"],"keyframe_insert",kwargs={"data_path":"location","frame":5})
    call(["data","meshes"],"new",["AuthoredMesh"],alias="mesh")
    call(["refs","mesh"],"from_pydata",[[[-1,-.8,0],[1,-.8,0],[1,-.55,0],[-1,-.55,0]],[],[[0,1,2,3]]])
    object_("Bar","mesh");call(["refs","mesh","materials"],"append",[ref("material")])
    call(["data","node_groups"],"new",["MotionGeometry","GeometryNodeTree"],alias="geometry")
    for side in ("INPUT","OUTPUT"):
        call(["refs","geometry","interface"],"new_socket",kwargs={"name":"Geometry","in_out":side,"socket_type":"NodeSocketGeometry"})
    for kind,name in (("NodeGroupInput","input"),("GeometryNodeTransform","transform"),("NodeGroupOutput","output")):
        call(["refs","geometry","nodes"],"new",[kind],alias=name)
    set_(["refs","transform","inputs","Translation","default_value"],[.2,0,0])
    call(["refs","geometry","links"],"new",[
        {"$ref":["refs","input","outputs","Geometry"]},{"$ref":["refs","transform","inputs","Geometry"]}])
    call(["refs","geometry","links"],"new",[
        {"$ref":["refs","transform","outputs","Geometry"]},{"$ref":["refs","output","inputs","Geometry"]}])
    call(["refs","Bar","modifiers"],"new",["ProceduralMotion","NODES"],alias="modifier")
    set_(["refs","modifier","node_group"],ref("geometry"))
    actions.extend([{"op":"describe","path":["refs","type"]},
                    {"op":"read","path":["refs","transform","inputs","Translation","default_value"]},
                    {"op":"list","path":["data","objects"],"offset":0,"limit":20}])
    return {"version":VERSION,"project":None,"actions":actions,
        "renders":[{"scene":"Scene","frame":f,"format":"png"} for f in (1,3,5)]}


def native_motion_proof(workspace):
    root=Path(workspace).resolve()
    if root.exists() and any(root.iterdir()):raise FileExistsError("Use a new native motion proof workspace")
    root.mkdir(parents=True,exist_ok=True)
    original=fixture_job()
    revision={"version":VERSION,"project":"original.zxmotion","actions":[
        {"op":"set","path":["data","curves","Typography","body"],"value":"EDIT"},
        {"op":"set","path":["data","node_groups","MotionGeometry","nodes","Transform Geometry","inputs","Translation","default_value"],"value":[.8,0,0]},
        {"op":"read","path":["data","curves","Typography","body"]},
        {"op":"read","path":["data","node_groups","MotionGeometry","nodes","Transform Geometry","inputs","Translation","default_value"]}],
        "renders":[{"scene":"Scene","frame":3,"format":"png"}]}
    for name,job in (("original",original),("revision",revision)):(root/(name+".json")).write_text(json.dumps(job))
    graph=[{"id":"native","tool_id":"body.motion_project","purpose":"Native Blender project control proof",
            "inputs":{"plan":"original.json","out":"original.zxmotion"},"depends_on":[]},
           {"id":"revision","tool_id":"body.motion_project","purpose":"Reopen and edit the same native project",
            "inputs":{"plan":"revision.json","out":"revision.zxmotion"},"depends_on":["native"]},
           {"id":"delivery","tool_id":"body.motion_export","purpose":"Actual media from authored frames",
            "inputs":{"bundle":"original.zxmotion","out":"motion.mp4","fps":12},"depends_on":["native"]},
           {"id":"preview","tool_id":"body.motion_export","purpose":"Actual revised frame",
            "inputs":{"bundle":"revision.zxmotion","out":"revision.png","fps":12},"depends_on":["revision"]}]
    ir={"project":{"creative_intent":"Native motion project engineering acceptance"},"shots":[{"id":"motion","purpose":"Technical control probe"}],"tool_graph":graph}
    first=run_body_project(ir,root)
    if first["status"]!="all_tool_results_verified":raise RuntimeError(str(first["errors"]))
    before=digest(root/"original.zxmotion")
    again=run_body_project(ir,root)
    if again["status"]!="all_tool_results_verified" or len(again["reused"])!=4:raise RuntimeError("Native durable reuse failed")
    a=verify_motion_bundle(root/"original.zxmotion");b=verify_motion_bundle(root/"revision.zxmotion")
    assert a["members"]["render_000001.png"]!=b["members"]["render_000000.png"]
    assert a["members"]["render_000000.png"]!=a["members"]["render_000002.png"]
    assert b["parent_bundle_sha256"]==before==digest(root/"original.zxmotion")
    assert b["native"]["actions"][2]["result"]=="EDIT"
    assert abs(b["native"]["actions"][3]["result"][0]-.8)<1e-6
    broken={"version":VERSION,"project":"original.zxmotion","actions":[
        {"op":"set","path":["data","curves","Typography","property_that_does_not_exist"],"value":1}],"renders":[]}
    (root/"broken.json").write_text(json.dumps(broken))
    try:run_motion_project(root/"broken.json",root,root/"broken.zxmotion")
    except RuntimeError:pass
    else:raise AssertionError("Invalid native edit unexpectedly succeeded")
    assert not (root/"broken.zxmotion").exists() and digest(root/"original.zxmotion")==before
    report={"all_checks_passed":True,"engine_version":a["engine_version"],"native_geometry_nodes_executed":True,
        "native_text_animation_and_material_executed":True,"saved_native_project_reopened_and_revised":True,
        "original_project_preserved":True,"actual_revision_pixels_changed":True,"verified_stages_reused":4,
        "native_runtime_property_discovery_executed":True,"model_inference_performed":False,"artistic_quality_approved":False}
    report["failed_native_edit_published_nothing_and_preserved_original"]=True
    (root/"motion-proof.json").write_text(json.dumps(report,indent=2)+"\n")
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--workspace",type=Path,required=True)
    print(json.dumps(native_motion_proof(parser.parse_args().workspace),indent=2))


if __name__=="__main__":main()
