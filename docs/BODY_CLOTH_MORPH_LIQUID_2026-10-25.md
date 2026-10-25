# Public BODY: cloth, topology-preserving morphs and native liquid meshes

This extends the existing public `body.cgi_shot` operation and its discoverable
JSON scene contract. The director authors geometry, physics, materials, camera
and timing. There is no imposed film, product, cloth layout or liquid preset.
The existing source-custody, real decode, publication, revision fingerprints
and host permission boundaries remain in force.

## Native controls

| Scene data | Actual execution | Boundary |
|---|---|---|
| `custom_mesh.shape_keys` | Basis-relative native Blender shape keys, independent weights, curves and LINEAR/BEZIER/CONSTANT interpolation | Explicit matching vertex count/order; no imported skeletal rig or acting generator |
| `custom_mesh.cloth` | Native cloth solver with authored mass, stiffness, damping, quality, weighted pins, environmental and self-collision controls | Unparented control mesh; no competing object transform animation/rigid/liquid simulation |
| `cloth_collision` | Native mesh collision with explicit shell distances, damping and friction | Separate explicit collider; may follow ordinary authored transforms |
| `liquid_domain` | Actual Mantaflow liquid data/mesh bake with voxel resolution, mesh upscaling/radius, time scale, FLIP ratio and viscosity | One static box domain per shot; verified Blender 4.5+ runtime required |
| `liquid_flow` | Initial volume, continuous inflow or outflow, source surface distance and initial velocity | Explicit closed source geometry; moving sources use INFLOW rather than a one-time GEOMETRY emission |
| `liquid_obstacle` | Native fluid effector, surface distance and planar/closed collision choice | Explicit mesh; no simultaneous cloth/rigid/morph role on that object |

The common `physics.gravity` world now also accepts cloth-only or liquid-only
scenes. Rigid substeps/iterations remain required when rigid bodies exist;
they are rejected as unused controls when there is no rigid body.

Query the current `body.cgi_shot` plan schema through the existing model-facing
interface. Complete original technical commissions are packaged as
`cloth_drape_shot.json`, `mesh_morph_shot.json` and `liquid_impact_shot.json`
under `studio_next/fixtures`. They are examples and acceptance fixtures, not
renderer templates. The artist may author unrelated original mesh data.

## Original-clock cloth and morph behavior

The cloth solver evaluates the complete original shot from frame 1. Evaluated
control-mesh poses are retained, the solver modifier is removed, and the poses
are baked into linear shape-key curves. Finishing subdivision/solidify/bevel
modifiers are added after that bake. The solver therefore sees the artist's
original topology rather than silently simulating a subdivided or shelled mesh.

The requested render range is restored only after simulation. A cold render
of the last frame must match its decoded RGB pixels and geometry report in a
whole-sequence render. Weighted pin positions, geometry hashes, bounds and
maximum solved vertex displacement are recorded from actual native geometry.
Interpolation between integer-frame baked poses is linear; this is not a claim
of continuous-time cloth integration at every arbitrary subframe.

Authored morph curves have independently selected interpolation. Applying a
second shape key cannot silently change the interpolation of the first one.
Topology remains fixed, so original geometry/UV identity is preserved.

## Actual liquid bake and runtime limitation

The trusted renderer assigns an internal cache directory below its private
frame output, sets the full authored cache frame range and invokes the native
liquid bake. It requires both native baked-data/mesh flags and one physical
mesh-cache file per authored frame. It then inspects the actual evaluated
surface for every frame. Flow-source objects are hidden from the final render
after baking, so the generated liquid is not covered by its original emitter.
Cache destinations cannot be supplied by the model.

Liquid acceptance requires nonempty changing surface topology, gravity-driven
surface motion, a real viscosity-dependent geometry change, public BODY
render/decode/custody, exact stage reuse and original-clock picture/geometry
agreement between full and late-frame renders on the tested native runtime.
Cold subsets currently rebake the full simulation. Persisted cross-host fluid
caches, domain coupling and distributed simulation recovery are not supplied.

The inspected distro Blender 4.0.2 liquid bake aborted inside native Mantaflow
Python initialization. The adapter now rejects liquid scenes on Blender <4.5
before initializing a scene or entering that bake. Native cloth/morph paths
retain separate Blender 4.0 acceptance. The installed-package liquid gate uses
the existing pinned Blender 4.5.15 LTS distribution.

Variable-topology liquid velocity-aware motion blur and the existing required
EXR vector-pass contract are not implemented here. These combinations fail
before rendering; a changing-topology surface is never advertised as providing
valid VFX motion vectors. The existing non-liquid EXR path remains separate.
This change adds liquids, not smoke/fire gas simulation, fracture, soft bodies,
skeletal skinning, facial performance or a generative human/video model.

## Verification

```bash
python -m unittest studio_next.test_deform_simulations -v
python -m studio_next.body_deform_proof --workspace /absolute/new-folder
```

The unit native commission explicitly tests cloth/morphs and records that
liquid was not requested. The separately installed package proof requires
liquid by default. The release workflow rejects missing liquid execution or
failed original-clock comparisons; it does not treat an omitted liquid check
as a pass. The checkpoint records exact native versions, test counts and
matching CI runs. Technical acceptance does not certify premium artistic
quality, independent creative inference or a finished universal studio.

Official API sources consulted:

- [Cloth settings](https://docs.blender.org/api/4.5/bpy.types.ClothSettings.html)
- [Cloth collision settings](https://docs.blender.org/api/4.5/bpy.types.ClothCollisionSettings.html)
- [Object collision settings](https://docs.blender.org/api/4.5/bpy.types.CollisionSettings.html)
- [Fluid domain settings](https://docs.blender.org/api/4.5/bpy.types.FluidDomainSettings.html)
- [Fluid flow settings](https://docs.blender.org/api/4.5/bpy.types.FluidFlowSettings.html)
- [Native fluid operators](https://docs.blender.org/api/4.5/bpy.ops.fluid.html)
