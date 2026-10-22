# ZX7 Studio — Production BODY Capability Contract & Independent Review
**Review date:** 22 October 2026
**Source of truth:** \`oyzitjfzj/Ad\` branch \`zx7-body/mobile-operator-20261021\` (draft PR #3, base \`zx7-specialist-free-stack-20261020\`).
**Product claim:** not production-complete. Engineering verification and creative skill are different axes.

## 0. What the product actually is

A **general-purpose autonomous, professional film production environment** capable of accepting independently conceived visual/narrative decisions from a future creative intelligence and converting them to editable, legally traceable, verifiable original audiovisual artifacts. It should make an elite artist *able to work*, not replace creative judgment with one giant list of templates. The BODY is the controllable apparatus: timeline, media rights, all coordinate/time/color systems, renderer/compositor/audio editors, source-generative adaptors only when actually installed, measured feedback and recovery, an orchestration graph, and a secure owner review/edit/control plane.

At "world's best editor" level, required OUTPUT is not a fixed quality number or the mere ability to render one pretty MP4. The BODY must provide enough expressive freedom for excellent human or AI decisions to be implemented; independent creative evaluation across multiple projects is still required. Every inferred narrative/semantic attribute must be reviewed against actual visuals, audio and human taste; a diagnostic statistic is not a quality grade.

## 1. Architectural laws

1. **Director owns originality.** The BODY cannot hardcode shots, transitions, aspect ratios, logo placement, color palette, scene count, language, narration, camera style or the content of an unfinished film. The actor/script/musical choices, including old approved voices, are independent inputs, never substituted.
2. **Media is physical, rights-attested and content-addressed.** Do not treat an LLM-supplied filename, caption, prompt, stock URL or manifest as proof of an original licensed asset. A source identity includes SHA256 of actual immutable bytes, exact custody attestation and stable logical asset URI.
3. **Tools are typed, physically checked and discoverable.** Models select a capability through a narrow registry. Model-supplied shell commands, plugin Python scripts, payment decisions and unbounded remote network credentials never become trusted.
4. **Time is exact; edits are reversible.** Use frame/sample rational clocks and domain-specific film IR. Preserve original sources and previous approved outputs. Modified nodes invalidate only their proven descendants; asset changes are measured again at commit time.
5. **Space and color are explicit.** Screenspace, 3D camera/world units, image alpha/premultiplication, scene-linear/HDR/display-referred colorspaces and original sound sample rate must not be collapsed into "make it cinematic" strings. Detect and report unsupported color transforms, never fake them.
6. **Evidence before claims.** An installed executable/codec/EXR/ML model is available only with a live installed tool and physically decoded output proving the relevant properties. A formal registration is not a working adapter, and a paper is not installed weights.
7. **Execution respects finite hosts.** Record CPU, RAM, VRAM, scratch-disk and lease budgets. Work with interrupted jobs and exact per-frame/per-clip checkpoints. The owner is on Android but the render may be remote; mobile UI is not a phone GPU.
8. **Review drives iterative improvement.** For each attempt: technical receipts → sampled/whole-media observations → creative/semantic review → explicit actionable edited decisions → reproducible partial rerender → external/artistic comparison, without accidental unrelated source replacement.
9. **Architecture is plugin-compatible, not a pile of plugins.** Optional adapters declare availability, output interchange, constraints, source security and failure semantics. No paid dependency, public tunnel, models/weights, cloud GPU, or domain purchase without owner action.
10. **Only separately measured global acceptance permits RELEASE-COMPLETE.** Code coverage or 400+ tests of limited features cannot certify elite creative filmmaking.

## 2. Twelve required BODY subsystems, dependency and evidence

|Subsystem|Must actually do|Concrete release gate|Last independently seen|
|---|---|---|---|
|A. Governance and factual source|Exact original brief, edit/rights decisions, source versioning, capability permissions|Reject forged rights, preserve source on failure and cross-host import|Physical MediaVault and rights tests green|
|B. Film/project interchange|Versioned film IR and open editable timelines, sound/multi-track references, explicit loss report|OTIO roundtrip of mixed movie/timeline with original timings and audio; no silent effect loss|OTIO link migration tested; other formats partial|
|C. Exact editorial engine|Cut, ripple, trim, slip, slide, trim linked audio, multitrack, retime ramps, fine keyframes|Frame/sample-accurate natively decoded regression on unrelated edit kinds, previous originals intact|Basic timeline/retime and selective revision graph verified; not full NLE breadth|
|D. Scene compositor|2D/2.5D, alpha/channel order, expressions/keyframes, tracking, roto, masks, shadows, camera movement, physically correct overlay|Real media pixels composited under native decoder; alpha/edge tests, occlusion/temporal QA|FFmpeg chroma key, compositing and independent motion/3D engines partial|
|E. 3D/VFX|Licensed mesh, material, camera, lighting/physics, depth/vector/normal, multi-pass EXR, dynamic range|Render+decode artist-authored multi-frame 32f EXR + alpha/Z/normals/vectors, resumption after fatal failure|Blender Cycles CPU pass+per-frame recovery green at previous head|
|F. Color science|Explicit scene and display space, OCIO transforms with pinned config, true working-space conversion, EXR and graded SDR/HDR masters|Pixel numeric comparison to trusted reference; full workflow EXR→OCIO→compositor→delivery and VUI|Explicit SDR BT.709 3D LUT and scene-linear Blender EXR; no certified ACES/OCIO|
|G. Audio/music/voices|Independent original audio tracks, dialogue, expressive authorized voice, placement/time stretch, sample accurate sync, mastering, captions|Physical entire track decode; LUFS/peak, stem audit, sync/time drift; voice choice preserved|Audio mix, original sound, atempo and volumedetect verified; advanced mastering partial|
|H. Source generation|Original shots, objects, textures, realistic performances when permitted by real GPU models, copyright/rights custody|Real installed weights/license/hardware and genuine output continuity on varied prompts|CUDA/movie model absent/unknown; block, never claim free unlimited AI footage|
|I. Orchestration and safety|Typed source/capability plan, costs, per-asset rights, exact input revisions, durable DAG, cancellation and graph invalidation|Simulated and real kill, simultaneous owner, frame level resume, replay refusal, selective rerender|Local SQLite stage ownership and original per-frame Blender EXR now measured|
|J. Perceptual feedback and critique|Actual accessible review frames, soundtrack windows, visual/motion/loudness evidence, model/human comparison, grounded repair plan|No hallucinated images; director can inspect real pixel/clip evidence and decide edit; do not label dark/still intentional scene as broken|Full-decode and limited frame QA existed; new portable sampled frame+sound review tool in testing|
|K. Owner UX and hosting|Android owner control for brief, upload, preview, revision, download, budgets, approval, HTTPS and backup|Actual off-LAN Android handshake, owner-authenticated HTTPS, safe media, persistent compute+recovery|Real local Chromium phone-size UI; persistent external host and HTTPS not deployed|
|L. Audience/release evaluation|Independent human reviewer across diverse original project types, metadata/provenance, market-ready deliverables|Multi-genre films with editor review, storytelling/visual/audio judgement and measurable production repeatability|Not certified, no elite editor claim|

## 3. Critical path for independent implementation
These are **logical dependency gates**, not an unbounded to-do list or instructions to the creative AI.

**Stage P0 — repository and user truth.** Inspect actual repo tree, head commit, CI and docs. Preserve original media, voice preferences, active branch and unfinished film material. Adopt the current G0-G8 plan as a correctness constraint, not as a model prompt.

**Stage P1 — reliable production runtime.** Continue source license attestations, stable logical media URI, original source fingerprinting, irreversible publication refusal, cache/revision dependency closure, process leases and audited on-disk resumable frame checkpoints. Current progress is meaningful but host-local.

**Stage P2 — expressive operation graph.** Generalize keyframe/time/space/color/mask/audio coordinate systems and typed transformations. Provide genuine NLE multi-track editing and VFX graph primitives with reversible versions and independent editors. Do not create style templates to imitate intelligence.

**Stage P3 — proper color/VFX interoperability.** Pin compatible OCIO/ACES configs and build color-managed scene-linear 3D/EXR→2D alpha→display pass with measured pixel differences, mastering formats, explicit gamut/view and no silently converted HDR/log into SDR.

**Stage P4 — audiovisual observation and creative revision.** Expose portable, verified real frames, motion/difference observations and soundtrack levels for one edit revision. Then layer grounded multimodal comparison against artist goals and source footage. Objective observations are not semantic understanding; such a brain must actually run on available hardware before further claims.

**Stage P5 — source/model extensibility.** Only integrate working, license-cleared open video generators on genuinely available host GPUs with frame-level output measurements. No hallucinated actors from test patterns, no chargeable cloud assumptions.

**Stage P6 — distributed/failure scale.** Real worker identities, assignment, resource leases, frame manifests, cross-host proof-bound transfers, partial result reuse with absolute-path translation. Host-only fcntl locks are not distributed synchronization. Test source race, disk full, interrupted upload, worker crash, GPU allocation failure.

**Stage P7 — secure remote Android workflow.** Actual owner identity + HTTPS on a persistent authorized machine, narrow upload/download permissions, review previews and asynchronous external control. Cloudflare edge routing alone does not supply a permanent renderer; no public anonymous tunnel.

**Stage P8 — creative acceptance.** Test diverse original advertisements, explanatory shorts, narrative films, multi-layer real footage, 3D and mixed audio with independent human/editor reviewers. Revise against real media and report quality honestly.

## 4. Live capability truth tests

For EVERY registered tool:
- Declarations only after on-host runtime availability probe.
- Typed parameter schema, allowed access, original custody requirements, hardware limits, expected source and output colorspace/audio/time formats.
- Native physical proof for actual supported inputs, not only mocked unit tests.
- Negative case for wrong rights, damaged/corrupted source, path traversal, changed source during render and interruption.
- Actual encoded frame/audio decode and output SHA+size/revision fingerprint.
- Cache reuse proof and interrupted job recovery where repeatable.
- Evidence and logs with a user-readable artifact; false technical claim fails release.
- No creative-approval or paid provider authority inferred.

## 5. Cost, mobile and honesty

The owner currently controls work by phone and expects genuinely zero-budget/free tooling. Select physically CPU-viable proof jobs in the free GitHub CI and keep reviewer artifacts small. GitHub Actions is a temporary testing environment, not a guaranteed 24x7 render service. A remote GPU, hostname, persistent disk, model weight license or model studio availability must be actually provided/authorized. Where missing, report a genuine blocker rather than offering a fake button.

## 6. Independent sources and method
Official OpenTimelineIO: https://opentimelineio.readthedocs.io/en/latest/
ASWF OpenColorIO: https://opencolorio.org/
ASWF OpenEXR: https://openexr.com/
ASWF OpenCue: https://github.com/AcademySoftwareFoundation/OpenCue
OpenFX: https://github.com/AcademySoftwareFoundation/openfx
GStreamer Editing Services: https://gstreamer.freedesktop.org/documentation/gst-editing-services/
MLT: https://www.mltframework.org/
FFmpeg filters/ffprobe: https://ffmpeg.org/ffmpeg-filters.html ; https://ffmpeg.org/ffprobe.html
Research directions: Crayotter traceable heterogeneous long-video editing; DIRECT hierarchical intent-guided editing; LumiVideo color-grade analysis; UniVA tool-use and video task integration. **Papers are evidence of technical directions, not proof of local verified model capability.**

## 7. Status disclaimer
This document is an independently maintained engineering plan, not a complete app, certified editor or creative model. Exact current technical test results must come from the matching GitHub Actions commit after relevant code changes. Never backdate success from a previous green run. Do not merge draft PR #3 into main until exit criteria satisfy the owner and are independently evidenced.


## 8. Measured BODY progress on 22 October 2026 — actual footage observations

**New, physically tested**: original rights-attested movie → entire native picture/sound decode → artist-selected original 8-bit RGB review PNG frames → bounded chosen audio-window dBFS evidence → SHA256-bound portable .zxreview archive with exact source ownership identity. The complete archive is independently re-opened and each PNG is losslessly decoded and its exact bytes, timestamps, frame shapes and sample provenance rechecked. A movie's black/still/quiet interval is never marked aesthetically bad by this tool. Source inspection rejects changed bytes, forged media custody, invalid timecode, malformed audio level and altered archived PNG.

**Readback operation**: BODY exposes verified review metadata to a future director/vision model and independently extracts a single exact decoded source PNG at an authorized original timecode, with permissions and cache-input fingerprints.

**Revision comparison**: BODY computes true 8-bit RGB pixel differences only between matched timecodes from two independently verified original movie reviews, plus original audio-window mean/peak levels at exactly matching intervals; it records all unmatched timecodes without inventing optical flow/semantic similarity or rearranging original shots. It returns measured differences, not claims of "better story" or creative approval.

**Native evidence at code commit 9005b8c6a2ab7f88fdc4d9dc5cd50e8d14bd6abe**:
- https://github.com/oyzitjfzj/Ad/actions/runs/39755064211
- 426 native tests completed (425 success, one separate Chromium browser test skipped in this runner); real picture/sound, licensed review PNGs, original audio volume measurements, changed blue-vs-red movie pixels, version readback and archive-tampering refusal independently passed.
- https://github.com/oyzitjfzj/Ad/actions/runs/39755064211/artifacts/12415771381 has actual original reviewed MP4, three independently decoded PNGs and the review artifact alongside older Blender/VFX, color grade and professional timeline proofs.
- https://github.com/oyzitjfzj/Ad/actions/runs/39755051067 verified separate security contracts on this engineering series.
- The actual phone-size Chromium acceptance suite is independent from the native-decode suite. Never cite a local Chromium pass as external production Android HTTPS operation.

**Still missing**: proven multimodal artistic interpretation and semantic continuity, editable mask/advanced tracking/optical flow, OCIO/ACES color-space pinning across real input formats, cross-host worker farm, actual free licensed generative cinematic actors, off-device secure persistent Android access, and independently judged narrative/ad/story creative quality. Zero G0-G8 global-complete certification.
