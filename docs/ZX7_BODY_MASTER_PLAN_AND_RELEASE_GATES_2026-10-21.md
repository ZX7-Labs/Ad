# ZX7 Studio — BODY Production Master Plan and Release Gates
**Date:** 21 October 2026. **Purpose:** one coherent engineering project, not serial ad hoc features or a giant creative-system prompt. **Canonical active branch:** zx7-body/mobile-operator-20261021, draft PR #3 into zx7-specialist-free-stack-20261020; main unchanged. **Status:** NOT RELEASE-COMPLETE.

## Guiding goal (independent of the user's examples)
A future autonomous creative director should have the equivalent of a complete professional *working environment*, not a magic "make a video" API. The director can formulate original style, technique, rhythm and artistic decisions; acquire verified assets by identity; edit time and space precisely; simulate, composite and mix; inspect the real output; and revise individual decisions without rebuilding an unrelated film. No hardwired aesthetics, templates, genre bounds, shot counts or prompt handbooks in the BODY.

**Two separate claims must never be conflated:** technical readiness (tool execution, provenance, crash recovery, measured movie) versus expert creative quality (human preference, cinematography, storytelling, acting). BODY correctness does not certify creative excellence. The creative AI/model/approved voice choices remain unchanged while BODY infrastructure is developed.

## Full architecture
### A. Governance and immutable artist's authority
- Original brief, explicit personal facts, licensing, restrictions, creative intent and choices preserved as immutable source. Any unapproved asset must block publishing.
- Permissions: read, write, network, paid, third-party executable are separate capabilities. Creative model cannot grant itself paid access, model weights, GPU, rights or shell access.
- One creative agent/brain can make broad artistic decisions. Specialist tools are independent executors, not independent competing editors silently overriding intent.

### B. Project identity and media storage
- Content-addressed MediaVault with actual bytes, format inspection, source labels and attestation, immutable working originals.
- Portable URI backed by exact digest + attestation, not by the old machine's paths; source fingerprints must include the physical CAS bytes.
- OTIO/3D/audio project interchange is loss-aware and separate from body execution. An external NLE's unsupported effects are reported as lost, not discarded silently.
- Relocation on another host retains media, art and history, quarantines old worker jobs and caches, then reconstructs new editable media links only if source SHA and rights match. Same-path restore may keep exact state; different-path import cannot claim old jobs ran there.

### C. Creative intermediate representation
- Director-controlled film/scene/shot identities, arbitrary narrative structure, reference images/footage, physically declared effect/audio/3D graphs, editable clips/tracks, source-frame timebase, keyframe points, colorspace/source/output metadata.
- Interchange OTIO for shots/tracks, OpenUSD scene description (only when installed/proven), OpenColorIO for linear/scene/view transforms, OpenEXR for multi-channel intermediate passes. Their schemas are adapters, not constraints on artistic intent.
- Automatic extension through discovered and verified tools that expose compact argument schemas queried on demand, with code-supplied budgets and safety constraints.

### D. Real nonlinear editing controls
- Independent editorial operations (cuts, trims, slip/slide/ripple, alternate takes, nested tracks, transitions, speed mappings, holds, reverse, proxy/version, clip/keyframe curves) with rational sample/frame time semantics and accurate source identity.
- Real native backends benchmarked on the same original assets: proven FFmpeg body; MLT as candidate for multitrack and live timeline; GStreamer Editing Services as candidate for fast preview. Promote only native benchmark results.
- Whole-project effects need reversible revisions and dirty-subgraph rerenders, not a sequence of destructive mp4 re-encodes.

### E. Visual design and VFX
- Scene/spatial operations: masks/rotoscopy/keying/tracking, optical flow, motion blur, alpha/premultiply, 2D/2.5D depth, typography and layout, particles, lighting, image processing, color/grading and motion graphics.
- Original 3D: Blender camera/lighting/assets/materials/physics/simulation with strongly versioned script/asset SHA; optional OpenUSD interchange and multi-pass EXR.
- Natron/OpenFX candidates, only as trusted installed adapters. No unapproved user/model Python script gets executed as an effect.
- Distinguish creative layer, actual render output, and objective constraints; retain stylization even when metrics dislike an intentional dark/quiet scene.

### F. Authentic audiovisual production
- Real sources, not a claim that one text model can invent photoreal actors when the local GPU is unavailable. Verified provider/weights/license/device budgets required for generative source footage, with controllable motion/camera/continuity and temporal inspections.
- Recorded speech/approved M3/F2 voices, independent music/FX/ambient sound, signed original source clips, sample-accurate soundtrack sync, measured LUFS/true peak, mastering, captions and lip alignment as verifiable separate operations.
- Never drop or replace voice/soundtrack without an explicit original artistic decision.

