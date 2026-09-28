"""Phase 10C-1 spot-check verification aid (read-only).

Reads OEM_SPOTCHECK_SHEET.csv and the brochure PDFs; never writes to either,
never opens the KB. For each sheet row it renders the located spec-table page
and a crop that stacks the table's variant header band above the field's row
band (same x-range, so columns line up). The target variant column (from
`variant_name`) is tinted yellow; if `observation_raw_name` points at a
different column, that column gets an orange dashed outline.

The locations below (page, header band, column centres, row-label regex) were
set by hand from pdfplumber word coordinates. They say WHERE to look, never
what the cell says. Rendering uses pypdfium2 (poppler is not installed here).

Run from the repo root:  python3 knowledge_base/reports/phase10c/spotcheck_aid/build_spotcheck_aid.py
"""
import csv
import hashlib
import html
import os
import re

import pdfplumber
import pypdfium2 as pdfium
from PIL import Image, ImageDraw

SHEET = "knowledge_base/reports/phase10c/OEM_SPOTCHECK_SHEET.csv"
OUT = "knowledge_base/reports/phase10c/spotcheck_aid"
PAGE_SCALE = 1.5   # full-page PNGs
CROP_SCALE = 3.0   # crops

# Table geometry, PDF points. hdr = (y0, y1) of the variant header band;
# x = (x0, x1) of the table; cols = column centre x per variant label;
# yoff = shift applied to row bands where pdfplumber text boxes sit off the rendered glyphs.
AMAZE = dict(x=(20, 1132), cols={"V": 649, "VX": 835, "ZX": 1022})
CITY_COLS = {"SV": 280, "V": 364, "ZX": 448, "ZX+": 538}
AURA = dict(hdr=(95, 122), x=(40, 1045), cols={"E": 615, "S": 734, "SX": 850, "SX(O)": 967})
CRETA = dict(hdr=(92, 122), x=(40, 1045), cols={
    "E": 587, "EX": 639, "EX(O)": 689, "S(O)": 740, "S(O) Knight": 790, "SX": 842,
    "SX Premium": 892, "King": 943, "King Knight": 994})
BALENO = dict(hdr=(944, 988), x=(95, 985), yoff=-3.5, cols={
    "Sigma": 419, "Delta": 544, "Zeta": 668, "Alpha": 793, "Alpha (O)": 918})
BREZZA = dict(hdr=(6, 24), x=(45, 395), cols={"LXi": 189, "VXi": 235, "ZXi": 291, "ZXi+": 355})
FRONX = dict(hdr=(27, 45.5), x=(425, 815), cols={
    "Sigma": 578, "Delta": 630, "Delta+": 684, "Zeta": 736, "Alpha": 787})
SWIFT = dict(hdr=(470, 496), x=(15, 575), cols={
    "LXi": 240, "VXi": 305, "VXi (O)": 380, "ZXi": 460, "ZXi+": 535})
KYLAQ = dict(hdr=(34, 56), x=(35, 690), cols={
    "Classic": 281, "Classic+": 336, "Signature": 394, "Signature+": 458,
    "Sportline": 527, "Prestige": 592, "Prestige+": 653})
VIRTUS = dict(hdr=(60, 88), x=(90, 780), cols={
    "Comfortline": 481, "Highline": 526, "Highline Plus": 571, "Topline": 616,
    "GT Plus Chrome": 659, "GT Line": 703, "GT Plus Sport": 750})

