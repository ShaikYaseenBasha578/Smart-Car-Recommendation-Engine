"""Image step: give catalogue models that have no photo one from the maker's own brochure PDF on disk.

Sourcing rule (the app's existing practice): photos come ONLY from the maker's official brochure PDFs already on
disk (knowledge_base/sources/oem and oem_kbpipe), are credited "<Make> brochure" and recorded in the app's
data/image_manifest.csv with PDF name, page and SHA-1. Nothing is downloaded and no model is called: candidates are ranked
with deterministic heuristics (size, aspect, early page, little text, colour and edge measures) and a human picks.

    python -m kbpipe.images --app-repo ~/carrec_worktrees/recsys-v3 [--run-dir DIR] [--only "Tata/Punch"]
    python -m kbpipe.images --app-repo ... --apply DIR/picks.json [--replace]

Default is a dry run that writes only into the run folder. --apply writes the app's image file and manifest row.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
import time

import fitz
import numpy as np
from PIL import Image

LICENSE = "OEM brochure — not licensed for reuse; replace for commercial use"
OUT_WIDTH = 800          # the existing set: WebP, 800 px wide, quality 80, no metadata
OUT_QUALITY = 80
MAX_PAGES = 14           # hero images sit early; later pages are specification and detail shots
MIN_WIDTH = 500          # px of source detail (embedded) or rendered width
TOP_N = 3
CONF_HIGH = 0.62         # top score at or above this, with a clear lead, may be pre-filled as the pick
CONF_LEAD = 0.04


# ---------------------------------------------------------------- catalogue, manifest, brochures
def slug(*parts):
    return re.sub(r"[^a-z0-9]+", "_", " ".join(parts).lower()).strip("_")


def _norm(s):
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


def manifest_path(app_repo):
    return os.path.join(os.path.expanduser(app_repo), "data", "image_manifest.csv")


def read_manifest(app_repo):
    with open(manifest_path(app_repo), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def models_without_image(app_repo):
    """[(make, model, body_type)] of catalogue models with no manifest row, in catalogue order."""
    have = {(r["make"], r["model"]) for r in read_manifest(app_repo)}
    out, seen = [], set()
    path = os.path.join(os.path.expanduser(app_repo), "data", "catalogue_v3", "catalogue.csv")
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            k = (r["make"], r["model"])
            if k in seen:
                continue
            seen.add(k)
            if k not in have:
                out.append((r["make"], r["model"], r.get("body_type", "")))
    return out


def sha1_file(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def find_brochures(make, model, oem_dir, oem_new_dir):
    """Official brochure PDFs on disk for this exact model: [path]. Reads both manifests, writes neither.
    A sibling model's brochure is never returned (exact make+model key only)."""
    out = []
    new = _load_json(os.path.join(os.path.expanduser(oem_new_dir), "brochure_manifest.json"))
    for key, v in new.items():
        if key.split("|")[0] == f"{make}/{model}":
            p = os.path.join(os.path.expanduser(oem_new_dir), v["path"])
            if os.path.isfile(p):
                out.append(p)
    old = _load_json(os.path.join(os.path.expanduser(oem_dir), "brochure_manifest.json"))
    kb_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.expanduser(oem_dir.rstrip("/")))))
    for key, v in old.items():
        if _norm(v.get("manufacturer", "")) == _norm(make) and _norm(v.get("model", "")) == _norm(model):
            p = os.path.join(kb_root, v.get("artifact_path", ""))
            if os.path.isfile(p):
                out.append(p)
    return out


# ---------------------------------------------------------------- image measures (deterministic)
def _to_rgb(im):
    if im.mode in ("RGBA", "LA") or "transparency" in im.info:
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        return bg
    return im.convert("RGB")


