"""Brochure layer: for one model, find its OEM brochure, read the specification and feature pages with an LLM
(two independent reads that must agree) and attach the agreed values to the model's variants as OEM evidence.

Entry point: enrich(item, bundle, conn, cfg, fetcher, log, run_dir).  It appends to `version["brochure"]` on the
bundle's version dicts, as plan._cands() expects: [{"field", "value", "obs"}].  It never touches a database
(`conn` is a read-only connection) and never writes under sources/oem/.

Policy: P1 (value only from a brochure page, cited by file, page and SHA-1), P3 (no value from another model),
P4 (units), P7 (existing cells are not re-attached; the plan sends differences to review), P8 (editions skipped).
Order of work: locate -> index -> find pages (no LLM) -> read (LLM, x2) -> map columns to variants -> keep agreeing
cells -> attach.  Every LLM reply is cached, so a rerun costs no calls."""
import hashlib
import json
import os
import re
import shutil
import tempfile
import time
from datetime import datetime, timezone

from . import __version__, llm, match, plan
from . import fields as F
from . import reconcile as R
from .sources import common as c

HERE = os.path.dirname(os.path.abspath(__file__))
GLOSSARY = os.path.join(HERE, "brochure_glossary.md")
NEW_BASE = "https://stc.aeplcdn.com/"

DEFAULTS = {
    "enabled": True,
    "max_pages_per_brochure": 6,
    "max_page_reads_per_run": 400,       # LLM calls (each page is read twice)
    "reads_per_page": 2,
    "min_page_score": 5,
    "dpi": 140,
    "tile_w": 580, "tile_h": 650, "tile_overlap": 20,
    "index_dir": "~/carrec_kb_scratch/enrich_claude/index",
    "match_fraction": 0.5,               # wrong-year guard
    "check": True,                       # independent image check of every extracted cell (a different model than the reader)
    "check_fraction": 1.0,               # 1.0 = every cell; below 1: a fixed sample per (model, field group), see check_cells
    "check_chunk": 40,                   # claims per checker call
    "check_prompt_version": "bc1",
    "check_bar": 0.95,                   # sample mode: a field group whose sample is below this attaches nothing it did not check
    "max_consecutive_failures": 3,
}

# fields a brochure does not state (price) or that define a variant's identity (fuel, gearbox): never read from a brochure
SKIP_FIELDS = {"price_ex_showroom", "fuel_type", "transmission"}
BROCHURE_FIELDS = [f for f in F.FIELDS if f not in SKIP_FIELDS]

# expected printed unit(s) per field; a reply with another unit is dropped. Power and gearbox-free units are converted in code.
UNITS = {
    "engine_cc": {"cc"}, "torque_nm": {"nm"}, "power_bhp": {"bhp", "kw", "ps"},
    "length_mm": {"mm"}, "width_mm": {"mm"}, "height_mm": {"mm"}, "wheelbase_mm": {"mm"}, "ground_clearance_mm": {"mm"},
    "kerb_weight_kg": {"kg"}, "seating_capacity": {"count"}, "boot_space_litres": {"litres"}, "fuel_tank_litres": {"litres"},
    "mileage_arai_kmpl": {"km/l"}, "mileage_arai_km_per_kg": {"km/kg"}, "claimed_ev_range_km": {"km"},
    "airbags": {"count"}, "drive_modes": {"count"},
}

# a text-layer page that never mentions a field's words cannot show it; that field is left out of the prompt for the page
FIELD_KW = {
    "engine_cc": r"\bcc\b|displacement|capacity", "power_bhp": r"power|\bbhp\b|\bps\b|\bkw\b|\bhp\b",
    "torque_nm": r"torque|\bnm\b", "drivetrain": r"drive\s*train|\bfwd\b|\brwd\b|\bawd\b|\b4wd\b|\b4x4\b|\b4x2\b|2wd|wheel drive",
    "length_mm": r"length|dimension", "width_mm": r"width|dimension", "height_mm": r"height|dimension",
    "wheelbase_mm": r"wheel\s*base", "ground_clearance_mm": r"clearance", "kerb_weight_kg": r"kerb|curb|weight",
    "seating_capacity": r"seat|passenger", "boot_space_litres": r"boot|luggage|cargo",
    "fuel_tank_litres": r"tank|fuel\s+capacity", "mileage_arai_kmpl": r"km\s*/\s*l|kmpl|mileage|efficiency|arai",
    "mileage_arai_km_per_kg": r"km\s*/\s*kg|mileage|efficiency|arai", "claimed_ev_range_km": r"range|certified|\bkm\b",
    "airbags": r"air\s*bag", "abs": r"\babs\b|anti.?lock", "esc": r"\besc\b|\besp\b|\bvsm\b|\bvdc\b|stability",
    "hill_assist": r"hill|\bhac\b|\bhha\b|\bhsa\b|\bhhc\b", "tyre_pressure_monitoring_system": r"tpms|tyre pressure|tire pressure|pressure monitor",
    "rear_parking_sensors": r"sensor|parking", "rear_camera": r"camera", "camera_360": r"360|surround|around view|bird",
    "adas_available": r"adas|lane|collision|autonomous|assist", "automatic_climate_control": r"climate|\bfatc\b|air.?condition|\bac\b",
    "rear_ac_vents": r"rear\s+(ac|a/c|air|vent)|\bac\s+vent|\bvents?\b", "sunroof": r"sunroof|moonroof|panoramic",
    "ventilated_front_seats": r"ventilat|cooled\s+seat|seat\s+cool", "cruise_control": r"cruise|\bscc\b|\bacc\b",
    "paddle_shifters": r"paddle", "wireless_charging": r"wireless|charg|\bqi\b", "heads_up_display": r"head.?up|\bhud\b",
    "drive_modes": r"drive\s*mode|driving\s*mode|multi.?drive|\beco\b|\bsport\b", "connected_car_features": r"connect|telematics|bluelink|\bapp\b|remote",
    "android_auto": r"android|carplay", "apple_carplay": r"android|carplay",
}

