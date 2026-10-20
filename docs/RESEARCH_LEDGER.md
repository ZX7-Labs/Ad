# Two-Track Research Ledger (2026-10-20)
This document distinguishes demonstrated capabilities from aspirational claims. It is NOT a ranking of model creativity. We have not trained or benchmarked a new domain-specific language model.

## Track A — creative intelligence (screenwriting, filmmaking, editing decision-making)

| Candidate | Category & verified basis | What we can actually use | Open issues / decision |
|---|---|---|---|
| [CineCrew](https://github.com/Ironieser/CineCrew) | ECCV 2026 narrative-to-film orchestration via FilmDSL, shared shot/camera/asset/continuity spec; source repo openly available | Structured studio intermediate representation, continuity and targeted repairs | This is NOT a tiny film-trained LLM or universal renderer. Real video generator backends still required. Reference architecture, not drop-in brain. |
| [VideoAgent](https://github.com/HKUDS/VideoAgent) | EMNLP 2026 editing/understanding/remaking; >30 specialized editing agents; MIT project source | Intent-based multi-tool routing, editors as discoverable capabilities and evaluations | Project docs call for GPU memory ~8GB; model services and multiple weights. **Not fully free lightweight standalone model.** |
| [FilmAgent](https://arxiv.org/abs/2501.12909) | 2025 director/writer/cinematographer roles in virtual 3D; evaluated on 15 ideas and reported human preference | Task separation + critique-correct-verify | Narrow virtual environments, limited sample benchmark and resource assumptions. Does not prove general genre coverage. |
| [MovieAgent](https://arxiv.org/abs/2503.07314) | 2025 hierarchical story/scenes/shot planning | Long-form and consistency planning patterns | Needs asset/reference banks and heavy external video models. |
| [Director Skills](https://github.com/0xhughs/director-skills) | Modular cinematic prompts/skills | A skill library to supplement visual literacy and story craft | NOT a trained model; third-party skills are untrusted until reviewed. Do not auto-install or execute. |
| [GPT2 Small screenplay fine-tune](https://huggingface.co/raghavnimbalkar/gpt2-screenplay-generator) | 124M screenplay-oriented fine-tuned generative model, user-contributed model card | Evidence that small domain training is possible | Not validated on high-end advertising/storytelling; license and screenplay corpus rights unresolved; not a production selection. |
| Local Qwen3/3.5 experiments | Model providers, general-purpose LLMs used for direction | Cheap starting brain for measurable experiments | Original first drafts generic; Qwen3.5 CPU tests slow; Q4 4B/9B not proven premium script models. Keep behind replaceable provider interface. |

**Research conclusion:** As of 2026-10-20, no verified small, self-contained *creativity-only* film/directing model that guarantees world-class scripts, image judgment, editing decisions and CPU-speed production was established. Better outcomes likely require task-specific training **plus** genuine film-production tool orchestration, reliable data/assets and rigorous real-output evaluation. Domain expertise != small param count or advertised title.

## Track B — editing/production tools

| Tool | Scope, official source | Role / known constraint |
|---|---|---|
| [Motion Canvas](https://github.com/motion-canvas/motion-canvas) | TypeScript generator-based 2D animations, real-time editor/preview, designed to synchronize informative vector motion to voiceover; MIT source | Candidate procedural motion adapter, NOT a full video NLE or automatic high-quality producer. Needs adapter and benchmark. |
| [OpenTimelineIO](https://github.com/AcademySoftwareFoundation/OpenTimelineIO) | ASWF open interchange and editorial cut information; Apache-2.0 | Canonical timeline exchange (clips/tracks/transitions/metadata); **no video/audio data embedded**, not a render engine. |
| [FFmpeg](https://ffmpeg.org/) | Cross-platform audio/video encoding, filtering and muxing | Installed legacy baseline, use reviewed argv plans, not raw shell strings. Per-library licensing must be checked based on build. |
| [Blender](https://www.blender.org/) | Authoring/rendering 3D characters/objects/lights/camera/animation | Adapter for *actual* 3D; headless compute is heavy, no unverified 24/7 free GPU promise. |
| Existing motion_studio compositor | Our own data-driven Pillow/NumPy/FFmpeg 2D/2.5D project | Retain as baseline and low-cost fallback. Does not execute arbitrary natural-language instructions. |
| M3 / F2 Supertonic v3 | Previously approved original male and female voices, CPU-oriented | Keep voice profiles; weights BigScience OpenRAIL-M, not unconditional OSI open-source. Plugin must validate terms at distribution. |
| Generative image/video models | Provider-specific weights, often GPU-bound | Future opt-in GPU or remote adapter; check provenance, license, prompts, costs, availability and output rights. Not currently installed. |

## Research questions still open
- Find credible film/ad-specialized small LLM checkpoints *with documented licensed training data*, not just 'screenplay' in model title.
- Benchmark creative writing with identical briefs: product ad, explanatory Short, 2–5 minute narrative, educational long-form, multilingual.
- Evaluate naturalness with blind human pairwise comparisons and notes about clarity, originality, accurate claims, aesthetic decisions, retention—not self-reported numerical grade alone.
- Determine the lowest-cost true image/video-understanding critic (consider sampled frames and local OCR/ASR selectively, protect personal media).
- Derive a model-agnostic \`Studio IR\` that can compile to OTIO, Motion Canvas, existing compositor, Blender or optional generative video tools without forcing impossible rendering promises.
- Test plugins against licensing and resource/cost envelopes. Defer 'automatic install every possible engine' until security sandbox and consent exists.
- Compare AI-directed visuals with *rendered* previews, not only JSON plans or scripted demonstrations.

## Decision policy
Every new capability has: source repo/model ID, model-weight+software license, version, installed status, input/output contract, declared cost+hardware, security risk and independently verified output sample. *Proposed* tools remain unavailable until installed and tested. Never silently tell the creative model a proposed tool is executable.
