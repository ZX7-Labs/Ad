"""Voice authoring is open; runtime availability is checked at synthesis time."""
import hashlib
import importlib.util
import json
import math
import re
from pathlib import Path

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
_LIMITS = {"speed": (.1, 4), "silence_duration": (0, 10),
           "total_steps": (1, 100), "max_chunk_length": (1, 10000)}


def valid_voice_id(value, *, allow_silence=True):
    return (isinstance(value, str) and bool(_NAME.fullmatch(value)) and
            value not in (".", "..") and (allow_silence or value != "no_voice"))


def validate_voice_settings(settings):
    if not isinstance(settings, dict) or set(settings) - (_LIMITS.keys() | {"lang"}):
        raise ValueError("Unknown voice synthesis settings")
    for key, value in settings.items():
        if key == "lang":
            if not isinstance(value, str) or not re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z]{2,8})?", value):
                raise ValueError("Voice lang must be an explicit language code")
            continue
        lo, hi = _LIMITS[key]
        if (isinstance(value, bool) or not isinstance(value, (int, float)) or
                not math.isfinite(value) or not lo <= value <= hi or
                (key in ("total_steps", "max_chunk_length") and type(value) is not int)):
            raise ValueError("Invalid voice setting: " + key)
    return dict(settings)


def voice_inventory(model_dir):
    """Discover installed style documents, without downloads or model inference.

    A parseable file is not proof that a TTS engine can load it; the engine's
    own voice_style_names and parser remain authoritative during synthesis.
    """
    root = Path(model_dir)
    styles = root / "voice_styles"
    voices = []
    if styles.is_dir() and not styles.is_symlink():
        for file in sorted(styles.glob("*.json")):
            if file.is_symlink() or not valid_voice_id(file.stem, allow_silence=False):
                continue
            if not 2 <= file.stat().st_size <= 16 * 1024 * 1024:
                continue
            raw = file.read_bytes()
            try:
                document = json.loads(raw)
            except (ValueError, UnicodeError):
                continue
            if isinstance(document, dict) and document:
                voices.append({"id": file.stem, "style_sha256": hashlib.sha256(raw).hexdigest()})
    return {"voices": voices, "tts_package_installed": importlib.util.find_spec("supertonic") is not None,
            "synthesis_verified": False, "automatic_downloads": False,
            "settings": {"lang": "engine-supported language code",
                         **{key:list(bounds) for key,bounds in _LIMITS.items()}},
            "per_scene_voice_and_settings": True}