# words that mark a specification or feature page
PAGE_KW = [("specification", 3), ("dimension", 2), ("wheelbase", 2), ("airbag", 2), ("kerb", 2), ("fuel tank", 2), ("boot", 2),
           ("ground clearance", 2), ("mileage", 2), ("arai", 2), ("km/l", 2), ("torque", 2), ("displacement", 2),
           ("feature", 1), ("sunroof", 1), ("cruise", 1), ("abs", 1), ("esc", 1), ("climate", 1), ("camera", 1),
           ("android", 1), ("carplay", 1), ("tyre", 1), ("seat", 1), ("variant", 1), ("trim", 1)]

ABSENCE_MARKER = re.compile(r"(^|[\s'\"(])[-–—x✗](?=$|[\s'\")])|dash|not available|not fitted|absent|cross", re.I)


# ---------------------------------------------------------------- small helpers
def bcfg(cfg):
    out = dict(DEFAULTS)
    out.update(cfg.get("brochure") or {})
    return out


def _utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha(path, algo):
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")


def kb_dir(cfg):
    """The repo's knowledge_base folder (the parent of sources/)."""
    return os.path.dirname(os.path.dirname(cfg["oem_dir"]))


def stored_path(cfg, abspath):
    """pdf_path as stored in the observation: relative to the repo root when the file is under knowledge_base, else absolute."""
    root = os.path.dirname(kb_dir(cfg))
    ap = os.path.abspath(abspath)
    return os.path.relpath(ap, root) if ap.startswith(kb_dir(cfg) + os.sep) else ap


def file_url(cfg, abspath, page):
    ap = os.path.abspath(abspath)
    rel = os.path.relpath(ap, kb_dir(cfg)) if ap.startswith(kb_dir(cfg) + os.sep) else ap
    return "file:%s#page=%d" % (rel, page)


# ---------------------------------------------------------------- session (budget, LLM chain, per-run results)
class Session:
    def __init__(self, cfg, run_dir, chain=None):
        self.cfg, self.run_dir = cfg, run_dir
        self.chain = chain
        self.calls = 0
        self.check_calls = 0
        self.check_hits = 0
        self.fails = 0                   # consecutive failed LLM calls (reader or checker); 3 stop the run
        self.exhausted = None
        self.models = {}
        self.checkers = {}
        self.check_chain = None          # tests inject a checker chain here; the reader-is-not-checker rule still applies


_SESSIONS = {}


def session(cfg, run_dir, chain=None, check_chain=None):
    s = _SESSIONS.get(run_dir)
    if s is None:
        s = _SESSIONS[run_dir] = Session(cfg, run_dir, chain)
    if chain is not None:
        s.chain = chain
    if check_chain is not None:
        s.check_chain = check_chain
    if s.chain is None:
        s.chain = llm.get(cfg, "brochure_read", run_dir)
    return s


# ---------------------------------------------------------------- 1. locate
def _load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def locate_disk(item, cfg, log):
    """Brochures already on disk for a KB model, from the OEM manifest. Returns [{path, sha1, url_base, source}]."""
    man = _load_json(os.path.join(cfg["oem_dir"], "brochure_manifest.json"), {})
    out = []
    for key, m in man.items():
        if m.get("model_id") != item.get("kb_model_id"):
            continue
        ap = os.path.join(os.path.dirname(kb_dir(cfg)), m["artifact_path"])
        if not os.path.exists(ap):
            log("brochure", "%s %s: manifest file missing: %s" % (item["make"], item["model"], m["artifact_path"]))
            continue
        if m.get("sha256") and _sha(ap, "sha256") != m["sha256"]:
            log("brochure", "%s %s: %s does not match the manifest SHA-256; not used" % (item["make"], item["model"], m["artifact_path"]))
            continue
        out.append({"path": ap, "sha1": _sha(ap, "sha1"), "origin": "disk", "url": m.get("direct_document_url") or m.get("source_url")})
    return out


def _text_of(path, limit=400):
    import fitz
    doc = fitz.open(path)
    try:
        return [doc[i].get_text() for i in range(min(doc.page_count, limit))]
    finally:
        doc.close()


def locate_new(item, bundle, cfg, fetcher, log):
    """Download the brochure CarWale links for a model that is not in the KB. Returns [] with a logged reason on any problem."""
    href = bundle.get("brochure")
    if not href:
        log("brochure", "%s %s: CarWale lists no brochure" % (item["make"], item["model"]))
        return []
    url = href if href.startswith("http") else NEW_BASE + href.lstrip("/")
    body, meta = fetcher.get(url, binary=True)
    if not body:
        log("brochure", "%s %s: brochure download failed: %s" % (item["make"], item["model"], url))
        return []
    if not body.startswith(b"%PDF"):
        log("brochure", "%s %s: %s is not a PDF" % (item["make"], item["model"], url))
        return []
    return store_new(item, url, body, meta, cfg, log)


def store_new(item, url, body, meta, cfg, log, key=None):
    """Save a downloaded brochure under oem_new_dir/<make>/<model>/<sha1>.pdf (never under sources/oem) and record URL, date and
    hashes in oem_new_dir/brochure_manifest.json. Refuses a file that is not a PDF with a text layer naming the model."""
    sha1 = hashlib.sha1(body).hexdigest()
    d = os.path.join(cfg["oem_new_dir"], _slug(item["make"]), _slug(item["model"]))
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, sha1 + ".pdf")
    if not os.path.exists(path):
        with open(path, "wb") as f:
            f.write(body)
    try:
        texts = _text_of(path)
    except Exception as e:                      # corrupt PDF
        log("brochure", "%s %s: PDF unreadable (%s)" % (item["make"], item["model"], type(e).__name__))
        return []
    flat = re.sub(r"[^a-z0-9]", "", " ".join(texts).lower())
    if not flat:
        log("brochure", "%s %s: PDF has no text layer, so the model name cannot be confirmed; skipped" % (item["make"], item["model"]))
        return []
    if re.sub(r"[^a-z0-9]", "", item["model"].lower()) not in flat:
        log("brochure", "%s %s: the PDF does not mention the model name; skipped (%s)" % (item["make"], item["model"], url))
        return []
    mp = os.path.join(cfg["oem_new_dir"], "brochure_manifest.json")
    man = _load_json(mp, {})
    man[key or "%s/%s" % (item["make"], item["model"])] = {
        "url": url, "sha1": sha1, "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body),
        "fetched_at": (meta or {}).get("fetched_at") or _utc(), "path": os.path.relpath(path, cfg["oem_new_dir"]),
        "pages": len(texts)}
    tmp = mp + ".tmp"
    with open(tmp, "w") as f:
        json.dump(man, f, indent=1, sort_keys=True)
    os.replace(tmp, mp)
    return [{"path": path, "sha1": sha1, "origin": "new", "url": url}]


