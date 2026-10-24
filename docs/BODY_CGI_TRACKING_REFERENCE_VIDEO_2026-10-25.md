# Public BODY: CGI, measured planar VFX and reference video inputs

The owner authorized improving the public production BODY, rather than installing
a tool available only inside ChatGPT. This change adds native operations to the
same authenticated service, tool discovery, document contracts, source custody,
durable graph and output-publication machinery. It does not select a screenplay,
visual style or replacement creative Brain.

## Actual public operations

| Operation | New behavior | Required host runtime |
|---|---|---|
| `body.cgi_shot` | Original Cycles scene with frozen, attested texture/GLB assets | Blender, FFmpeg, FFprobe |
| `body.planar_insert` | Measures footage motion, corner-pins PNG art, protects supplied foreground masks, preserves original sound when requested | `.[vfx_tracking]`, FFmpeg, FFprobe |
| `body.generate_video` | Can pass owned reference PNGs into operator-installed native workflow slots; additional engine identities discovered from deployments | Actual compatible CUDA GPU, licensed verified weights, local ComfyUI, valid installed workflow |

Tools retain `needs_setup` when their runtime is absent. Registering a provider
does not prove it has generated a movie.

## CGI scene and asset contract

Invoke `body.cgi_shot` with `{"plan":"cgi-plan.json","out":"product.mp4"}`.
The plan has exactly `scene` and `assets`:

```json
{
  "scene": {"shot_id":"artist-authored-scene"},
  "assets": [{
    "name":"label.png",
    "media": {"source":"owned/label.png","asset_id":"ACTUAL_SHA256","attestation_id":"ACTUAL_ATTESTATION"}
  }]
}
```

The abbreviated scene above is illustrative, not a runnable scene. Obtain the
complete machine-readable scene contract through authenticated
`GET /v1/tools/body.cgi_shot` or `document_contract()` in
`studio_next.body_document_schemas`. A complete authored acceptance example is
created by `python -m studio_next.body_cgi_proof --workspace /absolute/new-folder`.
Its bottle is test art; it is not an imposed production template.

The original scene fields remain supported. Additions are:

- Principled material transmission, IOR, coat, coat roughness, sheen, emission,
  color/roughness/metallic/normal/emission PNG/JPEG maps and optional texture alpha.
  Color and emission maps use sRGB; data maps use Non-Color.
- Equirectangular PNG/JPEG environment with authored rotation. This is currently
  an LDR environment input, not an HDR/EXR environment import.
- `lathe`: strictly increasing `[radius,z]` profile, authored `segments` and
  `caps`; generated surface UVs. `custom_mesh` accepts per-polygon loop `uvs`.
- `empty` transform rigs; explicit object parents with cycle rejection;
  LINEAR/BEZIER/CONSTANT object transform interpolation.
- Explicit bevel, solidify and subdivision modifier stacks.
- Camera lens and focus-distance keyframes; focus requires depth of field.
- Rectangular/elliptical area lights with separate dimensions, optional denoise.

Every referenced image/model must appear exactly once in the asset manifest.
Original custody is verified and immutable private copies enter Blender. GLB
rights labels must agree with the real attestation. Changed plan/source bytes
fail publication. Existing output movies are never overwritten.

## Measured planar insertion

Invoke `body.planar_insert` with `{"plan":"insert.json","out":"inserted.mp4"}`.

```json
{
  "media":{"source":"shot.mp4","asset_id":"ACTUAL_SHA256","attestation_id":"ACTUAL_ATTESTATION"},
  "overlay":{"source":"art.png","asset_id":"ACTUAL_SHA256","attestation_id":"ACTUAL_ATTESTATION"},
  "quad":[[40,30],[240,40],[230,180],[45,175]],
  "tracking":{"max_features":1800,"min_matches":10,"min_inlier_ratio":0.55,"ransac_pixels":2,"max_reprojection_error":1.5},
  "opacity":0.9,
  "audio":"preserve_source"
}
```

