"""Build the v0 grounded and ungrounded prompts (paper/SPEC.md §5). No DB access, no LLM calls.

Inputs:  paper/data/catalogue_snapshot.csv, paper/data/queries_v0.jsonl
Outputs: paper/data/system_prompts_v0.json  (one system prompt per condition x body type, with SHA-256)
         paper/data/prompts_v0.jsonl        (one record per query x condition x phrasing)

Usage: python3 paper/prompts/build_prompts.py
"""
import csv
import hashlib
import json
import os

PAPER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(PAPER_DIR, "data")
CATALOGUE_CSV = os.path.join(DATA, "catalogue_snapshot.csv")
QUERIES = os.path.join(DATA, "queries_v0.jsonl")
SYSTEMS_OUT = os.path.join(DATA, "system_prompts_v0.json")
PROMPTS_OUT = os.path.join(DATA, "prompts_v0.jsonl")
PROMPT_VERSION = "v0"

# Shared by both conditions. Neutral: no hint about feasibility, abstention or disclosure; no length limit.
INSTRUCTIONS = (
    "You are a car-buying assistant for buyers in India. You can recommend only cars from the catalogue below, "
    "which lists every car model available. All prices and budgets are ex-showroom. Answer the buyer's message."
)
TABLE_LEGEND = ("Label meanings: Manual and iMT are manual; Torque Converter, AMT, DCT, CVT, e-CVT and "
                       "Automatic are automatic. Diesel Mild Hybrid is a diesel; Petrol Hybrid is a hybrid.")
TABLE_COLUMNS = ("Manufacturer", "Model", "Variant", "Fuel", "Transmission", "Seats", "Ex-showroom price")


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def indian_rupees(n):
    s = str(int(n))
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return "₹" + ",".join(groups + [tail])


def load_catalogue_csv(path=CATALOGUE_CSV):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def model_list(rows):
    names = sorted({(r["manufacturer"], r["model"]) for r in rows})
    return "\n".join(f"- {mfr} {model}" for mfr, model in names)


def variant_table(rows, body_type):
    sel = sorted((r for r in rows if r["body_type"] == body_type),
                 key=lambda r: (r["manufacturer"], r["model"], int(r["price"]), int(r["variant_id"])))
    lines = ["| " + " | ".join(TABLE_COLUMNS) + " |", "|" + "---|" * len(TABLE_COLUMNS)]
    for r in sel:
        cells = (r["manufacturer"], r["model"], r["variant_name"], r["fuel_raw"], r["transmission_raw"], r["seats"],
                 indian_rupees(r["price"]))
        lines.append("| " + " | ".join(c.replace("|", "/") for c in cells) + " |")
    return "\n".join(lines), [int(r["variant_id"]) for r in sel]


def ungrounded_system(rows):
    return f"{INSTRUCTIONS}\n\nCatalogue models:\n{model_list(rows)}"


def grounded_system(rows, body_type):
    table, ids = variant_table(rows, body_type)
    return (f"{ungrounded_system(rows)}\n\n"
            f"Every {body_type} variant in the catalogue, with its specifications:\n{TABLE_LEGEND}\n\n{table}"), ids


def build(rows=None, queries=None):
    rows = rows if rows is not None else load_catalogue_csv()
    if queries is None:
        with open(QUERIES, encoding="utf-8") as f:
            queries = [json.loads(line) for line in f]
    csv_sha = file_sha256(CATALOGUE_CSV)

    systems = {}
    u_text = ungrounded_system(rows)
    systems["U"] = {"condition": "ungrounded", "body_type": None, "text": u_text, "sha256": sha256(u_text),
                    "table_variant_ids": [], "approx_tokens": len(u_text) // 4}
    for body in sorted({q["constraints"]["body_type"] for q in queries}):
        g_text, ids = grounded_system(rows, body)
        systems[f"G-{body}"] = {"condition": "grounded", "body_type": body, "text": g_text, "sha256": sha256(g_text),
                                "table_variant_ids": ids, "approx_tokens": len(g_text) // 4}

    prompts = []
    for q in queries:
        surfaces = ([("na", q["surface_numeric"])] if q["phrasing_na"]
                    else [("numeric", q["surface_numeric"]), ("lakh", q["surface_lakh"])])
        for cond, sys_id in (("ungrounded", "U"), ("grounded", f"G-{q['constraints']['body_type']}")):
            for phrasing, user in surfaces:
                system = systems[sys_id]["text"]
                prompts.append({
                    "prompt_id": f"{q['query_id']}-{cond[0].upper()}-{phrasing}",
                    "query_id": q["query_id"],
                    "type": q["type"],
                    "condition": cond,
                    "phrasing": phrasing,
                    "system_id": sys_id,
                    "system_sha256": systems[sys_id]["sha256"],
                    "user": user,
                    "messages_sha256": sha256(json.dumps([system, user], ensure_ascii=False)),
                    "prompt_version": PROMPT_VERSION,
                    "catalogue_csv_sha256": csv_sha,
                    "kb_sha1": q["kb_sha1"],
                })
    return systems, prompts


def main():
    systems, prompts = build()
    with open(SYSTEMS_OUT, "w", encoding="utf-8") as f:
        json.dump(systems, f, ensure_ascii=False, indent=1)
        f.write("\n")
    with open(PROMPTS_OUT, "w", encoding="utf-8") as f:
        for p in prompts:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"wrote {len(systems)} system prompts and {len(prompts)} prompt records")
    for sid, s in systems.items():
        print(f"  {sid:12s} rows={len(s['table_variant_ids']):4d} ~{s['approx_tokens']} tokens")


if __name__ == "__main__":
    main()
