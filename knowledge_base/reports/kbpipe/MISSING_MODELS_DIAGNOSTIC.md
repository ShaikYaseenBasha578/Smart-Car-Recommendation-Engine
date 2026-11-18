# Missing models: diagnostic of why nothing links (step 1, no code change)

Source: cached CarWale and CarDekho model pages from the 17 Nov discovery file (`knowledge_base/runs/update_full_2026-11-17_specs/discovery.json`), original linker (tier 0 = the linker before any change). Offline: no page was fetched for this report.

Per CarWale version: the best CarDekho candidate on the model page (most shared trim words once battery, descriptor and dual-tone words are set aside, then nearest price) and the blocks that stop the link. A version can have several blocks. Blocks: **A** battery size in one name only; **B** page-name kWh spelling; **C** hybrid labelled Petrol; **D** descriptor words; **E** price beyond tolerance; **F** genuinely different names. `other` = none of these explains it.

## Totals

CarWale versions examined: **101** across 16 models.

| Block | Versions with this block | Versions where it is the first blocker |
|---|---|---|
| A battery size in one name only | 49 | 49 |
| B page-name kWh spelling | 5 | 5 |
| C hybrid labelled Petrol | 10 | 5 |
| D descriptor words | 12 | 7 |
| E price beyond tolerance | 46 | 10 |
| F genuinely different names | 25 | 25 |
| other unexplained | 0 | 0 |

First blocker order used: F, B, A, C, D, E (a name that differs outright is reported before anything else). The old linker linked 5 versions on the list pages (block B versions are among them: they link, then the page-name check discards the page).

## Per model

| Model | CarWale versions | CarDekho variants | Blocks (version counts) |
|---|---|---|---|
| Honda ZR-V | 1 | 1 | D 1, E 1, F 1 |
| Hyundai Creta Electric | 29 | 29 | A 28, E 2, F 1 |
| Kia Syros EV | 7 | 7 | A 7, E 1 |
| MG Comet EV | 5 | 6 | A 3, D 2, E 5 |
| MG Hector Tomahawk EV | 4 | 4 | A 4, E 4 |
| MG Hector Tomahawk PHEV | 2 | 2 | C 2, D 2, E 2, F 2 |
| MG ZS EV | 7 | 7 | A 2, E 7, F 5 |
| Mahindra BE 6 Sporteq | 20 | 10 | E 20, F 10 |
| Mahindra XUV 3XO EV | 4 | 2 | D 2, E 2, F 2 |
| Mahindra XUV400 | 5 | 5 | B 5 |
| Maruti Suzuki Invicto | 3 | 3 | C 3 |
| Nissan X-Trail | 1 | 1 | F 1 |
| Tata Tigor EV | 4 | 4 | A 4 |
| Toyota Camry | 4 | 2 | C 4, D 1, F 3 |
| Toyota Fortuner Legender | 3 | 3 | C 1, D 3, E 1 |
| Toyota Urban Cruiser Ebella | 2 | 1 | A 1, D 1, E 1 |

## Every CarWale version

