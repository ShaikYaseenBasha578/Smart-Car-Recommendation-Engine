"""Phase 10K: gearbox/fuel qualifiers dropped from brochure tables (backlog item 3). Usage: apply_phase10k.py <db>
Found by scanning every brochure for feature rows with a qualifier, then reading each candidate page. Hand-verified, cell by cell."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brochure_phase import run
R = "OEM_BROCHURE_QUALIFIER_DROPPED"
BRO = {
 "kushaq": ("skoda/kushaq/latest/brochures/cartrade/kushaq_brochure.pdf", "291ac68611472bb47017da2560c456f322bb171f"),
 "venue": ("hyundai/venue/latest/brochures/hyundai_venue_brochure.pdf", "00eabf1c73ad06d076b7e3928d9ca54d9b4cb1c4"),
 "nios": ("hyundai/grand_i10_nios/latest/brochures/Grand_i10_Nios_Brochure.pdf", "352bd5977f225145e35687450ee4635e0d7416aa"),
 "victoris": ("maruti_suzuki/victoris/latest/brochures/maruti_suzuki_victoris_brochure.pdf", "94f94973736c150efdf2cc5ae6c40845d8e856a3"),
 "tiago": ("tata/tiago/latest/brochures/tata_tiago_brochure.pdf", "245f8902fb90cb3f50f576ec63a09e7ee6bc774f"),
}
def cell(vid, col, old, new, bro, page, printed): return dict(vid=vid, col=col, old=old, new=new, bro=bro, page=page, printed=printed, reason=R, release=None)
V = "Cruise control row: HX 2 -, HX 4 -, HX 5 S## (1.0 Turbo Petrol & 1.5 Diesel only), HX 5+ -, HX 6 S^ (DCT/AT only), HX 6T -"
H = "Hill start assist control (HAC) row: Era -, Magna -, Corporate AMT only, Sportz S, Sportz (O) S, Asta S"
C = "Cruise Control row: Lxi -, Vxi tick, Zxi / Zxi (O) tick, Zxi+ / Zxi+ (O) tick (MT & Strong Hybrid)"
T = "*Cruise control is not available in CNG AMT."
CELLS = [
 cell(605, "paddle_shifters", 1, 0, "kushaq", 27, "Paddle Shifters on Steering Wheel row: Classic+ AT only"),
 cell(605, "cruise_control", 1, 0, "kushaq", 27, "Cruise Control row: Classic+ AT only"),
 cell(150, "cruise_control", 1, 0, "venue", 20, V), cell(151, "cruise_control", 1, 0, "venue", 20, V), cell(154, "cruise_control", 1, 0, "venue", 20, V),
 cell(155, "cruise_control", 1, 0, "venue", 20, V), cell(156, "cruise_control", 1, 0, "venue", 20, V),
 cell(261, "esc", 0, 1, "nios", 10, "Electronic stability control (ESC) row: Corporate AMT only"),
 cell(259, "hill_assist", 0, 1, "nios", 10, H), cell(260, "hill_assist", 0, 1, "nios", 10, H), cell(264, "hill_assist", 0, 1, "nios", 10, H), cell(266, "hill_assist", 0, 1, "nios", 10, H),
 cell(570, "cruise_control", 0, 1, "victoris", 16, C), cell(574, "cruise_control", 0, 1, "victoris", 16, C),
 cell(364, "cruise_control", 1, 0, "tiago", 28, T), cell(365, "cruise_control", 1, 0, "tiago", 28, T),
]
if __name__ == "__main__":
    run(sys.argv[1], "10K", BRO, CELLS, quarantine_contradicted=True)
