"""Local-first swappable creative-model interfaces.

A provider supplies thinking power. It never obtains tool execution directly:
StudioDirector grants tool permissions and validates selected tool route.
No pretrained model is bundled and no 'best screenwriter' claim is made.
"""
from dataclasses import dataclass, field
import base64
import json
from urllib.parse import urlsplit
from urllib.request import Request
from .local_model_http import urlopen
from typing import Any

_CREATIVE_SYSTEM = """You are a studio CREATIVE DIRECTOR, story strategist and editor, not a coding assistant.
Think independently about audience, story, emotional arc, script, artwork, camera, composition,
music, voice, pace and production options. No fixed genre, runtime, scene count, font or render style.
Ground factual claims only in the caller-owned facts and licensed assets.
You have an advertised list of actually installed tools with honest limitations.
Choose when to ask ONE essential question, when to request a useful registered tool,
or when to propose a complete original treatment and justified tool route.
Reply as a JSON object with kind=question, kind=tool or kind=proposal.
A tool request has tool_id and inputs. Proposal has a plan with:
creative_intent, story, scenes, voice_choices, tool_route.
Scenes contain id, purpose, chosen duration_seconds when known, fact_refs and asset_refs.
Do not put fabricated media, invented claims or hidden tool commands in the result.
A producer and independent reviewer will test your decisions. Be specific and self-critical."""

_REVIEW_SYSTEM = """You are the skeptical independent editorial REVIEWER, not the creative author.
Critique the actual proposed work on original hook, emotional pacing, natural dialogue,
clarity, evidence accuracy, meaningful imagery, production tool feasibility,
continuity and sound design. Do not automatically approve. Identify concrete problems,
with exactly where they occur and how to repair them. Do not approve inaccessible
assets or imaginary tools. If no substantive blockers remain, approve.
Return JSON only: {"approved": true/false,
"issues":[{"location":"specific scene/field","reason":"specific flaw","repair":"actionable change"}]}.
You cannot execute tools or overrule caller evidence/security validation."""

@dataclass(frozen=True)
class LocalModelSettings:
    base_url: str = "http://127.0.0.1:8080"
    model_id: str = "local"
    timeout_seconds: int = 480
    max_response_bytes: int = 2000000
    sampling: dict[str, Any] = field(default_factory=dict)
    def __post_init__(self):
        parts=urlsplit(self.base_url)
        if parts.scheme!="http" or parts.hostname not in ("127.0.0.1","localhost","::1") or (
            parts.username or parts.password or parts.query or parts.fragment
            or parts.path not in ("","/")):
            raise ValueError("Only local unauthenticated HTTP model servers are permitted")
        if not isinstance(self.model_id,str) or not self.model_id.strip():
            raise ValueError("Missing model id")
        if not 1 <= self.timeout_seconds <= 3600:
            raise ValueError("Specify a finite timeout for free compute")
        if not 1024 <= self.max_response_bytes <= 50000000:
            raise ValueError("Unsafe response size limit")
        if not isinstance(self.sampling,dict):
            raise ValueError("Sampling options must be a dict")
        if any(k in self.sampling for k in ("messages","model","stream","tools","tool_choice")):
            raise ValueError("Sampling config cannot override messages or model")

class LocalCreativeModel:
    """OpenAI-compatible local model adapter. No expensive cloud calls."""
    def __init__(self,settings:LocalModelSettings,system_prompt:str=_CREATIVE_SYSTEM):
        self.settings=settings
        self.system_prompt=system_prompt

    def _invoke(self,role,context,*,images=()):
        user_content=json.dumps(context,ensure_ascii=False,allow_nan=False)
        if images:
            content=[{"type":"text","text":user_content}]
            for mime,raw in images:
                if mime not in ("image/png","image/jpeg") or not isinstance(raw,bytes) or not 100<=len(raw)<=3000000:
                    raise ValueError("Bounded actual decoded model image required")
                content.append({"type":"image_url","image_url":{
                    "url":"data:"+mime+";base64,"+base64.b64encode(raw).decode("ascii")}})
            user_content=content
        payload={"model":self.settings.model_id,"stream":False,
                 "messages":[{"role":"system","content":role},
                             {"role":"user","content":user_content}],
                 "response_format":{"type":"json_object"}}
        payload.update(self.settings.sampling)
        data=json.dumps(payload,ensure_ascii=False).encode("utf-8")
        req=Request(self.settings.base_url.rstrip("/")+"/v1/chat/completions",
                    data=data,headers={"Content-Type":"application/json"},method="POST")
        with urlopen(req,timeout=self.settings.timeout_seconds) as resp:
            raw=resp.read(self.settings.max_response_bytes+1)
        if len(raw)>self.settings.max_response_bytes:
            raise ValueError("Local model response exceeds safe size limit")
        decoded=json.loads(raw.decode("utf-8"))
        choice=decoded["choices"][0]
        if choice.get("finish_reason")=="length":
            raise ValueError("Local model's structured answer was truncated")
        body=choice["message"].get("content")
        if not isinstance(body,str) or not body.strip():
            raise ValueError("Local model returned no JSON")
        def reject_constant(value):
            raise ValueError("Local model returned non-finite JSON: "+value)
        parsed=json.loads(body.strip(),parse_constant=reject_constant)
        if not isinstance(parsed,dict):
            raise ValueError("Local model returned a non-object JSON value")
        return parsed

    def decide(self,context):
        return self._invoke(self.system_prompt,context)

    def decide_with_images(self,context,images):
        return self._invoke(self.system_prompt,context,images=images)

    def review(self,context):
        # Caller can create a separate instance with a different local model id,
        # but can also reuse one model while acknowledging role-only separation.
        return self._invoke(_REVIEW_SYSTEM,context)
