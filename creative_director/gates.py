"""Pure, testable production gate: AI critic approval alone can never override this."""
import math
import re

CLAIMS=re.compile(r"(?i)\b(?:100%|guaranteed|clinically proven|number one|#1|best in the world|fastest|cures?|saves? \d+|\d+[xX] faster|\d+%|free forever|zero risk)\b")
ROLE={"hook","context","reveal","demonstration","proof","payoff","cta"}
SHOTS={"2d","2.5d","3d","real_footage"}
VOICE={"M3","F2"}
def audit(plan,brief):
    errors=[];warnings=[]
    if not isinstance(plan,dict):
        return {"errors":["Treatment not JSON object"],"warnings":[]}
    for k in ("concept","creative_reason","hook","tone"):
        if not str(plan.get(k) or "").strip():errors.append("Missing "+k)
    vision=plan.get("visual_system")
    if not isinstance(vision,dict) or not isinstance(vision.get("palette"),list) or len(vision["palette"])<2:
        errors.append("Invalid palette")
    else:
        for color in vision["palette"]:
            if not re.fullmatch(r"#[0-9a-fA-F]{6}",str(color)):
                errors.append("Invalid palette color")
    audio=plan.get("audio")
    if not isinstance(audio,dict) or audio.get("voice") not in VOICE:
        errors.append("Voice must be approved M3 or F2")
    shots=plan.get("beats",[])
    if not isinstance(shots,list) or not 4<=len(shots)<=6:
        errors.append("Need 4-6 meaningful shots");shots=[]
    truth=" ".join(map(str,brief.get("truths") or [])).lower()
    total=0;words=0
    for i,beat in enumerate(shots,1):
        if not isinstance(beat,dict):
            errors.append(f"Shot {i} must be object");continue
        if beat.get("role") not in ROLE:errors.append(f"Shot {i} invalid story role")
        tech=beat.get("technique")
        if tech not in SHOTS:errors.append(f"Shot {i} invalid shot technique")
        if tech=="real_footage":errors.append(f"Shot {i} requires unprovided licensed footage")
        if tech=="3d":warnings.append(f"Shot {i}: 3D feasibility not yet verified")
        for k in ("visual","motion","on_screen","transition","sound","fact_basis"):
            if not str(beat.get(k) or "").strip():errors.append(f"Shot {i} missing {k}")
        try:duration=float(beat.get("seconds",0))
        except (TypeError,ValueError):duration=0.0
        if not math.isfinite(duration) or not 2<=duration<=12:
            errors.append(f"Shot {i} invalid duration");duration=0
        total+=duration
        narration=str(beat.get("narration") or "")
        n=len(re.findall(r"\b[\w'-]+\b",narration));words+=n
        if n>max(3,int(duration*3.25)):errors.append(f"Shot {i} narration too fast")
        combined=(narration+" "+str(beat.get("on_screen") or "")).lower()
        for claim in CLAIMS.findall(combined):
            if claim.lower() not in truth:errors.append(f"Shot {i} unsupported claim: {claim}")
    try:requested=float(brief.get("duration_seconds") or 24)
    except (TypeError,ValueError):requested=24
    if not 12<=requested<=90:errors.append("Unsupported target duration")
    if shots and abs(total-requested)>1:errors.append(f"Duration total {total:g}s differs from {requested:g}s")
    if shots and shots[0].get("role")!="hook":errors.append("Opening lacks hook shot")
    if shots and shots[-1].get("role") not in ("cta","payoff"):
        warnings.append("Last shot needs payoff or CTA")
    if brief.get("action") and shots and shots[-1].get("role")=="cta":
        spoken=(str(shots[-1].get("narration") or "")+" "+str(shots[-1].get("on_screen") or "")).lower()
        if str(brief["action"]).lower() not in spoken:
            warnings.append("Final CTA does not precisely match owner's action")
    return {"errors":list(dict.fromkeys(errors)),"warnings":list(dict.fromkeys(warnings)),
            "duration_seconds":round(total,2),"target_seconds":requested,"narration_words":words}
