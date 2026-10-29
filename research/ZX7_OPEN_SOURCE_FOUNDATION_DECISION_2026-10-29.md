# ZX7 BODY — source-grounded architecture selection and research gate (2026-10-29)

Status: RESEARCH / ARCHITECTURE DECISION; no engine implementation or artistic acceptance performed. Isolated research branch from main 7f814126d433a7b1f9df022819cbaaa770c6b663. No changes to main. No proof of world-best capability. Prefer actual source, license and test results over promotion. This is a design checkpoint, not a certificate of completeness.

## 1. Recovered owner intent and nonnegotiable constraints

Build a universal AI-operated *creative body*, controlled by a replaceable external model/brain. The brain exercises original research, planning, creativity, direct technical control, observation, listening, error correction and revision. BODY delivers profound existing creative affordances — video NLE, graphics, typography, animation, 3D, VFX, simulation, color, sound, generative media, native assets — without being a hardcoded style engine, constrained template, fixed prompt chain or one renderer. A user can provide existing footage plus a reference and request a professional edited ad/film; model should independently choose the best media, craft and tool route, then genuinely produce, inspect and revise a legal, high-quality deliverable. Low cost, transparent open source, privacy, reliability, model interchangeability, portability and artistic excellence all matter. Beyond-best is a research target, never a claim without head-to-head evidence.

Important distinction: mouse/GUI imitation was an analogy, NOT a requirement. The model can program native APIs, author code-driven graphics, manipulate structured projects, invoke legitimate tools or use authorized GUI controls. Generated creative code is an optional powerful pathway, not a forced practice for every job. Native host capability and creative decision-making should not be confused. Keep project state independently editable and versioned.

Owner earlier required one field fully complete before another. Respect depth, but dependencies A/B/F/G/I/J connect to video field C; prove *whole working vertical slices* (including assets, editor, render, audio, visual quality, recovery) rather than declaring isolated modules finished.

Sources of intent: README.md, AGENTS.md, CAPABILITIES.md, TEMP_ZX7_BODY_NEXT_CHAT_HANDOFF.md at main and historic owner conversations. Existing handoff is read, not deleted by this research-only branch; do not corrupt other concurrent engineering work.

## 2. Live ZX7 status reviewed

