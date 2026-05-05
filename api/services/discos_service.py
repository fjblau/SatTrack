"""
ESA DISCOSweb v2 API client service.

Provides access to ESA's DISCOS (Database and Information System Characterising Objects in Space)
via the DISCOSweb v2 REST/JSON:API.

Authentication: Bearer token from DISCOS_API_TOKEN env var.
All requests include DiscosWeb-Api-Version: 2 header.
Responses are cached for 24 hours by default (DISCOS_CACHE_TTL).
Rate-limit responses (429) are retried with backoff.
"""
from typing import Any, Dict, List, Optional
import logging
import time
import threading

import requests

from config import config

logger = logging.getLogger(__name__)

_BASE_URL = config.external.DISCOS_BASE_URL
_TOKEN = config.external.DISCOS_API_TOKEN
_CACHE_TTL = config.external.DISCOS_CACHE_TTL
_TIMEOUT = config.external.DISCOS_REQUEST_TIMEOUT

_cache: Dict[str, tuple] = {}
_cache_lock = threading.Lock()

_RATE_LIMIT_BACKOFF_BASE = 2.0
_RATE_LIMIT_MAX_RETRIES = 5
_RATE_LIMIT_FALLBACK_WAIT = 60.0
_RATE_LIMIT_REMAINING_THRESHOLD = 5


def _token_configured() -> bool:
    return bool(config.external.DISCOS_API_TOKEN)


def _make_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {config.external.DISCOS_API_TOKEN}",
        "DiscosWeb-Api-Version": "2",
        "Accept": "application/vnd.api+json",
    }


def _cache_get(key: str) -> Optional[Any]:
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del _cache[key]
            return None
        return value


def _cache_set(key: str, value: Any) -> None:
    with _cache_lock:
        _cache[key] = (value, time.monotonic() + config.external.DISCOS_CACHE_TTL)


def _do_get(path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict]:
    """
    Perform an authenticated GET against the DISCOS API.

    Handles rate limiting (429) with exponential backoff.
    Returns the parsed JSON dict, or None on error.
    """
    if not _token_configured():
        logger.warning("DISCOS_API_TOKEN not configured; skipping request")
        return None

    url = f"{config.external.DISCOS_BASE_URL}{path}"
    headers = _make_headers()

    for attempt in range(_RATE_LIMIT_MAX_RETRIES + 1):
        try:
            resp = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=config.external.DISCOS_REQUEST_TIMEOUT,
            )
            if resp.status_code == 200:
                remaining = resp.headers.get("X-Ratelimit-Remaining")
                if remaining is not None:
                    try:
                        if int(remaining) <= _RATE_LIMIT_REMAINING_THRESHOLD:
                            retry_after = resp.headers.get("Retry-After")
                            wait = float(retry_after) + 1.0 if retry_after else _RATE_LIMIT_FALLBACK_WAIT
                            logger.warning(
                                f"DISCOS rate budget nearly exhausted "
                                f"(remaining={remaining}); pausing {wait:.0f}s"
                            )
                            time.sleep(wait)
                    except ValueError:
                        pass
                return resp.json()
            elif resp.status_code == 429:
                if attempt < _RATE_LIMIT_MAX_RETRIES:
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after:
                        try:
                            wait = float(retry_after) + 1.0
                        except ValueError:
                            wait = _RATE_LIMIT_FALLBACK_WAIT
                    else:
                        wait = _RATE_LIMIT_FALLBACK_WAIT
                    logger.warning(
                        f"DISCOS rate limit hit; retrying in {wait:.0f}s (attempt {attempt + 1})"
                    )
                    time.sleep(wait)
                    continue
                else:
                    logger.error("DISCOS rate limit exhausted after all retries; giving up")
                    return None
            elif resp.status_code == 401:
                logger.error("DISCOS authentication failed; check DISCOS_API_TOKEN")
                return None
            elif resp.status_code == 404:
                logger.debug(f"DISCOS 404 for {path}")
                return None
            else:
                logger.warning(f"DISCOS returned {resp.status_code} for {path}")
                return None
        except requests.exceptions.Timeout:
            logger.error(f"DISCOS request timed out for {path}")
            return None
        except Exception as exc:
            logger.error(f"DISCOS request error for {path}: {exc}")
            return None
    return None


def _get_paginated(path: str, params: Optional[Dict[str, Any]] = None) -> List[Dict]:
    """
    Fetch all pages from a paginated DISCOS JSON:API endpoint.

    Follows JSON:API pagination links.links.next until exhausted.
    """
    results: List[Dict] = []
    p = dict(params or {})
    if "page[size]" not in p:
        p["page[size]"] = 100

    while path:
        data = _do_get(path, p)
        if data is None:
            break
        items = data.get("data", [])
        if isinstance(items, list):
            results.extend(items)
        elif isinstance(items, dict):
            results.append(items)

        links = data.get("links", {})
        next_url = links.get("next")
        if next_url:
            if next_url.startswith(config.external.DISCOS_BASE_URL):
                path = next_url[len(config.external.DISCOS_BASE_URL):]
            else:
                path = next_url
            p = {}
        else:
            break
    return results


def _parse_attributes(item: Dict) -> Dict:
    """Extract id + attributes from a JSON:API resource object."""
    return {
        "discos_id": item.get("id"),
        **item.get("attributes", {}),
    }


