# ZX7 Studio — BODY Production-Grade Definition and Complete Acceptance Plan
Review date 22 October 2026. Engineering architecture document, NOT an LLM creative prompt. Branch zx7-body/mobile-operator-20261021. No modifications to Brain, scripts, voices M3/F2, original film briefs or main.

## Fundamental decision
The product is an autonomous, fully expressive audiovisual **production operating environment**. The future creative intelligence can decide any style/genre/length/technique and obtain verifiable tools to construct, observe and revise genuine images, video, motion, effects, 3D, film audio and timelines. The user's analogies about expert editing and manual tools are examples, never an instruction to hard-code a manual human-editing workflow or a certain visual look.

A production-grade body is not a count of tools/tests or a playable 3D sample. Technical release requires original verified sources, an expressive non-destructive project model, professional scene/audio/color operations, actual creative tool discovery, reliable rendered-media evidence, persistent scheduling and backups, secure phone interaction, independent audiovisual feedback, and demonstrated diverse quality. All requirements coexist. Do not force a generic lower-quality style to hide missing tools.

## Authoritative system boundaries
- Creative Brain owns original narrative, aesthetics, editorial/camera/VFX intent and changes. BODY validates technical permissions, provenance, time/space/color and physically operates instruments, never chooses style.
- Owner facts and rights are immutable. External imported/created model, image, footage, voice, music, font or LUT requires actual SHA256 source custody and relevant legal license. A model assertion does not establish rights.
- Film/project IR owns editable scenes/shots, exact rational timebase, tracks, effects, masks, geometry, sound buses, color spaces, original source references and version history. OpenTimelineIO is interoperable edit data, not a whole renderer; OpenUSD is future CG interchange, not a model of cinematic thought.
- Installed tool ABI provides concise typed schema, executable/library+weight hashes, actual hardware, permission and cost scope, and a genuinely decodable media-output proof. Do not feed broad handbooks into model context.
- Source media and creative revisions are content-addressed. Rendering is a dependency graph: original asset SHA, relevant shot facts, tool revision, color/sound inputs and upstream actual output receipts key a stage. A change only invalidates its real descendants. Recheck sources after long render before accepting output.
- Editor operations are not preset videos: exact trims/splits/slip/slide, keyframe/curve/retime and source audio, reversible overlapping layers, compositing matte, planar/optical tracking, typography, physical 3D camera, light, simulation and full VFX passes must be independent technical instruments.
- Color is scientific, not a gamma slider. Display-referred BT709 8/10-bit finishing is a useful verified tool, but not scene-linear OCIO/ACES/EXR. A genuine next-generation pipeline needs per-source camera input transforms, color-space+transfer labels, immutable actual OCIO config, 16f/32f RGBA/depth/motion passes, correct alpha and display encoding.
- Audio contains independently owned speech, music, FX and ambience with sample clocks, original sync, fade/mastering/ducking, real loudness/true peak and licensing. A missing performance cannot silently be replaced with synthesized audio.
- Scheduler measures CPU/RAM/VRAM/disk and is durable under process death, source corruption, missing devices, lease races, intermittent networks, render chunk failure and host relocation. OpenCue only helps if real licensed render workers exist. A GitHub free test runner is not a persistent GPU host.
- Owner mobile interface needs secure external HTTPS identity, authenticated state and media upload/review, job control and backups on a persistently running authorized machine. Existing 375px Chromium loopback proof does not prove actual remote Android availability.
- Reality check is twofold: actual decoded audio/video/time/color/media/copyright plus human independent editorial/story/aesthetic evaluation on unrelated original commissions. Pass/fail logs never assert everyone likes the film.

