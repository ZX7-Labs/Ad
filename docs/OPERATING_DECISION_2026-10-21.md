# ZX7 operating decision — 21 October 2026

## One execution plan (supersedes server-shopping priority; does not remove existing research)

The objective is a premium-quality, Android-accessible conversational video maker using free/open-source software and weights whose terms actually permit the intended use. The user should not pick models, shot counts, engines, prompts or deployment approaches. Do not force a fixed template. Do not claim fully autonomous editing before rendered samples receive quality approval.

### Evidence re-verified on 2026-10-21

1. Old model execution is NOT a many-server design. The repository workflow `.github/workflows/studio-script-9b-reference.yml` on `studio-vnext-independent-proof` uses **GitHub Actions ubuntu-24.04**, pinned GGUF fetched from Hugging Face, SHA256 verification and local **llama.cpp** HTTP endpoint on localhost. Free standard public-repo runner CPU is the proven pattern. Example: https://github.com/oyzitjfzj/Ad/actions/runs/39455528289 . It is CPU-heavy (~16 min for one 9B creative workflow), and the script failed creative acceptance.
2. Hugging Face OAuth connector authenticated (free personal account) and Jobs list works, but **Hugging Face Jobs is a billed container compute product**. Do not launch Jobs assuming free compute or request another server. HF is currently a model catalog/download and read-only research connection, not a verified free GPU backend.
3. Cloudflare connector authenticated. Read-only AI model catalog works; candidate free-tier model names include `@cf/zai-org/glm-4.7-flash`, `@cf/google/gemma-4-26b-a4b-it`, and `@cf/openai/gpt-oss-20b`. Official Workers AI free tier allocates 10,000 neurons/day to eligible models; some large models are paid-only. **Account-specific billing plan/balance endpoints returned 403 due OAuth permission scope.** Therefore none of these candidates was called, and their eligibility/quality on the current account remains unverified. Cloudflare is optional, not a requirement to replace GitHub.
4. Hugging Face model metadata confirms ShotVL-3B cinematography fine-tune (3.75B total parameters), Q-ReAlign Mini visual quality assessor (~1.11B total parameters in metadata), ScriptAgent (~10.73B adapter-oriented). These are specialist **research tools, not the complete creative brain**. Avoid model sprawl: do not install all three. Individual title/parameter count isn't quality proof.
5. Plugin directory lookup found Hugging Face installed and Render available to install, but **no verified better zero-cost general GPU server plugin**. Render requires separate hosting-plan evaluation; do not ask owner to connect speculative services.

### Deliberate operating order

**A — Freeze what works:** Keep existing V3, 2D/2.5D compositor and approved Supertonic M3/F2 sound. Preserve all source/artifact proofs; do not overwrite `main`. Retain existing `studio-vnext-independent-proof` architecture and security checks.

**B — Improve one brain, not run a zoo:** Reuse the existing pinned, free GitHub CPU evaluation path with Qwen3.5-4B as a baseline only. First fix the *specific* writing problems observed in the saved FOLD and DNS stories: causal link to product, factual semantic truth, non-formulaic distinct premises, reasonable executable shots, reviewer citing wrong details. Quantitative structural scores are necessary but not quality evidence. Compare a *single* clearly stronger licensed candidate to that same baseline only when its compute fits the runner. No blind model promotion.

**C — Close the compiler gap:** Convert one accepted treatment into the existing machine-checkable Film IR and registered real 2D/2.5D compositor + FFmpeg pipeline, retaining original direction/shot choices. No model-authored shell; typed allowlisted tools only. This is the biggest gap between JSON and film.

**D — Real proof:** Render **two genre-different videos** from ordinary input without hard-coded manually-authored shot graphs. Inspect actual video and audio for script meaning, voice timing, shot relevance and quality. Automatically repair precisely located issues. Human preference remains separate from measurable technical gates.

**E — Add specialist only when a demonstrated bottleneck demands it:** Consider ShotVL if poor shot semantics persists, Q-ReAlign if visual IQA needs model judgement, an optional GPU still/video generator only for visually necessary scenes after hardware, rights and cost are verified. Different tasks can use same orchestration rather than separate always-on servers.

**F — Delivery:** Phone-friendly chat/task-queue interface with status, resumable proofs, video playback/download; separate website from studio application. Release only after all rights/security/provenance/tests and owner quality acceptance.

### Rules for changing plan

New information may revise sequence, but **preserve all scope and capabilities**, don't drop a previous stage because of a new suggestion. Distinguish `tested`, `installed`, `potential`, and `blocked`. Free must be demonstrated, not estimated from a marketing page. Don't ask owner to choose one of many technologies; ask only for permissions/access that cannot safely be inferred. No cloud inference, account upgrade or public media upload without verified zero cost and authorization.

### Current audit boundary

This file is a recorded planning decision; it did NOT install new weights, provision compute, invoke Cloudflare AI, or render a new film. The first real next test is single-model creative-output quality on existing GitHub Actions, followed by an executable compiler slice. 