def measures(im):
    """Colourfulness (Hasler-Suesstrunk), edge density, flat fraction, centre-vs-border edge ratio, mean luma."""
    small = im.copy()
    small.thumbnail((200, 200))
    a = np.asarray(small.convert("RGB"), dtype=np.float32)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    rg, yb = r - g, 0.5 * (r + g) - b
    colour = float(np.hypot(rg.std(), yb.std()) + 0.3 * np.hypot(rg.mean(), yb.mean()))
    gray = a.mean(axis=2)
    gx = np.abs(np.diff(gray, axis=1))[:-1, :]
    gy = np.abs(np.diff(gray, axis=0))[:, :-1]
    mag = gx + gy
    edge = float((mag > 25).mean())
    h, w = mag.shape
    c = mag[h // 4: 3 * h // 4, w // 4: 3 * w // 4]
    border = (mag.sum() - c.sum()) / max(1, mag.size - c.size)
    ratio = float(c.mean() / (border + 1e-6))
    flat = float((mag < 3).mean())
    return {"colour": colour, "edge": edge, "centre_ratio": ratio, "flat": flat, "luma": float(gray.mean())}


def dhash(im, n=8):
    g = np.asarray(im.convert("L").resize((n + 1, n), Image.LANCZOS), dtype=np.int16)
    return int("".join("1" if v else "0" for v in (g[:, 1:] > g[:, :-1]).flatten()), 2)


def _hamming(a, b):
    return bin(a ^ b).count("1")


def _clamp01(x):
    return max(0.0, min(1.0, x))


def score(meta, im_m):
    """0..1 heuristic score of a candidate. meta: width, height, page (1-based), text_frac, kind."""
    w, h = meta["width"], meta["height"]
    aspect = w / h
    s_size = _clamp01((w - MIN_WIDTH) / 900.0)
    if 1.35 <= aspect <= 2.1:
        s_aspect = 1.0
    elif 1.15 <= aspect <= 2.5:
        s_aspect = 0.6
    else:
        s_aspect = 0.1
    s_page = 1.0 / (1.0 + 0.12 * (meta["page"] - 1))
    s_text = 1.0 - _clamp01(meta["text_frac"] * 4.0)
    s_colour = _clamp01(im_m["colour"] / 40.0) if im_m["colour"] < 80 else 0.8
    s_edge = 1.0 if 0.04 <= im_m["edge"] <= 0.35 else 0.4
    s_centre = _clamp01((im_m["centre_ratio"] - 0.8) / 1.2)       # a car sits in the middle of its frame
    s_busy = 1.0 - _clamp01((im_m["flat"] - 0.85) / 0.15)         # near-flat images are logos, swatches, text
    s_luma = 1.0 if 40 <= im_m["luma"] <= 225 else 0.7
    parts = {"size": s_size, "aspect": s_aspect, "page": s_page, "text": s_text, "colour": s_colour,
             "edge": s_edge, "centre": s_centre, "busy": s_busy, "luma": s_luma}
    weights = {"size": 1.0, "aspect": 1.6, "page": 1.0, "text": 1.4, "colour": 0.7, "edge": 0.5, "centre": 1.0,
               "busy": 0.8, "luma": 0.3}
    total = sum(weights.values())
    v = sum(parts[k] * weights[k] for k in parts) / total
    if min(s_aspect, s_text, s_busy) < 0.2:
        v *= 0.5
    return round(v, 4), parts


# ---------------------------------------------------------------- candidate extraction
def _area(r):
    return max(0.0, r.width) * max(0.0, r.height)


def _text_fraction(page, rect):
    area = max(_area(rect), 1.0)
    used = 0.0
    for b in page.get_text("blocks"):
        if len(b) > 6 and b[6] != 0:      # image blocks
            continue
        r = fitz.Rect(b[:4]) & rect
        if not r.is_empty:
            used += _area(r)
    return min(1.0, used / area)


def _pix_to_image(pix):
    if pix.alpha or pix.colorspace is None or pix.colorspace.n != 3:
        pix = fitz.Pixmap(fitz.csRGB, pix)
    im = Image.frombuffer("RGB", (pix.width, pix.height), pix.samples, "raw", "RGB", pix.stride, 1)
    return im.copy()


def _embedded(doc, xref):
    try:
        pix = fitz.Pixmap(doc, xref)
        im = _pix_to_image(pix)
        smask = doc.extract_image(xref).get("smask", 0)
        if smask:
            m = _pix_to_image(fitz.Pixmap(doc, smask)).convert("L")
            if m.size == im.size:
                bg = Image.new("RGB", im.size, (255, 255, 255))
                bg.paste(im, mask=m)
                im = bg
        return im
    except Exception:
        return None



def salient_window(im, aspect=1.6):
    """For a tall picture: the landscape window (full width, height = width/aspect) with the most edge and colour
    energy, as fractional (top, bottom). Deterministic; a car on a plain backdrop is the busiest part."""
    small = im.copy()
    small.thumbnail((160, 400))
    a = np.asarray(small.convert("RGB"), dtype=np.float32)
    gray = a.mean(axis=2)
    edge = np.abs(np.diff(gray, axis=0))[:, :-1] + np.abs(np.diff(gray, axis=1))[:-1, :]
    sat = a.max(axis=2) - a.min(axis=2)
    energy = (edge > 20).astype(np.float32).sum(axis=1) + 0.02 * sat[:-1, :-1].sum(axis=1)
    h = energy.shape[0]
    win = max(1, int(round(small.width / aspect)))
    if win >= h:
        return 0.0, 1.0
    csum = np.concatenate([[0.0], np.cumsum(energy)])
    # a car sits in the lower-middle of a portrait hero: prefer windows whose centre is not at the very top or bottom
    best, best_t = -1.0, 0
    for t in range(0, h - win + 1):
        centre = (t + win / 2) / h
        v = (csum[t + win] - csum[t]) * (1.0 - 0.5 * abs(centre - 0.55))
        if v > best:
            best, best_t = v, t
    return best_t / h, (best_t + win) / h



def _add_salient(out, im, kind, pageno, page, bbox):
    """Tall pictures (portrait brochure pages) get one extra candidate: the busiest landscape window."""
    if im.width / im.height >= 1.0:
        return
    top, bot = salient_window(im)
    if bot - top >= 0.98:
        return
    crop = im.crop((0, round(top * im.height), im.width, round(bot * im.height)))
    sub = fitz.Rect(bbox.x0, bbox.y0 + top * bbox.height, bbox.x1, bbox.y0 + bot * bbox.height)
    out.append({"page": pageno, "kind": "window-" + kind, "image": crop, "width": crop.width,
                "height": crop.height, "text_frac": _text_fraction(page, sub)})


def extract_candidates(pdf_path, max_pages=MAX_PAGES):
    """All plausible hero candidates of a PDF: [{page, kind, image(PIL), width, height, text_frac}].
    kind 'embedded' = an embedded raster as stored; 'crop' = the page rendered over a large picture's area
    (covers heroes that are split into tiles or carry vector parts)."""
    out = []
    doc = fitz.open(pdf_path)
    try:
        for pno in range(min(len(doc), max_pages)):
            page = doc[pno]
            prect = page.rect
            infos = page.get_image_info(xrefs=True)
            for info in infos:
                bbox = fitz.Rect(info["bbox"]) & prect
                if bbox.is_empty or _area(bbox) < 0.12 * _area(prect):
                    continue
                if info["width"] < MIN_WIDTH * 0.8 and info["height"] < 300:
                    continue
                tf = _text_fraction(page, bbox)
                xref = info.get("xref", 0)
                if xref:
                    im = _embedded(doc, xref)
                    if im is not None and im.width >= MIN_WIDTH and im.height >= 250:
                        out.append({"page": pno + 1, "kind": "embedded", "image": im, "width": im.width,
                                    "height": im.height, "text_frac": tf})
                        _add_salient(out, im, "embedded", pno + 1, page, bbox)
                scale = min(3.0, 1600.0 / max(bbox.width, 1))
                pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=bbox, alpha=False)
                im = _pix_to_image(pix)
                if im.width >= MIN_WIDTH:
                    out.append({"page": pno + 1, "kind": "crop", "image": im, "width": im.width,
                                "height": im.height, "text_frac": tf})
                    _add_salient(out, im, "crop", pno + 1, page, bbox)
            # tiled / vector heroes: the union of all picture placements of the page, if no single one is large
            boxes = [fitz.Rect(i["bbox"]) & prect for i in infos]
            boxes = [b for b in boxes if not b.is_empty and _area(b) > 0.02 * _area(prect)]
            if len(boxes) >= 2:
                u = fitz.Rect(boxes[0])
                for b in boxes[1:]:
                    u |= b
                if _area(u) >= 0.2 * _area(prect):
                    scale = min(3.0, 1600.0 / max(u.width, 1))
                    im = _pix_to_image(page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=u, alpha=False))
                    out.append({"page": pno + 1, "kind": "crop", "image": im, "width": im.width,
                                "height": im.height, "text_frac": _text_fraction(page, u)})
    finally:
        doc.close()
    return out


