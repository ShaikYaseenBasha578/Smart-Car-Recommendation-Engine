"""Stage 4, verification. Independent of extraction by construction:
  * this module imports nothing from extract.py, plan.py, reconcile.py or the source adapters' field mappings;
  * the verifier model gets ONLY: the field's definition, the KB value, and the source's own content
    (fetched again here). It never sees how the value was extracted, by what, or why it was accepted;
  * results are appended once to verify/results.jsonl, the file is made read-only at the end of the run, and
    every accuracy number in the report is computed from that file alone (see `summarise`).

Verdicts: match · mismatch · unreachable (the source could not be fetched or no longer shows this variant) ·
          verifier_error (no usable reply, or the quoted evidence is not in the source text).
Accuracy = match / (match + mismatch). The other two are reported beside it, never folded in."""
import html
import json
import os
import random
import re
import stat

from . import fields as F
from . import llm

PROMPT = """You are checking one fact in a car database against its source. Use ONLY the source content below.

Car: {car}
Field: {field}
Definition: {definition}
Database value: {value}

SOURCE ({kind}; {url}):
{content}

Decide whether the source supports the database value for this exact car variant.
- "match": the source states this value (same number after unit conversion or rounding to the source's precision; for a 0/1 field, 1 means the source shows it fitted, 0 means the source shows it absent or "No").
- "mismatch": the source states a different value, or shows the opposite for a 0/1 field.
- "not_found": the source says nothing about this field for this variant.
Reply with one JSON object and nothing else:
{{"verdict": "match|mismatch|not_found", "source_value": "<what the source says, or empty>", "evidence": "<one line copied exactly from the source content, or empty>"}}"""


# ---------- independent source readers (generic JSON walkers; no field mapping) ----------
def _json_blobs(page):
    m = re.search(r'<script[^>]*id="initial-state"[^>]*>(.*?)</script>', page, re.S)
    if m:
        try:
            yield json.loads(html.unescape(m.group(1)))
        except ValueError:
            pass
    i = page.find("window.__INITIAL_STATE__")
    if i >= 0:
        j = page.find("{", i)
        try:
            yield json.JSONDecoder().raw_decode(page[j:])[0]
        except ValueError:
            pass


def _find(o, pred):
    if isinstance(o, dict):
        if pred(o):
            yield o
        for v in o.values():
            for x in _find(v, pred):
                yield x
    elif isinstance(o, list):
        for v in o:
            for x in _find(v, pred):
                yield x


def _lines(o, out, depth=0):
    """Flatten label/value items and scalar leaves into 'label: value' lines."""
    if isinstance(o, dict):
        label = o.get("itemName") or o.get("text")
        if label is not None and "value" in o and not isinstance(o["value"], (dict, list)):
            unit = o.get("unitType") or ""
            out.append("%s: %s %s" % (str(label).strip(), html.unescape(str(o["value"])).strip(), unit))
            return
        for k, v in o.items():
            if isinstance(v, (dict, list)):
                _lines(v, out, depth + 1)
            elif v not in (None, "", False, 0) and depth <= 2 and re.search(r"name|price|fuel|status|title|mileage", k, re.I):
                out.append("%s: %s" % (k, v))
    elif isinstance(o, list):
        for v in o:
            _lines(v, out, depth + 1)


_MEMO = {}   # url -> page, for the life of one process: the verifier downloads each source once per run, itself


def read_web_source(url, fetcher):
    """(content_text, problem). Fetches the page again (not the extractor's cached copy; once per run) and returns only
    the part for this variant."""
    base, _, frag = url.partition("#")
    if base not in _MEMO:
        _MEMO[base] = fetcher.get(base, max_age_days=0)[0]
    page = _MEMO[base]
    if not page:
        return None, "fetch failed"
    out = []
    for blob in _json_blobs(page):
        if frag.startswith("vid="):
            vid = frag[4:]
            hits = [d for d in _find(blob, lambda d: str(d.get("versionId")) == vid and ("specsSummary" in d or "featureSpecs" in d))]
            if not hits:
                return None, "the page no longer lists version %s" % vid
            _lines(hits[0], out)
        else:
            for key in ("specsTechnicalJson", "overView", "selectedVariant"):
                for d in _find(blob, lambda d, key=key: key in d):
                    v = d[key]
                    if isinstance(v, str):
                        out.append("%s: %s" % (key, v))
                    else:
                        _lines(v, out)
                    break
        if out:
            break
    seen, uniq = set(), []
    for l in out:
        l = re.sub(r"\s+", " ", l).strip()
        if l and l not in seen and len(l) < 300:
            seen.add(l)
            uniq.append(l)
    if len(uniq) < 5:
        return None, "no structured content found on the page"
    return "\n".join(uniq), None


