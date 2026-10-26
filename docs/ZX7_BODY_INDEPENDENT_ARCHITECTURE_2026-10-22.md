# ZX7 Studio BODY — independent architecture decision and executable development map
**Decision recorded:** 22 October 2026. **Status:** engineering plan + partial implemented foundations, NOT production-complete. **Scope:** BODY only; creative model selection, original film scripts and approved voices are frozen. **Branch:** `zx7-body/mobile-operator-20261021`, draft PR #3; main untouched.

## 1. Independent system conclusion

The system's core problem is **not** how to make a model memorize software manuals. It is how to expose real instrument abilities and constraints without making a speculative planner responsible for the physical truth. The BODY owns executable mechanisms, not editing tastes; a future film intelligence owns artistic decisions, not file permissions or proof. A static catalog of model prompts and a one-shot MP4 API both fail this division. A robot analogy is useful only when translated into measurable boundaries: sensed real state, narrow motor affordances, exact actuator commands, observed consequences and persistent task history.

**Decision:** use a stateful, code-native **film production operating system** with independent but coupled:
1. **Intent plane:** immutable briefs, exact owner facts, permissible source identities, style and story decisions, human approvals. The BODY does not generate these facts.
2. **Film state plane:** original-media CAS + rights, canonical versioned timeline/scene/audio graphs, exact rational clocks, color/coordinate conventions, loss-aware external interchange, dependency links.
3. **Somatic capability plane:** trusted registered operations, hardware probes, compact typed discovery, only selected command schema, rights/permission preflight, output contracts and failure modes.
4. **Motor/execution plane:** side-effect authority, reliable source-bound transactions, typed execution DAG, finite host budgets, source/version invalidation, recoverable stage/checkpoint and physical post-encode verification.
5. **Sensory plane:** source-bound decoded image, timecode, audio, color and motion evidence; documented uncertainty and confidence. Subjective creative analysis, once real, is independently marked as semantic and cannot impersonate a technical measurement.
6. **Review/learning plane:** factual evidence ↔ requested film intent ↔ human/model review ↔ minimal targeted edit ↔ measured new revision. Artist may explicitly reject model suggestions. No background self-updating executable plugin.
7. **Owner/control plane:** mobile browser, authenticated project rights/upload/preview, cost resource limits, staged deployment and secure backup. Actual external HTTPS requires an authorized persistent origin; GitHub runners are CI, not always-on render servers.

Each plane communicates using compact typed data with provenance rather than copies of an entire prose handbook. No installed tool may be silently granted creative authority, cost authority, model weight ownership or permission to replace existing source media.

## 2. Runtime contract, not MD-model prompting

The core machine dialogue is an executable state protocol:
```
caller goal + authorised owner facts + requested exact capability
       ↓
SENSE: current project state + installed feasible actions (small paginated list)
       ↓
DESCRIBE: selected tool ABI, precise input/output/rights/time/colour boundaries
       ↓
PREFLIGHT: actual right-attested input bytes + host constraints, *no execution*
       ↓
ACT: submitted immutable Film IR, authorized finite tool graph and durable job
       ↓
OBSERVE: exact output artifact hash, decoded frames/audio, timecode, stage receipts
       ↓
REVISE: selective versioned delta, revalidate input, replay only affected nodes
```
Messages are *facts and selected decisions*, not scripts telling a model that FFmpeg exists. The capability map changes when physically installed software changes; stale cursors and results must be refused. Registered-but-uninstalled tools must be separately visible as needs-setup, never fictional ready operations. Instruments must not hallucinate licensed footage, host GPU, full ACES, cinema quality or finished creative judgments.

**Implemented in this increment:** `studio_next/body_affordances.py` and authenticated `/v1/affordances`, `/v1/affordances/<id>`, `/v1/affordances/preflight`. They are a **read-only preparatory control surface**, not a full nervous system or an MCP server. They defer actual writes to the existing durable Film IR graph. Existing `body_capabilities.py` remains compatible; later migrate callers deliberately once equivalent security and browser tests pass. There is no proprietary model dependency in this surface. Current list's `input_schema` is lazy; its tooling implementation uses the actual registered tool versions. It refuses a forged original MediaVault `asset_id` or `attestation_id` at preflight rather than accepting empty source receipts. It still cannot prove frame output before a real render.

