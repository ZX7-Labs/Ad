# ZX7 BODY — cross-branch consolidation and actionable release truth

Reviewed 23 October 2026. **One canonical engineering head:** `zx7-body/mobile-operator-20261021`, Draft PR #3 into `zx7-specialist-free-stack-20261020`. Do not merge to `main` or deploy an external owner console without explicit approval. This is a permanent short checkpoint for model/engineer handover, **not** a giant prompt to read during a movie render.

## Branch inspection — facts vs missing equivalence

| Branch | Relationship to active branch (exact GitHub compare) | Action |
| --- | --- | --- |
| `main` | Ancestor; active branch +638 commits at previous HEAD comparison; no main changes | Preserve |
| `director-grounded-planning` | Ancestor, 0 unique commits versus active branch | Preserve historical story/owner decisions |
| `studio-vnext-independent-proof` | Ancestor, 0 unique commits versus active branch | Preserve physical historical tests |
| `zx7-specialist-free-stack-20261020` | Active Draft PR #3 base, 0 unique commits | Preserve base and original voices |
| `zx7-body/live-signal-contract-20261021` | Diverged, **one unique** `body_signal.py` commit; other branch ~276 commits behind active | Reconcile semantic contract into canonical BODY. Do **not** cherry-pick stale worker or duplicate catalog. |
| `zx7-body/real-multitrack-renderer` | Diverged, **ten unique** original changes; alternate `media_body.py`, `media_recovery.py` and tests | Retain Draft PR #2 for provenance. Compare concrete feature contracts, not module names. |
| `zx7-body/mobile-operator-20261021` | Active canonical stage, latest independent native/security CI required | Deliver edits here only, no automatic main merge |

Git history comparison is directional: a branch can contain a different file with useful semantics even if current main development has many more commits. **No abandoned feature is presumed incorporated merely because another module has a similar name.**

## Reconciled implementation and verification

1. **Live creative BODY interface.** Independent live-signal `discover/describe/observe/command` semantics were implemented as `studio_next/body_signal.py` on the active branch. The canonical adapter delegates instrument discovery, selected typed contracts and physical source preflight to `BodyAffordanceSurface`, delegates factual job feedback to `sense_body_job`, and delegates mutations to the existing `LocalBodyCoordinator` and its durable Film IR graph. **Explicit host-owned workspace allowlisting** now prevents a single agent from observing or retrying another owner's workspace job. It neither fabricates a verified MP4 from a job status nor gives the model paid/network/shell rights. `test_body_signal.py` tests the real controller with blocked source, permissions and owner-isolated jobs. This is a Python model-facing adapter, **not MCP compliance or a deployed real remote agent**.
2. **Alternative generic composer.** Alternate PR #2 included timeline clips with independent audio tracks, alpha, layer positions and owner-authored still-image overlays. The current `body.composite_mix` is stronger for versioned rights attestations, sealed immutable CAS source bytes, full-decoder validation, native keyframed motion, chroma, original independent audio clocks, gain automation and safe no-clobber publication; the old standalone `media_body.py` does **not** have equivalent current legal custody and should NOT be reactivated as a second production authority. Its missing **still-image-to-native-moving-layer** semantics were transferred into the current compositor as opt-in `source_kind="still_image"`: genuinely decoded and exact SHA256-bound PNG/JPEG/WebP sources, physical source trim 0, unchanged soundtrack, real video render and refusal to claim unsupported color management. Tested on actual pixels and sound. This eliminates useful feature loss while avoiding two editing engines with contradictory rights policies.
3. **Alternate recovery.** Alternate PR #2's original `render_resumable` used a single-process `fcntl` lock, an output hash and a sidecar JSON; the canonical durable DAG has stage identity, input fingerprints, lease renewal, crash journal and editor/source rights checks. Automatic merge would weaken or duplicate safety. **Formal pairwise performance tests and migration of old sidecar checkpoints remain open**; the original branch is retained, not deleted.
4. **Native release.** The most recent 476-case integrated baseline before consolidation is [39813513431](https://github.com/oyzitjfzj/Ad/actions/runs/39813513431), 475 passed plus one independently run browser skip, matching actual code `1ffd5173614482f15ac7915546b06451609d93f5`. Current post-consolidation commits require **their own** matching native and security CI; never borrow this historical green status. Dedicated real source-custody CI runs physical video/audio/Pillow tests with zero skips.

## Decision boundaries for the final film

- **Technical accepted:** only exact code-matching successful real movie, source license, CAS, decoder, audio, full render output, crash repeat and access controls.
- **Creative accepted:** distinct original project, real source and unaltered owner decisions, professional scene/sound review, actual observed revisions and consent for copyrighted external materials. No unverified photos/actors or model-produced camera shots are invented as rendered footage.
- **Release accepted:** 12 subsystem gates (see `ZX7_BODY_VERIFIED_PROGRESS_MATRIX_2026-10-22.md`) must each pass their independent full acceptance. Right now **zero of 12 have passed entirely**; ten have meaningful partial technical foundations and two are principally blocked (real rights-cleared generative footage compute and external creative acceptance).
- **Work in progress is not a master:** a visual proof made from free original vector/physical media demonstrates working technical machinery but does not prove world-class autonomous scene direction, full non-destructive NLE, OCIO/ACES, cross-host render farms, real external Android usage, or a licensed original live-action actor.
- **No human prompt handbook:** a future model sees only the selected on-host affordance, compact operation schema and observed result, not all project markdown text.

## Future engineering acceptance required before universal studio sign-off

A. Final open NLE with image/video/audio interleaving, nested sequences, exact rational video frames and audio samples, transitions, masks, trims, professional revision and OTIO round-trip **without silently dropping anything**.
B. Full scene-linear VFX/OCIO-ACES/OpenEXR pipeline tested by pixel reference and multiple source color spaces; verified animation and original camera/storyboard control.
C. Real semantic pixel/audio/temporal observation, independent comparison to director objectives and selective editable rerender proven on multiple unrelated original media projects.
D. Real installed and license-verified model weights plus authorized GPU or artist-provided footage; block absent actor/product source rather than silently making a proxy.
E. Hardened persistent owner-approved HTTPS remote Android infrastructure with privacy, backups and resource budgets; true distributed worker interruption/restart and signed per-job history.
F. Independent professional evaluation of several complete original films; verify title/shot/continuity/sound/visual design in the physically exported video rather than relying on test count.

No two-hour documentary or false 100% completion percentage is inferred from code alone. Existing creative source film The Fold and approved M3/F2 voice choices stay unchanged.
