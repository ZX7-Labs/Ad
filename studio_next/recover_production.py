"""Model-owned production recovery of a SAVED original film, never a new pitch.

A failed technical scene specification is shown back to the SAME film model,
with the actual installed renderer contract as engineering context. The model
must either preserve the visual intent with an executable technical specification
or truthfully declare required missing footage/skills. No original scene,
duration, dialogue or story is silently rewritten; no extra aesthetic presets.
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import shutil
from pathlib import Path

from .blender_scene import LIGHTS, SHAPES, validate_blender_shot
from .creative_tool_registry import creative_tool_inventory
from .production_handoff import validate_visual_design
from .providers import LocalCreativeModel, LocalModelSettings
from .stage_checkpoint import DurableStageStore, content_signature, fingerprint


TECHNICAL_FEEDBACK = """You are the SAME independent artistic film director and
technical production designer. Your original film and all of its shots are
already authored and are IMMUTABLE. Your last *technical* renderer job was
rejected; this is not permission to simplify or rewrite your artistic vision.
You must now decide what to do with this specific shot.

You have the ACTUAL renderer's Python validation contract below. A syntactic
description of an unsupported operation is NOT a real production capability.
Do not assume Blender can create a credible human actor, tailored clothing,
market crowds or true handheld location footage from primitive shapes. Do not
assert source footage, reference photography, texture maps, realistic cloth
or real location recordings exist when no such files are provided.

If your intended subject and film impact can genuinely be realized with
installed tools, return a complete schema-correct render job satisfying the
director-chosen scene identity, duration, plot, voice and owner evidence.
If not, choose engine 'unresolved', scene_job {}, and explicitly state the
missing licensed media or production capability. Do not create a 'low quality
stand-in' to satisfy technical tests.

