"""Source-exact, reversible SMPTE-style editorial frame/timecode labels.

Timecode is an address/label for real media frames, not a frame-drop,
retiming instruction, guessed FPS, wall clock or duration approximation.
Frame/sample clocks remain exact rational numbers. This module never
changes original media, creative decisions, time bases, assets or rights.

Reference derivation: FFmpeg libavutil/timecode.c, SMPTE ST 12-1 time
addresses, and IETF RFC 5484 §4.2.2. Drop-frame labels at 30000/1001
and 60000/1001 skip numbered addresses, NEVER actual decoded frames.
"""
from __future__ import annotations

import re
from fractions import Fraction

_LABEL=re.compile(r"(?P<h>[0-9]{2}):(?P<m>[0-9]{2}):(?P<s>[0-9]{2})(?P<mark>[:;])(?P<f>[0-9]{2})\Z")
_DROP={Fraction(30000,1001):(30,2),Fraction(60000,1001):(60,4)}


def _rate(numerator,denominator,drop_frame):
    if (type(numerator) is not int or type(denominator) is not int
            or not 1<=numerator<=1_000_000_000
            or not 1<=denominator<=1_000_000_000):
        raise ValueError("Timecode requires exact bounded positive rational frame rate")
    if type(drop_frame) is not bool:
        raise ValueError("SMPTE drop-frame label policy must be an exact boolean")
    rate=Fraction(numerator,denominator)
    nominal=(2*rate.numerator+rate.denominator)//(2*rate.denominator)
    if not 1<=nominal<=99:
        raise ValueError("Two-digit SMPTE frame field cannot represent this rate")
    if drop_frame:
        if rate not in _DROP:
            raise ValueError("Drop-frame is restricted to exact standard NTSC rational clocks")
        nominal,skipped=_DROP[rate]
    else:
        skipped=0
    per_day=nominal*24*60*60-skipped*(24*60-24*6)
    return rate,nominal,skipped,per_day


def _frame(frame_index,per_day):
    if type(frame_index) is not int or not 0<=frame_index<per_day:
        raise ValueError("Timecode must identify one actual frame within one 24h label epoch")
    return frame_index


def format_timecode(frame_index,numerator,denominator,*,drop_frame=False):
    """Bijection: a source-frame index → one exact HH:MM:SS[:;]FF label."""
    _,nominal,skip,per_day=_rate(numerator,denominator,drop_frame)
    frame=_frame(frame_index,per_day)
    if skip:
        every_tenth=nominal*600-skip*9
        ordinary_minute=nominal*60-skip
        ten,remaining=divmod(frame,every_tenth)
        # Each non-tenth minute begins with 2 (or 4) invalid *labels*.
        # Do not remove any actual frames or use 29.97 float rounding.
        labels=frame+skip*9*ten
        labels+=skip*max(0,(remaining-skip)//ordinary_minute)
    else:
        labels=frame
    ff=labels%nominal
    sec=labels//nominal%60
    minute=labels//(nominal*60)%60
    hour=labels//(nominal*3600)
    if not 0<=hour<24:
        raise ValueError("Timecode label unexpectedly crossed the exact 24h boundary")
    divider=";" if skip else ":"
    return f"{hour:02d}:{minute:02d}:{sec:02d}{divider}{ff:02d}"


def parse_timecode(label,numerator,denominator):
    """Strict inverse; omitted drop-frame addresses are invalid, never clamped."""
    if not isinstance(label,str) or len(label)!=11:
        raise ValueError("SMPTE label must have exactly eleven ASCII characters")
    parts=_LABEL.fullmatch(label)
    if not parts:
        raise ValueError("Invalid HH:MM:SS:FF or HH:MM:SS;FF timecode grammar")
    drop=parts["mark"]==";"
    _,nominal,skip,per_day=_rate(numerator,denominator,drop)
    hh,mm,ss,ff=(int(parts[k]) for k in ("h","m","s","f"))
    if hh>23 or mm>59 or ss>59 or ff>=nominal:
        raise ValueError("SMPTE original timecode address exceeds valid field bounds")
    if skip and mm%10!=0 and ss==0 and ff<skip:
        raise ValueError("Omitted drop-frame label has no physically existing source frame")
    elapsed_minutes=hh*60+mm
    indexed=((hh*3600+mm*60+ss)*nominal+ff
             -skip*(elapsed_minutes-elapsed_minutes//10))
    _frame(indexed,per_day)
    # Canonical inverse assures non-standard, reordered and ambiguous labels
    # never map to an adjacent recorded media frame.
    if format_timecode(indexed,numerator,denominator,drop_frame=drop)!=label:
        raise ValueError("SMPTE label cannot be reconstructed without loss")
    return indexed,drop


def _receipt(index,numerator,denominator,drop):
    rate,nominal,skip,per_day=_rate(numerator,denominator,drop)
    exact_seconds=Fraction(index,1)/rate
    return {
        "rate_numerator":numerator,
        "rate_denominator":denominator,
        "frame_index":index,
        "drop_frame":drop,
        "timecode_label":format_timecode(index,numerator,denominator,
                                         drop_frame=drop),
        "nominal_label_frames_per_second":nominal,
        "labels_skipped_per_nontenth_minute":skip,
        "frames_per_24h_label_epoch":per_day,
        "physical_elapsed_seconds_numerator":exact_seconds.numerator,
        "physical_elapsed_seconds_denominator":exact_seconds.denominator,
        "actual_picture_frames_removed":0,
        "artistic_or_delivery_quality_certified":False,
    }


def frame_timecode_receipt(frame_index,numerator,denominator,drop_frame):
    _,_,_,per_day=_rate(numerator,denominator,drop_frame)
    return _receipt(_frame(frame_index,per_day),
                    numerator,denominator,drop_frame)


def parse_timecode_receipt(timecode,numerator,denominator):
    index,drop=parse_timecode(timecode,numerator,denominator)
    return {"input_timecode_label":timecode,
            **_receipt(index,numerator,denominator,drop)}


def verify_timecode_receipt(result,tool_id):
    """Re-evaluate the identical address and physical clock on durable replay."""
    if type(result) is not dict:
        return False
    try:
        if tool_id=="body.timecode_format":
            expected=frame_timecode_receipt(
                result["frame_index"],result["rate_numerator"],
                result["rate_denominator"],result["drop_frame"])
        elif tool_id=="body.timecode_parse":
            expected=parse_timecode_receipt(
                result["input_timecode_label"],result["rate_numerator"],
                result["rate_denominator"])
        else:
            return False
        return result==expected
    except (ValueError,TypeError,KeyError,OverflowError):
        return False