- Main at 7f814126d433a7b1f9df022819cbaaa770c6b663, MIT license.
- Existing body_integration.py tools cover MLT, FFmpeg, Blender, 2D, compositing, provenance, review, audio, color and generators; discovered operations are not all installed backends.
- body_motion_project.py provides native Blender RNA path discovery, read/set and keyframe_insert via safe restricted operations, sealed .zxmotion native bundles. It must be physically evaluated with *real character armatures* before judging rig-control quality. The simpler body.blender3d generated humanoid shot is not equivalent to exercising this full native interface.
- body_creative_session.py and body_service.py provide bounded model-to-tool sessions and persisted job receipts. Tests with scripted models are not proof of a real model autonomously directing a professional film. Still-image visual observations do not establish full temporal/audio semantic judgment.
- CAPABILITIES.md explicitly states no complete A–L field has attained professional technical/human acceptance.
- Four existing draft PRs (#46–49) address source-owned grade, empty upper picture tracks, retimed audio coverage, unique-media source verification. Preserve their branches and integration history. Zero destructive main rewrite.

## 3. Primary source audit (GitHub source and official docs, 2026-10-29)

| Project | License of top-level code | Read in actual sources | ZX7 disposition | Caveat |
| --- | --- | --- | --- | --- |
| heygen-com/hyperframes | Apache-2.0 | packages/core/README.md, packages/engine/README.md, packages/producer/README.md, repository root and files. Core parses compositions and timing, frame adapter seek contract; Engine uses Puppeteer/Chrome CDP BeginFrame + FFmpeg; Producer adds frame workers, chunk/stream captures, audio and output packaging. | **SELECT** as first *browser/motion graphics execution backend*; make integration optional and isolated. | Not a substitute for native character rig/simulation, offline source edits or NLE. HTML/JS can contain malicious code, external CSS/network fetches, font/media differences. Other dependencies/licenses separate. |
| openfilm/openfilm | MIT | README, LICENSE, root/monorepo. film.html multi-track and deterministic frame(t) browser drawing, agent-editable source, Studio manual editing, rendered look/contact sheets, documented export. | **BENCHMARK** against HyperFrames on exact creative briefs; consider selective reuse/interchange if it outperforms. | Duplicates much browser rendering surface; do not integrate two entire equivalent engines prematurely. Agent flow and production reliability not independently validated. |
| motion-canvas/motion-canvas | MIT | README, LICENSE. TypeScript generator-based motion library, 2D drawing and real-time editor, FFmpeg exporter. | **RESERVE** specialist for 2D explanatory/vector motion where exact control offers clear benefit. | Specialized animation, not full NLE/3D. |
| bazodev/open-vids | Apache-2.0 | README: HyperFrames-derived desktop AI video editor with Director/Vision/Audio etc, story mode and QA. | **BENCHMARK** AI editing, source handling and revision UX; do not copy entire fork. | Smaller, comparatively new project. QA claims require real failure tests. |
| VelornLabs/velorn | GPL-3.0 | README and docs/MCP.md: open workstation, 100+ MCP editorial tools and ComfyUI generation via local server. | **BENCHMARK** scope and agent edit surface; optional external process under legal review. | GPL obligations; do not copy components into ZX7 MIT code without rights/packaging analysis. Model generation requires separately installed backend and may incur cost. |
| mltframework/mlt | LGPL-2.1 family (inspect actual distributed components) | Source metadata, ZX7 existing native MLT adapters, project roundtrip and controls. | **SELECT / RETAIN** for native multitrack NLE and media edit operations. | Effects may be nonportable; precise test of composition, audio, color and transforms. License depends on linked components. |
| Blender/blender | GPL-family; official source mirror | Blender open RNA interface; ZX7 already has transactional adapter. | **SELECT / RETAIN** for native 3D, rig, character performance, CGI, VFX and simulation. | Sandbox/project attacks and headless CPU/GPU need real checks. Integrate as separately managed native application; respect GPL obligations. |
| AcademySoftwareFoundation/OpenTimelineIO | Apache-2.0 | Primary GitHub project description and repository. | **SELECT** for editorial interchange only, with explicit loss reports. | OTIO does not render or preserve every engine-specific effect. Native source bundles remain authoritative. |
| AcademySoftwareFoundation/OpenColorIO | BSD-3-Clause | Primary repo and existing ZX7 color paths. | **SELECT** color transform plumbing with pinned config and correctness tests. | ACES/OCIO setting alone does not certify color fidelity. |
| AcademySoftwareFoundation/OpenEXR | BSD-3-Clause | Primary repo. | **SELECT** scene-linear float passes and VFX interchange. | Verify metadata, alpha and color spaces. |
| AcademySoftwareFoundation/OpenImageIO | Apache-2.0 | Primary repo. | **SELECT** high-quality asset/image operation backend when proven necessary. | Avoid duplicating FFmpeg/Blender functionality. |
| NatronGitHub/Natron | GPL-2.0 | Primary repo, node-based compositing, OFX. | **DEFER/BENCHMARK** for specialized node VFX. | GPL packaging and current headless stability must be tested. Not prerequisite to initial vertical slice. |
| Comfy-Org/ComfyUI | GPL-3.0 | Primary repo, locally controlled model graphs and backend API. | **SELECT OPTIONAL EXTERNAL BACKEND** for image/video generation, not a creative-core dependency. | Weights, custom nodes, GPUs, data rights and generation quality independently verified. |
| Wan-Video/Wan2.2 | Apache-2.0 model/code family, check each downloaded checkpoint | Official project and license; A14B reference single GPU requirement is very high (~80GB for unoptimized published route). | **SELECT FOR LICENSE-FIRST GENERATION RESEARCH**, optional backend. | "Free weights" does not mean free GPUs or realtime generation; model variant/context changes hardware needs. |
| resemble-ai/chatterbox | MIT repo | Primary TTS repository. | **AUDIO CANDIDATE** for future independent measured listening tests. | Voice rights, specific weights and output identity approvals still required. |
| hexgrad/kokoro | Apache-2.0 repo | Primary project. | **AUDIO CANDIDATE** for small offline TTS. | Repo license is not proof of legality of all voices/fonts/weights. |
| remotion-dev/remotion | Source-available, NOT OSI open-source | Official docs/license FAQ. | **REFERENCE/COMPARISON**, not freely integrated core. | Free allowance for small teams is not general public-product unrestricted licensing. |
| olive-editor/olive | GPL-3.0 | Public repo metadata last pushed 2024-12-05. | **DO NOT CHOOSE** over active MLT without modern proof. | Older activity is not proof of no functionality; insufficient reason to fork. |

Primary source links:
- https://github.com/heygen-com/hyperframes/tree/main/packages/{core,engine,producer} and https://github.com/heygen-com/hyperframes/blob/main/LICENSE
- https://github.com/openfilm/openfilm ; https://github.com/motion-canvas/motion-canvas
- https://github.com/bazodev/open-vids ; https://github.com/VelornLabs/velorn ; https://github.com/VelornLabs/velorn/blob/main/docs/MCP.md
- https://github.com/mltframework/mlt ; https://github.com/blender/blender ; https://github.com/KDE/kdenlive
- https://github.com/AcademySoftwareFoundation/OpenTimelineIO ; https://github.com/AcademySoftwareFoundation/OpenColorIO ; https://github.com/AcademySoftwareFoundation/OpenImageIO ; https://github.com/AcademySoftwareFoundation/openexr
- https://github.com/NatronGitHub/Natron ; https://github.com/Comfy-Org/ComfyUI ; https://github.com/Wan-Video/Wan2.2
- https://github.com/resemble-ai/chatterbox ; https://github.com/hexgrad/kokoro
- https://www.remotion.dev/docs/license/faq

## 4. Architecture decision A (pending trial signoff)

A replaceable creative brain talks to a permissioned capability discovery/observation/revision interface, not directly to unrestricted host OS. BODY retains native original project + legal provenance + exact rational picture/audio timeline + renderer-specific native documents (loss-aware); it does not reduce all media to uneditable MP4.

Two complementary tool surfaces:
1. Native structured operations: MLT NLE, FFmpeg, Blender RNA and editorial interchange. The model can discover and set original effects, curves, geometry, materials, actors, audio, frame timings and versions at professional native granularity.
2. Secure original creative-code execution: typed declarations and brokered program execution for HyperFrames HTML/CSS/JS/GSAP/Three/shaders and other vetted engines, enabling arbitrary new visual techniques when existing structured ops do not suffice. Never treat generated code as privileged. No arbitrary code in ZX7 trusted host process, secret store, or native plugin expressions.

Execution plan: source ledger and owner brief -> model-generated multimodal creative strategy -> graph of target native/HTML scene operations -> sandboxed renders with isolated CPU/memory/disk/network policy -> inspect actual frames, audio, project state and visual semantics -> targeted graph revision without overwriting originals -> quality/licensing/perf check -> export both editable project and deliverables. Brain may choose any format/genre/pacing/shot count/voice/style; engine contracts are technical, not aesthetic presets.

Minimum shared contracts:
- immutable assets with SHA-256, original and derivative identity, rights and expiry/revocation checks;
- precise fps rational, sample clock, source/sequence timebase, track order and overlap;
- explicit primaries, transfer function, alpha interpretation, scene/display color transforms;
- native effect/curve parameters preserved in native representation, import/export loss map and version history;
- project graph with revision dependencies, partial invalidation, cached outputs and measured cost;
- structured observations including actual sampled media and full-video temporal/audio inspection;
- secure untrusted input checks, network isolation, path confinement, process resource quotas, dependency lockfiles, permissioned provider spending and deterministic receipts;
- reproducible codec, fonts, GPU/CPU and engine versions, fast previews and durable resume.

Critical design opposition: do NOT replace all of ZX7 with HyperFrames (limited for 3D/NLE); do NOT copy GPL code into MIT library blindly; do NOT emulate premium applications by mouse clicks as the primary method; do NOT let AI code arbitrarily run on host; do NOT pretend that rich tool control automatically makes a model a genius editor; do NOT hard-code creative workflows. Performance, physical quality and model judgment require independent evidence.

## 5. Before coding — hard experiments still required

This initial primary-source audit is NOT a runtime comparison. Before final integration implementation, run these reproducible probes on representative available hardware with legal shared assets:

P1. Identical original 12–20 s motion-heavy ad brief: HyperFrames vs OpenFilm vs Motion Canvas vs baseline ZX7. Need frame-by-frame correctness, motion and layout quality, actual frame rate, audio sync, native editability, rerender on revision, end-to-end times, memory/CPU, reproducibility and p95 render time; no artificial advantage due to hand-crafted example.

P2. Real client's provided mixed FPS and multi-track footage: existing ZX7 MLT vs Kdenlive/MLT reference; physically check cuts, sound clock, grade, subtitles, masks, speed ramps, import/export and roundtrip. Protect owner media from public repo and external services.

P3. Rigged humanoid Blender .blend character performance controlled through existing body.motion_project RNA, not simple spherical primitive scene. Verify bone curves, poses, expressions, camera, correct frames and one independent revision; use legally usable rig.

P4. Bad-input/failure/cost threat models: untrusted HTML scripting, CSS URL, malicious asset path, external host network egress, DDoS frame sizes, arbitrary dependency download, resource exhaustion, native blend external references, model source-rights hallucination, canceled task/restart, lost cache, stale artifacts.

P5. Multimodal quality: actual model receives reference footage and original source, independently directs/executes/revises meaningful video, compares rendered temporal quality and listens to sound, receives blind evaluation against skilled human-produced references in multiple genres.

P6. Platform portability/license: Linux first + optional Windows/macOS, CPU and real GPU, cold-start cache, native project relocation. Verify every transitive dependency license, codecs, model weights, voices, fonts, stock media, Pexels permissions and plugin boundaries.

Success criteria are comparative: design originality, fidelity, editability, sound, reliable revision, security, legal reuse, latency, cost per usable second and failure recovery. No cross-field or beyond-best claim without these.

## 6. Proposed implementation order AFTER P1–P3

1. Preserve main, existing PR branches, original source and tests. Research branch is isolated. Do not delete any code/history just to get a clean visual tree.
2. Build a minimal adapter proving native content from existing ZX7 can coexist with HyperFrames composition under one versioned project/asset graph. Honor security and exact time/color. No general product rewrite.
3. Verify real separate AI model can discover both native and creative-code routes, choose source/format/genre freely, inspect and revise; no assistant-authored fixed scene output masquerading as autonomy.
4. Close NLE end-to-end field C + connected A/B/F/G/I/J gates, including real creative/quality evaluation.
5. Expand through evidence-led new capabilities (3D, VFX, audio, generative media, design) and exploit native whole engines rather than writing weak substitutes.

## 7. Honest unresolved facts / blockers

- No live apples-to-apples rendering tests performed in this research record. Source-level feature and repo metadata checks are not proof of performance or artistic quality.
- The zero-cost requirement includes cloud compute; generative weights may be free while GPU time is not. Resource budget requires user hardware evidence.
- GPL/LGPL/API/proprietary licenses need transitive dependency and distribution-boundary review before a public ZX7 release. This is engineering guidance, not formal legal opinion.
- Runtime support and model weights in any host are not established by repository existence.
- Additional external research app Firecrawl was connected but out of credits as of this audit; public web research and connected GitHub repo source still worked. The app itself is not a production runtime requirement.
- Research/design support plugin suggestions: Context7 (current API docs), Superpowers (engineering process), tldraw (diagrams); none is essential, free usage/connection not assumed.
- This document is the **selected initial architecture plus explicit benchmark gates**, not an authorization to deploy unreviewed code or to delete established work.

Owner-facing summary: Retain ZX7's strong foundations. Add a first-class, safe code-driven visual backend where genuinely useful. Use mature professional engines behind a discoverable coherent BODY. Prove the combined system on real creative tasks before coding a wholesale replacement.
