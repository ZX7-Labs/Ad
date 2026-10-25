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
        "normal_strength":(0,10),"anisotropic":(0,1),
        "anisotropic_rotation":(0,1),"subsurface":(0,1),
        "subsurface_scale":(.000001,1000),"coat_ior":(1,4),
        "sheen_roughness":(0,1)}
_BOUNCES = frozenset({"max_bounces","diffuse_bounces","glossy_bounces",
                     "transmission_bounces","volume_bounces","transparent_max_bounces"})
_COLLISIONS = frozenset({"BOX","SPHERE","CAPSULE","CYLINDER","CONE","CONVEX_HULL","MESH"})
_MATERIAL_SCALARS = {"metallic":(0,1),"roughness":(.001,1),
                    **{key:value for key,value in _PBR.items() if key!="normal_strength"}}
_CLOTH_FLOATS = {"mass":(.001,100),"air_damping":(0,10),
    **{key:(0,10000) for key in ("tension_stiffness","compression_stiffness","shear_stiffness","bending_stiffness")},
    **{key:(0,50) for key in ("tension_damping","compression_damping","shear_damping","pin_stiffness")},
    "bending_damping":(0,1000)}
_CLOTH_CONTACT = {"thickness_outer":(.001,1),"thickness_inner":(.001,1),
                  "damping":(0,1),"cloth_friction":(0,80)}
_LIQUID_FIELDS = frozenset({"liquid_domain","liquid_flow","liquid_obstacle"})


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


def _validate_render_controls(settings):
    _strict(settings,set(),_BOUNCES|{"seed","adaptive_threshold","motion_blur",
            "view_transform","exposure"},"render_settings")
    for key in _BOUNCES:
        if key in settings:
            _need(type(settings[key]) is int and 0<=settings[key]<=1024,
                  key+" must be an integer between 0 and 1024")
    if "seed" in settings:
        _need(type(settings["seed"]) is int and 0<=settings["seed"]<2**31,"Invalid render seed")
    if "adaptive_threshold" in settings:
        _num(settings["adaptive_threshold"],"adaptive_threshold",0,1)
    if "motion_blur" in settings:
        spec=_strict(settings["motion_blur"],{"shutter","position"},set(),"motion_blur")
        _num(spec["shutter"],"motion blur shutter",.000001,2)
        _need(spec["position"] in ("START","CENTER","END"),"Invalid shutter position")
    if "view_transform" in settings:
        _need(settings["view_transform"] in ("AgX","Standard","Filmic","Raw"),"Unsupported view transform")
    if "exposure" in settings:_num(settings["exposure"],"exposure",-32,32)


def _validate_surface_detail(m,label):
    if "subsurface_radius" in m:_vec(m["subsurface_radius"],3,label+".subsurface_radius",0,1000)
    if "surface_noise" in m:
        n=_strict(m["surface_noise"],{"scale","detail","roughness","distortion","mapping_scale"},
                  {"bump","roughness_range","color_range"},label+".surface_noise")
        _num(n["scale"],"noise scale",.000001,1e6)
        _num(n["detail"],"noise detail",0,15)
        _num(n["roughness"],"noise roughness",0,1)
        _num(n["distortion"],"noise distortion",-1000,1000)
        _vec(n["mapping_scale"],3,"noise mapping scale",.000001,1e6)
        _need(any(k in n for k in ("bump","roughness_range","color_range")),"Noise must control an authored surface property")
        if "bump" in n:
            b=_strict(n["bump"],{"strength","distance"},set(),"surface bump")
            _num(b["strength"],"bump strength",0,1);_num(b["distance"],"bump distance",0,1000)
        if "roughness_range" in n:
            _vec(n["roughness_range"],2,"noise roughness range",.001,1)
            _need("roughness_texture" not in m,"Choose a roughness map or procedural roughness, not an ignored input")
        if "color_range" in n:
            _need(isinstance(n["color_range"],list) and len(n["color_range"])==2,"Noise color range needs two RGBA colors")
            for color in n["color_range"]:_vec(color,4,"noise color",0,1)
            _need("base_color_texture" not in m,"Choose a color map or procedural color, not an ignored input")
    if "volume" in m:
        v=_strict(m["volume"],set(),{"absorption","scatter"},label+".volume")
        _need(bool(v),"Volume needs absorption or scatter")
        for key,spec in v.items():
            _strict(spec,{"color","density"}|({"anisotropy"} if key=="scatter" else set()),set(),"volume "+key)
            _vec(spec["color"],3,"volume color",0,1);_num(spec["density"],"volume density",0,1000)
            if key=="scatter":_num(spec["anisotropy"],"volume anisotropy",-.99,.99)


def _set_interpolation(owner,kind,*,data_path=None):
    """Handle both legacy Blender actions and 4.4+ slotted actions."""
    if not owner.animation_data or not owner.animation_data.action:return
    action=owner.animation_data.action
    curves=list(action.fcurves) if hasattr(action,"fcurves") else [
        curve for layer in action.layers for strip in layer.strips
        for bag in strip.channelbags for curve in bag.fcurves]
    _need(bool(curves),"Installed Blender exposes no editable animation curves")
    for curve in curves:
        if data_path is not None and curve.data_path!=data_path:continue
        for point in curve.keyframe_points:point.interpolation=kind


