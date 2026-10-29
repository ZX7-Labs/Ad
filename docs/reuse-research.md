# Foundation research and reuse decisions

Review date: 29 October 2026. Source baseline:
`f80a39824626bc319204e3ba89bae991a62541b1`.
Read with [architecture](architecture.md), [video research plan](video-research-plan.md)
and the full [A–L contract](../CAPABILITIES.md).

## Evidence rules and scope

This is a bounded engineering survey, not an exhaustive search or a quality
ranking. Source descriptions identify potential capability. Measured experiments
identify narrower facts. No model inference, professional expert review, GPU
render comparison or field acceptance was established by this survey.

The earlier foundation branch contains useful leads, but its declarations of
backend selection are not conformance results. This decision record keeps
browser engines and generative runtimes conditional until matched trials.
Documentation, code, weights, voices, fonts, plugin packages and shipped binary
dependencies need separate provenance/license records. Repository license
metadata alone is not a distribution audit.

## Existing system: keep the useful foundations

| Existing paths | What source inspection establishes | Disposition |
|---|---|---|
| `media_vault.py`, `body_asset_links.py`, `body_archive.py` | Byte identities, separate rights attestations, source snapshots and portable recovery work | Retain and test migrations/revocation; do not rebuild a second asset store |
| `registry.py`, `contracts.py`, `body_plugins.py` | Permissioned installed tool catalog and explicitly trusted Python extensions | Extend descriptors and probe evidence; plugins remain trusted code |
| `durable_graph.py`, `durable_sqlite.py`, `body_publication.py`, stage leases | Durable stages, source-dependent reuse and guarded artifact publication | Reuse; audit cross-store reconciliation and stale-worker fencing |
| `body_mlt_*` | Source-aware native editing, revisions and source-frame controls | Retain; benchmark native semantics instead of replacing with a smaller custom editor |
| `body_sequence_otio.py` | Deliberate strict one-picture/one-aligned-audio interchange; refuses unrepresented decisions | Preserve legacy behavior; add richer interchange with explicit loss reports |
| `composite_mix.py`, `precision_retime.py`, `body_timecode.py` | Real FFmpeg composition/retime and exact source/timecode work, with different precision limits between routes | Retain engines; reconcile clock and audio contracts |
| `body_motion_project.py`, `body_motion_worker.py` | Sealed native Blender projects, RNA inspection/edits, keyframes and retained native state | Retain; external cache/volume/linked-library restrictions are adapter limits, not Blender limits |
| `body_visual_graph.py`, `body_visual_render.py`, `creative_asset_ops.py` | Useful vector/graphics controls and rasterization | Retain working routes; do not certify full painting/type/motion scope |
| Color/EXR/ACES modules | Explicit technical workflows and validation code | Preserve; verify actual transforms and metadata at each engine boundary |
| `body_creative_session.py`, model HTTP adapters, observation/review modules | Persisted model decisions, actual image evidence and numerical audio reports | Extend audiovisual modality support; current still-image loop is not semantic motion/audio proof |
| Service/mobile/client and delivery modules | Existing owner access and job surfaces | Test and improve rather than starting another disconnected UI |

Source review found that the native motion worker rejects external movieclips,
volumes, cache files, linked libraries and certain baked simulation caches.
That is a real deployment/packaging constraint to address in the later E field;
it is not evidence that Blender lacks those capabilities. Likewise, MLT supports
more services and parameters than ZX7 currently accepts.

## Engine and system comparison

The decisions below are engineering choices. “Retain” means build on an existing
route, not “fully accepted.” “Trial” means a bounded comparison is required before
adding a product dependency. Avoid installing every candidate.