def locate_new_dir(item, cfg, log):
    """Brochures already downloaded into the kbpipe folder (oem_new_dir manifest; keys 'Make/Model' or 'Make/Model|n').
    Used for models that are now in the KB but have no brochure in sources/oem."""
    man = _load_json(os.path.join(cfg["oem_new_dir"], "brochure_manifest.json"), {})
    out = []
    base = "%s/%s" % (item["make"], item["model"])
    for key in sorted(man):
        if key != base and not key.startswith(base + "|"):
            continue
        m = man[key]
        ap = os.path.join(cfg["oem_new_dir"], m["path"])
        if not os.path.exists(ap) or _sha(ap, "sha1") != m["sha1"]:
            log("brochure", "%s: %s missing or changed since download; not used" % (base, m["path"]))
            continue
        out.append({"path": ap, "sha1": m["sha1"], "origin": "new", "url": m["url"]})
    return out


# ---------------------------------------------------------------- 2. index
def page_texts(pdf, sha1, cfg):
    """Text per page (1-based list index 0 = page 1). Text layer by PyMuPDF; for an image-only page an OCR text from an
    existing index (<index_dir>/<sha1>/p<N>.ocr.txt) when present. No OCR is run here."""
    import fitz
    idx = os.path.join(os.path.expanduser(bcfg(cfg)["index_dir"]), sha1)
    doc = fitz.open(pdf)
    out = []
    try:
        for i in range(doc.page_count):
            t = doc[i].get_text()
            if len(t.strip()) < 50:
                for name in ("p%d.ocr.txt" % (i + 1), "p%d.txt" % (i + 1)):
                    p = os.path.join(idx, name)
                    if os.path.exists(p):
                        with open(p, errors="replace") as f:
                            t = f.read()
                        break
            out.append(t)
    finally:
        doc.close()
    return out


# ---------------------------------------------------------------- 3. find pages (no LLM)
def trim_words(variants, model):
    words = set()
    for v in variants:
        words |= set(c.trim_tokens(v["name"], model))
    return {w for w in words if len(w) > 1 or w.isdigit()}


def score_page(text, words):
    t = text.lower()
    if len(t.strip()) < 50:
        return 0
    toks = c.trim_tokens(text, "")
    hits = sum(1 for w in words if w in toks)
    kw = sum(wt for k, wt in PAGE_KW if k in t)
    return min(hits, 12) * 2 + kw


def find_pages(texts, variants, model, cap, min_score):
    words = trim_words(variants, model)
    scored = [(score_page(t, words), i + 1) for i, t in enumerate(texts)]
    keep = [(s, p) for s, p in scored if s >= min_score]
    keep.sort(key=lambda x: (-x[0], x[1]))
    chosen = [p for s, p in keep[:cap]]
    # image-only pages (no text layer, no OCR) cannot be scored; a short brochure whose tables are images would otherwise yield
    # no specification page. In a brochure of at most 12 pages, fill the remaining slots with them (at most 3), after every scored page.
    blind = [i + 1 for i, t in enumerate(texts) if len(t.strip()) < 50 and i > 0]
    if len(chosen) < cap and len(texts) <= 12:        # short brochures only
        chosen += blind[:min(3, cap - len(chosen))]
    return sorted(chosen), dict((p, s) for s, p in scored)


# ---------------------------------------------------------------- 4. read
def tiles(pdf, page_no, cfg, sha1):
    import fitz
    b = bcfg(cfg)
    d = os.path.join(cfg["cache_dir"], "brochure_tiles", "%s_p%d" % (sha1, page_no))
    ready = os.path.join(d, "done")
    if os.path.exists(ready):
        return sorted(os.path.join(d, f) for f in os.listdir(d) if f.endswith(".png"))
    os.makedirs(d, exist_ok=True)
    doc = fitz.open(pdf)
    out = []
    try:
        pg = doc[page_no - 1]
        w, h = pg.rect.width, pg.rect.height
        TW, TH, OV = b["tile_w"], b["tile_h"], b["tile_overlap"]
        xs = list(range(0, max(1, int(w)), TW - OV)) if w > TW else [0]
        ys = list(range(0, max(1, int(h)), TH - OV)) if h > TH else [0]
        n = 0
        for y in ys:
            if y and y + OV >= h:
                continue
            for x in xs:
                if x and x + OV >= w:
                    continue
                n += 1
                p = os.path.join(d, "tile%02d.png" % n)
                pg.get_pixmap(dpi=b["dpi"], clip=fitz.Rect(x, y, min(x + TW, w), min(y + TH, h))).save(p)
                out.append(p)
    finally:
        doc.close()
    open(ready, "w").close()
    return out


def glossary():
    with open(GLOSSARY) as f:
        return f.read()