| Model | CarWale version (fuel, price) | Best CarDekho candidate (fuel, price) | Old linker | Blocks | Detail |
|---|---|---|---|---|---|
| ZR-V | Sport Hybrid (Electric + Petrol) Automatic e:HEV (Petrol Hybrid, 4799000) | Honda ZR-V Hybrid (Petrol Hybrid, 4999900) | no candidate with the same identity | D,E,F | descriptor words: e, hev; different words: sport; price 4799000 vs 4999900 |
| Creta Electric | Executive 42.0 kWh (Electric, 1457159) | Hyundai Creta Electric Executive (Electric, 1802800) | no candidate with the same identity | A,E | kWh 42 is in the CarWale name only; price 1457159 vs 1802800 |
| Creta Electric | Executive Tech 42.0 kWh (Electric, 1899900) | Hyundai Creta Electric Executive Tech (Electric, 1899900) | no candidate with the same identity | A | kWh 42 is in the CarWale name only |
| Creta Electric | Premium 42.0 kWh (Electric, 1999900) | Hyundai Creta Electric Premium (Electric, 1999900) | no candidate with the same identity | A | kWh 42 is in the CarWale name only |
| Creta Electric | Executive (O) LR 51.4 kWh (Electric, 1999900) | Hyundai Creta Electric Executive (O) LR (Electric, 1999900) | no candidate with the same identity | A | kWh 51.4 is in the CarWale name only |
| Creta Electric | Premium 42.0 kWh Dual Tone (Electric, 2015500) | Hyundai Creta Electric Premium DT (Electric, 2015500) | no candidate with the same identity | A | kWh 42 is in the CarWale name only |
| Creta Electric | Premium 42.0 kWh (HC) (Electric, 2073500) | Hyundai Creta Electric Premium HC (Electric, 2073500) | no candidate with the same identity | A | kWh 42 is in the CarWale name only |
| Creta Electric | Premium 42.0 kWh Dual Tone (HC) (Electric, 2088500) | Hyundai Creta Electric Premium HC DT (Electric, 2088500) | no candidate with the same identity | A | kWh 42 is in the CarWale name only |
| Creta Electric | Excellence 42.0 kWh (Electric, 2130500) | Hyundai Creta Electric Excellence (Electric, 2130500) | no candidate with the same identity | A | kWh 42 is in the CarWale name only |
| Creta Electric | Excellence Knight Edition 42.0 kWh (Electric, 2145400) | Hyundai Creta Electric Excellence Knight (Electric, 2145400) | no candidate with the same identity | A | kWh 42 is in the CarWale name only |
| Creta Electric | Excellence 42.0 kWh Dual Tone (Electric, 2145500) | Hyundai Creta Electric Excellence DT (Electric, 2145500) | no candidate with the same identity | A | kWh 42 is in the CarWale name only |
| Creta Electric | Smart (O) LR 51.4 kWh (Electric, 2153700) | Hyundai Creta Electric Smart (O) LR (Electric, 2153700) | no candidate with the same identity | A | kWh 51.4 is in the CarWale name only |
| Creta Electric | Excellence Knight Edition 42.0 kWh Dual Tone (Electric, 2160400) | Hyundai Creta Electric Excellence Knight DT (Electric, 2160400) | no candidate with the same identity | A | kWh 42 is in the CarWale name only |
| Creta Electric | Excellence 42.0 kWh (HC) (Electric, 2203500) | Hyundai Creta Electric Excellence HC (Electric, 2203500) | no candidate with the same identity | A | kWh 42 is in the CarWale name only |
| Creta Electric | Excellence Knight Edition 42.0 kWh (HC) (Electric, 2218400) | Hyundai Creta Electric Excellence HC Knight (Electric, 2218400) | no candidate with the same identity | A | kWh 42 is in the CarWale name only |
| Creta Electric | Excellence 51.4 kWh Dual Tone (Electric, 2218500) | Hyundai Creta Electric Excellence DT (Electric, 2145500) | no candidate with the same identity | E,F | same price on CarDekho: Hyundai Creta Electric Excellence HC Knight; Hyundai Creta Electric Excellence HC DT; Hyundai Creta Electric Smart (O) LR HC; battery 51.4 vs 42 kWh; price 2218500 vs 2145500 |
| Creta Electric | Smart (O) LR 51.4 kWh (HC) (Electric, 2226700) | Hyundai Creta Electric Smart (O) LR HC (Electric, 2226700) | no candidate with the same identity | A | kWh 51.4 is in the CarWale name only |
| Creta Electric | Excellence Knight Edition 42.0 kWh Dual Tone (HC) (Electric, 2233400) | Hyundai Creta Electric Excellence HC Knight DT (Electric, 2233400) | no candidate with the same identity | A | kWh 42 is in the CarWale name only |
| Creta Electric | Excellence LR 51.4 kWh (Electric, 2367200) | Hyundai Creta Electric Excellence LR (Electric, 2367200) | no candidate with the same identity | A | kWh 51.4 is in the CarWale name only |
| Creta Electric | Excellence LR Knight Edition 51.4 kWh (Electric, 2382100) | Hyundai Creta Electric Excellence LR Knight (Electric, 2382100) | no candidate with the same identity | A | kWh 51.4 is in the CarWale name only |
| Creta Electric | Excellence LR 51.4 kWh Dual Tone (Electric, 2382200) | Hyundai Creta Electric Excellence LR DT (Electric, 2382200) | no candidate with the same identity | A | kWh 51.4 is in the CarWale name only |
| Creta Electric | Excellence LR 51.4 kWh Dual Tone Knight Edition (Electric, 2397100) | Hyundai Creta Electric Excellence LR Knight DT (Electric, 2397100) | no candidate with the same identity | A | kWh 51.4 is in the CarWale name only |
| Creta Electric | Excellence LR 51.4 kWh Lounge Edition (Electric, 2434100) | Hyundai Creta Electric Excellence LR Lounge Edition (Electric, 2434100) | no candidate with the same identity | A | kWh 51.4 is in the CarWale name only |
| Creta Electric | Excellence LR 51.4 kWh (HC) (Electric, 2440200) | Hyundai Creta Electric Excellence LR HC (Electric, 2440200) | no candidate with the same identity | A | kWh 51.4 is in the CarWale name only |
| Creta Electric | Excellence LR 51.4 kWh Dual Tone Lounge Edition (Electric, 2449100) | Hyundai Creta Electric Excellence LR Lounge Edition DT (Electric, 2449100) | no candidate with the same identity | A | kWh 51.4 is in the CarWale name only |
| Creta Electric | Excellence LR Knight Edition 51.4 kWh (HC) (Electric, 2455100) | Hyundai Creta Electric Excellence LR HC Knight (Electric, 2455100) | no candidate with the same identity | A | kWh 51.4 is in the CarWale name only |
| Creta Electric | Excellence LR 51.4 kWh Dual Tone (HC) (Electric, 2455200) | Hyundai Creta Electric Excellence LR HC DT (Electric, 2455200) | no candidate with the same identity | A | kWh 51.4 is in the CarWale name only |
| Creta Electric | Excellence LR 51.4 kWh Dual Tone (HC) Knight Edition (Electric, 2470100) | Hyundai Creta Electric Excellence LR HC Knight DT (Electric, 2470100) | no candidate with the same identity | A | kWh 51.4 is in the CarWale name only |
| Creta Electric | Excellence LR Lounge Edition 51.4 kWh (HC) (Electric, 2507100) | Hyundai Creta Electric Excellence LR HC Lounge Edition (Electric, 2507100) | no candidate with the same identity | A | kWh 51.4 is in the CarWale name only |
| Creta Electric | Excellence LR Lounge Edition 51.4 kWh Dual Tone (HC) (Electric, 2522100) | Hyundai Creta Electric Excellence LR HC Lounge Edition DT (Electric, 2522100) | no candidate with the same identity | A | kWh 51.4 is in the CarWale name only |
| Syros EV | HTK 42.0 kWh (Electric, 1075719) | Kia Syros EV HTK (Electric, 1349900) | no candidate with the same identity | A,E | kWh 42 is in the CarWale name only; price 1075719 vs 1349900 |
| Syros EV | HTK+  42.0 kWh (Electric, 1499900) | Kia Syros EV HTK Plus (Electric, 1499900) | no candidate with the same identity | A | kWh 42 is in the CarWale name only |
| Syros EV | HTX 42.0 kWh (Electric, 1599900) | Kia Syros EV HTX (Electric, 1599900) | no candidate with the same identity | A | kWh 42 is in the CarWale name only |
| Syros EV | HTK+ ER  51.4 kWh (Electric, 1699900) | Kia Syros EV HTK Plus ER (Electric, 1699900) | no candidate with the same identity | A | kWh 51.4 is in the CarWale name only |
| Syros EV | HTX ER  51.4 kWh (Electric, 1799900) | Kia Syros EV HTX ER (Electric, 1799900) | no candidate with the same identity | A | kWh 51.4 is in the CarWale name only |
| Syros EV | HTX+ ER  51.4 kWh (Electric, 1949900) | Kia Syros EV HTX Plus ER (Electric, 1949900) | no candidate with the same identity | A | kWh 51.4 is in the CarWale name only |
| Syros EV | X-Line ER 51.4 kWh (Electric, 1999900) | Kia Syros EV X-Line ER (Electric, 1999900) | no candidate with the same identity | A | kWh 51.4 is in the CarWale name only |
| Comet EV | Executive 17.3 kWh (Electric, 647865) | MG Comet EV Executive (Electric, 789800) | no candidate with the same identity | A,E | kWh 17.3 is in the CarWale name only; price 647865 vs 789800 |
| Comet EV | Excite 17.3 kWh (Electric, 757381) | MG Comet EV Excite (Electric, 899800) | no candidate with the same identity | A,E | kWh 17.3 is in the CarWale name only; price 757381 vs 899800 |
| Comet EV | Excite FC 17.4 kWh (Electric, 784381) | MG Comet EV Excite FC (Electric, 926800) | no candidate with the same identity | A,E | kWh 17.4 is in the CarWale name only; price 784381 vs 926800 |
| Comet EV | Exclusive 17.3 kWh Dual Tone (Electric, 852275) | MG Comet EV Exclusive (Electric, 989800) | no candidate with the same identity | D,E | dual tone on one site; price 852275 vs 989800 |
| Comet EV | Exclusive FC 17.4 kWh Dual Tone (Electric, 879275) | MG Comet EV Exclusive FC (Electric, 1016800) | no candidate with the same identity | D,E | dual tone on one site; price 879275 vs 1016800 |
| Hector Tomahawk EV | Excite 69.2 kWh 7 STR (Electric, 1715738) | Excite 7-Seater (Electric, 2024800) | no candidate with the same identity | A,E | kWh 69.2 is in the CarWale name only; price 1715738 vs 2024800 |
| Hector Tomahawk EV | Exclusive 69.2 kWh 7 STR (Electric, 1941045) | Exclusive 7-Seater (Electric, 2274800) | no candidate with the same identity | A,E | kWh 69.2 is in the CarWale name only; price 1941045 vs 2274800 |
| Hector Tomahawk EV | Essence 69.2 kWh 5 STR (Electric, 2041045) | Essence 5-Seater (Electric, 2374800) | no candidate with the same identity | A,E | kWh 69.2 is in the CarWale name only; price 2041045 vs 2374800 |
| Hector Tomahawk EV | Essence 69.2 kWh 7 STR (Electric, 2091045) | Essence 7-Seater (Electric, 2424800) | no candidate with the same identity | A,E | kWh 69.2 is in the CarWale name only; price 2091045 vs 2424800 |
| Hector Tomahawk PHEV | Exclusive Plug-in Hybrid (Electric + Petrol) Automatic (Petrol Hybrid, 2376797) | MG Hector Tomahawk PHEV Exclusive 7-Seater (Petrol, 2569800) | no candidate with the same identity | C,D,E,F | fuel Petrol Hybrid vs Petrol; descriptor words: in, plug; different words: 7; price 2376797 vs 2569800 |
| Hector Tomahawk PHEV | Essence Plug-in Hybrid (Electric + Petrol) Automatic (Petrol Hybrid, 2586797) | MG Hector Tomahawk PHEV Essence 7-Seater (Petrol, 2779800) | no candidate with the same identity | C,D,E,F | fuel Petrol Hybrid vs Petrol; descriptor words: in, plug; different words: 7; price 2586797 vs 2779800 |
| ZS EV | Executive 50.3 kWh (Electric, 1550082) | MG ZS EV Executive (Electric, 1799000) | no candidate with the same identity | A,E | kWh 50.3 is in the CarWale name only; price 1550082 vs 1799000 |
| ZS EV | Excite Pro 50.3 kWh (Electric, 1613485) | MG ZS EV Excite Pro (Electric, 1874600) | no candidate with the same identity | A,E | kWh 50.3 is in the CarWale name only; price 1613485 vs 1874600 |
| ZS EV | Exclusive Plus 50.3 kWh Dark Grey (Electric, 1713485) | MG ZS EV Exclusive Plus (Electric, 1999600) | no candidate with the same identity | E,F | different words: dark, grey; price 1713485 vs 1999600 |
| ZS EV | Exclusive Plus 50.3 kWh Dual Tone Iconic Ivory (Electric, 1713485) | MG ZS EV Exclusive Plus (Electric, 1999600) | no candidate with the same identity | E,F | different words: dual, iconic, ivory, tone; price 1713485 vs 1999600 |
| ZS EV | 100-Year 50.3 kWh Dual Tone [special] (Electric, 1713485) | MG ZS EV 100 Year Limited Edition (Electric, 1974600) | no candidate with the same identity | E,F | different words: dual, limited, tone; price 1713485 vs 1974600 |
| ZS EV | Essence 50.3 kWh Dark Grey (Electric, 1813485) | MG ZS EV Essence (Electric, 2074600) | no candidate with the same identity | E,F | different words: dark, grey; price 1813485 vs 2074600 |
| ZS EV | Essence 50.3 kWh Iconic Ivory (Electric, 1813485) | MG ZS EV Essence (Electric, 2074600) | no candidate with the same identity | E,F | different words: iconic, ivory; price 1813485 vs 2074600 |
| BE 6 Sporteq | One 59.0 kWh No Charger (Electric, 1545392) | Mahindra BE 6 SPORTEQ One 59kWh (Electric, 1945000) | 1 candidates share the identity or price differs | E | price 1545392 vs 1945000 |
| BE 6 Sporteq | Two 59.0 kWh No Charger (Electric, 1695392) | Mahindra BE 6 SPORTEQ Two 59kWh (Electric, 2095000) | 1 candidates share the identity or price differs | E | price 1695392 vs 2095000 |
| BE 6 Sporteq | Three 59.0 kWh No Charger (Electric, 1795392) | Mahindra BE 6 SPORTEQ Three 59kWh (Electric, 2195000) | 1 candidates share the identity or price differs | E | price 1795392 vs 2195000 |
| BE 6 Sporteq | Three 70.0 kWh No Charger (Electric, 1845441) | Mahindra BE 6 SPORTEQ Three 70kWh (Electric, 2295000) | 1 candidates share the identity or price differs | E | price 1845441 vs 2295000 |
| BE 6 Sporteq | Three Plus 70.0 kWh No Charger (Electric, 1945441) | Mahindra BE 6 SPORTEQ Three Plus 70kWh (Electric, 2395000) | 1 candidates share the identity or price differs | E | same price on CarDekho: Mahindra BE 6 SPORTEQ One 59kWh; price 1945441 vs 2395000 |
| BE 6 Sporteq | FE 79.0 kWh No Charger (Electric, 1945490) | Mahindra BE 6 SPORTEQ FE 79kWh (Electric, 2445000) | 1 candidates share the identity or price differs | E | same price on CarDekho: Mahindra BE 6 SPORTEQ One 59kWh; price 1945490 vs 2445000 |
| BE 6 Sporteq | Three Plus 79.0 kWh No Charger (Electric, 1995490) | Mahindra BE 6 SPORTEQ Three Plus 79kWh (Electric, 2495000) | 1 candidates share the identity or price differs | E | price 1995490 vs 2495000 |
| BE 6 Sporteq | One 59.0 kWh 11.2kW Charger (Electric, 2020000) | Mahindra BE 6 SPORTEQ One 59kWh (Electric, 1945000) | no candidate with the same identity | E,F | different words: acfc; price 2020000 vs 1945000 |
| BE 6 Sporteq | Two 59.0 kWh 11.2kW Charger (Electric, 2170000) | Mahindra BE 6 SPORTEQ Two 59kWh (Electric, 2095000) | no candidate with the same identity | E,F | different words: acfc; price 2170000 vs 2095000 |
| BE 6 Sporteq | FE Four 79.0 kWh No Charger (Electric, 2195490) | Mahindra BE 6 SPORTEQ FE Four 79kWh (Electric, 2695000) | 1 candidates share the identity or price differs | E | same price on CarDekho: Mahindra BE 6 SPORTEQ Three 59kWh; price 2195490 vs 2695000 |
| BE 6 Sporteq | Four 79.0 kWh No Charger (Electric, 2195490) | Mahindra BE 6 SPORTEQ Four 79kWh (Electric, 2695000) | 1 candidates share the identity or price differs | E | same price on CarDekho: Mahindra BE 6 SPORTEQ Three 59kWh; price 2195490 vs 2695000 |
| BE 6 Sporteq | Launch Edition 79.0 kWh No Charger (Electric, 2195490) | Mahindra BE 6 SPORTEQ Launch Edition 79kWh (Electric, 2695000) | 1 candidates share the identity or price differs | E | same price on CarDekho: Mahindra BE 6 SPORTEQ Three 59kWh; price 2195490 vs 2695000 |
| BE 6 Sporteq | Three 59.0 kWh 11.2kW Charger (Electric, 2270000) | Mahindra BE 6 SPORTEQ Three 59kWh (Electric, 2195000) | no candidate with the same identity | E,F | different words: acfc; price 2270000 vs 2195000 |
| BE 6 Sporteq | Three 70.0 kWh 11.2kW Charger (Electric, 2370000) | Mahindra BE 6 SPORTEQ Three 70kWh (Electric, 2295000) | no candidate with the same identity | E,F | different words: acfc; price 2370000 vs 2295000 |
| BE 6 Sporteq | Three Plus 70.0 kWh 11.2kW Charger (Electric, 2470000) | Mahindra BE 6 SPORTEQ Three Plus 70kWh (Electric, 2395000) | no candidate with the same identity | E,F | different words: acfc; price 2470000 vs 2395000 |
| BE 6 Sporteq | FE 79.0 kWh 11.2kW Charger (Electric, 2520000) | Mahindra BE 6 SPORTEQ FE 79kWh (Electric, 2445000) | no candidate with the same identity | E,F | different words: acfc; price 2520000 vs 2445000 |
| BE 6 Sporteq | Three Plus 79.0 kWh 11.2kW Charger (Electric, 2570000) | Mahindra BE 6 SPORTEQ Three Plus 79kWh (Electric, 2495000) | no candidate with the same identity | E,F | different words: acfc; price 2570000 vs 2495000 |
| BE 6 Sporteq | FE Four 79.0 kWh 11.2kW Charger (Electric, 2770000) | Mahindra BE 6 SPORTEQ FE Four 79kWh (Electric, 2695000) | no candidate with the same identity | E,F | different words: acfc; price 2770000 vs 2695000 |
| BE 6 Sporteq | Launch Edition 79.0 kWh 11.2kW Charger (Electric, 2770000) | Mahindra BE 6 SPORTEQ Launch Edition 79kWh (Electric, 2695000) | no candidate with the same identity | E,F | different words: acfc; price 2770000 vs 2695000 |
| BE 6 Sporteq | Four 79.0 kWh 11.2kW Charger (Electric, 2770000) | Mahindra BE 6 SPORTEQ Four 79kWh (Electric, 2695000) | no candidate with the same identity | E,F | different words: acfc; price 2770000 vs 2695000 |
| XUV 3XO EV | AX5 39.4 kWh with No Charger (Electric, 1389000) | Mahindra XUV 3XO EV AX5 (Electric, 1388999) | no candidate with the same identity | D | descriptor words: with |
| XUV 3XO EV | AX5 39.4 kWh with Charger (Electric, 1439000) | Mahindra XUV 3XO EV AX5 (Electric, 1388999) | no candidate with the same identity | E,F | different words: charger, with; price 1439000 vs 1388999 |
| XUV 3XO EV | AX7 L 39.4 kWh with No Charger (Electric, 1496000) | Mahindra XUV 3XO EV AX7L (Electric, 1495999) | no candidate with the same identity | D | descriptor words: with |
| XUV 3XO EV | AX7 L 39.4 kWh with Charger (Electric, 1546000) | Mahindra XUV 3XO EV AX7L (Electric, 1495999) | no candidate with the same identity | E,F | different words: charger, with; price 1546000 vs 1495999 |
| XUV400 | EC PRO 34.5 kWh (Electric, 1549000) | Mahindra XUV400 EV EC Pro 34.5 kWh (Electric, 1548999) | links | B | page says 'Mahindra XUV400 EV EC Pro 345 kWh', list says 'Mahindra XUV400 EV EC Pro 34.5 kWh' |
| XUV400 | EL PRO 34.5 kWh (Electric, 1674000) | Mahindra XUV400 EV EL Pro 34.5 kWh (Electric, 1674000) | links | B | page says 'Mahindra XUV400 EV EL Pro 345 kWh', list says 'Mahindra XUV400 EV EL Pro 34.5 kWh' |
| XUV400 | EL PRO 34.5 kWh Dual Tone (Electric, 1694000) | Mahindra XUV400 EV EL Pro DT 34.5 kWh (Electric, 1694000) | links | B | page says 'Mahindra XUV400 EV EL Pro DT 345 kWh', list says 'Mahindra XUV400 EV EL Pro DT 34.5 kWh' |
| XUV400 | EL PRO 39.4 kWh (Electric, 1748967) | Mahindra XUV400 EV EL Pro 39.4 kWh (Electric, 1749000) | links | B | page says 'Mahindra XUV400 EV EL Pro 394 kWh', list says 'Mahindra XUV400 EV EL Pro 39.4 kWh' |
| XUV400 | EL PRO 39.4 kWh Dual Tone (Electric, 1768987) | Mahindra XUV400 EV EL Pro DT 39.4 kWh (Electric, 1769000) | links | B | page says 'Mahindra XUV400 EV EL Pro DT 394 kWh', list says 'Mahindra XUV400 EV EL Pro DT 39.4 kWh' |
| Invicto | Zeta Plus Hybrid (Electric + Petrol) Automatic 7 STR (Petrol Hybrid, 2502400) | Maruti Suzuki Invicto Zeta Plus 7Str (Petrol, 2502400) | no candidate with the same identity | C | fuel Petrol Hybrid vs Petrol |
| Invicto | Zeta Plus Hybrid (Electric + Petrol) Automatic 8 STR (Petrol Hybrid, 2537300) | Maruti Suzuki Invicto Zeta Plus 8Str (Petrol, 2537300) | no candidate with the same identity | C | fuel Petrol Hybrid vs Petrol |
| Invicto | Alpha Plus Hybrid (Electric + Petrol) Automatic 7 STR (Petrol Hybrid, 2870500) | Maruti Suzuki Invicto Alpha Plus 7Str (Petrol, 2870500) | no candidate with the same identity | C | fuel Petrol Hybrid vs Petrol |
| X-Trail | Mild Hybrid CVT Petrol Automatic (Petrol, 4819862) | Nissan X-Trail STD (Petrol, 4819862) | no candidate with the same identity | F | different words: std |
| Tigor EV | XE 26.0 kWh (Electric, 1249000) | Tata Tigor EV XE (Electric, 1249000) | no candidate with the same identity | A | kWh 26 is in the CarWale name only |
| Tigor EV | XT 26.0 kWh (Electric, 1299000) | Tata Tigor EV XT (Electric, 1299000) | no candidate with the same identity | A | kWh 26 is in the CarWale name only |
| Tigor EV | XZ Plus 26.0 kWh (Electric, 1349000) | Tata Tigor EV XZ Plus (Electric, 1349000) | no candidate with the same identity | A | kWh 26 is in the CarWale name only |
| Tigor EV | XZ Plus LUX 26.0 kWh (Electric, 1375000) | Tata Tigor EV XZ Plus LUX (Electric, 1375000) | no candidate with the same identity | A | kWh 26 is in the CarWale name only |
| Camry | Elegant Hybrid (Electric + Petrol) Automatic (Petrol Hybrid, 4869000) | Toyota Camry Elegance (Petrol, 4869000) | no candidate with the same identity | C,F | fuel Petrol Hybrid vs Petrol; different words: elegance, elegant |
| Camry | Sprint Edition Hybrid (Electric + Petrol) Automatic Dual Tone (Petrol Hybrid, 4869000) | Toyota Camry Sprint Edition (Petrol, 4869000) | no candidate with the same identity | C,D | fuel Petrol Hybrid vs Petrol; dual tone on one site |
| Camry | Elegant Hybrid (Electric + Petrol) Automatic Platinum White Pearl (Petrol Hybrid, 4889000) | Toyota Camry Elegance (Petrol, 4869000) | no candidate with the same identity | C,F | fuel Petrol Hybrid vs Petrol; different words: elegance, elegant, pearl, platinum, white |
| Camry | Sprint Edition Hybrid (Electric + Petrol) Automatic Platinum White Pearl (Petrol Hybrid, 4889000) | Toyota Camry Sprint Edition (Petrol, 4869000) | no candidate with the same identity | C,F | fuel Petrol Hybrid vs Petrol; different words: pearl, platinum, white |
| Fortuner Legender | 4X2 2WD Diesel Turbo Automatic Dual Tone (Diesel, 4335000) | Toyota Fortuner Legender 4x2 AT (Diesel, 4335000) | no candidate with the same identity | D | dual tone on one site |
| Fortuner Legender | 4X4 4WD Diesel Turbo Manual Dual Tone (Diesel, 4553000) | Toyota Fortuner Legender 4x4 (Diesel, 4553000) | no candidate with the same identity | D | dual tone on one site |
| Fortuner Legender | 4X4 4WD Mild Hybrid (Electric + Diesel) Turbo Automatic Dual Tone (Diesel Mild Hybrid, 4877000) | Toyota Fortuner Legender 4x4 (Diesel, 4553000) | no candidate with the same identity | C,D,E | same price on CarDekho: Toyota Fortuner Legender Neo Drive; fuel Diesel Mild Hybrid vs Diesel (not every CarWale version is a strong hybrid); dual tone on one site; price 4877000 vs 4553000 |
| Urban Cruiser Ebella | E3 61.0 kWh (Electric, 2360000) | Toyota Urban Cruiser EBELLA E3 (Electric, 2360000) | no candidate with the same identity | A | kWh 61 is in the CarWale name only |
| Urban Cruiser Ebella | E3 61.0 kWh Dual Tone (Electric, 2380000) | Toyota Urban Cruiser EBELLA E3 (Electric, 2360000) | no candidate with the same identity | D,E | dual tone on one site; price 2380000 vs 2360000 |

