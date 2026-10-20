# Controlled 4B / 9B comparison and review-grounding repair

This is preproduction research. No model is promoted to the production editor on
the basis of a self-assigned score. No video, audio or reference-style match is
established by these text outputs.

## Controlled generation

[Original four-job run](https://github.com/oyzitjfzj/Ad/actions/runs/39432084613)
used source `8f78d05ba717b72eda437622ba7cc7e0bb8218e9`, the corrected literal
caption contract, visible schemas, seed 41, temperature 0.4, top-p 0.9, thinking
disabled, llama.cpp b11750, 16K context, and **zero revision attempts**. All runs
used standard Ubuntu CPU runners, four inference threads and the same prompts.
This isolates a first complete proposal rather than mixing in different repairs.

Both models use Q4_K_M, but different quantization publishers; these are single
trials on separately assigned runners. They are not a reliable general model
ranking or controlled hardware speed benchmark. Model bytes, pinned revisions
and SHA-256 values are retained beside each case.

| Model | Brief | Shots | Inference seconds incl. probe | Original score | Original outcome |
|---|---|---:|---:|---:|---|
| 4B | FOLD paper notebook, 18s | 6 | 257.54 | 4 | Blocked |
| 4B | NOVA software, 24s | 5 | 453.21 | 4 | Blocked |
| 9B | FOLD paper notebook, 18s | 3 | 373.71 | 6 | Blocked |
| 9B | NOVA software, 24s | 6 | 1340.14 | — | Complete draft saved; critic truncated at 700 tokens |

Inference timings exclude weight download, runtime setup and cache transfer.
Original critic scores are shown for auditability; the critic was demonstrably
fallible and its grades must not be treated as objective quality measurements.

## What the actual plans show

- **4B / physical:** the concept turns handwriting into a folded object on a
  traveler's lap. The spoken "Fold it" implies a folding property that was never
  supplied for this notebook. Several asset fields merely say `vector_shapes`,
  despite requiring a pen, train fabric, hand and traveler. A short valid caption
  contract alone does not make a detailed executable or truthful treatment.
- **4B / software:** the plan repeats chaos-to-calm geometry and asks for
  volumetric glow without an available implementation. That is a genuine
  capability mismatch. Its explanation rejects photorealistic 3D; a keyword hit
  on that negative explanation is an additional checker false positive.
- **9B / physical:** the waveform-to-white cut is simpler and more coherent, but
  the notebook itself is barely communicated: five seconds of noise, six seconds
  of a white field/line, seven seconds of CTA. There is no clear handwritten
  notebook action. That is a story/product-clarity concern, not impossible edit
  physics. No rendered result or audience judgement has been obtained.
- **9B / software:** a complete six-shot draft survived a critic that filled its
  problems list with repeated and incorrect objections until the token cap. It
  wrongly rejected allowed 2.5D and owner-reported copy. The hard checker also
  mistook an audience wanting a metaphorical "pause button" for a product UI.
  After the targeted checker fixes, structural QA passes this unchanged draft;
  creative acceptance does not follow from that. The film still repeats generic
  breathing-circle/lattice imagery. Its original error, raw truncated response
  and draft are preserved in `qwen35-9b-software/`.

The recovered [visual reference](../../../REFERENCE_STYLE.md) was **not** supplied
to these generation calls. They therefore do not evaluate reference adherence.

## Review/checker defects found in the real runs

Both physical proposals were hard-blocked for `instantly` inside visual prose.
The 9B text says the waveform "instantly cuts" to white. An instantaneous cut is
an available editing operation, not a promise of instant notebook performance.
The old critic then repeated that diagnosis as impossible physics. It also
treated animated text as incompatible with a static camera and called "the world
is too loud" an invented measurable product promise. Those criticisms are wrong.
Other real creative and execution defects can still exist in the same proposal.

The follow-up checker narrowly distinguishes adjacent animation timing verbs and
transform parameters from audience-facing product promises. Spoken/caption
claims remain checked; "instantly solves every problem" and visible unsupported
badges still block. Explicit nearby exclusions such as "No photorealistic 3D" no
longer request that effect. These remain lexical tripwires, not semantic proof.

## Evidence-linked review, version 2

The new reviewer is explicitly a motion-design/editorial reviewer. Every issue
must supply a real JSON-pointer path, an exact excerpt from that field, a concrete
reason, a category and a repair. Paths are constrained during generation; quotes
are checked afterward. False factual/execution flags require a corresponding
finding. A malformed or ungrounded review blocks acceptance and **cannot trigger
a rewrite of the proposal**. The model can still make a mistaken judgement about
a real quotation, so this is stronger traceability, not human-equivalent review.

The critic judges the proposal without being shown keyword diagnoses. Independent
hard QA still gates acceptance. The score threshold remains 8/10, with truthful
and plausible execution flags and zero findings. `render_ready` and
`human_quality_approved` remain false even after text approval.

`--proposal <saved-result.json>` now rechecks a saved plan without changing its
words or timing. It verifies that the original evidence exactly matches the brief,
requires a separate output directory and records a SHA-256 of the original file.
The original outcomes above are never overwritten by derived re-evaluations.
The [real 4B recheck of the unchanged 9B physical proposal](recheck-v2-4b/result.json)
completed in 307.31 seconds, excluding the 24.46-second runtime probe. Structural
QA now correctly passed the instantaneous-cut wording. The reviewer still made
poor criticisms and attached two quotations to the wrong fields. The new review
validator detected both, kept the result blocked, and preserved the original
proposal. This demonstrates rejection of ungrounded feedback, **not** a proven
quality critic. It used eight local CPU threads; its timing is not comparable to
the four-thread cloud trials. The [pinned 9B recheck](recheck-v2-9b/result.json) also completed, using
[the dedicated workflow](https://github.com/oyzitjfzj/Ad/actions/runs/39435559687)
at source `214b09ed7d75b37a0d47a371007719652d82fd97`. It returned a bounded
three-finding review but again misattached two quotations. The validator correctly
blocked it as `invalid_review`; no automatic rewrite was run. Both critics still
confuse some graphic edits with material simulation. Exact citations make those
errors inspectable; they do not make the critic a reliable creative authority.

## Current acceptance boundary

The physical 9B treatment is a better base for diagnosing review behavior, not a
selected production winner. We still need a compelling product-specific story,
feasible detailed assets, an executable scene representation and real visual/
audio review before connecting a premium autonomous editor. The project goal
and owner-approved voices remain as recorded in `PROJECT_SCOPE.md`.

## Requested real-video sample

The owner then explicitly requested an MP4. The agent authored a different FOLD
story and rendered it using the new [declarative compositor](../../../motion_studio/README.md),
with original notebook artwork, real accepted M3 speech and measured cut times.
That sample is **not output of either rejected local-model proposal**. Its
provenance is retained with the project. Building an executable, authored
scene graph is a concrete rendering milestone; automatic natural-language
direction and arbitrary-scene compilation remain unfinished.
