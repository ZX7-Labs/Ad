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
