# AD Voice Lab — Reference-first original voice development (Oct 2026)

**Status: research/specification, not production. No selected final voice.**
**Scope:** only the speech system. Do not modify video renderer while voice quality is unproven.

## User listening references

- Recorded tech Short originally supplied by project owner (73.45 s screen recording; social watermark `insiderforce.io`, English captions, tech product/tool explainer).
- User-preferred original AD Lab candidate: **Voice B — Cinematic Baritone**, though not final.
- User-preferred independent reference: second Tony Stark movie clip for relaxed confident, slightly witty dialogue. **Do not use film audio as voice cloning training data**, and do not imply endorsement.
- Additional vocal archetype: Indian TV advertising from Colgate and Lifebuoy, where story and brand emotion drive narration.
- Desired ChatGPT-like delivery: inviting, natural, emotionally aware, clear, reactive and easy to listen to.
- Voice identity may be male or female after anonymous listening test. No mandatory heavy/deep bass.

## Core finding

**Voice identity != voice performance != script quality != sound mix.**
Changing just the neural synthesizer will not create a good hook, expert explanation or motivated emotional narration.
For short-form content the content director must align emphasized words with the actual edit.
The audio recording is a *mixed screen recording*, not an isolated voice stem: cannot identify the original narrator or measure clean voice pitch/tempo reliably from this mixed file.

## Target identity (not a specific real person)

Unique warm low-to-mid register, natural brightness and clear articulation; confident, observant, human, conversational, with smart controlled shifts from dry wit/curiosity to revealing an important point. No fake growling, exaggerated 60 Hz bass boosts, announcing, breathless hype or robotic monotone.

## Proposed components

`Narrative Planner`
: Writes a content-specific hook, what matters, a useful revealing detail, and a payoff; never auto-inserts hyperbole without evidence. Emotional words such as "amazing" and "crazy" belong here **only when genuinely earned**.

`Performance Director`
: Convert sentences into phrase-level performance instructions (calm/curious/reveal/warm/urgent), emphasize semantic focal words, planned breaks, rate and pitch curves. Use pronunciation dictionary for brand names. Keep one recognizable vocal identity across modes.

`Voice Engine (reference-first)`
: **High-quality teacher for development**: Qwen3 VoiceDesign 1.7B (Apache-2.0). Not practical for realtime CPU on a small cloud machine: prior 13.52 s sample required ~452 s synthesis on GitHub CPU.
: **Candidate student/runtime**: Kyutai Pocket TTS 100M (MIT code; CC BY 4.0 weights plus acceptance of model access terms), CPU-oriented, streams, voice conditioning; public training code released Aug 2026.
: **Alternative runtime**: Chatterbox Nano / Turbo (MIT code); current Nano audition wasn't accepted, so not automatically selected.
: **Multilingual**: Pocket TTS lists English, French, German, Portuguese, Italian, Spanish; **not Hindi**. Do not claim Hindi support. Evaluate a separately licensed Hindi path later.

`Mastering`
: Transparent EQ and corrective de-esser (as needed), phrase-spacing, compression, loudness and true-peak checks, low background music in final mix. **Do not pitch-shift a bright voice and label it cinematic**.

`Quality Gates`
: Same three scripts through every candidate. (i) 30s creator explainer, (ii) 30s relatable brand commercial, (iii) short assistant dialogue. Later Hindi separate engine. Record actual output for subjective listening; blind A/B without model names.
: Test script wording, pronunciation of nonstandard words, audible hesitation, emotion shifts, intelligibility, clipping, silence, consistency, CPU latency and correct legal permissions.
: Candidate is production-ready only when owner approves the **real edited context** and objective checks pass; theoretical model quality doesn't imply narrator quality.
: Optional ASR re-transcription for WER; note that it measures intelligibility, not charisma or expressiveness.

## Create our own lightweight voice: feasible paths

**Path A — practical right now, no GPU training:** distinct branded **voice profile** combining author-owned/licensed consenting voice reference and a permissive base TTS. Store voice conditioning state/preset plus performance-director rules. This is a branded voice configuration, NOT yet a separately trained model.

**Path B — true custom branded model:** properly licensed, consenting actor recordings and transcripts; fine-tune a pretrained teacher on clean target speech and distill to a small student for CPU. The Pocket TTS official guide provides `finetune.yaml` and `depth_distill.yaml`, but GPU training is needed. Their scratch recipe says 200h yields intelligible speech and ~2000h high-grade baseline; this is not a claim that a small single-speaker finetune always needs exactly 2000h. A reliable fully-free GPU training allocation is NOT assured.

**Path C — train everything from scratch:** not a practical free/mobile project milestone. Avoid spending limited compute here.

## Licenses / consent

- **Do not upload third-party YouTube/movie/TV reference recordings into this public GitHub repository.** Use for style analysis and testing only.
- No cloning identifiable speakers without their explicit permission; do not clone famous actors.
- Check code licenses, model licenses, dataset rights, and voice actor performance consent separately before app launch.
- Model download access agreements may require manual authentication; do not commit tokens or private voice references.
- Open source code does not itself imply a guaranteed free hosted cloud service or unlimited GPU.
- Attribution required for Pocket TTS CC BY 4.0 checkpoints if reused/distributed.

## Verified sources

- https://github.com/kyutai-labs/pocket-tts
- https://huggingface.co/kyutai/pocket-tts
- https://github.com/kyutai-labs/pocket-tts/blob/main/training/README.md
- https://github.com/QwenLM/Qwen3-TTS
- https://github.com/resemble-ai/chatterbox

## Next engineerable milestone

1. Obtain a consenting, properly licensed/owned original human voice reference (optionally commission a voluntary public-domain/CC0 recording with explicit voice-model rights).
2. Evaluate **one** baseline on three context-specific scripts and blind listen in realistic video mix, rather than a stream of unrelated 8-second samples.
3. Fix script/prosody before trying another model. Consider Pocket TTS gated terms, account access and any actual free GPU availability before claims of training.
4. Only after quality acceptance add a versioned, modular `voice_engine` API into the app. Don't touch production video until then.