PROMPT = """You are reading ONE page of an OEM car brochure for the {model}. Use ONLY the page image tiles given and the page text below. Never use knowledge of the car from anywhere else.

FIELD GLOSSARY (authoritative; follow it exactly)
{glossary}

TASK
Report every value this page states for any of the variants listed below, for the fields listed below. The brochure prints trim columns or trim names (for example "HTK+", "ZXi+ AT"); map each printed trim to the catalogue variants that it means, using each variant's fuel and gearbox to apply printed restrictions ("AT only", "Diesel only", "6MT"). A value shared by several variants is reported once with all of them in "variants". Use catalogue variant names EXACTLY as listed. Leave out any variant or field the page does not state: do not report null, do not guess, do not copy a value from another trim or engine. Report numbers as printed with their printed unit; do not convert units.

CATALOGUE VARIANTS (name | fuel | gearbox)
{variants}

FIELDS TO REPORT ON THIS PAGE (field: definition)
{fields}

PAGE TEXT (text layer, may be scrambled or incomplete; the image tiles are the authority when they differ)
{text}

The page image is given as tile files (overlapping tiles of the same page); read every one.

OUTPUT: reply with ONE JSON object and nothing else, no markdown fences:
{{"page_columns":["<every trim/variant column or row header the page's table prints, as printed>"],
 "cells":[{{"field":"<field name from the list>","value":<number, or a string for drivetrain>,"unit":"<bool|bhp|kW|PS|hp|Nm|kgm|cc|mm|kg|litres|km/l|km/kg|km|count|text>","qualifier":"<restriction printed with the value, e.g. 'AT only', or ''>","source":"<the exact header or line the value comes from>","variants":["<catalogue variant name>", "..."]}}]}}
Features: value 1 when the page shows the feature fitted on those variants, 0 only when the page shows it absent for them. Read number {read}.
"""


def build_prompt(model, variants, fields, text, read_no):
    vs = list(variants)
    fs = list(fields)
    if read_no % 2 == 0:                  # the second read sees the lists in another order: a more independent read
        vs.reverse()
        fs.reverse()
    vtxt = "\n".join("%s | %s | %s" % (v["name"], v.get("fuel") or "?", v.get("transmission") or "?") for v in vs)
    ftxt = "\n".join("%s: %s" % (f, F.DEFINITIONS[f]) for f in fs)
    return PROMPT.format(model=model, glossary=glossary(), variants=vtxt, fields=ftxt, text=(text or "")[:14000], read=read_no)


def cache_key(sha1, page, fields, variants, model_name, read_no):
    h = hashlib.sha256(json.dumps([sorted(fields), sorted(v["name"] for v in variants)]).encode()).hexdigest()[:16]
    return "%s_p%d_%s_%s_r%d" % (sha1, page, h, _slug(model_name) or "model", read_no)


def read_page(S, pdf, sha1, page, text, model, variants, fields, log, read_no):
    """One LLM read of one page: parsed reply dict, or None when it could not be had. Counts against the budget unless cached."""
    b = bcfg(S.cfg)
    cdir = os.path.join(S.cfg["cache_dir"], "brochure_reads")
    os.makedirs(cdir, exist_ok=True)
    key = cache_key(sha1, page, fields, variants, "%s_%s" % (model, S.chain.model), read_no)
    path = os.path.join(cdir, key + ".json")
    if os.path.exists(path):
        d = _load_json(path, None)
        if isinstance(d, dict):
            d.setdefault("_reader", S.chain.name)       # a read cached before readers were recorded came from the chain's first backend
        return d
    if S.exhausted:
        return None
    if S.calls >= b["max_page_reads_per_run"]:
        if not S.exhausted:
            S.exhausted = "budget of %d page reads for this run is used up" % b["max_page_reads_per_run"]
            log("brochure", "STOP: " + S.exhausted + "; the remaining models get no brochure data in this run")
        return None
    imgs = tiles(pdf, page, S.cfg, sha1)
    prompt = build_prompt(model, variants, fields, text, read_no)
    S.calls += 1
    try:
        reply = S.chain.complete(prompt, images=imgs, json_mode=True, label="brochure p%d r%d" % (page, read_no))
        data = llm.parse_json(reply)
        data["_reader"] = S.chain.last or S.chain.name
        S.fails = 0
    except llm.QuotaExhausted as e:
        S.exhausted = "LLM quota or usage limit (reader): %s" % str(e)[:200]
        log("brochure", "STOP: " + S.exhausted)
        return None
    except (llm.LLMError, ValueError) as e:
        log("brochure", "page %d read %d failed: %s" % (page, read_no, str(e)[:160]))
        _fail(S, b, "reader", e, log)
        return None
    with open(path + ".tmp", "w") as f:
        json.dump(data, f)
    os.replace(path + ".tmp", path)
    return data


def _fail(S, b, who, e, log):
    S.fails += 1
    if S.fails >= b["max_consecutive_failures"] and not S.exhausted:
        S.exhausted = "%d consecutive %s call failures (last: %s)" % (S.fails, who, str(e)[:160])
        log("brochure", "STOP: " + S.exhausted)


# ---------------------------------------------------------------- 5. units
def to_value(field, value, unit):
    """(value, None) in the KB's unit, or (None, reason). Power: kW x 1.34102 (2 dp); PS x 0.98632 (P4)."""
    u = str(unit or "").strip().lower()
    kind = F.FIELDS[field][1]
    if field == "drivetrain":
        v = str(value).strip().upper().replace(" ", "")
        v = {"4X4": "4WD", "2WD": None}.get(v, v)
        return (v, None) if v in F.DRIVETRAINS else (None, "drivetrain %r" % value)
    if kind == "bool":
        n = F.norm(field, value)
        return (n, None) if n in (0, 1) else (None, "not a boolean: %r" % (value,))
    try:
        x = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None, "not a number: %r" % (value,)
    if field == "power_bhp":
        if u == "bhp":
            return round(x, 2), None
        if u == "kw":
            return round(x * 1.34102, 2), None
        if u == "ps":
            return round(x * 0.98632, 2), None
        return None, "power in unit %r (only bhp, kW, PS are converted)" % unit
    ok = UNITS.get(field)
    if ok and u not in ok:
        return None, "unit %r for %s" % (unit, field)
    return F.norm(field, x), None


