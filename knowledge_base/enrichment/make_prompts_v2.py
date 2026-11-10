"""Round-2 prompts (pre-registered). One prompt per gold page. No KB values enter a prompt.

Usage: python -I make_prompts_v2.py <db_copy> <index_dir> <gold.tsv> <out_dir>
Writes <out_dir>/<pdf_sha1>_p<N>.prompt.txt and .pagetext.txt (the exact page text given to
Gemini; the filter checks quotes against it). Page text = pdfplumber tables first, then the
text layer (method 'text') or Vision OCR ('ocr', 'text+ocr'), exactly as in round 1.
Fields asked on a page = the gold fields of that brochure.
"""
import csv, os, sqlite3, sys
from make_prompts import render_tables, FIELD_HELP
import json

INSTRUCTION = """Extract only these fields: {fields}. Return a JSON array of rows with:
- variant_label: the TRIM or VARIANT name exactly as printed (e.g. 'Zxi+', 'HTX'). Never a feature or field name.
- label_source: one of COLUMN_HEADER, ROW_HEADER, SAME_LINE, SECTION_HEADING.
- header_quote: the exact text of that header or heading, copied character-for-character.
- qualifier: any restriction printed with the value or its header (e.g. '6AT', 'AT only', '(AMT)', '*', '^'), with its footnote meaning if printed; else ''.
- field, value, unit
- value_quote: the exact text containing the value, copied character-for-character.
If one value applies to several trims (e.g. 'Zxi / Zxi (O)'), return ONE ROW PER TRIM. If you can't tie a value to a trim from the text, set variant_label to UNSURE. Use only the given text; don't paraphrase quotes."""


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
            'Answer with the JSON array only, no other text.',
            '',
            f'===== PAGE TEXT ({"OCR" if g["prompt_source"] == "ocr" else "PDF text layer"}; tables first) =====',
            pagetext,
            '===== END PAGE TEXT =====',
        ])
        open(f'{out}/{sha}_p{page}.prompt.txt', 'w').write(prompt)
        print(f'{sha}_p{page}', g['model'], g['prompt_source'], len(prompt), 'chars', file=sys.stderr)


if __name__ == '__main__':
    main()