| Capability / candidate | Type and useful native surface | Decision and reason | Required falsification test |
|---|---|---|---|
| [MLT](https://mltframework.org/docs/melt/) | NLE framework: producers, playlists, multitracks, tractors, filters and transitions | Retain first video backend; existing source-aware integration has value | Source-frame edits, multitrack compositing, effect order, native save/reopen and actual decoded A/V |
| [FFmpeg](https://ffmpeg.org/ffmpeg-filters.html) | Codec/filter engine, including sample-unit delay and trimming | Retain technical executor; fix adapter precision rather than reimplement DSP | One-sample impulses, trim edges, channel isolation, resampling and codec delay |
| [OTIO](https://opentimelineio.readthedocs.io/en/latest/tutorials/otio-timeline-structure.html) | Editorial exchange with clips, gaps, stacks and transitions; effects are application-specific | Retain interchange; do not treat it as a renderer or universal native state | Nested multitrack roundtrip with metadata and declared unsupported effects |
| [Blender API](https://docs.blender.org/api/main/info_overview.html) | Native scene/data/animation/node API, background authoring and rendering | Retain 3D/motion foundation; add sealed dependencies and isolation when that field is active | Rig/curve/cache authoring, packed dependencies, reopen/revise and native physical renders |
| [Inkscape CLI](https://wiki.inkscape.org/wiki/Using_the_Command_Line) | Editable SVG and installed action discovery/export | Retain vector/type route, test actual installed version and fonts | Editable Hindi/Latin typography, masks/filters, final raster and SVG reopen |
| [Krita scripting](https://docs.krita.org/en/user_manual/python_scripting.html) | Application plugin API and native painting/layer documents | Trial during D field, not mandatory for the video milestone | Real layer/paint/animation controls, application-hosted scripting and native reopen |
| [GIMP scripting](https://developer.gimp.org/resource/) | Layered photo operations and batch/plugin mechanisms | Alternate D-field photo route; do not integrate both photo apps without a needed distinction | Masked nondestructive edit, metadata/color, batch control and native recovery |
| [Gaffer contexts](https://www.gafferhq.org/documentation/1.1.8.0/WorkingWithTheNodeGraph/Contexts/index.html) | Image/scene graph with deferred, context-dependent processing | Strong compositor candidate and dependency-evaluation reference | Same EXR composite against Blender compositor, including alpha/color and revision cost |
| [Natron](https://github.com/NatronGitHub/Natron) | Dedicated node compositor / OFX ecosystem | Alternative to Gaffer; defer choosing until matched E/D workloads | Headless reproducibility, plugins, editable graph, masks/roto and resource use |
| [OpenColorIO](https://opencolorio.readthedocs.io/) + [OpenEXR](https://github.com/AcademySoftwareFoundation/openexr) | Color transforms/configuration and float image interchange | Retain; pin configuration and verify actual transforms, not just labels | Scene-linear passes, alpha edges, data channels and SDR/HDR boundary values |
| [OpenImageIO](https://github.com/AcademySoftwareFoundation/OpenImageIO) | Image formats/processing and metadata tools | Optional only for a gap not efficiently served by current stack | High-bit-depth asset roundtrip and matched memory/time against current route |
| [OpenUSD](https://github.com/PixarAnimationStudios/OpenUSD) | Scene composition/interchange | Defer core dependency; not a universal timeline, simulation or audio project model | Needed cross-DCC scene transfer with declared rig/material losses |
| [HyperFrames](https://github.com/heygen-com/hyperframes) | Browser composition/render packages; editable web-native art | Browser-motion trial candidate, not unconditionally selected | Same typography/motion brief vs existing Blender/SVG route; exact seeking, fonts, audio and isolation |
| [OpenFilm](https://github.com/openfilm/openfilm) / [Motion Canvas](https://github.com/motion-canvas/motion-canvas) | Agent/editor composition system / programmatic 2D motion library | Comparators or selective specialist reuse; avoid duplicate browser render stacks | Identical assets and direction, then targeted revision and editable export |
| [NodeTool](https://github.com/nodetool-ai/nodetool) / [Velorn](https://github.com/VelornLabs/velorn) / [OpenKatana](https://github.com/rk0neki/OpenKatana) | Whole creative/agent workstations | Benchmark coordination and UX; do not infer unique invention from tool aggregation | Same brief/model/hardware, revision, reopen and failure/recovery |
| [Ardour Lua](https://manual.ardour.org/lua-scripting/) | DAW session, bus/plugin and automation control | G-field candidate if native DAW needs exceed offline FFmpeg bus processing | Sample-accurate stems, editable automation, plugin latency and session reopen |
| [PipeWire](https://docs.pipewire.org/) / JACK | Live media routing/latency infrastructure | Defer until realtime monitoring/capture is required; not an offline DAW replacement | Measured end-to-end latency, clock drift and device reconnect |
| [ComfyUI](https://github.com/Comfy-Org/ComfyUI) | Extensible generation workflow/runtime | Keep optional external backend with approved nodes | Installed weights, isolated node execution, cancellation, resume and actual output quality |

The Gaffer context design is a useful precedent for requesting only a frame,
channel, scene location or tile. It does not justify implementing a new Gaffer
clone. Use native evaluation inside engines; BODY invalidates cross-engine
artifacts conservatively until finer-grained reuse is proven correct.

## Brain, perception, generation and optimization are separate choices

| Candidate | What evidence supports | Decision / unresolved gate |
|---|---|---|
| [llama.cpp server](https://github.com/ggml-org/llama.cpp/tree/master/tools/server) | Lightweight native inference route with model-dependent multimodal support | Trial eligible small tool-using and perception models; confirm exact model/backend/modality combination |
| [Qwen3-VL](https://github.com/QwenLM/Qwen3-VL) | Vision-language family, useful for timed visual inspection | Candidate, not proof of creative editorial competence or semantic listening |
| [Qwen3-Omni](https://github.com/QwenLM/Qwen3-Omni) | Documented joint audio/image/video input and configurable speech output | Candidate for A/V review; run real synchronized-segment and Hindi tests within measured RAM/VRAM |
| [Wan2.2](https://github.com/Wan-Video/Wan2.2) | Generative video model family | Candidate; exact variant/checkpoint/license, temporal quality and hardware trials required |
| [WanGP](https://github.com/deepbeepmeep/Wan2GP) | Multi-model application/inference integration with low-memory routes | Compare API/headless execution with current Comfy route; do not import the whole application solely for a VRAM claim |
| [FastVideo](https://github.com/hao-ai-lab/FastVideo) | Inference and post-training framework with offload, sparse/distilled and distributed routes | Compare supported checkpoint/hardware pair; not interchangeable with a video model |
| [SparkDiffusion](https://github.com/AlibabaResearch/SparkDiffusion) | CUDA-oriented sparse/distilled/quantized video inference research | Optional trial, no general speedup claim; compare actual compatible checkpoints and full decode cost |
| [Nunchaku source](https://github.com/nunchaku-ai/nunchaku/blob/main/nunchaku/models/linear.py) | W4A4 linear layers call specialized CUDA kernels | Quantized-runtime candidate for supported architectures; not a universal quantizer for all video models |
| [Chatterbox](https://github.com/resemble-ai/chatterbox) / [Kokoro](https://github.com/hexgrad/kokoro) | TTS candidates with different scope/size | Real listening, Hindi pronunciation and voice-rights gates; do not pick solely by parameter count |
| [ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5) | Music generation with documented inference and hardware paths | G/H candidate; compare fit, structure, stems/editability, rights and actual listening |

No globally best open brain or generator is selected. The required procedure is
eligibility gates first, then a Pareto comparison on the owner's workloads.
Keep the creative brain pluggable and ability to switch runtimes without
changing native projects. A quantized model must re-pass tool use, adherence,
Hindi and temporal/audio inspection tests; reduced weight size does not prove
reduced full-system memory or accepted-revision cost.

Optimization experiments must distinguish: weight quantization, KV cache,
activation/attention memory, CPU offload, layerwise offload, tiling, compilation,
attention kernels, sparse attention, fewer steps/distillation and proxy previews.
Measure cold/warm wall time, download size, total RAM, peak VRAM, decode/export,
energy where measurable, retries and quality. Compare accelerated output both
against its own unoptimized checkpoint and, separately, alternative models.
Matched seeds alone do not establish identical outputs across kernels/runtimes.

## Source identities captured

These are research observations, not approved production locks. Production
selection must also pin build/dependencies/config/weights and verify licenses.

| Source branch observed | Commit |
|---|---|
| MLT `master` | `640940607fa8f8d58c582250dca4dc5d816f6078` |
| OTIO `main` | `4524367491df94841cbf48ade184b818d2dc6354` |
| OCIO `main` | `22dd9c4faa0d1b7cfb3d64d1a6e9cb454acc6cfd` |
| Gaffer `main` | `7dc354f6576a7d02209dc200edff45708e6a1b84` |
| HyperFrames `main` | `a5496b1887950777b78ed5ac2bff3505961cb5fe` |
| FastVideo `main` | `7203b4976eefcd70a52728ca1281797ce96734eb` |
| SparkDiffusion `main` | `3fd210c7baaf6ad233ce4c730d0e329bb8014b6b` |
| Qwen3-VL `main` | `96588727e44c78b25ba03ea03b8e12f7e64fd0da` |
| Qwen3-Omni `main` | `e4235853125589c789f06a2dd83e9f4126df5e9d` |
| ComfyUI `master` | `0df1646a9cd71d4c990a87014fb37797a2956ead` |
| Wan2.2 `main` | `1ea34ff48f87168174e12956e200b1d908b1c5ff` |

The WanGP historical GitHub API path returned a repository-moved response;
resolve its canonical identity before pinning. Nunchaku's source URL redirects
to `nunchux-ai/nunchaku`; use the resolved identity at installation. Do not treat
old names or search result snippets as dependency locks.

## Actual measurements recovered from this research

| Experiment | Result | Scope / limitation |
|---|---|---|
| Live registered tool catalog on baseline | 46 registered, 31 dependency probes installed, 15 need setup | Probe counts are not completed creative fields or successful operation trials |
| Existing selected baseline tests | 121 run, 113 passed, 8 skipped for OTIO | Earlier source/contract sample, not all tests or full native release suite |
| Enable actual OTIO in research dependency directory | Previously skipped 8 OTIO tests all passed in 16.944 s | Their intentional strict bridge scope remains unchanged |
| Sample-clock differential, 48 kHz impulse placed at sample 1 | BODY-generated audio branch peaks at sample 0; FFmpeg sample-unit reference peaks at 1 | Lossless PCM diagnostic, video branch sunk; not AAC delivery or a separate autonomous model |
| Expanded local sample-clock matrix | 108 cases: 16 matching, 56 decoded timing mismatches, 36 generated-command rejections; maximum decoded error 24 samples | 44.1/48 kHz mono/stereo, 3 source trims and 9 placements; both routes use the current stereo bus |
| Local three-track source-frame trial | FFmpeg baseline 12/12 frames matched; revised edit 11/12, with the intended top layer absent at frame 7 | 12 fps opaque diagnostic plates only; local MLT absent, native comparison must run separately |

The sample-clock result specifically implicates `round(start*1000)` in the
composition adapter. FFmpeg supports `adelay` sample units. One measured failure
is enough to reject a universal sample-accurate placement claim; it does not
prove every trim, retime or bus operation wrong. A comprehensive remedy needs
source trims, duration, channel policy, resampling and legacy schema migration,
not merely replacing one literal filter string.

The expanded matrix also established a distinct serialization failure:
`source_in=1/44100` becomes `2.2675736961451248e-05` in `atrim`, which the
installed FFmpeg duration parser rejects. The sample-unit reference executes.
Both timing quantization and accepted-value serialization belong in the remedy.
The source-frame revision mismatch needs native comparison and timestamp tracing
before assigning a root cause; do not guess that it is an inclusive-end error.

Reproduce with `python scripts/research_audio_clock.py --out /tmp/audio-clock.json`
and `python scripts/research_native_editor.py --out /tmp/native-editor.json`.
The second requires real MLT; its explicit `--ffmpeg-only` mode reports partial
coverage. `.github/workflows/zx7-foundation-research.yml` runs both native probes
and the actual OTIO tests. Measurement completion is separate from conformance:
inspect the reports, or use `--require-conformance` on the audio probe.

Host observations: Python 3.12.14; FFmpeg/FFprobe, Inkscape and `bwrap` present;
Blender, MLT `melt` and Docker absent. OTIO was loaded from a research-only
dependency directory, not installed as a new mandatory core dependency. No
usable GPU/model inference was established. Firecrawl quota was exhausted in
the earlier review; public primary documentation, web search and GitHub source
reads were used instead. No paid compute was provisioned.

## A–L research-to-acceptance traceability

| Domain | Foundation decision | Evidence still needed before field completion |
|---|---|---|
| A | Retain source/rights vault and custody journal | Concurrent import/revoke/relink, hostile inputs, backup/restore and downstream revocation |
| B | Manifest plus native subprojects, OTIO interchange | Rich multitrack/nested roundtrip, native metadata and explicit conversion losses |
| C | Retain MLT + FFmpeg; reconcile time/audio | Complete editorial operation matrix, variable rate, transitions/curves, long projects and native output |
| D | Retain SVG/native motion; trial one painting and one browser route only if needed | Typography, editability, masks/tracking, curves and multi-brief craft assessment |
| E | Retain Blender; compare compositor only on demonstrated gaps | Rigs, simulation/cache packaging, EXR and professional integration/revision |
| F | Retain OCIO/EXR-aware color work | Boundary correctness, 10bit/HDR/SDR measured pixels and external playback |
| G | Preserve streams/stems; FFmpeg first, DAW/generators optional | Sample clocks, channels/latency, loudness and independent Hindi/music listening |
| H | Optional isolated model runtimes, no GPU assumed | Installed licensed weights, matched hardware/quality/cost, consistency and recovery |
| I | Retain durable graph/catalog; extend project publication | Stale attempts, crash windows, resource isolation, cancellation and cache correctness |
| J | Modality-aware evidence and targeted revisions | Real A/V critic input, calibrated defect detection and meaningfully improved output |
| K | Existing local-first service/mobile surfaces | Real Android/off-LAN secure deployment, accessibility, private assets and restore |
| L | Independent evaluation, not an aggregate test score | Diverse original briefs, real brain/BODY sessions, expert/owner judgments and complete disclosure |

## Consequential unresolved decisions

1. MLT/FFmpeg composition versus a richer native path must be compared on the
   same editorial workloads with actual installed MLT. Current host absence
   prevents that experiment; it does not justify deleting MLT integration.
2. Browser motion, dedicated compositor, painting app and DAW are conditional
   additions. Prove an expressive or operating advantage before adopting one.
3. Exact clock/channel contract needs executable differential probes before a
   product schema change. Keep failures visible; do not weaken old tests.
4. The creative-code isolation profile needs actual host enforcement tests.
5. Brain/perception/generation winners and hardware profiles remain unselected
   until licensed weights and authorized compute can run matched trials.
6. Independent professional quality and real Android delivery remain release
   gates; neither can be replaced by this architecture document.

These gaps mean the full comparative research is not finished. They do not
prevent preserving the current design and executing the next bounded research
experiment. No product implementation is authorized by an invented claim that
all comparisons have passed.
