# AD Motion Studio — Open-source Faceless Video Maker

**Latest: V3** — zero-fee creative-brief-to-video prototype, rendered in the cloud. Made for Android-only workflows.

## New experimental Creative Director (planning only)

[Talk to the Director on your phone](https://github.com/oyzitjfzj/Ad/issues/new?template=talk-to-director.yml). Describe the idea in your own words and reply to any one-question follow-up. A local free open-weight Qwen3-4B-Instruct model designs a concept, timed storyboard, visual grammar, justified 3D, soundtrack and preferred M3/F2 voice, then runs an independent critic and deterministic truth/timing/rights checks. It produces a **creative treatment and QA report, not an MP4**. The V3 video renderer and approved voice profiles are unchanged. See [Director Lab](creative_director/README.md) for precise limitations and public-Issue privacy warnings.

## 🎬 New: Tell the director about your product

**[Start here: Create an Ad (answer 5 short questions)](https://github.com/oyzitjfzj/Ad/issues/new?template=make-video.yml)**

1. Sign into GitHub on your phone and open the link above.
2. Answer the questions: name, product type, target customer, main real benefit, call to action; optional slogan.
3. Tap **Submit new issue**. Do not enter secrets: your answers appear in this public repository.
4. GitHub automatically makes a short video if you are the repository owner.
5. When the issue gets a new comment with a render link, open it, download artifact **AD-original-motion-film** and unzip `short.mp4`.

A test video without filling a form: [Run V3 demo](https://github.com/oyzitjfzj/Ad/actions/workflows/studio-v3.yml) → **Run workflow**.

## What it does

- **Open-source voice**: Kokoro 82M ONNX, full-size model in Apache 2.0 license, male narrator `am_michael`.
- **Open-source video**: Python + Pillow, FFmpeg, NumPy, SoundFile; designed 2.5D graphics and camera-like layered motion.
- **Original soundtrack**: music and cut accents synthesized procedurally, no stolen audio or copyrighted stock music.
- **Content-aware visual presets**: distinct on-screen mockups for software, physical product and service; the brief controls product name, audience, benefit and CTA.
- **Seven story beats**: hook, audience, reveal, benefit, polish, message, action. Timing follows locally synthesized voice.
- **Export**: 1080 × 1920 MP4 with narration and audio, available as a downloadable GitHub Actions artifact.

## Important — not an AI Creative Director yet

V3 asks structured questions and uses its own rules to arrange scenes. **It does not yet autonomously reason with a language model, interview dynamically, browse product documentation, generate true 3D meshes, guarantee the accuracy of claims or create arbitrary video stories from one sentence.** It uses category-aware procedural graphics and user-provided truthful details. The demo uses an imaginary brand called NOVA.

Quality is a subjective target, not a guarantee. The free GitHub-hosted runner and model downloads are subject to platform limits; GitHub hosting itself is free infrastructure, not open-source server software. For full independence, the engine can run on any Linux machine with the listed dependencies.

## Requirements / provenance

Own project code: MIT license (see LICENSE). Third-party code remains under its respective licenses:

- [Kokoro ONNX](https://github.com/thewh1teagle/kokoro-onnx) — MIT inference; Kokoro model — Apache 2.0.
- [Pillow](https://github.com/python-pillow/Pillow) — HPND historical permission.
- [NumPy](https://github.com/numpy/numpy) — BSD-3-Clause.
- [SoundFile](https://github.com/bastibe/python-soundfile) — BSD-3-Clause.
- [FFmpeg](https://ffmpeg.org/legal.html) — LGPL/GPL depending on compiled configuration.
- `actions/checkout`, `actions/setup-python`, `actions/cache` and `actions/upload-artifact` have their own GitHub open-source code licenses.

Model data is downloaded on the runner; it is not included in this repository.

## Technical files

- `src/film_v3.py`: seven-scene Open-source animation, TTS, procedural audio, export.
- `src/issue_to_brief.py`: converts the issue form to a validated JSON creative brief.
- `.github/ISSUE_TEMPLATE/make-video.yml`: mobile questions.
- `.github/workflows/studio-v3.yml`: automated cloud render and downloadable artifact.
- `examples/sample-brief.json`: sample ad for an imaginary product.
- Prior V2 exists in Git history only. Production uses only V3 open-source code and locally generated Kokoro voice.

### Run V3 on your own Linux computer (optional)

Install Python 3.12, FFmpeg, espeak-ng and suitable fonts; install `numpy Pillow soundfile kokoro-onnx`; download the model files `kokoro-v1.0.onnx` and `voices-v1.0.bin` from the [official Kokoro ONNX model release](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.1) into `models/`; run `python src/film_v3.py --brief examples/sample-brief.json`. No paid API credentials needed.

**Safety:** Only video requests submitted by the repository owner are rendered by the GitHub Issue workflow, and uploaded information is handled as data (not shell commands). For private brand details, do not use public GitHub Issues.

