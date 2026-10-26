"""Compact truthful reflex feedback from ACTUAL persisted film job state.

This is a sensory state sampler, not a visual-language model, media decoder,
new execution command or creative quality grader. It refuses to equate an
executor's 'completed' status with a delivered and aesthetically approved MP4.
"""
from __future__ import annotations

import hashlib
import json
import re

_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_STATES = {"queued","running","completed","blocked","failed","paused","cancelled"}


def _digest(value):
    return hashlib.sha256(json.dumps(value,allow_nan=False,
        ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()


def sense_body_job(coordinator,job_id,*,max_stages=16):
    if not isinstance(job_id,str) or not _ID.fullmatch(job_id):
        raise ValueError("Authenticated sensory reader needs exact original job ID")
    if type(max_stages) is not int or not 1<=max_stages<=40:
        raise ValueError("Bounded sensory stage selection required")
    snapshot=coordinator.inspect(job_id)
    state=snapshot["status"]
    if state not in _STATES:
        raise ValueError("Unknown actual physical job state")
    raw=snapshot.get("result")
    if raw is not None and not isinstance(raw,dict):
        raise ValueError("Untrusted physical execution feedback type")
    result=raw or {}
    progress=snapshot.get("actual_tool_progress") or {}
    source=progress.get("observed_tool_states",[])
    if not isinstance(source,list):
        raise ValueError("Physical stage receipt must be bounded array")
    rows=[]
    for item in source[:max_stages]:
        if (not isinstance(item,dict) or
            not all(key in item for key in ("node_id","state","attempts","updated_at"))):
            raise ValueError("Bad physical state receipt from database")
        rows.append({key:item[key] for key in (
            "node_id","state","attempts","updated_at")})
    errors=result.get("errors",[])
    if not isinstance(errors,list) or any(not isinstance(v,str) for v in errors):
        errors=["Persisted failed-stage report is unavailable or malformed"]
    if state=="failed" and not errors:
        error=result.get("message","The physical executor failed without a bounded summary")
        errors=[str(error)]
    errors=[e[:600] for e in errors[:8]]
    observed=bool(progress.get("tool_progress_is_actual_sqlite"))
    # A completed registered operation does not imply a visually valid movie.
    # Actual decoding/rights/creative review are separate trusted capabilities.
    return {
        "schema":1,
        "kind":"physical_job_state_observation",
        "job_id":job_id,
        "workspace_id":snapshot["workspace_id"],
        "job_state":state,
        "job_attempts":snapshot["attempts"],
        "observed_at_job_update":snapshot["updated_at"],
        "operator_requested_action":snapshot.get("requested_action"),
        "actual_durable_stage_database_found":observed,
        "stage_observation_scope":progress.get(
            "stage_scope","no_verified_project_lineage"),
        "stage_entries_are_shared_film_cache_not_job_attempt_receipts":True,
        "recent_native_stages":rows if observed else [],
        "additional_stages_omitted":max(0,len(source)-max_stages),
        "failure_reasons":errors,
        "persisted_result_sha256":_digest(result) if raw is not None else None,
        "executor_report_is_not_a_media_decoder":True,
        "movie_physically_decoded_by_this_observation":False,
        "cinematic_or_narrative_quality_certified":False,
        "next_evidence_route":"body.full_decode / body.review only with rights-checked actual source"
    }
