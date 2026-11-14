"""Text layer of `kbpipe reviews`: Autocar aspect notes and CarWale owner themes.

Roles (config llm.reviews_write / llm.reviews_check):
  writer  claude_sonnet (subscription). One call per model for Autocar (all aspects at once); CarWale reviews in chunks.
  checker the free Gemini then Groq chain. One call per model per source carrying every claim of that model.
The two chains must not share a backend or a model; the checker chain never falls back to the writer. If a chain runs out
(Sonnet subscription limit, or all free checker quota) the run raises TextStop and stops text cleanly: everything already
obtained is in the disk cache, so a rerun resumes with zero repeated calls.

Disk cache: <cache_dir>/review_llm/<hash>.json, keyed by (role, KB model, source, hash of the page text sent, prompt version
[, hash of the claims for the checker]). An unchanged page therefore costs no LLM call on a rerun or on the later write run.
Every note and theme, kept or dropped, is appended to Engine.audit (written to text_audit.jsonl) with the claim, the checker's
verdict, the supporting line and the drop reason."""
import hashlib
import json
import math
import os
import re

from . import llm
from .sources import autocar_reviews as AC

PROMPT_V = {"ac_write": "ac-w5", "ac_check": "ac-c4", "cw_write": "cw-w4", "cw_check": "cw-c4", "num_check": "num-c2"}
THEMES = ["reliability", "service_cost", "service_experience", "real_world_mileage", "build_issues", "recurring_fault", "resale",
          "satisfaction"]
DIRECTIONS = ("positive", "negative", "mixed")


class TextStop(Exception):
    """A whole role is out (writer subscription limit or checker quota): text stops, the run goes on without more text."""
    def __init__(self, role, why):
        super().__init__("%s: %s" % (role, why))
        self.role, self.why = role, why


class TextFail(Exception):
    """One model's text could not be produced (bad reply, error); the next model is still tried."""


def _sha(*parts):
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8") if isinstance(p, str) else json.dumps(p, sort_keys=True, ensure_ascii=False).encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def _flat(s):
    return re.sub(r"\s+", " ", (s or "").replace("’", "'").replace("‘", "'").replace("“", '"')
                  .replace("”", '"').replace("–", "-").replace("—", "-")).strip().lower()


def in_text(needle, text):
    """Substring test that ignores case, runs of whitespace and curly quotes."""
    return bool(_flat(needle)) and _flat(needle) in _flat(text)


def words(s):
    return len((s or "").split())


def sampled(seed, model, source, fraction):
    """Deterministic: the same models are sampled on every run, so a later run finds their checks in the cache."""
    return int(_sha(seed, model, source)[:8], 16) / 0xFFFFFFFF < fraction


# ---------------------------------------------------------------- prompts
def autocar_write_prompt(blob, aspects, max_words, max_quote):
    return ("You read an Autocar India car review (TEXT below). It has 'We like' and 'We don't like' lists and, for some aspects, a paragraph under the aspect's name.\n"
            "For each aspect in the list that the TEXT actually speaks about, write ONE note for a car buyer in your own words, at most %d words "
            "(count them: longer notes are thrown away), saying what the reviewer found (praise or criticism, with the concrete point: for example the engine, ride, space, boot, equipment). "
            "Optionally add a verbatim quote (at most %d words) copied exactly from the TEXT.\n"
            "Rules: one aspect per note. Use only what the TEXT says: no outside facts, no inferences about what a fact 'means', no advice. Do not mention numeric scores. If the TEXT says nothing "
            "about an aspect (not even in the like / don't like lists), leave that aspect out.\nAspects: %s\n"
            'Reply with JSON only: {"notes":[{"aspect":"<aspect exactly as listed>","note":"...","quote":"<exact text or null>"}]}\n\nTEXT:\n%s'
            % (max_words - 5, max_quote, json.dumps(aspects), blob))


