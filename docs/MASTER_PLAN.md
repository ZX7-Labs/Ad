# AD Studio — Master Architecture and Execution Plan
**Revision:** 2026-10-20 / v1 — living plan, revise upon evidence  
**Project:** universal creative video studio, not an ad-template generator.  
**Current milestone:** architecture + safe orchestration prototype. **NOT production-ready.**

## 0. North star and non-negotiables
A person on Android can conversationally describe *anything* (product ad, educational Short, storytelling, long-form edit, trailer, documentary, social content). The studio takes **creative ownership**, forms original editorial intent, makes independent decisions about script, emotion, visual metaphor, talent/voice, camera, fonts, sound, 2D/2.5D/3D/live footage, tool routing, pacing and multi-shot revision. It watches its own preview and fixes concrete defects. A generic template with name substitutions is a failure.

DO NOT hardcode creative choices: not number of shots, exact runtime, ad format, speaking rate, silence length, favored font, music mood, male/female voice, maximum 2.5D, frame transitions, color palette, scene roles, or particular rendering backend. User instructions, evidence, platform technical limits, resource permissions, and licenses are enforceable limits. Model generation parameters (sampling temperature etc.) may be tuned per *task* by a provider policy rather than imposing one constant across creative work.

**Truthfulness:** do not fabricate product features, client numbers, reviews, performance metrics, endorsements, user interface screens or product footage. Artistic invention is welcome, factual invention is not. Source claims from an immutable caller-owned fact ledger. Ask one question when a crucial real fact/asset is genuinely missing. Visual simulation must be marked conceptual.

**Quality:** attractive JSON is not a finished film. Structural correctness ≠ creativity ≠ renderability ≠ quality. Track separate acceptance states and evidence. No autonomous claim of 'better than human' without rigorous side-by-side user tests.

**Economics:** lightweight local CPU baseline for planning; opportunistic GPU/hosted render plugins subject to explicit connection, pricing and licensing. Free GH Actions is bounded compute, not a 24/7 free GPU. No secrets/public user data in GitHub Issues. Keep source code open and check EACH adapter's model and weights licenses separately.

**Preservation:** historical V3, FOLD renderer, approved Supertonic M3/F2 samples, evidence/test results are archival baselines. Never silently overwrite them. Do not promote an experimental branch to stable without acceptance.

## 1. Two concurrent research streams
### A. Creative intelligence and specialized models
1. Audit film-specific research: CineCrew FilmDSL, FilmAgent, MovieAgent, VideoAgent (filmmaking vs editing *systems* rather than ready-made specialist weights).
2. Search for actual downloadable *film-trained* small LLMs and evaluate origin, corpus legality, license, reproducible quality, script naturalness, narrative arc, controllability and latency. Do not trust model-card self-reports; do not automatically pick a tiny screenwriting GPT-2 because it is small.
3. Compare one lightweight general narrative model, one storytelling/screenplay specialist where licensed/credible, and a larger quality reference on *identical* blind creative briefs: consumer product, educational short, cinematic story and long-form assembly.
4. Build narrative editor skill: audience insight, memorable premise, researched facts, characters/voice, plot turns, emotional rhythm, brand appropriateness, legitimate originality. Director can propose alternatives and self-select with explicit rationale.
5. Distinct creative and factual critiques; require grounded evidence and no self-awarded "excellent" score.
6. Optimize latency by skipping roles that are unnecessary, caching asset metadata and parallelizing independent generation, NOT by forcing shorter scripts or deleting original ideas.