### G. Agent-tool loop (BODY service, NOT model choice)
- Discover on-host installed capabilities. Ask only for a selected operation's concise typed schema; execute limited artifact job with trusted implementation, input media fingerprints, material provenance and permission checks.
- Durable DAG scheduler with dependency tracking, timeouts, leases, attempt identity and idempotency; atomic stage receipts; actual physical verification on all reused results.
- Keep feedback interpretable: decoded timecode, image/audio evidence, broken source references, missing capabilities, timing drift, rights blocker and actionable repair target; not 1000 lines of textual model instructions.
- Entire chain must preserve original user facts and not overwrite creative decisions under error recovery.

### H. Persistence and physical compute
- Host scheduler accounts for CPU/GPU, free memory, disk, render time, code/model revisions, stage-level intermediate assets and queued jobs. Site-level resource constraints are not creative limitations.
- Reproduce host power-off mid-render, simultaneous worker race, missing/corrupted inputs, partial external I/O, out-of-memory and network loss.
- OpenCue optional only after a real authorized worker farm exists. No remote service can be presumed free/infinite or GPU-equipped.
- Renderer evidence must survive kill/restart with checksums and cleanup; portability must not reuse stale absolute paths or old host claims.

### I. Android, privacy and 24/7 UX
- Mobile-only user needs a secure remote browser control plane; rendering need not occur on the phone. Local 127.0.0.1 API already exists but is NOT remote production deployment.
- Owner-identity security for public HTTPS host, narrow API permissions, file-upload integrity, resumable source transfers, review previews/shot selection, job retry/pause/cancel, media download, explicit billable-action approval.
- Cloudflare Pages/Workers/Access/Tunnel are candidates for cheap control/routing when a persistent authorized origin host exists; free edge does NOT equal a Blender/GPU farm, and no public tunnel is provisioned without actual owner and account permission.
- Software must be controllable from phone, with no PC installation prerequisite for the owner.

### J. QA and product release
- Technical QA: full decode, original video/audio requirement, source hashes, rights, timecode, color, alpha, profile/codec, audio loudness, portable OTIO/scene/project interchange, crash recovery.
- Aesthetic QA separate: blind real human ratings across ads, stories, educational clips, actual live-action and original 3D/VFX; 2 very different original editing styles with scene-continuity evidence. Human response is empirical, never assumed 100% positive.
- Network/security/privacy/rights tests must be included in release candidates, not waived because FFmpeg generated a playable MP4.

## Dependency graph and acceptance gates
| Gate | Dependencies | Evidence required | Status as of 2026-10-21 |
|---|---|---|---|
| G0 Original media + legal custody | Immutable source, MediaVault attestation, user facts | Malicious media spoof blocked and original archive digest physically verified | Verified native base, ongoing extensions |
| G1 Local production kernel | Tool registry, typed ABI, job DAG, event/state, preview and audit | Concurrent kill/restart/resume test and physical output SHA | Verified native kernel, distributed scheduling incomplete |
| G2 Portable editing project | G0 G1, asset refs, OTIO loss-report | Cross-host original sound+video survives, new OTIO links exact digest, no stale job replay | Cross-host import verified; complete auto media relink under new native tests |
| G3 Full physical editing operations | G1 G2, timeline time engine | Arbitrary cross-track edits and retime, masks/tracking, original sound, edit curve exactness on decoded frames | Partial, not complete |
| G4 Full film/VFX/3D/color stack | G2 G3, trusted native library adapters | VFX masks, 3D motion/pass, color transform and original footage render actual pixel artifacts | Blender/2D/FFmpeg proven, advanced VFX/OCIO pending |
| G5 Independent source production | G0 G4, rights + actually deployed model/device | Genuine original scenes matching camera/acting/motion/continuity plan with no missing source | Blocked: no verified free local GPU/live-action actors |
| G6 Remote production and owner control | G0 G1, persistent compute and verified HTTPS identity | Actual Android external connection, no exposed secret, steady jobs and data backup | Blocked: localhost only |
| G7 Scale + failure protection | G1 through G6 | Real long projects: cross-host restart, dropped network, worker preemption, corrupted media, bounded resource recovery | Partial |
| G8 Delivery and human acceptance | All prior | Multi-genre independent cinematic films + detailed human/editor review, repeatable production evidence | Blocked |

