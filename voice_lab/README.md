# Voice Lab (voice-only research phase)

**Do not use this lab to modify the video renderer yet.** We are benchmarking voice quality first.

[▶ Run a fresh voice A/B test](https://github.com/oyzitjfzj/Ad/actions/workflows/voice-lab.yml)

## Audition

Identical 24-word English narration is synthesized twice via:
- **Ryan:** rhythmically dynamic English male voice.
- **Aiden:** bright, sunny American male voice.

Engine: [Qwen3-TTS-12Hz-0.6B-CustomVoice](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice), Apache-2.0; no API key and no paid TTS subscription. Both voices are built in; no reference recording or impersonation is required.

Each generated ZIP includes `ryan-sample.wav`, `aiden-sample.wav`, and `comparison.json` with measured CPU runtime, output duration and sample rate.

## Script

> Most people think better ideas need more tools. They don't. They need room to breathe. Meet Nova, a calmer space for creative work.

Both are given the same expressive delivery instructions: warm, personal, confident, thoughtful, naturally paced, with short intentional pauses, avoiding robotic or radio-announcer rhythm.

## Quality gate

**Machine validations already implemented:**
- non-empty WAV, finite numerical values
- at least 3 seconds of speech, mono 24kHz output
- full response runtime measurement

**Human listening still required before choosing a winner:**
1. Naturalness and authenticity (not monotone, not forced hype).
2. Clear punctuation, real pauses and emphasis.
3. Accurate pronunciation: 'Nova', 'ideas', 'creative work'.
4. Vocal identity consistency from opening to finish.
5. Listening comfort at normal playback volume.

Don't choose a model just because it's faster. After selecting a voice, next steps are an open-source ASR transcription check and delivery testing on multiple scripts.

## Known limits

- Running the Qwen 0.6B model on free GitHub CPU can take over a minute to generate a ~10-second clip.
- Package downloads and free public runner execution are subject to availability and changing GitHub terms.
- No fixed output quality claims; TTS is probabilistic.
- Repo runs can be inspected under [Voice Lab workflow](https://github.com/oyzitjfzj/Ad/actions/workflows/voice-lab.yml).

Other researched models to evaluate if Qwen is insufficient:
- [Resemble Chatterbox Turbo (MIT)](https://github.com/resemble-ai/chatterbox)
- [CosyVoice 3 (Apache 2.0 repository)](https://github.com/QwenAudio/CosyVoice)
- IndexTTS-2.5 is not preferred for this strict permissive-license requirement, because it uses the separate bilibili Model Use License.
