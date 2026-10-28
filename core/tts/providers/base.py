"""Provider interface. Implementations write out_dir/<id>.wav and out_dir/dur.json."""
from __future__ import annotations

from typing import Any, Protocol


class TtsProvider(Protocol):
    name: str

    def synthesize(self, lines: list[dict[str, Any]], out_dir: str, **opts: Any) -> dict[str, float]:
        """Synthesize all lines. Returns dur map {id: seconds}. Raises SystemExit-style errors via caller."""
        ...