def autocar_check_prompt(blob, claims):
    body = "\n".join("CLAIM %s [%s]: %s" % (c["id"], c["aspect"], c["claim"]) for c in claims)
    return ("You check claims about an Autocar India car review against its text. EVIDENCE is the review text. For each CLAIM decide from the EVIDENCE alone "
            "(no outside knowledge) whether it supports the claim for that aspect. verdict is 'supported' only if EVERY part of the claim (each fact, figure and comparison) is stated in the EVIDENCE; if any part is missing or only implied, 'not_supported'. If supported, "
            "supporting_line is ONE sentence or phrase copied EXACTLY, character for character, from the EVIDENCE.\n"
            'Reply with JSON only: {"results":[{"id":"...","verdict":"supported","supporting_line":"..."}]}\n\nEVIDENCE:\n%s\n\n%s' % (blob, body))


def carwale_write_prompt(items, min_mentions, max_words):
    body = "\n".join("[%s] %s" % (i["id"], i["text"]) for i in items)
    return ("Below are %d owner reviews of one car model, each starting with its id in brackets. Find themes that owners raise repeatedly. Allowed themes: %s. "
            "For recurring_fault and build_issues give a short label (a few words, for example 'AC compressor failure'); otherwise label is null. "
            "direction is positive, negative or mixed. In review_ids list EVERY id whose text clearly raises the theme (do not guess). "
            "note: one sentence in your own words saying what owners report, at most %d words, no quotes, no advice to the reader, and no figures (kmpl, rupees) unless several reviews give similar ones. Only themes raised by at least %d different ids.\n"
            'Reply with JSON only: {"themes":[{"theme":"...","label":null,"direction":"negative","review_ids":["id1","id2","id3"],"note":"..."}]}\n\n%s'
            % (len(items), ", ".join(THEMES), max_words, min_mentions, body))


def carwale_check_prompt(reviews_text, claims):
    body = "\n".join("CLAIM %s: owners raise the theme '%s'%s, direction %s. Our summary: %s" % (
        c["id"], c["theme"], " (%s)" % c["label"] if c["label"] else "", c["direction"], c["note"] or "-") for c in claims)
    return ("You check claims about owner reviews against the reviews themselves. REVIEWS below are numbered by id. For each CLAIM, list EVERY review id from REVIEWS that "
            "clearly raises that theme in that direction (a review about something else does not count), with one short line (at most 20 words) copied EXACTLY, "
            "character for character, from that review. verdict is 'supported' if at least %d different reviews support the claim AND our summary does not state anything the reviews do not, else 'not_supported'. "
            "Use only the REVIEWS, no outside knowledge.\n"
            'Reply with JSON only: {"results":[{"id":"...","verdict":"supported","support":[{"review_id":"...","line":"..."}]}]}\n\nREVIEWS:\n%s\n\n%s'
            % (3, reviews_text, body))


def numbers_check_prompt(evidence, claims):
    body = "\n".join("CLAIM %s: aspect '%s' (the page may word it differently, e.g. Exterior for Design and Styling, Comfort for Comfort and Space) is %s" % (
        c["id"], c["label"], c["shown"]) for c in claims)
    return ("EVIDENCE is text from a car review page. For each CLAIM, decide whether the EVIDENCE shows that score for that aspect. Rounding to the "
            "claimed number of decimals is fine (4.6462 shows as 4.65 or 4.6). found is true or false; if true, line is ONE short piece copied EXACTLY, "
            "character for character, from the EVIDENCE that contains the number.\n"
            'Reply with JSON only: {"results":[{"id":"...","found":true,"line":"..."}]}\n\nEVIDENCE:\n%s\n\n%s' % (evidence, body))


def _cid(x):
    """Checker ids come back as '3', 'CLAIM 3' or 'C3'; the number is what matters."""
    m = re.findall(r"\d+", str(x))
    return m[-1] if m else str(x)


def _fmt(x):
    s = ("%g" % x) if isinstance(x, float) else str(x)
    return s