Use the same outer JSON technical envelope as the previous design:
shot_id, engine, creative_rationale, continuity, scene_job,
desired_capabilities, production_gap. Never insert new or remove original
artistic shots. No external APIs, paid models, unverified URLs or executable
model-authored code. Output JSON only."""


def audited_renderer_contract():
    """The contract is dynamically obtained from REAL validation source.

    It is an execution *interface*, not a cinematic style/shot template.
    """
    return {
        "blender_backend":"Blender Cycles CPU with actual validated geometry",
        "blender_validator_source":inspect.getsource(validate_blender_shot),
        "blender_supported_object_kinds":sorted(SHAPES),
        "blender_supported_light_kinds":sorted(LIGHTS),
        "other_registered_engines":{
            "motion2d":"Original explicit vector-based artwork, needs valid Film IR",
            "unresolved":"Keep requested artistic visuals without falsely rendering them"},
    }


def recover_saved_original(saved_director, original_brief, model, output):
    """Resume actual archived film: no brainstorming, no original mutations."""
    saved=Path(saved_director)
    output=Path(output)
    original=Path(saved/"director-translation.json")
    original_vision=Path(saved/"original-vision"/"director-original.txt")
    brief=json.loads(Path(original_brief).read_text(encoding="utf-8"))
    if not isinstance(brief,dict) or not isinstance(brief.get("facts"),dict):
        raise ValueError("Actual original owner facts required")
    treatment=json.loads(original.read_text(encoding="utf-8"))
    shots=treatment.get("scenes",[])
    if not isinstance(shots,list) or not shots:
        raise ValueError("Original screenplay not found")
    vision=original_vision.read_text(encoding="utf-8")
    if not vision.strip():
        raise ValueError("Original director imagination is missing")
    output.mkdir(parents=True,exist_ok=True)
    prior=output/"original-preserved"
    prior.mkdir(exist_ok=True)
    # Never regenerate the original work; preserve exact raw source bytes.
    shutil.copyfile(original,prior/"director-translation.json")
    shutil.copyfile(original_vision,prior/"director-original.txt")
    saved_delivery=saved/"designs"/"delivery.json"
    if saved_delivery.is_file():
        shutil.copyfile(saved_delivery,output/"delivery.json")
    tool_catalog=creative_tool_inventory()
    tool_contract=audited_renderer_contract()
    technical_state=DurableStageStore(output/"verified-technical-checkpoints")
    pinned_model_id=getattr(getattr(model,"settings",None),"model_id",None)
    source_status=saved/"original-vision"/"director-status.json"
    if source_status.is_file():
        stated=json.loads(source_status.read_text(encoding="utf-8")).get("model")
        if stated and stated!=pinned_model_id:
            raise ValueError("Refusing to resume an archived film with a different artistic model")
    contract_signature=fingerprint(tool_contract)
    source_bytes=original.read_bytes()
    res=[]
    for index,scene in enumerate(shots,1):
        sid=scene.get("id")
        if not isinstance(sid,str):
            raise ValueError("Original shot identity missing")
        source=saved/"designs"/f"design-{index:03d}.json"
        archived=json.loads(source.read_text(encoding="utf-8"))
        if archived.get("scene_id")!=sid:
            raise ValueError("Archive mixes up original authored shots")
        initial=archived.get("model_response")
        reason=archived.get("verification",{}).get("reason","")
        if not isinstance(initial,dict):
            raise ValueError("Missing original scene technology proposal")
        context={"original_complete_story":vision,
                 "original_film_metadata":{k:v for k,v in treatment.items() if k!="scenes"},
                 "immutable_original_shot":scene,
                 "adjacent_shots":[shots[k] for k in (index-2,index)
                                   if 0<=k<len(shots)],
                 "owner_facts":brief["facts"],
                 "rejected_model_design":initial,
                 "actual_validator_result":reason,
                 "real_tool_capabilities":tool_catalog,
                 "actual_renderer_contract":tool_contract}
        if archived.get("verification",{}).get("executable"):
            proposed=initial
            recovery="reuse previously verified original design"
        else:
            stage=f"scene_{index:03d}"
            signature=content_signature(
                film_bytes=source_bytes,brief=brief,model_id=pinned_model_id,
                scene=scene,previous_design=archived,
                validation_contract_hash=contract_signature)
            proposed=technical_state.find(stage,signature)
            if proposed is None:
                proposed=model.decide(context)
                # Atomically save raw output BEFORE validation, allowing restart
                # after a future technical error without re-running this expensive
                # *artistic* model decision.
                technical_state.save(stage,signature,proposed)
                recovery="same artist directed technical rework; stage saved"
            else:
                recovery="exact original model response resumed from signed checkpoint"
        result={"scene_id":sid,"source_archive":source.name,
                "original_visual":scene["visual"],
                "original_duration_seconds":scene["duration_seconds"],
                "original_model_design":initial,
                "original_validation_failure":reason,
                "recovery_method":recovery,
                "revised_model_design":proposed}
        try:
            audited=validate_visual_design(scene,proposed,brief["facts"])
            result["verification"]=audited
        except (ValueError,TypeError,KeyError,OverflowError) as exc:
            result["verification"]={"executable":False,
                "reason":type(exc).__name__+": "+str(exc)}
        raw=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)
        result["audit_sha256"]=hashlib.sha256(raw.encode("utf-8")).hexdigest()
        (output/f"reviewed-design-{index:03d}.json").write_text(
            json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        # Normal compositor interface consumes *only validated* original art.
        (output/f"design-{index:03d}.json").write_text(json.dumps({
            "scene_id":sid,
            "model_response":proposed,
            "verification":result["verification"]},ensure_ascii=False,indent=2)+"\n",
            encoding="utf-8")
        res.append({"scene_id":sid,
                    "executable":bool(result["verification"]["executable"]),
                    "real_gap":result["verification"].get("reason",""),
                    "attempted":recovery})
        print("ARCHIVED ORIGINAL SHOT TECHNICAL REVIEW",json.dumps(res[-1],
            ensure_ascii=False),flush=True)
    output_manifest={
        "film_title":treatment.get("title"),
        "original_sha256":hashlib.sha256(original.read_bytes()).hexdigest(),
        "original_vision_sha256":hashlib.sha256(original_vision.read_bytes()).hexdigest(),
        "same_model_id":getattr(getattr(model,"settings",None),"model_id",None),
        "original_scene_count":len(shots),
        "result_scene_count":len(res),
        "original_film_story_unchanged":True,
        "original_director_shots_unchanged":True,
        "designs":res,
        "all_designs_executable":all(v["executable"] for v in res),
        "movie_rendered":False,
        "human_artistic_approval":False,
        "status":"READY_FOR_SEPARATE_REAL_RENDER" if all(v["executable"] for v in res)
                 else "BLOCKED_BY_VERIFIED_PRODUCTION_REQUIREMENTS"}
    (output/"recovery-manifest.json").write_text(json.dumps(
        output_manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return output_manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--saved-director",type=Path,required=True)
    p.add_argument("--brief",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--model",required=True)
    p.add_argument("--api",default="http://127.0.0.1:8085")
    a=p.parse_args()
    model=LocalCreativeModel(LocalModelSettings(base_url=a.api,model_id=a.model,
        timeout_seconds=1800,sampling={"temperature":.25,"top_p":.9,"max_tokens":2800}),
        system_prompt=TECHNICAL_FEEDBACK)
    print(json.dumps(recover_saved_original(a.saved_director,a.brief,model,a.out),
        ensure_ascii=False,indent=2),flush=True)


if __name__=="__main__":
    main()
