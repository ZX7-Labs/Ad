# Qwen3.5-4B Cinema Director — Real CPU Benchmark Findings

**Date:** 2026-10-20
**Status:** REJECTED as production director; valuable research prototype, not a user-approved video system.
**Scope:** `director_research/` only. Original V3 video renderer, previous Director Lab, and the user-approved Supertonic M3/F2 samples are untouched.

## Goal
Test a fully offline, no-API-key, Apache-2.0 Qwen3.5-4B-GGUF with a CineCrew-*inspired* FilmDSL-like intermediate film plan: global art/voice rules, continuity assets, shots with action + staging + render instructions, independent critic, hard claim/timing/asset checks.

The official CineCrew repo is a complete orchestration system using configurable backends. **This code is our separate small benchmark; it does not reproduce/claim to run CineCrew.**
- CineCrew: https://github.com/Ironieser/CineCrew
- Qwen3.5-4B: https://huggingface.co/Qwen/Qwen3.5-4B
- Tested Q4_K_M quantization: https://huggingface.co/SoAIHQ/Qwen3.5-4B-GGUF
- llama.cpp backend release tested: b11750.

## Observed experiments on free GitHub Actions CPU

| Run | Creative stages | Measured model generation | Outcome |
| --- | --- | --- | --- |
| [39419824396](https://github.com/oyzitjfzj/Ad/actions/runs/39419824396) | Concept, shots, critic | 100.2 + 163.8 + 162.5 = 426.5 seconds | **Failed:** reviewer truncated response at 500 tokens; program correctly exited failure. |
| [39421003900](https://github.com/oyzitjfzj/Ad/actions/runs/39421003900) | Concept, shots, shorter critic | 24.6 + 116.7 + 43.8 = 185.1 seconds | **Blocked:** missing palette, voice, art metadata, descriptive rather than enumerated technique labels; critic 4/10. |
| [39421883500](https://github.com/oyzitjfzj/Ad/actions/runs/39421883500) | Concept, art/sound, shots, critic | 26.6 + 52.6 + 125.0 + 49.7 = 253.9 seconds | **Blocked:** tech labels are descriptive strings (`2.5d liquid simulation`) instead of enums (`2.5d`); independent critic scores 5/10, and story has practical and conceptual inconsistencies. |

Timing is model generation only, not all GitHub setup/download time.

## Third run — actual proposed direction
- Concept: A chaotic river of neon scribbles and files becomes smooth water to symbolize clarity.
- Positive: Narration text present, 5 timed clips totaling exactly 24s, full palette, M3 narrator, motion/camera/light/audio and continuity anchor.
- Serious problem: A 'Click Organize' button was invented despite no verified NOVA UI or ability description.
- Serious problem: 2.5D 'liquid simulation' and convincing water are beyond the existing lightweight Pillow/FFmpeg renderer without a new, tested implementation.
- Continuity/creative issue: shaky panic in first scene contradicts a calm, premium brand concept.
- Most structural QA flags arose because the model puts descriptive phrases in `technique` where strict enums were required; fix by parsing base technique AND keeping descriptive detail. This is formatting, not proof the idea is feasible.
- Critic recommendations themselves require scrutiny: the critic requested actual UI and fluid simulations without those assets/tools having been verified. An LLM critic is NOT objective production verification.

## Engineering conclusions
1. **Don't ship this as an expert director.** Text-only Qwen3.5-4B on free CPU can generate a structured storyboard, but reliable visual originality, claim grounding, and feasibility are not yet shown.
2. **Keep art direction detailed.** Reducing output detail is not the goal; split responsibilities and use a coherent film specification. Clip count (5) and target duration (24s) were fixed **only as controlled research conditions**, not future creative templates.
3. **Add a capability registry** reflecting the actual available renderer/asset tools. Never ask for unsupported physical fluid dynamics, real software screenshots, live actor footage or complex 3D as if available.
4. **Repair schema mismatch deterministically** (map `2.5d liquid simulation` to technique `2.5d` plus a retained `technique_notes` field). This should NEVER override feasibility errors.
5. **Add truthful asset/claim grounding** linking narration to product facts supplied by owner. Do not invent click interactions, guaranteed results or services.
6. **Use human-selected creative taste** as a quality criterion; critic grades are not a substitute for professional-looking visual test renders.
7. Next meaningful benchmark: at least two **different genres** (tech creator and realistic consumer product ad) and a genuinely adaptive number of shots; benchmark creative value per elapsed CPU minute.
8. Vision capability was NOT tested; the GGUF run used TEXT only, no separate mmproj.

No MP4 or animation was produced, no voices were changed, no agency website repository was touched.

**Bottom line:** a functioning isolated research pipeline and clear failure evidence exist. The desired world-class creative editor does **not** exist yet, and accepting this prototype would be premature.
