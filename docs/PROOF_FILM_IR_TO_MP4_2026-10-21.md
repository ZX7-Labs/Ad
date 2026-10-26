# ZX7 — Verified Film IR-to-MP4 Execution Proof (21 October 2026)

## Result

**SUCCESS:** [GitHub Actions run 39512086009](https://github.com/oyzitjfzj/Ad/actions/runs/39512086009) executed real FFmpeg rendering on a standard free GitHub CPU runner, after all unit and security contracts passed. ffprobe verified a **2.75-second 320×480 H.264/AAC MP4** with one video and one audio stream and scene IDs `open`, `turn`. Saved artifact: [compiled Film IR real MP4](https://github.com/oyzitjfzj/Ad/actions/runs/39512086009/artifacts/12305388688), retention 7 days. The artifact also includes compiler output JSON, manifest and preview frame JPGs.

## Added code

- `studio_next/motion_bridge.py` checks a complete, approved-asset declarative Film IR and converts it to the real original 2D/2.5D motion compositor's project format without inventing unknown text, media, footage or camera instructions.
- `studio_next/silent_audio.py` creates measured silence WAV timing only when a director specifically selected `no_voice`. It explicitly refuses to replace actual requested narration.
- Regression tests cover unsupported assets, unverified claims, nonexistent tools, model-supplied shell input, corrupt keyframes and unsupported font encoding.
- `studio_next/fixtures/vector_two_scene_film_ir.json` is independent illustrative vector geometry, not an AI-model-written story.
- `.github/workflows/studio-ir-to-mp4.yml` runs tests, compiles Film IR, renders audio/video, verifies media streams, retains evidence.

## Exact acceptance boundary

- This bridge is an **actual intermediate-representation-to-renderer execution milestone**, not autonomous language-to-visual generation. It only executes adequately specified original drawable art and motion.
- It cannot create product footage, scene geometry, arbitrary 3D, semantic visuals or Hindi text with the legacy Latin fonts. It blocks those cases honestly rather than silently substituting a slideshow.
- No generative model inference was called in this proof; creative quality and story causality remain unapproved.
- Pre-existing approved M3/F2 synthetic voice code/samples and main branch are untouched.
- The hard `0.5-60s` scene span and `1-60` scene count are **limitations of the current motion renderer** and must never become universal Studio limits.

## Next owner-independent engineering step

Run one real, pinned creative model on normal owner-language briefs and retain full outputs. Add a *film-art design pass* that authors actual drawable objects/positions/motion (with capability checks and fact ledger) from an approved direction. Route the resulting Film IR to this tested bridge. If model directions require true 3D, real footage, non-Latin fonts or image generation, use a different validated capability or flag unsatisfied requirements; do not force inappropriate 2D. Keep rendered/human quality review independent of schema and decoder success.

No new server, billing, third-party plugin installation or paid API was required for this milestone.
