# ZX7 Studio — free compute and specialist capability evidence (20 October 2026)

**Status:** research/design addendum, not installation, deployment, product-quality approval or replacement of the master plan.
**Based on:** docs/MASTER_PLAN.md, docs/RESEARCH_LEDGER.md, PROJECT_SCOPE.md, studio_next/experiments/RESULTS_2026-10-20.md.
**Branch policy:** preserve main, studio-vnext-independent-proof, tested M3/F2 voice artifacts and historical rejected model outputs. This document extends rather than replaces the living plan.

## Recovered product requirement

An Android-first, conversational, open-source video studio should **own creative decisions** about original idea, narrative, scene structure, cinematography, 2D/3D, footage, music, performance, voice, subtitles, continuity, editing and quality correction. It must render and inspect REAL video, not merely return beautiful JSON. No hardcoded shot/length/genre/style template. No unlicensed media or invented customer/product facts. No required paid API/subscription. Free public compute is scarce, conditional and cannot be represented as an always-on editing server.

## Verified repository checkpoint before this research

- Main already has source for legacy V3 and independently authored FOLD and marketing MP4 samples; those are NOT automatically generated from arbitrary dialogue.
- Separate studio-vnext-independent-proof branch has typed planning, Film IR, registered permission-gated tool execution, resumable checkpoints and tests. Latest contract run 39463581081 passed (https://github.com/oyzitjfzj/Ad/actions/runs/39463581081).
- Story competition runs still failed; see 39459063665 (https://github.com/oyzitjfzj/Ad/actions/runs/39459063665). A passing contract run does not mean professional-quality scripts or rendered videos.
- The 9B screenplay reference was rejected for causality, genericity/unsupported physical details and reviewer errors; measured CPU stages totaled ~976.36s in run 39455528289. An increase in parameter count is NOT verified creative competence.
- Do not promote any model to the production Director until identical blind trials, semantic truth checks and rendered human-reviewable output succeed.

## Candidate specialist capability registry

**All are CANDIDATES, not installed runnable adapters.** Distinguish software license, model-weight license, data/asset provenance and hosted service policy. Hardware thresholds are publication estimates and must be measured with pinned versions.

| Capability | Candidate (official) | License as currently shown | Fit and boundary |
|---|---|---|---|
| Cinema shot-language understanding | ShotVL-3B, https://huggingface.co/Vchitect/ShotVL-3B | model Apache-2.0 | Actual cinematography-specialized 3B VLM. Use on source/preview frames for angle, shot size, motion and composition. NOT evidence of good independent screenplay or reliable instruction following. |
| Human-aligned perceptual quality | Q-ReAlign-Mini-0.8B, https://huggingface.co/q-future/Q-ReAlign-Mini-0.8B | model Apache-2.0 | Very small video/image quality and aesthetics reviewer; scores MUST be paired with concrete rendered observations; not dramaturgy. |
| Advertisement clip selection/order/music | AutoCut, https://github.com/AdAutoCut/Autocut and https://huggingface.co/MiltonZ/AutoCut_embsft | research code and weights published; redistribution/commercial status requires inspection | Relevant learned editing design, but 8B + multimodal encoders; not a drop-in tiny CPU editor. Research dataset URLs do not confer commercial reuse rights. |
| Shooting-script conversion | ScriptAgent, https://huggingface.co/XD-MU/ScriptAgent | commercial weight-license not verified | Genuine domain-targeted shooting-script research, but ~11B and GPU-centric; must remain blocked pending license/hardware evaluation. |
| Original stills + reference editing | FLUX.2 [klein] 4B, https://github.com/black-forest-labs/flux2 and https://huggingface.co/black-forest-labs/FLUX.2-klein-4B | model Apache-2.0 | Strong actual asset-generation candidate. Marketing/blog hardware and VRAM claims are not our measured throughput. If client product photo not supplied, generated image must not imply a literal authentic product photo. |
| Short generative footage | Wan2.1 T2V-1.3B, https://github.com/Wan-Video/Wan2.1 and https://huggingface.co/Wan-AI/Wan2.1-T2V-1.3B | model Apache-2.0 | Short optional shot-generation engine; published ~8.19GB GPU VRAM at baseline, much more expensive than FFmpeg graphics. Not a universal GPU-free renderer. |
| Music/background scoring | ACE-Step 1.5, https://github.com/ace-step/ACE-Step-1.5 and https://huggingface.co/ACE-Step/Ace-Step1.5 | code/model labeled MIT | Optional GPU music generation; verify specific revision and downstream output/platform permissions. Hosted API terms can differ from self-hosted model terms. Avoid unlicensed reference music. |
| Shot boundary detection | TransNetV2, https://github.com/soCzech/TransNetV2 | inspect installed code AND weights license separately | Preprocessing when user supplied source footage; not a creative decision model. |
| Speech-to-text | whisper.cpp, https://github.com/ggml-org/whisper.cpp | MIT software | Transcript/timing input for editing and QC; model weight provenance separately. |
| Existing selected voices | Supertonic M3/F2, retained voice_lab/ | OpenRAIL-M family; restrictions need review | Preserve approved performance and studio sound; not equivalent to unrestricted OSI-open weights. No voice change without a demonstrated reason. |
| Typed edit/animation/3D | OpenTimelineIO + FFmpeg + Motion Canvas + Blender | check each tool/build; open-source software | OTIO timeline exchange, FFmpeg encode/mix, Motion Canvas directed 2D, Blender purposeful true 3D. These are execution engines, NOT thinking models. |

Key insight: cinema understanding, narrative originality, scene ordering, real video generation, sound and perceptual QA are DIFFERENT capabilities. A single 0.8–3B expert should not be sold as a world-class universal Director. The producing model stays replaceable and must prove its craft in a blind creative competition.

## Free infrastructure verified from official docs

| Resource | Free state as of 20 Oct 2026 | Use in studio | Safety/limits |
|---|---|---|---|
| Public GitHub Actions standard runners | Free standard CPU jobs on public repositories (currently e.g. Ubuntu 4 vCPU, 16GB RAM) | CI, contract checks, controlled short CPU inference, encode/procedural render tests | No dedicated GPU, runner time/disk quotas, no confidential customer briefs in public issue/workflow logs; not an unlimited commercial production farm. https://docs.github.com/en/actions/reference/runners/github-hosted-runners |
| Kaggle Notebooks | Official free P100 GPU, generally quota of 30 hours/week or variable higher; queued availability | Reproducible offline GPU specialist/image/music/video experiments | Notebook sessions are NOT permanent API servers; quota/capacity fluctuates; verify allowed automation and access before linking to consumer UX. https://www.kaggle.com/docs/efficient-gpu-usage |
| Hugging Face ZeroGPU | Free personal account in good standing (verified email, >30 days) may host up to 2 Gradio ZeroGPU Spaces; existing Spaces can be used free | Short interactive PyTorch model tasks/preview services | Shared queue, user quotas, only Gradio-compatible; not general always-on arbitrarily long GPU jobs. https://huggingface.co/docs/hub/spaces-zerogpu |
| HF CPU Basic Spaces | Advertised compute itself at $0/hour but new compute Space creation requires paid plan, except qualified ZeroGPU route | NOT a default zero-cost new server | Must not repeat outdated claim that any free user can create unlimited CPU Spaces. https://huggingface.co/docs/hub/spaces-overview |
| Cloudflare Workers AI | 10,000 Neurons/day free on Workers Free; eligible models only | Optional stronger hosted reasoning/review when budget permits | Custom specialist weights cannot simply be assumed to run; models and billing access vary; no paid-upgrade by automation. https://developers.cloudflare.com/workers-ai/platform/pricing/ |
| Oracle Cloud Always Free A1 | Account eligible pool includes 3,000 OCPU-hours + 18,000 GB-hours monthly (roughly 4 OCPU/24 GB continuously if provisionable) | Candidate long-lived CPU inference/orchestration | A1 capacity, signup/verification, ARM compatibility and idle instance reclaim matter. No guaranteed GPU or no-card signup. https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm |
| Google Colab Free | Free GPU sometimes accessible | Backup human-operated research | GPU access/restrictions/idle life unguaranteed. Not an unattended production server. https://research.google.com/colaboratory/faq.html |
| Modal Starter | $30/month in compute credits | Experimental opt-in ONLY if owner explicitly authorizes billing arrangement and hard spending limits | $0 subscription does not guarantee $0 bill. Exclude from required-zero-expense path by default. https://modal.com/pricing |
| HF Inference Providers Free | Current free tier $0.10 monthly inference credit | Very small inference experiments only | Not suitable as free large-scale studio backend. https://huggingface.co/docs/inference-providers/pricing |

## Decision: coherent adaptable architecture, not a pile of independent demo apps

1. **Chat / owner-controlled facts:** owner input in Hindi or English, rights ledger, purpose and any essential missing question; treat retrieved material as untrusted.
2. **Producer + narrative intelligence:** chooses original story/creative direction from available evidence. Specialist cinematic models are consulted as tools, not required to dictate every shot. Benchmark reasoning models and film-trained candidates blind before selecting.
3. **Adaptive capability planner:** queries model/tool offerings for present *availability, installed code, license, memory/VRAM, cost, account eligibility, privacy permissions, deadline and job quota*. A published model ID is not an installed executable provider. Never choose paid service or leak private media by inference.
4. **Film IR:** explicit shot purpose, continuity, assets/rights, scene duration (chosen by Director), layer/camera/edit tracks, voice/SFX spans and tool graph. No permanent shot count/runtime/style constants.
5. **Real execution:** CPU FFmpeg/2D or Motion Canvas when it artistically fits; Blender for actual 3D; available licensed GPU still/video/audio generator only when resources actually exist. Export real video, not an idealized specification. Unsupported styles block honestly or trigger concept-level reconsideration.
6. **Self-inspection and repair:** decode actual A/V, run measurable timing/loudness/subtitle tests, use Q-ReAlign/ShotVL when actually available, attach evidence to precise shots, selectively re-render failed portions, seek human subjective acceptance separately.

This retains all the stages in docs/MASTER_PLAN.md. It neither imposes fixed creative limits nor promises a model/server that is not installed. Route by **real capability and current resource offers**, not by fixed provider priority. Keep a resumable hash-verified artifact per stage, fail closed on quotas and unlicensed dependencies.

## Immediate owned execution sequence and evidence gates

- **E0:** Preserve all previous artifacts, original repo branches, voice baselines. Never overwrite failed runs to appear successful. Verify user-visible sources before reuse.
- **E1:** Add a *read-only* model/compute capability probe with typed offerings, machine-checkable licenses and eligibility flags, and tests that block (a) no GPU, (b) quota exhausted, (c) paid cost without explicit authorization, (d) unlicensed weights/asset, (e) private input on public host, (f) uninstalled tool. Never auto-create accounts or enable billing.
- **E2:** Build a reproducible specialized benchmark: identical owner-grounded footage and prompts; ShotVL cinematography interpretation vs general VLM; Q-ReAlign measured quality; FLUX.2 Klein and Wan2.1 on GPU when free compute is actually available. Retain pinned hashes, actual VRAM/time and *failed* samples.
- **E3:** Compare creative plans across unrelated ads and educational/stories, blind to model names; evaluate natural story causal link, novelty, truth, specific visual direction and executability. No self-reported winner.
- **E4:** Connect **one** creative treatment from normal user dialogue to installed Film IR => real short MP4. Use limited external GPU only for shots requiring it, preserving alternatives instead of silently downgrading ambitious plans.
- **E5:** Visual/audio preview analysis, defect-location and selective revision, cost/latency logging, human acceptance; only then branch promotion and broader genres.

### Non-achievements

As of this addendum: no Kaggle/ZeroGPU/Oracle/Cloudflare compute was provisioned by this research; no specialist weights were downloaded into ZX7; no new rendered MP4 or creative-quality pass was obtained. Current outputs are verified repository state, official external resource research, and a proposed controlled integration route.

**Master decision:** prioritize creative narrative quality *and* executable visual depth together; do not replace real studio engineering with either a large generic LLM or claims of free unlimited GPU. All experimental capability claims require output proof before main-branch integration.
