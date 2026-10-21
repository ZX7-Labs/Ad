"""Open font discovery for a real creative typography body.

An artist can choose any *installed* specific typeface. No forced Nimbus
palette, fixed art style or giant list of fonts in the AI context. Fontconfig
gets queried only when a named font is actually selected; missing specific
fonts are not silently swapped for an aesthetically different replacement.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

# Exact historically approved fallback binaries for the legacy project.
_ORIGINAL_FONTS={
    "sans":"/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf",
    "bold":"/usr/share/fonts/opentype/urw-base35/NimbusSans-Bold.otf",
    "serif":"/usr/share/fonts/opentype/urw-base35/P052-Italic.otf",
    "mono":"/usr/share/fonts/opentype/urw-base35/NimbusMonoPS-Regular.otf",
}
_GEN={"sans":"sans-serif","bold":"sans-serif:style=Bold",
      "serif":"serif","mono":"monospace"}
_SAFE_FONT=re.compile(r"^[\w .,:=-]{1,140}$",re.UNICODE)


def resolve_artist_font(name,*,which=None,match=None):
    if not isinstance(name,str) or not _SAFE_FONT.fullmatch(name):
        raise ValueError("Artistic font identifier must be a font name, not a file or command")
    if name in _ORIGINAL_FONTS and Path(_ORIGINAL_FONTS[name]).is_file():
        return str(Path(_ORIGINAL_FONTS[name]))
    finder=which or shutil.which
    command=finder("fc-match")
    if not command:
        raise RuntimeError("Fontconfig not installed; actual chosen typography cannot be rendered")
    query=_GEN.get(name,name)
    if match is None:
        match=lambda cmd:subprocess.check_output(cmd,timeout=12,text=True)
    value=match([command,"-f","%{family}\n%{file}\n",query])
    if not isinstance(value,str):
        raise RuntimeError("Font discovery returned no real file evidence")
    lines=value.splitlines()
    if len(lines)<2 or not lines[1].strip():
        raise RuntimeError("No physically resolved font asset")
    selected=Path(lines[1].strip())
    if not selected.is_file() or selected.suffix.lower() not in (".ttf",".otf",".ttc"):
        raise RuntimeError("Installed font file is missing")
    if name not in _GEN:
        desired=name.split(":")[0].casefold().strip()
        names=[x.strip().casefold() for x in lines[0].split(",")]
        if desired not in names:
            raise RuntimeError("Specific creative font absent; do not silently substitute")
    return str(selected)


def require_unicode_font_coverage(path,text):
    """Fail closed instead of printing tofu squares for Hindi/other scripts.

    FontTools checks actual physical Unicode cmap; RAQM/Harfbuzz is needed
    for joining/shaping. No arbitrary creative font substitution.
    """
    if not isinstance(text,str):
        raise ValueError("Type copy must be model-authored Unicode text")
    if text.isascii():
        return True
    try:
        from fontTools.ttLib import TTFont,TTCollection
        from PIL import features
    except ImportError as exc:
        raise RuntimeError("Actual Unicode glyph inspection runtime not installed") from exc
    if not features.check("raqm"):
        raise RuntimeError("Unicode complex text requires installed RAQM shaping engine")
    face=Path(path)
    if not face.is_file():
        raise RuntimeError("Artist-selected original font is not physically installed")
    try:
        if face.suffix.lower()==".ttc":
            faces=TTCollection(str(face)).fonts
        else:
            faces=[TTFont(str(face),fontNumber=0,lazy=True)]
        cmap=set()
        for font in faces:
            for table in font["cmap"].tables:
                if table.isUnicode():
                    cmap.update(table.cmap.keys())
    except Exception as exc:
        raise RuntimeError("Physical font's Unicode map could not be decoded") from exc
    chars={ord(c) for c in text if not c.isspace() and (
        unicodedata.category(c)!="Cf")}
    absent=sorted(chars-cmap)
    if absent:
        raise RuntimeError("Artist-selected installed font lacks "+
          str(len(absent))+" required Unicode glyphs; never silently substitute")
    return True
