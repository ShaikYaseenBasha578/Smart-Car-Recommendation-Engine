# CORPUS-WIDE FIELD CLASSIFICATION

## Canonical Schema Reference
Valid boolean/feature columns in `variant` table:
airbags, abs, esc, hill_assist, tyre_pressure_monitoring_system, rear_parking_sensors, rear_camera, camera_360, adas_available, automatic_climate_control, rear_ac_vents, sunroof, ventilated_front_seats, cruise_control, paddle_shifters, wireless_charging, heads_up_display, drive_modes, connected_car_features, android_auto, apple_carplay

## Classification of Top Unmapped Fields

| Raw Field | Cleaned Key | Classification | Target Field | Reason |
|---|---|---|---|---|
| `electronic stability control (esc)` | `electronic stability control esc` | **CANONICALIZABLE** | `esc` | Direct match for Electronic Stability Control |
| `tyre pressure monitoring system(tpms) highline` | `tyre pressure monitoring system tpms highline` | **CANONICALIZABLE** | `tyre_pressure_monitoring_system` | Direct match for TPMS |
| `abs(anti-lock braking system) with ebd` | `abs anti lock braking system with ebd` | **CANONICALIZABLE** | `abs` | Direct match for ABS |
| `isofix` | `isofix` | **UNSUPPORTED** | `N/A` | Not in the canonical `variant` schema |
| `keyless entry system` | `keyless entry system` | **UNSUPPORTED** | `N/A` | Not in the canonical `variant` schema |
| `automatic headlamps` | `automatic headlamps` | **UNSUPPORTED** | `N/A` | Not in the canonical `variant` schema |
| `rear defogger` | `rear defogger` | **UNSUPPORTED** | `N/A` | Not in the canonical `variant` schema |
| `projector headlamps` | `projector headlamps` | **UNSUPPORTED** | `N/A` | Not in the canonical `variant` schema |
| `black painted` | `black painted` | **MARKETING_TEXT** | `N/A` | Styling/Marketing |
| `seatbelt reminder (all seats)` | `seatbelt reminder all seats` | **MARKETING_TEXT** | `N/A` | Styling/Marketing |
| `rear parcel tray` | `rear parcel tray` | **UNSUPPORTED** | `N/A` | Not in the canonical `variant` schema |
| `central locking` | `central locking` | **UNSUPPORTED** | `N/A` | Not in the canonical `variant` schema |
| `speed sensing auto door lock` | `speed sensing auto door lock` | **UNSUPPORTED** | `N/A` | Not in the canonical `variant` schema |
| `impact sensing auto door unlock` | `impact sensing auto door unlock` | **MARKETING_TEXT** | `N/A` | Styling/Marketing |
| `immobilizer` | `immobilizer` | **UNSUPPORTED** | `N/A` | Not in the canonical `variant` schema |
| `burglar alarm` | `burglar alarm` | **UNSUPPORTED** | `N/A` | Not in the canonical `variant` schema |
| `headlamp escort function` | `headlamp escort function` | **UNSUPPORTED** | `N/A` | Not in the canonical `variant` schema |
| `shark fin` | `shark fin` | **UNSUPPORTED** | `N/A` | Not in the canonical `variant` schema |
| `led tail lamps` | `led tail lamps` | **MARKETING_TEXT** | `N/A` | Styling/Marketing |
| `rear spoiler` | `rear spoiler` | **UNSUPPORTED** | `N/A` | Not in the canonical `variant` schema |
| `front footwell illumination` | `front footwell illumination` | **UNSUPPORTED** | `N/A` | Not in the canonical `variant` schema |
| `emergency stop signal (ess)` | `emergency stop signal ess` | **MARKETING_TEXT** | `N/A` | Styling/Marketing |
| `shark fin antenna` | `shark fin antenna` | **UNSUPPORTED** | `N/A` | Not in the canonical `variant` schema |
| `front parking sensors` | `front parking sensors` | **UNSUPPORTED** | `N/A` | Not in the canonical `variant` schema |
| `driver seat height adjuster` | `driver seat height adjuster` | **UNSUPPORTED** | `N/A` | Not in the canonical `variant` schema |
| `body coloured door handles` | `body coloured door handles` | **UNSUPPORTED** | `N/A` | Not in the canonical `variant` schema |
| `rear wiper & washer` | `rear wiper washer` | **UNSUPPORTED** | `N/A` | Not in the canonical `variant` schema |
| `driver & passenger` | `driver passenger` | **AMBIGUOUS** | `N/A` | Context-dependent (could refer to airbags, but the key alone is just "driver & passenger" or "side & curtain") |
| `side & curtain` | `side curtain` | **AMBIGUOUS** | `N/A` | Context-dependent (could refer to airbags, but the key alone is just "driver & passenger" or "side & curtain") |
| `vehicle stability management (vsm)` | `vehicle stability management vsm` | **CANONICALIZABLE** | `esc` | OEM equivalent name for Electronic Stability Control (Hyundai/Kia) |
| `rear disc brakes` | `rear disc brakes` | **UNSUPPORTED** | `N/A` | Not in the canonical `variant` schema |
| `seat belt pretensioners - driver & passenger` | `seat belt pretensioners driver passenger` | **AMBIGUOUS** | `N/A` | Context-dependent (could refer to airbags, but the key alone is just "driver & passenger" or "side & curtain") |
| `driver anchor pretensioner` | `driver anchor pretensioner` | **MARKETING_TEXT** | `N/A` | Styling/Marketing |
| `height adjustable front seat belts` | `height adjustable front seat belts` | **UNSUPPORTED** | `N/A` | Not in the canonical `variant` schema |
| `3 point seat belts (all seats)` | `3 point seat belts all seats` | **UNSUPPORTED** | `N/A` | Not in the canonical `variant` schema |
| `inside door override (driver only)` | `inside door override driver only` | **MARKETING_TEXT** | `N/A` | Styling/Marketing |
| `driver power window with auto up down and safety` | `driver power window with auto up down and safety` | **UNSUPPORTED** | `N/A` | Not in the canonical `variant` schema |
| `day and night mirror` | `day and night mirror` | **UNSUPPORTED** | `N/A` | Not in the canonical `variant` schema |
| `inside rear day and night mirror with telematics switches` | `inside rear day and night mirror with telematics switches` | **UNSUPPORTED** | `N/A` | Not in the canonical `variant` schema |
| `electro chromic mirror (ecm) with telematics switches` | `electro chromic mirror ecm with telematics switches` | **UNSUPPORTED** | `N/A` | Not in the canonical `variant` schema |
| `rear defogger with timer` | `rear defogger with timer` | **UNSUPPORTED** | `N/A` | Not in the canonical `variant` schema |
| `driver side` | `driver side` | **MARKETING_TEXT** | `N/A` | Styling/Marketing |
| `passenger side` | `passenger side` | **MARKETING_TEXT** | `N/A` | Styling/Marketing |