def _validate_physics(job):
    bodies=[o for o in job["objects"] if "rigid_body" in o]
    simulated=[o for o in job["objects"] if "cloth" in o or "liquid_domain" in o]
    if "physics" not in job:
        _need(not bodies and not simulated,"Simulations require explicit physics world settings")
        return
    p=_strict(job["physics"],{"gravity"},{"substeps_per_frame","solver_iterations"},"physics")
    _vec(p["gravity"],3,"gravity",-10000,10000)
    if bodies:
        for key in ("substeps_per_frame","solver_iterations"):
            _need(type(p.get(key)) is int and 1<=p[key]<=1000,key+" must be 1..1000 for rigid bodies")
    else:_need(set(p)=={"gravity"},"Rigid solver settings require actual rigid bodies")
    _need(bool(bodies or simulated),"Physics world has no simulated objects")
    for o in bodies:
        _need(o["type"] not in ("empty","licensed_glb") and "parent" not in o,
              "Rigid bodies require an explicit unparented mesh")
        s=_strict(o["rigid_body"],{"type","collision_shape","mass","friction","restitution",
                  "linear_damping","angular_damping","collision_margin","kinematic"},set(),"rigid_body")
        _need(s["type"] in ("ACTIVE","PASSIVE") and s["collision_shape"] in _COLLISIONS,
              "Unsupported rigid body type/collision shape")
        _need(not (s["type"]=="ACTIVE" and s["collision_shape"]=="MESH"),
              "Active concave MESH simulation is unsupported; use a convex collider")
        _num(s["mass"],"rigid body mass",.001,1e7)
        _num(s["friction"],"rigid body friction",0,10)
        for key in ("restitution","linear_damping","angular_damping","collision_margin"):
            _num(s[key],"rigid body "+key,0,1)
        _need(type(s["kinematic"]) is bool,"kinematic must be boolean")
        _need(not o.get("animate") or s["kinematic"],"Simulated transforms cannot also be authored animation")
        _need("scale" not in o.get("animate",{}),"Animated collider scale is unsupported")


def _closed_mesh(o):
    if o["type"]=="lathe":return o["caps"]
    if o["type"]=="custom_mesh":
        edges={}
        for face in o["faces"]:
            for a,b in zip(face,face[1:]+face[:1]):
                key=tuple(sorted((a,b)));edges[key]=edges.get(key,0)+1
        return bool(edges) and all(n==2 for n in edges.values())
    return o["type"] not in ("plane","empty","licensed_glb")


def _validate_deformable_objects(job,*,require_vector_passes):
    domains=[];flows=[]
    for o in job["objects"]:
        label="object "+o["id"]
        if "shape_keys" in o:
            _need(o["type"]=="custom_mesh" and not any(k in o for k in {"cloth","rigid_body"}|_LIQUID_FIELDS),
                  "Shape keys require explicit mesh topology without a competing simulation")
            keys=o["shape_keys"];_need(isinstance(keys,list) and keys,"Shape keys missing")
            ids={"Basis"}
            for key in keys:
                _strict(key,{"id","vertices","value"},{"animate","interpolation"},"shape key")
                _need(isinstance(key["id"],str) and key["id"].strip() and key["id"] not in ids,"Duplicate or reserved shape key ID")
                ids.add(key["id"])
                _need(isinstance(key["vertices"],list) and len(key["vertices"])==len(o["vertices"]),"Shape key must preserve original vertex count and order")
                for v in key["vertices"]:_vec(v,3,"shape key vertex")
                _num(key["value"],"shape key weight",0,1)
                _need(key.get("interpolation","BEZIER") in ("LINEAR","BEZIER","CONSTANT"),"Unsupported shape interpolation")
                if "animate" in key:
                    _keyframes(key["animate"],"shape weight",job["frames"],1)
                    for p in key["animate"]:_vec(p["value"],1,"shape weight",0,1)
        if "cloth" in o:
            _need(o["type"]=="custom_mesh" and "parent" not in o and "rigid_body" not in o and not o.get("animate")
                  and not any(k in o for k in _LIQUID_FIELDS|{"cloth_collision"}),
                  "Cloth requires an unparented explicit mesh without competing transforms or simulation")
            c=_strict(o["cloth"],set(_CLOTH_FLOATS)|{"quality","pins","collisions","collision_distance","collision_quality","self_collision","self_distance","self_friction"},set(),"cloth")
            for key,(lo,hi) in _CLOTH_FLOATS.items():_num(c[key],"cloth "+key,lo,hi)
            for key in ("quality","collision_quality"):
                _need(type(c[key]) is int and 1<=c[key]<=80,"Invalid cloth solver quality")
            for key in ("collisions","self_collision"):_need(type(c[key]) is bool,"Cloth collision flags must be boolean")
            _num(c["collision_distance"],"cloth collision distance",.001,1)
            _num(c["self_distance"],"cloth self distance",.001,.1);_num(c["self_friction"],"cloth self friction",0,80)
            _need(isinstance(c["pins"],list),"Cloth pins must be explicit")
            pins=set()
            for pin in c["pins"]:
                _strict(pin,{"vertex","weight"},set(),"cloth pin")
                _need(type(pin["vertex"]) is int and 0<=pin["vertex"]<len(o["vertices"]) and pin["vertex"] not in pins,"Invalid or duplicate cloth pin")
                pins.add(pin["vertex"]);_num(pin["weight"],"pin weight",0,1)
        if "cloth_collision" in o:
            _need(o["type"] not in ("empty","licensed_glb") and "cloth" not in o and not any(k in o for k in _LIQUID_FIELDS),"Cloth collider needs explicit mesh geometry")
            c=_strict(o["cloth_collision"],set(_CLOTH_CONTACT),set(),"cloth_collision")
            for key,(lo,hi) in _CLOTH_CONTACT.items():_num(c[key],"cloth collider "+key,lo,hi)
        roles=set(o)&_LIQUID_FIELDS
        _need(len(roles)<=1,"Each object can have only one liquid role")
        if roles:
            _need(o["type"] not in ("empty","licensed_glb") and "parent" not in o and
                  not any(k in o for k in ("cloth","rigid_body","shape_keys","cloth_collision")),"Liquid role needs an explicit unparented mesh without competing simulation")
            _need("scale" not in o.get("animate",{}),"Animated fluid scale is unsupported")
        if "liquid_domain" in o:
            domains.append(o)
            _need(o["type"]=="cube" and not o.get("animate") and not o.get("modifiers"),"Liquid domain must be an unmodified static box")
            d=_strict(o["liquid_domain"],{"resolution","mesh_scale","particle_radius","time_scale","flip_ratio","viscosity"},set(),"liquid domain")
            _need(type(d["resolution"]) is int and 6<=d["resolution"]<=512,"Liquid grid resolution must be 6..512")
            _need(type(d["mesh_scale"]) is int and 1<=d["mesh_scale"]<=4,"Liquid mesh scale must be 1..4")
            _num(d["particle_radius"],"liquid particle radius",.01,10)
            _num(d["time_scale"],"liquid time scale",.0001,10);_num(d["flip_ratio"],"FLIP ratio",0,1)
            _num(d["viscosity"],"liquid viscosity",0,10)
        if "liquid_flow" in o:
            flows.append(o);f=_strict(o["liquid_flow"],{"behavior","surface_distance","velocity"},set(),"liquid flow")
            _need(f["behavior"] in ("GEOMETRY","INFLOW","OUTFLOW"),"Unknown liquid flow behavior")
            _need(_closed_mesh(o),"Liquid flow source must be a closed mesh")
            _num(f["surface_distance"],"liquid surface distance",0,10);_vec(f["velocity"],3,"liquid velocity",-1000,1000)
            _need(f["behavior"]!="GEOMETRY" or not o.get("animate"),"Initial geometry emits once; moving liquid sources require INFLOW")
            _need(f["behavior"]!="OUTFLOW" or f["velocity"]==[0,0,0],"Outflow removes liquid rather than injecting velocity")
        if "liquid_obstacle" in o:
            f=_strict(o["liquid_obstacle"],{"surface_distance","planar"},set(),"liquid obstacle")
            _num(f["surface_distance"],"liquid obstacle distance",0,10)
            _need(type(f["planar"]) is bool and (f["planar"] or _closed_mesh(o)),"Choose a planar obstacle or closed collision mesh")
    if domains or flows or any("liquid_obstacle" in o for o in job["objects"]):
        _need(len(domains)==1 and any(f["liquid_flow"]["behavior"]!="OUTFLOW" for f in flows),"One liquid domain and an actual liquid source are required per shot")
        _need(not require_vector_passes,"Variable-topology liquid requires velocity-aware EXR passes; this adapter does not supply them")
        _need("motion_blur" not in job.get("render_settings",{}),"Variable-topology liquid shutter blur requires an unsupported velocity-aware render")
    _need(not any("cloth_collision" in o for o in job["objects"]) or any("cloth" in o for o in job["objects"]),
          "Cloth collision controls require an actual cloth simulation")


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