def applicable(field, fuel):
    """Fuel rules from the glossary: km/l not for CNG or electric, km/kg CNG only, tank not electric, EV range electric only,
    engine displacement not for electric."""
    if field == "mileage_arai_kmpl":
        return fuel not in ("CNG", "Electric")
    if field == "mileage_arai_km_per_kg":
        return fuel == "CNG"
    if field == "fuel_tank_litres":
        return fuel != "Electric"
    if field == "claimed_ev_range_km":
        return fuel == "Electric"
    if field == "engine_cc":
        return fuel != "Electric"
    return True


def parse_cells(reply, variants, fields_asked):
    """Turn one reply into {(variant, field): {value, qualifier, source}} plus drop counters. Variant names must exist exactly."""
    names = {v["name"]: v for v in variants}
    out, dropped, named = {}, {}, set()

    def drop(why):
        dropped[why] = dropped.get(why, 0) + 1

    cells = (reply or {}).get("cells") or []
    for cell in cells if isinstance(cells, list) else []:
        if not isinstance(cell, dict):
            continue
        f = cell.get("field")
        if f not in fields_asked:
            drop("field not asked")
            continue
        val, why = to_value(f, cell.get("value"), cell.get("unit"))
        if val is None:
            drop(why.split(":")[0][:40])
            continue
        if not F.in_range(f, val):
            drop("out of range")
            continue
        for vn in cell.get("variants") or []:
            if vn not in names:
                drop("variant not in the bundle")
                continue
            named.add(vn)
            if not applicable(f, names[vn].get("fuel")):
                drop("field not applicable to the fuel")
                continue
            k = (vn, f)
            if k in out and not F.same(f, out[k]["value"], val):
                out[k] = {"value": None, "conflict": True}       # one read contradicts itself on this cell
                continue
            out[k] = {"value": val, "qualifier": str(cell.get("qualifier") or ""), "source": str(cell.get("source") or "")[:300],
                      "raw": "%s %s" % (cell.get("value"), cell.get("unit") or "")}
    out = {k: v for k, v in out.items() if v.get("value") is not None}
    # absent-as-zero guard (enrich_batch, 10B lesson): a 0 for a feature the page never shows fitted on any variant, with no marker
    any1 = {f for (vn, f), v in out.items() if F.FIELDS[f][1] == "bool" and v["value"] == 1}
    for k in list(out):
        f = k[1]
        if F.FIELDS[f][1] == "bool" and out[k]["value"] == 0 and f not in any1 and not ABSENCE_MARKER.search(out[k]["source"]):
            del out[k]
            drop("zero without an absence marker")
    return out, dropped, named


def agree_reads(reads, tol=0.0):
    """Cells on which every read agrees (reconcile.agree). Returns (kept, n_disagree, n_single)."""
    first = reads[0]
    kept, dis, single = {}, 0, 0
    for k, a in first.items():
        others = [r.get(k) for r in reads[1:]]
        if any(o is None for o in others):
            single += 1
        elif all(R.agree(k[1], a["value"], o["value"], tol) for o in others):
            kept[k] = a
        else:
            dis += 1
    for r in reads[1:]:
        single += sum(1 for k in r if k not in first)
    return kept, dis, single


# ---------------------------------------------------------------- 7/8. existing evidence, KB links
def oem_backed(conn):
    """{(variant_id, field)} with accepted/confirmed brochure evidence in the database (rule 7)."""
    sid = conn.execute("select id from source where name='oem'").fetchone()
    if not sid:
        return set()
    rows = conn.execute("select p.variant_id, p.field_name from field_provenance p join source_observation o on o.id=p.source_observation_id "
                        "where o.source_id=? and p.decision in ('accepted','confirmed')", (sid[0],)).fetchall()
    return {(r[0], r[1]) for r in rows}


def kb_links(item, bundle, conn):
    """{version name: KB variant row} using the same linking the plan uses; plus the set of names the KB holds as editions."""
    if not item.get("in_kb"):
        return {}, set()
    kbv = plan.kb_variants(conn, item["kb_model_id"])
    editions = {x["name"] for x in kbv if x["base_variant_id"] is not None}
    live = [x for x in kbv if x["base_variant_id"] is None]
    for x in live:
        x["_t"] = {"name": x["name"], "fuel": x["fuel_type"], "transmission": x["transmission"],
                   "price": x["price_ex_showroom"], "engine_cc": x["engine_cc"]}
    out, matched = {}, set()
    for v in bundle["versions"]:
        if v["special"] or v["name"] in editions:
            continue
        f = v["fields_cw"]
        tgt = {"name": v["name"], "fuel": f.get("fuel_type"), "transmission": f.get("transmission"),
               "price": f.get("price_ex_showroom"), "engine_cc": f.get("engine_cc")}
        hit, _ = match.link(tgt, [x["_t"] for x in live if x["id"] not in matched], item["make"] + " " + item["model"])
        row = next((x for x in live if hit is not None and x["_t"] is hit), None)
        if row:
            matched.add(row["id"])
            out[v["name"]] = row
    return out, editions


# ---------------------------------------------------------------- 8. wrong-year guard (pre-LLM, from the text layer)
def guard_text(variants, texts, pages, model):
    """Share of catalogue variants whose trim words all appear on the chosen pages. None when no chosen page has a text layer."""
    toks = set()
    have = False
    for p in pages:
        if len(texts[p - 1].strip()) >= 50:
            have = True
            toks |= set(c.trim_tokens(texts[p - 1], ""))
    if not have:
        return None
    judged = [set(c.trim_tokens(v["name"], model)) for v in variants]
    judged = [t for t in judged if t]
    if not judged:
        return None
    return sum(1 for t in judged if t <= toks) / float(len(judged))