def rank_candidates(cands, top_n=TOP_N):
    """Score, drop near-duplicates (dHash), return the best top_n (highest first), each with 'score' and 'parts'."""
    scored = []
    for c in cands:
        s, parts = score(c, measures(c["image"]))
        c = dict(c, score=s, parts=parts, hash=dhash(c["image"]))
        scored.append(c)
    scored.sort(key=lambda c: (-c["score"], c["page"], 0 if c["kind"] == "embedded" else 1))
    keep = []
    for c in scored:
        if any(_hamming(c["hash"], k["hash"]) <= 6 for k in keep):
            continue
        keep.append(c)
        if len(keep) == top_n:
            break
    return keep


def confidence(top):
    """0..1: the top score, shrunk when the runner-up is close. A human decides below CONF_HIGH."""
    if not top:
        return 0.0
    lead = top[0]["score"] - (top[1]["score"] if len(top) > 1 else 0.0)
    conf = top[0]["score"] * (0.75 + 0.25 * _clamp01(lead / 0.15))
    return round(conf, 3)


# ---------------------------------------------------------------- the run (dry: writes only into the run folder)
def default_run_dir(app_repo=None):
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "knowledge_base", "runs")
    return os.path.join(base, time.strftime("images_%Y%m%dT%H%M%SZ", time.gmtime()))


