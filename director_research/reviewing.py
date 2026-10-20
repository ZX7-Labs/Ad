"""Evidence-linked motion-design review, version 2.

Grounding a complaint in an actual field prevents invented quotations and broken
references. It does not prove the complaint is correct; human review still matters.
"""
import copy

from director_research.contracts import TEXT, obj, schema_errors, text_fields


FINDING = obj({
    "category": {"type": "string", "enum": ["factual", "execution", "story",
                                            "readability", "continuity", "sound"]},
    "path": TEXT,
    "excerpt": TEXT,
    "reason": TEXT,
    "repair": TEXT,
})
REVIEW = obj({
    "approved": {"type": "boolean"},
    "score_out_of_10": {"type": "number", "minimum": 0, "maximum": 10},
    "factual_support": {"type": "boolean"},
    "execution_realistic": {"type": "boolean"},
    "strongest_moment": TEXT,
    "findings": {"type": "array", "items": FINDING, "maxItems": 3},
})

PROMPT = """You are a skeptical senior MOTION DESIGN and editorial reviewer.
Assess the complete short: story, precise benefit, viewer appeal, visual continuity,
legibility, feasible animation, timing, narration and sound. Be rigorous and fair.
This is a 2D/2.5D faceless motion graphic, not live-action footage. Do not apply
physical-camera or material-simulation requirements to graphic editing.

Distinguish these cases correctly:
- An instantaneous cut/freeze/appearance is an edit, not an instant product result.
- A static camera CAN contain animated text and moving graphic layers.
- A rhetorical problem setup ('the world is too loud') is not automatically a
  measurable product promise. Flag a specific unsupported product assertion.
- Owner-reported benefit copy may be used as supplied; it is not independently
  verified. Do not demand different facts or insist every source fact appear.
- A symbolic paper outline can introduce a notebook without an exact product
  photo. It cannot invent foldability, dimensions, endorsements or actual UI.
- 'No photorealistic 3D' rejects that technique; it does not request it.
- A cut between drawn shapes is available; continuous material morph simulation
  is not. Cite the actual instruction requiring an unavailable operation.
- Do not demand 3D, screenshots, footage or recordings that were not supplied.

Do catch genuine unsupported features, false evidence citations, feature-like
metaphors, unavailable assets or tools, conflicting continuity/timings, vague
assets, generic repeated slogans and weak connection between motif and product.
Check the final shot details against the design and the brief, not just the idea.
The current registry supplies primitives, not an arbitrary renderer; judge whether
the proposed instructions have a plausible implementation with those primitives.

For EACH blocker return a finding with category, a provided JSON-pointer path,
an EXACT contiguous excerpt copied from that field, the concrete reason and an
actionable repair. Do not invent a quotation or cite a different field. At most
three findings, each concise. No filler such as 'Recommended repairs' in findings.
Set factual_support=false only for a factual finding; execution_realistic=false
needs an execution/readability/continuity/sound finding. Problems of taste or
story alone do not make a fact false. Strongest_moment must describe this proposal.
Approval requires score >=8, factual_support=true, execution_realistic=true and
zero findings. Do not approve merely because the JSON is valid. Return the schema.
"""


def review_schema(bundle):
    schema = copy.deepcopy(REVIEW)
    # Constrain pointer generation to fields that actually exist in this draft.
    schema["properties"]["findings"]["items"]["properties"]["path"] = {
        "type": "string", "enum": list(dict(text_fields(bundle)))}
    return schema


def audit_review(review, bundle):
    errors = schema_errors(review, review_schema(bundle))
    if errors:
        return {"passed": False, "errors": errors}
    fields = dict(text_fields(bundle))
    categories = {f["category"] for f in review["findings"]}
    for index, finding in enumerate(review["findings"], 1):
        if finding["excerpt"] not in fields[finding["path"]]:
            errors.append(f"Finding {index}: excerpt is not in the cited field")
    if not review["factual_support"] and "factual" not in categories:
        errors.append("False factual_support requires a grounded factual finding")
    if not review["execution_realistic"] and not categories.intersection(
            {"execution", "readability", "continuity", "sound"}):
        errors.append("False execution_realistic requires a grounded execution-related finding")
    if review["approved"] and (review["findings"] or review["score_out_of_10"] < 8
                               or not review["factual_support"] or not review["execution_realistic"]):
        errors.append("Approval contradicts the score, findings or review flags")
    return {"passed": not errors, "errors": errors,
            "notice": "Grounded quotations do not establish correctness of model judgement"}


def review_passes(review, bundle):
    return (audit_review(review, bundle)["passed"] and review["approved"] is True
            and review["score_out_of_10"] >= 8 and review["factual_support"] is True
            and review["execution_realistic"] is True and not review["findings"])
