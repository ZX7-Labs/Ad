# ZX7 BODY — Source-attested reversible timeline editor

**Written:** 22 October 2026. **Repo:** `oyzitjfzj/Ad`.
**Active draft branch:** `zx7-body/mobile-operator-20261021`, PR #3. **Main remains untouched.**
This file records a verified technical subset, **not** completion of the film studio.

## Original contract and versioning
`body.timeline_revision` is an installed discoverable BODY capability implemented by
`studio_next/body_timeline_revision.py`. Typed input:
`{"plan":"relative-original-plan.json","operation":"relative-editor-decisions.json","out":"new-original-film.mp4"}`.

Each plan is an existing `body.sequence_cuts` schema with exact rational FPS,
width/height, and only physical MediaVault original shots:
`source=zx7:sha256:<digest>`, `asset_id`, `attestation_id`,
first decoded frame, exclusive end decoded frame, and explicit
`preserve_source` or `intentional_silence`. MediaVault actually checks original bytes,
custody and actual video. Sources must be tagged BT.709 and true CFR on this adapter.
Unknown source formats are blocked, **not** converted or substituted. Original
audio for moved and split shots remains explicitly attached to the same source range.

The director supplies a JSON object of one to 64 independent operations:
- `{"kind":"roll","at":0,"delta":2}`: move a boundary by exact signed source frames in both adjacent original shots; total runtime unchanged
- `{"kind":"slip","clip":1,"delta":-3}`: move the underlying original media window without changing the clip timeline length
- `{"kind":"slide","clip":1,"delta":2}`: keep selected source window, extend the previous shot and shorten following shot by the chosen exact frames
- `{"kind":"ripple_trim","clip":1,"edge":"in","delta":3}`: change an original in/out frame and ripple the total timeline duration, preserving following source identities
- `{"kind":"split","clip":1,"offset":5}`: split a source window into two separate original source-range clips with independent future editability
- `{"kind":"reorder","clip":1,"to":0}`: move a full source window and soundtrack into a different ordered cut position

All values are physical frame indices, not seconds rounded into approximate container durations.
Each edit is applied to a deep copy, validated for exact original frame bounds,
and verified with real native FFmpeg render + full decoded CFR, BT.709 and actual audio.
The original authored plan, actual original media and earlier approved masters remain
unmodified. Successful editing stores an immutable canonical new plan at
`.zx7-timeline-revisions/<SHA256>.json` and returns its relative path, SHA256,
original plan hash, operation hash and frame-count history. This revision is a normal
legal `body.sequence_cuts` input and can itself be edited again, without guessing
creative styles, video subjects, voice, pace, color or duration. The whole source/
decision fingerprint is included in cache invalidation.

A mutated decision or original plan during render, changed original source bytes,
out-of-range frames, invalid editorial arguments, revision store overwrite, output
overwrite, and mismatched physical decode cause refusal and cleanup rather than an
approved counterfeit film. Per-workspace archive and portable owner restore retain
the SHA-indexed revision plans and the original source evidence.

## Exact verified CI, quality boundaries
- **First accepted code commit:** `ef920794200a839e72b1192a9e938a842440d79e`
- [Integrated native build 39769719050](https://github.com/oyzitjfzj/Ad/actions/runs/39769719050): **448 tests; 447 succeeded, 1 separate real Chromium test skipped as designed**; installed wheel + actual Blender 3D/2D, audio and editor proof passed.
- [Chromium phone-width browser run 39769718980](https://github.com/oyzitjfzj/Ad/actions/runs/39769718980): SUCCESS on matching first accepted code.
- Follow-up code/test commit `8ad96f9954aab62b411a1af7f43082d83d942c91` adds real opposite-host project restore/render, mid-render edit-instruction tamper denial and canonical plan overwrite denial. Matching [CI 39770332570](https://github.com/oyzitjfzj/Ad/actions/runs/39770332570) must be separately checked before claiming that increment passed.

## What this does NOT prove
This adds exact independent hard-cut editorial operations only. It is not a complete
multitrack professional timeline: transitions, nested edits, moving masks, advanced
curve retimes, optical-flow, cross-app conform/proxies, source-independent frame
crossfades, scene-linear OCIO/ACES, all sound mastering and fully interactive NLE
canvas remain different release tasks. This BODY operation does **not** choose music,
story, voice, narration or visual layout. Artistic quality across real independent
films and remote persistent Android HTTPS are **not** certified.
Global status remains **0/12 completed final subsystem gates**, 10 partly verified,
two primarily blocked. Never label passing technical tests as elite-editor quality.