def get_objects(filters: Optional[Dict[str, Any]] = None) -> List[Dict]:
    """
    Fetch space objects from DISCOS.

    Returns list of attribute dicts with discos_id added.
    """
    cache_key = f"objects:{filters}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    params = dict(filters or {})
    items = _get_paginated("/objects", params)
    result = [_parse_attributes(i) for i in items]
    _cache_set(cache_key, result)
    return result


def get_object_by_cospar(cospar_id: str) -> Optional[Dict]:
    """
    Fetch a single space object by COSPAR / international designator.

    Returns attribute dict with discos_id, or None if not found.
    """
    cache_key = f"object_cospar:{cospar_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    items = _get_paginated("/objects", {"filter[cosparId]": cospar_id})
    if not items:
        return None
    result = _parse_attributes(items[0])
    _cache_set(cache_key, result)
    return result


def get_object_by_discos_id(discos_id: str) -> Optional[Dict]:
    """
    Fetch a single space object by its DISCOS internal ID.

    Returns attribute dict, or None if not found.
    """
    cache_key = f"object_discos:{discos_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    data = _do_get(f"/objects/{discos_id}")
    if data is None:
        return None
    result = _parse_attributes(data.get("data", {}))
    _cache_set(cache_key, result)
    return result


def get_fragmentation_events(filters: Optional[Dict[str, Any]] = None) -> List[Dict]:
    """
    Fetch fragmentation events from DISCOS.

    Returns list of attribute dicts with discos_id added.
    """
    cache_key = f"fragmentations:{filters}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    items = _get_paginated("/fragmentations", dict(filters or {}))
    result = [_parse_attributes(i) for i in items]
    _cache_set(cache_key, result)
    return result


def get_launch_events(filters: Optional[Dict[str, Any]] = None) -> List[Dict]:
    """
    Fetch launch events from DISCOS.

    Returns list of attribute dicts with discos_id added.
    """
    cache_key = f"launches:{filters}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    items = _get_paginated("/launches", dict(filters or {}))
    result = [_parse_attributes(i) for i in items]
    _cache_set(cache_key, result)
    return result


def get_launch_vehicles(filters: Optional[Dict[str, Any]] = None) -> List[Dict]:
    """
    Fetch launch vehicles from DISCOS.

    Returns list of attribute dicts with discos_id added.
    """
    cache_key = f"launch_vehicles:{filters}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    items = _get_paginated("/launch-vehicles", dict(filters or {}))
    result = [_parse_attributes(i) for i in items]
    _cache_set(cache_key, result)
    return result


def get_launch_sites(filters: Optional[Dict[str, Any]] = None) -> List[Dict]:
    """
    Fetch launch sites from DISCOS.

    Returns list of attribute dicts with discos_id added.
    """
    cache_key = f"launch_sites:{filters}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    items = _get_paginated("/launch-sites", dict(filters or {}))
    result = [_parse_attributes(i) for i in items]
    _cache_set(cache_key, result)
    return result


def get_entities(filters: Optional[Dict[str, Any]] = None) -> List[Dict]:
    """
    Fetch entities (operators/countries) from DISCOS.

    Returns list of attribute dicts with discos_id added.
    """
    cache_key = f"entities:{filters}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    items = _get_paginated("/entities", dict(filters or {}))
    result = [_parse_attributes(i) for i in items]
    _cache_set(cache_key, result)
    return result


def get_object_attributions(discos_id: str) -> List[Dict]:
    """
    Fetch fragmentation event attributions for a given DISCOS object ID.

    Returns list of relationship dicts (which events produced this fragment).
    """
    cache_key = f"attributions:{discos_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    data = _do_get(f"/objects/{discos_id}/relationships/fragmentations")
    if data is None:
        return []
    items = data.get("data", [])
    if isinstance(items, dict):
        items = [items]
    result = [{"discos_id": i.get("id"), "type": i.get("type")} for i in items]
    _cache_set(cache_key, result)
    return result


def get_fragmentation_attributed_objects(fragmentation_id: str) -> List[Dict]:
    """
    Fetch all objects attributed to a given DISCOS fragmentation event.

    Returns list of dicts with discos_id (the object's DISCOS ID) and optional confidence.
    """
    cache_key = f"frag_objects:{fragmentation_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    data = _do_get(f"/fragmentations/{fragmentation_id}/relationships/objects")
    if data is None:
        return []
    items = data.get("data", [])
    if isinstance(items, dict):
        items = [items]
    result = [{"discos_id": i.get("id"), "type": i.get("type")} for i in items]
    _cache_set(cache_key, result)
    return result


def health_check() -> Dict[str, Any]:
    """
    Lightweight health check — fetches a single object to verify connectivity.

    Returns dict with status "ready" or "error".
    """
    if not _token_configured():
        return {"status": "error", "detail": "DISCOS_API_TOKEN not configured"}

    data = _do_get("/objects", {"page[size]": 1})
    if data is None:
        return {"status": "error", "detail": "Failed to reach DISCOS API"}
    return {"status": "ready"}


def clear_cache() -> None:
    """Clear the in-memory response cache."""
    with _cache_lock:
        _cache.clear()
