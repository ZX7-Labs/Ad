# Film Direction Research — Qwen3.5 / CineCrew-inspired (experimental)

## Grounded Director iteration

`python -m director_research.grounded` adds a separate capability-aware experiment.
It preserves full art/sound/shot detail, chooses **3–10 shots** rather than a fixed
five-shot sequence, checks immutable owner-reported evidence, constrains model
outputs using JSON Schema, and allows **one complete revision** after a skeptical
review. Every draft, raw response and timing trace is retained. A timeout or critic
failure cannot erase a finished draft or turn it into an approved film.

The JSON-schema wrapper follows the pinned runtime's implementation in
[server-common.cpp](https://github.com/ggml-org/llama.cpp/blob/b11750/tools/server/server-common.cpp).
An adversarial runtime probe first verifies that constrained generation actually
works; JSON syntax alone is insufficient. Responses are then validated again with
`jsonschema`.

The available registry describes **primitive drawing/audio operations already in
the repository**, not an arbitrary-scene renderer. It cannot execute a free-form
film proposal. No renderer adapter, real 3D, fluid solver or media-rights system is
claimed. Known unavailable techniques, invented UI, unsupported promises,
missing evidence references, impossible narration timing and omitted CTA are
blocked. These lexical/structural checks do not prove semantic truth; the critic
can also be wrong. All expert roles currently use the **same local 4B model** in
separate passes. A `proposal_passed_text_review` state is not a rendered or
human-approved production result. `render_ready` remains false.

Run a local llama.cpp b11750 server with the documented Qwen3.5 GGUF, 16K context,
thinking disabled, and a stable model alias, then:

```bash
python -m pip install -r director_research/requirements.txt
python -m director_research.grounded --brief examples/sample-brief.json --out output/grounded/software
python -m director_research.grounded --brief examples/physical-product-brief.json --out output/grounded/physical
```

`--resume` reuses a checkpoint only when the model alias, prompt, full input,
schema and sampling settings match. Use a new alias when changing model weights.
The local endpoint is restricted to loopback HTTP; no hosted API or credentials
are used. Do not treat resumed elapsed time as a fresh speed benchmark.

[Two-genre cloud evaluation](https://github.com/oyzitjfzj/Ad/actions/workflows/director-grounded.yml)
is manual to avoid spending runner resources on every edit. It tests the fictional
software brief and a separate 18-second paper-notebook brief, retains blocked
plans, and fails the job if either proposal remains rejected. Structural regression
tests run independently without downloading a model. The current phone Issue
interface still uses the earlier Director Lab; this experiment is not silently
connected to that workflow.

This is an **isolated research benchmark**, not a replacement for the current Creative Director or Video Studio V3. It does **not** create video, render animation, use 3D tools, generate music or alter the owner-approved Supertonic voice samples.

## Research basis
- CineCrew (ECCV 2026) [Apache-2.0, upstream repository](https://github.com/Ironieser/CineCrew), FilmDSL idea: one explicit source of cinematic intent for each shot, shared assets, continuity, reviewer and repair.
- Qwen3.5-4B [official Apache-2.0 model](https://huggingface.co/Qwen/Qwen3.5-4B), independently [Q4_K_M quantized](https://huggingface.co/SoAIHQ/Qwen3.5-4B-GGUF). We use the GGUF TEXT path for this initial test: **the model's vision capability is NOT being evaluated**. Image understanding needs an appropriate vision projector.
- Recent llama.cpp [source and releases](https://github.com/ggml-org/llama.cpp). CPU inference, no external paid API.
- This program is independently authored, *inspired by film-planning concepts*. It is **not** a bundled or complete CineCrew implementation. All remote code/models remain subject to their licenses.

## Three-stage controlled experiment
1. **Director / art department**: generate concept, audience insight, metaphor, typography, camera grammar, lighting, 3D justification and music/voice decisions from truthful product briefing.
2. **Cinematographer / story editor**: generate detailed five-clip storyboard for a 24-second controlled test.
3. **Independent critic + deterministic validator**: challenge vague creative decisions; enforce narrator M3/F2, claimed facts, asset continuity, narrative roles, readable time, valid palette and total duration.

The benchmark compiles a FilmDSL-*style* structure with:
`{meta,assets,memory,clips[]}`, with every clip containing `action,staging,render,audio` layers.
It reports elapsed seconds per inference stage and stores both JSON and a human-readable full treatment.

## Experimental design caveats
- Five shots and 24 seconds are **fixed only for comparability in this benchmark**, not a proposed fixed template for the actual future creative engine. A final director must choose duration, pacing, narrative structure and number of scenes based on the idea.
- The test uses a fictional NOVA software concept. No claims about actual products or verified end-user utility are implied.
- A green CI result means the test reached the end and passed *defined* checks, not that human-level art direction was demonstrated.
- Claims may still evade keyword checks; reviewers may approve bad ideas; subjective creative quality must be judged by humans.
- Current model is text-only during the test even though the underlying model supports vision. Visual judging awaits separate benchmarks and image rights checks.
- CPU performance, free runner allowance and model downloads may limit practical usage; no unlimited free 24/7 host is promised.
- No user or third-party private references/audio are uploaded.

## How to run
From GitHub Actions, open [Qwen3.5 Cinema Director Benchmark](https://github.com/oyzitjfzj/Ad/actions/workflows/director-qwen35-research.yml) and choose **Run workflow**.
The resulting artifact `qwen35-director-filmplan-research` should contain `film_plan.json`, `storyboard.md`, server logs and/or `failure.json`. Failure must not be represented as a finished concept.

## Criteria before production integration
1. Full structured plan without truncation and meaningful concept.
2. The hard QA must pass: no unsupported claims and viable production strategy.
3. Reviewer has specific criticisms, not reflexive approval.
4. Owner judges the *visual story* against real creator/TV ad references.
5. Only then evaluate free quality-oriented image/video tools and integrate accepted M3/F2 voice options via a modular adapter. Keep original V3 untouched until those pass.
