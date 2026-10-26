# ZX7 — Failure audit and verified corrective changes (21 October 2026)

This is a log-grounded engineering record, NOT a film-completion claim.

## Actual last complete creative model run

- Run https://github.com/oyzitjfzj/Ad/actions/runs/39524196131 **FAILED**. Code and tool installation stages passed. Qwen3.5-4B Q4_K_M via local `llama.cpp` authored and cached pitches/selection/spine, then five factual-grounding revisions. It generated its first fully written scene and **failed validation**: shot `s1` was director-approved for **6.0s** in the original scene map, but the model wrote **4.5s** in the concrete scene. The output was not silently accepted. No autonomous movie was made.
- Examined actual original GitHub artifact id `12312069973`, not only logs. The scene incorrectly treated a tablet voltage-drop/device malfunction as established physical cause, although the owner's brief only provides that FOLD is a paper pocket notebook intended for handwritten ideas, plus absence of verified product photographs/material claims/sales evidence. A matching `fact_refs` key alone does not prove the *content* of that scene.
- This is also a **creative-story causality / evidence issue**, not only a schema mismatch. Valid JSON, sound design and 3D camera directions do not certify truthful, memorable cinema.

## Changes

1. `studio_next/segmented_screenplay.py`: one per-scene artistic repair when a model breaks the director-authored timing, scene identity/purpose or fact reference. The original raw scene remains checkpointed and separately preserved; repairs cannot change the original beat or silently change voice/length. A second invalid repair remains blocked. This does NOT assume any fixed film length, number of shots or 2D style.
2. `studio_next/test_segmented_screenplay.py`: new tests that reproduce a 6-vs-4.5s mismatch and ensure the model must genuinely rewrite the failed scene; no zero-effort substitution or fake approval; added guards against invented fact refs and unchanged other scenes.
3. `studio_next/creative_challenge.py`: independent editor review explicitly checks the real screenplay for unsupported material/competitor/effect claims and narrative dependence on the subject; cite real excerpts, no free passes from nominal fact IDs. Model critic is **not an independent factual oracle** and human creative evaluation still necessary.
4. `motion_studio/voice.py`: earlier accepted Supertonic M3/F2 voice synthesis and style settings remain unchanged when speech exists. For intentionally dialogue-free scenes in a film that has a selected M3/F2 narrator, a real 16-bit PCM silence WAV is created instead of asking TTS to speak an empty string. The first test identified incorrectly encoded literal escape bytes (3200 rather than 800 PCM samples); fixed using `bytes(samples*2)`.
5. `studio_next/test_voice_slots.py`, `.github/workflows/studio-creative-contracts.yml`: silence WAV regression verified (16,000 Hz, 800 mono samples, 0.05s), negative input validation, and reproducible no-inference tests.

## Evidence

- Exact lightweight contract run https://github.com/oyzitjfzj/Ad/actions/runs/39526447076 **SUCCESS**, all **167 tests** passed.
- Another heavy *real-model* run https://github.com/oyzitjfzj/Ad/actions/runs/39526137163 was **in progress in the film-authoring stage at last check**. It uses a snapshot prior to the later silence bug fix, so that later correction is not proven by this heavy run. Do not retroactively call it a success or imply GitHub will run after chat without inspecting it again.
- All source changes live in the isolated branch `zx7-specialist-free-stack-20261020`; main is untouched. No added required paid model/host/server.

## Outstanding, high-priority milestones

A creative writing model must produce a storyboard preserving its own causally correct film arc. Scenes must be meaningfully verified against owner facts, rights and actual production capability, then executed to a real MP4 with M3/F2 as appropriate. Final rendered frame/audio quality must be independently judged; a script-audition score or 167 passing code tests is not evidence of high-end movie quality.

Do not start a new full 4B CPU run for every minor code change; preserve verified checkpoints and use the separate lightweight tests first. The existing 4B baseline has repeated actual creative/output-control failures, and may need replacement or domain training instead of endless per-error patching.
