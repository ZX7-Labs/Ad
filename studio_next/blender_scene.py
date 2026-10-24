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
                    "torus", "plane", "custom_mesh", "licensed_glb", "lathe", "empty"})
LIGHTS = frozenset({"AREA", "POINT", "SUN", "SPOT"})
_TRANSFORMS = frozenset({"location", "rotation_degrees", "scale"})
_MAPS = frozenset({"base_color_texture", "roughness_texture", "metallic_texture",
                   "normal_texture", "emission_texture"})
_PBR = {"transmission":(0,1),"ior":(1,4),"coat":(0,1),
        "coat_roughness":(0,1),"sheen":(0,1),"emission_strength":(0,100000),
        "normal_strength":(0,10)}


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
    _need(o.get("interpolation","BEZIER") in ("LINEAR","BEZIER","CONSTANT"),
          label+" unsupported interpolation")


def _asset(name, root, label, suffixes):
    _need(isinstance(name,str) and name and len(name)<512 and "\\" not in name
          and ":" not in name and not Path(name).is_absolute()
          and all(p not in ("..", ".") and not p.startswith(".") for p in name.split("/"))
          and Path(name).suffix.lower() in suffixes,label+" requires a local asset name")
    _need(root is not None,label+" needs approved local asset root")
    base=Path(root).resolve();file=(base/name).resolve()
    _need(file.is_relative_to(base) and file.is_file(),label+" asset missing/escapes root")


def referenced_scene_assets(job):
    """Names only. Authenticated custody is supplied by the CGI plan adapter."""
    found={m[k] for m in job.get("materials",[]) for k in _MAPS if k in m}
    found.update(o["asset"] for o in job.get("objects",[]) if o.get("type")=="licensed_glb")
    if "environment_texture" in job.get("world",{}):found.add(job["world"]["environment_texture"])
    return found


def lathe_geometry(profile,segments,caps):
    """Author-owned surface of revolution with actual UV coordinates."""
    vertices=[];faces=[];uvs=[]
    low,high=profile[0][1],profile[-1][1]
    for radius,z in profile:
        for i in range(segments):
            angle=2*math.pi*i/segments;vertices.append([radius*math.cos(angle),radius*math.sin(angle),z])
    for ring in range(len(profile)-1):
        for i in range(segments):
            j=(i+1)%segments
            faces.append([ring*segments+i,ring*segments+j,(ring+1)*segments+j,(ring+1)*segments+i])
            a=(profile[ring][1]-low)/(high-low);b=(profile[ring+1][1]-low)/(high-low)
            uvs.append([[i/segments,a],[(i+1)/segments,a],[(i+1)/segments,b],[i/segments,b]])
    if caps:
        for ring,reverse in ((0,True),(len(profile)-1,False)):
            indices=list(range(segments));indices=indices[::-1] if reverse else indices
            faces.append([ring*segments+i for i in indices])
            uvs.append([[.5+.5*math.cos(2*math.pi*i/segments),.5+.5*math.sin(2*math.pi*i/segments)] for i in indices])
    return vertices,faces,uvs


