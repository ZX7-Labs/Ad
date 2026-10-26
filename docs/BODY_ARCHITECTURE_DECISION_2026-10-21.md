# ZX7 BODY — Independent Engineering Architecture / 21 October 2026

## Evidence boundary
Base for this decision: zx7-specialist-free-stack-20261020, head 24db0231b9d789ac798fbce71e9a3da8272559ad. Tree includes 273 files/directories. GitHub Actions release run 39596676559 tested 323 cases on preceding code revision; verified native CPU 2D+Blender 3D+audio+OTIO+MP4+crash recovery. Main branch is behind; separate multitrack draft PR #2 is preserved rather than overwritten. This document is for engineering continuation, NOT a model instruction.

User's latest priority: BODY first. Creative models, screenwriting competition and prior failed original The Fold test are left untouched.

## Product interpretation
Build a single production operating system for moving image work, not scene templates, visual limits or thousands of lines of language model prompt instructions. The future brain owns artistic choices. The BODY must make physical operations discoverable, executable, observable, reversible where possible and safe.

The analogy of an integrated body suggests useful principles but is not a literal implementation plan. Runtime tool discovery, just-in-time typed contracts, original film IR, factual/rights evidence, a persistent scheduler and media feedback are more reliable than implicit magical model knowledge.

## Architecture and contracts

- Intent and provenance: human brief; immutable fact ledger; source-rights and source-byte identities. No generated factual claim promoted to owner evidence.
- Creative handoff: unmodified artistic project plus typed Film IR for original shots, assets, timing, layers, cameras, voice performances and dependencies. No fixed genre/shot count/style/engine/format.
- Capability services: an inventory of actually installed and permitted operations. Detailed inputs and limits discovered only for the operation requested. Separate installed, needs_setup, blocked_by_cost, license_unknown and GPU_unverified states.
- Authorized tool routing: trusted registered adapters with explicit access mode, version, schema, resource requirements, media fingerprints and retry/idempotency semantics. Never execute untrusted shell/Python or install model-requested plug-ins.
- Physical execution: 2D motion compositing, Blender 3D, color/effects, digital audio, voice, actual assets, frame composition, FFmpeg and editable timeline. Real video generators are conditional physical plugins; no GPU => no fabricated film.
- Orchestration: dependency DAG, bounded concurrency, stage checkpoints, atomic output publishing, fail-closed permission gates, per-tool physical evidence, explicit pause/resume/retry.
- Observation: objective decoder/probe/QC; separate semantic and artistic film review. Feed precise failed observations back for scene-level revision without silently changing the original creative intention.
- Delivery: verified movie + audio + captions + editable timeline + original assets + source/rights/technical receipts. Immutable accepted output identity.
- User interface: authenticated local API, responsive phone operator console, eventually full owner-identity and secure remote access. The studio does not require ChatGPT in order to run.
- Future brain connection: the model asks which tools exist, requests one exact operation schema, invokes a declared operation, receives measured media evidence and iterates. This is a practical sensor/action feedback protocol without giant handbook prompting.

## Engineering release gates and sequence

### Already physically evidenced, preserve
Real free CPU 2D and true Blender 3D motion, composite/audio, complete movie decode, editable OTIO, original asset custody, process-death recovery, native wheel, authenticated local jobs, pause/restart/resume, local desktop GUI. Verify all this again after subsequent integration changes; unit green does not establish cinematic artistry.

### Workstream A: control and access
Mobile operator shell should have no token baked into HTML or persisted into web storage. Keep backend bound to 127.0.0.1, all production APIs on Bearer authorization, no model-directed installs, no CORS wildcard. Remote access only behind an explicitly configured owner-approved HTTPS identity-aware connection. The new branch introduces a phone-sized browser controller, but does NOT create a host, remote tunnel, chat or generative-film system.

### Workstream B: asset and project portability
Today's physical backup is tied to original absolute workspace paths. Implement stable content-addressed media references and a separate migration transaction. Rebind references only after verifying all original bytes and tool/codec versions. Do not blindly alter hashed SQLite records or reuse cache under different host conditions. Preserve archival proof.

### Workstream C: rich original film media
Extend multi-engine scene compositor and actual audio mixing with cinematic timing, responsive proxy previews, subtitles, original graphics, multi-channel timelines, genuine 3D and legally sourced motion footage. Use GPU generative footage only if the installed hardware, weights, runtime, license, output quality and budget are measured. Missing scenes remain missing; never silently downgrade to a generic moving card.

### Workstream D: long film reliability
Address checkpoint granularity (frame/segment), concurrent writers, leases after power loss, full disk, GPU OOM, interrupted publish, failed audit, corrupted checkpoint, cache drift, media relocation, distributed-worker race and retry safety. Prove actual kill/restart and cross-host restore; do not call best-effort CI caches durable infrastructure.

### Workstream E: quality loop
Technical gates: codec properties, frame-by-frame decode and timestamps, audio stream presence, loudness/clipping, readable text, factual references, shot continuity and edit alignment. Artistic approval remains a separate blind/human assessment of complete diverse films. A 323-test engineering suite does not certify global artistic quality.

### Workstream F: release
Independent zero-cost eligible execution path, Android-compatible secure UI, explicit rights and license controls, no fixed backend assumption, reversible upgrades, complete audit receipts, trusted plugin provenance, environment verification, operator-grade observability, verified editable projects, license manifest and regular end-to-end regression tests.

## Priority failure matrix
- Fake product facts, unaudited rights, uninstalled renderer, no verified GPU, insufficient compute or no owner-approved spend => blocked, never silently replaced with fabricated media.
- Unknown or non-idempotent step after crash => explicit operator recovery decision, never unattended replay.
- Dirty/missing cached media, new renderer revision, shifted fonts, modified source => invalidate affected dependency subtree.
- Network without HTTPS identity boundary => localhost only.
- Original creative film fails production => preserve original direction, report missing real capability and do not call technical fallback the authored film.
- Full-film quality unreviewed => do not mark professional creative release.

## External architecture sources rechecked
ASWF OpenTimelineIO documents editable cut metadata referencing EXTERNAL media, not embedding raw media; file adapters have feature limitations. Our media custody must accompany the timeline. https://github.com/AcademySoftwareFoundation/OpenTimelineIO
https://opentimelineio.readthedocs.io/en/latest/tutorials/adapters.html
https://opentimelineio.readthedocs.io/en/latest/tutorials/otio-filebundles.html
FFmpeg documents multi-source complex filtergraphs and explicit stream mapping. https://ffmpeg.org/ffmpeg.html
Cloudflare official docs describe secure private browser access by outbound tunnel + identity-aware Access; configuring it is separate from deploying a CPU/GPU body. https://developers.cloudflare.com/cloudflare-one/setup/secure-private-apps/private-web-app/

## Verified-vs-unverified policy
Never call a plan, tool manifest, attractive JSON, dummy video, model card, or passed test a finished original high-end film. Each claim requires recorded physical CI/media evidence, and premium creative quality requires independent judgment. Do not feed this engineering document to a creative model as its system prompt; query live tool contracts instead.
