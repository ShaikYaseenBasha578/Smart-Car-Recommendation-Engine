# Field glossary for brochure extraction

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

## Output units
bool (1/0), km/l, km/kg. `value` is a number or null; `status` is FOUND or NOT_ON_PAGE.