def read_brochure_source(payload, cfg):
    """(page_text, [png paths], problem) for a brochure observation: the cited page, rendered here."""
    try:
        import fitz
    except ImportError:
        return None, [], "PyMuPDF is not installed"
    rel = payload.get("pdf_path") or ""
    cands = [rel, os.path.join(os.path.dirname(os.path.dirname(cfg["oem_dir"])), "..", rel),
             os.path.join(cfg["oem_dir"], rel.split("sources/oem/")[-1]),
             os.path.join(cfg["oem_new_dir"], rel.split("sources/oem_kbpipe/")[-1])]
    path = next((p for p in cands if p and os.path.exists(p)), None)
    if not path:
        return None, [], "brochure file not found: %s" % rel
    try:
        page_no = int(str(payload.get("page")).split(",")[0].split("-")[0].strip().lstrip("p"))
    except (TypeError, ValueError):
        return None, [], "no usable page number: %r" % payload.get("page")
    doc = fitz.open(path)
    if not (1 <= page_no <= doc.page_count):
        return None, [], "page %s is outside the PDF (%d pages)" % (page_no, doc.page_count)
    pg = doc[page_no - 1]
    text = pg.get_text()
    d = os.path.join(cfg["cache_dir"], "verify_pages")
    os.makedirs(d, exist_ok=True)
    png = os.path.join(d, "%s_p%d.png" % (re.sub(r"[^A-Za-z0-9]+", "_", os.path.basename(path)), page_no))
    if not os.path.exists(png):
        pg.get_pixmap(dpi=110).save(png)
    return text, [png], None


# ---------- sampling ----------
def source_class(method, source_name):
    if source_name == "oem":
        return "brochure"
    if source_name == "v6_migration":
        return "legacy"
    return "aggregator"


def population(conn, only_run_methods=False, variant_ids=None):
    """Every live, accepted cell with its accepted evidence: one dict per (variant, field)."""
    q = ("select p.variant_id, p.field_name, p.accepted_value, p.id pid, o.id oid, o.source_url, o.extraction_method, "
         "o.raw_payload, o.raw_name, s.name source, v.full_name, v.name vname, m.name model, mk.name make "
         "from field_provenance p join source_observation o on o.id=p.source_observation_id join source s on s.id=o.source_id "
         "join variant v on v.id=p.variant_id join model m on m.id=v.model_id join manufacturer mk on mk.id=m.manufacturer_id "
         "where p.decision='accepted' and v.base_variant_id is null "
         "and not exists (select 1 from v_active_quarantine q where q.target_table='field_provenance' and q.target_id=p.id) "
         "and not exists (select 1 from v_active_quarantine q where q.target_table='source_observation' and q.target_id=o.id) "
         "order by p.id")
    best = {}
    rank = {"brochure": 3, "aggregator": 2, "legacy": 1}
    for r in conn.execute(q):
        f = r["field_name"]
        if f not in F.FIELDS:
            continue
        if variant_ids is not None and r["variant_id"] not in variant_ids:
            continue
        if only_run_methods and not str(r["extraction_method"] or "").startswith("kbpipe"):
            continue
        cls = source_class(r["extraction_method"], r["source"])
        key = (r["variant_id"], f)
        if key not in best or (rank[cls], r["pid"]) > (rank[best[key]["cls"]], best[key]["pid"]):
            best[key] = dict(r, cls=cls)
    out = []
    for (vid, f), r in best.items():
        tbl = F.FIELDS[f][0]
        if tbl == "variant":
            cur = conn.execute('select "%s" from v_variant_canonical_q where id=?' % f, (vid,)).fetchone()[0]
        else:
            cur = conn.execute('select p."%s" from variant v join powertrain p on p.id=v.powertrain_id where v.id=?' % f, (vid,)).fetchone()
            cur = cur[0] if cur else None
        if F.norm(f, cur) is None:
            continue
        r["value"] = F.norm(f, cur)
        r["group"] = F.FIELDS[f][2]
        out.append(r)
    return out