def validate_blender_shot(job, *, verified_assets_root=None):
    """Validate all paths, geometry and animation before Blender gets commands."""
    _strict(job,{"shot_id","width","height","fps","frames","camera","world",
                 "materials","objects","lights"}, {"samples","denoise"}, "3D film shot")
    _need(isinstance(job["shot_id"],str) and 0<len(job["shot_id"])<100,
          "Shot ID required")
    _need(all(x.isalnum() or x in "._-" for x in job["shot_id"]),
          "Shot ID must not contain filesystem instructions")
    _int(job["width"],"width")
    _int(job["height"],"height")
    _int(job["fps"],"fps")
    frames=_int(job["frames"],"frames")
    _int(job.get("samples",8),"cycles CPU samples")
    _need(type(job.get("denoise",False)) is bool,"denoise must be boolean")
    _strict(job["world"],{"color","strength"},{"environment_texture","environment_rotation_degrees"},"world")
    _vec(job["world"]["color"],3,"world.color",0,1)
    _num(job["world"]["strength"],"world.strength",0,100)
    if "environment_texture" in job["world"]:
        _asset(job["world"]["environment_texture"],verified_assets_root,"world.environment_texture",{".png",".jpg",".jpeg"})
    if "environment_rotation_degrees" in job["world"]:
        _need("environment_texture" in job["world"],"Environment rotation requires a texture")
        _num(job["world"]["environment_rotation_degrees"],"environment rotation",-36000,36000)
    cam=_strict(job["camera"],{"location","target","lens_mm"},
                {"animate_location","animate_target","depth_of_field","animate_lens_mm","animate_focus_distance"}, "camera")
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
    for key,low,high in (("animate_lens_mm",1,300),("animate_focus_distance",.001,10000)):
        if key not in cam:continue
        if key=="animate_focus_distance":_need("depth_of_field" in cam,"Animated focus requires depth of field")
        _keyframes(cam[key],"camera."+key,frames,1)
        for p in cam[key]:_num(p["value"][0],key,low,high)
    mats=job["materials"]
    _need(isinstance(mats,list) and mats,"At least one authored material required")
    matids=set()
    for i,m in enumerate(mats):
        lab=f"material[{i}]"
        _strict(m,{"id","color","metallic","roughness"},set(_PBR)|_MAPS|{"emission_color","texture_alpha"},lab)
        _need(isinstance(m["id"],str) and m["id"].strip() and m["id"] not in matids,
              lab+" material ID duplicated/missing")
        matids.add(m["id"])
        _vec(m["color"],4,lab+".color",0,1)
        _num(m["metallic"],lab+".metallic",0,1)
        _num(m["roughness"],lab+".roughness",.001,1)
        for key,(low,high) in _PBR.items():
            if key in m:_num(m[key],lab+"."+key,low,high)
        if "emission_color" in m:_vec(m["emission_color"],3,lab+".emission_color",0,1)
        if "texture_alpha" in m:
            _need(type(m["texture_alpha"]) is bool and "base_color_texture" in m,lab+" texture alpha needs a color texture")
        for key in _MAPS:
            if key in m:_asset(m[key],verified_assets_root,lab+"."+key,{".png",".jpg",".jpeg"})
    objects=job["objects"]
    _need(isinstance(objects,list) and objects,"Real scene needs explicit 3D objects")
    objects_seen=set()
    for i,o in enumerate(objects):
        lab=f"object[{i}]"
        _strict(o,{"id","type","material","location","rotation_degrees","scale"},
                {"animate","vertices","faces","asset","rights","uvs","profile","segments","caps","modifiers","parent","interpolation"},lab)
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
            if "uvs" in o:
                _need(isinstance(o["uvs"],list) and len(o["uvs"])==len(faces),lab+" UV face count differs from geometry")
                for face,uv in zip(faces,o["uvs"]):
                    _need(isinstance(uv,list) and len(uv)==len(face),lab+" UV loop count differs from polygon")
                    for pair in uv:_vec(pair,2,lab+".uv",-10000,10000)
        elif o["type"]=="lathe":
            profile=o.get("profile");segments=o.get("segments")
            _need(isinstance(profile,list) and 2<=len(profile)<=512,lab+" lathe needs an authored radial profile")
            previous=-float("inf")
            for radius_z in profile:
                _vec(radius_z,2,lab+".profile")
                _need(radius_z[0]>.00001 and radius_z[1]>previous,lab+" profile radii must be positive and heights increasing")
                previous=radius_z[1]
            _need(type(segments) is int and 8<=segments<=512,lab+" lathe segments outside supported range")
            _need(type(o.get("caps")) is bool,lab+" choose open or closed lathe")
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
        if o["type"]!="custom_mesh":_need("uvs" not in o,lab+" UVs require explicit mesh loops")
        if o["type"]!="custom_mesh":_need(not any(k in o for k in ("vertices","faces")),lab+" explicit mesh data requires custom_mesh")
        if o["type"]!="licensed_glb":_need(not any(k in o for k in ("asset","rights")),lab+" imported model fields require licensed_glb")
        if o["type"]!="lathe":_need(not any(k in o for k in ("profile","segments","caps")),lab+" radial geometry requires a lathe")
        modifiers=o.get("modifiers",[])
        _need(isinstance(modifiers,list) and len(modifiers)<=8,lab+" invalid modifier stack")
        _need(not modifiers or o["type"] not in ("empty","licensed_glb"),lab+" modifiers require one explicit mesh")
        for mod in modifiers:
            _need(isinstance(mod,dict),lab+" invalid modifier")
            if mod.get("kind")=="bevel":
                _strict(mod,{"kind","width","segments","angle_degrees"},set(),lab+" bevel")
                _num(mod["width"],"bevel width",.000001,1000)
                _need(type(mod["segments"]) is int and 1<=mod["segments"]<=12,"Invalid bevel segments")
                _num(mod["angle_degrees"],"bevel angle",0,180)
            elif mod.get("kind")=="solidify":
                _strict(mod,{"kind","thickness","offset"},set(),lab+" solidify")
                _num(mod["thickness"],"shell thickness",.000001,1000);_num(mod["offset"],"shell offset",-1,1)
            elif mod.get("kind")=="subdivision":
                _strict(mod,{"kind","levels"},set(),lab+" subdivision")
                _need(type(mod["levels"]) is int and 0<=mod["levels"]<=4,"Invalid subdivision level")
            else:raise Invalid3DShot(lab+" unsupported modifier")
    parents={o["id"]:o.get("parent") for o in objects}
    for identity,parent in parents.items():
        seen={identity}
        while parent is not None:
            _need(isinstance(parent,str) and parent in parents and parent not in seen,"Unknown or cyclic object parent")
            seen.add(parent);parent=parents[parent]
    lights=job["lights"]
    _need(isinstance(lights,list) and lights,"Director must specify actual light rig")
    lightids=set()
    for i,l in enumerate(lights):
        lab=f"light[{i}]"
        _strict(l,{"id","type","location","rotation_degrees","energy","color"},
                {"size","size_y","shape"},lab)
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
        if "shape" in l:
            _need(l["type"]=="AREA" and l["shape"] in ("DISK","SQUARE","RECTANGLE","ELLIPSE"),lab+" light shape requires an area light")
        if "size_y" in l:
            _need(l["type"]=="AREA" and l.get("shape") in ("RECTANGLE","ELLIPSE"),lab+" second size requires a rectangular/elliptical area light")
            _num(l["size_y"],lab+".size_y",.01,10000)
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
            view_layer.cycles.use_denoising=job.get("denoise",False)
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
    if "environment_texture" in job["world"]:
        env=world.node_tree.nodes.new("ShaderNodeTexEnvironment")
        env.image=bpy.data.images.load(str((Path(verified_assets_root)/job["world"]["environment_texture"]).resolve()))
        env.texture_mapping.rotation[2]=radians(job["world"].get("environment_rotation_degrees",0))
        world.node_tree.links.new(env.outputs["Color"],bg.inputs["Color"])

    materials={}
    for raw in job["materials"]:
        m=bpy.data.materials.new(raw["id"])
        m.use_nodes=True
        principled=m.node_tree.nodes.get("Principled BSDF")
        principled.inputs["Base Color"].default_value=raw["color"]
        principled.inputs["Metallic"].default_value=raw["metallic"]
        principled.inputs["Roughness"].default_value=raw["roughness"]
        slots={"transmission":("Transmission Weight","Transmission"),"ior":("IOR",),
               "coat":("Coat Weight","Clearcoat"),"coat_roughness":("Coat Roughness","Clearcoat Roughness"),
               "sheen":("Sheen Weight","Sheen"),"emission_strength":("Emission Strength",)}
        def socket(names):
            for name in names:
                if name in principled.inputs:return principled.inputs[name]
            raise Invalid3DShot("Installed Blender lacks requested Principled input: "+str(names))
        for key,names in slots.items():
            if key in raw:socket(names).default_value=raw[key]
        if "emission_color" in raw:socket(("Emission Color","Emission")).default_value=(*raw["emission_color"],1)
        for key in _MAPS:
            if key not in raw:continue
            tex=m.node_tree.nodes.new("ShaderNodeTexImage")
            # Separate datablocks prevent a roughness map from changing the
            # color space of the same file used as a color texture.
            tex.image=bpy.data.images.load(str((Path(verified_assets_root)/raw[key]).resolve()),check_existing=False)
            tex.image.colorspace_settings.name="sRGB" if key in ("base_color_texture","emission_texture") else "Non-Color"
            target={"base_color_texture":("Base Color",),"roughness_texture":("Roughness",),
                    "metallic_texture":("Metallic",),"emission_texture":("Emission Color","Emission")}
            if key=="normal_texture":
                normal=m.node_tree.nodes.new("ShaderNodeNormalMap");normal.inputs["Strength"].default_value=raw.get("normal_strength",1)
                m.node_tree.links.new(tex.outputs["Color"],normal.inputs["Color"])
                m.node_tree.links.new(normal.outputs["Normal"],socket(("Normal",)))
            else:m.node_tree.links.new(tex.outputs["Color"],socket(target[key]))
            if key=="base_color_texture" and raw.get("texture_alpha",False):m.node_tree.links.new(tex.outputs["Alpha"],socket(("Alpha",)))
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
            for kp in fcurve.keyframe_points:kp.interpolation=data.get("interpolation","BEZIER")

    directed_objects={}
    for raw in job["objects"]:
        kind=raw["type"]
        uvs=None
        if kind=="empty":
            obj=bpy.data.objects.new(raw["id"],None);scene.collection.objects.link(obj)
        elif kind=="licensed_glb":
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
        elif kind in ("custom_mesh","lathe"):
            vertices,faces,uvs=(lathe_geometry(raw["profile"],raw["segments"],raw["caps"]) if kind=="lathe" else (raw["vertices"],raw["faces"],raw.get("uvs")))
            mesh=bpy.data.meshes.new(raw["id"]+" geometry")
            mesh.from_pydata(vertices,[],faces)
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
        if uvs is not None:
            uv_layer=obj.data.uv_layers.new(name="Director UV")
            for polygon,coordinates in zip(obj.data.polygons,uvs):
                for index,coordinate in zip(polygon.loop_indices,coordinates):uv_layer.data[index].uv=coordinate
        for spec in raw.get("modifiers",[]):
            kind_mod=spec["kind"]
            if kind_mod=="bevel":
                mod=obj.modifiers.new("Authored bevel","BEVEL");mod.width=spec["width"];mod.segments=spec["segments"];mod.limit_method="ANGLE";mod.angle_limit=radians(spec["angle_degrees"])
            elif kind_mod=="solidify":
                mod=obj.modifiers.new("Authored shell","SOLIDIFY");mod.thickness=spec["thickness"];mod.offset=spec["offset"]
            else:
                mod=obj.modifiers.new("Authored subdivision","SUBSURF");mod.levels=spec["levels"];mod.render_levels=spec["levels"]
        obj.location=raw["location"]
        obj.rotation_euler=[radians(x) for x in raw["rotation_degrees"]]
        obj.scale=raw["scale"]
        animate_transform(obj,raw)
        directed_objects[raw["id"]]=obj
        if obj.type=="MESH":
            for face in obj.data.polygons: face.use_smooth = kind not in ("plane","cube")
    for raw in job["objects"]:
        if "parent" in raw:directed_objects[raw["id"]].parent=directed_objects[raw["parent"]]

    for spec in job["lights"]:
        light_data=bpy.data.lights.new(spec["id"],spec["type"])
        light_data.energy=spec["energy"]
        light_data.color=spec["color"]
        if spec["type"]=="AREA":
            light_data.shape=spec.get("shape","DISK")
            light_data.size=spec.get("size",2.)
            if "size_y" in spec:light_data.size_y=spec["size_y"]
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
    for key in job["camera"].get("animate_lens_mm",[]):
        cam_data.lens=key["value"][0];cam_data.keyframe_insert(data_path="lens",frame=key["frame"])
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
        for key in job["camera"].get("animate_focus_distance",[]):
            cam_data.dof.focus_distance=key["value"][0];cam_data.dof.keyframe_insert(data_path="focus_distance",frame=key["frame"])
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
