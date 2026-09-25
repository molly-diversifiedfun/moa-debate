"""Resolve roster FAMILIES to real model ids at call time.

Dated ids retire (claude-opus-4-20250514 now returns Anthropic 404
not_found_error). Pinning them in the roster broke every debate the day they
went away. A roster entry may instead name a family ("anthropic:opus"); the id
is resolved in this order:

  1. override   MOA_MODEL_<FAMILY> env var (ANTHROPIC_OPUS for anthropic:opus)
                or ~/.moa/models.yaml {"anthropic:opus": "anthropic/claude-opus-5"}
  2. cache      ~/.moa/model-cache.json, if resolved in the last 24h
  3. listed     the provider's own list-models endpoint, newest family member
  4. stale      an expired cache entry, if the listing call fails
  5. pinned     the roster entry's own name, the last resort

"Newest" is decided by the version in the id (major, minor, date), never by
list order: claude-opus-4-20250514 is 4.0, older than claude-opus-4-5-20251101.
Ids that returned 404 are recorded as retired and skipped from then on.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import config

CACHE_TTL_S = 24 * 3600
LIST_TIMEOUT_S = 15


@dataclass(frozen=True)
class Family:
    provider: str          # key for list_provider_models
    pattern: str           # regex over the provider's bare id
    litellm_prefix: str    # prepended to the bare id for litellm


FAMILIES: Dict[str, Family] = {
    # claude-<family>-<major>[-<minor 1-2 digits>][-<YYYYMMDD>]
    "anthropic:opus": Family("anthropic", r"^claude-opus-(\d+)(?:-(\d{1,2}))?(?:-(\d{8}))?$", "anthropic/"),
    "anthropic:sonnet": Family("anthropic", r"^claude-sonnet-(\d+)(?:-(\d{1,2}))?(?:-(\d{8}))?$", "anthropic/"),
    "anthropic:haiku": Family("anthropic", r"^claude-haiku-(\d+)(?:-(\d{1,2}))?(?:-(\d{8}))?$", "anthropic/"),
    # plain gpt-<major>[.<minor>]: excludes -pro, -mini, -codex and named variants
    "openai:flagship": Family("openai", r"^gpt-(\d+)(?:\.(\d+))?()$", ""),
}


def _version(family: Family, bare_id: str) -> Optional[Tuple[int, int, int]]:
    m = re.match(family.pattern, bare_id)
    if not m:
        return None
    major, minor, date = (m.group(1), m.group(2), m.group(3))
    return (int(major), int(minor or 0), int(date or 0))


def pick_newest(family_key: str, bare_ids: List[str], retired: Optional[List[str]] = None) -> Optional[str]:
    """Newest listed member of the family, as a litellm id; None if none listed."""
    fam = FAMILIES[family_key]
    skip = set(retired or [])
    ranked = sorted(
        ((v, i) for i in bare_ids if (v := _version(fam, i)) and fam.litellm_prefix + i not in skip),
        reverse=True,
    )
    return fam.litellm_prefix + ranked[0][1] if ranked else None


def list_provider_models(provider: str) -> List[str]:
    """Bare model ids from the provider's list-models endpoint. Raises on failure."""
    if provider == "anthropic":
        key = os.environ["ANTHROPIC_API_KEY"]
        ids, after = [], None
        while True:
            url = "https://api.anthropic.com/v1/models?limit=1000" + (f"&after_id={after}" if after else "")
            req = urllib.request.Request(url, headers={"x-api-key": key, "anthropic-version": "2023-06-01"})
            with urllib.request.urlopen(req, timeout=LIST_TIMEOUT_S) as r:
                page = json.load(r)
            ids += [m["id"] for m in page.get("data", [])]
            if not page.get("has_more"):
                return ids
            after = page.get("last_id")
    if provider == "openai":
        key = os.environ["OPENAI_API_KEY"]
        req = urllib.request.Request("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=LIST_TIMEOUT_S) as r:
            return [m["id"] for m in json.load(r).get("data", [])]
    raise ValueError(f"no list-models endpoint for provider {provider!r}")


# ── cache ────────────────────────────────────────────────────────────────────

def _cache_path() -> Path:
    return config.MOA_HOME / "model-cache.json"


def _load_cache() -> dict:
    try:
        return json.loads(_cache_path().read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_cache(cache: dict) -> None:
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, indent=2))
    tmp.replace(path)


def _override(family_key: str) -> Optional[str]:
    env = os.environ.get("MOA_MODEL_" + re.sub(r"[^A-Z0-9]", "_", family_key.upper()))
    if env:
        return env
    path = config.MOA_HOME / "models.yaml"
    if path.exists():
        import yaml
        pinned = (yaml.safe_load(path.read_text()) or {}).get(family_key)
        if pinned:
            return str(pinned)
    return None


def resolve_model(model) -> Tuple[str, str]:
    """(litellm id, source) for a ModelConfig. Never raises."""
    family_key = getattr(model, "family", None)
    if not family_key:
        return model.name, "pinned"
    override = _override(family_key)
    if override:
        return override, "override"
    cache = _load_cache()
    entry = cache.get("families", {}).get(family_key)
    if entry and time.time() - entry.get("resolved_at", 0) < CACHE_TTL_S:
        return entry["id"], "cache"
    try:
        newest = pick_newest(family_key, list_provider_models(FAMILIES[family_key].provider), cache.get("retired"))
    except Exception:
        newest = None
    if newest:
        cache.setdefault("families", {})[family_key] = {"id": newest, "resolved_at": time.time()}
        _save_cache(cache)
        return newest, "listed"
    if entry:
        return entry["id"], "stale-cache"
    return model.name, "pinned"


def mark_retired(model, litellm_id: str) -> None:
    """Record an id that returned 404 and drop the family's cached resolution."""
    cache = _load_cache()
    retired = cache.setdefault("retired", [])
    if litellm_id not in retired:
        retired.append(litellm_id)
    if getattr(model, "family", None):
        cache.get("families", {}).pop(model.family, None)
    _save_cache(cache)


def is_not_found(exc: Exception) -> bool:
    """True for a provider 'model does not exist' error: retire, don't back off."""
    status = getattr(exc, "status_code", None)
    text = str(exc)
    return status == 404 or "not_found_error" in text or "model_not_found" in text
