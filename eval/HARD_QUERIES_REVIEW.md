# Hard queries: owner review (DRAFT, not frozen)

`eval/hard_queries.jsonl` has 40 drafted queries (`"draft": true` on every line). Labels were written from what a careful reader takes from the query, before any LLM run and without tuning to the parser. Tick **OK** or write the change you want; once you approve, the `draft` flag is removed and the file is frozen.

Kinds: 10 indirect_limit, 10 hinglish, 12 multi_clause (rules leave at least one token unexplained, so `llm_parse` would consider them), and 8 control (rules explain everything; the LLM must not change them).

Label vocabulary is `eval/README.md`. A label lists only what the query *requires*; wishes ("if possible", "ideally", "matters") are deliberately left out. Unlabellable parts are flagged in the rationale.

| id | kind | query | labels | rationale | OK? |
|---|---|---|---|---|---|
| hq-001 | indirect_limit | can't spend more than my 9 lakh loan sanction | budget ≤ 9 lakh | Loan sanction is the ceiling on spending. | [ ] |
| hq-002 | indirect_limit | bank has approved 12 lakh only, that's the ceiling, need an automatic hatchback | budget ≤ 12 lakh; transmission_family: automatic; body_include: hatchback | Approved amount stated as a ceiling. | [ ] |
| hq-003 | indirect_limit | my garage is only 4 metres long, need a small petrol hatchback | fuel_include: petrol; body_include: hatchback | Length limit (4 m) has no label key and is not scored; only petrol and hatchback are labelled. (length limit 4 m is not expressible in the label schema; labelled only the rest) | [ ] |
| hq-004 | indirect_limit | papa ne bola 7 lakh se upar ka nahi lena, manual petrol | budget ≤ 7 lakh; transmission_family: manual; fuel_include: petrol | '7 lakh se upar ka nahi' = nothing above 7 lakh. | [ ] |
| hq-005 | indirect_limit | we are 7 people in the family and all travel together, diesel | seats_min: 7; fuel_include: diesel | Seven travellers need at least seven seats. | [ ] |
| hq-006 | indirect_limit | my salary is 6 lakh a year so nothing above 5 lakh | budget ≤ 5 lakh | The stated cap is 5 lakh; the salary is context. | [ ] |
| hq-007 | indirect_limit | I have exactly 10 lakh in hand, not a rupee more, want a sedan | budget ≤ 10 lakh; body_include: sedan | 'Not a rupee more' than 10 lakh = ceiling. | [ ] |
| hq-008 | indirect_limit | must clear speed breakers on my village road, at least 200 mm of ground clearance, diesel | min ground_clearance_mm 200; fuel_include: diesel | Explicit minimum 200 mm. | [ ] |
| hq-009 | indirect_limit | boot should swallow two big suitcases, at least 400 litres, SUV | min boot_space_litres 400; body_include: suv | Explicit minimum 400 litres. | [ ] |
| hq-010 | indirect_limit | I can't drive a manual because of my knee, petrol hatchback under 8 lakh | transmission_family: automatic; fuel_include: petrol; body_include: hatchback; budget ≤ 8 lakh | Cannot drive manual means automatic only. | [ ] |
| hq-011 | hinglish | bhai 15 lakh ke andar koi mast diesel gaadi bata, jisme sunroof ho | budget ≤ 15 lakh; fuel_include: diesel; required_features: sunroof | 'ke andar' = within; sunroof is required ('jisme ... ho'). | [ ] |
| hq-012 | hinglish | mujhe kuch aisa chahiye jo petrol ho par CNG nahi, 6 seater, 14 lakh se kam | fuel_include: petrol; fuel_exclude: cng; seats_min: 6; budget ≤ 14 lakh | Petrol wanted, CNG excluded, six seats, under 14 lakh. | [ ] |
| hq-013 | hinglish | automatic hi chahiye, diesel mat dikhana, 11 lakh tak ka scene hai | transmission_family: automatic; fuel_exclude: diesel; budget ≤ 11 lakh | 'hi chahiye' = required; 'mat dikhana' = exclude. | [ ] |
| hq-014 | hinglish | sasti si hatchback jisme 4 airbag toh ho hi, 5 lakh ke aas paas | min airbags 4; body_include: hatchback; budget ≈ 5 lakh | 'toh ho hi' makes 4 airbags a minimum; 'aas paas' = around. | [ ] |
| hq-015 | hinglish | ek aisi SUV jo Tata ki na ho aur Mahindra ki bhi nahi, 13 lakh tak | body_include: suv; makes_exclude: Tata, Mahindra; budget ≤ 13 lakh | Two makes excluded. | [ ] |
| hq-016 | hinglish | yaar sunroof wali gaadi chahiye, par 10 lakh se ek paisa zyada nahi | required_features: sunroof; budget ≤ 10 lakh | 'ek paisa zyada nahi' = hard ceiling. | [ ] |
| hq-017 | hinglish | family ke liye badi gaadi, kam se kam 7 log baith sakein, diesel, 20 lakh ceiling | seats_min: 7; fuel_include: diesel; budget ≤ 20 lakh | At least 7 seated, diesel, 20 lakh ceiling. | [ ] |
| hq-018 | hinglish | chhoti hatchback, shehar ke liye, 6 lakh ke neeche, automatic zaroori | body_include: hatchback; budget ≤ 6 lakh; transmission_family: automatic | 'neeche' = below; 'zaroori' = must. | [ ] |
| hq-019 | hinglish | Maruti ya Hyundai, dono mein se koi bhi, 9 lakh tak, petrol | makes_include: Maruti Suzuki, Hyundai; budget ≤ 9 lakh; fuel_include: petrol | Either make is acceptable. | [ ] |
| hq-020 | hinglish | kuch bhi chalega bas CVT nahi, 12 lakh tak | transmission_exclude: cvt; budget ≤ 12 lakh | CVT excluded; ceiling 12 lakh. | [ ] |
| hq-021 | multi_clause | compact SUV, but not a Tata or Mahindra, with a sunroof and at least 6 airbags, between 10 and 13 lakh, and it shouldn't be a diesel | body_include: suv; makes_exclude: Tata, Mahindra; required_features: sunroof; min airbags 6; budget ≥ 10 lakh; budget ≤ 13 lakh; fuel_exclude: diesel | Six independent clauses. | [ ] |
| hq-022 | multi_clause | first I want a petrol hatchback, nothing over 7 lakh; it must have Android Auto and cruise control | fuel_include: petrol; body_include: hatchback; budget ≤ 7 lakh; required_features: android_auto, cruise_control | Two required features after a semicolon. | [ ] |
| hq-023 | multi_clause | office commute of 40 km daily, CNG, automatic if possible but manual is ok, under 8 lakh | fuel_include: cng; budget ≤ 8 lakh | Automatic is only a preference ('if possible'), so not labelled. | [ ] |
| hq-024 | multi_clause | something with ventilated seats and a 360 camera, SUV, automatic, ADAS too, up to 30 lakh, and the Kia dealer near me is a nightmare so not a Kia | required_features: ventilated_seats, camera_360, adas; body_include: suv; transmission_family: automatic; budget ≤ 30 lakh; makes_exclude: Kia | Three features, body, gearbox, ceiling, one excluded make. | [ ] |
| hq-025 | multi_clause | 7 seater, diesel, manual is fine, but no Mahindra, under 17 lakh, and boot at least 300 litres | seats_min: 7; fuel_include: diesel; makes_exclude: Mahindra; budget ≤ 17 lakh; min boot_space_litres 300 | 'Manual is fine' adds no constraint. | [ ] |
| hq-026 | multi_clause | Honda or Toyota sedan, petrol, automatic, I'd pay up to 16 lakh but would stretch a bit for good safety | makes_include: Honda, Toyota; body_include: sedan; fuel_include: petrol; transmission_family: automatic; budget ≤ 16 lakh | Stated ceiling 16 lakh; the stretch is vague, so the ceiling is labelled. | [ ] |
| hq-027 | multi_clause | not too big, not too small, hatchback or compact SUV, petrol, under 11 lakh, with wireless charging | body_include: hatchback, suv; fuel_include: petrol; budget ≤ 11 lakh; required_features: wireless_charging | Either body type is acceptable. | [ ] |
| hq-028 | multi_clause | buying for my mother who is 68 so easy entry, automatic, no diesel, 4 airbags at least, 10 lakh max | transmission_family: automatic; fuel_exclude: diesel; min airbags 4; budget ≤ 10 lakh | Easy entry is a wish; the rest are stated limits. | [ ] |
| hq-029 | multi_clause | I drive 2000 km a month so mileage matters, diesel only, SUV, 14 to 17 lakh, 5 star safety if possible | fuel_include: diesel; body_include: suv; budget ≥ 14 lakh; budget ≤ 17 lakh | 5 star is only 'if possible'; mileage is a wish. | [ ] |
| hq-030 | multi_clause | ek MPV chahiye, 8 seater, 18 lakh se kam, diesel, aur sunroof bilkul nahi | body_include: mpv; seats_min: 8; budget ≤ 18 lakh; fuel_include: diesel; excluded_features: sunroof; expect_empty: True | Hinglish plus five clauses. The catalogue has no 8-seat diesel MPV under 18 lakh without a sunroof; the label is what the query asks. | [ ] |
| hq-031 | multi_clause | electric car with minimum 300 km real range, 20 lakh se kam, and no sunroof please | fuel_include: electric; min ev_range_km 300; budget ≤ 20 lakh; excluded_features: sunroof | Range minimum, ceiling and an excluded feature. | [ ] |
| hq-032 | multi_clause | something along the lines of a Creta but cheaper, up to 11 lakh, petrol, and not a Hyundai | reference_models: Creta; budget ≤ 11 lakh; fuel_include: petrol; makes_exclude: Hyundai | 'Like Creta' is a reference only; 'cheaper' is a wish. | [ ] |
| hq-033 | control | petrol automatic hatchback under 9 lakh chahiye | fuel_include: petrol; transmission_family: automatic; body_include: hatchback; budget ≤ 9 lakh | Fully rule-handled control. | [ ] |
| hq-034 | control | diesel SUV with 7 seats up to 22 lakh | fuel_include: diesel; body_include: suv; seats_min: 7; budget ≤ 22 lakh | Control. | [ ] |
| hq-035 | control | manual CNG hatchback below 7 lakh | transmission_family: manual; fuel_include: cng; body_include: hatchback; budget ≤ 7 lakh | Control. | [ ] |
| hq-036 | control | sedan with sunroof, automatic, between 10 and 14 lakh | body_include: sedan; required_features: sunroof; transmission_family: automatic; budget ≥ 10 lakh; budget ≤ 14 lakh | Control. | [ ] |
| hq-037 | control | Kia petrol automatic SUV under 16 lakh | makes_include: Kia; fuel_include: petrol; transmission_family: automatic; body_include: suv; budget ≤ 16 lakh | Control. | [ ] |
| hq-038 | control | hatchback with at least 6 airbags, 8 lakh tak | body_include: hatchback; min airbags 6; budget ≤ 8 lakh | Control. | [ ] |
| hq-039 | control | electric car under 20 lakh with a sunroof | fuel_include: electric; budget ≤ 20 lakh; required_features: sunroof | Control. | [ ] |
| hq-040 | control | Honda petrol automatic sedan 12 lakh tak | makes_include: Honda; fuel_include: petrol; transmission_family: automatic; body_include: sedan; budget ≤ 12 lakh | Control. | [ ] |
