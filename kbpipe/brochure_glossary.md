# Field glossary for brochure extraction (kbpipe)

Included in every extraction prompt. Sources: `KB_SCHEMA.sql` (variant columns), root `CLAUDE.md` (policy P1–P9),
the 10E–10N phase reports, and the cost check (all 8 errors came from the cruise-control definition below).
A value is for ONE variant, read from that variant's own column, row or trim list on the page.

## Rules that apply to every field
- Unknown is not zero. A feature is 0 only when the page shows it absent for that variant: a dash or empty cell in a table that
  covers the variant, a printed restriction that excludes the variant ("AT only" on a manual car), or a cumulative tier list
  ("in addition to ...") in which the feature is listed at some other trim of the same page and not at this variant's tier.
  A feature that appears nowhere on the page, for any trim, is NOT_ON_PAGE for every variant: do not report 0 because a list
  "has no HUD". A page that is silent about the variant gives value null, status NOT_ON_PAGE.
- A restriction printed with a value ("AT only", "6AT", "DCT only", "Petrol MT only", "1.5 Diesel only", "Strong Hybrid", "(O)")
  applies to the variant's own gearbox, engine and fuel. Copy the restriction into `qualifier`.
  A restricted feature is 1 on the matching variants and 0 on the others (the printed restriction proves the absence).
