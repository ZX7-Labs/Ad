# AD Director Lab — Creative brain (experimental)

**Status:** conversational creative planning only. It does not yet generate, edit or render video, and it is **not** the existing V3 renderer. The V3 pipeline and approved Supertonic M3/F2 voice tests remain unchanged.

## Talk to it from Android

[Start a natural conversation with the Creative Director](https://github.com/oyzitjfzj/Ad/issues/new?template=talk-to-director.yml)

Describe the product, topic or idea in normal words. You do not need any editing expertise or a long prompt. The public GitHub Issue launches a free CPU model job for the repo owner; if a crucial detail is missing, the Director replies **DIRECTOR QUESTION** in the issue. Reply in the same issue, in natural language, and the Director restarts with the updated conversation.

When a plan is available, it leaves a comment linking the GitHub Actions **director-creative-treatment** downloadable artifact containing:

- `treatment.md`: unique concept, spoken hook, voice selection, art direction, each shot's timing, camera, motion, proposed 3D (if justified), transitions and audio cues.
- `director_result.json`: machine-readable treatment, the independent critic feedback and hard validation results.

**Privacy:** this is a *public* repository. Everything you write in the issue is visible. Never post customer data, unpublished campaign secrets, or API keys. The issue runner only responds to the repository owner's `[DIRECTOR]` issues and owner comments.

## Internals

- `prompts.py` — natural intake, creative strategist, independent critic and repair roles.
- `gates.py` — deterministic checks. Unsupported marketing facts, impossible narration pacing, incorrect total duration, unlicensed real footage assumptions, and unknown narrator are blocked.
- `__main__.py` — single local CPU Qwen3 4B Instruct Q4_K_M GGUF model, acting in sequential roles; never pretends that critics were approved if audit fails.
- `test_director.py` — fast no-network regression tests.
- `compiler.py` — safely unwrap nested JSON and normalize shot timings to spoken words before rechecking claims.
- `.github/workflows/director-lab.yml` — model setup, tests, offline inference and issue comments.

Model: [bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF](https://huggingface.co/bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF), based on Apache-2.0 Qwen3-4B-Instruct-2507, quantized approximately 2.5 GB. Initial 1.7B prototype gave incomplete shot timing and malformed review output, and was rejected. Inference: [llama-cpp-python](https://github.com/abetlen/llama-cpp-python), MIT. No cloud API key and no subscription required, but free GitHub Actions minutes and caching have real platform limits.

For local work (Linux/PC), Python 3.11, C++ compiler and OpenBLAS:

```bash
python -m unittest discover -s creative_director -p 'test_*.py'
python -m creative_director --brief examples/sample-brief.json --model models/director/Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf --out output/director
```

## Why this is not yet a professional final editor

A creative-plan JSON and automated critique are not a complete movie. AI can produce generic ideas, unsupported implied claims, uncertain visual feasibility or missed nuance even when structural checks pass. This must be judged using *real artifacts* before integration with voice, 3D and motion renderers.

What has **not** been built yet: production visual asset generator, a live editor timeline, real 3D quality, finished motion graphics, real voice timing alignment, automatic footage rights verification, guarantee of creative quality, or publication as a consumer app.

**Current milestone:** prove a non-generic, safe, coherent, shot-specific preproduction treatment from natural owner conversation. Only after this works should renderers be connected.

## How the director behaves

Input → (one conversational clarification if needed) → story strategist → shot-by-shot production proposal → independent critic + hard QA → one repaired revision if needed → reviewed proposal.

**Blocked** plans remain available for inspection, but are never called approved. "Best human creative director" is the aspirational quality bar, not a current verified capability.