**Final RELEASE-COMPLETE invariant**: G0..G8 must have verifiable independent evidence. A new model or preset cannot substitute for missing BODY infrastructure. The next engineering operation is chosen by the highest dependency/impact, not by repetition of the last user analogy.

## Research backbone and non-executable candidates
ASWF OpenTimelineIO (including OTIOZ and media linkers): https://opentimelineio.readthedocs.io/en/latest/
OpenAssetIO portable asset identity: https://github.com/OpenAssetIO/OpenAssetIO
OpenCue distributed film render jobs: https://github.com/AcademySoftwareFoundation/OpenCue
MLT: https://www.mltframework.org/
GStreamer Editing Services: https://gstreamer.freedesktop.org/documentation/gst-editing-services/
OpenFX/Natron: https://github.com/AcademySoftwareFoundation/openfx and https://natrongithub.github.io/
OpenColorIO, OpenEXR, OpenUSD: https://github.com/AcademySoftwareFoundation/OpenColorIO ; https://github.com/AcademySoftwareFoundation/openexr ; https://openusd.org/
FFmpeg: https://ffmpeg.org/documentation.html
Cloudflare platform: https://developers.cloudflare.com/
Research literature on professional edit technique/AV synchronization: inspect original findings and bench results before selecting any generative model, and never equate a paper with local measured tool availability.

## Verified evidence pointers (historical and branch-relative)
Baseline fully physical native release: https://github.com/oyzitjfzj/Ad/actions/runs/39596676559
339 tests including actual frame-retime and original synchronized audio: https://github.com/oyzitjfzj/Ad/actions/runs/39633396399
347 tests including cross-host archive/rights and unsafe job quarantine: https://github.com/oyzitjfzj/Ad/actions/runs/39638672302
Latest new stable media source identity + OTIO rebind suite must have its OWN green native run, do not backdate success from earlier commits. GitHub draft PR #3 retains branch history and exact current CI artifacts.

## Preservation rules
- Do not modify the original 'The Fold' film brief, scripts or M3/F2 voice choice in BODY tasks.
- Do not merge to main or publish customer service without explicit permission.
- Do not install or trigger paid external compute, domains, plugins, random weights or services without owner approval.
- No fake 24/7 GPU/cloud performance claims or artificial model scores.


## Additional system-failure research and physical execution — 21 October 2026
The following were selected by independent security and reliability analysis, not by any one editor example.

- **Download byte provenance**: An earlier HTTP path hashed media and then reopened it after emitting the 200 response, creating a file-swap race. The new verified-delivery module first takes a disk-backed, O_NOFOLLOW, exact SHA256 and byte-length snapshot, then sends only those physically verified bytes. Direct authenticated and single-use ticket downloads use it. Adversarial tests deliberately swap or truncate originals between inspection and serving.
- **Long production leases**: A render that lasts longer than its one-hour durable lease might be retried while still publishing. The graph now renews an exact owner/node/input-fingerprint lease through a trusted heartbeat and stops the heartbeat before committing. Tests exercise actual SQLite timeouts, stale-owner denial, crash expiry and concurrent renderer no-duplication. This is NOT a cross-machine render scheduler.
- **Actual mobile-width browser**: A 375px Chromium instance calls the real loopback BODY HTTP service, validates token rejection and no tab persistence, imports a real rights-attested wave file, submits original Film IR, inspects jobs, downloads actual bytes using a single-use authorized ticket and captures a UI screenshot. Browser acceptance is separate from the physically rendered installed-wheel 2D+3D+audio+GUI crash-proof suite. Browser emulation does NOT verify access from a real Android device across networks.
- **Honest measured technical resources**: Live authenticated API reports real CPU, workspace disk, Linux RAM, cgroup v2 CPU/memory restrictions and driver-reported NVIDIA GPU capacity. No device presence proves model weights, successful photoreal cinematography, free hosted GPU, aesthetics or safe cloud pricing. Resource probes are still not a production-quality workload scheduler.
- **Strict native release evidence**: The complete native CI suite may skip only a separately proven Chromium browser test. Any unrelated skip or failure invalidates the release. Real MP4, OTIO, PNG, desktop QA, crash-recovery evidence and installed-wheel outputs are preserved as GitHub Actions artifacts where successful.

