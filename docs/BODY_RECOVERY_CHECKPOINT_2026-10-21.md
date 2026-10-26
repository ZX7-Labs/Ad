# ZX7 BODY — Recovery checkpoint (2026-10-21)

**Owner priority:** Deliver a genuinely production-grade, universal, open-source video **BODY** before revisiting AI Brain, script, or model selection. Preserve previously approved Supertonic M3/F2 voices and all older working/failed research samples. Android-accessible eventual studio, creative choices by director rather than arbitrary templates; never invent media or facts. Distinguish actual rendered quality from validated code.

**Repository truth:** `PROJECT_SCOPE.md`, `docs/MASTER_PLAN.md` and `studio_next/`. Root README has been removed; agency website is a separate effort. Earlier prototypes `src/film_v3.py` and `motion_studio/` do not meet universal production-grade standards.

## Verified implementation

This isolated branch `zx7-body/real-multitrack-renderer` / draft PR #2 has:
- `studio_next/media_body.py`: FFmpeg/FFprobe source verification, authored overlapping video/image/audio layers, variable canvas/timing, H.264/AAC MP4, video/source duration, stream and dimensions verification, local asset path safeguards, atomic exports.
- `studio_next/media_recovery.py`: content-hashed inputs and implementation, output integrity checks, exclusive locking, atomic manifest; invalidated media causes re-render.
- Actual FFmpeg integration and malicious-input tests and CI dependency installation.

**GitHub Actions proof:** https://github.com/oyzitjfzj/Ad/actions/runs/39594373322 — success; 50 tests passed. The prior initial run failed because its runner lacked FFmpeg; fixed.

**Local technical MP4:** 4 seconds, 720x1280, 3 layers/sources, H.264/AAC confirmed by ffprobe. A repeated identical render used verified cached bytes. Proof is not a polished creative film.

## Remaining before BODY acceptance

The present PR is unmerged and experimental. Still required: Film IR graph executor and trusted tool registry binding; owner-authorized rights/asset ingest; robust captions/type/FX; real 3D and specialist compositor adapters; multitrack editorial semantics; voice alignment/mastering; frame-level visual QA, render farm/recovery at scale, genuine multi-genre films, and human quality acceptance. No assertions of full production-grade state.

## Next-chat continuity

Inspect this checkpoint, PR #2, HEAD and latest tests, then **continue BODY execution**, not script/model research. Preserve historical media, refuse unlicensed/unavailable assets, maintain source provenance. Match source and actual MP4 evidence before changing status. Never promote failed quality to completion.

**Canonical PR:** https://github.com/oyzitjfzj/Ad/pull/2
