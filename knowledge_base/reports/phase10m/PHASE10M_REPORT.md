# Phase 10M — km/kg for CNG, km/l not applicable (backlog item 7, app only)

No KB write: prod stays `acf32b47e19c711d9f8bdc332132c5df6510c489`. No catalogue change.

## 2. Change
The detail page hid the km/l row on CNG cars. It now reads "Not applicable: CNG is rated in km/kg". `spec_item` carries the note; `specList` shows a not-applicable item only if it has a note, so EV pages are unchanged. Audit of other surfaces: cards and the variants table use km/kg only (`static/script.js`, `services/car_detail.py`), ranking and filters never read km/l on CNG (`KMPL_UNTRUSTED_FUELS`), and the summary states km/kg separately.

## 3. Verification
`pytest` 353 passed. Rendered on a local run; screenshots are in the PR.

## 6. Schema
None.

## 7. App
`app/cng-kmpl-not-applicable`, stacked on `app/kb-10l-warranty`.

## 8. Prod SHA-1
Unchanged.