MCP-inspired discovery (official: https://modelcontextprotocol.io/specification/2026-07-28/server/tools ) is a *possible external adapter* with tools/list, input/output schema and change notifications. ZX7's authenticated local HTTP interface **does not claim MCP compliance**, and MCP is not a creative reasoning model. Tool metadata and source rights stay server-side.

## 3. Media and time as actual computational substrates

**Original legal custody:** all source bytes, generator weights, uploaded/licensed image/video/sound/3D/fonts/LUTs and their authorized transformations require content hashes, owner attestations and operation/source revisions. Preserve immutable original sound, original user facts and earlier film masters. File paths are locations, not proof. Archive imports must confirm CAS identity before relinking.

**Canonical film state:** use an extensible versioned graph with independent picture tracks, audio buses, nested sequences, masks, keyframe curves, camera transforms, scene graph, render passes, color metadata and exact rational clocks. Define cross-domain transformation explicitly (video frame, audio sample, motion frame, world 3D, image pixels). OTIO is used for time-based external interchange and requires loss report (https://opentimelineio.readthedocs.io/); never claim it is a complete VFX renderer. OpenUSD is a future independently tested scene interchange, not an artistic director. Existing source-bound exact-cut/reversible NLE is a partial foundation, not a full NLE.

**Color/VFX:** the adapter must not confuse 8/10-bit display BT.709 with scene-linear EXR. Establish a pinned tested OpenColorIO/ACES config, exact numerical reference transforms, linear/premultiplied alpha, gamut-aware display encoding, physically measured depth/normal/vector and compliant mastering. Test all color-space crossings before promising HDR/ACES. Advanced roto, optical-flow tracking, keyed masks, rigged animation, camera match, physics and 3D source inventory are separate verified operators.

**Sound:** multi-stem speech/music/FX/ambience with measured source legal identity, original M3/F2 choice preservation, rational sample clocks, sample-exact automation, native LUFS/LRA/true peak and listening-based mastering. Do not silently drop a missing voice or synthesize a substitute. Cross-shot audio is independently editable from picture.

## 4. Executable skill/adapter contract

Every tool must have a versioned typed ABI; declared required inputs; output media type, time/color/audio geometry and authoritative physical postconditions; rights policy; execution mode; measured host cost ceiling; dependency fingerprint; versioned open/proprietary license review; install/uninstall health probe; streamable evidence; cleanup, interruption and idempotency/retry semantics.

An entry-point import is trusted host code, not a sandbox. The model never supplies shell commands or unrestricted Python. Plugins are independently audited; no automation installs arbitrary packages, models, workers or paid services. Discovery is *not* proof of usable GPU, model weights or skill. When a tool is missing, return an unresolved dependency with alternatives **only if artist-approved**, never a fabricated imitation.

## 5. Reliable physiology: execution and perception

BODY is not a chatbot executing shell commands. Jobs are stored as immutable film-project DAGs in a trusted coordinator; every stage has source/key/input version, host tool version, exact resource lease, output physical witness and state transition. On crash, replay only proven idempotent stages, verify source hash again and never replay uncertain paid/generative effects silently. Concurrent stages must not publish into approved originals. On another host, invalidate stale host-specific claims while preserving original media and editing decisions.

Real performance progression: single-host leases → resumable exact tile/frame workers → cross-host transfer with signed/authenticated worker identities and source verification → resource-aware dispatch and monitoring (CPU, VRAM, disk, RAM, minutes) → interrupted upload/worker loss/disk full/GPU allocation failure tests. OpenCue can schedule *actual provisioned* render hosts but cannot provide free GPU machines (https://github.com/AcademySoftwareFoundation/OpenCue).

A sensory observation is (source digest, actual frame/audio samples, exact time range, decoder/color assumptions, measured properties, uncertainty, artifact link). A semantic judgement is a separate, explicitly sourced hypothesis. Dark/quiet/still content is not automatically a defect. A creative revision must identify exact prior owner goal and scene span and prove its changed physical result, not merely fabricate a higher quality score.

## 6. Risk-driven implementation order (not permanent hard-coded phases)

| Track | Engineering release evidence | Current reality |
|---|---|---|
| T0. Live control/runtime | Trusted discovery, schema-specific preflight, authenticated caller, code fingerprint and denial of forged rights | New preliminary somatic surface; latest matching CI must pass before verification |
| T1. Provenance/correctness | Asset ingest/restore, dependency cache, source revocation, same source across editing/audio/3D/export | Strong partial physically tested host-local foundations |
| T2. Expressive NLE | Ripple/roll/slip/slide, nested cross-track editing, multi-bus source sound, exact retime, transition/curve and reversible preview | Only hard-cut precise ops/partial multitrack implemented |
| T3. Professional VFX/color | OpenEXR scene-linear ↔ OCIO pinned transforms ↔ VFX comp ↔ 10bit/HDR master with independent pixel evidence | Blender 32f EXR and BT709 separate; no coherent certified OCIO pipeline |
| T4. Sensory loop | Actual decoded every relevant frame/audio + grounded semantic temporal/story observations + independent directed revisions | Physical picture/audio review, not autonomous cinema critique |
| T5. Original source creation | License/weights/hardware, controlled actual generated footage, continuity and provenance across scenes | Genuine legal no-cost video compute not presently verified |
| T6. Distributed durability | Reproducible multi-host exact-frame transfer, leases and failure injection | Host-local crash/resume and archive mostly verified |
| T7. Owner remote control | Real off-LAN Android HTTPS identity + persistent authorized render host + backups + cost/rate authorization | Chromium loopback, not deployed off-device |
| T8. Creative acceptance | Independent professional editor/audience review on multiple different real films with revisions and delivery | Not satisfied |

Ordering follows hard dependencies, and may change when actual performance measurements justify it. Source rights, native OS security, coherent time/color, accurate observations and independent creative evaluation must all pass; *no early release by test-count or document length*.

## 7. Release truth and anti-self-deception

The 12 subsystem ledger at `ZX7_BODY_VERIFIED_PROGRESS_MATRIX_2026-10-22.md` remains normative: **zero entire subsystem gates fully accepted**, ten with partial proof, two primarily blocked. This is not a progress percentage. Every new code commit requires a matching actual native CI run, plus adversarial tests for unsupported media, forged license, plan race, crash and cross-host when applicable. Native movie proof must be from actually decoded frames and audio with exact source identity. A fast no-FFmpeg test runner cannot certify physical movie tests.

Final product acceptance is **not a clever sentence or a model benchmark**. It is a repeatable independently scrutinized portfolio of real projects where a director can conceive and execute diverse original cinematic ideas with editing freedom, physical proof, reliable revision, legal custody, sound/color correctness and usable mobile control. No tool is marked elite until independently judged media warrants it.

## 8. Explicitly preserved boundaries

Do not modify or replace original The Fold screenplay/story or approved M3/F2 voice identities as BODY development. Do not merge draft PR #3 or deploy a public endpoint without owner consent. Do not buy accounts/GPUs/domain or install external risky tools without explicit authorization. An engineering record in this repository is for maintainers and future recovery; **it is not an LLM prompt** and must not be streamed wholesale to the creative agent.