## From owner request to verified master
S0 Owner-approved original brief, facts/rights and immutable intent.
S1 Rights-verified asset acquisition/original source production, exact owner evidence and CAS URI; no invented actors or fake original recordings.
S2 Editable Film IR, source color/time and independent scene graph.
S3 Check installed real tool/effects/3D/codec/GPU/plugin and budgets; missing capabilities stay unresolved, never replaced by anonymous remote service.
S4 Schedule graph nodes and physical media using exact source bytes, prior lineage, worker leases and resource capacity.
S5 Create original video/3D/2D/VFX/voice/music/SFX in separate verified scene and track operations.
S6 Composite physically, output correct frame/sample and scene color properties; expose loss-aware OTIO/scene interoperability.
S7 Finishing scene-linear effects, color transforms/EXR and high-quality audio/stems (only when verified); export chosen mezzanine/delivery format.
S8 Complete decode, rights, color tags, pixel/sample metrics, temporal sync and continuity observations.
S9 Creative Director inspects actual full evidence and revises only targeted original scene nodes. Previous masters remain immutable.
S10 Owner preview/approval, human quality gate, audit receipts, secure distribution and project migration.

## Evidence-driven release matrix
| ID | Requirement | Blocking proof |
|---|---|---|
| A0 | Facts/legal originals | Real signed/digested video/music/voice/3D/weights, denied forgery and original story immutable |
| A1 | Editable film semantics | Arbitrary film shapes/shot dependencies, exact time/sample/source references, reversible revisions, real export/import loss report |
| A2 | Native postproduction toolkit | Physically decoded nonlinear multitrack, true masks/key/roto/tracking, precise VFX/3D/light/motion and audio buses; no fake shell effects |
| A3 | Correct color and sound | Professional tagged source, verified OCIO+ACES and EXR high-precision passes with alpha/depth; decoded picture and true audio loudness/stems |
| A4 | Autonomy-ready API | Live verified model-neutral tool discovery, fine-grained operations and read-only visual/audiovisual review, constrained permissions and no secret spend |
| A5 | Scalable durable computation | Resource admission, chunk/frame checkpoints, restart/worker crash, cross-host lease and source integrity, safe immutable completion |
| A6 | Quality + continuity observation | Full decoded movie and shot identity/position/camera/music/voice evaluation, targeted defect repair, independent original film quality samples |
| A7 | Phone-first production | Actual remote Android HTTPS owner identity; 24/7 durable authorized host, secure media, backup and tested browser controls |
| A8 | Independent acceptance | Several unrelated original films, advertisements, educational and VFX pieces with real actual source, independent human ratings; pass all previous gates |

RELEASE requires all A0–A8, verified by objective and independent evidence; none can be waived because 400+ unit tests pass. Earlier G0–G8 master gates remain authoritative and compatible.

## Independent candidate technologies and real limitations
- FFmpeg is a verified local compositor and media encoder, with original frame/audio and tetrahedral/trilinear Iridas CUBE LUT: https://ffmpeg.org/ffmpeg-filters.html
- Academy OpenTimelineIO handles editable media/time interchange, not final rendering: https://opentimelineio.readthedocs.io/en/latest/
- Academy OpenColorIO ACES configurations require physically selected exact config/transform revisions and testing: https://github.com/AcademySoftwareFoundation/opencolorio-config-aces
- Scene-linear OpenEXR supports HDR precision/alpha beyond display 8-bit, enabling correct VFX passes: https://openexr.com/en/latest/SceneLinear.html
- Blender is physically installed for real 3D CPU scene rendering; OpenUSD is a future content-interchange option: https://openusd.org/release/intro.html
- Natron/OpenFX for node compositing and plugin host support only when actual licensed installed adapter passes tests: https://github.com/AcademySoftwareFoundation/openfx
- MLT and GStreamer Editing Services are pilots for advanced edit/scrub/preview; adoption needs real latency/frame/audio/interop benchmarks against existing FFmpeg, not automatic replacement.
- OpenCue is a render-farm coordinator, not a source of free GPU workers: https://github.com/AcademySoftwareFoundation/OpenCue
- Recent AVE-Compass, JAVEDIT, VideoAgent and professional editorial-technique research highlight audiovisual and creative-evaluation gaps; a paper never proves local weights or world-class output.
- Cloudflare free edge/tunnel must not be presented as a zero-cost persistent 3D/render computer. No anonymous public test origin without explicit owner approval.