# model -> {field: (page, table, [row-label regexes], note)}
LOC = {
    "Hyundai Aura": {
        "tyre_pressure_monitoring_system": (9, AURA, [r"^Tyre pressure monitoring"], ""),
        "hill_assist": (9, AURA, [r"^Hill start assist"], ""),
        "abs": (9, AURA, [r"^ABS \(Anti-lock"], ""),
        "rear_parking_sensors": (9, AURA, [r"^Rear parking sensors"], ""),
    },
    "Maruti Suzuki Baleno": {
        "rear_ac_vents": (11, BALENO, [r"^Rear AC Vents"], ""),
        "heads_up_display": (11, BALENO, [r"^Head Up Display"], ""),
    },
    "Maruti Suzuki Brezza": {
        "hill_assist": (10, BREZZA, [r"^Hill Hold Assist"], ""),
        "connected_car_features": (10, BREZZA, [r"^Connected Services powered", r"^Internet Connectivity"],
                                   "No row literally named 'connected car'; nearest rows shown."),
        "sunroof": (10, BREZZA, [r"^Electric Sunroof"], ""),
        "tyre_pressure_monitoring_system": (10, BREZZA, [r"^Tyre Pressure Monitoring"], ""),
        "heads_up_display": (10, BREZZA, [r"^Head Up Display"], ""),
        "cruise_control": (10, BREZZA, [r"^Cruise Control"], ""),
        "ventilated_front_seats": (10, BREZZA, [r"^Front Ventilated Seats"], ""),
        "rear_ac_vents": (10, BREZZA, [r"^Rear AC Vents"], ""),
    },
    "Maruti Suzuki Fronx": {
        "automatic_climate_control": (19, FRONX, [r"^Automatic Climate Control"], ""),
    },
    "Maruti Suzuki Swift": {
        "hill_assist": (6, SWIFT, [r"^Hill Hold Assist"], ""),
        "rear_parking_sensors": (6, SWIFT, [r"^Reverse Parking Sensors"], ""),
        "rear_camera": (6, SWIFT, [r"^Wide-angle Rear Parking Camera"], ""),
        "wireless_charging": (6, SWIFT, [r"^Wireless Charger"], ""),
    },
    "Skoda Kylaq": {
        "tyre_pressure_monitoring_system": (23, KYLAQ, [r"^Tyre Pressure Monitoring"], ""),
        "hill_assist": (23, KYLAQ, [r"^Hill Hold Control"], ""),
        "cruise_control": (23, KYLAQ, [r"^Cruise control"], ""),
        "paddle_shifters": (24, KYLAQ, [r"^Paddle Shifters"], ""),
        "android_auto": (25, KYLAQ, [r"^Wired Android Auto", r"^Wireless Android Auto"],
                         "Two rows (wired / wireless) shown."),
        "apple_carplay": (25, KYLAQ, [r"^Wired Android Auto", r"^Wireless Android Auto"],
                          "CarPlay shares the Android Auto rows; both shown."),
    },
    "Volkswagen Virtus": {
        "sunroof": (14, VIRTUS, [r"^Electric sunroof"], ""),
    },
    "Honda Amaze": {
        "automatic_climate_control": (39, dict(AMAZE, hdr=(18, 36)), [r"^Fully Automatic Climate Control"], ""),
    },
    "Honda City": {
        "cruise_control": (36, dict(hdr=(8, 28), x=(15, 585), cols=CITY_COLS), [r"Adaptive Cruise Control"],
                           "Only cruise row on the page is 'Adaptive Cruise Control'."),
        "paddle_shifters": (37, dict(hdr=(8, 28), x=(15, 585), cols=CITY_COLS),
                            [r"7-Speed Paddle Shifters", r"Deceleration Selector Paddle Shifters"],
                            "Both paddle-shifter rows shown."),
    },
    "Hyundai Creta": {
        "hill_assist": (13, CRETA, [r"^Hill start assist"], ""),
        "abs": (13, CRETA, [r"^ABS ?\(Anti-lock"], ""),
        "tyre_pressure_monitoring_system": (13, CRETA, [r"^Tyre pressure monitoring"], ""),
    },
}

# variant_name / raw name -> column label, per model.
def column_for(model, name):
    n = name.strip()
    if model == "Hyundai Aura":
        return n.split()[0]                     # "SX(O) MT" -> "SX(O)"
    if model == "Hyundai Creta":
        m = {"EX": "EX", "EX(O)": "EX(O)", "EX (O)": "EX(O)", "King": "King", "King Edition": "King"}
        for k in sorted(m, key=len, reverse=True):
            if n.startswith(k):
                return m[k]
    if model == "Maruti Suzuki Baleno":
        return "Alpha (O)" if n.startswith("Alpha (O)") else n.split()[0]
    if model in ("Maruti Suzuki Brezza", "Maruti Suzuki Fronx"):
        return n.split()[0]
    if model == "Maruti Suzuki Swift":
        return "VXi (O)" if n.startswith("VXi (O)") else n.split()[0]
    if model == "Skoda Kylaq":
        if n.startswith("Classic Plus") or n.startswith("Classic+"):
            return "Classic+"
        return n.split()[0]
    if model == "Volkswagen Virtus":
        if n.startswith("GT Plus"):
            for k in ("Chrome", "Sport"):
                if n.endswith(k):
                    return f"GT Plus {k}"
        for k in ("GT Plus Chrome", "GT Plus Sport", "GT Line", "Highline Plus", "Highline", "Topline", "Comfortline"):
            if n.startswith(k):
                return k
    if model in ("Honda Amaze", "Honda City"):
        return n.split()[0]                     # "V O O" -> "V", "SV - - -" -> "SV"
    return None


