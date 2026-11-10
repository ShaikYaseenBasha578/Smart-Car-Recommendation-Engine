# Blind re-scoring task (round 2)

`rows.jsonl` holds 30 rows that a language model extracted from car-brochure pages. For each row:
- `page_file` is the exact page text the model was given;
- `words_file` holds word boxes for that page: `{"words": [{"text", "x0", "top", "x1", "bottom", "line"}]}`.
  Coordinates are normalised 0..1, origin top-left, y down. `line` is an OCR line number, or null for text-layer words;
- `variants_file` lists the catalogue variant names for that car (names only).

Decide for every row whether it PASSES the five checks below. Then, for rows that pass, decide from the page
text whether the value is right. Use only the files in this directory. You may write small `python3 -I`
scripts to do this.

## Definitions
- ws(x): every run of whitespace becomes one space, then trim.
- key(x): upper case with all whitespace removed.
- **Trim name of a catalogue variant:** its name with these words removed: fuel (Petrol, Diesel, CNG), gearbox (MT, AT, AMT, DCT, DCA, DSG,
  IVT, CVT, e-CVT, TC, Manual, Automatic, also in brackets like "(TC)"), engine sizes (1.2, 1.5L …), Turbo, Strong, Hybrid,
  Mild, ADAS, ALLGRIP, Dual, Tone. Compare trims by key(), so "HX 5" equals "HX5".
- **Word order:** OCR words (non-null `line`) form reading rows. Lines are grouped into a row when their tops are within 0.006
  of the row's first line; rows run top to bottom and lines within a row left to right. Text-layer words (null `line`) follow,
  in file order.
- **Trim occurrence:** a run of consecutive words whose concatenated key, ignoring , ; : . at word edges, EQUALS a trim key.
  Drop an occurrence that lies inside a longer trim occurrence.
- **Quote span:** the shortest run of consecutive words whose concatenated key CONTAINS the quote's key.

## Checks (all must hold to PASS)
- **a:** ws(value_quote) is non-empty and occurs in ws(page text).
- **b:** the value appears in value_quote.
  - For numbers, some number in the quote equals the value.
  - For yes/no fields, value 1 needs "cruise" / "wireless" / "paddle", or a presence mark (• ● ✓ ✔ Yes Std Standard,
    a stand-alone S, a gearbox code such as 6AT, or "AT only"). Value 0 needs a stand-alone absence mark (- – — × ✗ No NA N/A "Not available").
- **c:** ws(header_quote) is non-empty and occurs in ws(page text). variant_label is not UNSURE, and key(variant_label)
  occurs inside key(header_quote).
- **d (structural link):**
  - **Value boxes:** the quote spans of value_quote. For numeric fields with no span, use single words containing the number.
  - **Header boxes:** the trim occurrences of the claimed trim, kept only if inside a quote span of header_quote (when such a span exists).
  - Tolerances: TY = 0.004, TX = 0.003. "Vertical overlap" = the intervals overlap within TY; "horizontal overlap" = within TX.
  - Relation by label_source:
    - COLUMN_HEADER: header.top < value.top, header.bottom ≤ value.top + TY, and they overlap horizontally.
    - ROW_HEADER: they overlap vertically, and header.x1 ≤ value.x0 + TX.
    - SAME_LINE: they overlap vertically.
    - SECTION_HEADING: header.top ≤ value.top + TY, and header.x0 ≤ value.x1 + TX.
    - Any other label_source fails d.
  - **Nearest:** among ALL trim occurrences on the page that meet the same relation to that value box, keep the nearest:
    - COLUMN_HEADER: the largest bottom (within TY);
    - ROW_HEADER: the largest x1 (within TX);
    - SAME_LINE: the smallest horizontal gap (within TX);
    - SECTION_HEADING: the largest top (within TY).
  - d holds if some (header box, value box) pair meets the relation AND that header occurrence is among the nearest.
- **e (qualifier):** a marker can sit in three places:
  - in value_quote, or in the value's "line" (the run of words around a value-quote span in the same band, where neighbouring
    words are ≤ 0.010 apart horizontally; if no span exists, the page-text line(s) containing the quote).
    Markers here: * ^ # ‡ † "only" (AT) (MT) (AMT) (DCT) (CVT) (IVT), or the gearbox codes AT/6AT/DCT/DSG/AMT/IVT/CVT;
  - in header_quote. Markers here: * ^ # ‡ † "only".

  If any marker is found, the qualifier must be non-empty.

## Verdict, for rows that PASS
- Work out which catalogue variants the row covers:
  - the claimed trim;
  - restricted by any gearbox or fuel words in the label, otherwise those in the header segment naming the trim;
  - then restricted by gearbox/fuel/engine words in the qualifier.
  - km/l rows exclude CNG variants unless CNG is named, and exclude ALLGRIP variants unless ALLGRIP is named.
  - km/kg rows cover CNG variants only.
  - Feature rows with no gearbox restriction cover every gearbox of the trim.
- **CORRECT:** the page text shows the value is right for every covered variant.
- **WRONG:** the page shows it is wrong for at least one.
- **CANNOT_TELL:** the page doesn't settle it.
- **AMBIGUOUS:** no catalogue variant can be identified.

Rows that are REJECTED get verdict `-`.

## Output
Write `answers.tsv` here with the header `blind_id a b c d e status verdict note`. a–e are 1 or 0; status is PASS or REJECTED.