## Frozen priority / execution strategy
1. Verify every existing BODY artifact, regression, original brief, rights and code branch. Eliminate source, permission, data corruption or invalidation bugs before inventing new tools.
2. Stabilize shared owned source identity across color/audio/edit/3D and build loss-aware media/scene interchange. Prove unchanged originals and only affected rerenders.
3. Grow **physical** professional editing toolkit inside same graph: layered original VFX, true masks/keying, camera/depth tracking, registered effects, rational timeline/audio and non-destructive revisions; test decoded pixels and original soundtrack.
4. Establish real BT709 8/10-bit color transform path now; then verify OpenEXR 16/32f scene-linear intermediate, OCIO config integrity, Blender/Natron roundtrip and alpha/lighting/depth preservation. Distinguish an effect LUT from ACES.
5. Enforce stage-level resource budgets and durable frame/chunk rendering. Prove kill/restart/corruption and cross-host recovery without replaying old paid jobs or falsifying output.
6. Build genuine owned-source generation/acquisition when real hardware/rights/checkpoints are available and keep all unmet original actor/video effects explicit.
7. Add full actual media observation, mixed speech/music/FX QC and selective art-driven repair. Brain/model research remains frozen until BODY is complete.
8. Expose Android owner interface through deliberately approved secure persistent compute identity (no unsupported promises of 24×7 free GPU).
9. Run multi-style independent films and expert/human audience tests before declaring BODY complete, proposing any model as the final artist, or merging unfinished PR into main.

## Current honest evidence
The mature BODY branch has real 2D/3D, FFmpeg, multitrack sound and editing, approved source rights, source-rational retiming, cross-host project relocation, one-use proof-bound media downloads, stage lease renewal, actual Chromium mobile-width loopback UI, original-shot selective re-render and prior full native 396-test release. Confirmed native release (22 October 2026): https://github.com/oyzitjfzj/Ad/actions/runs/39731187547 physically ran actual owned-camera RGB keying and retained sound, tagged BT709 compositing, owner-attested Iridas CUBE 3D LUT, 8-bit H264 and 10-bit ProRes MOV grading. An independent actual Blender Cycles CPU scene-linear **32-bit float multilayer OpenEXR** frame engine then passed a 409-test native integrated release at https://github.com/oyzitjfzj/Ad/actions/runs/39732481834 (one browser test skipped here and separately exercised in Chromium): Combined RGBA, Depth.Z, Normal.X and Vector.X were actually decoded through OpenEXR v3.3+. The EXR asset ZIP is bound to per-frame SHA/size and verified scene inputs. The later archive hardening, EXR artifact retention and every indexed frame integrity check were actually verified in full native run https://github.com/oyzitjfzj/Ad/actions/runs/39733099620 : 410 tests, 409 passed; sole Chromium browser acceptance handled by separate real browser run. Actual Blender 32-bit channel data, EXR ZIP archives, first decoded original EXR, VFX camera MP4, fully keyed original and 10-bit ProRes MOV with original sound are archived at https://github.com/oyzitjfzj/Ad/actions/runs/39733099620/artifacts/12405304829, not claimed to be an independently directed premium film.

Scene-linear EXR native passes do NOT yet demonstrate a complete cross-application OCIO/ACES project, EXR-to-HDR film grade, arbitrary VFX mask/track/relight, real video generation GPU, a free persistent renderer host, owner-external Android access, complete original The Fold or independent human cinematic quality approval.

This document is an end-to-end engineering contract and blockers log, not prose fed to the eventual creative intelligence. Code and physical evidence, not this document, determine completion.