## What the table shows beyond the plan

- **XUV400 (B)** is the only block where the *list* names agree: the old linker links all 5 versions, then the page-name check discards each variant page (the variant page prints `345 kWh` for 34.5 and `394 kWh` for 39.4).
- **ZR-V and X-Trail** are listed in the plan as descriptor cases (D) but the descriptors are not what blocks them: CarWale's name has the word `Sport` (ZR-V) or only fuel and gearbox words (X-Trail), CarDekho's has `Hybrid` or `STD`. After every fold the trim words still differ (`sport` vs none; none vs `std`), so they are **F**. No rule in the plan links them; they go to review.
- **Camry**: `Elegant` vs `Elegance` is F, as the plan says. `Sprint Edition ... Dual Tone` has the same price as CarDekho's `Sprint Edition`; the only differences are the hybrid label (C) and CarWale's `Dual Tone`. Colour names (`Platinum White Pearl`) are F.
- **`Dual Tone` on one site only** (Fortuner Legender 2 versions, Camry Sprint, Comet 2, Urban Cruiser Ebella E3) is not in the plan's descriptor list. It is the whole reason Fortuner Legender cannot link, so it is listed here as D and handled as a separate, price-guarded rule (see the commit message and the rule list in `match.py`).
- **`with No Charger`** (XUV 3XO EV, 2 versions): `trim_tokens` already drops `no charger` but leaves the word `with`. Not in the plan; found by this table.
- **BE 6 Sporteq `11.2kW Charger` versions (10) and XUV 3XO EV `with Charger` (2)** carry a charger word CarDekho does not (F); their prices also differ the other way (E). They stay unlinked.
- **ZS EV colour names** (`Dark Grey`, `Iconic Ivory`) are F.
- **Hector Tomahawk PHEV**: besides C and `Plug-in` (D), CarDekho says `7-Seater` and CarWale gives no seat count; the existing implied-seat rule needs an agreeing price, and the prices differ (E).
- **Creta Electric `Excellence 51.4 kWh Dual Tone`** (CarWale 2,218,500) has no CarDekho counterpart: the nearest name is a 42 kWh `Excellence HC DT` at the same price. The batteries differ, so it must stay unlinked.

