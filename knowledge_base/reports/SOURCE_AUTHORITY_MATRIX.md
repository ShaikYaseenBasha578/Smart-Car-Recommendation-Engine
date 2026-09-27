# Field-Level Source Authority Matrix

This matrix establishes the strict hierarchy of truth for the CarRec Knowledge Base. It separates objective specifications from experiential evidence. We never rely on a single source if cross-validation is possible, but we resolve conflicts using the priority below.

## Objective Specifications (Dimensional & Powertrain)

| Field | Preferred Source | Secondary Source | Tertiary Source | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Make / Model / Variant Name** | OEM | 91Wheels | CarWale | Must be used as the primary entity resolution key. |
| **Engine CC** | OEM | 91Wheels | V3Cars | Objective fact. |
| **Cylinders** | OEM | 91Wheels | Autocar India | Objective fact. |
| **Max Power (bhp)** | OEM | 91Wheels | CarWale | Beware of PS vs BHP unit conversion discrepancies. |
| **Max Torque (Nm)** | OEM | 91Wheels | CarWale | Objective fact. |
| **Transmission Type** | OEM | 91Wheels | V3Cars | Ensure exact nomenclature (e.g., TC, DCT, CVT, AMT). |
| **Gears** | OEM | 91Wheels | V3Cars | Objective fact. |
| **Drivetrain (FWD/RWD/AWD)** | OEM | 91Wheels | CarWale | Objective fact. |
| **Length (mm)** | OEM | 91Wheels | CarWale | Objective fact. |
| **Width (mm)** | OEM | 91Wheels | CarWale | Objective fact. |
| **Height (mm)** | OEM | 91Wheels | CarWale | Objective fact. |
| **Wheelbase (mm)** | OEM | 91Wheels | CarWale | Objective fact. |
| **Ground Clearance (mm)** | OEM | 91Wheels | Autocar India | OEM methods vary (unladen vs laden). Prefer unladen standard. |
| **Boot Space (Litres)** | OEM | 91Wheels | V3Cars | Objective fact. |
| **Kerb Weight (kg)** | OEM | Autocar India | 91Wheels | Often missing on aggregators; OEM brochures are best. |
| **Fuel Tank Capacity (L)** | OEM | 91Wheels | CarWale | Objective fact. |
| **Claimed ARAI Mileage (kmpl)** | OEM | 91Wheels | CarWale | Must be explicitly labeled as "Claimed". |
| **Claimed EV Range (km)** | OEM (MIDC) | 91Wheels | V3Cars | Must specify testing cycle (MIDC, WLTP) if possible. |
| **Battery Capacity (kWh)** | OEM | 91Wheels | EVDB | EV specific. |
| **Charging Time (DC Fast)** | OEM | 91Wheels | Autocar India | Important context for EV recommendations. |

## Variant-Specific Features & Equipment

| Field | Preferred Source | Secondary Source | Tertiary Source | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Airbags Count** | OEM | 91Wheels | V3Cars | Critical for base-variant safety. |
| **ADAS Level / Availability** | OEM | 91Wheels | Autocar India | Distinguish Level 1 vs Level 2. |
| **ESC / ESP** | OEM | 91Wheels | V3Cars | Standardization varies widely by year. |
| **Sunroof Type** | OEM | 91Wheels | V3Cars | Single pane vs Panoramic. |
| **Touchscreen Size** | OEM | 91Wheels | V3Cars | Objective fact. |
| **Wireless Apple CarPlay / Android Auto** | OEM | 91Wheels | V3Cars | Often misreported by aggregators; requires strict validation. |
| **Ventilated Seats** | OEM | 91Wheels | V3Cars | Objective fact. |
| **360-Degree Camera** | OEM | 91Wheels | V3Cars | Objective fact. |
| **Drive Modes** | OEM | 91Wheels | V3Cars | Use strict presence/absence logic (developed in V5). |
| **Standard Warranty (Years/Km)** | OEM | V3Cars | 91Wheels | Preserve "Unlimited" strings (developed in V6). |
| **EV Battery Warranty** | OEM | V3Cars | — | Must be explicitly separated from vehicle warranty. |

## Safety Ratings (Highly Strict Validation)

| Field | Preferred Source | Secondary Source | Tertiary Source | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Testing Body** | BNCAP / GNCAP | — | — | Only official test results permitted. |
| **Adult Occupant Stars** | BNCAP / GNCAP | — | — | Manual override required to ensure applicability. |
| **Child Occupant Stars** | BNCAP / GNCAP | — | — | Manual override required to ensure applicability. |
| **Test Year** | BNCAP / GNCAP | — | — | Critical to prevent generation-mismatch (e.g. Swift 2022 vs 2024). |
| **Tested Variant / Powertrain** | BNCAP / GNCAP | — | — | CNG and EV models cannot inherit ICE scores without explicit proof. |

## Experiential Evidence & Market Data

| Field | Preferred Source | Secondary Source | Tertiary Source | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Real-World Mileage (City/Hwy)** | Team-BHP | Autocar India | Overdrive | Aggregated NLP extraction from owners vs professional tests. |
| **0-100 kmph (Tested)** | Autocar India | Evo India | Overdrive | Professional VBOX testing only. Never trust OEM claims alone. |
| **Ride Quality / Comfort** | Professional Reviews | Team-BHP | — | NLP synthesized consensus. |
| **Handling / Dynamics** | Professional Reviews | Team-BHP | — | NLP synthesized consensus. |
| **NVH Levels** | Professional Reviews | Team-BHP | — | NLP synthesized consensus. |
| **Reliability / Recurring Issues** | Team-BHP | Professional Reviews | — | Must require threshold of multiple mentions (prevent 1-off anecdotes). |
| **Service Centre Experience** | Team-BHP | — | — | Highly region-dependent, synthesize broadly. |
| **Ex-Showroom Price** | OEM | 91Wheels | CarWale | Prices change monthly; requires high-freshness pipeline. |
