from __future__ import annotations

from pathlib import Path
from typing import Iterable

from models.settings import ImageItem
from utils.paths import SUPPORTED_EXTENSIONS


def discover_images(inputs: Iterable[str | Path]) -> list[ImageItem]:
    found: dict[Path, ImageItem] = {}
    for raw in inputs:
        path = Path(raw).expanduser().resolve()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            found[path] = ImageItem(path=path, source_root=path.parent)
        elif path.is_dir():
            for candidate in path.rglob("*"):
                if candidate.is_file() and candidate.suffix.lower() in SUPPORTED_EXTENSIONS:
                    resolved = candidate.resolve()
                    found[resolved] = ImageItem(path=resolved, source_root=path)
    return sorted(found.values(), key=lambda item: str(item.path).casefold())

