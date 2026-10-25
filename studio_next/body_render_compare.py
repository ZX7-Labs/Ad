"""Strict native RGB agreement with an explicit 8-bit numerical-roundoff budget.

Same solved geometry is checked independently by callers. CPU path tracing
and quantization may differ by one code value in very sparse pixels. A global
shift, geometric displacement or a two-code-value change is never accepted.
"""
from __future__ import annotations


def compare_native_rgb_arrays(reference,candidate):
    import numpy as np
    a=np.asarray(reference);b=np.asarray(candidate)
    if a.shape!=b.shape or a.ndim!=3 or a.shape[2]!=3 or not a.size:
        raise ValueError('Native comparisons require equal nonempty RGB dimensions')
    if a.dtype!=np.uint8 or b.dtype!=np.uint8:
        raise ValueError('Roundoff comparison is defined only for actual 8-bit RGB')
    delta=np.abs(a.astype(np.int16)-b.astype(np.int16))
    total=int(a.shape[0]*a.shape[1]);changed=int(np.any(delta,axis=2).sum())
    maximum=int(delta.max());fraction=changed/total
    return {'pixels_identical':changed==0,
        'within_quantization_tolerance':maximum<=1 and fraction<=.001,
        'max_channel_difference':maximum,'mean_absolute_channel_difference':float(delta.mean()),
        'differing_pixels':changed,'total_pixels':total,'differing_pixel_fraction':fraction,
        'allowed_channel_difference':1,'allowed_pixel_fraction':.001}


def compare_native_rgb(reference,candidate):
    import numpy as np
    from PIL import Image
    with Image.open(reference) as a,Image.open(candidate) as b:
        return compare_native_rgb_arrays(np.asarray(a.convert('RGB')),np.asarray(b.convert('RGB')))
