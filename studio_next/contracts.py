"""Model-neutral orchestration contracts. No scene/genre/voice/render-style presets."""
from dataclasses import dataclass, field
import json
import re
from typing import Any

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.-]{1,100}$")
CAPABILITY_STATES = {"installed", "unavailable", "needs_setup"}
ACCESS_MODES = {"read", "write", "network", "paid"}
STATUS = {"ready_for_human_review", "blocked", "needs_input", "failed"}

def _string(value: Any, field_name: str):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a nonempty string")
    return value.strip()

def _json_like(value: Any):
    """Remove executable Python objects before they are sent to a model."""
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))

@dataclass(frozen=True)
class ToolSpec:
    tool_id: str
    capability: str
    description: str
    access: str
    status: str = "installed"
    license: str = "not-reviewed"
    resource: str = "unknown"
    operation_schema: dict = field(default_factory=dict)
    limitations: tuple[str, ...] = ()
    def __post_init__(self):
        if not _IDENTIFIER.fullmatch(self.tool_id):
            raise ValueError(f"Invalid tool identifier {self.tool_id!r}")
        _string(self.capability, "capability")
        _string(self.description, "description")
        if self.access not in ACCESS_MODES:
            raise ValueError("Tool access must be read, write, network, or paid")
        if self.status not in CAPABILITY_STATES:
            raise ValueError("Invalid tool status")
        _json_like(self.operation_schema)
    def public(self):
        return {"id": self.tool_id,"capability": self.capability,
                "description": self.description,"access": self.access,
                "status": self.status,"license": self.license,
                "resource": self.resource,"schema": _json_like(self.operation_schema),
                "limitations": list(self.limitations)}

@dataclass(frozen=True)
class OwnerBrief:
    request: str
    owner_facts: dict[str, str] = field(default_factory=dict)
    asset_rights: dict[str, str] = field(default_factory=dict)
    preferences: dict = field(default_factory=dict)
    hard_limits: dict = field(default_factory=dict)
    def __post_init__(self):
        _string(self.request, "request")
        for key, value in self.owner_facts.items():
            _string(key, "fact id")
            _string(value, "fact value")
        for key, value in self.asset_rights.items():
            _string(key, "asset id")
            _string(value, "asset rights")
        _json_like(self.preferences);_json_like(self.hard_limits)
    def public(self):
        return {"request": self.request,"facts":self.owner_facts,
                "asset_rights":self.asset_rights,"preferences":self.preferences,
                "hard_limits":self.hard_limits}

def audit_proposal(plan, brief: OwnerBrief, available_tool_ids: set[str]):
    """A deterministic feasibility gate, not a creative-quality evaluator.
    Never invent a user fact, screenshot, third-party asset or capability.
    """
    errors=[]
    if not isinstance(plan, dict):
        return ["Director did not return a structured plan"]
    if not isinstance(plan.get("creative_intent"), str) or not plan["creative_intent"].strip():
        errors.append("Missing original creative intent")
    scenes=plan.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        errors.append("Need at least one authored scene; count is director-selected")
        scenes=[]
    ids=set()
    for i,scene in enumerate(scenes,1):
        if not isinstance(scene,dict):
            errors.append(f"Scene {i}: must be a structured object");continue
        ident=scene.get("id")
        if not isinstance(ident,str) or not ident.strip() or ident in ids:
            errors.append(f"Scene {i}: missing or duplicate id")
        ids.add(ident)
        if not isinstance(scene.get("purpose"),str) or not scene["purpose"].strip():
            errors.append(f"Scene {i}: missing story purpose")
        # Creative timing is not fixed. Validate only if the director specified it.
        if "duration_seconds" in scene:
            d=scene["duration_seconds"]
            if isinstance(d,bool) or not isinstance(d,(int,float)) or not 0 < d < float("inf"):
                errors.append(f"Scene {i}: invalid duration")
        for ref in scene.get("fact_refs",[]):
            if ref not in brief.owner_facts:
                errors.append(f"Scene {i}: unknown caller fact {ref}")
        for ref in scene.get("asset_refs",[]):
            if ref not in brief.asset_rights:
                errors.append(f"Scene {i}: no evidence of rights for asset {ref}")
    requested=plan.get("tool_route",[])
    if not isinstance(requested,list):
        errors.append("tool_route must be a list")
        requested=[]
    for index,tool in enumerate(requested,1):
        if not isinstance(tool,dict):
            errors.append(f"Tool step {index}: not an object");continue
        tool_id=tool.get("tool_id")
        if tool_id not in available_tool_ids:
            errors.append(f"Tool step {index}: unavailable or unregistered tool {tool_id}")
        if not isinstance(tool.get("reason"),str) or not tool["reason"].strip():
            errors.append(f"Tool step {index}: director must justify tool choice")
        if not isinstance(tool.get("inputs",{}),dict):
            errors.append(f"Tool step {index}: inputs must be an object")
    voices=plan.get("voice_choices",[])
    if not isinstance(voices,list):
        errors.append("voice_choices must be list")
    # No hardcoded choices here; installed adapters declare voice identities.
    if not isinstance(plan.get("story"),str) or not plan["story"].strip():
        errors.append("Missing story, not just visuals")
    return list(dict.fromkeys(errors))

def normalize_verdict(value):
    if not isinstance(value,dict):raise ValueError("Invalid reviewer result")
    issues=value.get("issues")
    if not isinstance(value.get("approved"),bool) or not isinstance(issues,list):
        raise ValueError("Reviewer must supply approved:boolean and issues:list")
    for i in issues:
        if not isinstance(i,dict) or not all(
          isinstance(i.get(k),str) and i[k].strip()
          for k in ("location","reason","repair")):
            raise ValueError("Reviewer issues must cite a location, reason and repair")
    return value
