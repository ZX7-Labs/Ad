# Native creative controls — 25 October 2026

## Owner's requirement and role boundary

The AI is the creative operator. BODY is the engineered working system it
controls. BODY engineering belongs to this repository's developers. The AI
must not have to modify BODY source, install an application, add a capability,
or rebuild its instruments to make a creative decision. It changes **project
data**: imagery, geometry, timelines, sound, layers, masks, values and curves.
The desired breadth covers every creative field; editing examples are not
the complete requirement. This checkpoint is **not a completed universal
studio or a claim of world-leading quality**.

## Implemented control change

`body.visual_graph` is a native NumPy pixel engine. It evaluates original
mathematical fields, images, motion, masks, inverse spatial maps, separable
convolution and source-over compositing. An artist composes these primitives
and explicitly authors their parameters instead of selecting named finished
looks. Graph branches and numeric curves remain editable project data.

- Float32 linear-sRGB associated-alpha internal processing. Straight channel
  expressions are converted at node boundaries; spatial filtering uses
  associated channels to avoid transparent-edge fringes.
- Authored hold, linear and cubic-Hermite control curves. Cubic in/out slopes
  are independent. Original zero-based frame time and rational frame rate are
  retained when rendering an excerpt.
- Sealed, rights-attested image/video inputs. Exact source frame selection
  supports reverse, hold and reordering. Source files are reverified before
  atomic no-overwrite publication.
- Current deliveries are actual pixel-verified sRGB PNG, lossless RGBA
  PNG-in-MOV and lossless float32 linear-sRGB EXR stills. Audio remains on the existing independently editable audio
  tracks; no soundtrack is silently invented or copied through a retime.
- Existing discovery, typed authoring, durable graph execution and generated
  media custody expose the new operation to the model-facing BODY interface.

`inspect_plan` reads a selected JSON Pointer from an exact immutable creative
document. `revise_plan` applies explicit add/remove/replace/test edits, checks
the native document schema, and publishes a new content-addressed version.
It works across supported creative document types, not just this image graph.
Originals remain available for revision/undo. These actions never modify BODY
implementation, executable access or source-media rights.

The session protocol now advertises these project actions. Its prompt identity
changes accordingly; existing sessions retain the existing model/protocol
identity check rather than silently resuming under changed instructions.

## Validation and durability

After workspace maintenance removed unsaved local working files, the GitHub
checkpoint `e7dbc243753a26fb6d166c74e08ba4eba11b3c8c` was restored and the
new code reconstructed. Older local full-suite output was lost and is not
claimed as a result for this code. New source is saved incrementally on the
existing GitHub development branch; main is unchanged.

The reconstructed controls, graph, project revision, BODY signal, creative
session, capability discovery and integration modules passed **52 focused
tests** locally (including native float EXR and independent RGB/alpha filtering). Actual native tests cover analytically known compositing
pixels, subpixel alpha, convolution, new pixel formulas, source mutation,
RGBA video reverse/hold, excerpt frame identity, model-facing author/submit,
generated output custody, scoped project revision and preservation of originals.
The caller in these tests is a deterministic test program, **not LLM inference**.
A native public-tool acceptance graph physically rendered motion, an original-clock
excerpt, a float master and an image, registered their generated source custody,
and then reused all eight verified stages. Decoded RGBA and float32 EXR match
the original mathematical data exactly. The independently installed wheel also passed the eight-stage native graph proof,
with exact original-clock RGBA and floating pixels. A minimal installation
correctly reports missing numeric/image engines as needs_setup. A subsequent
adversarial file-swap check binds the plan receipt to the exact bytes parsed.
Final-source full-suite and remote CI evidence will be recorded separately.

## Actual remaining limitations

- This is not all professional design/photo/NLE/VFX/CGI/audio functionality.
  Existing adapters still have narrower controls. The new graph does not
  automatically expose the entirety of Blender or any other engine.
- PNG/MOV video source and export paths remain 8-bit SDR. Float32 EXR still
  input/output preserves extended and negative RGB, supports explicit source
  channel selection and alpha association, and is tested with OpenEXR 3.5.2.
  This does not add float video, HDR display delivery or deep compositing.
- CPU graph execution is not a measured GPU compositor, real-time playback
  engine, temporal denoiser, optical-flow solver, full paint/text system,
  character rig, smoke/fire simulator or complete DAW.
- Dependency identities report affected creative nodes. They are not a claim
  of already verified cross-version pixel-cache reuse. The existing durable
  BODY execution layer independently verifies physical cache receipts.
- Host memory, decode/storage, expression complexity and execution budgets
  are resource policies; they do not select a genre, visual style or story.
- A real configured creative model, full remote production deployment,
  performance at production scale and independent artistic acceptance remain
  separate release requirements. Passing technical tests certifies none of
  those claims.

## Primary technical references

- W3C compositing and Porter-Duff source-over:
  https://www.w3.org/TR/compositing-1/
- W3C sRGB/linear-light transfer definitions:
  https://www.w3.org/TR/css-color-4/
- OpenEXR native Python/NumPy read/write interface:
  https://openexr.com/en/latest/python.html

Research informs numerical implementation; no third-party creative example or
finished template is embedded as an artistic default.

## Final exact-source native acceptance

Source `58c74867eced01712a0728596330dfa65eb2e59a` passed the complete native
GitHub run [40229772599](https://github.com/oyzitjfzj/Ad/actions/runs/40229772599):
647 cases, 646 passed, one separately exercised browser skip, zero failures/errors.
The installed wheel passed both the new eight-stage editable visual graph proof
and the existing real 2D/3D/audio/OTIO, CGI/tracked VFX, controls, cloth/morph/liquid
proofs. The clean-run result is the final full-suite acceptance; a local run had
previously stalled in an existing HTTP sensory test, which passed on its own.
That stalled local run is not counted as a passing suite.

[Exact receipts and remaining limits](ZX7_BODY_NATIVE_VISUAL_ACCEPTANCE_2026-10-25.json)
retain source identity, installed-module hashes, original-clock RGBA and float
proofs, artifact digest and the unchanged full-studio/creative-quality boundary.
The source inventory covered all 375 tracked files (234 Python), with no parse
blocker; this is not a completed manual security review.
