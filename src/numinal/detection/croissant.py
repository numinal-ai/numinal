"""Bootstrap a numinal data card from an existing Croissant JSON-LD document.

Implements the input side of spec §11.5 — read structured metadata from a
Croissant source (local path or URL) and map it onto numinal fields. JSON-LD
properties may appear with or without prefixes (`name` vs `sc:name`) depending
on the document's @context, and values may be plain strings or `{"@value": ...}`
objects, so all helpers normalise both shapes.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


_FETCH_TIMEOUT_SECONDS = 30


def load_croissant(source: str) -> dict[str, Any]:
    """Load a Croissant JSON-LD document from a local file path or HTTP(S) URL."""
    if source.startswith(("http://", "https://")):
        try:
            with urllib.request.urlopen(source, timeout=_FETCH_TIMEOUT_SECONDS) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Failed to fetch Croissant from {source}: {e}") from e
    else:
        path = Path(source)
        if not path.is_file():
            raise FileNotFoundError(f"Croissant file not found: {source}")
        raw = path.read_text(encoding="utf-8")

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Croissant source is not valid JSON: {e}") from e


def _get_prop(obj: dict[str, Any], *names: str) -> Any:
    """Return the first matching property value, trying prefixed and unprefixed names."""
    for n in names:
        if n in obj:
            return obj[n]
    return None


def _string_value(v: Any) -> str:
    """Normalise a JSON-LD value to a plain string."""
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        if "@value" in v:
            return _string_value(v["@value"])
        if "@id" in v:
            return _string_value(v["@id"])
        name = _get_prop(v, "name", "sc:name")
        if name is not None:
            return _string_value(name)
        return ""
    if isinstance(v, list):
        return _string_value(v[0]) if v else ""
    return str(v)


def _extract_creator(v: Any) -> str:
    """Extract a creator name from a string, Person/Organization object, or list."""
    if v is None:
        return ""
    if isinstance(v, list):
        names = [_extract_creator(item) for item in v]
        return ", ".join(n for n in names if n)
    if isinstance(v, dict):
        name = _get_prop(v, "name", "sc:name")
        if name is not None:
            return _string_value(name)
        return _string_value(v)
    return _string_value(v)


def _map_field(item: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    name = _get_prop(item, "name", "sc:name")
    if name is not None:
        out["name"] = _string_value(name)
    dtype = _get_prop(item, "dataType", "sc:dataType", "cr:dataType")
    if dtype is not None:
        out["dataType"] = _string_value(dtype)
    desc = _get_prop(item, "description", "sc:description")
    if desc is not None:
        out["description"] = _string_value(desc)
    return out


def _map_record_set(item: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    name = _get_prop(item, "name", "sc:name")
    if name is not None:
        out["name"] = _string_value(name)
    desc = _get_prop(item, "description", "sc:description")
    if desc is not None:
        out["description"] = _string_value(desc)
    fields = _get_prop(item, "field", "cr:field")
    if fields is not None:
        items = fields if isinstance(fields, list) else [fields]
        mapped = [_map_field(f) for f in items if isinstance(f, dict)]
        out["fields"] = [m for m in mapped if m]
    return out


def _map_distribution_entry(item: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    name = _get_prop(item, "name", "sc:name")
    if name is not None:
        out["name"] = _string_value(name)
    enc = _get_prop(item, "encodingFormat", "sc:encodingFormat")
    if enc is not None:
        out["contentType"] = _string_value(enc)
    size = _get_prop(item, "contentSize", "sc:contentSize")
    if size is not None:
        try:
            out["totalSizeBytes"] = int(_string_value(size))
        except ValueError:
            pass
    sha = _get_prop(item, "sha256", "cr:sha256")
    if sha is not None:
        out["sha256"] = _string_value(sha)
    return out


def extract_bootstrap(croissant: dict[str, Any]) -> dict[str, Any]:
    """Extract numinal-shaped fields from a Croissant JSON-LD document.

    Returns a dict containing only the fields the Croissant supplied; missing
    fields are simply absent. Caller is responsible for merging this with
    directory-scan results and prompts.
    """
    bootstrap: dict[str, Any] = {}

    name = _get_prop(croissant, "name", "sc:name")
    if name is not None:
        bootstrap["name"] = _string_value(name)

    desc = _get_prop(croissant, "description", "sc:description")
    if desc is not None:
        bootstrap["description"] = _string_value(desc)

    version = _get_prop(croissant, "version", "sc:version")
    if version is not None:
        bootstrap["version"] = _string_value(version)

    license_v = _get_prop(croissant, "license", "sc:license")
    if license_v is not None:
        bootstrap["license"] = _string_value(license_v)

    creator = _get_prop(croissant, "creator", "sc:creator")
    if creator is not None:
        bootstrap["creator"] = _extract_creator(creator)

    date_published = _get_prop(croissant, "datePublished", "sc:datePublished")
    if date_published is not None:
        bootstrap["datePublished"] = _string_value(date_published)

    distribution = _get_prop(croissant, "distribution", "cr:distribution", "sc:distribution")
    if distribution is not None:
        items = distribution if isinstance(distribution, list) else [distribution]
        mapped = [_map_distribution_entry(d) for d in items if isinstance(d, dict)]
        bootstrap["distribution"] = [m for m in mapped if m]

    record_set = _get_prop(croissant, "recordSet", "cr:recordSet")
    if record_set is not None:
        items = record_set if isinstance(record_set, list) else [record_set]
        mapped = [_map_record_set(r) for r in items if isinstance(r, dict)]
        bootstrap["recordSet"] = [m for m in mapped if m]

    return bootstrap
