"""Declarative real 3D shot engine; no scene template or LLM-authored code.

Validation works in ordinary CPython; bpy is imported only inside Blender. The
director is free to specify light rigs, meshes, keyframed cameras, materials,
composition and shot length. The current backend supports Blender Cycles CPU
plus original mesh geometry, and verified GLB objects. Its available operations
are NOT a global limit on future ZX7 production capabilities.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path


SHAPES = frozenset({"cube", "uv_sphere", "ico_sphere", "cylinder", "cone",
                    "torus", "plane", "custom_mesh", "licensed_glb"})
LIGHTS = frozenset({"AREA", "POINT", "SUN", "SPOT"})
_TRANSFORMS = frozenset({"location", "rotation_degrees", "scale"})


class Invalid3DShot(ValueError):
    pass


def _need(test, msg):
    if not test: raise Invalid3DShot(msg)


def _num(value, field, min_v=-1e7, max_v=1e7):
    _need(not isinstance(value, bool) and isinstance(value,(int,float))
          and math.isfinite(value) and min_v <= value <= max_v,
          field + " must be finite and in range")
    return float(value)


def _int(value, field, min_v=1):
    _need(isinstance(value,int) and not isinstance(value,bool) and value >= min_v,
          field + " must be a positive integer")
    return value


def _vec(value, count, field, min_v=-1e7, max_v=1e7):
    _need(isinstance(value,list) and len(value)==count, field+f" needs {count} numbers")
    return [_num(x,field,min_v,max_v) for x in value]


def _strict(value, required, optional, field):
    _need(isinstance(value,dict), field+" must be an object")
    _need(set(required).issubset(value) and set(value).issubset(set(required)|set(optional)),
          field+" missing required or contains unsupported fields")
    return value


def _keyframes(value, field, frame_count, dims):
    _need(isinstance(value,list) and value, field+" keyframes missing")
    prev=0
    for idx,key in enumerate(value):
        _strict(key,{"frame","value"},set(),field+f"[{idx}]")
        at=_int(key["frame"],field+".frame")
        _need(prev<at<=frame_count,field+" must be strictly increasing within shot")
        prev=at
        _vec(key["value"],dims,field+".value")


def _transform(o, label, frames):
    _vec(o["location"],3,label+".location")
    _vec(o["rotation_degrees"],3,label+".rotation_degrees")
    _vec(o["scale"],3,label+".scale",.0001,100000)
    a=o.get("animate",{})
    _need(isinstance(a,dict) and set(a).issubset(_TRANSFORMS),
          label+" animation may only contain named transform curves")
    for key,val in a.items():
        _keyframes(val,label+"."+key,frames,3)


def validate_blender_shot(job, *, verified_assets_root=None):
    """Validate all paths, geometry and animation before Blender gets commands."""
    _strict(job,{"shot_id","width","height","fps","frames","camera","world",
                 "materials","objects","lights"}, {"samples"}, "3D film shot")
    _need(isinstance(job["shot_id"],str) and 0<len(job["shot_id"])<100,
          "Shot ID required")
    _need(all(x.isalnum() or x in "._-" for x in job["shot_id"]),
          "Shot ID must not contain filesystem instructions")
    _int(job["width"],"width")
    _int(job["height"],"height")
    _int(job["fps"],"fps")
    frames=_int(job["frames"],"frames")
    _int(job.get("samples",8),"cycles CPU samples")
    _strict(job["world"],{"color","strength"},set(),"world")
    _vec(job["world"]["color"],3,"world.color",0,1)
    _num(job["world"]["strength"],"world.strength",0,100)
    cam=_strict(job["camera"],{"location","target","lens_mm"},
                {"animate_location","animate_target","depth_of_field"}, "camera")
    _vec(cam["location"],3,"camera.location")
    _vec(cam["target"],3,"camera.target")
    _need(cam["location"]!=cam["target"],"Camera cannot look at its own origin")
    _num(cam["lens_mm"],"camera.lens_mm",1,300)
    if "animate_location" in cam:
        _keyframes(cam["animate_location"],"camera.animate_location",frames,3)
    if "animate_target" in cam:
        _keyframes(cam["animate_target"],"camera.animate_target",frames,3)
    if "depth_of_field" in cam:
        _strict(cam["depth_of_field"],{"focus_distance","fstop"},set(),"depth_of_field")
        _num(cam["depth_of_field"]["focus_distance"],"focus_distance",.001,10000)
        _num(cam["depth_of_field"]["fstop"],"fstop",.1,100)
    mats=job["materials"]
    _need(isinstance(mats,list) and mats,"At least one authored material required")
    matids=set()
    for i,m in enumerate(mats):
        lab=f"material[{i}]"
        _strict(m,{"id","color","metallic","roughness"},set(),lab)
        _need(isinstance(m["id"],str) and m["id"].strip() and m["id"] not in matids,
              lab+" material ID duplicated/missing")
        matids.add(m["id"])
        _vec(m["color"],4,lab+".color",0,1)
        _num(m["metallic"],lab+".metallic",0,1)
        _num(m["roughness"],lab+".roughness",.001,1)
    objects=job["objects"]
    _need(isinstance(objects,list) and objects,"Real scene needs explicit 3D objects")
    objects_seen=set()
    for i,o in enumerate(objects):
        lab=f"object[{i}]"
        _strict(o,{"id","type","material","location","rotation_degrees","scale"},
                {"animate","vertices","faces","asset","rights"},lab)
        _need(isinstance(o["id"],str) and o["id"].strip()
              and o["id"] not in objects_seen,lab+" ID duplicated/missing")
        objects_seen.add(o["id"])
        _need(o["type"] in SHAPES,lab+" geometry type unsupported by THIS 3D adapter")
        _need(o["material"] in matids,lab+" unknown material")
        _transform(o,lab,frames)
        if o["type"]=="custom_mesh":
            vs=o.get("vertices")
            faces=o.get("faces")
            _need(isinstance(vs,list) and len(vs)>=3 and isinstance(faces,list) and faces,
                  lab+" explicit vertices/faces required")
            for v in vs: _vec(v,3,lab+".vertex")
            for face in faces:
                _need(isinstance(face,list) and 3<=len(face) and len(set(face))==len(face)
                      and all(isinstance(index,int) and not isinstance(index,bool)
                              and 0<=index<len(vs) for index in face),
                      lab+" invalid polygon")
        elif o["type"]=="licensed_glb":
            _need(verified_assets_root is not None,lab+" needs approved local asset root")
            _need(o.get("rights") in ("owner_supplied","appropriately_licensed"),
                  lab+" model rights missing")
            rel=o.get("asset")
            _need(isinstance(rel,str) and rel.endswith(".glb")
                  and not Path(rel).is_absolute() and len(Path(rel).parts)>0
                  and all(part not in ("..",".") for part in Path(rel).parts),
                  lab+" only local relative .glb allowed")
            root=Path(verified_assets_root).resolve()
            path=(root/rel).resolve()
            _need(path.is_relative_to(root) and path.is_file(),lab+" verified .glb missing/escapes root")
        else:
            _need(not any(k in o for k in ("vertices","faces","asset","rights")),
                  lab+" must not hide extra geometry")
    lights=job["lights"]
    _need(isinstance(lights,list) and lights,"Director must specify actual light rig")
    lightids=set()
    for i,l in enumerate(lights):
        lab=f"light[{i}]"
        _strict(l,{"id","type","location","rotation_degrees","energy","color"},
                {"size"},lab)
        _need(isinstance(l["id"],str) and l["id"] and l["id"] not in lightids,
              lab+" duplicate light")
        lightids.add(l["id"])
        _need(l["type"] in LIGHTS,lab+" unsupported light")
        _vec(l["location"],3,lab+".location")
        _vec(l["rotation_degrees"],3,lab+".rotation")
        _num(l["energy"],lab+".energy",0,10000000)
        _vec(l["color"],3,lab+".color",0,1)
        if "size" in l:
            _num(l["size"],lab+".size",.01,10000)
    return job


def render_blender_shot(job, out: Path, *, verified_assets_root=None,
                        original_exr_passes=False, frame_start=None, frame_end=None):
    """This entry point must run under installed Blender, never eval model code."""
    validate_blender_shot(job,verified_assets_root=verified_assets_root)
    # Validate the ACTUAL full authored scene before building any subset.
    # This changes execution granularity, never the artist's animation clock.
    if frame_start is not None or frame_end is not None:
        if (type(frame_start) is not int or type(frame_end) is not int or
                not 1 <= frame_start <= frame_end <= job["frames"]):
            raise Invalid3DShot("Render range must be an ordered inclusive subset of original shot")
    import bpy
    from math import radians
    from mathutils import Vector

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene
    scene.render.engine="CYCLES"
    scene.cycles.device="CPU"
    scene.cycles.samples=job.get("samples",8)
    # Ubuntu free CPU builds may not include OpenImageDenoiser; do not require it.
    for view_layer in scene.view_layers:
        if hasattr(view_layer, "cycles") and hasattr(view_layer.cycles, "use_denoising"):
            view_layer.cycles.use_denoising=False
    scene.render.resolution_x=job["width"]
    scene.render.resolution_y=job["height"]
    scene.render.resolution_percentage=100
    scene.render.film_transparent=bool(original_exr_passes)
    if original_exr_passes:
        scene.render.image_settings.file_format="OPEN_EXR_MULTILAYER"
        scene.render.image_settings.color_mode="RGBA"
        scene.render.image_settings.color_depth="32"
        scene.render.image_settings.exr_codec="ZIP"
        layer=scene.view_layers[0]
        layer.use_pass_z=True
        layer.use_pass_vector=True
        layer.use_pass_normal=True
        layer.use_pass_diffuse_color=True
    else:
        scene.render.image_settings.file_format="PNG"
        scene.render.image_settings.color_mode="RGB"
    scene.frame_start=1 if frame_start is None else frame_start
    scene.frame_end=job["frames"] if frame_end is None else frame_end
    scene.render.fps=job["fps"]
    world=bpy.data.worlds.new("ZX7 director-owned world")
    scene.world=world
    world.use_nodes=True
    bg=world.node_tree.nodes.get("Background")
    if bg is None:
        bg=next(n for n in world.node_tree.nodes if n.type=="BACKGROUND")
    bg.inputs["Color"].default_value=(*job["world"]["color"],1.)
    bg.inputs["Strength"].default_value=job["world"]["strength"]

    materials={}
    for raw in job["materials"]:
        m=bpy.data.materials.new(raw["id"])
        m.use_nodes=True
        principled=m.node_tree.nodes.get("Principled BSDF")
        principled.inputs["Base Color"].default_value=raw["color"]
        principled.inputs["Metallic"].default_value=raw["metallic"]
        principled.inputs["Roughness"].default_value=raw["roughness"]
        materials[raw["id"]]=m

    def animate_transform(obj, data):
        for name, tracks in data.get("animate",{}).items():
            attr="rotation_euler" if name=="rotation_degrees" else name
            for p in tracks:
                v=p["value"]
                setattr(obj,attr,tuple(radians(x) for x in v) if name=="rotation_degrees" else v)
                obj.keyframe_insert(data_path=attr,frame=p["frame"])
        for fcurve in (obj.animation_data.action.fcurves if obj.animation_data and
                       hasattr(obj.animation_data.action,"fcurves") else []):
            for kp in fcurve.keyframe_points:kp.interpolation="BEZIER"

    for raw in job["objects"]:
        kind=raw["type"]
        if kind=="licensed_glb":
            path=(Path(verified_assets_root)/raw["asset"]).resolve()
            before=set(bpy.context.scene.objects)
            bpy.ops.import_scene.gltf(filepath=str(path))
            imported=[o for o in bpy.context.scene.objects if o not in before and o.type=="MESH"]
            _need(imported,"GLB has no usable meshes")
            # Parent imported meshes under an explicitly controllable empty.
            master=bpy.data.objects.new(raw["id"],None)
            scene.collection.objects.link(master)
            for m in imported:m.parent=master
            obj=master
        elif kind=="custom_mesh":
            mesh=bpy.data.meshes.new(raw["id"]+" geometry")
            mesh.from_pydata(raw["vertices"],[],raw["faces"])
            mesh.update()
            obj=bpy.data.objects.new(raw["id"],mesh)
            scene.collection.objects.link(obj)
        else:
            op={"cube":bpy.ops.mesh.primitive_cube_add,
                "uv_sphere":bpy.ops.mesh.primitive_uv_sphere_add,
                "ico_sphere":bpy.ops.mesh.primitive_ico_sphere_add,
                "cylinder":bpy.ops.mesh.primitive_cylinder_add,
                "cone":bpy.ops.mesh.primitive_cone_add,
                "torus":bpy.ops.mesh.primitive_torus_add,
                "plane":bpy.ops.mesh.primitive_plane_add}[kind]
            op()
            obj=bpy.context.object
            obj.name=raw["id"]
        if obj.type=="MESH":obj.data.materials.append(materials[raw["material"]])
        obj.location=raw["location"]
        obj.rotation_euler=[radians(x) for x in raw["rotation_degrees"]]
        obj.scale=raw["scale"]
        animate_transform(obj,raw)
        if obj.type=="MESH":
            for face in obj.data.polygons: face.use_smooth = kind not in ("plane","cube")

    for spec in job["lights"]:
        light_data=bpy.data.lights.new(spec["id"],spec["type"])
        light_data.energy=spec["energy"]
        light_data.color=spec["color"]
        if spec["type"]=="AREA":
            light_data.shape="DISK"
            light_data.size=spec.get("size",2.)
        light_obj=bpy.data.objects.new(spec["id"],light_data)
        scene.collection.objects.link(light_obj)
        light_obj.location=spec["location"]
        light_obj.rotation_euler=[radians(x) for x in spec["rotation_degrees"]]

    cam_data=bpy.data.cameras.new("ZX7 camera")
    cam=bpy.data.objects.new("ZX7 directed camera",cam_data)
    scene.collection.objects.link(cam)
    scene.camera=cam
    cam.location=job["camera"]["location"]
    cam_data.lens=job["camera"]["lens_mm"]
    target=bpy.data.objects.new("ZX7 director target",None)
    scene.collection.objects.link(target)
    target.location=job["camera"]["target"]
    constraint=cam.constraints.new(type="TRACK_TO")
    constraint.target=target
    constraint.track_axis="TRACK_NEGATIVE_Z"
    constraint.up_axis="UP_Y"
    for field,obj in (("animate_location",cam),("animate_target",target)):
        for key in job["camera"].get(field,[]):
            obj.location=key["value"]
            obj.keyframe_insert(data_path="location",frame=key["frame"])
    if "depth_of_field" in job["camera"]:
        spec=job["camera"]["depth_of_field"]
        cam_data.dof.use_dof=True
        cam_data.dof.focus_distance=spec["focus_distance"]
        cam_data.dof.aperture_fstop=spec["fstop"]
    out=Path(out)
    out.mkdir(parents=True,exist_ok=True)
    scene.render.filepath=str(out/"frame_")
    bpy.ops.render.render(animation=True)
    return {"shot_id":job["shot_id"],"frames":job["frames"],"fps":job["fps"],
            "format":("scene-linear multilayer 32-bit float OpenEXR RGBA, depth, normal and vector"
                      if original_exr_passes else
                      "PNG sequence; video encoding requires reviewed FFmpeg adapter"),
            "renderer":"real Blender Cycles CPU 3D; artistic quality not certified"}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scene",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--assets-root",type=Path,default=None)
    p.add_argument("--exr-passes",action="store_true",
                   help="Physical 32-bit float linear multi-pass VFX EXR instead of display PNG")
    p.add_argument("--frame-start",type=int,default=None,
                   help="Original 1-based absolute render frame start (inclusive)")
    p.add_argument("--frame-end",type=int,default=None,
                   help="Original 1-based absolute render frame end (inclusive)")
    import sys
    args=p.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else None)
    job=json.loads(args.scene.read_text(encoding="utf-8"))
    print(json.dumps(render_blender_shot(job,args.out,verified_assets_root=args.assets_root,
                 original_exr_passes=args.exr_passes,
                 frame_start=args.frame_start,frame_end=args.frame_end),
                     indent=2),flush=True)


if __name__ == "__main__":
    main()
