"""Structural compiler between the LLM draft and deterministic QA.
Corrects only metadata/format and timings, never writes product claims.
"""
import copy
import re

def compile_treatment(draft,brief):
    if not isinstance(draft,dict):return draft
    p=copy.deepcopy(draft)
    # Some compact LLMs put the whole request inside an extra treatment key.
    for _ in range(2):
        if not p.get("beats") and isinstance(p.get("treatment"),dict):
            p=p["treatment"]
        else:break
    beats=p.get("beats")
    if not isinstance(beats,list) or not 4<=len(beats)<=6:return p
    target=brief.get("duration_seconds",24)
    try:target=float(target)
    except(TypeError,ValueError):target=24
    if not 12<=target<=90:return p
    for beat in beats:
        if not isinstance(beat,dict):continue
        # Interpret absent documentation as a CONCEPTUAL render plan only, never as sourced product evidence.
        if not beat.get("fact_basis"):
            beat["fact_basis"]="Conceptual illustrative asset, not a literal product demo or evidence"
        # On-screen copy must be actual words; bracketed text describes visuals instead.
        onscreen=str(beat.get("on_screen") or "")
        if onscreen.startswith("[") and onscreen.endswith("]"):
            if not beat.get("visual"):
                beat["visual"]=onscreen[1:-1]
            # Do not create advertising promises to repair unusable captions.
            spoken=str(beat.get("narration") or "").strip()
            shortlist=re.split(r"(?<=[.!?])\s+",spoken)[0].strip()
            beat["on_screen"]=" ".join(shortlist.split()[:5]).strip(" .!?") or str(beat.get("role","")).upper()
    durations=[]
    for beat in beats:
        try:durations.append(float(beat.get("seconds",0)))
        except(TypeError,ValueError):durations.append(0)
    if abs(sum(durations)-target)<=0.6:return p
    # Reschedule based on the spoken message's reading time, preserving total duration.
    # If total narration cannot fit even at 3 words/sec, leave invalid and block.
    wordcounts=[len(re.findall(r"\b[\w'-]+\b",str(b.get("narration") or ""))) for b in beats]
    if sum(wordcounts)>target*2.95:return p
    weights=[max(2.4,w/2.4) for w in wordcounts]
    totalw=sum(weights)
    seconds=[round(target*w/totalw,1) for w in weights]
    seconds[-1]=round(target-sum(seconds[:-1]),1)
    if any(s<2 or s>12 for s in seconds):
        return p  # Not safely auto-fixable.
    for b,d in zip(beats,seconds):b["seconds"]=d
    p.setdefault("production_warnings",[]).append(
        "Shot seconds normalized to spoken word counts; human editor should review rhythm.")
    return p