def run(app_repo, oem_dir, oem_new_dir, run_dir=None, only=None, top_n=TOP_N, prefill=True, apply_repo=None):
    """Stage entry: list models without an image, extract and rank candidates, write candidates, contact sheet
    and picks.json into run_dir. Returns the picks dict. Never touches the app repo or the brochure folders.
    prefill=False leaves every choice empty (a person always picks). apply_repo is the repo recorded in picks.json for a later
    --apply when the catalogue was read from somewhere else (the update's scratch clone)."""
    app_repo = os.path.expanduser(app_repo)
    run_dir = run_dir or default_run_dir()
    os.makedirs(os.path.join(run_dir, "candidates"), exist_ok=True)
    picks, no_brochure = {}, []
    for make, model, body in models_without_image(app_repo):
        if only and f"{make}/{model}" not in only:
            continue
        pdfs = find_brochures(make, model, oem_dir, oem_new_dir)
        if not pdfs:
            no_brochure.append(f"{make}/{model}")
            continue
        pool = []
        for pdf in pdfs:
            for c in extract_candidates(pdf):
                c["pdf"] = pdf
                pool.append(c)
        top = rank_candidates(pool, top_n)
        key = slug(make, model)
        entries = []
        for i, c in enumerate(top, 1):
            rel = os.path.join("candidates", key, f"c{i}.jpg")
            os.makedirs(os.path.join(run_dir, "candidates", key), exist_ok=True)
            im = c["image"]
            if im.width > 1600:
                im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
            im.save(os.path.join(run_dir, rel), "JPEG", quality=90)
            entries.append({"file": rel, "page": c["page"], "kind": c["kind"], "score": c["score"],
                            "size": [c["width"], c["height"]], "text_frac": round(c["text_frac"], 3),
                            "pdf": c["pdf"], "pdf_sha1": sha1_file(c["pdf"])})
        conf = confidence(top)
        confident = prefill and bool(top) and conf >= CONF_HIGH and (len(top) == 1 or top[0]["score"] - top[1]["score"] >= CONF_LEAD)
        picks[key] = {"make": make, "model": model, "body_type": body, "candidates": entries,
                      "choice": 1 if confident else None, "crop": None, "confidence": conf,
                      "needs_human": not confident,
                      "note": "" if confident else "low confidence or no candidate: choose 1-3 by eye, or leave null to keep the placeholder"}
    with open(os.path.join(run_dir, "picks.json"), "w", encoding="utf-8") as f:
        json.dump({"app_repo": os.path.expanduser(apply_repo or app_repo), "no_brochure": no_brochure, "picks": picks}, f, indent=1, ensure_ascii=False)
    write_contact_sheet(run_dir, picks, no_brochure)
    return {"run_dir": run_dir, "picks": picks, "no_brochure": no_brochure}


