"""Cached, rate-limited HTTP fetch (stdlib only). Every body is stored with its URL, fetch time and SHA-256, so a
rerun is reproducible and a later run can tell what changed. Fails closed: a failed fetch returns None and is logged."""
import gzip
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
import zlib
from datetime import datetime, timezone


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def age_days(iso):
    t = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - t).total_seconds() / 86400.0


class Fetcher:
    def __init__(self, cfg, log=None, offline=False):
        self.dir = os.path.join(cfg["cache_dir"], "http")
        os.makedirs(self.dir, exist_ok=True)
        self.ua, self.gap = cfg["user_agent"], cfg["min_seconds_between_requests"]
        self.timeout, self.retries = cfg["fetch_timeout"], cfg["fetch_retries"]
        self.offline, self.log = offline, log or (lambda *a: None)
        self._last = {}
        self.stats = {"network": 0, "cache": 0, "failed": 0, "bytes": 0}

    def _paths(self, url):
        h = hashlib.sha256(url.encode()).hexdigest()
        d = os.path.join(self.dir, h[:2])
        return os.path.join(d, h + ".body"), os.path.join(d, h + ".json")

    def meta(self, url):
        _, m = self._paths(url)
        if os.path.exists(m):
            with open(m) as f:
                return json.load(f)
        return None

    def get(self, url, max_age_days=None, binary=False):
        """Return (body, meta) or (None, None). max_age_days None = any cached copy is fine; 0 = always refetch."""
        b, m = self._paths(url)
        meta = self.meta(url)
        fresh = meta and os.path.exists(b) and (max_age_days is None or age_days(meta["fetched_at"]) < max_age_days)
        if fresh or (self.offline and meta and os.path.exists(b)):
            self.stats["cache"] += 1
            with open(b, "rb") as f:
                data = f.read()
            return (data if binary else data.decode("utf-8", "replace")), meta
        if self.offline:
            return None, None
        host = url.split("/")[2]
        for attempt in range(self.retries + 1):
            wait = self.gap - (time.time() - self._last.get(host, 0))
            if wait > 0:
                time.sleep(wait)
            self._last[host] = time.time()
            try:
                req = urllib.request.Request(url, headers={"User-Agent": self.ua, "Accept-Encoding": "gzip, deflate",
                                                           "Accept": "text/html,application/xhtml+xml,application/pdf,*/*"})
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    data = r.read()
                    enc = (r.headers.get("Content-Encoding") or "").lower()
                    if enc == "gzip":
                        data = gzip.decompress(data)
                    elif enc == "deflate":
                        data = zlib.decompress(data)
                    status, final, etag = r.status, r.geturl(), r.headers.get("ETag")
                prev = meta["sha256"] if meta else None
                meta = {"url": url, "final_url": final, "status": status, "fetched_at": now_iso(), "etag": etag,
                        "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "previous_sha256": prev}
                os.makedirs(os.path.dirname(b), exist_ok=True)
                with open(b, "wb") as f:
                    f.write(data)
                with open(m, "w") as f:
                    json.dump(meta, f)
                self.stats["network"] += 1
                self.stats["bytes"] += len(data)
                return (data if binary else data.decode("utf-8", "replace")), meta
            except urllib.error.HTTPError as e:
                self.log("fetch", url, "HTTP %s" % e.code)
                if e.code in (403, 404, 410):
                    break
                time.sleep(5 * (attempt + 1))
            except Exception as e:  # network errors, timeouts
                self.log("fetch", url, "error %s" % type(e).__name__)
                time.sleep(5 * (attempt + 1))
        self.stats["failed"] += 1
        return None, None