# ---------------------------------------------------------------- the entry point
def enrich(item, bundle, conn, cfg, fetcher, log, run_dir, chain=None, check_chain=None):
    """Attach brochure evidence to bundle["versions"][i]["brochure"]. Returns a summary dict (also written to
    <run_dir>/brochure/<make>_<model>.json). Never raises for a missing or unusable brochure: it logs why and returns."""
    b = bcfg(cfg)
    make, model = item["make"], item["model"]
    S = session(cfg, run_dir, chain, check_chain)
    summ = {"make": make, "model": model, "status": None, "brochures": [], "pages_read": 0, "llm_calls": 0, "cells_kept": 0,
            "cells_attached": 0, "cells_skipped_existing": 0, "cells_dropped_disagree": 0, "cells_dropped_single_read": 0,
            "cells_dropped_page_conflict": 0, "drops": {}, "cells": []}
    for v in bundle["versions"]:
        v.setdefault("brochure", [])
    if not b["enabled"]:
        summ["status"] = "disabled"
        return summ
    if S.exhausted:
        summ["status"] = "skipped: " + S.exhausted
        return summ
    calls0 = S.calls
    try:
        _enrich(item, bundle, conn, cfg, fetcher, log, S, b, summ)
    except Exception as e:                 # a broken brochure must never stop the run
        log("brochure", "%s %s: brochure layer failed (%s: %s); continuing without brochure data" % (make, model, type(e).__name__, str(e)[:200]))
        summ["status"] = "error: %s" % type(e).__name__
        for v in bundle["versions"]:
            v["brochure"] = []
    summ["llm_calls"] = S.calls - calls0
    S.models["%s/%s" % (make, model)] = summ
    _write(S, summ)
    return summ


def _write(S, summ):
    d = os.path.join(S.run_dir, "brochure")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "%s_%s.json" % (_slug(summ["make"]), _slug(summ["model"]))), "w") as f:
        json.dump(summ, f, indent=1, default=str)
    keys = ("status", "pages_read", "llm_calls", "cells_kept", "cells_attached", "cells_skipped_existing",
            "cells_dropped_disagree", "cells_dropped_single_read", "cells_dropped_page_conflict")
    with open(os.path.join(d, "summary.json"), "w") as f:
        json.dump({k: {x: m.get(x) for x in keys} for k, m in S.models.items()}, f, indent=1)


def _enrich(item, bundle, conn, cfg, fetcher, log, S, b, summ):
    make, model = item["make"], item["model"]
    links, editions = kb_links(item, bundle, conn)
    versions = [v for v in bundle["versions"] if not v["special"] and v["name"] not in editions]
    if not versions:
        summ["status"] = "no variants"
        return
    vinfo = [{"name": v["name"], "fuel": v["fields_cw"].get("fuel_type"), "transmission": v["fields_cw"].get("transmission")}
             for v in versions]
    by_name = {v["name"]: v for v in versions}
    summ["kb_linked"] = {n: r["id"] for n, r in links.items()}
    backed = oem_backed(conn)
    if item.get("in_kb"):
        brochures = locate_disk(item, cfg, log) or locate_new_dir(item, cfg, log)
    else:
        brochures = locate_new(item, bundle, cfg, fetcher, log)
    if not brochures:
        summ["status"] = "no brochure"
        if item.get("in_kb"):
            log("brochure", "%s %s: no brochure on disk for model id %s" % (make, model, item.get("kb_model_id")))
        return
    all_cells = {}                      # (variant, field) -> [ {value, page, ...} ]
    reader_of = {}                      # (pdf sha1, page) -> set of reader backend names
    for bro in brochures:
        pdf, sha1 = bro["path"], bro["sha1"]
        rec = {"pdf": stored_path(cfg, pdf), "sha1": sha1, "origin": bro["origin"], "pages": [], "status": None}
        summ["brochures"].append(rec)
        texts = page_texts(pdf, sha1, cfg)
        pages, scores = find_pages(texts, vinfo, model, b["max_pages_per_brochure"], b["min_page_score"])
        rec["pages"] = pages
        rec["page_scores"] = {str(p): scores[p] for p in pages}
        if not pages:
            rec["status"] = "no specification or feature page found"
            log("brochure", "%s %s: %s" % (make, model, rec["status"]))
            continue
        blind = any(len(texts[p - 1].strip()) < 50 for p in pages)       # an image-only page cannot be judged from text; the guard after the reads still applies
        frac = None if blind else guard_text(vinfo, texts, pages, model)
        rec["variant_match_fraction_text"] = None if frac is None else round(frac, 2)
        if frac is not None and frac < b["match_fraction"]:
            rec["status"] = "brochure does not match the current listing"
            log("brochure", "%s %s: brochure does not match the current listing (%d%% of variants named on its pages)" % (make, model, round(frac * 100)))
            continue
        named_all, page_results, readers = set(), [], {}
        for pg in pages:
            if S.exhausted:
                break
            text = texts[pg - 1]
            textual = len(text.strip()) >= 50
            fields = [f for f in BROCHURE_FIELDS if not textual or re.search(FIELD_KW[f], text, re.I)]
            if not fields:
                continue
            reads, dropped_all = [], {}
            for r in range(1, b["reads_per_page"] + 1):
                data = read_page(S, pdf, sha1, pg, text, model, vinfo, fields, log, r)
                if data is None:
                    break
                cells, dropped, named = parse_cells(data, vinfo, set(fields))
                readers.setdefault((sha1, pg), set()).add(data.get("_reader") or S.chain.name)
                reads.append(cells)
                named_all |= named
                for k, n in dropped.items():
                    dropped_all[k] = dropped_all.get(k, 0) + n
            if len(reads) < b["reads_per_page"]:
                continue
            summ["pages_read"] += 1
            kept, dis, single = agree_reads(reads)
            summ["cells_dropped_disagree"] += dis
            summ["cells_dropped_single_read"] += single
            for k, n in dropped_all.items():
                summ["drops"][k] = summ["drops"].get(k, 0) + n
            page_results.append((pg, kept))
        if page_results and len(named_all) < b["match_fraction"] * len(vinfo):
            rec["status"] = "brochure does not match the current listing"
            log("brochure", "%s %s: brochure does not match the current listing (the pages name %d of %d variants)" % (
                make, model, len(named_all), len(vinfo)))
            summ["pages_read"] -= len(page_results)
            continue
        rec["status"] = "read"
        for pg, kept in page_results:
            for (vn, f), cell in kept.items():
                all_cells.setdefault((vn, f), []).append(dict(cell, page=pg, pdf=pdf, sha1=sha1, url_origin=bro, field=f, variant=vn))
        reader_of.update(readers)
    # the same cell on several pages must agree, else it is dropped
    final = []
    for (vn, f), lst in all_cells.items():
        if len({F.norm(f, x["value"]) for x in lst}) > 1:
            summ["cells_dropped_page_conflict"] += 1
            continue
        final += lst
    summ["cells_kept"] = len(final)
    verdicts = check_cells(S, b, model, vinfo, final, reader_of, log, summ)
    # attach; one observation per (variant, page) so that its payload lists exactly the cells it supports
    per_obs = {}
    for x in final:
        row = links.get(x["variant"])
        existing = bool(row and (row["id"], x["field"]) in backed)
        v = verdicts.get(id(x)) or {"verdict": "unchecked", "attach": not b["check"], "evidence": "", "checker": None}
        summ["cells"].append({"variant": x["variant"], "kb_variant_id": row["id"] if row else None, "field": x["field"], "value": x["value"],
                              "page": x["page"], "printed": x["source"], "qualifier": x["qualifier"], "raw": x.get("raw"),
                              "group": F.FIELDS[x["field"]][2], "kb_has_brochure_value": existing, "verdict": v["verdict"],
                              "checker": v.get("checker"), "check_evidence": v.get("evidence", "")[:200], "sha1": x["sha1"]})
        if not v["attach"]:
            summ["cells_not_attached_check"] = summ.get("cells_not_attached_check", 0) + 1
            continue
        if existing:
            summ["cells_skipped_existing"] += 1       # rule 7: already brochure-backed, nothing to add
            continue
        per_obs.setdefault((x["variant"], x["page"], x["sha1"]), []).append(x)
    for (vn, pg, sha1), xs in sorted(per_obs.items()):
        first = xs[0]
        o = {"source": "oem", "raw_name": vn, "url": brochure_url(cfg, first["url_origin"], first["pdf"], pg), "observed_at": _utc(),
             "method": "kbpipe/%s brochure_page llm=%s" % (__version__, S.chain.model),
             "payload": {"pdf_path": stored_path(cfg, first["pdf"]), "pdf_sha1": sha1, "page": pg,
                         "printed": {x["field"]: x["source"] for x in xs},
                         "qualifier": {x["field"]: x["qualifier"] for x in xs if x["qualifier"]},
                         "fields": {x["field"]: x["value"] for x in xs}}}
        for x in xs:
            by_name[vn]["brochure"].append({"field": x["field"], "value": x["value"], "obs": o})
            summ["cells_attached"] += 1
    summ["status"] = summ["status"] or ("ok" if summ["pages_read"] else "nothing read")
    if S.exhausted:
        summ["status"] = "incomplete: " + S.exhausted
    log("brochure", "%s %s: %d page(s) read, %d call(s), %d cells kept (%d attached, %d already brochure-backed), dropped: %d disagree, %d single-read, %d page conflict" % (
        make, model, summ["pages_read"], S.calls, summ["cells_kept"], summ["cells_attached"], summ["cells_skipped_existing"],
        summ["cells_dropped_disagree"], summ["cells_dropped_single_read"], summ["cells_dropped_page_conflict"]))


