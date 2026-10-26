# Public BODY: physical CGI controls and native acceptance

The owner requested substantially better CGI under one creative AI's control.
This change extends the existing public `body.cgi_shot` scene contract. The
same controls also reach `body.blender3d`, `body.exr_passes` and
`body.exr_checkpoint`; their existing custody requirements still apply.
It adds no screenplay, aesthetic preset, creative model, hosted generation
service or unapproved executable scene code.

The previous implementation already provided PBR maps, glass, radial geometry,
rigs, camera/focus animation, frozen sources, planar tracking, EXR/ACES and
generator-reference plumbing. Those features are retained.

## New artist controls

| Area | Explicit scene data | Native behavior |
|---|---|---|
| Light transport | `render_settings` seed, adaptive threshold, total/diffuse/glossy/transmission/volume/transparent bounces | Actual Cycles properties; no automatic artistic preset |
| Exposure and shutter | Named available view transform, display exposure, shutter duration and START/CENTER/END position | Physical multi-sampled 3D motion blur; exposure/view affect display PNGs, not scene-linear EXR values |
| Material response | Anisotropy/rotation, subsurface weight/radius/scale, coat IOR, sheen roughness | Principled BSDF inputs with explicit unsupported-version errors |
| Microdetail | Authored 3D noise frequency/detail/distortion/mapping; bump and optional roughness/color ranges | Real procedural nodes; bump layers over an existing verified normal map |
| Volume | Absorption and/or scattering color/density, scattering anisotropy | Volume closures connected to the material output; absorption depends on interior path length |
| Material animation | Scalar Principled inputs, base RGBA and emission RGB, interpolation | Editable native node-tree keyframe curves on the original frame clock |
| Lighting animation | Location/rotation, energy and color curves, interpolation | Actual light object/data animation |
| Optics | Sensor width, lens shifts, focus object, aperture blades/ratio/rotation, camera interpolation | Native camera and DOF controls; focus can follow a simulated or animated object |
| Physics | Authored gravity, substeps, iterations and active/passive collider properties | Actual Blender Bullet world; dynamic trajectories baked to transforms for rendering |

All additions are optional. Existing scenes retain their previous inputs.
Per-operation machine-readable document contracts are available through the
existing authenticated tool-description API and Python `document_contract()`.
No defaults are injected into that schema to choose a film's style.

## Physics execution and supported boundary

Objects explicitly supply collider shape, active/passive role, mass, friction,
restitution, linear/angular damping, collision margin and kinematic choice.
Colliders must be explicit unparented meshes. Imported GLB hierarchies, active
concave MESH colliders and animated collider scale are rejected here. A dynamic
transform cannot simultaneously be controlled by authored transform curves.
Kinematic bodies may use authored translation/rotation.

The trusted renderer evaluates Bullet sequentially from frame 1 through the
whole authored shot. It records evaluated dynamic world poses, disables the
simulation and writes linear translation/quaternion curves. The requested
output frame range is applied after this bake. Resuming at frame 6 therefore
does not initialize a falling object at its original height. Motion blur of
the baked dynamic poses uses interpolation between the integer-frame samples;
this does not claim continuous solver integration at every shutter sample.
Long shots currently pay the full simulation warmup cost for each cold subset.

The existing EXR tools require meaningful unblurred vector passes. Blender
suppresses their motion vectors when physical shutter blur is enabled (the
channels still exist but contain zeros in the inspected moving-scene render).
These EXR entry points therefore reject `render_settings.motion_blur` before
launching Blender. Choose an unblurred EXR pass render or a physically blurred
CGI MP4 render explicitly; this change does not silently issue empty VFX data.

This is rigid-body simulation. Fluid, cloth, soft-body, fracture, constraints,
forces and a general 3D camera solve are not added by this change. Likewise,
HDR environment import, arbitrary shader/Geometry Nodes graphs, a GPU backend
and skeletal facial acting are not certified by these controls.

## Source safety, revisions and evidence

Scene validation rejects unrecognized nested fields, non-finite/out-of-range
properties, conflicting animation/texture inputs and invalid focus targets.
Existing frozen, attested image/GLB handling is unchanged. No shader code,
model-authored Python or shell command is accepted as scene data.

Blender writes a physical control report beside its intermediate frames. The
MP4 adapter carries it through the CGI receipt: actual Blender version, CPU
device, samples, shutter, bounces, optics, animated material/light identities,
volume/procedural identities and sampled real solver positions. During a
publication-only recovery, the tool does not invent missing render observations.
Durable cache reuse retains the previously committed receipt. Renderer source
and authored scene bytes already participate in the existing stage signatures;
changed controls invalidate the affected CGI stage.

The complete acceptance commission is
`studio_next/fixtures/advanced_cgi_physics_shot.json`. It is technical test art,
not a supplied production template or an independently authored AI film.

```bash
python -m unittest studio_next.test_cgi_controls -v
python -m studio_next.body_cgi_controls_proof --workspace /absolute/new-folder
```

The real native proof checks:

- Public CGI graph render, full MP4 decode, generated-source custody and all
  three nodes reused on retry without changing movie bytes or modification time.
- A sphere falling from z=2 and settling on an actual floor collider near z=0.4.
- The same original frame rendered in a full sequence and a cold frame subset:
  native solver trajectories (including hashes of every baked pose matrix)
  must match exactly. RGB may differ by at most one 8-bit code value in no
  more than 0.1% of pixels; both the measured difference and whether pixels
  are truly identical are recorded. PNG container metadata such as render
  time is not compared as picture content.
- Separate renders with changed volume density and surface detail must have
  measured pixel differences.
- An independent self-lit moving-object experiment must have a wider rendered
  support with the shutter open. A JSON motion-blur flag alone is insufficient.

The release workflow runs the contracts/native test in its system-Blender suite,
then runs the proof again through the separately installed wheel with pinned
Blender 4.5.15. Its aggregate evidence now requires the control proof. Technical
acceptance is separate from skilled human evaluation of a finished film.

## Evidence consulted

- Official [Principled BSDF manual for Blender 4.0](https://docs.blender.org/manual/en/4.0/render/shader_nodes/shader/principled.html).
- Official [RigidBodyObject Python API](https://docs.blender.org/api/4.0/bpy.types.RigidBodyObject.html).
- Official [RenderSettings Python API](https://docs.blender.org/api/4.0/bpy.types.RenderSettings.html).
- Actual renderer execution under Blender 4.0.2 and 4.5.15 LTS; exact local
  and remote acceptance outcomes are recorded in the companion checkpoint.

No local creative LLM/VLM, text-to-video model, voice inference or independent
professional film-quality comparison is claimed for this engineering change.
The universal studio remains incomplete; keep the existing PR draft/unmerged.

The initial remote minimal-dependency job exposed a pre-existing 160ms lease-test scheduling race. Its regression now observes real SQLite renewals against a controlled clock and uses signals for owner-loss observation. Production lease behavior and the duplicate-render rejection assertion are unchanged. Matching rerun outcomes are in the checkpoint.
