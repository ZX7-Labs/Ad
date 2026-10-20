# Grounded Director — measured review, 20 October 2026

The engineering experiment runs, but **this configuration is not accepted as the
finished creative director**. Both full evaluations remained blocked after one
revision. A local caption repair subsequently passed structural checks; this is
not a new complete creative evaluation or a finished video.

The owner wants a premium conversational video editor, not a fixed scene template
or a storyboard document. That product goal is retained in
[PROJECT_SCOPE.md](../../../PROJECT_SCOPE.md).

## What was implemented

The isolated Director now has schema-constrained JSON plus post-validation, an
adversarial runtime-contract probe, an immutable owner-reported evidence ledger,
an explicit registry of existing drawing/audio primitives, adaptive 3–10 shots,
full concept/art/sound/shot instructions, a separate skeptical review pass, one
bounded revision, resumable request checkpoints, and retained rejected drafts.
These mechanisms do not establish professional creative quality or an executable
arbitrary-scene renderer.

The pinned runtime requires `response_format.json_schema.schema`. The earlier
README-style sibling `schema` was silently ignored. This was found in an actual
local call, checked against b11750 source, corrected, and verified with a forced
sentinel-output probe. The runtime and model provenance are in
[provenance.json](provenance.json).

## Full cloud evaluations

Both genres ran on the same pinned Qwen3.5-4B Q4_K_M weights, text-only CPU
inference, 16K context, four threads, reasoning disabled, and one revision.
Every role uses the same model in separate passes. This is not independent-model
verification. The original evaluated source revision is
`d8ed4e4311e413b61688ebbde9c688315de3737b`.

| Fictional brief | Target | Initial → revised shots | Model critic score | Inference time, including probe | Outcome |
| --- | --- | --- | --- | --- | --- |
| NOVA software | 24 s | 5 → 5 | 4 → 4 | 1,220.00 s / 20.33 min | Blocked |
| FOLD paper notebook | 18 s | 5 → 4 | 7 → 5 | 957.47 s / 15.96 min | Blocked |

Times are sums of real inference-stage timings, excluding runner setup/download.
They are not video rendering times. These latencies are too high for claiming a
fast interactive production experience from this configuration.

[Cloud run and original artifacts](https://github.com/oyzitjfzj/Ad/actions/runs/39426895058).
For durable inspection, the original treatments, initial drafts, both reviews and
timing traces are retained here:

- [NOVA treatment](software/treatment.md) and [original result](software/result.json).
- [FOLD treatment](physical/treatment.md) and [original result](physical/result.json).

The original failed outputs are preserved without changing their scores or
rewriting them to look successful.

## What the actual outputs revealed

The FOLD first draft passed structural checks and received 7/10 from the model
critic. Its revision put visual staging paragraphs into the caption field and
reduced the critic score to 5/10. A full rewrite can make a valid draft worse.
The critic also suggested reducing reading time to improve legibility and demanded
product photos to validate an explicitly illustrative concept. Those are not
reliable production instructions.

NOVA's revised shots were all labelled `proof`, including the opening and CTA.
Several captions were visual descriptions rather than actual screen copy. The
checker also incorrectly treated animation parameters such as `80% scale` as
marketing promises; the model critic then repeated that mistaken diagnosis.
This was a checker defect, not evidence that the product made a percentage claim.

There is still no image-based judgement, asset execution or measured voice
alignment. Even a structurally valid plan can be generic, unattractive or
physically incoherent. The model's self-rating does not decide owner taste.

## Follow-up fixes and their precise scope

The generator now sees the output schema as text as well as receiving constrained
decoding. Captions have an explicit six-word / 70-character contract. The first
regex used `\S`, which b11750 does not support; the runtime emitted a conversion
warning. It was replaced with explicit character classes supported by that
runtime. A separate adversarial grammar probe checks that longer requested copy
cannot bypass the six-word constraint.

Percentage checks now distinguish explicit adjacent visual transform parameters
from spoken/caption claims. A visible `100% better` badge or caption still blocks.
These fixes address observed format/checker defects; they do not turn the archived
two-genre failures into passing creative evaluations.

The targeted [caption patch probe](caption-patch-probe.json) produced:
`Ground the thought.`, `Keep it real.`, `Pocket size. Handwritten.`, `MEET FOLD`.
Replacing only those fields in the rejected FOLD proposal passed structural QA.
The model was not asked to re-evaluate the complete revised film, and no visual
quality approval is claimed. The additional runtime grammar evidence is in
`caption-grammar-probe.json`.

The follow-up regression suite has **42 passing checks**: 29 research checks and
13 existing Director Lab checks. Tests cover real failure modes, including critic
crashes, immutable evidence, unsupported UI/techniques, narration timing, bounded
repair, caption paragraphs, percentage false positives and claims hidden in badges.

## Decision

Keep this as an inspectable development engine. Do not connect this particular
model/reviewer configuration to automatic final-video approval. The evidence
supports improving semantic planning and reviewer reliability, testing stronger
local backends, and replacing blanket rewrites with verified targeted corrections
before production rendering. The original V3 renderer and accepted voice samples
were not changed. No new finished MP4 was generated in this work.
