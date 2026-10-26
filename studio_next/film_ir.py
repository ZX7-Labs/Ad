"""Universal, expressive film/project intermediate representation with dependency QA.

Creative decisions are NOT made here. The LLM/film director owns story and artistic
choices; this contract checks that proposed work is executable and rights-aware.
No preset scene counts, aspect ratios, time limits, genres, fonts, or render style.
"""
from collections import defaultdict
from dataclasses import dataclass,field
import math
from typing import Any
from .contracts import _json_like

def _nonempty(v):
    return isinstance(v,str) and bool(v.strip())

@dataclass(frozen=True)
class IRValidation:
    errors:list[str]
    warnings:list[str]
    render_ready:bool
    order:list[str] = field(default_factory=list)
    def public(self):
        return {"errors":self.errors,"warnings":self.warnings,
                "render_ready":self.render_ready,"tool_execution_order":self.order}

def _order(nodes):
    """Prove dependency acyclicity before any tool invocation."""
    node_by_id={n["id"]:n for n in nodes if isinstance(n,dict) and _nonempty(n.get("id"))}
    parents={i:set(n.get("depends_on",[])) for i,n in node_by_id.items()}
    outgoing=defaultdict(set)
    degree={i:len(deps) for i,deps in parents.items()}
    for identifier,deps in parents.items():
        for dep in deps:outgoing[dep].add(identifier)
    available=sorted([i for i,d in degree.items() if d==0])
    result=[]
    while available:
        curr=available.pop(0)
        result.append(curr)
        for nxt in sorted(outgoing[curr]):
            degree[nxt]-=1
            if degree[nxt]==0:
                available.append(nxt);available.sort()
    return result if len(result)==len(nodes) else None

def validate_film_ir(ir:dict, *, installed_tool_ids:set[str], fact_ids:set[str]):
    errors=[];warnings=[]
    if not isinstance(ir,dict):
        return IRValidation(["Film plan must be object"],[],False)
    meta=ir.get("project") or {}
    if not isinstance(meta,dict) or not _nonempty(meta.get("creative_intent")):
        errors.append("No creative intent");meta={}
    shots=ir.get("shots")
    if not isinstance(shots,list) or not shots:
        errors.append("Missing film shots");shots=[]
    asset_entries=ir.get("assets",[])
    if not isinstance(asset_entries,list):
        errors.append("Asset list must be array");asset_entries=[]
    asset_ids=set()
    for i,asset in enumerate(asset_entries,1):
        if not isinstance(asset,dict):
            errors.append(f"Asset {i} malformed");continue
        uid=asset.get("id")
        if not _nonempty(uid) or uid in asset_ids:
            errors.append(f"Asset {i} missing or duplicate id");continue
        asset_ids.add(uid)
        if asset.get("status")!="verified":
            warnings.append(f"Asset {uid} not verified/available")
        if asset.get("rights") not in ("owner_supplied","generated_original",
                                       "appropriately_licensed"):
            errors.append(f"Asset {uid} rights not established")
        if asset.get("status")=="verified" and not _nonempty(asset.get("location")):
            errors.append(f"Asset {uid} verified without real location")
    shot_ids=set()
    for idx,shot in enumerate(shots,1):
        if not isinstance(shot,dict):
            errors.append(f"Shot {idx} malformed");continue
        uid=shot.get("id")
        if not _nonempty(uid) or uid in shot_ids:
            errors.append(f"Shot {idx} missing or duplicate id")
        shot_ids.add(uid)
        if not _nonempty(shot.get("purpose")):
            errors.append(f"Shot {idx} missing creative purpose")
        if "duration_seconds" in shot:
            duration=shot["duration_seconds"]
            if isinstance(duration,bool) or not isinstance(duration,(float,int)) or (
                not math.isfinite(duration) or duration<=0):
                errors.append(f"Shot {idx} invalid duration")
        for field,allowed,label in (("asset_refs",asset_ids,"unknown media"),
                                    ("fact_refs",fact_ids,"unprovided fact")):
            refs=shot.get(field,[])
            if not isinstance(refs,list):
                errors.append(f"Shot {idx} {field} must be an array");continue
            for ref in refs:
                if not isinstance(ref,str) or ref not in allowed:
                    errors.append(f"Shot {idx} references {label} {ref}")
        for field_name in ("camera","audio","layers","motion","typography","edit"):
            if field_name in shot:
                try:_json_like(shot[field_name])
                except (TypeError,ValueError):
                    errors.append(f"Shot {idx} invalid {field_name} data")
    nodes=ir.get("tool_graph",[])
    if not isinstance(nodes,list):
        errors.append("Tool graph must be list");nodes=[]
    known=set();ids=[]
    for idx,node in enumerate(nodes,1):
        if not isinstance(node,dict):
            errors.append(f"Tool node {idx} malformed");continue
        uid=node.get("id")
        if not _nonempty(uid) or uid in known:
            errors.append(f"Tool node {idx} missing or duplicate id");continue
        known.add(uid);ids.append(uid)
        tid=node.get("tool_id")
        if tid not in installed_tool_ids:
            errors.append(f"Tool node {uid} has uninstalled/unavailable tool {tid}")
        if not isinstance(node.get("inputs",{}),dict):
            errors.append(f"Tool node {uid} inputs invalid")
        if not _nonempty(node.get("purpose")):
            errors.append(f"Tool node {uid} missing production purpose")
        if not isinstance(node.get("depends_on",[]),list):
            errors.append(f"Tool node {uid} dependencies invalid")
        if "shot_refs" in node:
            refs=node["shot_refs"]
            if not isinstance(refs,list) or not refs or any(
                    not isinstance(r,str) or r not in shot_ids for r in refs):
                errors.append(f"Tool node {uid} has invalid authored shot scope")
        if "asset_refs" in node:
            refs=node["asset_refs"]
            if not isinstance(refs,list) or any(
                    not isinstance(r,str) or r not in asset_ids for r in refs
                    ) or len(set(map(str,refs)))!=len(refs):
                errors.append(f"Tool node {uid} has invalid original media asset scope")
    for node in nodes:
        if not isinstance(node,dict) or not _nonempty(node.get("id")):continue
        deps=node.get("depends_on",[])
        if not isinstance(deps,list):continue
        for dep in deps:
            if not isinstance(dep,str):
                errors.append(f"Tool node {node['id']} has malformed dependency");continue
            if dep not in known:errors.append(f"Tool node {node['id']} references missing dependency {dep}")
            if dep==node["id"]:errors.append(f"Tool node {node['id']} depends on itself")
    safe_nodes=(len(nodes)==len(known) and all(
        isinstance(n,dict) and isinstance(n.get("depends_on",[]),list)
        and all(isinstance(dep,str) for dep in n.get("depends_on",[])) for n in nodes))
    order=_order(nodes) if safe_nodes else None
    if order is None:
        errors.append("Tool dependency cycle or invalid tool graph")
        order=[]
    if not nodes:
        warnings.append("No execution graph; plan is creatively drafted, not renderable")
    # A project with planned assets, no graph, or missing facts cannot be render-ready.
    unresolved=any(not isinstance(a,dict) or a.get("status")!="verified" for a in asset_entries)
    return IRValidation(list(dict.fromkeys(errors)),list(dict.fromkeys(warnings)),
            not errors and bool(nodes) and not unresolved,order)