def validate_blender_shot(job, *, verified_assets_root=None, require_vector_passes=False):
    """Validate all paths, geometry and animation before Blender gets commands."""
    _strict(job,{"shot_id","width","height","fps","frames","camera","world",
                 "materials","objects","lights"}, {"samples","denoise","render_settings","physics"}, "3D film shot")
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
    if "render_settings" in job:_validate_render_controls(job["render_settings"])
    _need(not (require_vector_passes and "motion_blur" in job.get("render_settings",{})),
          "Vector-pass EXR requires an unblurred render; Blender suppresses vectors with physical motion blur")
    _strict(job["world"],{"color","strength"},{"environment_texture","environment_rotation_degrees"},"world")
    _vec(job["world"]["color"],3,"world.color",0,1)
    _num(job["world"]["strength"],"world.strength",0,100)
    if "environment_texture" in job["world"]:
        _asset(job["world"]["environment_texture"],verified_assets_root,"world.environment_texture",{".png",".jpg",".jpeg"})
    if "environment_rotation_degrees" in job["world"]:
        _need("environment_texture" in job["world"],"Environment rotation requires a texture")
        _num(job["world"]["environment_rotation_degrees"],"environment rotation",-36000,36000)
    cam=_strict(job["camera"],{"location","target","lens_mm"},
                {"animate_location","animate_target","depth_of_field","animate_lens_mm","animate_focus_distance","interpolation","sensor_width_mm","shift_x","shift_y"}, "camera")
    _vec(cam["location"],3,"camera.location")
    _vec(cam["target"],3,"camera.target")
    _need(cam["location"]!=cam["target"],"Camera cannot look at its own origin")
    _num(cam["lens_mm"],"camera.lens_mm",1,300)
    if "animate_location" in cam:
        _keyframes(cam["animate_location"],"camera.animate_location",frames,3)
    if "animate_target" in cam:
        _keyframes(cam["animate_target"],"camera.animate_target",frames,3)
    if "depth_of_field" in cam:
        _strict(cam["depth_of_field"],{"focus_distance","fstop"},{"focus_object","aperture_blades","aperture_ratio","aperture_rotation_degrees"},"depth_of_field")
        _num(cam["depth_of_field"]["focus_distance"],"focus_distance",.001,10000)
        _num(cam["depth_of_field"]["fstop"],"fstop",.1,100)
        dof=cam["depth_of_field"]
        if "aperture_blades" in dof:_need(type(dof["aperture_blades"]) is int and (dof["aperture_blades"]==0 or 3<=dof["aperture_blades"]<=16),"Invalid aperture blade count")
        if "aperture_ratio" in dof:_num(dof["aperture_ratio"],"aperture_ratio",.01,100)
        if "aperture_rotation_degrees" in dof:_num(dof["aperture_rotation_degrees"],"aperture_rotation_degrees",-36000,36000)
        _need(not ("focus_object" in dof and "animate_focus_distance" in cam),"Object focus and distance animation cannot compete")
    _need(cam.get("interpolation","BEZIER") in ("LINEAR","BEZIER","CONSTANT"),"Invalid camera interpolation")
    for key,low,high in (("sensor_width_mm",1,1000),("shift_x",-10,10),("shift_y",-10,10)):
        if key in cam:_num(cam[key],key,low,high)
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
        _strict(m,{"id","color","metallic","roughness"},set(_PBR)|_MAPS|{"emission_color","texture_alpha","subsurface_radius","surface_noise","volume","animate","interpolation"},lab)
        _need(isinstance(m["id"],str) and m["id"].strip() and m["id"] not in matids,
              lab+" material ID duplicated/missing")
        matids.add(m["id"])
        _vec(m["color"],4,lab+".color",0,1)
        _num(m["metallic"],lab+".metallic",0,1)
        _num(m["roughness"],lab+".roughness",.001,1)
        for key,(low,high) in _PBR.items():
            if key in m:_num(m[key],lab+"."+key,low,high)
        _validate_surface_detail(m,lab)
        _need(m.get("interpolation","BEZIER") in ("LINEAR","BEZIER","CONSTANT"),"Invalid material interpolation")
        animation=m.get("animate",{})
        _need(isinstance(animation,dict) and set(animation).issubset(set(_MATERIAL_SCALARS)|{"color","emission_color"}),"Unsupported material animation")
        for key,curve in animation.items():
            dims=4 if key=="color" else 3 if key=="emission_color" else 1
            _keyframes(curve,lab+".animate."+key,frames,dims)
            for point in curve:
                low,high=_MATERIAL_SCALARS.get(key,(0,1))
                _vec(point["value"],dims,"material animated value",low,high)
            if key in ("color","roughness"):
                _need(("base_color_texture" if key=="color" else "roughness_texture") not in m and
                    ("color_range" if key=="color" else "roughness_range") not in m.get("surface_noise",{}),
                    "Animated material input cannot be overridden by a texture")
            if key=="emission_color":_need("emission_texture" not in m,"Animated emission cannot be overridden by a texture")
            if key=="metallic":_need("metallic_texture" not in m,"Animated metal cannot be overridden by a texture")
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
                {"animate","vertices","faces","asset","rights","uvs","profile","segments","caps","modifiers","parent","interpolation","rigid_body","cloth","cloth_collision","shape_keys"}|_LIQUID_FIELDS,lab)
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
    if "focus_object" in cam.get("depth_of_field",{}):
        focus=cam["depth_of_field"]["focus_object"]
        _need(isinstance(focus,str) and focus in parents,"Unknown camera focus object")
    _validate_deformable_objects(job,require_vector_passes=require_vector_passes)
    _validate_physics(job)
    lights=job["lights"]
    _need(isinstance(lights,list) and lights,"Director must specify actual light rig")
    lightids=set()
    for i,l in enumerate(lights):
        lab=f"light[{i}]"
        _strict(l,{"id","type","location","rotation_degrees","energy","color"},
                {"size","size_y","shape","animate","animate_energy","animate_color","interpolation"},lab)
        _need(isinstance(l["id"],str) and l["id"] and l["id"] not in lightids,
              lab+" duplicate light")
        lightids.add(l["id"])
        _need(l["type"] in LIGHTS,lab+" unsupported light")
        _vec(l["location"],3,lab+".location")
        _vec(l["rotation_degrees"],3,lab+".rotation")
        _num(l["energy"],lab+".energy",0,10000000)
        _vec(l["color"],3,lab+".color",0,1)
        animation=l.get("animate",{})
        _need(isinstance(animation,dict) and set(animation).issubset({"location","rotation_degrees"}),"Unsupported light transform animation")
        for key,curve in animation.items():_keyframes(curve,lab+".animate."+key,frames,3)
        _need(l.get("interpolation","BEZIER") in ("LINEAR","BEZIER","CONSTANT"),"Invalid light interpolation")
        for key,dims,high in (("animate_energy",1,1e7),("animate_color",3,1)):
            if key in l:
                _keyframes(l[key],lab+"."+key,frames,dims)
                for point in l[key]:_vec(point["value"],dims,lab+"."+key,0,high)
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
    validate_blender_shot(job,verified_assets_root=verified_assets_root,require_vector_passes=original_exr_passes)
    # Validate the ACTUAL full authored scene before building any subset.
    # This changes execution granularity, never the artist's animation clock.
    if frame_start is not None or frame_end is not None:
        if (type(frame_start) is not int or type(frame_end) is not int or
                not 1 <= frame_start <= frame_end <= job["frames"]):
            raise Invalid3DShot("Render range must be an ordered inclusive subset of original shot")
    import bpy
    from math import radians
    from mathutils import Vector

    # The inspected distro Blender 4.0 liquid bake aborts inside Mantaflow's
    # embedded Python initialization. Refuse it before entering native bake;
    # cloth/morph/rigid CGI keep their independently tested 4.0 path.
    if any("liquid_domain" in raw for raw in job["objects"]):
        _need(bpy.app.version>=(4,5,0),"Native liquid baking requires Blender 4.5 or newer; this older runtime is unsupported")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene
    scene.render.engine="CYCLES"
    scene.cycles.device="CPU"
    scene.cycles.samples=job.get("samples",8)
    if hasattr(scene.cycles,"use_denoising"):scene.cycles.use_denoising=job.get("denoise",False)
    settings=job.get("render_settings",{})
    for key in _BOUNCES|{"seed"}:
        if key in settings:setattr(scene.cycles,key,settings[key])
    if "adaptive_threshold" in settings:
        scene.cycles.use_adaptive_sampling=True
        scene.cycles.adaptive_threshold=settings["adaptive_threshold"]
    if "motion_blur" in settings:
        scene.render.use_motion_blur=True
        scene.render.motion_blur_shutter=settings["motion_blur"]["shutter"]
        scene.cycles.motion_blur_position=settings["motion_blur"]["position"]
    if "view_transform" in settings:
        try:scene.view_settings.view_transform=settings["view_transform"]
        except TypeError as exc:raise Invalid3DShot("Requested view transform unavailable in installed Blender") from exc
    if "exposure" in settings:scene.view_settings.exposure=settings["exposure"]
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
    if "physics" in job:scene.gravity=job["physics"]["gravity"]
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
        slots={"color":("Base Color",),"metallic":("Metallic",),"roughness":("Roughness",),
               "emission_color":("Emission Color","Emission"),
               "transmission":("Transmission Weight","Transmission"),"ior":("IOR",),
               "coat":("Coat Weight","Clearcoat"),"coat_roughness":("Coat Roughness","Clearcoat Roughness"),
               "sheen":("Sheen Weight","Sheen"),"emission_strength":("Emission Strength",),
               "anisotropic":("Anisotropic IOR Level","Anisotropic"),
               "anisotropic_rotation":("Anisotropic Rotation",),
               "subsurface":("Subsurface Weight","Subsurface"),
               "subsurface_scale":("Subsurface Scale",),"coat_ior":("Coat IOR",),
               "sheen_roughness":("Sheen Roughness",)}
        def socket(names):
            for name in names:
                if name in principled.inputs:return principled.inputs[name]
            raise Invalid3DShot("Installed Blender lacks requested Principled input: "+str(names))
        for key,names in slots.items():
            if key in raw and key not in ("color","emission_color"):socket(names).default_value=raw[key]
        if "subsurface_radius" in raw:socket(("Subsurface Radius",)).default_value=raw["subsurface_radius"]
        if "emission_color" in raw:socket(("Emission Color","Emission")).default_value=(*raw["emission_color"],1)
        for key,curve in raw.get("animate",{}).items():
            target_input=socket(slots[key])
            for point in curve:
                value=point["value"]
                target_input.default_value=(*value,1) if key=="emission_color" else value if key=="color" else value[0]
                target_input.keyframe_insert(data_path="default_value",frame=point["frame"])
        _set_interpolation(m.node_tree,raw.get("interpolation","BEZIER"))
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
        if "surface_noise" in raw:
            spec=raw["surface_noise"];nodes=m.node_tree.nodes;links=m.node_tree.links
            coords=nodes.new("ShaderNodeTexCoord");mapping=nodes.new("ShaderNodeMapping")
            mapping.inputs["Scale"].default_value=spec["mapping_scale"]
            links.new(coords.outputs["Object"],mapping.inputs["Vector"])
            noise=nodes.new("ShaderNodeTexNoise")
            for field in ("scale","detail","roughness","distortion"):
                noise.inputs[field.title()].default_value=spec[field]
            links.new(mapping.outputs["Vector"],noise.inputs["Vector"])
            if "roughness_range" in spec:
                remap=nodes.new("ShaderNodeMapRange");remap.inputs["To Min"].default_value=spec["roughness_range"][0];remap.inputs["To Max"].default_value=spec["roughness_range"][1]
                links.new(noise.outputs["Fac"],remap.inputs["Value"]);links.new(remap.outputs["Result"],socket(("Roughness",)))
            if "color_range" in spec:
                ramp=nodes.new("ShaderNodeValToRGB")
                for element,color in zip(ramp.color_ramp.elements,spec["color_range"]):element.color=color
                links.new(noise.outputs["Fac"],ramp.inputs["Fac"]);links.new(ramp.outputs["Color"],socket(("Base Color",)))
            if "bump" in spec:
                bump=nodes.new("ShaderNodeBump")
                for key in ("strength","distance"):bump.inputs[key.title()].default_value=spec["bump"][key]
                links.new(noise.outputs["Fac"],bump.inputs["Height"])
                # Layer the procedural microdetail over any attested normal map.
                normal_input=socket(("Normal",))
                if normal_input.is_linked:links.new(normal_input.links[0].from_socket,bump.inputs["Normal"])
                links.new(bump.outputs["Normal"],normal_input)
        if "volume" in raw:
            shaders=[]
            for kind,spec in raw["volume"].items():
                node=m.node_tree.nodes.new("ShaderNodeVolumeAbsorption" if kind=="absorption" else "ShaderNodeVolumeScatter")
                node.inputs["Color"].default_value=(*spec["color"],1);node.inputs["Density"].default_value=spec["density"]
                if kind=="scatter":node.inputs["Anisotropy"].default_value=spec["anisotropy"]
                shaders.append(node.outputs["Volume"])
            if len(shaders)==2:
                mix=m.node_tree.nodes.new("ShaderNodeAddShader")
                for index,shader in enumerate(shaders):m.node_tree.links.new(shader,mix.inputs[index])
                volume=mix.outputs[0]
            else:volume=shaders[0]
            output=next(n for n in m.node_tree.nodes if n.type=="OUTPUT_MATERIAL")
            m.node_tree.links.new(volume,output.inputs["Volume"])
        materials[raw["id"]]=m

    def animate_transform(obj, data):
        for name, tracks in data.get("animate",{}).items():
            attr="rotation_euler" if name=="rotation_degrees" else name
            for p in tracks:
                v=p["value"]
                setattr(obj,attr,tuple(radians(x) for x in v) if name=="rotation_degrees" else v)
                obj.keyframe_insert(data_path=attr,frame=p["frame"])
        _set_interpolation(obj,data.get("interpolation","BEZIER"))

    def add_modifiers(obj,specs):
        for spec in specs:
            kind_mod=spec["kind"]
            if kind_mod=="bevel":
                mod=obj.modifiers.new("Authored bevel","BEVEL");mod.width=spec["width"];mod.segments=spec["segments"];mod.limit_method="ANGLE";mod.angle_limit=radians(spec["angle_degrees"])
            elif kind_mod=="solidify":
                mod=obj.modifiers.new("Authored shell","SOLIDIFY");mod.thickness=spec["thickness"];mod.offset=spec["offset"]
            else:
                mod=obj.modifiers.new("Authored subdivision","SUBSURF");mod.levels=spec["levels"];mod.render_levels=spec["levels"]

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
        if "shape_keys" in raw:
            obj.shape_key_add(name="Basis")
            for key in raw["shape_keys"]:
                block=obj.shape_key_add(name=key["id"])
                for vertex,position in zip(block.data,key["vertices"]):vertex.co=position
                block.value=key["value"]
                for point in key.get("animate",[]):
                    block.value=point["value"][0];block.keyframe_insert(data_path="value",frame=point["frame"])
                _set_interpolation(obj.data.shape_keys,key.get("interpolation","BEZIER"),data_path=block.path_from_id("value"))
        # Cloth solves the original control mesh; finishing modifiers are
        # attached after baking, so solver topology cannot silently change.
        if "cloth" not in raw:add_modifiers(obj,raw.get("modifiers",[]))
        obj.location=raw["location"]
        obj.rotation_euler=[radians(x) for x in raw["rotation_degrees"]]
        obj.scale=raw["scale"]
        animate_transform(obj,raw)
        directed_objects[raw["id"]]=obj
        if obj.type=="MESH":
            for face in obj.data.polygons: face.use_smooth = kind not in ("plane","cube")
    for raw in job["objects"]:
        if "parent" in raw:directed_objects[raw["id"]].parent=directed_objects[raw["parent"]]

    physics_report=None
    if any("rigid_body" in raw for raw in job["objects"]):
        # Evaluate the REAL Bullet world on the original shot clock, then bake
        # dynamic poses. A resumed frame subset sees the same history and
        # subframe motion blur can interpolate the resulting native poses.
        scene.frame_set(1)
        dynamic=[]
        for raw in job["objects"]:
            if "rigid_body" not in raw:continue
            obj=directed_objects[raw["id"]];spec=raw["rigid_body"]
            bpy.ops.object.select_all(action="DESELECT");obj.select_set(True);bpy.context.view_layer.objects.active=obj
            bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
            bpy.ops.rigidbody.object_add()
            for key,value in spec.items():setattr(obj.rigid_body,key,value)
            obj.rigid_body.use_margin=True
            if spec["type"]=="ACTIVE" and not spec["kinematic"]:dynamic.append(obj)
        scene.gravity=job["physics"]["gravity"]
        world_physics=scene.rigidbody_world
        world_physics.substeps_per_frame=job["physics"]["substeps_per_frame"]
        world_physics.solver_iterations=job["physics"]["solver_iterations"]
        world_physics.point_cache.frame_start=1;world_physics.point_cache.frame_end=job["frames"]
        scene.frame_start=1;scene.frame_end=job["frames"]
        poses={obj.name:[] for obj in dynamic}
        for frame in range(1,job["frames"]+1):
            scene.frame_set(frame);depsgraph=bpy.context.evaluated_depsgraph_get()
            for obj in dynamic:poses[obj.name].append(obj.evaluated_get(depsgraph).matrix_world.copy())
        world_physics.enabled=False
        for obj in dynamic:
            bpy.ops.object.select_all(action="DESELECT");obj.select_set(True);bpy.context.view_layer.objects.active=obj
            bpy.ops.rigidbody.object_remove();obj.rotation_mode="QUATERNION"
            for frame,matrix in enumerate(poses[obj.name],1):
                obj.location=matrix.to_translation();obj.rotation_quaternion=matrix.to_quaternion()
                obj.keyframe_insert(data_path="location",frame=frame);obj.keyframe_insert(data_path="rotation_quaternion",frame=frame)
            _set_interpolation(obj,"LINEAR")
        selected=sorted({1,max(1,job["frames"]//2),job["frames"]})
        physics_report={"solver":"Blender Bullet rigid body; integer-frame pose bake",
            "original_clock_frames":job["frames"],"dynamic_objects":len(dynamic),
            "positions":{name:[{"frame":f,"location":list(values[f-1].to_translation())} for f in selected] for name,values in poses.items()}}
        scene.frame_start=1 if frame_start is None else frame_start
        scene.frame_end=job["frames"] if frame_end is None else frame_end

    def mesh_observation(obj,mesh,frame):
        import hashlib,struct
        coords=[tuple(v.co) for v in mesh.vertices]
        _need(all(math.isfinite(x) for v in coords for x in v),"Native simulation produced non-finite geometry")
        world_coords=[obj.matrix_world@v.co for v in mesh.vertices]
        return {"frame":frame,"vertices":len(coords),"polygons":len(mesh.polygons),
            "geometry_sha256":hashlib.sha256(b"".join(struct.pack("<fff",*v) for v in coords)).hexdigest(),
            "bounds_min":[min((v[i] for v in world_coords),default=0) for i in range(3)],
            "bounds_max":[max((v[i] for v in world_coords),default=0) for i in range(3)]}

    cloth_specs=[raw for raw in job["objects"] if "cloth" in raw]
    cloth_report=None
    if cloth_specs:
        scene.frame_set(1);cloth_modifiers={}
        for raw in job["objects"]:
            if "cloth_collision" not in raw:continue
            obj=directed_objects[raw["id"]];obj.modifiers.new("Authored cloth contact","COLLISION")
            for key,value in raw["cloth_collision"].items():setattr(obj.collision,key,value)
        for raw in cloth_specs:
            obj=directed_objects[raw["id"]];spec=raw["cloth"]
            bpy.ops.object.select_all(action="DESELECT");obj.select_set(True);bpy.context.view_layer.objects.active=obj
            bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
            mod=obj.modifiers.new("Authored native cloth","CLOTH");cloth_modifiers[raw["id"]]=mod
            for key in set(_CLOTH_FLOATS)|{"quality"}:setattr(mod.settings,key,spec[key])
            pins=obj.vertex_groups.new(name="ZX7 authored cloth pins")
            for pin in spec["pins"]:pins.add([pin["vertex"]],pin["weight"],"REPLACE")
            mod.settings.vertex_group_mass=pins.name
            cs=mod.collision_settings;cs.use_collision=spec["collisions"];cs.use_self_collision=spec["self_collision"]
            for source,target in (("collision_distance","distance_min"),("collision_quality","collision_quality"),("self_distance","self_distance_min"),("self_friction","self_friction")):
                setattr(cs,target,spec[source])
            mod.point_cache.frame_start=1;mod.point_cache.frame_end=job["frames"]
        snapshots={raw["id"]:[] for raw in cloth_specs};observations={raw["id"]:[] for raw in cloth_specs}
        scene.frame_start=1;scene.frame_end=job["frames"]
        for frame in range(1,job["frames"]+1):
            scene.frame_set(frame);depsgraph=bpy.context.evaluated_depsgraph_get()
            for raw in cloth_specs:
                identity=raw["id"];obj=directed_objects[identity];evaluated=obj.evaluated_get(depsgraph);mesh=evaluated.to_mesh()
                try:
                    _need(len(mesh.vertices)==len(obj.data.vertices),"Cloth control topology changed during simulation")
                    row=mesh_observation(obj,mesh,frame)
                    row["pins"]=[{"vertex":pin["vertex"],"position":list(obj.matrix_world@mesh.vertices[pin["vertex"]].co)} for pin in raw["cloth"]["pins"]]
                    observations[identity].append(row)
                    snapshots[identity].append([tuple(v.co) for v in mesh.vertices])
                finally:evaluated.to_mesh_clear()
        for raw in cloth_specs:
            identity=raw["id"];obj=directed_objects[identity];obj.modifiers.remove(cloth_modifiers[identity])
            poses=snapshots[identity]
            for vertex,position in zip(obj.data.vertices,poses[0]):vertex.co=position
            obj.data.update();obj.shape_key_add(name="Basis")
            for frame,positions in enumerate(poses[1:],2):
                block=obj.shape_key_add(name=f"ZX7 baked cloth {frame}")
                for vertex,position in zip(block.data,positions):vertex.co=position
                for at,value in ((frame-1,0.),(frame,1.),(frame+1,0.)):
                    if at<=job["frames"]:block.value=value;block.keyframe_insert(data_path="value",frame=at)
            _set_interpolation(obj.data.shape_keys,"LINEAR")
            add_modifiers(obj,raw.get("modifiers",[]))
        cloth_report={"solver":"Blender native cloth; original-clock vertex pose bake",
            "original_clock_frames":job["frames"],"meshes":observations,
            "maximum_vertex_displacement":{identity:max(math.dist(a,b) for a,b in zip(poses[0],poses[-1])) for identity,poses in snapshots.items()}}
        scene.frame_start=1 if frame_start is None else frame_start;scene.frame_end=job["frames"] if frame_end is None else frame_end

    liquid_report=None
    domain_spec=next((raw for raw in job["objects"] if "liquid_domain" in raw),None)
    if domain_spec is not None:
        scene.frame_set(1);domain=directed_objects[domain_spec["id"]]
        for raw in job["objects"]:
            if not any(k in raw for k in _LIQUID_FIELDS):continue
            obj=directed_objects[raw["id"]]
            bpy.ops.object.select_all(action="DESELECT");obj.select_set(True);bpy.context.view_layer.objects.active=obj
            bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
            mod=obj.modifiers.new("Authored native liquid","FLUID")
            if "liquid_domain" in raw:
                mod.fluid_type="DOMAIN";bpy.context.view_layer.update();ds=mod.domain_settings;spec=raw["liquid_domain"]
                ds.domain_type="LIQUID";ds.resolution_max=spec["resolution"];ds.use_mesh=True;ds.mesh_scale=spec["mesh_scale"]
                ds.mesh_particle_radius=spec["particle_radius"];ds.time_scale=spec["time_scale"];ds.flip_ratio=spec["flip_ratio"]
                ds.use_viscosity=spec["viscosity"]>0;ds.viscosity_value=spec["viscosity"]
                cache=Path(out)/"native-liquid-cache";cache.mkdir(parents=True,exist_ok=False)
                ds.cache_type="ALL";ds.cache_directory=str(cache.resolve());ds.cache_frame_start=1;ds.cache_frame_end=job["frames"]
            elif "liquid_flow" in raw:
                mod.fluid_type="FLOW";bpy.context.view_layer.update();flow=mod.flow_settings;spec=raw["liquid_flow"]
                flow.flow_type="LIQUID";flow.flow_behavior=spec["behavior"];flow.surface_distance=spec["surface_distance"]
                flow.use_initial_velocity=True;flow.velocity_coord=spec["velocity"]
            else:
                mod.fluid_type="EFFECTOR";bpy.context.view_layer.update();effector=mod.effector_settings;spec=raw["liquid_obstacle"]
                effector.effector_type="COLLISION";effector.surface_distance=spec["surface_distance"];effector.use_plane_init=spec["planar"]
        scene.frame_start=1;scene.frame_end=job["frames"];scene.frame_set(1)
        bpy.ops.object.select_all(action="DESELECT");domain.select_set(True);bpy.context.view_layer.objects.active=domain
        done=bpy.ops.fluid.bake_all()
        _need("FINISHED" in done and ds.has_cache_baked_data and ds.has_cache_baked_mesh,"Native liquid cache did not actually bake")
        cache_meshes=list((cache/"mesh").glob("*.bobj.gz"))
        _need(len(cache_meshes)==job["frames"],"Native liquid mesh cache lost original frames")
        observations=[]
        for frame in range(1,job["frames"]+1):
            scene.frame_set(frame);evaluated=domain.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
            try:observations.append(mesh_observation(domain,mesh,frame))
            finally:evaluated.to_mesh_clear()
        _need(any(row["polygons"]>0 for row in observations),"Liquid simulation produced no real surface")
        for raw in job["objects"]:
            if "liquid_flow" in raw:directed_objects[raw["id"]].hide_render=True
        liquid_report={"solver":"Blender Mantaflow native liquid mesh","original_clock_frames":job["frames"],
            "cache_mesh_frames":len(cache_meshes),"resolution":ds.resolution_max,"viscosity":ds.viscosity_value,
            "meshes":observations}
        scene.frame_start=1 if frame_start is None else frame_start;scene.frame_end=job["frames"] if frame_end is None else frame_end

    morph_report={}
    for raw in job["objects"]:
        if "shape_keys" not in raw:continue
        rows=[];obj=directed_objects[raw["id"]]
        for frame in sorted({1,max(1,job["frames"]//2),job["frames"]}):
            scene.frame_set(frame);evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
            try:rows.append(mesh_observation(obj,mesh,frame))
            finally:evaluated.to_mesh_clear()
        morph_report[raw["id"]]=rows

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
        animate_transform(light_obj,spec)
        for field,prop in (("animate_energy","energy"),("animate_color","color")):
            for point in spec.get(field,[]):
                setattr(light_data,prop,point["value"][0] if prop=="energy" else point["value"])
                light_data.keyframe_insert(data_path=prop,frame=point["frame"])
        _set_interpolation(light_data,spec.get("interpolation","BEZIER"))

    cam_data=bpy.data.cameras.new("ZX7 camera")
    cam=bpy.data.objects.new("ZX7 directed camera",cam_data)
    scene.collection.objects.link(cam)
    scene.camera=cam
    cam.location=job["camera"]["location"]
    cam_data.lens=job["camera"]["lens_mm"]
    for source,target_attr in (("sensor_width_mm","sensor_width"),("shift_x","shift_x"),("shift_y","shift_y")):
        if source in job["camera"]:setattr(cam_data,target_attr,job["camera"][source])
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
        if "focus_object" in spec:cam_data.dof.focus_object=directed_objects[spec["focus_object"]]
        for source,target_attr in (("aperture_blades","aperture_blades"),("aperture_ratio","aperture_ratio"),("aperture_rotation_degrees","aperture_rotation")):
            if source in spec:setattr(cam_data.dof,target_attr,radians(spec[source]) if source.endswith("degrees") else spec[source])
        for key in job["camera"].get("animate_focus_distance",[]):
            cam_data.dof.focus_distance=key["value"][0];cam_data.dof.keyframe_insert(data_path="focus_distance",frame=key["frame"])
    for owner in (cam,target,cam_data):_set_interpolation(owner,job["camera"].get("interpolation","BEZIER"))
    out=Path(out)
    out.mkdir(parents=True,exist_ok=True)
    scene.render.filepath=str(out/"frame_")
    scene.frame_set(scene.frame_start)
    bpy.ops.render.render(animation=True)
    report={"blender_version":bpy.app.version_string,"cycles_device":scene.cycles.device,
            "samples":scene.cycles.samples,"denoise_requested":job.get("denoise",False),
            "motion_blur_enabled":scene.render.use_motion_blur,
            "shutter_frames":scene.render.motion_blur_shutter,
            "view_transform":scene.view_settings.view_transform,
            "display_exposure":scene.view_settings.exposure,
            "camera":{"lens_mm":cam_data.lens,"sensor_width_mm":cam_data.sensor_width,
                "shift_x":cam_data.shift_x,"shift_y":cam_data.shift_y,"dof_enabled":cam_data.dof.use_dof,
                "focus_object":cam_data.dof.focus_object.name if cam_data.dof.focus_object else None,
                "aperture_blades":cam_data.dof.aperture_blades,"aperture_ratio":cam_data.dof.aperture_ratio},
            "animated_materials":[m["id"] for m in job["materials"] if m.get("animate")],
            "animated_lights":[l["id"] for l in job["lights"] if any(l.get(k) for k in ("animate","animate_energy","animate_color"))],
            "rendered_range":[scene.frame_start,scene.frame_end],
            "bounces":{key:getattr(scene.cycles,key) for key in sorted(_BOUNCES)},
            "procedural_materials":[m["id"] for m in job["materials"] if "surface_noise" in m],
            "volume_materials":[m["id"] for m in job["materials"] if "volume" in m],
            "physics":physics_report,"cloth":cloth_report,"liquid":liquid_report,"shape_keys":morph_report}
    (out/"render-report.json").write_text(json.dumps(report,indent=2)+"\n")
    return {"shot_id":job["shot_id"],"frames":job["frames"],"fps":job["fps"],"native_controls":report,
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
