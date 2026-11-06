"""Phase 10J: brochure correction of the 10H sole-source cells (backlog item 2). Usage: apply_phase10j.py <db>
Only base-variant cells whose own brochure settles the value. Everything else stays quarantined (report section 2)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brochure_phase import run
H = "H1_SOLE_SOURCE_FROM_MISLINK"; R = "OEM_BROCHURE_MISMATCH"
BRO = {
 "harrier": ("tata/harrier/latest/brochures/tata_harrier_brochure.pdf", "93f7bf425f168db0f7a2a4b65b981ad21c7dd135"),
 "taigun": ("volkswagen/taigun/latest/brochures/volkswagen_taigun_brochure.pdf", "b2a396b599758b80a6643ad479eb21426eaa2c3c"),
 "amaze": ("honda/amaze/latest/brochures/honda_amaze_brochure.pdf", "6785506d40494ff77b00b47c3acc65f223758f73"),
 "dzire": ("maruti_suzuki/dzire/latest/brochures/maruti_suzuki_dzire_brochure.pdf", "26706ff36f0263e155ea920e7fb0e8344643271b"),
 "ertiga": ("maruti_suzuki/ertiga/latest/brochures/maruti_suzuki_ertiga_brochure.pdf", "d5a10fb1556e2ad77abd66a5747471bed3df5d2d"),
 "syros": ("kia/syros/latest/brochures/kia_syros_brochure.pdf", "7622f531b207ff69ab9ae6e3844653594356dced"),
 "clavis_ev": ("kia/carens_clavis_ev/latest/brochures/kia_carens_clavis_ev_brochure.pdf", "951ae4baf6eb4875e1ce2825232414b2634bb3f9"),
 "punch_ev": ("tata/punch_ev/latest/brochures/tata_punch_ev_brochure.pdf", "a15a4187083a334de6653570864a1cba206dffd4"),
 "tiago_ev": ("tata/tiago_ev/latest/brochures/tiago-brochure-evf-final.pdf", "c2aa56c0a2176ff75b381037466e2228b600cdc8"),
}
PX = "Key Features: Pure X (Features over Smart) lists Cruise Control"
TP = "Key Features: Fearless X (Features over Adventure X+) lists Tyre Pressure Monitoring System (TPMS); it is in no lower trim's list"
def cell(vid, col, old, new, bro, page, printed): return dict(vid=vid, col=col, old=old, new=new, bro=bro, page=page, printed=printed, reason=R, release=H)
CELLS = [
 # mileage
 cell(293, "mileage_arai_kmpl", 19.46, 18.65, "amaze", 27, "5 Speed Manual Transmission: Fuel Efficiency 18.65 km/l (CVT: 19.46 km/l)"),
 cell(237, "mileage_arai_kmpl", 25.71, 24.79, "dzire", 5, "24.79 km/l MT, 25.71 km/l AMT"),
 cell(210, "mileage_arai_kmpl", 20.3, 20.51, "ertiga", 7, "20.51 km/l Petrol: LXi MT, VXi MT, ZXi MT, ZXi+ MT (20.30 km/l: VXi AT, ZXi AT, ZXi+ AT)"),
 # Taigun: "AT only" qualifier dropped
 cell(630, "cruise_control", 1, 0, "taigun", 10, "Cruise control: Highline dot (AT only)"),
 cell(632, "cruise_control", 1, 0, "taigun", 10, "Cruise control: Highline Plus dot (AT only)"),
 cell(629, "cruise_control", 1, 1, "taigun", 10, "Cruise control: Highline dot (AT only)"),
 cell(631, "cruise_control", 1, 1, "taigun", 10, "Cruise control: Highline Plus dot (AT only)"),
 # Harrier
 cell(452, "sunroof", "0", "1", "harrier", 18, "Key Features: Pure X (Features over Smart) lists Voice-Assisted Panoramic Sunroof"),
 cell(453, "tyre_pressure_monitoring_system", 1, 0, "harrier", 19, TP),
 cell(457, "tyre_pressure_monitoring_system", 1, 0, "harrier", 19, TP),
 cell(452, "tyre_pressure_monitoring_system", 0, 0, "harrier", 19, TP),
 cell(458, "tyre_pressure_monitoring_system", 1, 1, "harrier", 19, TP),
 cell(460, "tyre_pressure_monitoring_system", 1, 1, "harrier", 19, TP),
 cell(462, "tyre_pressure_monitoring_system", 1, 1, "harrier", 19, TP),
 cell(452, "cruise_control", 1, 1, "harrier", 18, PX),
 cell(453, "cruise_control", 1, 1, "harrier", 18, PX + "; Adventure X adds to Pure X"),
 cell(457, "cruise_control", 1, 1, "harrier", 18, PX + "; Adventure X+ adds to Adventure X"),
 cell(458, "cruise_control", 1, 1, "harrier", 18, PX + "; Fearless X adds to Adventure X+ (p19)"),
 cell(460, "cruise_control", 1, 1, "harrier", 18, PX + "; Fearless X+ adds to Fearless X (p19)"),
 cell(462, "cruise_control", 1, 1, "harrier", 18, PX + "; Fearless X+ adds to Fearless X (p19)"),
 cell(453, "adas_available", 0, 0, "harrier", 18, "ADAS first listed at Adventure X+ (Features over Adventure X)"),
 # others
 cell(757, "cruise_control", 1, 1, "syros", 7, "HTK+ [Features in addition to HTK(EX)]: Cruise Control with Manual Speed Limit Assist"),
 cell(804, "cruise_control", 1, 1, "clavis_ev", 10, "HTK+: Cruise Control with Manual Speed Limit Assist; HTX is in addition to HTX E, in addition to HTK+"),
 cell(746, "cruise_control", 0, 0, "punch_ev", 23, "Cruise Control first listed at Adventure 40, not in Smart+ 30 and 40"),
 cell(742, "cruise_control", 0, 0, "tiago_ev", 32, "Cruise Control first listed at Creative+ 24 (Addition to Pure+ 24)"),
]
if __name__ == "__main__":
    run(sys.argv[1], "10J", BRO, CELLS, dict(corrected=8, confirmed=17, amend=8, obs=25, fp=25, released=25))