### B. Production engine and available tools
1. Enumerate concrete **capabilities**, not one mandatory renderer: motion design (Motion Canvas or other licensed adapter), editorial timeline (OpenTimelineIO and FFmpeg), existing Python compositor, 3D (Blender), reusable assets, typography, TTS, captions, shot recognition, ASR, music and audio mastering.
2. Assign each adapter honest status (installed / not installed / needs_setup), required hardware, license, format, input constraints, latency, cost, permission; discover dynamically.
3. Plan an open intermediate **Film Plan / Studio IR**: shot/scene identity, purpose, continuity, asset lineage, voice performance spans, music/SFX cues, editable timeline, visual design, edit instructions, dependencies and provenance. IR is descriptive; a compiler emits validated tool-specific execution graphs.
4. Support **multiple tools per shot**: agent chooses relevant combination; routers fallback gracefully. Realism needs actual images or a licensed generating backend; fallback symbolic graphics only if Director approves it as art.
5. Implement secure execution sandbox: fixed registered callable entry points, validated schemas, path/URL access restrictions, no arbitrary model-generated shell command, no paid tool without explicit permission, audit trail/undo/idempotency.
6. Preview at cheap resolution; run QA after visual/audio render, detect pacing, clipping, unreadable captions, continuity, wrong branding, invented UI; target repair of failing section.
7. Export H.264/AAC MP4 initially plus editable timeline IR, future format adapters. Do not assert all encoders/formats exist.

## 2. Architecture: one coherent studio, specialist roles on demand
User chat -> Intent + Owner fact & rights ledger -> Creative Strategist -> Screenwriter & Dramaturg -> Editorial Director -> Previsualization & Continuity -> **Tool Capability Router** -> Executable Studio IR -> Specialized renderers -> A/V Quality Inspection -> Targeted repair -> Preview/Final.

A *Producer* orchestrates with adaptive depth, not an arbitrary fixed 10/20/30 agents. A writer and director can use the **same local model** initially but should not masquerade as independent intelligence. Evidence reviewer and audiovisual QC should use appropriately distinct methods/models wherever possible. Creative initiative belongs to AI; execution permission does not.

Each stage communicates using typed contracts with source provenance and versioning, not opaque JSON blobs or copied prose. Store outputs by stage as resumable, content-hashed artifacts, with checkpoints and scenario-specific comparison results.