def write_contact_sheet(run_dir, picks, no_brochure):
    rows = []
    for key, p in picks.items():
        cells = "".join(
            f'<figure><img src="{c["file"]}" loading="lazy"><figcaption>c{i} p.{c["page"]} {c["kind"]} '
            f'score {c["score"]}</figcaption></figure>' for i, c in enumerate(p["candidates"], 1))
        flag = "needs a human pick" if p["needs_human"] else f'pre-filled: c{p["choice"]}'
        rows.append(f'<section><h2>{p["make"]} {p["model"]} <small>confidence {p["confidence"]} - {flag}</small>'
                    f'</h2><div class="row">{cells or "<em>no candidate</em>"}</div></section>')
    html = ("<!doctype html><meta charset=utf-8><title>Image candidates</title><style>"
            "body{font:14px system-ui;margin:16px;max-width:1200px}.row{display:flex;gap:12px;flex-wrap:wrap}"
            "figure{margin:0;width:360px}img{width:100%;aspect-ratio:16/9;object-fit:contain;background:#eee}"
            "small{font-weight:400;color:#555}</style><h1>Hero image candidates</h1>"
            "<p>Edit picks.json: set \"choice\" to 1, 2 or 3 (null keeps the placeholder). Photos come only from the "
            "maker's own brochure.</p>" + "".join(rows) +
            ("<h2>No brochure on disk (keep placeholder)</h2><p>" + ", ".join(no_brochure) + "</p>" if no_brochure else ""))
    with open(os.path.join(run_dir, "contact_sheet.html"), "w", encoding="utf-8") as f:
        f.write(html)


# ---------------------------------------------------------------- processing and applying a pick
def process_image(im, width=OUT_WIDTH, quality=OUT_QUALITY):
    """Same recipe as the existing set: RGB, 800 px wide (never upscaled), WebP quality 80, no metadata."""
    im = _to_rgb(im)
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=quality, method=6)
    return buf.getvalue()


def crop_fraction(im, box):
    """Optional human crop of the picked candidate: [left, top, right, bottom] as fractions 0..1 (a plain rectangle
    of the brochure picture; nothing is painted or generated). None or an invalid box leaves the image as is."""
    if not box or len(box) != 4:
        return im
    l, t, r, b = box
    if not (0 <= l < r <= 1 and 0 <= t < b <= 1):
        return im
    return im.crop((round(l * im.width), round(t * im.height), round(r * im.width), round(b * im.height)))


def manifest_row(make, model, filename, pdf_path, page, sha1):
    return {"make": make, "model": model, "filename": filename,
            "source": f"{os.path.basename(pdf_path)}, p.{page}, SHA-1 {sha1}",
            "license": LICENSE, "attribution": f"{make} brochure"}