- Optional, paid or accessory fitment is not standard fitment. Report value null, qualifier "optional", status NOT_ON_PAGE.
- Footnote markers (*, #, ^, **) change what a value means. Read the footnote and apply it.
- Only the brochure page you are given counts. Never use knowledge of the car from elsewhere.
- Editions (Dark, Kaziranga, Dual Tone and similar) are skipped: the catalogue lists base variants only.

## cruise_control (bool)
- 1 when the variant has ANY cruise control: plain cruise control, cruise control with speed limiter or speed-limit assist,
  adaptive cruise control (ACC), smart cruise control (SCC, SCC with Stop and Go), intelligent cruise control.
  Adaptive-only cruise counts as 1. A page can list "Cruise Control (MT & Strong Hybrid)" for one trim and
  "Adaptive Cruise Control (6AT)" for the same trim. Read both rows; the automatic variants of that trim are 1.
- Several cruise rows on one page (plain cruise control, adaptive/smart cruise control): the value is 1 if ANY of them is fitted on the
  variant. A variant shown absent (dash) in an adaptive/smart-cruise row, when the page has no plain-cruise row, is NOT_ON_PAGE,
  not 0: the plain cruise control may be listed on another page. 0 needs every cruise row the page shows to be absent.
- "Speed limiter" or "speed limit assist" alone is not cruise control.
- "Cruise control" in a driving-mode, marketing or lifestyle paragraph with no trim table is not evidence for a trim.

## wireless_charging (bool)
- 1 only for a wireless smartphone charger (Qi pad, "wireless phone charger", "wireless charging pad").
- NOT wireless Android Auto / Apple CarPlay (a connectivity feature), NOT USB or Type-C charging ports, NOT 12V sockets.

## heads_up_display (bool)
- 1 for a head-up display (windscreen or combiner projection; digital HUD). NOT a digital instrument cluster, NOT a
  multi-information display (MID/TFT), NOT a mirror-mounted display.

## ventilated_front_seats (bool)
- 1 for ventilated, cooled or air-conditioned front seats (driver, co-driver or both). Heated-only seats are 0 or NOT_ON_PAGE.
  Ventilated rear seats do not count. "Cooled glovebox" is not seats.
- Put "driver only" or "driver and co-driver" in `qualifier` when the page says which.

## paddle_shifters (bool)
- 1 for steering-mounted paddles (gear paddles; on electric cars the regen paddles, as the existing rows treat them).
  Put "regen" in `qualifier` for regen paddles. A gear-shift lever or selector is not a paddle.
- Most brochures print paddles as "AT only" or "DCT only". Apply the restriction as above.

## mileage_arai_kmpl (km/l) — non-CNG, non-electric variants only
- The ARAI-certified fuel efficiency in km/l printed for the variant's own fuel and gearbox. Petrol MT, petrol AT/AMT/CVT/DCT,
  diesel and strong hybrid usually have different figures. Put the gearbox/engine label in `qualifier`.
- NOT km/kg (that is CNG), NOT a WLTP, real-world, city or highway figure, NOT a range in km, NOT a tank-based estimate.
- Not electric (EV) variants. A figure without a gearbox/engine label that covers several variants: report it with qualifier "all".

## mileage_arai_km_per_kg (km/kg) — CNG variants only
- The ARAI-certified CNG efficiency in km/kg. Never put a km/l figure here and never put a km/kg figure in the km/l field.
- Petrol-only variants get no km/kg cell.

## fuel_tank_litres (litres) — non-electric variants only
- The capacity in litres of the LIQUID-fuel tank (petrol, diesel, hybrid fuel tank) printed for the variant's engine. The CNG cylinder's
  water capacity never goes in this field, for any variant. A figure per engine or per
  gearbox applies to the variants of that engine or gearbox; put the label in `qualifier`.
- CNG variants: the petrol tank capacity (the liquid-fuel tank). NEVER the CNG cylinder "water equivalent" / "water capacity" figure (for
  example "CNG tank 60 L (water capacity)"), NOT the AdBlue tank, NOT a range in km. If the page prints only the CNG water capacity for a
  CNG variant, the cell is NOT_ON_PAGE.
- Electric variants have no fuel tank: do not report a cell for them.
- A variant the page does not give a figure for is NOT_ON_PAGE. Never copy a figure from another engine.

## drive_modes (count) — number of driver-selectable drive modes
- The number of modes the page lists for the driver-selectable drive mode selector (for example "Eco / Normal / Sport" = 3,
  "City / Sport" = 2). Count the modes as printed, report the list in `source`.
- Terrain or traction modes (Sand / Mud / Snow), regen levels and "Eco" as an indicator-only light do not count; report null with
  qualifier "terrain only" or "regen only" when that is all the page shows.
- Absent is not zero (same rule as the features): unlisted = unknown, never "none". Report 0 only when the page states that the
  variant has no drive modes with an explicit absence marker (a dash in a drive-mode row of a table that covers the variant). A
  mode list printed for a higher trim only, with the variant's own tier silent, is NOT_ON_PAGE for the lower tiers.
- A mode list restricted by a printed qualifier ("7DCT/AT", "Petrol MT, AMT and Diesel MT only") applies to those variants only;
  the other variants of that trim are NOT_ON_PAGE unless the page shows them absent with an explicit marker. For drive_modes the
  general rule above ("a restricted feature is 0 on the variants the restriction excludes") does NOT apply: a manual car whose
  trim lists "Drive Mode Select (7DCT/AT)" is NOT_ON_PAGE, not 0 (owner rule: unlisted = unknown, never "none").

## Fields added for kbpipe (the first glossary did not cover them)
Same rules as above: one value per variant, only from the page given, unknown is not zero, optional is not standard.
Report the number AS PRINTED with its printed unit in `unit`; the pipeline converts units, you never do.

### Engine and performance
- engine_cc (cc): displacement in cc as printed (1497 cc, not "1.5 L"). Per engine; apply to the variants that have that engine.
- power_bhp: maximum power. unit "bhp", "kW" or "PS" exactly as printed. Do NOT convert. "hp" alone is ambiguous: report unit "hp".
  Take the engine's maximum power at the printed rpm, not a system or motor figure unless that is the only figure for the engine
  (state which in `qualifier`). A hybrid's engine and motor figures are not added.
- torque_nm: maximum torque, unit "Nm" (or "kgm" if that is what is printed; never convert).
- drivetrain: FWD, RWD, AWD or 4WD for the variant. A brochure that prints only "2WD" for a front-engined car without saying which wheels: NOT_ON_PAGE.
  Value is a string in `value`.

### Dimensions (mm / kg)
- length_mm, width_mm, height_mm, wheelbase_mm, ground_clearance_mm: millimetres. Dimensions printed once for the whole model apply to every
  variant they are not restricted away from. A figure printed per trim, per tyre size or per engine ("with roof rails", "17 inch") applies to
  the variants with that trim, tyre or engine; put the label in `qualifier`. Unladen vs laden clearance: report the printed figure and label it.
- kerb_weight_kg: kerb weight in kg. A range ("1150-1220") or per-trim figures belong to the trims they are printed against; a range with no
  mapping to variants is NOT_ON_PAGE.
- seating_capacity: number of seats (count). A "5+2" or 7-seat layout is the total number of seats of that variant.
- boot_space_litres: boot / luggage volume in litres (VDA if printed). Seats-up figure only. CNG variants have a smaller boot: use their own figure.
- claimed_ev_range_km: certified range in km (ARAI/MIDC) for electric variants only, per battery pack. Real-world or WLTP figures are not this field.

### Safety
- airbags (count): the number of airbags standard on that variant. "6 airbags" with a trim table marking which trims have them: use the table.
- abs, esc, hill_assist, tyre_pressure_monitoring_system, rear_parking_sensors, rear_camera, camera_360: 1/0 as defined in "Rules that apply to every field".
  esc includes ESP/VDC. hill_assist is hill hold or hill start assist (HAC/HHC/HSA). TPMS: direct or indirect (also "tyre pressure monitor").
  rear_camera is 1 if a 360-degree camera is fitted. rear_parking_sensors: front-only sensors are not rear sensors.
- adas_available: 1 when the variant has any ADAS suite (lane-keep, collision-mitigation, adaptive cruise as part of ADAS, etc.). A lone
  "autonomous emergency braking" with no suite name still counts only if the page calls it ADAS or lists it for the trim. Ordinary ABS/ESC/airbags are not ADAS.

### Comfort and features
- automatic_climate_control: 1 for automatic (or "dual-zone auto") climate control; manual AC is 0 when the page shows the variant with manual AC.
- rear_ac_vents: 1 for rear AC vents / rear air-conditioning vents.
- sunroof: 1 for any sunroof (single-pane, electric, panoramic, voice-enabled). A moonroof counts. Sunroof marked "(O)" or as a pack is optional.
- connected_car_features: 1 for a connected-car / telematics suite (e.g. Bluelink, iConnect, remote app functions) fitted on the variant.
- android_auto, apple_carplay: 1 when the variant supports it, wired or wireless. If the page prints one row "Android Auto & Apple CarPlay",
  give both fields the same value.

## Output units
Allowed `unit` values: bool, bhp, kW, PS, hp, Nm, kgm, cc, mm, kg, litres, km/l, km/kg, km, count, text. `value` is a number (a string only for drivetrain).
Fields the page does not state are simply left out of "cells" (nothing is reported as null).
