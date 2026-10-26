# ZX7 — Multi-engine creative freedom restored (21 October 2026)

## Binding product constraint

Re-reviewed original `docs/MASTER_PLAN.md` and `PROJECT_SCOPE.md`: **The studio must never globally prescribe 2D/2.5D, a fixed shot number, runtime, font, format, template, voice, narrative structure, or one renderer.** The creative Director decides the form. An individual currently installed renderer may have narrower capabilities. Those are adapter-specific execution facts, **not allowable reasons to silently rewrite the creative plan**.

## Actual code changes on research branch

- `studio_next/capability_routing.py` — routes explicit per-shot creative capabilities to *registered, executable, license-cleared and verified-free* engines. It supports multiple tools in one shot and only selects artistic alternatives explicitly supplied by the Director; no silent 3D-to-flat-card downgrade. It does not claim professional art quality.
- `studio_next/blender_scene.py` — real 3D renderer using **Blender Cycles CPU**. Accepts original artist-defined custom polygon meshes, procedural geometric 3D forms, explicit materials and lighting, animated objects and moving perspective camera. Supports verified locally licensed .glb imports, rejecting path escapes, model-supplied scripts or fake asset rights. These are Blender adapter capabilities, not an artificial all-studio design vocabulary.
- `studio_next/edit_timeline.py` — trusted FFmpeg montage of clips from different actual engines, with director-specified framing/aspect ratio and explicit preservation/intentional silence of audio; never silently loses speech or downloads unlicensed footage.
- Separate data-driven scene fixtures and adversarial tests. No changes to earlier accepted FOLD renderer, M3/F2 voices, main branch or failed Creative Director evaluations.

## Independent GitHub output proof

- **Mixed 2D and genuine 3D film** [successful run 39513980044](https://github.com/oyzitjfzj/Ad/actions/runs/39513980044), on public GitHub Actions CPU using Ubuntu Blender 4.0.2, FFmpeg and the existing procedural compositor.
- Actual animated Blender frames: 24 frames, **2.00s** verified H.264 MP4. Real custom polygon mesh, torus, material, world, two light sources and camera movement, not simulated flat gradients.
- Real 2D motion engine independently compiled a two-shot Film IR into 2.75s MP4 with sound.
- **Final combined film: 4.75s, 320×480**, verified MP4 with video **and** audio streams, explicit fit/letterboxing for dimension mismatch, two differently rendered source clips. Verified with ffprobe against the actual output; not inferred from JSON.
- [Artifact — final combined MP4, separate 2D and 3D MP4s, edit manifest and preview frames](https://github.com/oyzitjfzj/Ad/actions/runs/39513980044/artifacts/12306504412). The source artifact has 7-day retention.
- Earlier standalone 3D run: [39513553191](https://github.com/oyzitjfzj/Ad/actions/runs/39513553191).
- The stock Ubuntu Blender build lacks OpenImageDenoiser. Initial failed jobs recorded that fact and the adapter was corrected (disable unsupported denoising, retain direct Cycles rendering). Do not hide failed attempts.

## Scope still unresolved

This is a real engineering step beyond the 2D-only bridge, but it is **not** proof of human-level creativity, generative 3D filmmaking, automatic idea-to-video, or studio-quality aesthetics. The sample scenes are explicitly authored test inputs, not produced autonomously by Qwen. The 3D video proof is intentionally short to use free CPU. No paid API or hosted GPU was needed. Model selection, story quality, visual design from ordinary language, asset generation and critical audiovisual self-repair remain to be built and independently tested.

## Next honest work

Connect the *actual AI Creative Director* to designer-produced 3D/2D/tool-neutral shot specifications, with human-auditable story reasons, coherent subject/product causality, verified facts and per-scene rights. Let producer select present real capabilities without changing intent. Render two different genres from natural briefs, check decoded frames/speech/timing and repair failed segments without losing approved scenes. Keep model architecture replaceable and avoid a crowd of unnecessary models.

**Status:** 2D+3D rendering and mixed-engine assembly **verified**; natural-language autonomous premium movie **not verified**.
