"""A director-authored cinematic film without a monolithic output ceiling.

The AI first determines its OWN causal story and shot structure, then writes
individual production-grade scenes with the whole arc/adjacent beats in view.
No fixed scene count, duration, medium, style or artificial target length.
Stage artifacts are content-addressed by the existing checkpoint system.
"""
from __future__ import annotations

import math


SPINE = """You are the head director and dramaturg, not a template writer.
Given owner facts, a genuinely selected original premise and the entire
competition, imagine a COMPLETE compelling film. Make the audience care.
Structure the story freely: number of shots, length, format, genre, voice and
medium belong to you. Avoid generic slogans, fake facts, unexplained imagery,
invented product demonstrations and arbitrary visual effects.
This step is a production narrative BLUEPRINT, not the complete screenplay.
Choose story-specific shot purposes and continuity, so each shot is causally
necessary and its visuals can later be executed with licensed engines.
Think through how the subject creates the dramatic turn, and how the FINAL
image pays off the first. Do not default to 2D cards.
Return ONLY JSON with the exact required fields:
{"title":"specific original film title",
"creative_intent":"WHY this exact film exists",
"story":"fully intelligible causal dramatic progression, not generic adjectives",
"audience_impact":"what audience feels, knows or does",
"visual_language":{"imagery":"...","typography":"...","composition":"...",
"camera":"...","3d":"motivated where needed","music":"...","sound":"..."},
"voice":{"choice":"M3|F2|no_voice","why":"...","delivery":"..."},
"scene_map":[{"id":"meaningful unique machine ID",
"purpose":"how this advances story","duration_seconds":4.5,
"dramatic_action":"specific event/causal change","visual_goal":"specific film image",
"continuity_in":"relation to previous","continuity_out":"relation to next",
"sound_goal":"sound's narrative purpose","factual_intent":["verified fact IDs only"]}],
"last_image":"specific image closing the story",
"production_unknowns":["real unavailable rights/resources ONLY"]}.
This illustrative duration/scene count is NOT a target or fixed limit.
Design as many distinct necessary beats as this exact film demands.
All claims must derive from supplied owner facts. No Markdown."""


SHOT = """You are the same film's supervising director, production designer and writer.
Expand precisely ONE beat of the ALREADY CHOSEN original story into a concrete
filmable scene. Preserve id, purpose, duration, continuity, voice choice,
causal meaning and factual boundaries. Show a specific action with coherent
objects, camera, sound, edit and emotionally natural ACTUAL dialogue if needed.
You have the complete plot spine, the preceding finished scene (if any), the
immediate following beat and original facts. Do not invent real product footage,
UI, prices, endorsements or performance claims. You may invent explicitly
fictional staging and purposeful abstractions. Avoid vague aspirational visuals
and corporate filler. The treatment can ask for live action, 2D, layered 3D or
anything else; never downgrade to flat cards based on a weak installed tool.
Do not shorten/extend the director-approved shot to fit an output budget.
Each field can be concise but must give precise rich art/acting decisions.
Return ONLY this JSON object:
{"id":"exact beat ID","purpose":"same beat purpose",
"duration_seconds":4.5,
"narration":"natural actual spoken words, or empty string if intentional silence",
"visual":"concrete observable scene, composition, objects, aesthetics",
"motion":"what truly moves, choreography, depth and timing",
"edit":"motivated transition FROM previous and TO next",
"audio":"specific sound, score dynamics, timing relative to action",
"fact_refs":["original owner fact IDs actually asserted"],
"assets_needed":["specific asset and its actual rights/unknowns"]}.
This 4.5 second duration is an example, never a limitation or target.
No added claims, no code, no markdown."""


ENDING_REPAIR = """You are the supervising director finishing an ALREADY authored film.
The model already chose the plot, sequence, shot lengths, images and audience
impact. Preserve every prior decision unchanged. The only missing field is the
specific FINAL IMAGE: the literal visible last frame that provides a moving
payoff to the previously chosen story. Make this concrete and filmable while
never claiming unverified physical attributes or fabricated product features.
Do not re-author the story or add a new scene. Do not create a generic CTA.
Reply with ONLY JSON: {"last_image":"one specific dramatic visible last frame"}.
"""


def complete_missing_ending(spine, brief, call_stage):
    """Repair an explicitly missing final image without changing the scene map.

    The original generation is content-addressed and remains on disk; this
    surgical creative repair is separately cached and independently verified.
    """
    if not isinstance(spine,dict):
        raise TypeError("Director blueprint missing")
    if isinstance(spine.get("last_image"),str) and spine["last_image"].strip():
        return spine
    response=call_stage("spine-last-image",ENDING_REPAIR,
        {"owner":brief,"existing_film":spine},450,.48)
    if not isinstance(response,dict) or set(response)!={"last_image"}:
        raise ValueError("Ending repair must return only a literal last_image")
    ending=_good_text(response.get("last_image"),"closing image")
    return dict(spine,last_image=ending)


_FILM_FIELDS = ("voice", "scene_map", "last_image", "production_unknowns")


