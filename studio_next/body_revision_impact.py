"""Non-destructive edit-impact planning; NEVER execute or certify a movie.

Given TWO original artist-authored Film IR revisions, inspect the dependency
graph and identify the exact stages that *may* be reused vs need rendering.
Uses direct stage identity, original shot/asset scope and DAG dependency
closure. The result is an advisory plan, not a replacement for immutable
source hash verification and actual stage-cache checks during execution.
"""
from __future__ import annotations

from .body_dependency_scope import select_verified_node_assets
from .film_ir import validate_film_ir
from .stage_checkpoint import fingerprint


def _validated_original(ir):
    if not isinstance(ir,dict):
        raise ValueError("Revision impact needs original creative Film IR")
    graph=ir.get("tool_graph")
    if not isinstance(graph,list):
        raise ValueError("Invalid film execution DAG")
    # No installed tool may be executed by this diagnostic operation. Probe
    # declared IDs only to test graph semantics and scene/asset references.
    tools={n.get("tool_id") for n in graph if isinstance(n,dict)
           and isinstance(n.get("tool_id"),str)}
    rights=set(ir.get("owner_facts",{}))
    check=validate_film_ir(ir,installed_tool_ids=tools,fact_ids=rights)
    if not check.render_ready:
        raise ValueError("Cannot plan unsafe/unrenderable authored film: "+
                         "; ".join(check.errors+check.warnings))
    return check


def _signatures(ir):
    assets=ir.get("assets",[])
    shots=ir["shots"]
    nodes=ir["tool_graph"]
    by_id={}
    for node in nodes:
        scope=set(node.get("shot_refs",[]))
        scenes=[shot for shot in shots if not scope or shot["id"] in scope]
        material=select_verified_node_assets(assets,node,scenes)
        by_id[node["id"]]=fingerprint({
            "operation":node,
            "authoritative_scene_intent":scenes,
            "source_rights_and_media_metadata":material,
            # All non-scene project changes may affect brand, story facts,
            # narration or legal permission across the whole film.
            "global_original_intent":ir["project"],
            "global_owner_facts":ir.get("owner_facts",{})
        })
    return by_id


def plan_film_revision_impact(before,after):
    """Read-only dependency forecast; no cache or original media mutation."""
    previous=_validated_original(before)
    upcoming=_validated_original(after)
    a={n["id"]:n for n in before["tool_graph"]}
    b={n["id"]:n for n in after["tool_graph"]}
    prev=_signatures(before)
    next_=_signatures(after)
    gone=set(a)-set(b)
    direct={name for name in b if prev.get(name)!=next_.get(name)}
    # The old DAG and new DAG must both be considered; if a previously
    # depended-on stage disappears, the dependent node can never reuse a
    # partial result with the old structural lineage.
    parents={}
    for node_id,node in b.items():
        past=a.get(node_id,{})
        parents[node_id]=set(node.get("depends_on",[]))|set(past.get("depends_on",[]))
    impacted=set(direct)
    while True:
        changed={id_ for id_ in b if parents[id_] & (impacted|gone)}
        if changed.issubset(impacted):
            break
        impacted|=changed
    retained=[identifier for identifier in upcoming.order if identifier not in impacted]
    render=[identifier for identifier in upcoming.order if identifier in impacted]
    # This is only a structural forecast. The real BODY must still check
    # source hashes, plugin revision, rights, output evidence, and permissions.
    return {
        "schema":1,
        "prior_operations":len(previous.order),
        "revised_operations":len(upcoming.order),
        "original_unchanged_candidates":retained,
        "new_or_changed_operations":render,
        "deleted_original_operations":sorted(gone),
        "directly_changed_operations":sorted(direct),
        "dependency_propagated_changes":sorted(impacted-direct),
        "reusable_cached_bytes_proven":False,
        "source_media_bytes_physically_rechecked":False,
        "rights_attestations_rechecked":False,
        "tool_revisions_rechecked":False,
        "immutable_original_film_modified":False,
        "requires_runtime_custody_validation":True,
        "creative_style_prescribed":False
    }
