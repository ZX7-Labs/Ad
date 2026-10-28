"""Frame-exact, bounded RIFF PCM WAV inspection across Python 3.11+.

Python 3.11's wave module rejects WAVE_FORMAT_EXTENSIBLE (0xFFFE), even
when its SubFormat is uncompressed integer PCM. Parse the RIFF structure
rather than assuming a particular interpreter recognizes that tag.
Never decode compressed audio or convert the owner's channel layout.
"""
from __future__ import annotations

import struct
from pathlib import Path

_PCM_SUBFORMAT = bytes.fromhex("0100000000001000800000aa00389b71")


def inspect_pcm_wav(path):
    """Return actual whole samples, clock and channels of a complete PCM RIFF.

    Refuse truncated or ambiguous chunks and non-PCM extensible subtypes.
    Physical codec decoding is independently performed by the media vault.
    """
    try:
        with Path(path).open("rb") as source:
            physical_size=source.seek(0,2)
            source.seek(0)
            header=source.read(12)
            if len(header)!=12 or header[:4]!=b"RIFF" or header[8:]!=b"WAVE":
                raise ValueError("WAV does not contain a RIFF/WAVE body")
            claimed_size=int.from_bytes(header[4:8],"little")+8
            if claimed_size>physical_size:
                raise ValueError("WAV claimed more PCM samples than physically recorded")
            if claimed_size<physical_size:
                raise ValueError("WAV has bytes beyond its RIFF body")
            remaining=physical_size-12
            fmt=None
            audio_size=None
            while remaining:
                if remaining<8:
                    raise ValueError("Truncated original WAV chunk header")
                chunk=source.read(8)
                kind=chunk[:4]
                length=int.from_bytes(chunk[4:],"little")
                padded=length+(length&1)
                remaining-=8
                if padded>remaining:
                    raise ValueError("WAV declared more original samples than exist")
                if kind==b"fmt ":
                    if fmt is not None or not 16<=length<=4096:
                        raise ValueError("Ambiguous original WAV sample format")
                    fmt=source.read(length)
                    if len(fmt)!=length:
                        raise ValueError("Truncated WAV sample format")
                else:
                    if kind==b"data":
                        if audio_size is not None:
                            raise ValueError("Multiple WAV sample chunks are ambiguous")
                        audio_size=length
                    source.seek(length,1)
                if length&1 and len(source.read(1))!=1:
                    raise ValueError("Missing WAV chunk padding")
                remaining-=padded
            if fmt is None or audio_size is None:
                raise ValueError("WAV is missing sample format or recorded data")
    except OSError as exc:
        raise ValueError("Original PCM WAV is not readable") from exc

    tag,channels,rate,byte_rate,alignment,bits=struct.unpack("<HHIIHH",fmt[:16])
    if tag==0xFFFE:
        if (len(fmt)<40 or struct.unpack_from("<H",fmt,16)[0]<22 or
                18+struct.unpack_from("<H",fmt,16)[0]>len(fmt) or
                fmt[24:40]!=_PCM_SUBFORMAT):
            raise ValueError("Extensible WAV is not authenticated integer PCM")
        valid_bits=struct.unpack_from("<H",fmt,18)[0]
        if not 1<=valid_bits<=bits:
            raise ValueError("Extensible WAV has inconsistent sample precision")
    elif tag!=1:
        raise ValueError("WAV sample codec is not uncompressed integer PCM")
    if (not 1<=channels<=64 or not 1<=rate<=768000 or
            bits not in (8,16,24,32,64) or
            alignment!=channels*(bits//8) or
            byte_rate!=rate*alignment or not audio_size or
            audio_size%alignment):
        raise ValueError("WAV original sample clock or sample count is invalid")
    return {"frames":audio_size//alignment,"sample_rate":rate,
            "channels":channels,"sample_bits":bits}
