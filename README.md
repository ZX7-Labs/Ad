# AD Motion Studio — Automatic Faceless Shorts

फोन से topic डालकर **2.5D-style motion-graphics Short** बनाओ। Rendering GitHub के cloud computer पर होती है; फोन पर भारी software नहीं चलता।

## मोबाइल पर पहला वीडियो कैसे बनाएँ

1. [इस repo के Actions पेज पर जाओ](https://github.com/oyzitjfzj/Ad/actions).
2. **Generate premium-style Short** workflow खोलो।
3. **Run workflow** दबाओ (मोबाइल पर बटन न दिखे तो Chrome में **Desktop site** चालू करो)।
4. **topic** में वीडियो का विषय लिखो, जैसे: `3 tools every developer should know`।
5. **points** (optional) में 3 छोटी lines `|` से अलग लिखो, जैसे: `Build faster | Test better | Ship confidently`।
6. **Run workflow** दबाओ। Run green check होने तक इंतजार करो।
7. उसी completed run के नीचे **Artifacts → your-faceless-short** डाउनलोड करो। ZIP से **short.mp4** निकालो।

[▶️ Generate your first Short](https://github.com/oyzitjfzj/Ad/actions/workflows/create-short.yml)

## Video में अभी क्या मिलता है?

- 9:16 portrait MP4 (1080 × 1920 export, internal canvas 720 × 1280)
- Clean dot-grid background, floating UI panels, shadows, angled card animation, eased motion, typography
- Topic और 3 points पर आधारित 4 scenes
- हिंदी या अंग्रेज़ी में optional auto voice; `edge-tts` असफल हो तो वीडियो बिना आवाज़ बनेगा
- 19–35 सेकंड के लगभग video; export में platform watermark नहीं
- नया वीडियो बनाने के लिए सिर्फ Actions में नया topic डालना है

## महत्वपूर्ण सीमाएँ

**यह शुरुआती prototype है, कोई fully intelligent video-editing AI नहीं।** Title और दिए हुए points वीडियो में आते हैं, लेकिन card graphics अभी fixed design templates हैं। यह अभी original factual research, scene-to-scene content-specific visuals, native true 3D या guaranteed cinematic result नहीं बनाता।

- GitHub public repo में GitHub-hosted standard runners पर Actions उपलब्ध हैं, GitHub की policies लागू होती हैं।
- TTS अनौपचारिक third-party online endpoint का इस्तेमाल करता है; सेवा हमेशा काम करेगी या हमेशा free रहेगी, इसकी गारंटी नहीं।
- इंटरनेट/Runner/dependency समस्याओं पर run fail हो सकता है।
- अपनी videos में दूसरों की copyrighted photos, music, या brands बिना permission इस्तेमाल न करें।

## Developer notes

- Code: `src/render.py`
- Workflow: `.github/workflows/create-short.yml`
- CLI: `python src/render.py --topic "Creative motion" --points "Idea|Design|Impact"`
- Local deps: Python 3.12, Pillow, FFmpeg, Lato/Noto fonts, optional edge-tts.
- Output: `output/short.mp4` and `output/narration.txt`.
- Workflow can be manually run; also renders a sample when workflow file is first pushed.

अपनी वेबसाइट के repository से अलग रखा गया है।