The ordered corners identify a textured plane in the first source frame. SIFT
matches and RANSAC independently estimate reference-to-current-frame motion.
Insufficient texture, lost matches, flipped/degenerate geometry or excessive
reprojection error stop the shot. There is no static fallback.

Optional `foreground` is `{"media":SOURCE,"kind":"still_image"}` or `video`.
White mask pixels preserve original footage; black permits insertion. Moving
masks must share the exact source frame clock. This operation accepts attested
CFR SDR BT709 MP4 and PNG art. It composites premultiplied alpha in 8-bit SDR;
the existing separate EXR/ACES tools remain the scene-linear finishing path.
`preserve_source` copies the first original audio stream without re-encoding;
`intentional_silence` explicitly omits it.

This is **planar tracking**, not a general 3D camera solve, automatic human
rotoscoping, deformable object tracking or a claim of invisible VFX on any shot.
Direct-camera-projected test footage provides independent corner ground truth;
it must not be described as externally captured client footage.

## Additional self-hosted video engines and reference slots

Set `ZX7_VIDEO_DEPLOYMENTS` to the operator's installed deployment root and
`ZX7_COMFY_API` to the explicit loopback ComfyUI origin. Existing candidates
remain visible. An additional path-safe model directory can declare:

```json
{
  "model_id":"owned-engine",
  "model_metadata":{"repo":"actual/upstream","license_metadata":"verified-license","capabilities":["image_to_video"]},
  "license_accepted_or_verified":true,
  "minimum_locally_verified_vram_mb":24000,
  "required_comfyui_nodes":["ActualInstalledNode","SaveVideo"],
  "required_weight_roles":["checkpoint"],
  "weight_sha256":"ACTUAL_COMPONENT_SHA256",
  "weight_files":[{"role":"checkpoint","path":"checkpoint.safetensors","sha256":"ACTUAL_COMPONENT_SHA256"}]
}
```

These are installer attestations and verified file hashes, not a way to prove
arbitrary bytes are a working neural model. Declare every real required model
component and preserve upstream license/revision provenance. Existing legacy
deployments still require diffusion, VAE and text encoder roles by default.

`workflow.json` is a real ComfyUI API graph installed by the operator.
`bindings.json` retains its original `model_id`, `output_node` and `inputs`
mapping (prompt, frames, width, height and fps are required). Optional additions:

```json
{
  "images":{"product":{"node":"LOAD_IMAGE_NODE_ID","key":"image"}},
  "required_images":["product"]
}
```

An authored video job may supply `"images":[{"binding":"product","media":SOURCE}]`.
Only explicitly registered, distinct graph slots are changed. An owned, decoded
PNG is uploaded to local `/upload/image` in `zx7-body/<actual-sha256>.png`.
Ambient HTTP proxies and redirects are prohibited. Wrong server receipts,
missing/duplicate bindings, source changes and undeclared inputs are rejected.
Workflow, bindings, reference bytes and actual model weight identities invalidate
both DAG reuse and native job checkpoints when changed.

Real multipart transport, custody and codec tests are not evidence of an actual
conditioned AI performance. **No GPU/human-video inference was verified in this
change.**

## Verification and remaining scope

Local real Blender 4.5.15 CPU rendered a 512-square, 36-frame glass/liquid/metal
product shot with curved UV label and moving camera. A separate 24-frame
tracked/occluded composite preserved the decoded original audio exactly.
Automated tests also compare measured corners against independent 3D projection
and reject deliberately lost tracks. New CI exercises an installed wheel with
real Blender media; the existing complete native regression remains separate.
Check the companion checkpoint for exact source/run identity and counts.

This expands the production BODY. It does not certify a universal finished
studio, autonomous artistic excellence, real human acting generation, character
rigging/animation, fluid/cloth/particle simulation, general camera solving,
automatic roto/relighting or independent customer-conversion performance.
Those require additional real runtime integration and physical acceptance.

Primary technical references: [Blender Principled BSDF](https://docs.blender.org/manual/en/4.5/render/shader_nodes/shader/principled.html),
[OpenCV homography tutorial](https://docs.opencv.org/4.x/d1/de0/tutorial_py_feature_homography.html).
