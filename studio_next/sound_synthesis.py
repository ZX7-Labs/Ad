"""Artist-authored oscillators, noise and envelopes, without named SFX presets.

This is procedural sound synthesis, not semantic Foley/music generation.
Recorded or generated sound files use the existing attested compositor tracks.
"""
import math


def validate_mix(settings):
    allowed={"voice_gain_db","fade_in_seconds","fade_out_seconds","peak_ceiling","loudness"}
    if not isinstance(settings,dict) or set(settings)-allowed:
        raise ValueError("Unsupported authored sound mix settings")
    for key in ("fade_in_seconds","fade_out_seconds"):
        if key in settings:_number(settings[key],key,0,86400)
    if "voice_gain_db" in settings:_number(settings["voice_gain_db"],"voice gain",-120,120)
    if settings.get("peak_ceiling") is not None:
        _number(settings["peak_ceiling"],"peak ceiling",.000001,1)
    if settings.get("loudness") is not None:
        if not isinstance(settings["loudness"],dict) or set(settings["loudness"])!={
                "integrated_lufs","true_peak_dbfs","loudness_range"}:
            raise ValueError("Loudness target needs explicit LUFS, true peak and range")
        from .film_finishing import build_finishing_filters
        build_finishing_filters({"video_ops":[],"audio_ops":[{
            "kind":"loudnorm",**settings["loudness"]}]},has_audio=True)
    return dict(settings)


def _number(value, name, low, high):
    if (isinstance(value, bool) or not isinstance(value, (int, float)) or
            not math.isfinite(value) or not low <= value <= high):
        raise ValueError("Invalid sound " + name)
    return value


def validate_synth(cue, duration):
    required = {"type", "at", "seconds", "gain", "partials", "noise_gain", "seed", "envelope"}
    if not isinstance(cue, dict) or set(cue) != required or cue["type"] != "synth":
        raise ValueError("Sound requires explicit synth, timing, spectrum, noise and envelope")
    start = _number(cue["at"], "time", 0, duration)
    length = _number(cue["seconds"], "duration", .001, duration)
    if start + length > duration + 1e-9:
        raise ValueError("Sound extends beyond the authored scene")
    _number(cue["gain"], "gain", 0, 16)
    _number(cue["noise_gain"], "noise gain", 0, 1)
    if type(cue["seed"]) is not int or not 0 <= cue["seed"] < 2**64:
        raise ValueError("Sound noise needs an explicit stable seed")
    if not isinstance(cue["partials"], list) or len(cue["partials"]) > 64:
        raise ValueError("Sound partial count exceeds host budget")
    for part in cue["partials"]:
        if not isinstance(part, dict) or set(part) != {"start_hz", "end_hz", "amplitude", "phase_radians"}:
            raise ValueError("Each sound partial needs frequencies, amplitude and phase")
        for key in ("start_hz", "end_hz"):
            _number(part[key], key, 0, 24000)
        _number(part["amplitude"], "partial amplitude", 0, 16)
        _number(part["phase_radians"], "phase", -1e6, 1e6)
    envelope = cue["envelope"]
    if not isinstance(envelope, list) or not 2 <= len(envelope) <= 128:
        raise ValueError("Sound needs an authored piecewise-linear envelope")
    previous = -1
    for point in envelope:
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError("Sound envelope needs [seconds, amplitude]")
        at = _number(point[0], "envelope time", 0, length)
        _number(point[1], "envelope amplitude", 0, 16)
        if at <= previous:
            raise ValueError("Sound envelope times must strictly increase")
        previous = at
    if envelope[0][0] != 0 or abs(envelope[-1][0] - length) > 1e-9:
        raise ValueError("Sound envelope must cover the exact authored duration")
    return cue


def synthesize(cue, rate):
    import numpy as np
    validate_synth(cue, cue["at"] + cue["seconds"])
    if type(rate) is not int or not 8000 <= rate <= 192000:
        raise ValueError("Unsupported physical sound sample rate")
    samples = round(cue["seconds"] * rate)
    t = np.arange(samples) / rate
    signal = np.random.default_rng(cue["seed"]).normal(0, 1, samples) * cue["noise_gain"]
    for part in cue["partials"]:
        if max(part["start_hz"], part["end_hz"]) >= rate / 2:
            raise ValueError("Sound partial exceeds actual sample-rate Nyquist limit")
        phase = 2 * np.pi * (part["start_hz"] * t +
                    (part["end_hz"] - part["start_hz"]) * t*t / (2*cue["seconds"]))
        signal += part["amplitude"] * np.sin(phase + part["phase_radians"])
    envelope = np.asarray(cue["envelope"])
    return signal * np.interp(t, envelope[:, 0], envelope[:, 1]) * cue["gain"]