# ---------------------------------------------------------------- independent image check
CHECK_PROMPT = """You are checking claims extracted from ONE page of an OEM car brochure for the {model}. Use ONLY the page image tiles given (overlapping tiles of the same page; look at all of them). Do not use any other knowledge of the car.

For each claim decide whether THIS PAGE supports it for the named catalogue variant:
- The brochure prints trim columns or names; map them to the variant using its fuel and gearbox and any printed restriction ("AT only", "Diesel only").
- Numbers: supported only when the page prints that number (the claim lists the printed value and unit; "stored" is the same value converted to the KB's unit, so only the printed figure must be on the page).
- Features (value 1): supported only when the page shows the feature fitted on that trim (tick, dot, "Yes", or the feature listed under that trim or as standard for it).
- Features (value 0): supported ONLY when the page shows the feature explicitly absent for that trim (a dash, cross, "-", "NA", "Not available" in that trim's cell, or listed as not available). A feature that is merely not mentioned, or a blank cell with no marker, is "unclear".
- Counts (airbags, drive modes) must equal the printed number for that trim.

Verdicts: "supported", "not_supported" (the page shows something different), "unclear" (the page does not settle it, is unreadable, or the trim cannot be matched). Be strict: when in doubt, "unclear".

CLAIMS (id | variant (fuel, gearbox) | field: meaning | value | printed value and unit | header or line the reader cited)
{claims}

OUTPUT: ONE JSON object and nothing else, no markdown fences:
{{"results":[{{"id":<claim id>,"verdict":"supported|not_supported|unclear","evidence":"<the cell, header or line on the page that decides it, max 20 words>"}}]}}
Every claim id must appear exactly once."""


def _claims_text(chunk, vmeta):
    rows = []
    for i, x in enumerate(chunk, 1):
        vm = vmeta.get(x["variant"]) or {}
        rows.append("%d | %s (%s, %s) | %s: %s | %s | %s | %s" % (
            i, x["variant"], vm.get("fuel") or "?", vm.get("transmission") or "?", x["field"], F.DEFINITIONS[x["field"]],
            x["value"], (x.get("raw") or "").strip(), (x.get("source") or "")[:120]))
    return "\n".join(rows)