## 3. Implementation phases (sequenced, with gates)
- **P0 — Audit and preserve (NOW).** Inventory all 120 repository entries, distinguish legacy production and rejected research; preserve user-approved voices. Move necessary root README information into dated docs, then delete ONLY root \`README.md\` as explicitly requested.
- **P1 — Master architecture (NOW).** Establish this plan, research ledger, scope boundaries and risk register. Choose no single model/renderer until benchmarks.
- **P2 — Minimal functional producer core (NOW).** Develop \`studio_next/\` as isolated, standard-library Python modules: OwnerBrief, fact/rights ledger, registered tool manifests, capability discovery, permissioned tool calls, model-provider-agnostic Director, review and bounded iteration. **No fixed art or scene limits**. Validate with mocked brains and fake tools under free GitHub Actions.
- **P3 — Real specialist model competition.** Licensed providers as interchangeable adapters, same briefs and reference criteria, record inference latency, full output and real script quality. Advance only if concepts are fresh/specific/credible; never optimize against only a numeric self-score.
- **P4 — Executable Film IR / tool graph.** Composer builds a DAG of source assets, processing, layers, sound/voice, camera, and edit tracks. Validate dependency DAG, references, media rights, target device, resource estimates, exception recovery. Compile supported features to existing renderer; unavailable capabilities remain explicitly blocked or user-approved fallback.
- **P5 — Directed visual sample.** From a short *ordinary* user prompt, without writing a manual per-project scene graph, produce a genuine 9:16 marketing MP4 and a genre-different informative Short. Include M3 and/or F2 unchanged, sound/mix and timing chosen for each production rather than hard-coded creative constants.
- **P6 — Self-observation and selective revision.** Decode actual output; multimodal reviewer checks frame readability, scene message, style continuity; objective A/V checks clipping, speech alignment, clipping, loudness; regenerate defective segments only. Obtain human quality acceptance.
- **P7 — Advanced engines.** Install/enable licensed Motion Canvas, OpenTimelineIO, Blender, generative footage/images via connected opt-in APIs or GPU agents where available, and editor export adapters. Protect cost budgets and explicit consent.
- **P8 — App / open-source release.** Android-accessible UX, task queue/resume, artifact provenance, versioned plugins, safe defaults, observability, installation docs outside root README, accessibility, privacy/security audit, model/license compliance, bench CI and no false advertising.

## 4. Nested execution for EACH phase
1. Specify use case and measurable *output* acceptance; identify missing information.
2. Research 2–3 serious alternatives; check hardware/license/capabilities/real availability.
3. Build the smallest **non-throwaway architectural slice**; do not fake missing capabilities.
4. Write positive, adversarial and failure-path tests; require CI.
5. Run on at least two unrelated creative requests.
6. Inspect generated facts, script, storyboard, real outputs and agent traces; record defects.
7. Revise plan if evidence contradicts an assumption; move unproven choices to candidates, not constants.
8. Stage and release only with an honest changelog and user acceptance.

## 5. Risks / mitigations (living register)
- **R1 Script is generic:** specialist creative comparatives and a dramaturg using concrete premise, not formulaic hooks. Human A/B evaluation.
- **R2 Vision exceeds installed tools:** capabilities checked before scheduling; choose alternative *only with artistic agreement*. Never fake "3D generated".
- **R3 Circular AI praise:** critique backed by spans/frames and objective QC; independent model/algorithm if practical, human approval always.
- **R4 Infinite loops / no money:** bounded *compute* budget, artifact checkpoints, adaptive stage selection, resumability; user can raise budget explicitly.
- **R5 Fake product claims/media rights:** immutable facts, license/consent ledger, per-shot claim checks, block risky final renders.
- **R6 Prompt injection from web/assets/tool output:** provenance-separated untrusted data; tool allowlists and write/cost authorization; zero raw shell access.
- **R7 Model weights incompatible or noncommercial:** separate code/weights/data/voice license review and block distribution unless resolved.
- **R8 Audio gaps / timeline drift:** correct in Film IR using measured speech alignment and creative pacing, not one global fixed speed.
- **R9 Single-language or genre overfit:** compare Hindi/English, ads, Shorts, educational and long-form.
- **R10 False "free unlimited" claim:** account for GH Actions limits, cold starts, storage, GPU scarcity, rate limits.
- **R11 Performance regressions:** render-time / memory / quality gates per adapter, cache, proxy previews and selective renders.
- **R12 Lost work:** preserve source artifacts; separate research from stable; reversible changes, versioned schemas.

## 6. Immediate verified vs unverified
Verified from our repository: working authored 2D/2.5D scene compositor, M3/F2 demos, AI Director research attempts, a scripted 35.7-second marketing MP4. Also verified: some scripts/gates hardcode visual/scene restrictions, and unrenderable LLM output was previously rejected.

Not verified/not built: arbitrary natural-language -> auto-compiled production-grade MP4, autonomous human-level editing, unlimited tool install, visually correct 3D, independent visual QA, universal free GPU, high-quality specialist small creative model. This plan is an architecture **to implement**, not a feature-complete product.

## 7. Sources (recheck before implementation)
- CineCrew FilmDSL: https://github.com/Ironieser/CineCrew
- VideoAgent editing orchestration: https://github.com/HKUDS/VideoAgent
- FilmAgent role-based virtual production: https://arxiv.org/abs/2501.12909
- MovieAgent hierarchical CoT: https://arxiv.org/abs/2503.07314
- OpenTimelineIO: https://opentimelineio.readthedocs.io/en/latest/
- Motion Canvas: https://motioncanvas.io/
- Blender: https://www.blender.org/
- FFmpeg: https://ffmpeg.org/

**Plan update rule:** Evidence wins. If research finds a better creative model, renderer, reviewer or architecture, amend this plan and record *why*. Do not add arbitrary bottlenecks or pretend physical, computational and legal constraints do not exist.
