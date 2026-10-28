"""Style adapters: validated plan → content-only files (never touch demo engine cores)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .caption_news import adapt_caption_news
from .pictogram_motion import adapt_pictogram_motion
from .swiss_motion import adapt_swiss_motion

ADAPTERS: dict[str, Callable[[dict[str, Any], Path], list[Path]]] = {
    "swiss-motion": adapt_swiss_motion,
    "pictogram-motion": adapt_pictogram_motion,
    "caption-news": adapt_caption_news,
}


def adapt(plan: dict[str, Any], out_dir: Path) -> list[Path]:
    style = plan["style"]
    if style not in ADAPTERS:
        raise ValueError(f"no adapter for style {style}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    return ADAPTERS[style](plan, out_dir)
