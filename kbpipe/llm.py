"""One adapter for every LLM call (brochure extraction and verification). Backends are chosen in config:
  gemini      Google Generative Language REST API (free tier works; key in GEMINI_API_KEY)
  openai      any OpenAI-compatible endpoint, e.g. Groq (key in GROQ_API_KEY) or a local server
  ollama      local models through Ollama
  claude_cli  the `claude -p` command (optional; not free)
  mock        tests
Keys come from environment variables only. Every call is logged (backend, model, tokens when reported, seconds)."""
import base64
import json
import os
import subprocess
import time
import urllib.error
import urllib.request


class LLMError(Exception):
    pass


class QuotaExhausted(LLMError):
    pass


class Backend:
    def __init__(self, name, spec, calls_log=None, state_path=None):
        self.name, self.spec = name, spec
        self.kind, self.model = spec["kind"], spec.get("model", "")
        self.gap = 60.0 / max(1, spec.get("rpm", 10))
        self.daily = spec.get("daily_calls", 10 ** 9)
        self._last = 0.0
        self.calls = []
        self.calls_log = calls_log
        self.state_path = state_path
        self.mock = None

    # daily budget is kept per backend per UTC day so a rerun the same day does not overshoot a free tier
    def _used_today(self, add=0):
        if not self.state_path:
            return 0
        day = time.strftime("%Y-%m-%d", time.gmtime())
        st = {}
        if os.path.exists(self.state_path):
            with open(self.state_path) as f:
                st = json.load(f)
        key = "%s/%s" % (self.name, day)
        st[key] = st.get(key, 0) + add
        if add:
            with open(self.state_path, "w") as f:
                json.dump(st, f)
        return st[key]

    def _post(self, url, body, headers):
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=dict(headers, **{"Content-Type": "application/json", "User-Agent": "kbpipe/1.0"}))
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode())

    def complete(self, prompt, images=None, json_mode=True, label=""):
        """Return the model's text. images: list of PNG file paths."""
        if self.kind == "mock":
            return self.mock(prompt, images) if self.mock else "{}"
        if self._used_today() >= self.daily:
            raise QuotaExhausted("%s: daily call budget (%d) reached" % (self.name, self.daily))
        last_err = None
        for attempt in range(5):
            wait = self.gap - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.time()
            t0 = time.time()
            try:
                text, usage = self._call(prompt, images or [], json_mode)
                rec = {"backend": self.name, "model": self.model, "label": label, "seconds": round(time.time() - t0, 2),
                       "tokens_in": usage.get("in"), "tokens_out": usage.get("out"), "ok": True}
                self.calls.append(rec)
                self._used_today(1)
                if self.calls_log:
                    with open(self.calls_log, "a") as f:
                        f.write(json.dumps(rec) + "\n")
                return text
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")[:400]
                last_err = "HTTP %s %s" % (e.code, body)
                if e.code == 429:
                    if "per day" in body.lower() or "daily" in body.lower() or "PerDay" in body:
                        raise QuotaExhausted("%s: %s" % (self.name, last_err))
                    ra = e.headers.get("Retry-After")
                    time.sleep(min(90, float(ra) if ra and ra.replace(".", "").isdigit() else 20 * (attempt + 1)))
                elif e.code in (500, 502, 503, 504):
                    time.sleep(10 * (attempt + 1))
                else:
                    break
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last_err = "%s" % e
                time.sleep(10 * (attempt + 1))
        raise LLMError("%s failed: %s" % (self.name, last_err))

    def _call(self, prompt, images, json_mode):
        s = self.spec
        if self.kind == "gemini":
            key = os.environ.get(s.get("key_env", "GEMINI_API_KEY"))
            if not key:
                raise LLMError("environment variable %s is not set" % s.get("key_env"))
            parts = [{"text": prompt}]
            for p in images:
                with open(p, "rb") as f:
                    parts.append({"inline_data": {"mime_type": "image/png", "data": base64.b64encode(f.read()).decode()}})
            cfg = {"temperature": 0}
            if json_mode:
                cfg["responseMimeType"] = "application/json"
            out = self._post("https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % self.model,
                             {"contents": [{"parts": parts}], "generationConfig": cfg}, {"x-goog-api-key": key})
            try:
                text = "".join(p.get("text", "") for p in out["candidates"][0]["content"]["parts"])
            except (KeyError, IndexError):
                raise LLMError("gemini returned no text: %s" % json.dumps(out)[:300])
            u = out.get("usageMetadata", {})
            return text, {"in": u.get("promptTokenCount"), "out": u.get("candidatesTokenCount")}
        if self.kind == "openai":
            key = os.environ.get(s.get("key_env", ""), "")
            content = [{"type": "text", "text": prompt}]
            for p in images:
                with open(p, "rb") as f:
                    content.append({"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(f.read()).decode()}})
            body = {"model": self.model, "temperature": 0, "messages": [{"role": "user", "content": content if images else prompt}]}
            if json_mode:
                body["response_format"] = {"type": "json_object"}
            out = self._post(s["base_url"].rstrip("/") + "/chat/completions", body, {"Authorization": "Bearer " + key})
            u = out.get("usage", {})
            return out["choices"][0]["message"]["content"], {"in": u.get("prompt_tokens"), "out": u.get("completion_tokens")}
        if self.kind == "ollama":
            body = {"model": self.model, "prompt": prompt, "stream": False, "options": {"temperature": 0}}
            if json_mode:
                body["format"] = "json"
            if images:
                body["images"] = [base64.b64encode(open(p, "rb").read()).decode() for p in images]
            out = self._post(s["base_url"].rstrip("/") + "/api/generate", body, {})
            return out.get("response", ""), {"in": out.get("prompt_eval_count"), "out": out.get("eval_count")}
        if self.kind == "claude_cli":
            if images:
                prompt += "\nRead these image files first: " + ", ".join(images)
            r = subprocess.run(["claude", "-p", prompt, "--model", self.model, "--output-format", "json", "--tools", "Read",
                                "--no-session-persistence"], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=900)
            if r.returncode != 0:
                raise LLMError("claude cli: %s" % r.stderr[:300])
            out = json.loads(r.stdout)
            return out.get("result", ""), {"in": None, "out": None}
        raise LLMError("unknown backend kind %r" % self.kind)


class Chain:
    """Backends tried in order. A backend that runs out of quota or fails is skipped for the rest of the run."""
    def __init__(self, backends):
        self.backends, self.dead = backends, set()

    @property
    def name(self):
        live = [b for b in self.backends if b.name not in self.dead]
        return live[0].name if live else "none"

    @property
    def model(self):
        live = [b for b in self.backends if b.name not in self.dead]
        return live[0].model if live else "none"

    @property
    def calls(self):
        return [c for b in self.backends for c in b.calls]

    def complete(self, prompt, images=None, json_mode=True, label=""):
        err = None
        for b in self.backends:
            if b.name in self.dead:
                continue
            try:
                return b.complete(prompt, images=images, json_mode=json_mode, label=label)
            except QuotaExhausted as e:
                self.dead.add(b.name)
                err = e
            except LLMError as e:
                err = e
        if all(b.name in self.dead for b in self.backends):
            raise QuotaExhausted("every backend for this role is out of quota: %s" % err)
        raise LLMError(str(err))


def get(cfg, role, run_dir=None):
    """Backend chain for a role: 'extract', 'verify' or 'verify_image'."""
    names = cfg["llm"][role]
    names = [names] if isinstance(names, str) else names
    os.makedirs(cfg["cache_dir"], exist_ok=True)
    return Chain([Backend(n, cfg["llm"]["backends"][n], calls_log=os.path.join(run_dir, "llm_calls.jsonl") if run_dir else None,
                          state_path=os.path.join(cfg["cache_dir"], "llm_budget.json")) for n in names])


def parse_json(text):
    """Tolerant JSON read: strips code fences and leading prose."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        t = t.rsplit("```", 1)[0]
    i, j = t.find("{"), t.rfind("}")
    if i < 0 or j < 0:
        raise ValueError("no JSON object in the reply")
    return json.loads(t[i:j + 1])
