"""Auto-detection of dataset properties from a directory.

Implements spec §11.5:
  - File types, sizes, counts, SHA-256 checksums
  - Column names, data types, cardinality, null rates, basic statistics (tabular)
  - Existing README, LICENSE, Croissant metadata, HuggingFace dataset cards
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FileInfo:
    """Detected file metadata."""
    path: str
    relative_path: str
    size_bytes: int
    extension: str
    sha256: str


@dataclass
class ColumnInfo:
    """Detected column metadata for tabular files."""
    name: str
    inferred_type: str
    null_count: int
    total_count: int
    cardinality: int | None = None

    @property
    def null_rate(self) -> float:
        return self.null_count / self.total_count if self.total_count > 0 else 0.0


@dataclass
class DetectionResult:
    """Results of auto-detection on a dataset directory."""
    root_path: str
    files: list[FileInfo] = field(default_factory=list)
    columns: dict[str, list[ColumnInfo]] = field(default_factory=dict)  # filename -> columns
    existing_metadata: dict[str, str] = field(default_factory=dict)  # type -> path
    total_size_bytes: int = 0
    file_type_counts: dict[str, int] = field(default_factory=dict)

    @property
    def has_tabular_data(self) -> bool:
        return any(ext in self.file_type_counts for ext in (".csv", ".tsv", ".parquet", ".jsonl"))

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
_CSV_SAMPLE_ROWS = 1000  # Rows to sample for column analysis


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
            # Check if it looks like Croissant
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


def _infer_column_type(values: list[str]) -> str:
    """Infer column type from sample string values."""
    non_empty = [v for v in values if v.strip()]
    if not non_empty:
        return "unknown"

    # Try int
    int_count = 0
    float_count = 0
    bool_count = 0
    for v in non_empty:
        try:
            int(v)
            int_count += 1
            continue
        except ValueError:
            pass
        try:
            float(v)
            float_count += 1
            continue
        except ValueError:
            pass
        if v.lower() in ("true", "false", "yes", "no", "0", "1"):
            bool_count += 1

    total = len(non_empty)
    if int_count == total:
        return "integer"
    if (int_count + float_count) == total:
        return "float"
    if bool_count == total:
        return "boolean"
    return "string"


def _analyse_csv(path: Path, delimiter: str = ",") -> list[ColumnInfo]:
    """Analyse a CSV/TSV file and return column info."""
    columns: list[ColumnInfo] = []
    try:
        with open(path, newline="", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f, delimiter=delimiter)
            headers = next(reader, None)
            if not headers:
                return columns

            # Collect samples
            col_values: list[list[str]] = [[] for _ in headers]
            row_count = 0
            for row in reader:
                if row_count >= _CSV_SAMPLE_ROWS:
                    break
                for i, val in enumerate(row):
                    if i < len(col_values):
                        col_values[i].append(val)
                row_count += 1

            for i, header in enumerate(headers):
                vals = col_values[i] if i < len(col_values) else []
                null_count = sum(1 for v in vals if v.strip() == "")
                unique_vals = set(vals) - {""}
                columns.append(ColumnInfo(
                    name=header.strip(),
                    inferred_type=_infer_column_type(vals),
                    null_count=null_count,
                    total_count=len(vals),
                    cardinality=len(unique_vals),
                ))
    except (OSError, csv.Error):
        pass
    return columns


def detect(directory: str | Path) -> DetectionResult:
    """Run auto-detection on a dataset directory.

    Scans the directory tree for files, computes checksums, analyses
    tabular data, and detects existing metadata files.
    """
    root = Path(directory).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Not a directory: {root}")

    result = DetectionResult(root_path=str(root))
    result.existing_metadata = _detect_metadata_files(root)

    file_count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skipped directories
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

            # Compute checksum
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

            # Analyse tabular files
            if ext == ".csv":
                cols = _analyse_csv(fpath, delimiter=",")
                if cols:
                    result.columns[rel] = cols
            elif ext == ".tsv":
                cols = _analyse_csv(fpath, delimiter="\t")
                if cols:
                    result.columns[rel] = cols

    return result
