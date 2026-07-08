"""Look up whether a package actually exists on npm / PyPI, with a small on-disk cache."""

import json
import os
import subprocess
import time
from urllib.parse import quote

CACHE_DIR = os.path.expanduser("~/.cache/slopstop")
CACHE_FILE = os.path.join(CACHE_DIR, "registry_cache.json")
CACHE_TTL_SECONDS = 24 * 60 * 60
TIMEOUT = 3


def _load_cache():
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(cache):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f)
    except Exception:
        pass  # caching is best-effort, never fatal


_cache = None


def _get_cache():
    global _cache
    if _cache is None:
        _cache = _load_cache()
    return _cache


def _cache_key(ecosystem, name):
    return f"{ecosystem}:{name.lower()}"


def _fetch(url):
    """Shell out to curl (uses the OS trust store, sidesteps python cert-store issues).
    Returns (status_code, parsed_json_or_None)."""
    try:
        proc = subprocess.run(
            ["curl", "-sS", "-m", str(TIMEOUT), "-A", "slopstop-claude-plugin",
             "-w", "\n%{http_code}", url],
            capture_output=True, text=True, timeout=TIMEOUT + 2,
        )
    except Exception:
        return None, None
    if proc.returncode != 0:
        return None, None
    output = proc.stdout
    idx = output.rfind("\n")
    if idx == -1:
        return None, None
    body, status_str = output[:idx], output[idx + 1:].strip()
    try:
        status = int(status_str)
    except ValueError:
        return None, None
    data = None
    if status == 200:
        try:
            data = json.loads(body)
        except Exception:
            return status, None
    return status, data


def _lookup_npm(name):
    """Returns dict: {exists, published_days_ago} or {exists, error}."""
    url = f"https://registry.npmjs.org/{quote(name, safe='@')}"
    status, data = _fetch(url)
    if status == 404:
        return {"exists": False}
    if status != 200 or data is None:
        return {"exists": True, "error": True}

    published_days_ago = None
    try:
        created = data.get("time", {}).get("created")
        if created:
            created_ts = time.mktime(time.strptime(created[:19], "%Y-%m-%dT%H:%M:%S"))
            published_days_ago = (time.time() - created_ts) / 86400
    except Exception:
        pass

    return {"exists": True, "published_days_ago": published_days_ago}


def _lookup_pypi(name):
    url = f"https://pypi.org/pypi/{quote(name)}/json"
    status, data = _fetch(url)
    if status == 404:
        return {"exists": False}
    if status != 200 or data is None:
        return {"exists": True, "error": True}

    published_days_ago = None
    try:
        releases = data.get("releases", {})
        upload_times = []
        for files in releases.values():
            for f in files:
                if f.get("upload_time"):
                    upload_times.append(f["upload_time"])
        if upload_times:
            earliest = min(upload_times)
            created_ts = time.mktime(time.strptime(earliest[:19], "%Y-%m-%dT%H:%M:%S"))
            published_days_ago = (time.time() - created_ts) / 86400
    except Exception:
        pass

    return {"exists": True, "published_days_ago": published_days_ago}


_LOOKUPS = {"npm": _lookup_npm, "pypi": _lookup_pypi}


def check_package(ecosystem, name):
    """Returns a result dict, using and updating the on-disk cache."""
    cache = _get_cache()
    key = _cache_key(ecosystem, name)
    cached = cache.get(key)
    if cached and (time.time() - cached.get("_ts", 0)) < CACHE_TTL_SECONDS:
        return cached["result"]

    lookup_fn = _LOOKUPS.get(ecosystem)
    if lookup_fn is None:
        return {"exists": True, "error": True}

    result = lookup_fn(name)
    cache[key] = {"_ts": time.time(), "result": result}
    _save_cache(cache)
    return result


NEW_PACKAGE_THRESHOLD_DAYS = 30
