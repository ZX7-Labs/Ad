"""Artist-authored scalar curves on the original, possibly fractional frame clock.

Cubic tangents are value-per-frame derivatives. Time outside the keys holds
the endpoint. These are controls for creative data, not executable BODY code.
"""
from __future__ import annotations
import bisect
import math


def finite_number(value, label="value"):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(label + " must be a finite real number")
    return float(value)


def validate_curve(value, *, max_keys=10000):
    if type(value) in (int, float):
        finite_number(value)
        return
    if not isinstance(value, dict) or set(value) != {"interpolation", "keys"}:
        raise ValueError("Control needs a number or an authored interpolation/key curve")
    mode = value["interpolation"]
    if mode not in ("hold", "linear", "cubic_hermite"):
        raise ValueError("Unknown curve interpolation")
    keys = value["keys"]
    if not isinstance(keys, list) or not 1 <= len(keys) <= max_keys:
        raise ValueError("Curve exceeds host key budget or has no keys")
    previous = -math.inf
    expected = {"frame", "value"}
    if mode == "cubic_hermite":
        expected |= {"in_slope", "out_slope"}
    for key in keys:
        if not isinstance(key, dict) or set(key) != expected:
            raise ValueError("Curve key does not match its interpolation contract")
        for name, datum in key.items():
            finite_number(datum, name)
        if key["frame"] <= previous:
            raise ValueError("Curve frames must be strictly increasing")
        previous = key["frame"]


def curve_value(value, frame):
    if type(value) in (int, float):
        return float(value)
    keys = value["keys"]
    i = bisect.bisect_right([k["frame"] for k in keys], frame) - 1
    if i < 0:
        return float(keys[0]["value"])
    if i >= len(keys) - 1 or value["interpolation"] == "hold":
        return float(keys[i]["value"])
    left, right = keys[i], keys[i + 1]
    span = right["frame"] - left["frame"]
    u = (frame - left["frame"]) / span
    if value["interpolation"] == "linear":
        return (1-u)*left["value"] + u*right["value"]
    return ((2*u**3-3*u*u+1)*left["value"]
            + (u**3-2*u*u+u)*span*left["out_slope"]
            + (-2*u**3+3*u*u)*right["value"]
            + (u**3-u*u)*span*right["in_slope"])
