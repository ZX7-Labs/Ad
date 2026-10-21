# ZX7 Studio — Professional BODY Research and Engineering Plan
Date: 21 October 2026. Base: zx7-body/mobile-operator-20261021, derived from zx7-specialist-free-stack-20261020. This is an engineering handoff, not a prompt to any future AI filmmaker.

## Decision
Build a general-purpose professional non-destructive editing **operating environment**, not a collection of pre-designed videos or one hardcoded renderer. The eventual creative AI independently chooses which parts of its instruments to use. The BODY exposes installed operations by capability discovery, with concise exact schemas requested just-in-time, then renders, observes and repairs actual media. Visual taste and creative decisions do not belong inside the permission/type validation layer.

What is already physically verified: real Blender CPU 3D, moving-graphics 2D, FFmpeg sound/compositing, OpenTimelineIO export, signed media and rights receipts, crash-recovery, local API and operator UI. Prior full 323-test native baseline: https://github.com/oyzitjfzj/Ad/actions/runs/39596676559 . No verified general GPU generator, fully autonomous premium cinematography or finished original film. Preserve the previous The Fold experiment and M3/F2 voices.

## Research and integration choices
| Area | Grounded upstream system | Decision / why | Measured promotion gate |
|---|---|---|---|
| Editable timeline interchange | ASWF OpenTimelineIO | Keep; OTIO holds external media references, not media or a universal render engine | Cross-app frame/sample/effect-loss report |
| Live professional NLE | MLT 7.42 (released Oct 3, 2026) | Pilot independently; multitrack video/audio and adjustment clips, optional GPU placebo | Compare actual 3 video + 3 audio edit to trusted FFmpeg, rendering and scrubbing |
| Live timeline/proxy | GStreamer Editing Services | Pilot; layer/track pipeline and hardware compositor via installed plugins | Measured proxy delay, RAM, color and frame exactness |
| Reliable encoding | FFmpeg | Retain native backend with explicit stream and filtergraph mapping | Decode output, timing, true-peak and integrity evidence |
| 3D, camera, physical effects | Blender, OpenUSD | Blender proven; USD for interoperable non-destructive 3D scene overrides as available | Actually render same material/lighting/animation through installed tools |
| Node VFX | Natron/OpenFX | Trial an installed external OFX host, not automatic raw shell or model code | Masks, track, real EXR passes, alpha and dependency proof |
| Scene-referred color | OpenColorIO/ACES | Typed working/render/display transforms, hashed configs, never implicit view LUT | ACES pipeline output checked against known numerical reference |
| VFX intermediates | OpenEXR/OpenImageIO | Multichannel high-dynamic-range/alpha/depth intermediate | Preserve channel precision and metadata across tools |
| Optical-flow slow motion | RIFE family | Candidate only with real model weights, licensed runtime and GPU; do not silently invent interpolated frames | Motion artifacts, occlusion, provenance and performance audited |
| Professional sound | FFmpeg loudnorm + audiorouting | Preserve explicit soundtrack and voice, add measurable LUFS, samples and ducking | Before/after actual audio measurements and speech intelligibility |
| Continuity | shot identity + evidence ledger; multi-shot research | Persist characters, props, cameras, color and temporal anchors across revisions | Detect spatiotemporal mismatches in 3+ sequential shots |

Official source checks:
- https://mltframework.org/ and https://github.com/mltframework/mlt (framework LGPL-2.1; some apps/plugins differ)
- https://gstreamer.freedesktop.org/documentation/gst-editing-services/index.html
- https://gstreamer.freedesktop.org/documentation/gst-editing-services/hardware-acceleration.html
- https://opentimelineio.readthedocs.io/en/latest/index.html
- https://github.com/AcademySoftwareFoundation/OpenTimelineIO/blob/main/docs/tutorials/otio-timeline-structure.md
- https://openusd.org/release/intro.html
- https://github.com/AcademySoftwareFoundation/openfx
- https://natrongithub.github.io/about
- https://github.com/AcademySoftwareFoundation/OpenColorIO
- https://github.com/AcademySoftwareFoundation/openexr
- https://github.com/hzwer/ECCV2022-RIFE
- https://ffmpeg.org/ffmpeg-filters.html
- https://developer.blender.org/docs/release_notes/5.0/migration/compositor_migration/
- https://arxiv.org/abs/2608.26809
- https://arxiv.org/abs/2606.23327

