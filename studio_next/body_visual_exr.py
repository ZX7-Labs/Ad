"""Lossless scene-linear floating RGBA input/output for the native visual graph."""
from __future__ import annotations
import numpy as np

_PRIMARIES=(.64,.33,.30,.60,.15,.06,.3127,.3290)


def _library():
    try:import OpenEXR
    except ImportError as exc:raise RuntimeError("Float EXR graph I/O requires the installed OpenEXR 3.3+ native module") from exc
    return OpenEXR


def read_float_rgba(path,*,budget,alpha_mode,channels=None):
    OpenEXR=_library()
    if alpha_mode not in ("straight","associated"):raise ValueError("EXR alpha association must be explicitly authored")
    names=channels or dict(zip("rgba","RGBA"))
    if set(names)!=set("rgba") or any(not isinstance(v,str) or not v for v in names.values()):
        raise ValueError("EXR needs explicit RGBA channel names")
    with OpenEXR.File(str(path),header_only=True,separate_channels=True) as header_file:
        if len(header_file.parts)!=1:raise ValueError("Select one EXR part before native graph input")
        header=header_file.header()
        if header.get("type") not in (OpenEXR.scanlineimage,OpenEXR.tiledimage):
            raise ValueError("Deep EXR requires an explicit deep-compositing decoder")
        lower,upper=header["dataWindow"]
        width,height=int(upper[0])-int(lower[0])+1,int(upper[1])-int(lower[1])+1
        if min(width,height)<1 or width*height>budget.max_pixels:
            raise ValueError("EXR data window exceeds host pixel budget")
        count=len(header.get("channels",[]))
        if width*height*4*(count+16)>budget.max_live_bytes:
            raise ValueError("EXR channel decode exceeds host memory budget")
        if "chromaticities" in header and not np.allclose(np.asarray(header["chromaticities"]).reshape(-1),_PRIMARIES,rtol=0,atol=1e-5):
            raise ValueError("EXR primaries require an explicit linear-sRGB conversion")
        if header.get("zx7_alpha_mode",alpha_mode)!=alpha_mode:
            raise ValueError("EXR alpha declaration conflicts with file metadata")
        if header.get("zx7_working_space","linear_srgb")!="linear_srgb":
            raise ValueError("EXR working space conflicts with declared linear-sRGB")
    with OpenEXR.File(str(path),separate_channels=True) as image:
        found=image.channels()
        if any(name not in found for name in names.values()):raise ValueError("Selected EXR channel is absent")
        planes=[found[names[c]].pixels for c in "rgba"]
        if any(p.dtype not in (np.float16,np.float32) or p.shape!=(height,width) for p in planes):
            raise ValueError("EXR channels must be full-resolution finite float planes")
        rgba=np.stack(planes,axis=-1).astype(np.float32)
    if not np.all(np.isfinite(rgba)) or np.min(rgba[...,3])<0 or np.max(rgba[...,3])>1:
        raise ValueError("EXR contains invalid finite RGBA/alpha")
    if alpha_mode=="straight":rgba[...,:3]*=rgba[...,3:4]
    return rgba


def write_float_rgba(path,rgba,*,plan_sha256,budget):
    OpenEXR=_library()
    values=np.ascontiguousarray(rgba,dtype=np.float32)
    header={"compression":OpenEXR.ZIP_COMPRESSION,"type":OpenEXR.scanlineimage,
        "chromaticities":_PRIMARIES,"zx7_working_space":"linear_srgb","zx7_alpha_mode":"associated",
        "zx7_graph_sha256":plan_sha256}
    with OpenEXR.File(header,{"RGBA":values}) as image:image.write(str(path))
    decoded=read_float_rgba(path,budget=budget,alpha_mode="associated")
    if decoded.dtype!=np.float32 or decoded.tobytes()!=values.tobytes():
        raise RuntimeError("Float EXR did not retain exact authored 32-bit RGBA values")