class Engine:
    def __init__(self, cfg, run_dir, writer=None, checker=None, log=None):
        self.cfg, self.rc = cfg, cfg["reviews"]
        self.writer = writer or llm.get(cfg, "reviews_write", run_dir)
        self.checker = checker or llm.get(cfg, "reviews_check", run_dir)
        self._independent()
        self.cache_dir = os.path.join(cfg["cache_dir"], "review_llm")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.log = log or (lambda *a: None)
        self.stats = {"writer_calls": 0, "checker_calls": 0, "writer_cache_hits": 0, "checker_cache_hits": 0}
        self.cap = self.rc["max_llm_calls"]
        self.audit, self.numbers, self.stopped = [], [], {}
        self.write_only = False        # warm the writer cache without asking the checker (nothing is kept; the checks run later)
        self.run_dir = run_dir

    def _independent(self):
        def ids(ch):
            return {(b.name, b.model) for b in getattr(ch, "backends", [])}
        w, c = ids(self.writer), ids(self.checker)
        if {n for n, _ in w} & {n for n, _ in c} or {m for _, m in w} & {m for _, m in c}:
            raise ValueError("writer and checker must be different backends and models (writer %s, checker %s)" % (sorted(w), sorted(c)))
        for _, m in w | c:
            if "haiku" in (m or "").lower():
                raise ValueError("Haiku is not used in the review layers")

    # ---------------------------------------------------------------- cache + calls
    def _cpath(self, key):
        return os.path.join(self.cache_dir, key + ".json")

    def _call(self, role, key_parts, prompt, label):
        """-> (data, model_name, from_cache). Raises TextStop when the role's quota is out, TextFail for a bad reply."""
        key = _sha(role, *key_parts)
        p = self._cpath(key)
        if os.path.exists(p):
            with open(p) as f:
                rec = json.load(f)
            self.stats[role + "_cache_hits"] += 1
            return rec["response"], rec["model"], True
        if self.stopped.get(role):
            raise TextStop(role, self.stopped[role])
        if self.stats["writer_calls"] + self.stats["checker_calls"] >= self.cap:
            raise TextStop(role, "run LLM call cap (%d) reached" % self.cap)
        chain = self.writer if role == "writer" else self.checker
        try:
            text = chain.complete(prompt, json_mode=True, label=label)
        except llm.QuotaExhausted as e:
            self.stopped[role] = str(e)[:200]
            raise TextStop(role, str(e)[:200])
        except llm.LLMError as e:
            raise TextFail("%s call failed: %s" % (role, str(e)[:200]))
        self.stats[role + "_calls"] += 1
        model = ("%s:%s" % (chain.calls[-1]["backend"], chain.calls[-1]["model"])) if chain.calls else chain.model
        try:
            data = llm.parse_json(text)
        except ValueError as e:
            raise TextFail("%s reply was not JSON (%s)" % (role, e))
        with open(p + ".tmp", "w") as f:
            json.dump({"role": role, "label": label, "key": list(map(str, key_parts))[:4], "model": model, "response": data}, f, ensure_ascii=False)
        os.replace(p + ".tmp", p)
        return data, model, False

    def _log(self, rec):
        self.audit.append(rec)

    # ---------------------------------------------------------------- Autocar notes
    def autocar_notes(self, key, parsed, verify, flags_add):
        """-> (notes {aspect: {note, quote, _method}}, info). Every candidate is audited; unsupported ones are dropped."""
        rc = self.rc
        blob = AC.text_blob(parsed)
        info = {"kept": 0, "dropped": 0, "checked": 0, "supported": 0, "writer_model": None, "checker_model": None, "status": "ok", "unchecked": 0}
        base = {"source": "autocar", "model": key, "kind": "note"}
        if not blob.strip():
            info["status"] = "no text on page"
            return {}, info
        chash = _sha(blob)
        data, info["writer_model"], _ = self._call("writer", ("autocar", key, chash, PROMPT_V["ac_write"]),
                                                    autocar_write_prompt(blob, AC.ASPECTS, rc["max_note_words"], rc["max_quote_words"]), "autocar_notes %s" % key)
        cand, seen = {}, set()
        for n in data.get("notes") or []:
            a, note, quote = n.get("aspect"), (n.get("note") or "").strip(), (n.get("quote") or None)
            rec = dict(base, aspect=a, claim=note, quote=quote, writer=info["writer_model"], checked=False, verdict=None, supporting_line=None,
                       kept=False, drop_reason=None)
            why = None
            if a not in AC.ASPECTS:
                why = "unknown aspect"
            elif not note:
                why = "empty note"
            elif words(note) > rc["max_note_words"]:
                why = "note over %d words (%d)" % (rc["max_note_words"], words(note))
            elif a in seen:
                why = "second note for the same aspect"
            if why:
                rec["drop_reason"] = why
                info["dropped"] += 1
                flags_add("autocar", "NOTE_DROPPED", "%s: %s" % (a, why))
                self._log(rec)
                continue
            seen.add(a)
            if quote and (words(quote) > rc["max_quote_words"] or not in_text(quote, blob)):
                rec["quote_dropped"] = "quote over %d words" % rc["max_quote_words"] if words(quote) > rc["max_quote_words"] else "quote is not an exact substring of the page text"
                flags_add("autocar", "QUOTE_DROPPED", "%s: %s" % (a, rec["quote_dropped"]))
                quote = None
            cand[a] = {"note": note, "quote": quote, "rec": rec}
        if self.write_only:
            for a, c in cand.items():
                c["rec"]["drop_reason"] = "not checked yet (write-only run)"
                self._log(c["rec"])
            info["status"], info["kept"] = "write-only: checks pending", 0
            return {}, info
        if verify and cand:
            claims = [{"id": str(i), "aspect": a, "claim": cand[a]["note"]} for i, a in enumerate(sorted(cand))]
            order = {c["id"]: c["aspect"] for c in claims}
            try:
                res, info["checker_model"], _ = self._call("checker", ("autocar", key, chash, PROMPT_V["ac_check"], claims),
                                                           autocar_check_prompt(blob, claims), "autocar_check %s" % key)
            except TextFail as e:
                info["status"] = "checker failed: %s" % e
                for a, c in cand.items():
                    c["rec"].update(drop_reason="checker failed (nothing kept unchecked)", checker=None)
                    self._log(c["rec"])
                    info["dropped"] += 1
                flags_add("autocar", "CHECK_FAILED", str(e))
                return {}, info
            got = {_cid(r.get("id")): r for r in res.get("results") or []}
            for cid, a in order.items():
                r, c = got.get(cid), cand[a]
                rec = c["rec"]
                rec["checked"], rec["checker"] = bool(r), info["checker_model"]
                if not r:
                    rec["drop_reason"], rec["verdict"] = "checker returned no verdict (not counted in the supported rate)", None
                else:
                    info["checked"] += 1
                    rec["verdict"], rec["supporting_line"] = r.get("verdict"), r.get("supporting_line")
                    line_ok = in_text(r.get("supporting_line"), blob)
                    rec["line_found_in_page_text"] = line_ok
                    if r.get("verdict") != "supported":
                        rec["drop_reason"] = "checker: not supported"
                    elif not line_ok:
                        rec["drop_reason"] = "supporting line is not a substring of the page text"
                    else:
                        info["supported"] += 1
                        rec["kept"] = True
                if not rec["kept"]:
                    info["dropped"] += 1
                    flags_add("autocar", "NOTE_DROPPED", "%s: %s" % (a, rec["drop_reason"]))
                self._log(rec)
        else:
            for a, c in cand.items():
                c["rec"]["kept"] = True
                c["rec"]["note_status"] = "not sampled for checking" if cand else None
                info["unchecked"] += 1
                self._log(c["rec"])
        notes = {a: {"note": c["note"], "quote": c["quote"]} for a, c in cand.items() if c["rec"]["kept"]}
        info["kept"] = len(notes)
        return notes, info

    # ---------------------------------------------------------------- owner themes
    def _groups(self, cand, byid):
        """Claims grouped so one checker call stays within carwale_check_max_chars of review text (the free checker has a
        per-request token limit). Normally one group per model; a group of one is the minimum."""
        cap, groups, cur, cur_ids = self.rc.get("carwale_check_max_chars", 9000), [], [], set()
        for n, c in enumerate(cand):
            ids = set(c["ids"])
            size = sum(len(byid[i]["text"]) + 8 for i in cur_ids | ids)
            if cur and size > cap:
                groups.append(cur)
                cur, cur_ids = [], set()
            cur.append(n)
            cur_ids |= ids
        if cur:
            groups.append(cur)
        return groups

    def _chunks(self, items):
        n = max(5, self.rc.get("carwale_chunk_size", 60))
        return [items[i:i + n] for i in range(0, len(items), n)]

    def themes(self, key, source_tag, items, kind, verify, flags_add):
        """items: [{id, text}] (already capped, newest first). -> (themes [{theme,label,direction,mentions,note,ids}], info)."""
        rc = self.rc
        info = {"kept": 0, "dropped": 0, "checked": 0, "supported": 0, "sampled": len(items), "writer_model": None, "checker_model": None,
                "status": "ok", "unchecked": 0, "writer_chunks": 0}
        base = {"source": source_tag, "model": key, "kind": "theme"}
        if len(items) < rc["min_reviews_sampled"]:
            info["status"] = "only %d %s sampled (minimum %d)" % (len(items), kind, rc["min_reviews_sampled"])
            flags_add(source_tag, "THEMES_SKIPPED", info["status"])
            return [], info
        byid = {str(i["id"]): i for i in items}
        merged = {}
        for ch in self._chunks(items):
            chash = _sha([(i["id"], i["text"]) for i in ch])
            data, info["writer_model"], _ = self._call("writer", (source_tag, key, chash, PROMPT_V["cw_write"]),
                                                       carwale_write_prompt(ch, rc["min_theme_mentions"], rc["max_note_words"]), "%s_themes %s" % (source_tag, key))
            info["writer_chunks"] += 1
            chunk_ids = {str(i["id"]) for i in ch}
            for t in data.get("themes") or []:
                th, label = t.get("theme"), (t.get("label") or None)
                ids = {str(x) for x in (t.get("review_ids") or []) if str(x) in chunk_ids}
                m = merged.setdefault((th, label), {"theme": th, "label": label, "dirs": set(), "ids": set(), "notes": [], "invalid_dir": None})
                m["ids"] |= ids
                if t.get("direction") in DIRECTIONS:
                    m["dirs"].add(t.get("direction"))
                else:
                    m["invalid_dir"] = t.get("direction")
                m["notes"].append(((t.get("note") or "").strip() or None, len(ids)))
        cand = []
        for (th, label), m in merged.items():
            ids = sorted(m["ids"])
            direction = next(iter(m["dirs"])) if len(m["dirs"]) == 1 else ("mixed" if m["dirs"] else m["invalid_dir"])
            note = max(m["notes"], key=lambda x: x[1])[0] if m["notes"] else None
            rec = dict(base, theme=th, label=label, direction=direction, claim=note, writer_count=len(ids), writer=info["writer_model"], checked=False,
                       verdict=None, support=None, confirmed=None, kept=False, drop_reason=None, writer_ids=ids)
            why = None
            if th not in THEMES:
                why = "theme %r not allowed" % th
            elif direction not in DIRECTIONS:
                why = "direction %r not allowed" % direction
            elif th == "recurring_fault" and not label:
                why = "recurring_fault without a label"
            elif len(ids) < rc["min_theme_mentions"]:
                why = "below minimum mentions (%d of %d needed)" % (len(ids), rc["min_theme_mentions"])
            elif note and words(note) > rc["max_note_words"]:
                why = "note over %d words (%d)" % (rc["max_note_words"], words(note))
            if why:
                rec["drop_reason"] = why
                info["dropped"] += 1
                flags_add(source_tag, "THEME_DROPPED", "%s %s" % (th, why))
                self._log(rec)
                continue
            cand.append({"theme": th, "label": label, "direction": direction, "note": note, "ids": ids, "mentions": len(ids), "rec": rec})
        if self.write_only:
            for c in cand:
                c["rec"]["drop_reason"] = "not checked yet (write-only run)"
                self._log(c["rec"])
            info["status"], info["kept"] = "write-only: checks pending", 0
            return [], info
        if verify and cand:
            res_by, why_failed = {}, None
            for grp in self._groups(cand, byid):
                used = sorted({i for n in grp for i in cand[n]["ids"]})
                text = "\n".join("[%s] %s" % (i, byid[i]["text"]) for i in used)
                claims = [{"id": str(k), "theme": cand[n]["theme"], "label": cand[n]["label"], "direction": cand[n]["direction"], "note": cand[n]["note"]}
                          for k, n in enumerate(grp)]
                try:
                    res, info["checker_model"], _ = self._call("checker", (source_tag, key, _sha(text), PROMPT_V["cw_check"], claims),
                                                               carwale_check_prompt(text, claims), "%s_check %s" % (source_tag, key))
                except TextFail as e:
                    why_failed = e
                    continue
                for r in res.get("results") or []:
                    k = _cid(r.get("id"))
                    if k.isdigit() and int(k) < len(grp):
                        res_by[grp[int(k)]] = r
            if why_failed and not res_by:
                info["status"] = "checker failed: %s" % why_failed
                for c in cand:
                    c["rec"]["drop_reason"] = "checker failed (nothing kept unchecked)"
                    self._log(c["rec"])
                    info["dropped"] += 1
                flags_add(source_tag, "CHECK_FAILED", str(why_failed))
                return [], info
            got = {str(n): r for n, r in res_by.items()}
            for n, c in enumerate(cand):
                rec, r = c["rec"], got.get(str(n))
                rec["checked"], rec["checker"] = bool(r), info["checker_model"]
                info["checked"] += 1 if r else 0
                good = []
                if r:
                    rec["verdict"] = r.get("verdict")
                    for s in r.get("support") or []:
                        rid = str(s.get("review_id"))
                        if rid in c["ids"] and rid in byid and in_text(s.get("line"), byid[rid]["text"]) and rid not in [g[0] for g in good]:
                            good.append((rid, s.get("line")))
                    rec["support"] = [{"review_id": a, "line": b} for a, b in good][:8]
                rec["confirmed"] = len(good)
                if not r:
                    rec["drop_reason"] = "checker returned no verdict (not counted in the supported rate)"
                elif r.get("verdict") != "supported":
                    rec["drop_reason"] = "checker: not supported"
                elif len(good) < rc["min_theme_mentions"]:
                    rec["drop_reason"] = "unsupported: only %d distinct reviews with a line found in the review text (minimum %d)" % (len(good), rc["min_theme_mentions"])
                else:
                    info["supported"] += 1
                    rec["kept"] = True
                    c["ids"] = [g[0] for g in good]          # the mentions we store are the ones the checker confirmed, line and all
                    c["mentions"] = len(good)
                if not rec["kept"]:
                    info["dropped"] += 1
                    flags_add(source_tag, "THEME_DROPPED", "%s: %s" % (c["theme"], rec["drop_reason"]))
                self._log(rec)
        else:
            for c in cand:
                c["rec"]["kept"] = True
                c["rec"]["note_status"] = "not sampled for checking"
                info["unchecked"] += 1
                self._log(c["rec"])
        kept = [c for c in cand if c["rec"]["kept"]]
        info["kept"] = len(kept)
        return kept, info

    # ---------------------------------------------------------------- numbers re-check (plan section 5)
    def check_numbers(self, source, key, evidence, scores, flags_add):
        """scores: [(label, stored_value, shown_text, tolerance)]. The checker must find each on the page text, with a line that
        is a substring of it and carries a number within the tolerance. -> (n_ok, n_total)."""
        if self.write_only:
            return 0, 0
        claims = [{"id": str(i), "label": l, "shown": shown, "value": v, "tol": tol} for i, (l, v, shown, tol) in enumerate(scores)]
        try:
            res, model, _ = self._call("checker", (source, key, _sha(evidence), PROMPT_V["num_check"], [(c["label"], c["shown"]) for c in claims]),
                                       numbers_check_prompt(evidence, claims), "%s_numbers %s" % (source, key))
        except TextFail as e:
            flags_add(source, "NUMBERS_CHECK_FAILED", str(e))
            return 0, 0
        got = {_cid(r.get("id")): r for r in res.get("results") or []}
        ok = 0
        for c in claims:
            r = got.get(c["id"]) or {}
            line = r.get("line")
            nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", line or "")]
            hit = bool(r.get("found")) and in_text(line, evidence) and any(abs(n - c["value"]) <= c["tol"] for n in nums)
            ok += hit
            self.numbers.append({"source": source, "model": key, "aspect": c["label"], "stored": c["value"], "found": bool(r.get("found")),
                                 "line": line, "line_in_page_text": in_text(line, evidence), "confirmed": hit, "checker": model})
            if not hit:
                flags_add(source, "NUMBER_NOT_CONFIRMED", "%s=%s" % (c["label"], c["value"]))
        return ok, len(claims)
