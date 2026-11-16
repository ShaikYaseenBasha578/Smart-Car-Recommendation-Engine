"""Cached, rate-limited HTTP fetch (stdlib only). Every body is stored with its URL, fetch time and SHA-256, so a
rerun is reproducible and a later run can tell what changed. Fails closed: a failed fetch returns None and is logged."""
import gzip
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
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
        self.obey_robots = cfg.get("obey_robots", True)
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
        if self.obey_robots and not url.split("?")[0].endswith("/robots.txt"):
            # every network fetch, spec pages and brochures included, obeys robots.txt for this tool's user agent and for "*";
            # a refused path is recorded and never retried under another identity. Cached copies are not affected.
            if not self.robots_ok(url):
                self.__dict__.setdefault("blocks", []).append((url, "robots"))
                self.log("fetch", url, "disallowed by robots.txt; not fetched")
                self.stats["failed"] += 1
                return None, None
            self.gap_for = max(self.gap, self.crawl_delay(url) or 0)
        for attempt in range(self.retries + 1):
            wait = (self.__dict__.get("gap_for") or self.gap) - (time.time() - self._last.get(host, 0))
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


# ---- robots.txt (RFC 9309 subset): used by every network fetch, spec pages and review pages alike ----
class Robots:
    """Parsed robots.txt. Groups are chosen by the longest user-agent token that the product token starts with, else "*".
    Allow/Disallow patterns support * and $; the longest matching pattern wins, Allow wins a tie. Crawl-delay is read per group."""

    def __init__(self, text=""):
        self.groups = []          # [(agents, rules[(allow, pattern)], crawl_delay)]
        agents, rules, delay, in_rules = [], [], None, False
        for raw in (text or "").splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            k, v = (x.strip() for x in line.split(":", 1))
            k = k.lower()
            if k == "user-agent":
                if in_rules:
                    self.groups.append((agents, rules, delay))
                    agents, rules, delay, in_rules = [], [], None, False
                agents.append(v.lower())
            elif k in ("allow", "disallow"):
                in_rules = True
                if v:
                    rules.append((k == "allow", v))
            elif k == "crawl-delay":
                in_rules = True
                try:
                    delay = float(v)
                except ValueError:
                    pass
        if agents:
            self.groups.append((agents, rules, delay))

    def _group(self, ua):
        token = (ua or "*").split("/")[0].split()[0].lower()
        best, blen = None, -1
        for g in self.groups:
            for a in g[0]:
                if a != "*" and a and token.startswith(a) and len(a) > blen:
                    best, blen = g, len(a)
        if best is None:
            best = next((g for g in self.groups if "*" in g[0]), None)
        return best

    @staticmethod
    def _match(pattern, path):
        rx = re.escape(pattern).replace(r"\*", ".*")
        if rx.endswith(r"\$"):
            rx = rx[:-2] + "$"
        return re.match(rx, path) is not None

    def allowed(self, ua, url):
        g = self._group(ua)
        if g is None:
            return True
        u = urllib.parse.urlsplit(url)
        path = (u.path or "/") + ("?" + u.query if u.query else "")
        best = None
        for allow, pat in g[1]:
            if self._match(pat, path):
                key = (len(pat), allow)
                if best is None or key > best:
                    best = key
        return True if best is None else best[1]

    def delay(self, ua):
        g = self._group(ua)
        return g[2] if g else None


def _robots(self, host_url):
    """Robots for the site of host_url (cached for the life of the Fetcher and on disk for a day). A missing file (404/410)
    allows everything; a file that cannot be read for any other reason fails closed (nothing is fetched from that site)."""
    scheme_host = "/".join(host_url.split("/")[:3])
    cache = self.__dict__.setdefault("_robots_cache", {})
    if scheme_host in cache:
        return cache[scheme_host]
    seen = []
    old_log, old_retries = self.log, self.retries
    self.log, self.retries = (lambda *a: seen.append(" ".join(str(x) for x in a))), 1
    try:
        body, meta = self.get(scheme_host + "/robots.txt", max_age_days=1)
    finally:
        self.log, self.retries = old_log, old_retries
    if body is not None:
        cache[scheme_host] = Robots(body)
    elif any("HTTP 404" in s or "HTTP 410" in s for s in seen):
        cache[scheme_host] = Robots("")
    else:
        cache[scheme_host] = None          # unreadable robots file: fail closed
    return cache[scheme_host]


def robots_ok(self, url):
    r = self._robots(url)
    return bool(r and r.allowed("*", url) and r.allowed(self.ua, url))


def crawl_delay(self, url):
    r = self._robots(url)
    vals = [d for d in ((r.delay(self.ua), r.delay("*")) if r else ()) if d]
    return max(vals) if vals else None


def get_polite(self, url, max_age_days=None):
    """(body, meta, reason). reason is None on success, else 'robots', 'blocked:<code>', 'unreachable' or 'captcha'.
    One attempt only: a 403/429/captcha is recorded in self.blocks and the page is never retried around."""
    self.__dict__.setdefault("blocks", [])
    if not self.robots_ok(url):
        self.blocks.append((url, "robots"))
        return None, None, "robots"
    seen = []
    old_retries, old_log = self.retries, self.log
    self.retries, self.log = 0, (lambda *a: seen.append(" ".join(str(x) for x in a)))
    try:
        body, meta = self.get(url, max_age_days=max_age_days)
    finally:
        self.retries, self.log = old_retries, old_log
    if body is None:
        code = next((s.split("HTTP ")[1].split()[0] for s in seen if "HTTP " in s), None)
        reason = "blocked:%s" % code if code in ("403", "429", "401", "503") else ("unreachable" if code is None else "http:%s" % code)
        self.blocks.append((url, reason))
        return None, None, reason
    low = body[:6000].lower()
    if any(w in low for w in ("captcha", "access denied", "are you a robot", "unusual traffic")) and len(body) < 20000:
        self.blocks.append((url, "captcha"))
        return None, None, "captcha"
    return body, meta, None


Fetcher._robots, Fetcher.robots_ok, Fetcher.crawl_delay, Fetcher.get_polite = _robots, robots_ok, crawl_delay, get_polite
