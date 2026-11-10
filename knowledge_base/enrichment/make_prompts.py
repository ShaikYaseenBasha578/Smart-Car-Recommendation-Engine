"""Build one extraction prompt per gold page. No KB values enter a prompt.

Usage: python -I make_prompts.py <db_copy> <index_dir> <gold.tsv> <out_dir>
Writes <out_dir>/<pdf_sha1>_p<N>.prompt.txt and <out_dir>/<pdf_sha1>_p<N>.pagetext.txt
(the exact page text block given to Gemini, used later by the deterministic filter).
Page text = pdfplumber tables first, then the text layer (method 'text') or Vision OCR
(methods 'ocr' and 'text+ocr').
"""
import csv, json, os, sqlite3, sys

INSTRUCTION = ("Extract only these fields: {fields}. Return JSON rows: printed_label (exactly as printed), "
               "field, value, unit, quote (copied character-for-character from the text). Use only the given "
               "text. If the text doesn't clearly tie a value to a label, set printed_label to UNSURE. "
               "Do not paraphrase quotes.")
FIELD_HELP = {
    'mileage_arai_kmpl': 'fuel efficiency in km/l (value = the number, unit = "km/l")',
    'mileage_arai_km_per_kg': 'CNG fuel efficiency in km/kg (value = the number, unit = "km/kg")',
    'cruise_control': 'cruise control fitted (value 1 = present, 0 = shown as absent; unit = "bool")',
    'wireless_charging': 'wireless phone charger fitted (value 1 = present, 0 = shown as absent; unit = "bool")',
    'paddle_shifters': 'paddle shifters fitted (value 1 = present, 0 = shown as absent; unit = "bool")',
}


def render_tables(tables):
    out = []
    for k, t in enumerate(tables, 1):
        rows = [' | '.join('' if c is None else str(c).replace('\n', ' ') for c in r) for r in t]
        rows = [r for r in rows if r.replace('|', '').strip()]
        if rows:
            out.append(f'[TABLE {k}]\n' + '\n'.join(rows))
    return '\n\n'.join(out)


def main():
    db = sqlite3.connect(sys.argv[1]); idx = sys.argv[2]; out = sys.argv[4]
    os.makedirs(out, exist_ok=True)
    gold = list(csv.DictReader(open(sys.argv[3]), delimiter='\t'))
    pages = {}
    for g in gold:
        pages.setdefault((g['pdf_sha1'], int(g['page'])), g)
    for (sha, page), g in pages.items():
        fields = sorted({x['field'] for x in gold if x['pdf_sha1'] == sha})
        names = [r[0] for r in db.execute('select name from variant where model_id=? order by name', (g['model_id'],))]
        d = f'{idx}/{sha}'
        tables = render_tables(json.load(open(f'{d}/p{page}.tables.json')))
        body = open(f'{d}/p{page}.ocr.txt' if g['prompt_source'] == 'ocr' else f'{d}/p{page}.txt').read()
        pagetext = (tables + '\n\n' if tables else '') + body
        open(f'{out}/{sha}_p{page}.pagetext.txt', 'w').write(pagetext)
        prompt = '\n'.join([
            INSTRUCTION.format(fields=', '.join(fields)),
            '',
            'Field meanings:',
            *[f'- {f}: {FIELD_HELP[f]}' for f in fields],
            '',
            f'Car model: {g["model"]}. Variant names in our catalogue (names only; the brochure may print them differently):',
            ', '.join(names),
            '',
            'Answer with a JSON array of objects only, no other text.',
            '',
            f'===== PAGE TEXT ({ "OCR" if g["prompt_source"] == "ocr" else "PDF text layer" }; tables first) =====',
            pagetext,
            '===== END PAGE TEXT =====',
        ])
        open(f'{out}/{sha}_p{page}.prompt.txt', 'w').write(prompt)
        print(f'{sha}_p{page}', g['model'], g['prompt_source'], len(prompt), 'chars', file=sys.stderr)


if __name__ == '__main__':
    main()