def normalize_spine_layout(spine):
    """Recover misplaced *unchanged* film fields from a valid JSON response.

    Local 4B models sometimes accidentally nest these film-level fields inside
    visual_language. Promote exact existing bytes/values ONLY: no invented
    narrative, no fabricated fact references, no style/shot substitutions.
    A conflict between nested and root fields is a hard rejection.
    """
    if not isinstance(spine,dict):
        raise ValueError("Film spine not object")
    output=dict(spine)
    visual=output.get("visual_language")
    if not isinstance(visual,dict):
        return output
    visual=dict(visual)
    for name in _FILM_FIELDS:
        if name not in visual:
            continue
        if name in output and output[name]!=visual[name]:
            raise ValueError("Conflicting director-authored "+name)
        if name not in output:
            output[name]=visual[name]
        del visual[name]
    output["visual_language"]=visual
    return output


def _good_text(s, what):
    if not isinstance(s,str) or not s.strip():
        raise ValueError("Missing director-authored "+what)
    return s


def validate_spine(spine, fact_ids):
    if not isinstance(spine,dict):
        raise ValueError("Film spine not object")
    for k in ("title","creative_intent","story","audience_impact","last_image"):
        _good_text(spine.get(k), k)
    visual=spine.get("visual_language")
    if not isinstance(visual,dict) or not all(isinstance(x,str) and x.strip()
              for x in visual.values()) or not visual:
        raise ValueError("Visual grammar missing")
    voice=spine.get("voice")
    if not isinstance(voice,dict) or voice.get("choice") not in ("M3","F2","no_voice"):
        raise ValueError("Voice must be approved or deliberately silent")
    if not isinstance(spine.get("production_unknowns"),list):
        raise ValueError("Missing production unknowns ledger")
    beats=spine.get("scene_map")
    if not isinstance(beats,list) or not beats:
        raise ValueError("Director did not author a causal story arc")
    ids=set()
    for i,beat in enumerate(beats):
        if not isinstance(beat,dict):
            raise ValueError("Malformed beat "+str(i))
        ident=_good_text(beat.get("id"),"shot ID")
        if ident in ids:
            raise ValueError("Duplicate film beat "+ident)
        ids.add(ident)
        for k in ("purpose","dramatic_action","visual_goal","continuity_in",
                  "continuity_out","sound_goal"):
            _good_text(beat.get(k), f"{ident}.{k}")
        dur=beat.get("duration_seconds")
        if isinstance(dur,bool) or not isinstance(dur,(int,float)) or (
            not math.isfinite(dur) or dur<=0):
            raise ValueError("Invalid director-owned shot duration")
        ids_=beat.get("factual_intent")
        if not isinstance(ids_,list) or any(not isinstance(x,str) or x not in fact_ids
                                             for x in ids_):
            raise ValueError("Scene cites nonexistent owner facts")
    return beats


def validate_authored_shot(shot, beat, fact_ids):
    if not isinstance(shot,dict) or set(shot)!={
            "id","purpose","duration_seconds","narration","visual","motion",
            "edit","audio","fact_refs","assets_needed"}:
        raise ValueError("Model did not produce full independent authored scene")
    if shot["id"]!=beat["id"]:
        raise ValueError("Shot identity lost during segmented production")
    if shot["purpose"]!=beat["purpose"]:
        raise ValueError("Director's story purpose silently rewritten")
    if shot["duration_seconds"]!=beat["duration_seconds"]:
        raise ValueError("Director-approved duration silently changed")
    if not isinstance(shot["narration"],str):
        raise ValueError("Narration absent")
    for key in ("visual","motion","edit","audio"):
        _good_text(shot.get(key),key)
    facts=shot["fact_refs"]
    if not isinstance(facts,list) or any(not isinstance(x,str) or x not in fact_ids
                                        for x in facts):
        raise ValueError("Unverified factual assertion reference")
    if not isinstance(shot["assets_needed"],list) or any(not isinstance(x,str)
              or not x.strip() for x in shot["assets_needed"]):
        raise ValueError("Asset requirements not authored")
    return shot


def create_screenplay(brief, pitches, selection, call_stage):
    """call_stage(name, system, data, tokens, temperature) caches every output."""
    if not isinstance(brief,dict) or not isinstance(brief.get("facts"),dict):
        raise ValueError("Source fact ledger required")
    fact_ids=frozenset(brief["facts"])
    spine=call_stage("spine",SPINE,{"owner":brief,"pitches":pitches,
                      "selected_concept":selection},2200,.63)
    spine=normalize_spine_layout(spine)
    spine=complete_missing_ending(spine,brief,call_stage)
    beats=validate_spine(spine,fact_ids)
    scenes=[]
    for i,beat in enumerate(beats):
        context={"brief":brief,"film_spine":spine,
                 "current_beat":beat,
                 "previous_finished_scene":scenes[-1] if scenes else None,
                 "next_beat":beats[i+1] if i+1<len(beats) else None,
                 "explicit_constraints":"Only the shot detailed here; return one JSON object."}
        shot=call_stage(f"scene-{i+1:03d}",SHOT,context,1900,.55)
        scenes.append(validate_authored_shot(shot,beat,fact_ids))
    voice=spine["voice"]["choice"]
    if voice=="no_voice" and any(s["narration"].strip() for s in scenes):
        raise ValueError("Model chose no_voice but wrote actual spoken dialogue")
    return {k:v for k,v in spine.items() if k!="scene_map"} | {"scenes":scenes}


def retryable_output(error):
    """Only genuinely truncated generation is retryable with a larger budget."""
    return isinstance(error, ValueError) and "truncated" in str(error).lower()
