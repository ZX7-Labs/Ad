# Voice identity decision — 2026-10-20

## Accepted direction, preserved
The project owner liked **both Supertonic 3 M3 (male) and F2 (female)** in the identical tech-explainer test. These are the first two voice characters accepted for further finishing. Keep both available, without changing their natural speaking cadence, rate, words, pauses or pitch.

## Subtle finishing under review
Use `voice_lab/studio_finish.py` on the original unmastered WAVs. The process applies about 1 dB tonal corrections, a light 1.35:1 compressor, and -16 LUFS loudness. Do not replace raw audition files; ship both processed and source WAVs for A/B. The finishing variant is **not yet user-confirmed**: let user listen before marking it final.

## Default options
- M3: adult male English creator/narration, tech explainers and product demonstrations.
- F2: female English conversational creator, approachable explanations and some consumer storytelling.
- Do not infer that gender itself decides creative effectiveness. The director should choose depending on tone and script or offer a preference.
- Avoid vocal cloning of any named real creator or actor.
- Before public commercial deployment, verify archived Supertonic weights' BigScience OpenRAIL-M terms, redistribution obligations and any access conditions. MIT code license is not the weights license.

## Performance benchmark
GitHub run [39410775699](https://github.com/oyzitjfzj/Ad/actions/runs/39410775699):
- Generates both M3 and F2 samples successfully with 99M-param offline model.
- Runs `studio_finish.py` and validates finished mono MP3 files.
- Keeps raw 44.1kHz WAVs, comparison audio, and polished MP3s in downloadable ZIP.

## Honest integration status
**Video Studio V3 still uses older Kokoro**, not these accepted Supertonic voices. Do not claim the final app has changed voice. During the upcoming storytelling rebuild, wire M3 and F2 through one modular voice adapter and allow a simple voice selection. Avoid revising video rendering until narration scripting and story logic work well.

## Next milestone: story-first creative direction
The app should ask just enough questions to understand product/topic, audience, benefit or thesis, voice mood and intended action; then assemble:
1. Specific credible opening hook (avoid repeated "Here's one idea..." templates).
2. Context/real problem, grounded in provided facts.
3. One compelling reveal/proof/example — no fabricated claims.
4. A useful payoff.
5. Optional product call to action (not imposed on informational videos).
Each scene needs reason to exist, duration, visual concept and spoken line. Only then synthesize selected voice and align scene cuts to actual audio. Human review gate: "Could this narration stand on its own as a mini-story?".

No extra tool purchases, and no change to the separate agency website repository.
