"""Phase 10N: local brochure enrichment, first batch (backlog item 8). Usage: apply_phase10n.py <db>
Mileage where the brochure prints it, and cruise control / wireless charging for models whose tables were read by hand.
Cells, old values and printed text: phase10n_cells.tsv beside this script. A blind subagent read a stratified sample first (P12)."""
import csv, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from brochure_phase import run
R = "OEM_BROCHURE_ENRICHMENT"
BRO = {
    'amaze': ('honda/amaze/latest/brochures/honda_amaze_brochure.pdf', '6785506d40494ff77b00b47c3acc65f223758f73'),
    'city': ('honda/city/latest/brochures/honda_city_brochure.pdf', '36aee3e1e5add535a49ba4738533a7b5e2a30484'),
    'dzire': ('maruti_suzuki/dzire/latest/brochures/maruti_suzuki_dzire_brochure.pdf', '26706ff36f0263e155ea920e7fb0e8344643271b'),
    'ertiga': ('maruti_suzuki/ertiga/latest/brochures/maruti_suzuki_ertiga_brochure.pdf', 'd5a10fb1556e2ad77abd66a5747471bed3df5d2d'),
    'victoris': ('maruti_suzuki/victoris/latest/brochures/maruti_suzuki_victoris_brochure.pdf', '94f94973736c150efdf2cc5ae6c40845d8e856a3'),
    'harrier': ('tata/harrier/latest/brochures/tata_harrier_brochure.pdf', '93f7bf425f168db0f7a2a4b65b981ad21c7dd135'),
    'venue': ('hyundai/venue/latest/brochures/hyundai_venue_brochure.pdf', '00eabf1c73ad06d076b7e3928d9ca54d9b4cb1c4'),
    'taigun': ('volkswagen/taigun/latest/brochures/volkswagen_taigun_brochure.pdf', 'b2a396b599758b80a6643ad479eb21426eaa2c3c'),
    'virtus': ('volkswagen/virtus/latest/brochures/volkswagen_virtus_brochure.pdf', '882313c241b15256afc8f3c740c141a59d42a61a'),
    'kushaq': ('skoda/kushaq/latest/brochures/cartrade/kushaq_brochure.pdf', '291ac68611472bb47017da2560c456f322bb171f'),
    'punch_ev': ('tata/punch_ev/latest/brochures/tata_punch_ev_brochure.pdf', 'a15a4187083a334de6653570864a1cba206dffd4'),
    'altroz': ('tata/altroz/latest/brochures/tata_altroz_brochure.pdf', '5cbbf8b65224b23bb027ff078fe5e4721f793d25'),
    'syros': ('kia/syros/latest/brochures/kia_syros_brochure.pdf', '7622f531b207ff69ab9ae6e3844653594356dced'),
}
def num(col, v):
    if v == "": return None
    return float(v) if col.startswith("mileage") else v if col == "sunroof" else int(float(v))
CELLS = [dict(vid=int(r["vid"]), col=r["col"], old=num(r["col"], r["old"]), new=num(r["col"], r["new"]), bro=r["bro"], page=int(r["page"]), printed=r["printed"], reason=R, release="*")
         for r in csv.DictReader(open(os.path.join(HERE, "phase10n_cells.tsv")), delimiter="\t")]
if __name__ == "__main__":
    run(sys.argv[1], "10N", BRO, CELLS, quarantine_contradicted=True)