def _sample(cells, frac, model):
    """Deterministic sample: per field group the cells with the smallest hash, at least 5 (or all when fewer), at least `frac`."""
    by = {}
    for x in cells:
        by.setdefault(F.FIELDS[x["field"]][2], []).append(x)
    pick = []
    for g, xs in by.items():
        xs = sorted(xs, key=lambda x: hashlib.sha256(("%s|%s|%s" % (model, x["variant"], x["field"])).encode()).hexdigest())
        n = len(xs) if len(xs) <= 5 else max(5, int(-(-len(xs) * frac // 1)))
        pick += xs[:n]
    return pick


def check_chunk(S, b, model, sha1, pdf, page, chunk, vmeta, readers, log):
    """{claim no: (verdict, evidence, checker backend)} for one chunk, or None when it could not be had. Cached on disk by
    (pdf sha1, page, prompt version, claims): a rerun makes no call. A checker is never the backend that read the page."""
    cdir = os.path.join(S.cfg["cache_dir"], "brochure_checks")
    os.makedirs(cdir, exist_ok=True)
    ctext = _claims_text(chunk, vmeta)
    ver = b["check_prompt_version"]
    key = "%s_p%d_%s_%s" % (sha1, page, ver, hashlib.sha256((model + "\n" + ctext).encode()).hexdigest()[:16])
    path = os.path.join(cdir, key + ".json")
    if os.path.exists(path):
        d = _load_json(path, None)
        if d:
            S.check_hits += 1
            return {int(r["id"]): (r.get("verdict"), str(r.get("evidence") or ""), d.get("checker")) for r in d["results"]}
    if S.exhausted:
        return None
    ex = tuple(sorted(readers))
    chain = S.check_chain or S.checkers.get(ex)
    if chain is None:
        try:
            chain = S.checkers[ex] = llm.get(S.cfg, "brochure_check", S.run_dir, exclude=ex)
        except llm.LLMError as e:
            S.exhausted = "no checker available: %s" % e
            log("brochure", "STOP: " + S.exhausted)
            return None
    imgs = tiles(pdf, page, S.cfg, sha1)
    prompt = CHECK_PROMPT.format(model=model, claims=ctext)
    S.check_calls += 1
    try:
        reply = chain.complete(prompt, images=imgs, json_mode=True, label="brochure check p%d" % page)
        data = llm.parse_json(reply)
        res = {int(r["id"]): r for r in data["results"] if isinstance(r, dict) and "id" in r}
        S.fails = 0
    except llm.QuotaExhausted as e:
        S.exhausted = "LLM quota or usage limit (checker): %s" % str(e)[:200]
        log("brochure", "STOP: " + S.exhausted)
        return None
    except (llm.LLMError, ValueError, KeyError, TypeError) as e:
        log("brochure", "check p%d failed: %s" % (page, str(e)[:160]))
        _fail(S, b, "checker", e, log)
        return None
    who = chain.last
    if who in readers:
        raise RuntimeError("checker %s is the reader of this page; refused" % who)
    if chain.dead:
        log("brochure", "checker chain: %s unavailable (%s); %s is answering" % (
            ",".join(sorted(chain.dead)), "; ".join(getattr(chain, "dead_why", {}).values())[:160], who))
    out = {i: (str(res.get(i, {}).get("verdict") or "unclear"), str(res.get(i, {}).get("evidence") or ""), who) for i in range(1, len(chunk) + 1)}
    with open(path + ".tmp", "w") as f:
        json.dump({"checker": who, "model": next((x.model for x in chain.backends if x.name == who), None), "readers": sorted(readers),
                   "prompt_version": ver, "page": page, "sha1": sha1,
                   "results": [{"id": i, "verdict": v[0], "evidence": v[1]} for i, v in out.items()]}, f)
    os.replace(path + ".tmp", path)
    return out


def check_cells(S, b, model, vinfo, final, reader_of, log, summ):
    """Check the cells that survived the two reads against the rendered page with a different model. Returns
    {id(cell): {verdict, attach, evidence, checker}}. Only a cell the checker supports is attached; with check_fraction < 1 the
    unchecked cells of a field group are attached only when that group's sample is at least check_bar supported."""
    if not b["check"]:
        return {}
    vmeta = {v["name"]: v for v in vinfo}
    frac = b["check_fraction"]
    todo = list(final) if frac >= 1.0 else _sample(final, frac, model)
    out = {}
    by_page = {}
    for x in todo:
        by_page.setdefault((x["sha1"], x["page"], x["pdf"]), []).append(x)
    for (sha1, pg, pdf), xs in sorted(by_page.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        xs.sort(key=lambda x: (x["field"], x["variant"]))
        readers = set(reader_of.get((sha1, pg)) or {S.chain.name})
        for i in range(0, len(xs), b["check_chunk"]):
            chunk = xs[i:i + b["check_chunk"]]
            res = check_chunk(S, b, model, sha1, pdf, pg, chunk, vmeta, readers, log)
            for n, x in enumerate(chunk, 1):
                if res is None:
                    out[id(x)] = {"verdict": "unchecked", "attach": False, "evidence": "", "checker": None}
                else:
                    v, ev, who = res[n]
                    out[id(x)] = {"verdict": v if v in ("supported", "not_supported", "unclear") else "unclear",
                                  "attach": v == "supported", "evidence": ev, "checker": who}
    if frac < 1.0:
        groups = {}
        for x in final:
            groups.setdefault(F.FIELDS[x["field"]][2], []).append(x)
        for g, xs in groups.items():
            done = [out[id(x)] for x in xs if id(x) in out and out[id(x)]["verdict"] != "unchecked"]
            ok = bool(done) and sum(1 for d in done if d["verdict"] == "supported") / float(len(done)) >= b["check_bar"]
            for x in xs:
                if id(x) not in out:
                    out[id(x)] = {"verdict": "unchecked_sampled" if ok else "unchecked", "attach": ok, "evidence": "", "checker": None}
    cnt = {}
    for x in final:
        v = out.get(id(x), {"verdict": "unchecked"})["verdict"]
        key = (F.FIELDS[x["field"]][2], v)
        cnt[key] = cnt.get(key, 0) + 1
    summ["check_counts"] = {"%s/%s" % k: n for k, n in sorted(cnt.items())}
    return out


def brochure_url(cfg, bro, pdf, page):
    """Observation URL. The page is part of it so that two cells of one variant from different pages get different keys
    (plan.okey hashes source, url, raw_name and method only)."""
    if bro["origin"] == "new":
        return "%s#page=%d" % (bro["url"], page)
    return file_url(cfg, pdf, page)