def sample(pop, per_stratum, seed, exclude=()):
    """Stratified random sample: `per_stratum` cells from every (field group x source class) that has any."""
    rng = random.Random(seed)
    strata = {}
    for r in pop:
        if (r["variant_id"], r["field_name"]) in exclude:
            continue
        strata.setdefault((r["group"], r["cls"]), []).append(r)
    out = []
    for key in sorted(strata):
        rows = sorted(strata[key], key=lambda r: (r["variant_id"], r["field_name"]))
        rng.shuffle(rows)
        out += rows[:per_stratum]
    return out, {"%s/%s" % k: len(v) for k, v in strata.items()}


# ---------- the check ----------
def check_cell(cell, cfg, fetcher, backends, legacy_lookup=None):
    """One verdict dict. `backends`: {"text": Backend, "image": Backend}."""
    f = cell["field_name"]
    res = {"variant_id": cell["variant_id"], "car": cell["full_name"], "field": f, "group": cell["group"],
           "kb_value": cell["value"], "source_class": cell["cls"], "source": cell["source"], "source_ref": cell["source_url"],
           "verdict": None, "source_value": "", "evidence": "", "note": "", "verifier": None}
    images, kind = [], "structured data from the web page"
    if cell["cls"] == "brochure":
        try:
            payload = json.loads(cell["raw_payload"] or "{}")
        except ValueError:
            payload = {}
        content, images, problem = read_brochure_source(payload, cfg)
        res["source_ref"] = "%s p%s" % (payload.get("pdf_path"), payload.get("page"))
        kind = "text layer of the brochure page; the page image is attached and is the authority"
        be = backends["image"]
    elif cell["cls"] == "legacy":
        url = legacy_lookup(cell) if legacy_lookup else None
        if not url:
            res.update(verdict="unreachable", note="the KB records no URL for this value and no current page is linked to this variant")
            return res
        res["source_ref"] = url
        res["note"] = "no original URL on record; checked against the current page"
        content, problem = read_web_source(url, fetcher)
        be = backends["text"]
    else:
        content, problem = read_web_source(cell["source_url"], fetcher)
        be = backends["text"]
    if problem:
        res.update(verdict="unreachable", note=(res["note"] + "; " if res["note"] else "") + problem)
        return res
    res["verifier"] = "%s/%s" % (be.name, be.model)
    prompt = PROMPT.format(car=cell["full_name"], field=f, definition=F.DEFINITIONS[f], value=cell["value"], kind=kind,
                           url=res["source_ref"], content=(content or "")[:24000])
    try:
        reply = llm.parse_json(be.complete(prompt, images=images, label="verify"))
    except llm.QuotaExhausted:
        raise
    except Exception as e:
        res.update(verdict="verifier_error", note="no usable reply: %s" % str(e)[:160])
        return res
    v = str(reply.get("verdict", "")).strip().lower()
    res["source_value"] = str(reply.get("source_value", ""))[:200]
    res["evidence"] = str(reply.get("evidence", ""))[:300]
    if v not in ("match", "mismatch", "not_found"):
        res.update(verdict="verifier_error", note="unexpected verdict %r" % v)
    elif v == "not_found":
        res.update(verdict="unreachable", note=(res["note"] + "; " if res["note"] else "") + "the source does not state this field")
    else:
        ev = re.sub(r"\s+", " ", res["evidence"]).strip().lower()
        hay = re.sub(r"\s+", " ", content or "").lower()
        if not images and (not ev or ev not in hay):
            res.update(verdict="verifier_error", note="quoted evidence is not in the source text")
        else:
            res["verdict"] = v
    return res


