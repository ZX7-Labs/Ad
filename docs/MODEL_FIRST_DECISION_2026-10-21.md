# ZX7 — Model-first correction after repeated 4B failures (21 Oct 2026)

## Why this decision is necessary

The owner correctly pointed out that repeatedly changing application code to accommodate a weak story-writing model is not the intended world-class creative architecture. We audited the actual historical runs, not just unit tests:

- 4B pinned `SoAIHQ/Qwen3.5-4B-GGUF` (Q4_K_M) repeatedly failed to deliver its own chosen story's correct scene identities/durations/facts through a complete creative-to-video run. Contract scaffolding cannot manufacture strong cinematic judgment.
- Existing 9B baseline `unsloth/Qwen3.5-9B-GGUF` **ran** in [39455528289](https://github.com/oyzitjfzj/Ad/actions/runs/39455528289) for 976s and wrote a five-scene, no-voice, 16-second FOLD treatment. Its JSON was structurally acceptable, but its own reviewer did **not** approve it. Its actual treatment had invented physical notebook details and invented/scarcely motivated human stakes, and the reviewer fabricated an alleged medical-emergency subplot that wasn't in the source. 9B is feasible on free CPU but **not validated as film-ready**. We must not repeat that mistake or elevate a number on the label to creative quality.
- Rishanth Rajendhran et al.'s **POLARIS-9B**, [arXiv:2606.04095](https://arxiv.org/abs/2606.04095), domain-adapts Qwen3.5-9B via GRPO with high-quality anchored original literary references. Their **reported blinded human preference** is 67.5% over the same base Qwen3.5-9B, and near parity with Qwen3.5-27B on *long-form story writing*, not cinematography, editing, 3D, truthfulness or completed cinema. Official [weights](https://huggingface.co/rishanthrajendhran/POLARIS-9B) are **gated**, metadata `license:other` and explicit usage/contact terms, NOT verified freely reusable permissive/commercial film weights. No terms acceptance or model download without permission. Its methods are relevant to a future small director specialist trained on rights-cleared film editorial material.
- [Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B) and [Unsloth GGUF](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF) are **Apache-2.0**, with already SHA256-pinned 5.68 GB Q4 weights, working on the existing public Ubuntu 24.04 GitHub Actions runner (4 CPU, 16 GB RAM). This is our only currently VERIFIED zero-added-infrastructure stronger than-4B test candidate; no extra servers or paid AI.
- OpenAI is not an intended paid model dependency. Existing Supertonic M3/F2 voices and all proven compositor/3D/FFmpeg production code remain untouched.

## Decision

**Stop treating 4B as a candidate production-quality director.** It remains a regression/baseline and a lightweight cost option only if evaluated as objectively adequate for a particular subtask. The film's original creative voice should come from the most competent validated legal model the verified budget allows, not from hardcoding scene corrections.

The next candidate trial is not yet a default migration: the stronger pinned 9B model is now running on two **dissimilar** briefs (actual FOLD notebook ad and DNS mechanism explanation) using one uniform open-ended, non-template Creative Director prompt. The model independently chooses shot count, runtime, story, medium, camera, sound, voice, and narrative structure. Output is archived untouched. This is workflow [39536516419](https://github.com/oyzitjfzj/Ad/actions/runs/39536516419).

The independent `studio_next/model_audition.py` and `test_model_audition.py` define this testing workflow. The parser checks that responses are complete and do not cite owner facts that don't exist. **It does not score artistic quality or dictate a particular cinematic style, format, scene count, visual medium or length.** The existing creative critic must not be trusted to review its own unsupported inferred events or to claim human approval.

**Selection requirements**: look at real written shots and original story on at least two genres, real audience impact, credible human stakes, non-fabricated product/technical mechanism, sensible visual continuity and clip production demands. Compare to actual failed 4B and prior 9B outputs, not generic mathematical benchmarks. Promote only if significantly better with explicit evidence. If the result remains disappointing, prioritize genuine domain-specific *legal* creative post-training/evaluation and access to legitimately free adequate inference compute; do not build further brittle film-specific JSON repair patches.

Retain essential security contracts: owner evidence/rights, declared timing, supported tools, privacy, license and billing checks. These are interfaces and guardrails, **not hard-coded creative direction**. Never confuse code-contract pass, generated storyboard, successful MP4 decoding, or human-accepted premium film.

## Current evidence boundary

The no-inference contract workflow [39536538235](https://github.com/oyzitjfzj/Ad/actions/runs/39536538235) completed successfully. The separate actual 9B audition is in progress; no conclusion about its creative quality or new autonomous MP4 yet. Research and source changes are isolated in `zx7-specialist-free-stack-20261020`, while `main` remains unchanged.
