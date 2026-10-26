"""Autonomous planning loop with explicit resources, provenance and independent review.

The creative brain chooses number/length/style of scenes and chooses tools.
This module never assumes that structured text is already a rendered film.
"""
import json
from dataclasses import dataclass, field
from .contracts import OwnerBrief,audit_proposal,normalize_verdict
from .registry import ToolCatalog

@dataclass
class StudioOutcome:
    state: str
    plan: dict | None = None
    review: dict | None = None
    question: str | None = None
    blockers: list[str] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)
    note: str = "Planning only: no rendered video or human approval is implied."
    def public(self):
        return {"state":self.state,"plan":self.plan,"review":self.review,
                "question":self.question,"blockers":self.blockers,
                "trace":self.trace,"note":self.note}

class StudioDirector:
    def __init__(self,brain,reviewer,catalog:ToolCatalog,
                 *,max_turns=12,allowed_access=frozenset({"read"})):
        if not 1<=max_turns<=200:raise ValueError("Finite resource budget required")
        self.brain=brain
        self.reviewer=reviewer
        self.catalog=catalog
        self.max_turns=max_turns
        self.allowed_access=frozenset(allowed_access)
    def create(self,brief:OwnerBrief):
        if not isinstance(brief,OwnerBrief):raise TypeError("OwnerBrief required")
        trace=[]
        discovered=self.catalog.discover()
        errors=[]
        for step in range(self.max_turns):
            context={"brief":brief.public(),"tools":discovered,
                "tool_results":trace,"last_validation_errors":errors,
                "instruction":"Decide your own strategy, narrative, scene count, voice, art, music, timing, and tool route. "
                "Return a JSON action with kind=question, tool, or proposal. "
                "For tool: {kind,tool_id,inputs}; proposal: {kind,plan}; "
                "question: {kind,question}. Do not invent owner facts, media rights, or tool availability. "
                "Specify tool_route from discovered IDs with reasons. "
                "Aesthetic examples are not fixed presets."}
            decision=self.brain.decide(context)
            if not isinstance(decision,dict):
                return StudioOutcome("failed",blockers=["Brain returned invalid decision"],trace=trace)
            kind=decision.get("kind")
            if kind=="question":
                question=decision.get("question")
                if not isinstance(question,str) or not question.strip():
                    return StudioOutcome("failed",blockers=["Empty clarification question"],trace=trace)
                return StudioOutcome("needs_input",question=question.strip(),trace=trace)
            if kind=="tool":
                name=decision.get("tool_id")
                try:
                    result=self.catalog.invoke(name,decision.get("inputs",{}),self.allowed_access)
                    entry={"turn":step+1,"tool":name,"result":result,"outcome":"completed"}
                except (ValueError,TypeError,RuntimeError,PermissionError) as exc:
                    entry={"turn":step+1,"tool":name,"outcome":"blocked","error":str(exc)}
                trace.append(entry)
                continue
            if kind=="proposal":
                proposal=decision.get("plan")
                installed=self.catalog.executable_ids(allowed_access=self.allowed_access)
                # Plan may use only actual runnable tools; being documented does
                # not mean a provider/model/renderer is installed.
                errors=audit_proposal(proposal,brief,installed)
                if errors:
                    trace.append({"turn":step+1,"outcome":"plan_rejected","errors":errors})
                    continue
                try:
                    review=normalize_verdict(self.reviewer.review({
                        "brief":brief.public(),"plan":proposal,
                        "available_tools":discovered,
                        "instruction":"Critique narrative originality, product facts, pacing, edit feasibility, "
                        "music, visual clarity, continuity. Quote locations of concrete problems. "
                        "Being a separate role does not imply a different model."
                    }))
                except (ValueError,TypeError) as exc:
                    trace.append({"turn":step+1,"outcome":"invalid_review","error":str(exc)})
                    errors=["Reviewer response malformed; plan cannot be approved"]
                    continue
                trace.append({"turn":step+1,"outcome":"reviewed","approved":review["approved"],
                              "issue_count":len(review["issues"])})
                if review["approved"] and not review["issues"]:
                    return StudioOutcome("ready_for_human_review",
                         plan=proposal,review=review,trace=trace)
                errors=[f"{item['location']}: {item['reason']}; repair: {item['repair']}"
                        for item in review["issues"]]
                if not errors:errors=["Reviewer rejected plan without actionable issues"]
                # The model may revise creatively in the next turn. We never
                # rewrite its chosen scene count, visual format or duration.
                continue
            return StudioOutcome("failed",blockers=["Unrecognized brain action"],trace=trace)
        return StudioOutcome("blocked",blockers=errors or
            ["Finite turn budget exhausted without an acceptable creative proposal"],trace=trace)