**Zero-budget Android deployment research**: Cloudflare Quick Tunnels are officially for development and carry no uptime SLA. Since 2 October 2026, the official cloudflared allowed-mail flag can restrict a test tunnel by email OTP without owning a domain (https://developers.cloudflare.com/cloudflare-one/changelog/tunnel/). Nevertheless a safe permanent public owner-console needs owner-approved Access identity, stable running origin compute and suitable domain/hostname configuration (https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/). Never expose anonymous access or call ephemeral GitHub Actions a 24/7 render GPU host. No tunnel or paid compute was launched.

**Still BLOCKED**: production depth across OpenFX/masks/tracking, color-managed OpenColorIO and OpenEXR intermediate passes, loss-aware non-destructive multi-engine timeline/scene revision, real source footage and legally cleared generative weights+GPU, distributed render worker failure recovery, secure persistent external Android usage and independent human/audiovisual cinematic-quality acceptance. These are objective release gates, not a demand for generic prompts or an arbitrary number of extra tests.


## 22 October 2026 — Non-destructive film DAG and material custody engineering

This iteration followed the system's real execution bottleneck instead of a requested visual editing preset. Independent technical research compared action graph cache keys and original file dependencies used in Bazel-style builds with OpenTimelineIO's external source references.

Technical changes:
- Scoped exact asset fingerprints: original artist-authored shot_refs and optional per-tool asset_refs are validated against known Film IR identities. Unscoped operations conservatively include the entire artistic film. Artist-independent operations may retain proven results when a totally unrelated shot adds a new source.
- Before-commit source remeasurement: after a real encoder/tool finishes and its resulting movie is checked, the executor remeasures all original physical input SHA256/lengths. If source media changed while encoding, completion and signed output reuse are refused. This remeasurement does not certify subjective film quality.
- Read-only original film revision planner: calculates changed operations and the downstream dependency closure across previous+new DAGs; deleted nodes and unrelated unaffected operations are reported separately. An unchanged candidate is NEVER certified as cache-verified, because runtime must independently check physical source, rights, installed renderer code version and retained output.
- Mobile operator and authenticated API: two selected original Film IR files can be compared through bounded POST /v1/revisions/impact without model calls, paid resources, cache/database mutation or any physical render; separate Chromium QA drives the browser inputs and validates impact output.
- Physical two-shot audiovisual proof: native release tests actually encode two independently owner-attested original H264/AAC shots, assemble an audio-and-picture master, then replace only shot B with newly licensed physical source while preserving shot A's encoded bytes and the entire first finished film. They decode both final movies to reject fake JSON-only claims. Color and sound fixture choices are ONLY test data, NEVER default artistic film templates.

Release gates remain blocked for breadth of native VFX/color/3D/optical flow, real GPU-dependent actors/source generation, fully versioned non-destructive effect graphs, true distributed worker resource-aware retries, owner-authenticated persistent off-phone internet host, full audiovisual observation and independent human story/style quality assessment. Engineering docs are NOT a creative Brain prompt.


## 22 October 2026 — Frame-level original Blender EXR restart design and physical gate
**Systemic release blocker addressed:** a single long CPU/GPU simulation/render task could previously be retried only as one scene-level operation after process death. Its already valid frames were lost as performance work, even though the exact original 3D camera/geometry and multi-layer EXR can be rendered on its absolute frame clock.

**New engineering branch work under CI verification:** Blender receives an optional inclusive absolute frame interval while preserving the original full scene animation and source keyframes. A trusted BODY host-only per-frame checkpoint hashes the artist's original scene, actual Blender executable version/location, implementation source and OpenEXR decoder version. Frame-by-frame accepted output must decode actual 32-bit float RGBA, depth, normal and motion vectors and retain exact original width/height, SHA256, physical byte count and channels. After a simulated renderer interruption a second execution reloads only verified frames and renders the rest using original frame IDs, under an exclusive OS process lock. Distinct original artistic scene or renderer revisions cannot silently use stale checkpoint frames. Full ZIP publication requires every original EXR frame to pass native decoder and manifest verification, with exclusive archive linking, preserved owner scene and no visual creative defaults.

**Acceptance:** actual Blender Cycles produces three multi-pass EXR frames, an injected failure interrupts after the first, a second run resumes only frames two and three. Physically corrupting retained EXR forces rerender; replacing original scene identity refuses unsafe resume; simultaneous worker cannot create duplicate original frames; independent registered BODY tool composes its verified ZIP. These are CI tests, not automatic success claims until full native run is green.

**Scope and limitations:** genuinely local, permissioned 3D frame checkpointing; not distributed render farms, GPU generator deployment, optical-flow synthesis, external user-authenticated streaming or safe cross-host live-job migration. Later multi-host work requires durable centralized coordination, worker identity and leases, resource scheduling, transfers with signed frame custody, and actual preemption/restart acceptance. This module is infrastructure and never overrides the creative AI's original choices.