def sha1(path):
    with open(path, "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()


def find_rows(page, table, patterns):
    """Row bands (y0, y1) for each pattern: first matching text line below the header, inside the table x-range."""
    x0, x1 = table["x"]
    region = page.crop((max(0, x0 - 5), 0, min(page.width, x1), page.height))
    lines = [l for l in region.extract_text_lines() if l["top"] > table["hdr"][1]]
    bands = []
    for pat in patterns:
        hit = next((l for l in lines if re.search(pat, l["text"].strip(), re.I)), None)
        if hit is None:
            return None
        bands.append((hit["top"], hit["bottom"]))
    return bands


def col_span(cols, label):
    xs = sorted(cols.values())
    c = cols[label]
    i = xs.index(c)
    left = (xs[i - 1] + c) / 2 if i else c - (xs[1] - xs[0]) / 2
    right = (xs[i + 1] + c) / 2 if i + 1 < len(xs) else c + (xs[-1] - xs[-2]) / 2
    return left, right


def build_crop(img, table, bands, target, alt):
    s = CROP_SCALE
    x0, x1 = table["x"]
    pad = 1.5
    yo = table.get("yoff", 0)
    strips = [(table["hdr"][0], table["hdr"][1])] + [(a - pad + yo, b + pad + yo) for a, b in bands]
    pieces = [img.crop((int(x0 * s), int(y0 * s), int(x1 * s), int(y1 * s))) for y0, y1 in strips]
    gap = 10
    W = pieces[0].width
    H = sum(p.height for p in pieces) + gap * (len(pieces) - 1)
    out = Image.new("RGB", (W, H), "white")
    over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    y = 0
    for i, p in enumerate(pieces):
        out.paste(p, (0, y))
        for label, style in ((target, "fill"), (alt, "dash")):
            if not label:
                continue
            l, r = col_span(table["cols"], label)
            L, R = int((l - x0) * s), int((r - x0) * s)
            if style == "dash":
                L, R = L + 6, R - 6
            if style == "fill":
                d.rectangle([L, y, R, y + p.height], fill=(255, 220, 0, 70), outline=(200, 150, 0, 255), width=2)
            else:
                for yy in range(y, y + p.height, 12):
                    d.line([L, yy, L, yy + 6], fill=(230, 100, 0, 255), width=3)
                    d.line([R, yy, R, yy + 6], fill=(230, 100, 0, 255), width=3)
        if i:  # frame each field-row strip in red
            d.rectangle([0, y, W - 1, y + p.height - 1], outline=(220, 30, 30, 255), width=3)
        y += p.height
        if i < len(pieces) - 1:
            d.rectangle([0, y, W, y + gap], fill=(120, 120, 120, 255))
            y += gap
    out.paste(over, (0, 0), over)
    return out


def main():
    rows = list(csv.DictReader(open(SHEET, newline="")))
    os.makedirs(f"{OUT}/pages", exist_ok=True)
    os.makedirs(f"{OUT}/crops", exist_ok=True)
    pdf_hash_before = {p: sha1(p) for p in {r["pdf_path"] for r in rows}}
    page_png, hi_res, cards = {}, {}, []

    for i, r in enumerate(rows, 1):
        model, field, pdf_path = r["model"], r["field"], r["pdf_path"]
        loc = LOC.get(model, {}).get(field)
        target = column_for(model, r["variant_name"])
        raw_col = column_for(model, r["observation_raw_name"])
        card = dict(n=i, row=r, page=None, crop=None, page_png=None, note="", target=target, raw_col=raw_col)
        if loc is None or target is None or target not in loc[1]["cols"]:
            card["note"] = "No mapping for this variant/field."
            cards.append(card)
            continue
        pno, table, pats, note = loc
        with pdfplumber.open(pdf_path) as pdf:
            bands = find_rows(pdf.pages[pno - 1], table, pats)
        if bands is None:
            card["note"] = "Row label not found on page."
            cards.append(card)
            continue
        key = (pdf_path, pno)
        if key not in page_png:
            doc = pdfium.PdfDocument(pdf_path)
            slug = re.sub(r"[^A-Za-z0-9]+", "_", pdf_path.split("/oem/")[1].rsplit(".", 1)[0])
            page_png[key] = f"pages/{slug}_p{pno}.png"
            doc[pno - 1].render(scale=PAGE_SCALE).to_pil().save(f"{OUT}/{page_png[key]}", optimize=True)
            hi_res[key] = doc[pno - 1].render(scale=CROP_SCALE).to_pil().convert("RGB")
            doc.close()
        alt = raw_col if raw_col and raw_col != target and raw_col in table["cols"] else None
        crop = build_crop(hi_res[key], table, bands, target, alt)
        crop_rel = f"crops/row{i:02d}_{r['provenance_id']}.png"
        crop.save(f"{OUT}/{crop_rel}", optimize=True)
        card.update(page=pno, crop=crop_rel, page_png=page_png[key], note=note, alt=alt)
        cards.append(card)

    for p, h in pdf_hash_before.items():
        assert sha1(p) == h, f"PDF changed during run: {p}"
    write_html(cards, pdf_hash_before)
    print(f"cards={len(cards)} not_located={sum(c['crop'] is None for c in cards)}")


def write_html(cards, hashes):
    e = html.escape
    parts = []
    for c in cards:
        r = c["row"]
        rel_pdf = os.path.relpath(r["pdf_path"], OUT)
        head = (f'<div class="meta"><span class="n">#{c["n"]}</span>'
                f'<span class="k">prov</span> {e(r["provenance_id"])} '
                f'<span class="k">stratum</span> {e(r["stratum"])}</div>'
                f'<h2>{e(r["model"])} · {e(r["variant_name"])} · <code>{e(r["field"])}</code></h2>'
                f'<dl><dt>raw name</dt><dd>{e(r["observation_raw_name"])}</dd>'
                f'<dt>extracted_value</dt><dd><code>{e(r["extracted_value"])}</code></dd>'
                f'<dt>PDF</dt><dd><a href="{e(rel_pdf)}">{e(r["pdf_path"])}</a></dd>')
        if c["crop"] is None:
            body = (head + '<dt>page</dt><dd>—</dd></dl>'
                    f'<div class="nl">NOT LOCATED</div><p class="note">{e(c["note"])}</p>')
            cls = "card notloc"
        else:
            cols = f'yellow = <b>{e(c["target"])}</b> (from variant_name)'
            if c.get("alt"):
                cols += f'; orange dashes = <b>{e(c["alt"])}</b> (from raw name — differs)'
            body = (head + f'<dt>page</dt><dd><a href="{e(rel_pdf)}#page={c["page"]}">{c["page"]}</a> '
                    f'(<a href="{e(c["page_png"])}">full page PNG</a>)</dd></dl>'
                    f'<p class="legend">Crop = header band, then field row band(s) framed in red, same columns. {cols}.</p>'
                    + (f'<p class="note">{e(c["note"])}</p>' if c["note"] else "")
                    + f'<a href="{e(c["crop"])}"><img loading="lazy" src="{e(c["crop"])}" alt="crop row {c["n"]}"></a>')
            cls = "card"
        parts.append(f'<section class="{cls}" id="row{c["n"]}">{body}</section>')
    nl = sum(c["crop"] is None for c in cards)
    hash_list = "".join(f"<li><code>{h}</code> {e(p)}</li>" for p, h in sorted(hashes.items()))
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OEM Spot-check Aid</title>
<style>
:root{{--bg:#f6f6f4;--fg:#1d1d1b;--muted:#6b6b66;--card:#fff;--line:#ddd;--bad:#b3261e}}
@media (prefers-color-scheme:dark){{:root{{--bg:#1b1b1a;--fg:#eee;--muted:#a3a39c;--card:#262625;--line:#3a3a38;--bad:#ff8a80}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,sans-serif;margin:0 auto;max-width:1100px;padding:16px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 16px;margin:0 0 18px}}
.notloc{{border-color:var(--bad)}} .nl{{color:var(--bad);font-weight:700;font-size:20px}}
h1{{font-size:22px}} h2{{font-size:17px;margin:4px 0 8px}}
.meta{{color:var(--muted);font-size:13px}} .n{{font-weight:700;color:var(--fg);margin-right:10px}} .k{{margin-left:6px}}
dl{{display:grid;grid-template-columns:max-content 1fr;gap:2px 12px;margin:0 0 8px;font-size:14px}} dt{{color:var(--muted)}} dd{{margin:0;overflow-wrap:anywhere}}
img{{max-width:100%;border:1px solid var(--line);background:#fff}}
.legend,.note{{font-size:13px;color:var(--muted);margin:4px 0}}
a{{color:inherit}}
</style></head><body>
<h1>Phase 10C-1 OEM spot-check — verification aid</h1>
<p>{len(cards)} cards in sheet order · {nl} NOT LOCATED. Locations only: no value read by Claude appears on this page.
Fill <code>true_value</code>/<code>verdict</code> in <code>OEM_SPOTCHECK_SHEET.csv</code> from the crop, and open the full page whenever the crop looks off
(highlighted column and row were placed by hand from text coordinates). The <code>#page=</code> links work in most PDF viewers.</p>
<details><summary>PDF SHA-1 (unchanged during build)</summary><ul>{hash_list}</ul></details>
{''.join(parts)}
</body></html>"""
    with open(f"{OUT}/index.html", "w") as f:
        f.write(doc)


if __name__ == "__main__":
    main()
