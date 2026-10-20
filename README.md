# AD Motion Studio — Version 2

Automatic faceless motion-graphics Shorts from your phone.

## Create a new video on Android

1. Open [Generate premium-style Short V2](https://github.com/oyzitjfzj/Ad/actions/workflows/create-short.yml).
2. Tap **Run workflow**. If you don't see it, turn on **Desktop site** in Chrome.
3. Enter **topic** and 3 **points** separated with `|`.
4. Choose a voice:
   - `en-US-AndrewNeural` — recommended first try.
   - `en-US-BrianNeural` — alternative male voice.
   - `en-US-EmmaNeural` — female voice.
5. Choose speed: `+8%`, `+15%` (default), `+22%`, or `+28%`.
6. Press **Run workflow**. Open the new run and wait for **Success**.
7. Under **Artifacts**, download `premium-short-v2` ZIP and extract `short.mp4`.

[Open the V2 video maker](https://github.com/oyzitjfzj/Ad/actions/workflows/create-short.yml)

## What changed since V1?

- 8 shorter shots, rather than 4 static long scenes.
- More frequent animated entries, 2.5D floating elements and quick cut transitions.
- 3 user-entered points appear in a shot-by-shot sequence.
- 3 selectable neural voices and 4 voice speeds.
- Spoken-word metadata drives animated 4-word caption blocks when the voice provider returns timestamps.
- GitHub Actions updated for Node.js 24-based action versions.

## Real limitations

This is an **automated motion-design prototype** — not a truly cinematic 3D renderer. Templates are mostly reusable visual elements; images are not generated individually for each subject. Audio is generated through the unofficial `edge-tts` interface to Microsoft voices and may be unavailable or rate limited at any time. In that case, the renderer still exports a silent MP4.

Shorts should not be published without checking factual claims, pronunciation, visual fit, timing and quality. For a more human voice, choosing a different voice or using an independent voice recording may be necessary; TTS alone cannot guarantee a human performance. This project is separate from any existing website.

## Developer notes

- Source: `src/render.py`
- GitHub Actions: `.github/workflows/create-short.yml`
- Download: `output/short.mp4`, `output/narration.txt`, `output/metadata.json`
- Dependencies on Ubuntu: Python 3.12, Pillow, ffmpeg, Lato / Noto fonts, edge-tts (optional).
