> **CONTINUITY FOR EVERY NEW CHAT:** Read [`ZX7_START_HERE.md`](ZX7_START_HERE.md) first. It contains the owner's complete non-hardcoded world-class autonomous filmmaking mandate, verified vs unverified milestones, model failures, experiment links, and the next autonomous decision. Do not ask the owner to repeat the project vision.\n\n# AD Studio — product goal and acceptance boundary

## Goal recovered from the owner's shared conversation

Build an open-source faceless video production system that feels like talking to
a skilled creative editor. An Android-only user describes a product or topic in
ordinary language; the system asks only the missing useful questions and decides
story, visual concept, art direction, purposeful depth/3D, camera, motion, captions,
voice, soundtrack and pacing. The intended output is a polished downloadable
video without the user having to learn editing terminology or write prompts.

The desired look is clear, restrained, premium, satisfying motion design with
strong storytelling. Repeated moving cards, a fixed scene sequence, vague slogans,
or an attractive JSON document do not satisfy this goal. Match the creative
purpose of references without copying a creator's work or inventing product facts.

## Existing constraints and decisions

- The owner works from a phone and requires a route with no paid API or
  subscription. Free infrastructure has practical limits; do not promise
  unlimited or continuously available compute.
- Keep project code open source and inspect licenses for models, inference code,
  assets, fonts and audio separately. Free access alone is not an open-source license.
- Approved Supertonic M3/F2 voice samples remain unchanged while the creative
  brain is evaluated. Naming a narrator in a plan is not synthesized audio.
- The agency website is a separate project. This repository is `oyzitjfzj/Ad`.
- Current priority is creative direction quality. The owner previously asked to
  focus on one capability at a time and not finalize a weak output just to proceed.
- Original source: https://chatgpt.com/share/6ad7603d-c49c-83ee-a35b-2931189c82c8
  The accessible share includes missing assistant answers and unavailable uploaded
  media. A related supplied **YouTube** screen recording was subsequently
  recovered and its sampled frames reviewed; see [REFERENCE_STYLE.md](REFERENCE_STYLE.md).
  Do not claim absent media, complete motion or audio were reviewed.

## What exists

1. V3 can render a category-aware seven-scene procedural video with Kokoro voice.
   It is a prototype, not an autonomous creative editor.
2. Earlier Director Lab can interview through owner GitHub Issues and propose a
   treatment using a local Qwen3 model. It is not the video renderer.
3. The Qwen3.5 research baseline produced complete but rejected treatments.
   See `director_research/BENCHMARK_FINDINGS.md` for measured failures.
4. The grounded experiment adds schema-constrained output, an adversarial runtime
   probe, a caller-owned evidence ledger, a primitive capability registry,
   adaptive 3–10 shots, retained drafts, detailed review and one bounded revision.
   It remains separate from the phone Issue interface and final video production.
5. The requested [motion sample](motion_studio/README.md) has a new declarative
   2D/2.5D compositor, measured Supertonic M3 narration and an agent-authored FOLD
   project. It executes authored scene graphs, not arbitrary Director prose. The
   sample must not be attributed to the rejected local-model experiments or used
   to claim the full autonomous application is ready.

## Conditions for connecting production

- A complete, specific and coherent proposal must pass factual and structural
  checks and a skeptical review. Same-model review is fallible, not independent
  model verification; automated scores cannot establish human creative quality.
- Compare actual outputs on distinct genres, including a software brief and a
  physical product, without forcing the same scene count or story structure.
- Compile accepted direction into an **executable scene representation** and
  verify every asset/tool dependency before saying the plan can be rendered.
- Render real visual samples and evaluate composition, legibility, continuity,
  motion, natural voice, music balance and actual audio-aligned timing.
- Keep owner taste approval separate from machine QA. If the owner dislikes it,
  investigate the failure instead of declaring the system complete.

The full consumer app, arbitrary production renderer, true 3D, visual critic,
reference-video analysis and completed premium end-to-end output do not exist yet.
Do not rename a planning milestone as the finished product.
