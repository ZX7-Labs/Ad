"""Evidence-anchored screenplay review contract.

A critic must cite ACTUAL supplied draft text for each specific critique.
Matching evidence is *necessary*, not sufficient proof of correct reasoning.
Critical factual judgments require independent semantic verification/human review.
"""
from dataclasses import dataclass, field
from typing import Any
import re

@dataclass(frozen=True)
class ReviewAudit:
    structurally_valid: bool
    accepted_issues: list[dict] = field(default_factory=list)
    rejected_issues: list[dict] = field(default_factory=list)
    process_errors: list[str] = field(default_factory=list)
    verified_fact_claims: bool = False
    human_creative_approval: bool = False
    def public(self):
        return {
            "structurally_valid":self.structurally_valid,
            "accepted_issues":self.accepted_issues,
            "rejected_issues":self.rejected_issues,
            "process_errors":self.process_errors,
            "verified_fact_claims":self.verified_fact_claims,
            "human_creative_approval":self.human_creative_approval,
        }

def normalize_text(text):
    if not isinstance(text,str):
        return ""
    return re.sub(r"\s+"," ",text).strip().casefold()

def validate_evidence_review(treatment:dict, review:dict)->ReviewAudit:
    if not isinstance(treatment,dict) or not isinstance(treatment.get("scenes"),list):
        return ReviewAudit(False,process_errors=["Missing screenplay scenes"])
    if not isinstance(review,dict):
        return ReviewAudit(False,process_errors=["Reviewer output must be object"])
    items=review.get("issues")
    if not isinstance(items,list):
        return ReviewAudit(False,process_errors=["Reviewer must supply issues array"])
    if not isinstance(review.get("approved"),bool):
        return ReviewAudit(False,process_errors=["Reviewer must supply approved boolean"])
    texts={}
    for scene in treatment["scenes"]:
        if not isinstance(scene,dict) or not isinstance(scene.get("id"),str):
            return ReviewAudit(False,process_errors=["Bad screenplay scene id"])
        sid=scene["id"]
        if sid in texts:
            return ReviewAudit(False,process_errors=["Duplicate scene ids"])
        # Treat exact authored scene fields as admissible evidence, not the
        # critic's own made-up summary.
        fields=("purpose","narration","visual","motion","edit","audio")
        texts[sid]=" ".join(str(scene.get(k) or "") for k in fields)
    accepted=[];rejected=[]
    for n,issue in enumerate(items,1):
        if not isinstance(issue,dict):
            rejected.append({"index":n,"why":"Issue must be object"});continue
        sid=issue.get("scene_id")
        excerpt=issue.get("source_excerpt")
        reason=issue.get("reason")
        fix=issue.get("repair")
        if not all(isinstance(x,str) and x.strip() for x in (sid,excerpt,reason,fix)):
            rejected.append({"index":n,"why":"Missing scene ID, exact excerpt, reason or repair"});continue
        if sid not in texts:
            rejected.append({"index":n,"why":f"Unknown scene {sid}"});continue
        if normalize_text(excerpt) not in normalize_text(texts[sid]):
            rejected.append({"index":n,"why":f"No exact screenplay evidence for {sid}",
                             "unsupported_excerpt":excerpt[:150]});continue
        accepted.append(issue)
    # Do not let reviewer claim verified production, rights or facts merely
    # because the selected text exists in the script.
    issues=review.get("issues",[])
    contradictions=(review["approved"] and (accepted or rejected))
    errors=[]
    if contradictions:errors.append("Reviewer approves while listing issues")
    if rejected:errors.append("Reviewer included ungrounded or malformed issues")
    return ReviewAudit(not errors,accepted,rejected,errors,
                       verified_fact_claims=False,human_creative_approval=False)