## Internal architecture: engineering contracts, not model instructions
1. **Immutable original project and rights**. All owned/licensed media, sound, fonts, geometry, models and evidence have content identities and immutable source facts. A model cannot establish ownership of an untrusted external asset by naming it.
2. **Film and Timeline IR**. Express decisions as original shots and timelines with rational timebases, source trims, layers, camera moves, nodes, keyframes, source/audio clocks, edits and revision IDs. No fixed number of scenes, movie duration, genre, preset, voice or render engine. OTIO is a loss-aware external interchange adapter, not the canonical execution vocabulary.
3. **Non-destructive operation graph**. Effects are typed callable operations with time range, color space, input/reference IDs, artistic parameters, installed capability and exact source hash. Any edit yields a new revision and invalidates only dependent stages.
4. **Real compositor and precise NLE**. Multiple video/audio tracks, split, slip, slide, ripple, keyframe curves, speed ramps, masks, roto, blends, chroma/lighting/depth effects, motion blur, 3D mapping and optical-flow are separate tools. Technical operation coverage is expanded through installed native libraries; an absent renderer does not silently flatten the film.
5. **Image/3D standards**. Explicit ACES/OCIO color management, scene-linear multi-channel EXR, OpenUSD layers and physical Blender render passes when installed and verified. Blender 5 compositor API changes require per-version compatibility gates.
6. **Audio timeline**. Separate voice/music/FX/ambient stems, sample-accurate author placement, declared silence, pitch-preserving original sound retimes, measured LUFS/true peak, original permissions, no missing dialogue claims.
7. **Observation**. Preview is an explicitly lower-fidelity derivative, never mislabeled final. Decode full film; inspect physical sound, caption bounds, cut timing, continuity IDs and visual consistency. Aesthetic quality is an independent reviewer/human metric, not the renderer's own unit-test score.
8. **Scheduler and cache**. Resource-aware deterministic, stage-level DAG, signed physical media receipts, sandboxed trusted adapters, finite jobs and leases, restart recovery and safe retries. Long-video segment and cross-host workspace migration still require implementation and physical proofs.
9. **Mobile owner interface**. Phone UI and remote communication consume the same API; remote access needs separate owner-approved HTTPS identity access. No unverified 24/7 free GPU/server claim.
10. **Future AI handoff**. One independent creative intelligence asks for installed capabilities, requests only a chosen operation's machine-readable schema, executes and gets measured media/scene-state feedback. Do not feed this research document to the model as a giant prompt.

## Sequence with non-negotiable acceptance
A. Finish and verify a first truthful physical instrument: exact rational source-frame retiming and synchronized original audio. This branch has a native FFmpeg retiming module and adversarial/full-media CI; verify terminal run and decoder-produced MP4 before claiming success.
B. Add native timeline operations and cross-app import/export loss reports; benchmark real MLT and GES instead of installing everything blindly.
C. Build color-managed VFX and 3D passes, masks, tracking, motion camera and USD interchange in isolated tools; exact local runtime/version/license checks required.
D. Deepen audio and finishing, original source identity and continuity over multi-shot films; incrementally validate actual pixels/samples.
E. Improve long render resumability and portable asset URI migration without changing facts or cache provenance; test actual hard-kill, disk errors and host relocation.
F. Build phone preview and owner-controlled operations, security/audit trail and zero-paid compute routing; verify mobile remote identity before exposure.
G. With BODY production release passing: later connect and evaluate creative intelligence on genuine independent ads, long-form edits, 3D/VFX films and radically different educational/story commissions, using blinded human aesthetic tests. Unlimited expert cinematic quality is a research goal, not proven.

## Release stop gates
No verified license, source footage, actual tool binary/model weights/GPU, owner permission, safe tool path, valid frame/sample timing, cross-host cached identity or measurable physical output => BLOCK. No silent 3D-to-2D substitutions, no invented audio, no hidden paid provider, no untrusted executable code, no false creative-quality certificate.
