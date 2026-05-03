"""Discover sound effects under assets/sfx and build stable DB keys + admin labels."""
from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings

_SFX_SUFFIXES = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}


def sfx_assets_dir() -> Path:
    return Path(settings.BASE_DIR) / "assets" / "sfx"


def normalize_sfx_key(stem: str) -> str:
    """Map a file stem to the CharField value (snake_case)."""
    s = stem.strip()
    s = re.sub(r"[-\s]+", "_", s)
    s = re.sub(r"[^a-zA-Z0-9_]", "", s)
    s = s.lower().strip("_")
    s = re.sub(r"_+", "_", s)
    return s or "sound"


def _human_label(stem: str) -> str:
    s = re.sub(r"[_-]+", " ", stem.strip())
    return s[:1].upper() + s[1:] if s else ""


def discover_sfx_map() -> dict[str, Path]:
    """Map sfx_choice string -> absolute path for each audio file in assets/sfx."""
    d = sfx_assets_dir()
    out: dict[str, Path] = {}
    if not d.is_dir():
        return out
    for p in sorted(d.iterdir(), key=lambda x: x.name.lower()):
        if not p.is_file():
            continue
        if p.suffix.lower() not in _SFX_SUFFIXES:
            continue
        key = normalize_sfx_key(p.stem)
        if key in out:
            continue
        out[key] = p.resolve()

    ping = (getattr(settings, "PING_SFX_PATH", None) or "").strip()
    if ping:
        pp = Path(ping)
        if pp.is_file():
            out["ping"] = pp.resolve()

    cam = (getattr(settings, "CAMERA_SFX_PATH", None) or "").strip()
    if cam:
        cp = Path(cam)
        if cp.is_file():
            out["camera_shutter"] = cp.resolve()

    return out


def get_sfx_choices() -> list[tuple[str, str]]:
    """Admin / model dropdown: (stored value, label)."""
    choices: list[tuple[str, str]] = [("none", "None")]
    for key, path in sorted(discover_sfx_map().items(), key=lambda x: x[0]):
        label = _human_label(path.stem) or key.replace("_", " ").title()
        choices.append((key, label))
    return choices
