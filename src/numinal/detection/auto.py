"""Auto-detection of dataset properties from a directory.

Implements spec §11.5:
  - File types, sizes, counts, SHA-256 checksums
  - Existing README, LICENSE, Croissant metadata, HuggingFace dataset cards
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FileInfo:
    """Detected file metadata."""
    path: str
    relative_path: str
    size_bytes: int
    extension: str
    sha256: str


@dataclass
class DetectionResult:
    """Results of auto-detection on a dataset directory."""
    root_path: str
    files: list[FileInfo] = field(default_factory=list)
    existing_metadata: dict[str, str] = field(default_factory=dict)  # type -> path
    total_size_bytes: int = 0
    file_type_counts: dict[str, int] = field(default_factory=dict)

    @property
    def has_existing_croissant(self) -> bool:
        return "croissant" in self.existing_metadata

    @property
    def has_existing_license(self) -> bool:
        return "license" in self.existing_metadata

    @property
    def has_existing_readme(self) -> bool:
        return "readme" in self.existing_metadata


# Files to skip during scanning
_SKIP_DIRS = {".git", ".hg", "__pycache__", "node_modules", ".venv", "venv", ".numinal"}
_MAX_FILES = 10_000  # Safety limit
_HASH_CHUNK_SIZE = 8192


def _sha256(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(_HASH_CHUNK_SIZE):
            h.update(chunk)
    return h.hexdigest()


def _detect_metadata_files(root: Path) -> dict[str, str]:
    """Detect existing metadata files in the root directory."""
    metadata: dict[str, str] = {}

    for name in os.listdir(root):
        lower = name.lower()
        full = root / name

        if not full.is_file():
            continue

        if lower.startswith("readme"):
            metadata["readme"] = str(full)
        elif lower.startswith("license") or lower == "licence" or lower.startswith("licence"):
            metadata["license"] = str(full)
        elif lower in ("croissant.json", "metadata.json"):
            try:
                with open(full) as f:
                    data = json.load(f)
                if "@context" in data or "@type" in data or "recordSet" in data:
                    metadata["croissant"] = str(full)
            except (json.JSONDecodeError, OSError):
                pass
        elif lower in ("dataset_card.md", "datacard.md", "dataset_info.json"):
            metadata["huggingface"] = str(full)
        elif lower == "numinal.yaml":
            metadata["numinal"] = str(full)

    return metadata


def detect(directory: str | Path) -> DetectionResult:
    """Run auto-detection on a dataset directory.

    Scans the directory tree for files, computes checksums, and detects
    existing metadata files. Does not read file contents for analysis —
    recordSet schemas are publisher-supplied.
    """
    root = Path(directory).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Not a directory: {root}")

    result = DetectionResult(root_path=str(root))
    result.existing_metadata = _detect_metadata_files(root)

    file_count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]

        for fname in filenames:
            if file_count >= _MAX_FILES:
                break

            fpath = Path(dirpath) / fname
            if not fpath.is_file():
                continue

            ext = fpath.suffix.lower()
            size = fpath.stat().st_size
            rel = str(fpath.relative_to(root))
            checksum = _sha256(fpath)

            result.files.append(FileInfo(
                path=str(fpath),
                relative_path=rel,
                size_bytes=size,
                extension=ext,
                sha256=checksum,
            ))
            result.total_size_bytes += size
            result.file_type_counts[ext] = result.file_type_counts.get(ext, 0) + 1
            file_count += 1

    return result