def apply_picks(picks_path, app_repo=None, replace=False):
    """Process each pick with a choice into the app. Refuses to overwrite a model that already has an image
    unless replace is set. Returns {'applied': [...], 'skipped': [(key, reason)]}."""
    data = _load_json(picks_path)
    base = os.path.dirname(os.path.abspath(picks_path))
    app_repo = os.path.expanduser(app_repo or data["app_repo"])
    rows = read_manifest(app_repo)
    fields = list(rows[0].keys()) if rows else ["make", "model", "filename", "source", "license", "attribution"]
    applied, skipped = [], []
    for key, p in data["picks"].items():
        ch = p.get("choice")
        if not ch:
            skipped.append((key, "no choice (keeps placeholder)"))
            continue
        if not 1 <= ch <= len(p["candidates"]):
            skipped.append((key, f"choice {ch} out of range"))
            continue
        c = p["candidates"][ch - 1]
        filename = key + ".webp"
        target = os.path.join(app_repo, "static", "car_images", filename)
        existing = [r for r in rows if (r["make"], r["model"]) == (p["make"], p["model"])]
        if (existing or os.path.exists(target)) and not replace:
            skipped.append((key, "already has an image (use --replace)"))
            continue
        pdf = c["pdf"]
        if sha1_file(pdf) != c["pdf_sha1"]:
            skipped.append((key, "brochure PDF changed since the run"))
            continue
        with Image.open(os.path.join(base, c["file"])) as im:
            data_bytes = process_image(crop_fraction(im, p.get("crop")))
        with open(target, "wb") as f:
            f.write(data_bytes)
        new = manifest_row(p["make"], p["model"], filename, pdf, c["page"], c["pdf_sha1"])
        rows = [r for r in rows if (r["make"], r["model"]) != (p["make"], p["model"])]
        rows.append(new)
        applied.append(key)
    rows.sort(key=lambda r: (r["make"], r["model"]))
    if applied:
        with open(manifest_path(app_repo), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    return {"applied": applied, "skipped": skipped}


# ---------------------------------------------------------------- stage hook and CLI
def stage(cfg, run_dir, write=False, picks_path=None, replace=False, catalogue_repo=None):
    """Hook for `kbpipe update`, after the export so models added in this update are seen. Candidates only: the measured
    top pick matched a by-eye choice for 7 of 28 models, so no choice is pre-filled and a person always picks.
    catalogue_repo: where the fresh catalogue is (the update's scratch clone); picks are applied to cfg["app_repo"]."""
    res = run(catalogue_repo or cfg["app_repo"], cfg["oem_dir"], cfg["oem_new_dir"], run_dir=os.path.join(run_dir, "images"),
              prefill=False, apply_repo=cfg["app_repo"])
    out = {"run_dir": res["run_dir"], "models": len(res["picks"]), "no_brochure": res["no_brochure"],
           "need_human": sorted(k for k, p in res["picks"].items() if p["needs_human"] and p["candidates"]),
           "no_candidate": sorted(k for k, p in res["picks"].items() if not p["candidates"])}
    if write and picks_path:
        out["apply"] = apply_picks(picks_path, cfg["app_repo"], replace=replace)
    return out


def main(argv=None):
    from kbpipe import config
    try:
        cfg = config.load() if hasattr(config, "load") else dict(config.DEFAULTS)
    except Exception:
        cfg = dict(config.DEFAULTS)
    ap = argparse.ArgumentParser(prog="python -m kbpipe.images", description=__doc__.split("\n\n")[0])
    ap.add_argument("--app-repo", default=cfg.get("app_repo"))
    ap.add_argument("--oem-dir", default=cfg.get("oem_dir"))
    ap.add_argument("--oem-new-dir", default=cfg.get("oem_new_dir"))
    ap.add_argument("--run-dir")
    ap.add_argument("--only", action="append", help='"Make/Model", repeatable')
    ap.add_argument("--apply", metavar="PICKS_JSON", help="process the chosen candidates into the app")
    ap.add_argument("--replace", action="store_true", help="allow overwriting an existing model's image")
    a = ap.parse_args(argv)
    if a.apply:
        res = apply_picks(a.apply, a.app_repo, replace=a.replace)
        print(json.dumps(res, indent=1))
        return 0
    res = run(a.app_repo, a.oem_dir, a.oem_new_dir, a.run_dir, only=set(a.only) if a.only else None)
    need = [k for k, p in res["picks"].items() if p["needs_human"]]
    print(f"run folder: {res['run_dir']}\n{len(res['picks'])} models with candidates, {len(need)} need a human pick; "
          f"no brochure: {', '.join(res['no_brochure']) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
