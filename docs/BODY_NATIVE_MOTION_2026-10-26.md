# Native motion design — 26 October 2026

## Direction and engine choice

The selected field is **motion design**. Blender is the existing open-source
creative engine; BODY connects its native project controls to the AI operator.
The authoritative project remains a real editable `.blend` throughout creation,
inspection, revision, preview and delivery. This field is the engineering focus.

Blender was selected for its combined native geometry/text, animation, materials,
Geometry Nodes, cameras, rendering and compositor data. Glaxnimate is strong in
vector animation and Lottie/SVG delivery; it lacks the same combined 3D pipeline.
This is a fit decision, not a measured universal ranking.

Official references consulted:

- https://www.blender.org/features/
- https://www.blender.org/features/animation/
- https://docs.blender.org/api/current/bpy.types.bpy_struct.html
- https://docs.blender.org/api/main/bpy.types.BlendDataLibraries.html
- https://apps.kde.org/glaxnimate/
- https://glaxnimate.org/contributing/scripting/

Existing web search was sufficient after Firecrawl exhausted its credits.
Blender is separately installed GPL software; its binaries are not embedded
or relicensed under this repository's MIT license.

## Public native project interface

`body.motion_project` accepts a model-authored `zx7-native-motion/1` document.
It exposes native RNA properties and collections instead of compiling a fixed
set of shapes or effects. `describe` discovers installed property types, enum
choices and available data methods; `list` and `read` inspect actual values.
`set` edits native properties, pointers and array elements. `call` constructs
data, node connections, custom mesh topology, material slots, Geometry Nodes
interfaces and animation keys using the methods advertised in the ABI.

Paths start with `data` (Blender data), `scene` (active scene) or `refs` (named
call results). Literal JSON values and `{"$ref":[...]}` pointer references
compose actions. The queried document schema explains the ABI; Blender itself
supplies runtime property/enumeration data. Scene, frame, render settings,
dimensions, camera, lighting, materials and artistic values are authored controls.

Each transaction starts a fresh Blender process, opens an empty or sealed parent
project with auto-execution disabled, applies edits, saves a native project,
renders requested original frames and actually decodes their images. Errors
publish no project version. A `.zxmotion` bundle retains the `.blend`, renders,
native observations and member SHA256 manifest. Parent/job bytes are rechecked
before publication. Original versions remain available.

`body.motion_export` delivers authored PNG frame order as PNG or H264 MP4 at an
explicit integer fps. Generated output can enter existing BODY media custody for
downstream editing/sound. Existing publication recovery, physical source hashing
and durable stage verification apply to both tools.

## Validation and release gates

The pinned, checksum-verified **Blender 4.5.15 LTS** actually executed native text,
animation, custom geometry, material shader and a connected Geometry Nodes
modifier. A saved project was reopened to change typography and node inputs.
Actual pixels changed, the original project remained identical, and four public
execution stages plus generated-media custody reused verified results. A deliberately invalid native edit
must publish nothing and preserve its parent. Exact installed-package and CI
receipts are recorded separately. Historical 647-case acceptance belongs to the
older recorded source and is not acceptance of this change.

Completing production-grade motion design still requires representative substantial
jobs, verified host budgets and interruption/recovery during native rendering,
production-scale performance and artistic review with an actual configured AI.
The deterministic fixture is technical evidence, not aesthetic approval.

Current connection limits: only the advertised native data methods; packed
dependencies; no arbitrary Blender operators/Python execution; no external
footage or simulation-cache ingestion; no live interactive playback; picture-only
PNG/MP4 delivery, with float EXR retained inside the native bundle. Not every
Blender operator/import workflow is exposed. Other versions are not certified
by passing the minimum 4.5 runtime check. Work remains within motion design
until its release gates pass.