def run(cells, cfg, fetcher, backends, out_dir, log, legacy_lookup=None, batch=""):
    """Verify cells and append to results.jsonl. Returns the verdict dicts written in this call."""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "results.jsonl")
    done = set()
    if os.path.exists(path):
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        with open(path) as f:
            for line in f:
                r = json.loads(line)
                done.add((r["variant_id"], r["field"]))
    out = []
    try:
        with open(path, "a") as f:
            for i, cell in enumerate(cells):
                if (cell["variant_id"], cell["field_name"]) in done:
                    continue
                r = check_cell(cell, cfg, fetcher, backends, legacy_lookup)
                r["batch"] = batch
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
                f.flush()
                out.append(r)
                if (i + 1) % 25 == 0:
                    log("verify", "%d of %d cells checked" % (i + 1, len(cells)))
    finally:
        os.chmod(path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    return out


def load(out_dir):
    path = os.path.join(out_dir, "results.jsonl")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


def summarise(rows):
    """Accuracy tables computed from verifier rows only."""
    def acc(rs):
        m = sum(r["verdict"] == "match" for r in rs)
        x = sum(r["verdict"] == "mismatch" for r in rs)
        return {"n": len(rs), "match": m, "mismatch": x, "unreachable": sum(r["verdict"] == "unreachable" for r in rs),
                "verifier_error": sum(r["verdict"] == "verifier_error" for r in rs),
                "accuracy": round(m / (m + x), 4) if (m + x) else None}
    out = {"overall": acc(rows), "by_group": {}, "by_source_class": {}, "by_group_and_class": {}}
    for g in F.GROUPS:
        rs = [r for r in rows if r["group"] == g]
        if rs:
            out["by_group"][g] = acc(rs)
    for c in ("brochure", "aggregator", "legacy"):
        rs = [r for r in rows if r["source_class"] == c]
        if rs:
            out["by_source_class"][c] = acc(rs)
            for g in F.GROUPS:
                r2 = [r for r in rs if r["group"] == g]
                if r2:
                    out["by_group_and_class"]["%s/%s" % (g, c)] = acc(r2)
    return out


# ---------- planted-error control: does the verifier actually catch wrong values? ----------
def _perturb(field, value):
    kind = F.FIELDS[field][1]
    if kind == "bool":
        return 1 - int(value)
    if field in ("airbags", "seating_capacity", "drive_modes"):
        return int(value) + 2
    if kind in ("int", "num"):
        v = float(value) * 1.08
        return int(round(v)) if kind == "int" else round(v, 1)
    pool = sorted({"transmission": F.TRANSMISSIONS, "drivetrain": F.DRIVETRAINS, "fuel_type": F.FUELS}.get(field, set()) - {value})
    swap = {"Manual": "CVT", "Petrol": "Diesel", "Diesel": "Petrol", "FWD": "RWD"}
    return swap.get(value) or (pool[0] if pool else None)


def planted(cells, verdicts, n, cfg, fetcher, backends, out_dir, log, legacy_lookup=None):
    """Re-check n cells the verifier called a match, each with a deliberately wrong value. Written to planted.jsonl.
    A good verifier answers mismatch every time. This never touches results.jsonl or the accuracy numbers."""
    ok = {(r["variant_id"], r["field"]) for r in verdicts if r["verdict"] == "match"}
    pool = sorted([c for c in cells if (c["variant_id"], c["field_name"]) in ok], key=lambda c: (str(c["variant_id"]), c["field_name"]))
    random.Random(cfg["seed"] + 7).shuffle(pool)
    path = os.path.join(out_dir, "planted.jsonl")
    out = []
    with open(path, "a") as f:
        for c in pool[:n]:
            wrong = _perturb(c["field_name"], c["value"])
            if wrong is None:
                continue
            r = check_cell(dict(c, value=wrong), cfg, fetcher, backends, legacy_lookup)
            r["true_value"], r["planted_value"] = c["value"], wrong
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            out.append(r)
    caught = sum(r["verdict"] == "mismatch" for r in out)
    judged = sum(r["verdict"] in ("match", "mismatch") for r in out)
    return {"planted": len(out), "judged": judged, "caught": caught, "missed": judged - caught}
