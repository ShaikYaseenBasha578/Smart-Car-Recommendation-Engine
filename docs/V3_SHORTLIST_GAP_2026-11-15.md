# V3 vs owner shortlists on the new catalogue: why v3 fell behind (2026-11-15)

Diagnosis only. No code, data, labels or shortlist sheet changed. `--llm off`, `CARREC_CATALOGUE_DIR=data/catalogue_v3`, worktree `~/carrec_worktrees/recsys-v3` (feat/recsys-v3), eval process patches only. Scratch scripts in `/tmp/sg/`.

## Summary

1. The drop is the 30 new models, not the 632 new variants of old models: on the new catalogue with the 30 new models removed v3 scores recall@8 0.755 / MRR 0.802 (current engine 0.745 / 0.849); with them 0.655 / 0.762 (current 0.720 / 0.832). Adding the new models costs v3 0.100 recall, the current engine 0.025.
2. Cause in v3: a criterion is the mean of its known fields (`criteria.py:221-250`), so a nearly blank criterion can be perfect (tech_assist is 0.95+ on 44 to 52 % of new variants with 50 % or more of its weight blank; 0 % of old rows). The KB records the features a new model has and leaves the others blank (True share of known sunroof cells 0.77 vs 0.48 in old rows; ABS, ESC, ADAS, HUD 100 % blank), and a wholly unknown running_cost drops out instead of counting as a weak known value. The coverage charge (0.15 x unknown share) differs by only 0.006 to 0.061 between displacer and pick against raw gaps of 0.04 to 0.21.
3. Coverage constant 0.15 / 0.30 / 0.50 / 0.75: recall@8 0.655 / 0.695 / 0.720 / 0.745, MRR 0.762 / 0.842 / 0.853 / 0.843, probe still returned 63 / 54 / 43 / 37. A heavier global charge buys recall at the cost of the unknown probe (it wants a blank between yes and no).
4. The current engine has no popularity, sales, brand or learned prior, and no single term explains its lead (switching any one off moves it by 0.005 to 0.03 recall; random variant ids change nothing). The one measurable piece is that unverified cars sort after verified ones (`ranking_adapter.py:200`, +0.03 recall); more telling, v3 with a blank valued at 0 reaches 0.745 / 0.832, the current engine's level. The difference is how a blank is valued.
5. The sheet is stale: all 191 picks are old models. Of 40 new-model entries in the 17 changed sheets, 31 are genuine fits, 3 weak, 6 blank-driven (blank ground clearance, mileage or sunroof passes the query).
6. Reviews: no measured gain. Models with no review row get no lift while reviewed models get +0.01 to +0.10; all aspects are active in every query; the owner signal is discounted twice (w x w); the expert class can never exceed 0.38 of its weight. The two probe failures are Dzire beating a blanked City / Slavia by 0.004 to 0.006, from a +0.038 review lift on 616 ratings.
7. Ranked candidates (section 7): blank prior in the criterion, coverage 0.30 to 0.50, refresh the shortlist, demote unverified required items, review fixes. Only the expert-scale denominator is a bug; the rest are design decisions for the owner.

## 1. Top 8 per query: v3 and the current engine (new catalogue)

Both engines on `data/catalogue_v3`, `LLM_PARSER=off`, v3 with reviews at 0.60 / 0.25 / 0.15 (reproduces run b: recall@8 0.655, MRR 0.7625; current 0.720 / 0.832). Notation: `n.Model[tag]`, n = rank; `[*]` = owner pick, `[N]` = not a pick, model new in the 1,464 catalogue, `[o]` = not a pick, model that existed before. "missing" = owner picks outside the top 8. A non-pick slot is a (i) new / (ii) old displacer; with up to 5 picks and 8 slots at least 3 slots per list are non-picks, so some displacement is unavoidable.

Totals over the 40 queries (191 picks):

| | Picks in top 8 | Picks missing | Non-pick slots: (i) new model | (ii) old model |
|---|---|---|---|---|
| v3 | 122 | 69 | 66 | 89 |
| current | 135 | 56 | 38 | 98 |

v3 gives 28 more slots to new models than the current engine (66 vs 38) and 9 fewer to old non-picks; the 13 picks it loses relative to the current engine are the bulk of the recall gap (13 / 191 = 0.068). 43 % of v3's non-pick slots are new models; 57 % are old models that the owner did not list (Venue, Syros, Thar Roxx, Alto K10, S-Presso, Altroz, ...), which staleness cannot explain.

**plain-01** I want a petrol hatchback under 8 lakh  (picks: MSIL Swift, Tata Tiago, Hy Grand i10 Nios, MSIL Baleno, MSIL WagonR)
- v3: 1.Hy Grand i10 Nios[*]; 2.MSIL Celerio[N]; 3.Hy i20[N]; 4.MSIL Alto K10[o]; 5.Tata Tiago[*]; 6.MSIL S-Presso[o]; 7.Ren Kwid[N]; 8.MSIL Baleno[*]  | missing: MSIL Swift, MSIL WagonR | non-pick slots: 3 new, 2 old
- cur: 1.MSIL Alto K10[o]; 2.MSIL Swift[*]; 3.Hy Grand i10 Nios[*]; 4.Toy Glanza[o]; 5.Tata Altroz[o]; 6.Ren Kwid[N]; 7.Tata Tiago[*]; 8.Hy i20[N]  | missing: MSIL Baleno, MSIL WagonR | non-pick slots: 2 new, 3 old

**plain-02** diesel SUV under 20 lakh  (picks: Hy Creta, Kia Seltos, M Scorpio-N, M XUV 3XO, Tata Nexon)
- v3: 1.Hy Venue[o]; 2.Kia Seltos[*]; 3.Hy Creta[*]; 4.Tata Nexon[*]; 5.Kia Syros[o]; 6.M Thar Roxx[o]; 7.M XUV 3XO[*]; 8.Tata Harrier[o]  | missing: M Scorpio-N | non-pick slots: 0 new, 4 old
- cur: 1.Tata Nexon[*]; 2.Hy Creta[*]; 3.M XUV 3XO[*]; 4.Hy Venue[o]; 5.Kia Syros[o]; 6.M Thar Roxx[o]; 7.Tata Harrier[o]; 8.Kia Seltos[*]  | missing: M Scorpio-N | non-pick slots: 0 new, 4 old

**plain-03** automatic sedan with sunroof  (picks: Hy Verna, Sk Slavia, VW Virtus, Honda City, MSIL Dzire)
- v3: 1.Hy Verna[*]; 2.MSIL Dzire[*]; 3.Tata Aeris[N]; 4.Honda City[*]; 5.VW Virtus[*]; 6.Sk Slavia[*]  | missing: - | non-pick slots: 1 new, 0 old
- cur: 1.MSIL Dzire[*]; 2.Honda City[*]; 3.VW Virtus[*]; 4.Sk Slavia[*]; 5.Hy Verna[*]; 6.Tata Aeris[N]  | missing: - | non-pick slots: 1 new, 0 old

**plain-04** 7 seater diesel SUV under 25 lakh  (picks: M Scorpio-N, M XUV 7XO, M Scorpio Classic, M Bolero)
- v3: 1.M XUV 7XO[*]; 2.Tata Safari[N]; 3.M Scorpio-N[*]; 4.Hy Alcazar[N]; 5.M Bolero Neo[N]; 6.M Scorpio Classic[*]; 7.M Bolero Neo Plus[N]; 8.M Bolero[*]  | missing: - | non-pick slots: 4 new, 0 old
- cur: 1.M Scorpio Classic[*]; 2.M Scorpio-N[*]; 3.Hy Alcazar[N]; 4.M XUV 7XO[*]; 5.Tata Safari[N]; 6.M Bolero[*]; 7.M Bolero Neo[N]; 8.M Bolero Neo Plus[N]  | missing: - | non-pick slots: 4 new, 0 old

**plain-05** electric car under 15 lakh  (picks: Tata Punch EV, Tata Nexon EV, MG Windsor EV, Tata Tiago EV)
- v3: 1.Tata Punch EV[*]; 2.Tata Nexon EV[*]; 3.Tata Tiago EV[*]; 4.MG Windsor EV[*]  | missing: - | non-pick slots: 0 new, 0 old
- cur: 1.Tata Punch EV[*]; 2.Tata Tiago EV[*]; 3.Tata Nexon EV[*]; 4.MG Windsor EV[*]  | missing: - | non-pick slots: 0 new, 0 old

**plain-06** CNG hatchback under 7 lakh  (picks: MSIL WagonR, Tata Tiago, MSIL Alto K10, MSIL S-Presso)
- v3: 1.MSIL Celerio[N]; 2.Tata Tiago[*]; 3.MSIL Alto K10[*]; 4.MSIL S-Presso[*]; 5.MSIL WagonR[*]  | missing: - | non-pick slots: 1 new, 0 old
- cur: 1.MSIL Alto K10[*]; 2.MSIL S-Presso[*]; 3.Tata Tiago[*]; 4.MSIL WagonR[*]; 5.MSIL Celerio[N]  | missing: - | non-pick slots: 1 new, 0 old

**plain-08** compact SUV with a sunroof under 15 lakh  (picks: Tata Nexon, M XUV 3XO, Hy Venue, Kia Syros, MSIL Brezza)
- v3: 1.M XUV 3XO[*]; 2.Hy Venue[*]; 3.Tata Nexon[*]; 4.Sk Kylaq[o]; 5.Tata Punch[N]; 6.Kia Sonet[N]; 7.MSIL Victoris[o]; 8.Toy Urban Cruiser Taisor[o]  | missing: Kia Syros, MSIL Brezza | non-pick slots: 2 new, 3 old
- cur: 1.Tata Nexon[*]; 2.Kia Syros[*]; 3.M XUV 3XO[*]; 4.Sk Kylaq[o]; 5.Hy Venue[*]; 6.Sk Kushaq[o]; 7.Hy Exter[o]; 8.MSIL Victoris[o]  | missing: MSIL Brezza | non-pick slots: 0 new, 4 old

**plain-09** manual petrol SUV under 12 lakh  (picks: M XUV 3XO, Tata Nexon, Sk Kylaq, Hy Venue, MSIL Brezza)
- v3: 1.M XUV 3XO[*]; 2.Sk Kylaq[*]; 3.Hy Venue[*]; 4.Tata Punch[N]; 5.Toy Urban Cruiser Taisor[o]; 6.MSIL Fronx[o]; 7.Ren Kiger[N]; 8.Nis Magnite[o]  | missing: Tata Nexon, MSIL Brezza | non-pick slots: 2 new, 3 old
- cur: 1.Toy Urban Cruiser Taisor[o]; 2.MSIL Brezza[*]; 3.MSIL Fronx[o]; 4.Nis Magnite[o]; 5.Hy Exter[o]; 6.Sk Kylaq[*]; 7.M XUV 3XO[*]; 8.Kia Syros[o]  | missing: Tata Nexon, Hy Venue | non-pick slots: 0 new, 5 old

**plain-12** hybrid SUV  (picks: MSIL Victoris, MSIL Grand Vitara, Toy Urban Cruiser Hyryder)
- v3: 1.Ren Duster[o]; 2.MSIL Victoris[*]; 3.MSIL Grand Vitara[*]; 4.Toy Urban Cruiser Hyryder[*]; 5.Kia Sorento[N]  | missing: - | non-pick slots: 1 new, 1 old
- cur: 1.Toy Urban Cruiser Hyryder[*]; 2.MSIL Grand Vitara[*]; 3.MSIL Victoris[*]; 4.Ren Duster[o]; 5.Kia Sorento[N]  | missing: - | non-pick slots: 1 new, 1 old

**plain-13** MPV with 7 seats under 18 lakh  (picks: MSIL Ertiga, Kia Carens Clavis, Toy Rumion, Ren Triber, Nis Gravite)
- v3: 1.Toy Rumion[*]; 2.Kia Carens Clavis[*]; 3.Ren Triber[*]; 4.MSIL Ertiga[*]; 5.Kia Carens[N]; 6.Nis Gravite[*]  | missing: - | non-pick slots: 1 new, 0 old
- cur: 1.Toy Rumion[*]; 2.MSIL Ertiga[*]; 3.Kia Carens Clavis[*]; 4.Kia Carens[N]; 5.Nis Gravite[*]; 6.Ren Triber[*]  | missing: - | non-pick slots: 1 new, 0 old

**plain-16** Toyota hybrid  (picks: Toy Urban Cruiser Hyryder, Toy Innova Hycross)
- v3: 1.Toy Innova Hycross[*]; 2.Toy Urban Cruiser Hyryder[*]  | missing: - | non-pick slots: 0 new, 0 old
- cur: 1.Toy Urban Cruiser Hyryder[*]; 2.Toy Innova Hycross[*]  | missing: - | non-pick slots: 0 new, 0 old

**plain-17** Tata SUV under 15 lakh  (picks: Tata Nexon, Tata Punch EV, Tata Nexon EV, Tata Harrier)
- v3: 1.Tata Nexon[*]; 2.Tata Punch[N]; 3.Tata Punch EV[*]; 4.Tata Curvv[N]; 5.Tata Sierra[N]; 6.Tata Nexon EV[*]; 7.Tata Harrier[*]; 8.Tata Safari[N]  | missing: - | non-pick slots: 4 new, 0 old
- cur: 1.Tata Nexon[*]; 2.Tata Punch EV[*]; 3.Tata Punch[N]; 4.Tata Curvv[N]; 5.Tata Sierra[N]; 6.Tata Harrier[*]; 7.Tata Nexon EV[*]; 8.Tata Safari[N]  | missing: - | non-pick slots: 4 new, 0 old

**plain-20** EV with at least 400 km range under 25 lakh  (picks: MSIL e VITARA, Tata Nexon EV, Kia Carens Clavis EV, MG Windsor EV, Tata Punch EV)
- v3: 1.Kia Carens Clavis EV[*]; 2.MSIL e VITARA[*]; 3.Tata Nexon EV[*]; 4.Tata Harrier EV[N]; 5.Tata Punch EV[*]; 6.Tata Sierra EV[N]; 7.MG Windsor EV[*]; 8.Tata Curvv EV[N]  | missing: - | non-pick slots: 3 new, 0 old
- cur: 1.Tata Nexon EV[*]; 2.MSIL e VITARA[*]; 3.MG Windsor EV[*]; 4.Kia Carens Clavis EV[*]; 5.Tata Punch EV[*]  | missing: - | non-pick slots: 0 new, 0 old

**plain-22** sedan under 12 lakh  (picks: Honda Amaze, MSIL Dzire, Hy Aura, Tata Tigor, Sk Slavia)
- v3: 1.MSIL Dzire[*]; 2.Tata Aeris[N]; 3.Honda Amaze[*]; 4.Hy Aura[*]; 5.Tata Tigor[*]; 6.VW Virtus[o]; 7.Hy Verna[o]; 8.Sk Slavia[*]  | missing: - | non-pick slots: 1 new, 2 old
- cur: 1.MSIL Dzire[*]; 2.Honda Amaze[*]; 3.Hy Aura[*]; 4.Tata Tigor[*]; 5.Sk Slavia[*]; 6.VW Virtus[o]; 7.Tata Aeris[N]; 8.Honda City[o]  | missing: - | non-pick slots: 1 new, 2 old

**plain-25** automatic MPV under 20 lakh  (picks: Kia Carens Clavis, MSIL Ertiga, Toy Rumion, MSIL XL6, Toy Innova Hycross)
- v3: 1.Toy Rumion[*]; 2.Kia Carens Clavis[*]; 3.MSIL XL6[*]; 4.Ren Triber[o]; 5.MSIL Ertiga[*]; 6.Kia Carens Clavis EV[o]; 7.Toy Innova Hycross[*]; 8.Nis Gravite[o]  | missing: - | non-pick slots: 0 new, 3 old
- cur: 1.Toy Rumion[*]; 2.MSIL XL6[*]; 3.MSIL Ertiga[*]; 4.Kia Carens Clavis[*]; 5.Nis Gravite[o]; 6.Toy Innova Hycross[*]; 7.Kia Carens Clavis EV[o]; 8.Ren Triber[o]  | missing: - | non-pick slots: 0 new, 3 old

**plain-28** DCT petrol under 15 lakh  (picks: Tata Nexon, Hy Venue, Kia Syros, Ren Duster, Tata Altroz)
- v3: 1.Hy Venue[*]; 2.Tata Altroz[*]; 3.Tata Nexon[*]; 4.Hy i20 N Line[N]; 5.Kia Sonet[N]; 6.Kia Syros[*]; 7.Tata Curvv[N]; 8.Ren Duster[*]  | missing: - | non-pick slots: 3 new, 0 old
- cur: 1.Hy Venue N Line[N]; 2.Hy Venue[*]; 3.Kia Syros[*]; 4.Tata Nexon[*]; 5.Tata Altroz[*]; 6.Kia Sonet[N]; 7.Ren Duster[*]; 8.Nis Tekton[N]  | missing: - | non-pick slots: 3 new, 0 old

**hing-01** 10 lakh tak automatic SUV chahiye  (picks: M XUV 3XO, Nis Magnite, Sk Kylaq, Tata Nexon, MSIL Fronx)
- v3: 1.Tata Punch[N]; 2.Nis Magnite[*]; 3.Hy Exter[o]; 4.Kia Sonet[N]; 5.Toy Urban Cruiser Taisor[o]; 6.MSIL Fronx[*]; 7.Sk Kylaq[*]; 8.Ren Kiger[N]  | missing: M XUV 3XO, Tata Nexon | non-pick slots: 3 new, 2 old
- cur: 1.Hy Exter[o]; 2.Nis Magnite[*]; 3.MSIL Fronx[*]; 4.Toy Urban Cruiser Taisor[o]; 5.Ren Kiger[N]; 6.Tata Nexon[*]; 7.Sk Kylaq[*]; 8.Tata Punch[N]  | missing: M XUV 3XO | non-pick slots: 2 new, 2 old

**hing-03** 7 seater gaadi chahiye 20 lakh ke andar  (picks: Kia Carens Clavis, MSIL Ertiga, M XUV 7XO, Toy Rumion, Toy Innova Crysta)
- v3: 1.M Scorpio-N[o]; 2.Hy Alcazar[N]; 3.Toy Rumion[*]; 4.Tata Safari[N]; 5.Kia Carens Clavis[*]; 6.M XUV 7XO[*]; 7.M Bolero Neo[N]; 8.Ren Triber[o]  | missing: MSIL Ertiga, Toy Innova Crysta | non-pick slots: 3 new, 2 old
- cur: 1.Toy Rumion[*]; 2.Kia Carens Clavis[*]; 3.MSIL Ertiga[*]; 4.M XUV 7XO[*]; 5.M Scorpio Classic[o]; 6.Hy Alcazar[N]; 7.Tata Safari[N]; 8.Kia Carens[N]  | missing: Toy Innova Crysta | non-pick slots: 3 new, 1 old

**hing-04** petrol hatchback chahiye 6 lakh tak  (picks: MSIL WagonR, Tata Tiago, MSIL Alto K10, MSIL S-Presso, Hy Grand i10 Nios)
- v3: 1.MSIL Alto K10[*]; 2.MSIL S-Presso[*]; 3.Ren Kwid[N]; 4.MSIL Celerio[N]; 5.Tata Tiago[*]; 6.MSIL Swift[o]; 7.MSIL Baleno[o]; 8.Hy i20[N]  | missing: MSIL WagonR, Hy Grand i10 Nios | non-pick slots: 3 new, 2 old
- cur: 1.MSIL S-Presso[*]; 2.MSIL Alto K10[*]; 3.Hy Grand i10 Nios[*]; 4.Ren Kwid[N]; 5.Tata Tiago[*]; 6.Hy i20[N]  | missing: MSIL WagonR | non-pick slots: 2 new, 0 old

**hing-06** sunroof wali SUV 15 lakh tak  (picks: Tata Nexon, M XUV 3XO, Hy Venue, Kia Syros, MSIL Brezza)
- v3: 1.M XUV 3XO[*]; 2.Hy Venue[*]; 3.Tata Nexon[*]; 4.Sk Kylaq[o]; 5.Tata Punch[N]; 6.Kia Sonet[N]; 7.MSIL Victoris[o]; 8.Toy Urban Cruiser Taisor[o]  | missing: Kia Syros, MSIL Brezza | non-pick slots: 2 new, 3 old
- cur: 1.Tata Nexon[*]; 2.Kia Syros[*]; 3.M XUV 3XO[*]; 4.Sk Kylaq[o]; 5.Hy Venue[*]; 6.Sk Kushaq[o]; 7.Hy Exter[o]; 8.MSIL Victoris[o]  | missing: MSIL Brezza | non-pick slots: 0 new, 4 old

**hing-07** CNG gaadi 8 lakh ke andar  (picks: MSIL WagonR, Tata Tiago, Hy Exter, MSIL Alto K10, MSIL Baleno)
- v3: 1.Tata Aeris[N]; 2.Tata Tiago[*]; 3.Hy Grand i10 Nios[o]; 4.MSIL Swift[o]; 5.MSIL Celerio[N]; 6.MSIL Baleno[*]; 7.MSIL Fronx[o]; 8.Tata Punch[N]  | missing: MSIL WagonR, Hy Exter, MSIL Alto K10 | non-pick slots: 3 new, 3 old
- cur: 1.Tata Tiago[*]; 2.MSIL Alto K10[*]; 3.MSIL WagonR[*]; 4.MSIL S-Presso[o]; 5.Tata Aeris[N]; 6.MSIL Eeco[o]; 7.Tata Punch[N]; 8.Hy Exter[*]  | missing: MSIL Baleno | non-pick slots: 2 new, 2 old

**hing-12** electric car chahiye 400 km range wali  (picks: MSIL e VITARA, Tata Nexon EV, Kia Carens Clavis EV, Tata Punch EV, MG Windsor EV)
- v3: 1.Tata Nexon EV[*]; 2.MSIL e VITARA[*]; 3.Kia Carens Clavis EV[*]; 4.Tata Punch EV[*]; 5.MG Windsor EV[*]; 6.M XEV 9S[N]; 7.Tata Harrier EV[N]; 8.Tata Curvv EV[N]  | missing: - | non-pick slots: 3 new, 0 old
- cur: 1.MG Windsor EV[*]; 2.Tata Nexon EV[*]; 3.MSIL e VITARA[*]; 4.Tata Punch EV[*]; 5.Kia Carens Clavis EV[*]; 6.M XEV 9S[N]; 7.M XEV 9e[N]  | missing: - | non-pick slots: 2 new, 0 old

**hing-15** family ke liye 7 seater petrol  (picks: Kia Carens Clavis, Toy Innova Hycross, MSIL Ertiga, Toy Rumion, M XUV 7XO)
- v3: 1.M XUV 7XO[*]; 2.Tata Safari[N]; 3.M Scorpio-N[o]; 4.Hy Alcazar[N]; 5.VW Tayron[N]; 6.Kia Carens Clavis[*]; 7.Toy Rumion[*]; 8.Ren Triber[o]  | missing: Toy Innova Hycross, MSIL Ertiga | non-pick slots: 3 new, 2 old
- cur: 1.MSIL Ertiga[*]; 2.Toy Rumion[*]; 3.Nis Gravite[o]; 4.Ren Triber[o]; 5.Toy Innova Hycross[*]; 6.Kia Carens Clavis[*]; 7.M XUV 7XO[*]; 8.M Scorpio-N[o]  | missing: - | non-pick slots: 0 new, 3 old

**hing-19** papa ke liye automatic sedan 15 lakh tak  (picks: Honda Amaze, MSIL Dzire, Honda City, Hy Verna, Sk Slavia)
- v3: 1.MSIL Dzire[*]; 2.Hy Verna[*]; 3.Honda Amaze[*]; 4.Tata Aeris[N]; 5.VW Virtus[o]; 6.Sk Slavia[*]; 7.Honda City[*]; 8.Hy Aura[o]  | missing: - | non-pick slots: 1 new, 2 old
- cur: 1.MSIL Dzire[*]; 2.Honda Amaze[*]; 3.Sk Slavia[*]; 4.Honda City[*]; 5.VW Virtus[o]; 6.Tata Tigor[o]; 7.Tata Aeris[N]; 8.Hy Verna[*]  | missing: - | non-pick slots: 1 new, 2 old

**hing-21** Maruti ki CNG hatchback  (picks: MSIL WagonR, MSIL Swift, MSIL Baleno, MSIL Alto K10, MSIL S-Presso)
- v3: 1.MSIL Swift[*]; 2.MSIL Baleno[*]; 3.MSIL Alto K10[*]; 4.MSIL S-Presso[*]; 5.MSIL Celerio[N]; 6.MSIL WagonR[*]  | missing: - | non-pick slots: 1 new, 0 old
- cur: 1.MSIL Swift[*]; 2.MSIL WagonR[*]; 3.MSIL Baleno[*]; 4.MSIL S-Presso[*]; 5.MSIL Alto K10[*]; 6.MSIL Celerio[N]  | missing: - | non-pick slots: 1 new, 0 old

**hing-29** electric nahi chahiye, petrol chahiye  (picks: Hy Creta, Tata Nexon, MSIL Brezza, MSIL Swift, Honda Amaze)
- v3: 1.M XUV 3XO[o]; 2.Ren Duster[o]; 3.Hy Venue[o]; 4.Kia Seltos[o]; 5.MSIL Victoris[o]; 6.Tata Punch[N]; 7.Hy i20[N]; 8.MSIL Dzire[o]  | missing: Hy Creta, Tata Nexon, MSIL Brezza, MSIL Swift, Honda Amaze | non-pick slots: 2 new, 6 old
- cur: 1.MSIL Swift[*]; 2.MSIL Dzire[o]; 3.Toy Glanza[o]; 4.Toy Urban Cruiser Taisor[o]; 5.Hy Grand i10 Nios[o]; 6.Hy Aura[o]; 7.Sk Slavia[o]; 8.VW Virtus[o]  | missing: Hy Creta, Tata Nexon, MSIL Brezza, Honda Amaze | non-pick slots: 0 new, 7 old

**budget-19** SUV under 1.2 crore  (picks: Toy Fortuner, M XUV 7XO, M Scorpio-N, M Thar Roxx, Tata Harrier)
- v3: 1.Ren Duster[o]; 2.Kia Seltos[o]; 3.M XUV 3XO[o]; 4.M XUV 7XO[*]; 5.Tata Harrier[*]; 6.Hy Creta[o]; 7.MSIL e VITARA[o]; 8.VW Tayron[N]  | missing: Toy Fortuner, M Scorpio-N, M Thar Roxx | non-pick slots: 1 new, 5 old
- cur: 1.Toy Fortuner[*]; 2.Sk Kodiaq[N]; 3.Kia Sorento[N]; 4.Toy Urban Cruiser Hyryder[o]; 5.MSIL Victoris[o]; 6.MSIL Grand Vitara[o]; 7.Ren Duster[o]; 8.Tata Nexon[o]  | missing: M XUV 7XO, M Scorpio-N, M Thar Roxx, Tata Harrier | non-pick slots: 2 new, 5 old

**budget-05** around 10 lakh  (picks: M XUV 3XO, Tata Nexon, MSIL Fronx, MSIL Brezza, Hy Venue)
- v3: 1.Tata Altroz[o]; 2.Hy i20[N]; 3.M XUV 3XO[*]; 4.Tata Punch[N]; 5.MSIL Fronx[*]; 6.MSIL Dzire[o]; 7.Sk Kylaq[o]; 8.Ren Triber[o]  | missing: Tata Nexon, MSIL Brezza, Hy Venue | non-pick slots: 2 new, 4 old
- cur: 1.MSIL Swift[o]; 2.MSIL Dzire[o]; 3.Toy Urban Cruiser Taisor[o]; 4.Toy Glanza[o]; 5.Tata Nexon[*]; 6.Nis Gravite[o]; 7.Hy Exter[o]; 8.Nis Magnite[o]  | missing: M XUV 3XO, MSIL Fronx, MSIL Brezza, Hy Venue | non-pick slots: 0 new, 7 old

**named-01** Hyundai Creta  (picks: Hy Creta, Kia Seltos, VW Taigun, Sk Kushaq, Honda Elevate)
- v3: 1.Hy Creta[*]  | missing: Kia Seltos, VW Taigun, Sk Kushaq, Honda Elevate | non-pick slots: 0 new, 0 old
- cur: 1.Hy Creta[*]  | missing: Kia Seltos, VW Taigun, Sk Kushaq, Honda Elevate | non-pick slots: 0 new, 0 old

**named-02** Scorpio N diesel automatic  (picks: M Scorpio-N, M XUV 7XO, M Thar Roxx, Tata Harrier, Toy Fortuner)
- v3: 1.M Scorpio-N[*]  | missing: M XUV 7XO, M Thar Roxx, Tata Harrier, Toy Fortuner | non-pick slots: 0 new, 0 old
- cur: 1.M Scorpio-N[*]  | missing: M XUV 7XO, M Thar Roxx, Tata Harrier, Toy Fortuner | non-pick slots: 0 new, 0 old

**named-04** something like Creta  (picks: Kia Seltos, VW Taigun, Sk Kushaq, Honda Elevate, Ren Duster)
- v3: 1.M XUV 3XO[o]; 2.Ren Duster[*]; 3.Hy Venue[o]; 4.Kia Seltos[*]; 5.Tata Nexon[o]; 6.MSIL Victoris[o]; 7.Sk Kylaq[o]; 8.Toy Urban Cruiser Taisor[o]  | missing: VW Taigun, Sk Kushaq, Honda Elevate | non-pick slots: 0 new, 6 old
- cur: 1.Toy Urban Cruiser Hyryder[o]; 2.MSIL Grand Vitara[o]; 3.MSIL Victoris[o]; 4.Tata Nexon[o]; 5.Toy Urban Cruiser Taisor[o]; 6.M XUV 3XO[o]; 7.Kia Syros[o]; 8.Nis Magnite[o]  | missing: Kia Seltos, VW Taigun, Sk Kushaq, Honda Elevate, Ren Duster | non-pick slots: 0 new, 8 old

**named-06** Brezza alternatives  (picks: M XUV 3XO, Tata Nexon, Hy Venue, Kia Syros, Sk Kylaq)
- v3: 1.M XUV 3XO[*]; 2.Hy Venue[*]; 3.Tata Nexon[*]; 4.Tata Punch[N]; 5.MSIL Fronx[o]; 6.Sk Kylaq[*]; 7.Toy Urban Cruiser Taisor[o]; 8.Ren Kiger[N]  | missing: Kia Syros | non-pick slots: 2 new, 2 old
- cur: 1.Tata Nexon[*]; 2.MSIL Fronx[o]; 3.Toy Urban Cruiser Taisor[o]; 4.M XUV 3XO[*]; 5.Kia Syros[*]; 6.Nis Magnite[o]; 7.Sk Kylaq[*]; 8.Hy Exter[o]  | missing: Hy Venue | non-pick slots: 0 new, 4 old

**named-07** Innova Crysta  (picks: Toy Innova Crysta, Toy Innova Hycross, Kia Carens Clavis, MSIL Ertiga, Toy Rumion)
- v3: 1.Toy Innova Crysta[*]  | missing: Toy Innova Hycross, Kia Carens Clavis, MSIL Ertiga, Toy Rumion | non-pick slots: 0 new, 0 old
- cur: 1.Toy Innova Crysta[*]  | missing: Toy Innova Hycross, Kia Carens Clavis, MSIL Ertiga, Toy Rumion | non-pick slots: 0 new, 0 old

**named-11** like XUV 3XO under 14 lakh  (picks: Tata Nexon, Hy Venue, Kia Syros, Sk Kylaq, Nis Magnite)
- v3: 1.Tata Nexon[*]; 2.Sk Kylaq[*]; 3.Hy Venue[*]; 4.Tata Punch[N]; 5.Toy Urban Cruiser Taisor[o]; 6.MSIL Fronx[o]; 7.Kia Sonet[N]; 8.Ren Kiger[N]  | missing: Kia Syros, Nis Magnite | non-pick slots: 3 new, 2 old
- cur: 1.Tata Nexon[*]; 2.MSIL Fronx[o]; 3.Toy Urban Cruiser Taisor[o]; 4.Kia Syros[*]; 5.Nis Magnite[*]; 6.Sk Kylaq[*]; 7.Hy Exter[o]; 8.Sk Kushaq[o]  | missing: Hy Venue | non-pick slots: 0 new, 4 old

**num-06** SUV with ground clearance of at least 210 mm  (picks: M Thar, M Thar Roxx, Honda Elevate, Ren Duster, Toy Fortuner)
- v3: 1.Ren Duster[*]; 2.MSIL Victoris[o]; 3.Tata Punch[N]; 4.Hy Venue[o]; 5.Toy Urban Cruiser Taisor[o]; 6.M Thar Roxx[*]; 7.Ren Kiger[N]; 8.Kia Sonet[N]  | missing: M Thar, Honda Elevate, Toy Fortuner | non-pick slots: 3 new, 3 old
- cur: 1.Toy Urban Cruiser Hyryder[o]; 2.MSIL Grand Vitara[o]; 3.MSIL Victoris[o]; 4.Honda Elevate[*]; 5.M Thar[*]; 6.M Thar Roxx[*]; 7.Toy Fortuner[*]; 8.Ren Duster[*]  | missing: - | non-pick slots: 0 new, 3 old

**num-12** petrol hatchback with mileage above 22 kmpl  (picks: MSIL Swift, MSIL S-Presso, MSIL Alto K10, Toy Glanza, MSIL WagonR)
- v3: 1.Hy i20[N]; 2.Tata Altroz[o]; 3.MSIL Swift[*]; 4.Hy Grand i10 Nios[o]; 5.MSIL Celerio[N]; 6.MSIL Baleno[o]; 7.MSIL S-Presso[*]; 8.Hy i20 N Line[N]  | missing: MSIL Alto K10, Toy Glanza, MSIL WagonR | non-pick slots: 3 new, 3 old
- cur: 1.MSIL Swift[*]; 2.MSIL S-Presso[*]; 3.Toy Glanza[*]; 4.Hy Grand i10 Nios[o]; 5.Tata Altroz[o]; 6.Tata Tiago[o]; 7.Hy i20[N]; 8.Ren Kwid[N]  | missing: MSIL Alto K10, MSIL WagonR | non-pick slots: 2 new, 3 old

**neg-02** SUV but not diesel  (picks: Honda Elevate, MSIL Brezza, MSIL Grand Vitara, VW Taigun, Sk Kushaq)
- v3: 1.M XUV 3XO[o]; 2.Ren Duster[o]; 3.Hy Venue[o]; 4.Kia Seltos[o]; 5.Tata Nexon EV[o]; 6.MSIL Victoris[o]; 7.Sk Kylaq[o]; 8.Toy Urban Cruiser Taisor[o]  | missing: Honda Elevate, MSIL Brezza, MSIL Grand Vitara, VW Taigun, Sk Kushaq | non-pick slots: 0 new, 8 old
- cur: 1.Toy Urban Cruiser Hyryder[o]; 2.MSIL Grand Vitara[*]; 3.MSIL Victoris[o]; 4.Ren Duster[o]; 5.Toy Urban Cruiser Taisor[o]; 6.M XUV 3XO[o]; 7.Hy Venue N Line[N]; 8.Hy Venue[o]  | missing: Honda Elevate, MSIL Brezza, VW Taigun, Sk Kushaq | non-pick slots: 1 new, 6 old

**neg-08** no sunroof  (picks: Nis Magnite, MSIL Ertiga, Toy Rumion, Honda Amaze, Ren Triber)
- v3: 1.MSIL Fronx[o]; 2.MSIL Victoris[o]; 3.Tata Nexon EV[o]; 4.Toy Urban Cruiser Taisor[o]; 5.Ren Kiger[N]; 6.Toy Innova Crysta[o]; 7.Hy Grand i10 Nios[o]; 8.Kia Seltos[o]  | missing: Nis Magnite, MSIL Ertiga, Toy Rumion, Honda Amaze, Ren Triber | non-pick slots: 1 new, 7 old
- cur: 1.MSIL Swift[o]; 2.MSIL Dzire[o]; 3.Toy Urban Cruiser Hyryder[o]; 4.Ren Duster[o]; 5.Tata Nexon[o]; 6.Toy Innova Hycross[o]; 7.Hy Creta[o]; 8.Hy Grand i10 Nios[o]  | missing: Nis Magnite, MSIL Ertiga, Toy Rumion, Honda Amaze, Ren Triber | non-pick slots: 0 new, 8 old

**hing-34** wireless charging wali gaadi, 20 lakh tak  (picks: M XUV 3XO, Tata Nexon, Hy Venue, Kia Syros, MSIL Grand Vitara)
- v3: 1.Ren Duster[o]; 2.Hy Verna[o]; 3.Kia Seltos[o]; 4.Hy Venue[*]; 5.M XUV 3XO[*]; 6.Tata Harrier[o]; 7.Tata Altroz[o]; 8.Toy Rumion[o]  | missing: Tata Nexon, Kia Syros, MSIL Grand Vitara | non-pick slots: 0 new, 6 old
- cur: 1.Tata Nexon[*]; 2.MSIL Grand Vitara[*]; 3.MSIL Victoris[o]; 4.M XUV 3XO[*]; 5.VW Virtus[o]; 6.Toy Urban Cruiser Hyryder[o]; 7.Hy Venue[*]; 8.VW Taigun[o]  | missing: Kia Syros | non-pick slots: 0 new, 4 old

**plain-31** turbo petrol DCT SUV  (picks: Kia Seltos, Hy Creta, Sk Kushaq, VW Taigun, Ren Duster)
- v3: 1.Ren Duster[*]; 2.Hy Venue[o]; 3.Kia Seltos[*]; 4.Tata Nexon[o]; 5.Hy Creta[*]; 6.Kia Sonet[N]; 7.Kia Syros[o]; 8.Sk Kushaq[*]  | missing: VW Taigun | non-pick slots: 1 new, 3 old
- cur: 1.Hy Venue N Line[N]; 2.Hy Venue[o]; 3.Sk Kushaq[*]; 4.VW Taigun[*]; 5.Ren Duster[*]; 6.Kia Syros[o]; 7.Tata Nexon[o]; 8.Sk Kodiaq[N]  | missing: Kia Seltos, Hy Creta | non-pick slots: 2 new, 3 old

Totals over 40 queries: v3 hits 122, missing picks 69, non-pick slots new 66 / old 89; current hits 135, missing 56, non-pick new 38 / old 98
## 2. Do blanks carry the new models above owner picks?

### 2.1 Why blanks help: what the data and the scoring do

Three facts, all measured on `data/catalogue_v3` (1,464 variants; the 30 new models have 383 of them, the other 249 new variants belong to old models):

1. **A criterion is the mean of its known fields, so a nearly blank criterion can be perfect.** `criteria._weighted_mean` (`services/recsys/criteria.py:221-250`) divides by the weight of the known fields only. Mean criterion values and unknown field weight (per variant):

| Criterion | old 832 variants: value / unknown | new variants of old models | variants of the 30 new models |
|---|---|---|---|
| tech_assist | 0.39 / 0.09 | 0.73 / 0.60 | 0.74 / 0.59 |
| comfort_features | 0.59 / 0.05 | 0.79 / 0.11 | 0.82 / 0.12 |
| safety | 0.82 / 0.18 | 0.76 / 0.50 | 0.77 / 0.62 |
| space_practicality | 0.51 / 0.02 | 0.48 / 0.83 | 0.56 / 0.83 |
| running_cost | wholly unknown on 35 % | 54 % | 95 % |

   44 % of the new variants of old models and 52 % of the variants of new models score 0.95 or more on tech_assist while 50 % or more of its field weight is blank; in the old rows that never happens (0 %).
2. **The blanks are not random.** The KB records the features a new model has and leaves out the ones it lacks. Share of known cells that are True, old rows versus the 30 new models: sunroof 0.48 vs 0.77, ventilated seats 0.25 vs 0.57, 360 camera 0.24 vs 0.60, TPMS 0.68 vs 0.92. ABS, ESC, ADAS, connected-car and HUD are 100 % blank for all 30 new models, and these are the columns where old models are mostly False (ADAS 14 % True, HUD 3 %). Skipping a blank therefore scores a car on the cells that flatter it.
3. **The coverage charge is small.** overall = raw x (1 - 0.15 x unknown_share) (`score.py:155`). Over the 155 non-pick slots in v3's top 8 (shortlist queries, run b): new models average unknown share 0.443 (66 slots), old models 0.238 (89 slots). The multiplier is 0.934 against 0.964: a difference of 0.03. The mean raw score before the charge is 0.752 (new) against 0.768 (old).

### 2.2 Ten cases: displacing new model vs displaced owner pick (v3, new catalogue, reviews on, 0.60/0.25/0.15)

"Weight" is the criterion's global weight after class normalisation; D = displacer (new model), P = displaced pick. Spec criteria are shown; the 25 expert and owner criteria are summarised by count known and class sub-score. "partial unk" = share of that criterion's field weight that is blank although the criterion has a value. Coverage factor = 1 - 0.15 x unknown share. Raw = score before the coverage factor.


#### plain-01: "I want a petrol hatchback under 8 lakh"  displacer Maruti Suzuki Celerio (v976 ZXi Plus Petrol Automatic, Rs 6.8L) vs displaced pick Maruti Suzuki Swift (v66 ZXi Petrol Automatic, Rs 8.0L)
| criterion | class | weight D / P | value D | value P |
|---|---|---|---|---|
| value_for_budget | spec | 0.131 / 0.131 | 1.00 (partial unk 0.50) | 0.77 |
| safety | spec | 0.101 / 0.101 | 0.75 (partial unk 0.70) | 0.75 (partial unk 0.30) |
| running_cost | spec | 0.101 / 0.101 | 0.98 | 0.94 |
| tech_assist | spec | 0.067 / 0.067 | 1.00 (partial unk 0.81) | 0.33 (partial unk 0.14) |
| space_practicality | spec | 0.067 / 0.067 | 0.52 (partial unk 0.83) | 0.53 |
| performance | spec | 0.067 / 0.067 | 0.20 (partial unk 0.83) | 0.61 |
| comfort_features | spec | 0.067 / 0.067 | UNKNOWN | 0.25 |
| expert / owner criteria known | | | 10/13, 8/12 | 10/13, 8/12 |
| sub-scores spec/expert/owner | | | 0.788 / 0.740 / 0.865 | 0.644 / 0.820 / 0.903 |
| class weights used | | | spec=0.77 expert=0.10 owner=0.14 | spec=0.76 expert=0.10 owner=0.14 |
| unknown share / coverage factor (1-0.15u) | | | 0.476 / 0.9285 | 0.147 / 0.9779 |
| raw (before coverage) | | | 0.7941 | 0.6966 |
| final overall | | | **0.7373** | **0.6812** |

Weight in wholly unknown criteria: D 0.175, P 0.108. Flags D ['unrated_safety'], P ['unrated_safety'].

#### plain-01: "I want a petrol hatchback under 8 lakh"  displacer Renault Kwid (v1011 Climber Petrol Automatic, Rs 5.6L) vs displaced pick Maruti Suzuki Swift (v66 ZXi Petrol Automatic, Rs 8.0L)
| criterion | class | weight D / P | value D | value P |
|---|---|---|---|---|
| value_for_budget | spec | 0.131 / 0.131 | 1.00 (partial unk 0.50) | 0.77 |
| safety | spec | 0.101 / 0.101 | 0.75 (partial unk 0.70) | 0.75 (partial unk 0.30) |
| running_cost | spec | 0.101 / 0.101 | UNKNOWN | 0.94 |
| tech_assist | spec | 0.067 / 0.067 | 1.00 (partial unk 0.81) | 0.33 (partial unk 0.14) |
| space_practicality | spec | 0.067 / 0.067 | 0.52 (partial unk 0.83) | 0.53 |
| performance | spec | 0.067 / 0.067 | 0.33 (partial unk 0.33) | 0.61 |
| comfort_features | spec | 0.067 / 0.067 | UNKNOWN | 0.25 |
| expert / owner criteria known | | | 10/13, 7/12 | 10/13, 8/12 |
| sub-scores spec/expert/owner | | | 0.764 / 0.750 / 0.863 | 0.644 / 0.820 / 0.903 |
| class weights used | | | spec=0.86 expert=0.10 owner=0.04 | spec=0.76 expert=0.10 owner=0.14 |
| unknown share / coverage factor (1-0.15u) | | | 0.556 / 0.9166 | 0.147 / 0.9779 |
| raw (before coverage) | | | 0.7668 | 0.6966 |
| final overall | | | **0.7028** | **0.6812** |

Weight in wholly unknown criteria: D 0.288, P 0.108. Flags D ['unrated_safety'], P ['unrated_safety'].

#### plain-08: "compact SUV with a sunroof under 15 lakh"  displacer Tata Punch (v1097 Accomplished Plus (S) Petrol Turbo 6 Speed Manual, Rs 10.0L) vs displaced pick Kia Syros (v765 HTX(O) Petrol DCT, Rs 15.0L)
| criterion | class | weight D / P | value D | value P |
|---|---|---|---|---|
| value_for_budget | spec | 0.124 / 0.124 | 0.98 | 0.98 |
| safety | spec | 0.095 / 0.095 | 0.77 (partial unk 0.60) | 0.90 |
| running_cost | spec | 0.095 / 0.095 | UNKNOWN | 0.32 |
| comfort_features | spec | 0.095 / 0.095 | 1.00 (partial unk 0.19) | 1.00 |
| tech_assist | spec | 0.063 / 0.063 | 1.00 (partial unk 0.52) | 0.90 |
| space_practicality | spec | 0.063 / 0.063 | 0.40 (partial unk 0.83) | 0.43 |
| performance | spec | 0.063 / 0.063 | 0.44 | 0.66 |
| expert / owner criteria known | | | 10/13, 7/12 | 10/13, 7/12 |
| sub-scores spec/expert/owner | | | 0.804 / 0.810 / 0.914 | 0.765 / 0.820 / 0.905 |
| class weights used | | | spec=0.77 expert=0.10 owner=0.13 | spec=0.85 expert=0.10 owner=0.06 |
| unknown share / coverage factor (1-0.15u) | | | 0.342 / 0.9486 | 0.109 / 0.9836 |
| raw (before coverage) | | | 0.8195 | 0.7782 |
| final overall | | | **0.7774** | **0.7654** |

Weight in wholly unknown criteria: D 0.215, P 0.120. Flags D ['unrated_safety'], P [].

#### plain-09: "manual petrol SUV under 12 lakh"  displacer Renault Kiger (v1003 Emotion Petrol Turbo Manual Dual Tone, Rs 9.4L) vs displaced pick Tata Nexon (v1397 Creative Plus (S) Petrol 1.2L Turbo 6 Speed Manual Camo, Rs 10.7L)
| criterion | class | weight D / P | value D | value P |
|---|---|---|---|---|
| value_for_budget | spec | 0.131 / 0.131 | 0.99 | 0.96 |
| safety | spec | 0.101 / 0.101 | 0.77 (partial unk 0.60) | 0.66 (partial unk 0.40) |
| running_cost | spec | 0.101 / 0.101 | UNKNOWN | UNKNOWN |
| tech_assist | spec | 0.067 / 0.067 | 1.00 (partial unk 0.52) | 0.80 (partial unk 0.52) |
| space_practicality | spec | 0.067 / 0.067 | 0.40 (partial unk 0.83) | 0.40 (partial unk 0.83) |
| performance | spec | 0.067 / 0.067 | 0.27 | 0.44 |
| comfort_features | spec | 0.067 / 0.067 | 1.00 (partial unk 0.12) | 0.81 |
| expert / owner criteria known | | | 10/13, 7/12 | 10/13, 8/12 |
| sub-scores spec/expert/owner | | | 0.773 / 0.770 / 0.877 | 0.714 / 0.740 / 0.883 |
| class weights used | | | spec=0.79 expert=0.10 owner=0.11 | spec=0.76 expert=0.10 owner=0.14 |
| unknown share / coverage factor (1-0.15u) | | | 0.380 / 0.9429 | 0.339 / 0.9491 |
| raw (before coverage) | | | 0.7838 | 0.7403 |
| final overall | | | **0.7391** | **0.7026** |

Weight in wholly unknown criteria: D 0.221, P 0.208. Flags D ['unrated_safety'], P [].

#### hing-01: "10 lakh tak automatic SUV chahiye"  displacer Tata Punch (v1096 Accomplished Plus (S) Petrol Automatic, Rs 9.7L) vs displaced pick Mahindra XUV 3XO (v40 MX2 Pro Petrol 1.2L Turbo Automatic (TC), Rs 9.9L)
| criterion | class | weight D / P | value D | value P |
|---|---|---|---|---|
| value_for_budget | spec | 0.131 / 0.131 | 0.99 | 0.64 |
| safety | spec | 0.101 / 0.101 | 0.77 (partial unk 0.60) | 0.80 |
| running_cost | spec | 0.101 / 0.101 | UNKNOWN | 0.37 |
| tech_assist | spec | 0.067 / 0.067 | 1.00 (partial unk 0.52) | 0.00 |
| space_practicality | spec | 0.067 / 0.067 | 0.40 (partial unk 0.83) | 0.45 |
| performance | spec | 0.067 / 0.067 | 0.10 | 0.46 |
| comfort_features | spec | 0.067 / 0.067 | 1.00 (partial unk 0.19) | 0.46 (partial unk 0.19) |
| expert / owner criteria known | | | 10/13, 7/12 | 10/13, 8/12 |
| sub-scores spec/expert/owner | | | 0.750 / 0.810 / 0.914 | 0.488 / 0.820 / 0.902 |
| class weights used | | | spec=0.77 expert=0.10 owner=0.13 | spec=0.76 expert=0.10 owner=0.14 |
| unknown share / coverage factor (1-0.15u) | | | 0.385 / 0.9423 | 0.120 / 0.9820 |
| raw (before coverage) | | | 0.7772 | 0.5788 |
| final overall | | | **0.7324** | **0.5684** |

Weight in wholly unknown criteria: D 0.221, P 0.108. Flags D ['unrated_safety'], P [].

#### hing-03: "7 seater gaadi chahiye 20 lakh ke andar"  displacer Hyundai Alcazar (v840 Platinum Petrol 1.5L Turbo 6 Speed Manual 7 STR, Rs 19.0L) vs displaced pick Maruti Suzuki Ertiga (v212 ZXi+ MT, Rs 11.6L)
| criterion | class | weight D / P | value D | value P |
|---|---|---|---|---|
| value_for_budget | spec | 0.124 / 0.124 | 0.73 | 0.85 |
| space_practicality | spec | 0.095 / 0.095 | 0.90 (partial unk 0.83) | 0.45 |
| safety | spec | 0.095 / 0.095 | 0.77 (partial unk 0.60) | 0.74 (partial unk 0.30) |
| running_cost | spec | 0.095 / 0.095 | UNKNOWN | 0.69 |
| tech_assist | spec | 0.063 / 0.063 | 1.00 (partial unk 0.52) | 0.33 |
| performance | spec | 0.063 / 0.063 | 0.64 | 0.60 |
| comfort_features | spec | 0.063 / 0.063 | 0.81 | 0.50 |
| expert / owner criteria known | | | 10/13, 8/12 | 10/13, 8/12 |
| sub-scores spec/expert/owner | | | 0.801 / 0.750 / 0.901 | 0.624 / 0.780 / 0.901 |
| class weights used | | | spec=0.80 expert=0.10 owner=0.11 | spec=0.76 expert=0.10 owner=0.14 |
| unknown share / coverage factor (1-0.15u) | | | 0.373 / 0.9441 | 0.136 / 0.9796 |
| raw (before coverage) | | | 0.8069 | 0.6784 |
| final overall | | | **0.7618** | **0.6645** |

Weight in wholly unknown criteria: D 0.203, P 0.108. Flags D ['unrated_safety'], P ['unrated_safety'].

#### hing-03: "7 seater gaadi chahiye 20 lakh ke andar"  displacer Mahindra Bolero Neo (v959 N11 Diesel Turbo Manual, Rs 10.4L) vs displaced pick Toyota Innova Crysta (v304 GX 8 Seater, Rs 19.8L)
| criterion | class | weight D / P | value D | value P |
|---|---|---|---|---|
| value_for_budget | spec | 0.124 / 0.124 | 0.87 (partial unk 0.50) | 0.63 |
| space_practicality | spec | 0.095 / 0.095 | 0.90 (partial unk 0.83) | 0.67 |
| safety | spec | 0.095 / 0.095 | 0.50 (partial unk 0.80) | 0.84 (partial unk 0.30) |
| running_cost | spec | 0.095 / 0.095 | UNKNOWN | UNKNOWN |
| tech_assist | spec | 0.063 / 0.063 | UNKNOWN | 0.43 |
| performance | spec | 0.063 / 0.063 | 0.65 (partial unk 0.50) | 0.67 |
| comfort_features | spec | 0.063 / 0.063 | 1.00 (partial unk 0.81) | 0.25 |
| expert / owner criteria known | | | 10/13, 7/12 | 10/13, 7/12 |
| sub-scores spec/expert/owner | | | 0.783 / 0.620 / 0.870 | 0.607 / 0.680 / 0.917 |
| class weights used | | | spec=0.81 expert=0.10 owner=0.10 | spec=0.84 expert=0.10 owner=0.06 |
| unknown share / coverage factor (1-0.15u) | | | 0.580 / 0.9130 | 0.244 / 0.9634 |
| raw (before coverage) | | | 0.7760 | 0.6328 |
| final overall | | | **0.7085** | **0.6097** |

Weight in wholly unknown criteria: D 0.279, P 0.215. Flags D ['unrated_safety'], P ['unrated_safety'].

#### hing-15: "family ke liye 7 seater petrol"  displacer Volkswagen Tayron (v1465 R-Line Petrol Automatic 7 STR, Rs 47.7L) vs displaced pick Toyota Innova Hycross (v579 GX (O) 8 Seater Petrol CVT, Rs 20.8L)
| criterion | class | weight D / P | value D | value P |
|---|---|---|---|---|
| space_practicality | spec | 0.129 / 0.129 | 0.90 (partial unk 0.83) | 0.87 |
| safety | spec | 0.129 / 0.129 | 0.91 (partial unk 0.60) | 0.80 |
| running_cost | spec | 0.078 / 0.078 | UNKNOWN | 0.13 |
| value_for_budget | spec | 0.065 / 0.065 | 0.10 | 0.43 |
| comfort_features | spec | 0.065 / 0.065 | 1.00 | 0.62 (partial unk 0.19) |
| price | spec | 0.048 / 0.048 | 0.01 | 0.22 |
| tech_assist | spec | 0.043 / 0.043 | 1.00 (partial unk 0.52) | 0.65 (partial unk 0.19) |
| performance | spec | 0.043 / 0.043 | 0.88 | 0.67 |
| expert / owner criteria known | | | 10/13, 1/12 | 10/13, 8/12 |
| sub-scores spec/expert/owner | | | 0.739 / 0.800 / 0.919 | 0.601 / 0.809 / 0.907 |
| class weights used | | | spec=0.90 expert=0.08 owner=0.02 | spec=0.78 expert=0.08 owner=0.13 |
| unknown share / coverage factor (1-0.15u) | | | 0.487 / 0.9270 | 0.136 / 0.9797 |
| raw (before coverage) | | | 0.7475 | 0.6594 |
| final overall | | | **0.6929** | **0.6460** |

Weight in wholly unknown criteria: D 0.279, P 0.115. Flags D ['unrated_safety'], P [].

#### hing-07: "CNG gaadi 8 lakh ke andar"  displacer Tata Aeris (v1024 Pure Plus CNG Manual, Rs 7.7L) vs displaced pick Hyundai Exter (v657 HX 3 CNG Manual, Rs 7.4L)
| criterion | class | weight D / P | value D | value P |
|---|---|---|---|---|
| value_for_budget | spec | 0.131 / 0.131 | 1.00 (partial unk 0.50) | 0.87 |
| safety | spec | 0.101 / 0.101 | 0.72 (partial unk 0.70) | 0.74 (partial unk 0.30) |
| running_cost | spec | 0.101 / 0.101 | UNKNOWN | 0.50 |
| tech_assist | spec | 0.067 / 0.067 | 1.00 (partial unk 0.81) | 0.19 |
| space_practicality | spec | 0.067 / 0.067 | 0.50 (partial unk 0.83) | 0.14 (partial unk 0.33) |
| performance | spec | 0.067 / 0.067 | 0.22 | 0.16 |
| comfort_features | spec | 0.067 / 0.067 | 0.43 (partial unk 0.56) | 0.00 |
| expert / owner criteria known | | | 0/13, 7/12 | 0/13, 7/12 |
| sub-scores spec/expert/owner | | | 0.696 / nan / 0.931 | 0.452 / nan / 0.914 |
| class weights used | | | spec=0.86 owner=0.14 | spec=0.86 owner=0.14 |
| unknown share / coverage factor (1-0.15u) | | | 0.697 / 0.8955 | 0.365 / 0.9452 |
| raw (before coverage) | | | 0.7281 | 0.5165 |
| final overall | | | **0.6520** | **0.4882** |

Weight in wholly unknown criteria: D 0.413, P 0.312. Flags D ['unrated_safety'], P ['unrated_safety'].

#### budget-19: "SUV under 1.2 crore"  displacer Volkswagen Tayron (v1465 R-Line Petrol Automatic 7 STR, Rs 47.7L) vs displaced pick Mahindra Thar Roxx (v690 AX7 L 2WD Diesel 2.2L Turbo Automatic, Rs 20.0L)
| criterion | class | weight D / P | value D | value P |
|---|---|---|---|---|
| value_for_budget | spec | 0.131 / 0.131 | 0.44 | 0.70 |
| safety | spec | 0.101 / 0.101 | 0.91 (partial unk 0.60) | 0.90 |
| running_cost | spec | 0.101 / 0.101 | UNKNOWN | 0.27 |
| tech_assist | spec | 0.067 / 0.067 | 1.00 (partial unk 0.52) | 0.90 |
| space_practicality | spec | 0.067 / 0.067 | 0.90 (partial unk 0.83) | 0.82 |
| performance | spec | 0.067 / 0.067 | 0.88 | 0.76 |
| comfort_features | spec | 0.067 / 0.067 | 1.00 | 1.00 |
| expert / owner criteria known | | | 10/13, 1/12 | 10/13, 8/12 |
| sub-scores spec/expert/owner | | | 0.805 / 0.800 / 0.919 | 0.737 / 0.770 / 0.902 |
| class weights used | | | spec=0.88 expert=0.10 owner=0.02 | spec=0.77 expert=0.10 owner=0.14 |
| unknown share / coverage factor (1-0.15u) | | | 0.447 / 0.9329 | 0.108 / 0.9838 |
| raw (before coverage) | | | 0.8071 | 0.7633 |
| final overall | | | **0.7530** | **0.7510** |

Weight in wholly unknown criteria: D 0.296, P 0.108. Flags D ['unrated_safety'], P [].

Pattern: (a) in 7 of the 10 the displacer's `running_cost` (global weight 0.08 to 0.10) is wholly unknown (mileage blank) while the pick has a known and mostly mediocre value (0.13 to 0.69), so the criterion drops out for the displacer and its weight goes to the others; a blank beats a weak known. (b) In 8 of 10 the displacer's `tech_assist` is 1.00 on a basis that is 52 to 81 % blank, against 0.00 to 0.90 for the pick. (c) `safety` and `value_for_budget` are likewise computed on partly blank cells (partial unknown 0.5 to 0.8). (d) The coverage factor differs between displacer and pick by 0.006 to 0.061 while the raw gap is 0.04 to 0.21, so the charge cannot close it. Extreme case: hing-15 and budget-19 put the Rs 47.7L Tayron (value_for_budget 0.10 and 0.44, price criterion 0.01) above a pick because its spec sub-score is 0.74 to 0.81 on blank-heavy criteria and it has only 1 of 12 owner criteria (owner class weight 0.02, so the spec class dominates).

### 2.3 Is 0.15 too weak? Pair analysis

For the 102 (new displacer, missing owner pick) pairs in the top-8 lists of the 40 queries, the coverage constant at which the pick would overtake the displacer (solving raw_D (1 - p u_D) = raw_P (1 - p u_P) for p): the displacer's raw score is higher than the pick's in all 102 pairs (median raw gap 0.096, median gap in unknown share 0.205). Median required p = 0.58 (quartiles 0.35 to 0.87). Pairs reversed at p = 0.30: 21 %; 0.50: 39 %; 0.75: 59 %; 1.00: 75 %. So yes: at 0.15 the charge is far too small to reverse most of them; it would have to be 0.5 to 0.75 to reverse half.

### 2.4 Coverage constant sweep (reviews on, 0.60/0.25/0.15 class weights, new catalogue)

Patched `config.COVERAGE_PENALTY` in the eval process only (the repo constant stays 0.15). Main = 209 queries, held-out = 107.

| Coverage constant | Shortlist recall@8 | MRR | Probe: still returned (of 75) | Probe: known-lacking above / newly above | Main zero-violation | Relaxed truthful / mislabelled | Held-out zero-violation |
|---|---|---|---|---|---|---|---|
| 0.15 (current) | 0.655 | 0.762 | 63 | 2 / 2 | 193/193 | 11 / 0 | 105/107 |
| 0.30 | 0.695 | 0.842 | 54 | 2 / 2 | 193/193 | 11 / 0 | 105/107 |
| 0.50 | 0.720 | 0.853 | 43 | 4 / 2 | 193/193 | 11 / 0 | 105/107 |
| 0.75 | 0.745 | 0.843 | 37 | 4 / 1 | 193/193 | 11 / 0 | 105/107 |

For reference (same code, current engine, new catalogue): 0.720 / 0.832; v3 on the old 832 rows, reviews on, 0.770 / 0.816. Held-out: the same two queries (h-030, h-035) violate in every row, as before; no new violation appears. Paraphrase consistency 1.000 in all rows.

Reading: a heavier charge recovers recall and MRR (0.50 matches the current engine on recall and beats it on MRR) but it is paid by the unknown probe, whose purpose is that a blank is not scored as a "no": at 0.50 only 43 of 75 blanked top cars stay in the list (63 at 0.15) and known-lacking cars above double to 4. The probe wants a blank to rank between known-yes and known-no. A global multiplier cannot do that, because the charge hits the blanked car the same whether the cell would have been yes or no. See candidate change 1 (field-level prior).

## 3. Why the current engine does better

**There is no popularity, sales, brand or learned prior in either engine.** `grep -iE "popular|sales|bestsell|brand_weight|learned"` over `ranking_engine.py`, `services/*.py`, `services/recsys/*.py` finds nothing. The current engine (`services/new_car_service.get_kb_recommendations` -> `services/ranking_adapter.rank_candidates` -> `ranking_engine.rank_cars`) is a coarse additive point score. Its only model-specific input is a hand-written model-name list in `ranking_engine.model_quality_adjustment` (line 722; "family_friendly_models", "highway_friendly_models", ... used only when the query has a family / highway / parents / premium use case).

**What the current engine has that v3 does not (each tested by switching it off in the eval process, shortlist recall@8 / MRR, 40 queries, new catalogue; base = 0.720 / 0.832):**

| Mechanism (file:line) | Switched off | recall@8 | MRR | New-model non-pick slots in top 8 (base 38) |
|---|---|---|---|---|
| Unverified / unrated cars sort AFTER every verified car: `keys = ["n_soft_flags", "ranking_score", "variant_id"]`, ascending first (`services/ranking_adapter.py:200`; `n_soft_flags` = count of "Unverified: ..." labels + unrated safety, `services/filter_v2.py:239`) | n_soft_flags forced to 0 | 0.690 | 0.832 | 39 |
| Blank mileage scores 0 points (`ranking_engine.py:329`, `if mileage <= 0: return 0`) | mileage term off | 0.750 | 0.857 | 48 |
| Price closeness to 55-92 % of the budget (`ranking_engine.py:261`) | price term off | 0.705 | 0.795 | 27 |
| Hand model-name list (`ranking_engine.py:722`) | off | 0.715 | 0.832 | 39 |
| Max 2 models per make (`services/new_car_service.py:18,192`) | cap off | 0.745 | 0.834 | 35 |
| Use-case bonuses (`use_case_score`) | off | 0.720 | 0.832 | 39 |
| `variant_id` as final tie-break | ids randomly permuted (3 seeds) | 0.715 to 0.720 | 0.803 to 0.845 | - |
| All of: no flags, no quality list, no cap | | 0.715 | 0.835 | 40 |

Reading: no single mechanism explains the gap. The only two that help the current engine are the lexicographic unverified demotion (+0.030 recall) and the price-target term (+0.015 recall, +0.037 MRR). The mileage term and the make cap actually hurt it. The popularity hypothesis is not supported: the quality list is worth +0.005, and the tie-break by `variant_id` (which numbers the old catalogue first, 1 to 832) is worth about 0, because random ids give the same recall.

**What does separate the two engines is how a blank is valued.** v3 skips a blank field and averages the known ones (`criteria._weighted_mean`, `services/recsys/criteria.py:221-250`, `value = num_sum / den` over known fields only; `_bool_score` line 83 returns NaN for a blank), then charges only `1 - 0.15 x unknown_share` (`score.py:155`). The current engine gives a blank mileage zero points (`ranking_engine.py:329`), scores a blank ABS / feature as absent in the use-case rules, and sorts unverified cars after verified ones. Test of the hypothesis in v3, same eval process: fill each criterion's unknown share with a prior p (`value' = (1-u) x value + u x p`, u = the criterion's unknown fraction), reviews on, coverage 0.15:

| Prior for a blank (p) | recall@8 | MRR |
|---|---|---|
| none (as built: skip) | 0.655 | 0.762 |
| 0.5 | 0.705 | 0.824 |
| 0.35 | 0.725 | 0.832 |
| 0 (blank = absent, as the current engine does) | 0.745 | 0.832 |

With p = 0 v3 reaches 0.745 / 0.832, which is the current engine's recall and MRR (0.720 / 0.832) within one pick. The "skip a blank" rule, not the number of criteria, is the mechanism.

**Staleness shows up in the same experiment.** Restricting the new catalogue to the 62 models that were in the old one (new variants of those models kept, 1,081 rows):

| Catalogue | v3 recall / MRR | current recall / MRR |
|---|---|---|
| old 832 rows | 0.770 / 0.816 | 0.745 / 0.861 |
| new 1,464 rows, old 62 models only | 0.755 / 0.802 | 0.745 / 0.849 |
| new 1,464 rows, all 92 models | 0.655 / 0.762 | 0.720 / 0.832 |

Adding the 30 new models costs v3 0.100 recall and the current engine 0.025. On the old 62 models v3's recall is level with or above the current engine's; the current engine leads only in MRR (+0.047). A no-model baseline "hard filter, sort by `variant_id`, first 8 models" scores 0.755 / 0.820, and all 57 distinct owner picks are among the first 62 models in id order (ids 1 to 832 are the catalogue the owner saw). Popularity proxy: CarWale rating count, median 225 for owner picks (53 with a count), 106 for the 30 new models. The owner's picks are not unusually popular (mean percentile rank 0.57); they are simply old.

## 4. Are the owner's shortlists stale?

Yes, in large part. All 191 picks (57 distinct cars) are among the 62 models of the old catalogue, because the sheet was filled from it; the 30 models added later could not have been picked. The 17 sheets whose recall or MRR changed between the 832-row run and run (a) (list: plain-01, plain-06, plain-09, plain-12, hing-01, hing-03, hing-04, hing-07, hing-15, budget-19, budget-05, named-06, named-11, num-06, num-12, neg-08, plain-31) have 40 new-model entries in v3's top 8 (run b, reviews on). Verdict from catalogue facts only (the entrant's displayed variant, price, body, seats, fuel, the facts the query asks for):

| Query | Entrants (displayed variant, price) | Verdict |
|---|---|---|
| plain-01 petrol hatchback < 8 lakh | Celerio ZXi+ AMT 6.8L; i20 Sportz 7.9L; Kwid Climber AMT 5.6L | Genuine x3 (petrol hatchbacks inside budget). Kwid is entry-level |
| plain-06 CNG hatchback < 7 lakh | Celerio VXi CNG 6.0L | Genuine |
| plain-09 manual petrol SUV < 12 lakh | Punch Turbo MT 10.0L; Kiger Turbo MT 9.4L | Genuine x2 (catalogue body = suv) |
| plain-12 hybrid SUV | Sorento HTK hybrid 34.2L | Genuine on the stated constraints; a different price tier from the 10-20L picks |
| hing-01 automatic SUV, 10 lakh | Punch AMT 9.7L; Sonet 1.0T DCT 10.0L; Kiger AMT 7.5L | Genuine x3 |
| hing-03 7-seater < 20 lakh | Alcazar 19.0L; Safari 16.8L; Bolero Neo N11 10.4L | Alcazar, Safari genuine. Bolero Neo is a 7-seater but 2 airbags, coverage 0.42: weak fit |
| hing-04 petrol hatchback < 6 lakh | Kwid 5.6L; Celerio 4.7L; i20 Era 6.0L | Genuine x3 (i20 sits exactly at the cap, rank 8, score 0.495) |
| hing-07 CNG < 8 lakh | Aeris Pure+ CNG 7.7L; Celerio CNG 6.0L; Punch CNG 7.7L | Genuine x3 |
| hing-15 family 7-seater petrol | Safari 23.0L; Alcazar 21.0L; Tayron R-Line 47.7L | Safari, Alcazar genuine. Tayron meets "7 seats, petrol" but at 2 to 4 times the picks' price: weak fit |
| budget-19 SUV < 1.2 crore | Tayron 47.7L | Genuine (the owner picked Fortuner 35-50L) |
| budget-05 around 10 lakh (8.5 to 11.5L) | i20 Asta 8.7L; Punch 10.0L | Genuine x2 |
| named-06 Brezza alternatives | Punch, Kiger, Sonet X Line | Genuine x3 (Sonet is Brezza's direct rival) |
| named-11 like XUV 3XO < 14 lakh | Punch, Sonet, Kiger, Bolero Neo N10 10.0L | Punch, Sonet, Kiger genuine. Bolero Neo (ladder-frame 7-seat diesel, 2 airbags) is a poor fit |
| num-06 SUV, ground clearance >= 210 mm | Punch, Kiger, Sonet | **Blank-driven x3**: ground clearance is blank on all 26, 19 and 21 variants; they pass as "Unverified". Nothing in the catalogue shows 210 mm |
| num-12 petrol hatchback > 22 kmpl | i20 Asta 8.7L; i20 N Line N8 10.6L; Celerio ZXi+ 6.8L | Celerio genuine (26.0 kmpl known). **i20 and i20 N Line blank-driven x2**: mileage blank on all 15 and 5 variants; i20 is rank 1 |
| neg-08 "no sunroof" | Kiger Emotion | **Blank-driven**: sunroof blank on all 19 Kiger variants ("Unverified: no sunroof"); the picks are known to lack one |
| plain-31 turbo petrol DCT SUV | Sonet X Line 1.0T DCT 13.9L | Genuine |

Count: of 40 entries, 31 are genuine fits a reasonable person might have listed, 3 are weak or different-tier fits (Bolero Neo x2, Tayron), 6 are blank-driven (the constraint is checked against a blank, nothing verifies it). The 6 are all in queries with a numeric minimum or an excluded feature, where v3 treats an unverified required item as a tiny penalty: `REQUIRED_ITEM_WEIGHT` = 0.10 gives it 0.1 / (1 + 0.1) = 9 % of the unknown share, so it costs 0.15 x 0.09 = 1.4 % of the score (`score.py:150-155`). The current engine sorts the same cars after every verified one (`ranking_adapter.py:200`).

Blank-driven entry is not limited to new models: in num-06 and num-12 old models with blanks (Venue Knight, Taisor, Altroz, Baleno, Grand i10 Nios) also pass.

Consequence for the metric: a shortlist of 5 picks against 8 slots is saturated by stale picks as soon as 3 or more genuine new models qualify, so a drop in recall@8 does not mean worse ranking. It does mean the sheet needs a refresh before it can arbitrate between engines.

## 5. Review data

### 5.1 The 9 sheets that reviews change (run a without reviews vs run b with reviews, same code)

Method: `recommend()` with an empty `Evidence()` versus the repo files; for each model that enters or leaves the top 8, class sub-scores, the lift reviews give (class weight x (review sub-score - spec sub-score)) and the three aspects with the largest deviation, with the query's multiplier for that aspect (1.0 = the query does not care about it).

| Sheet | Moved | Lift from reviews | Aspect that moved it (multiplier) | Sensible? |
|---|---|---|---|---|
| plain-08 / hing-06 (sunroof SUV < 15L) | Sonet, Taisor in; Syros, Hyryder out | Taisor +0.016, Hyryder +0.022, Syros +0.013, Sonet +0.002 | owner service cost / value (1.0), owner real-world mileage (1.0), Autocar rear-seat and front space (1.0) | No. None of these aspects is in the query; the order flips on differences of 0.001 to 0.002 |
| hing-04 (petrol hatch < 6L) | i20 in (+0.092), WagonR out (0.000) | WagonR has no Autocar and no CarWale row, so spec only | owner comfort / satisfaction / features (1.0) | No. i20's spec score is 0.434; review values of 0.76 to 0.88 lift it by 0.09, a car without rows gets nothing |
| hing-07 (CNG < 8L) | Punch in (+0.103), Exter out (+0.064) | Punch spec 0.419, Exter spec 0.452 (no Autocar row) | owner value / features / satisfaction (1.0) | No. Same mechanism as hing-04 |
| budget-05 (around 10L) | Punch, Kylaq in; Nexon, Baleno out | Punch +0.017, Kylaq +0.028, Nexon +0.016, Baleno +0.009 | owner performance / satisfaction / value (1.0) | Marginal: gaps under 0.003; "around 10 lakh" has no use case |
| hing-15 (family 7-seater) | Rumion, Triber in; Hector Plus, Kodiaq out | Triber +0.039, Rumion +0.032 vs Hector Plus +0.008 (no Autocar row) | owner comfort (1.3), owner satisfaction (1.2), owner service cost (1.3) | Yes in direction: family profile boosts these. Hector Plus (not an owner pick, no Autocar row) is out partly for lacking a row |
| budget-19 (SUV < 1.2 crore) | Creta in, Venue out | Creta +0.023, Venue +0.017 | owner comfort / performance / service cost (1.0) | Marginal. Venue is not an obvious 1.2-crore car either way |
| num-12 (hatch > 22 kmpl) | Glanza out | Glanza has no Autocar row: spec 0.658, owner weight 0.05 | owner value / features (1.0) | Owner-picked car lost because it has no expert row |
| plain-02 | order only: Venue and Seltos swap 1st and 2nd | | | |

Three structural reasons the direction is poor on its face:
1. **A review class is present only for cars that have rows, and review values are higher than spec scores.** Autocar values average 0.767, CarWale 0.900 (all 88 models, `data/assessments.csv`, `data/owner_ratings.csv`); spec sub-scores of the candidates are 0.4 to 0.8. Blending a 0.9 into a car's score lifts it; a car with no row has its class redistributed to spec and gets no lift (`score.py:126-134`). 17 of 92 models have no Autocar row (WagonR, Exter, Glanza, Thar, Verna, Tigor, Windsor EV, Carens Clavis EV, Hector Plus, ...), and 17 of the owner's 191 picks (9 %) belong to them (WagonR alone 6). In three of the nine sheets an owner pick without rows is the model displaced (WagonR in hing-04, Exter in hing-07, Glanza in num-12).
2. **Every aspect is active at base weight in every query.** `weights.build_weights` starts every expert and owner criterion at multiplier 1.0 (`weights.py:134`, `:169`) and a profile only raises some. An Autocar "Mileage / Range And Efficiency" score (`expert_real_world_mileage`) therefore enters a query that never mentions mileage with the same weight as any other of the 13 aspects (about 0.019 of the final weight each), and CarWale "Fuel Economy" (`owner_real_world_mileage`) the same. Confirmed in the decompositions above: `expert_real_world_mileage` appears among the top movers of the sunroof-SUV sheet (Syros -0.0016). Not a mapping bug; the mapping table sends labels to the correct aspects. It is a design choice that makes review aspects non-selective.
3. **Three of 13 expert aspects have no data for any model** (`highway_stability`, `city_driveability`, `boot_practicality`: no Autocar label maps to them, `scripts/export_reviews_from_kb.py:34-43`). `expert_scale` divides covered aspects by relevant aspects (`evidence.py:330-348`; `highway` also boosts `expert_highway_stability` x2.5, an aspect with no data, which lowers the expert scale further), so even a perfect, fully rated car has at most 10/13 x 1/(1+1) = 0.38 of the expert class weight (one source: n/(n+K) = 0.5). The 0.25 expert class weight is 0.09 to 0.10 in practice (class weights printed above: spec 0.77, expert 0.10, owner 0.13).

### 5.2 Mapping and double counting

- Source labels that feed two aspects (`LABEL_MAP`, `scripts/export_reviews_from_kb.py:34-53`): "Performance And Refinement" -> engine_performance + refinement; "Ride Comfort And Handling" -> ride_comfort + handling; "Interior Space And Comfort" -> front_space + rear_seat_comfort; CarWale "After Sales Cost and Experience" -> service_cost + service_experience. In profiles that boost both aspects of a pair, one score counts twice: `parents` boosts ride_comfort x2, rear_seat_comfort x2 and front_space x1.5, so the one Interior score is counted at x3.5 and the one Ride score at x2; `highway` boosts engine_performance x2 and refinement x1.5 (one "Performance And Refinement" score at x3.5) and ride_comfort x1.5; `family` boosts rear_seat_comfort x2 and ride_comfort x1.5 (`weights.py:36-93`). Each is one observation counted at the sum of two multipliers, and its effect is limited only by the small expert class weight.
- Value for money is counted in three classes at once: spec `value_for_budget` and the price criterion, Autocar `expert_value_for_money`, CarWale `owner_value`; the `budget` and `student` profiles boost all three (x2.5 / x2.5 / x2.5 for budget).
- "Features And Safety" feeds `expert_features_tech` only; it does not feed spec `safety` (crash-test based), so there is no double count with safety.
- No mis-mapped label found: each Autocar and CarWale label goes to the aspect its name says. The mapping is applied correctly; the issue is breadth (5.1 point 2), not routing.

### 5.3 Thin owner evidence is discounted twice (confirmed)

`Evidence._build_owner_ratings` shrinks the rating toward the segment mean with weight w = count / (count + 50) (`evidence.py:313-315`). `score.py:129-134` then multiplies the owner class weight by `owner_scale` = count / (count + 50) again (`evidence.py:366-372`, same constant `OWNER_SAMPLE_K`, same count). The owner signal's deviation from the segment mean is therefore scaled by w x w, not w. For the 88 models with owner rows (count percentiles 10/25/50/75/90 = 28 / 51 / 200 / 388 / 658):

| Rating count | w (value shrink) | w x w (effective) |
|---|---|---|
| 20 | 0.29 | 0.08 |
| 30 | 0.38 | 0.14 |
| 50 | 0.50 | 0.25 |
| 100 | 0.67 | 0.44 |
| 225 | 0.82 | 0.67 |
| 600 | 0.92 | 0.85 |

Median model: effective 0.64 instead of 0.80. 35 of 88 models have w x w under 0.5 (22 have w under 0.5). In the probe cases (section 6) City (47 ratings, w x w = 0.24) gets owner class weight 0.07, Dzire (616 ratings) 0.14. Removing the second discount (owner class weight unscaled, shrink kept) changes shortlist recall@8 / MRR from 0.655 / 0.762 to 0.670 / 0.765 (patched in the eval process).

## 6. The two probe cases at 0.60 / 0.25 / 0.15 with reviews

Probe query "comfortable sedan under 20 lakh", blanked columns `ventilated_front_seats` and `cruise_control` on every variant of the probed model; "known-lacking" = a car whose cells for both are known False (Dzire: ventilated seats False on 9 of 11 variants and blank on 2, cruise control False on 11 of 11). The failing cases are the probe of City (rank 3 before, 5 after) and of Slavia (rank 4 before, 5 after), each with Dzire newly above. Dzire is a Rs 6.3 to 9.5L car; City is Rs 12.0 to 21.0L, Slavia 10.0 to 18.2L.

Trace (reproduced with `recommend(catalogue=blanked frame)`, displayed variant per model; overall = final score):

| Run | Dzire (v241, 9.4L) | City (v300, 16.1L) | Slavia (v619, 15.0L) | Order |
|---|---|---|---|---|
| Baseline, reviews off | 0.6986 | 0.7461 | 0.7423 | City, Slavia, Dzire |
| Baseline, reviews ON | 0.7367 | 0.7466 | 0.7420 | City, Slavia, Dzire (5th) |
| City blanked, reviews off | 0.6986 | 0.7262 | 0.7438 | Slavia, City, Dzire |
| City blanked, reviews ON | 0.7367 | 0.7324 | 0.7432 | Slavia, **Dzire**, City |
| Slavia blanked, reviews ON | 0.7367 | 0.7466 | 0.7311 | City, **Dzire**, Slavia |

Two effects add up, both small:
1. **Blanking costs the probed car 0.011 to 0.020.** City's `comfort_features` gets 37.5 % unknown field weight, unknown share 0.142 -> 0.188, coverage 0.979 -> 0.972, and its spec sub-score falls 0.752 -> 0.741 (the blanked cells leave the weighted mean, so the remaining comfort cells weigh more and the others less).
2. **Reviews lift Dzire by 0.038 and City by 0.000 to 0.006.** Dzire's spec sub-score is only 0.699 (comfort_features 0.625: ventilated seats and cruise control known absent), but it has Autocar ride comfort 0.90 and CarWale comfort 0.94 / satisfaction 0.95 on 616 ratings: owner class weight 0.14 and expert 0.12. City has 47 ratings (owner class weight 0.07, shrink w = 0.48, double discount per 5.3) so its 0.93 comfort rating counts for little. Without reviews Dzire is 0.03 to 0.05 below.

The final margin is 0.0043 (City case) and 0.0056 (Slavia case): inside the resolution of the score. At 0.15 coverage the probe is at its limit: with reviews off both cases pass (run a: 0 known-lacking above).

This is a limitation of the probe as a pass/fail on rank, not evidence that v3 scored the blank as "no": the blanked car's score fell by 0.011 to 0.020, about the size of removing one criterion's worth of evidence. But it does show reviews make the ordering of cars within 0.01 depend on rating sample size.

## 7. Ranked candidate changes (none implemented)

All numbers: main set (209 queries, shortlist = 40 sheets), new catalogue, patched in the eval process only. Zero-violation 193/193 and relaxed 11 truthful / 0 mislabelled in every run. Probe = "still returned of 75" / known-lacking above / newly above. Held-out was run for the coverage sweep only (105/107 in every row, same two queries as before).

| Configuration | recall@8 | MRR | Probe |
|---|---|---|---|
| As built (coverage 0.15, reviews 0.60/0.25/0.15) | 0.655 | 0.762 | 63 / 2 / 2 |
| Reviews off, coverage 0.15 (run a) | 0.675 | 0.772 | 66 / 0 / 0 |
| Blank prior p = 0.5 | 0.705 | 0.824 | 53 / 3 / 1 |
| Blank prior p = 0.35 | 0.725 | 0.832 | 52 / 3 / 1 |
| Blank = 0 (what the current engine does) | 0.745 | 0.832 | 46 / 4 / 2 |
| Coverage 0.30 | 0.695 | 0.842 | 54 / 2 / 2 |
| Coverage 0.50 | 0.720 | 0.853 | 43 / 4 / 2 |
| Coverage 0.75 | 0.745 | 0.843 | 37 / 4 / 1 |
| Reviews off, coverage 0.50 | 0.740 | 0.862 | 39 / 3 / 3 |
| Owner class weight not scaled a second time (shortlist only) | 0.670 | 0.765 | not run |
| REQUIRED_ITEM_WEIGHT 0.5 / 1.0 (shortlist only) | 0.665 / 0.665 | 0.769 / 0.773 | not run |
| Blank prior 0.5 with coverage 0.50 (shortlist only) | 0.720 | 0.866 | not run |
| Current engine, same catalogue | 0.720 | 0.832 | (9 known-lacking above in its own run) |
| v3 on old models only (new variants kept) | 0.755 | 0.802 | |

1. **Value a blank at a prior instead of skipping it, in the criterion (`criteria._weighted_mean`).** Largest measured effect on the cause: p = 0.35 gives +0.07 recall and +0.07 MRR, p = 0 matches the current engine's recall. Costs: probe "still returned" 63 -> 52 and one extra known-lacking case; no constraint change. **Design decision for the owner**: how much a missing feature should count, and whether the prior is a constant, the segment's known share, or the old catalogue's True-rate for that column (ADAS 14 %, HUD 3 %). The data fix is separate and better: the KB holds ABS, ESC, ADAS, connected-car and HUD for none of the 30 new models and records only the features they have; filling them removes the asymmetry at its source.
2. **Raise `COVERAGE_PENALTY` to 0.30 to 0.50.** One constant: 0.30 gives +0.04 recall, +0.08 MRR with the probe's known-lacking count unchanged at 2 / 2 (still returned 54); 0.50 matches the current engine's recall and beats it on MRR but drops the probe to 43 still returned and doubles known-lacking above. **Design decision**: the probe wants blank ranked between known-yes and known-no, a global multiplier cannot do that, so this is a cruder substitute for change 1.
3. **Refresh the owner's shortlists against the new catalogue before using them to rank engines (owner action, no code).** 31 of the 40 new-model entries in the 17 changed sheets are genuine fits the owner never saw; all 57 distinct picks are old models; on the 62 old models v3 is level with the current engine on recall (0.755 vs 0.745) and behind on MRR (0.802 vs 0.849). Until then recall@8 against the stale sheet measures staleness as much as ranking.
4. **Make an unverified numeric minimum or excluded feature cost more than a blank elsewhere (design).** 6 of the 40 entries are blank-driven (num-06, num-12, neg-08), all in queries where the one thing asked for is blank. In the current engine the equivalent rule (unverified cars sort after verified ones) is worth +0.03 recall. Raising `REQUIRED_ITEM_WEIGHT` to 0.5 or 1.0 does not help (0.665), so the lever is ordering, not weight. Not measured in v3. **Design decision.**
5. **Reviews: stop adding noise at 0.60/0.25/0.15 until three things are fixed.** (a) Owner evidence is discounted twice (w x w); removing the second discount gives +0.015 recall. The previous agent documented this as intended, so it is a **design decision**, not a bug fix. (b) `expert_scale` counts three aspects no model has data for, capping the expert class at 0.38 of its weight (`evidence.py:330-348`): this is the one item that reads as a **bug** (a denominator that cannot be met). (c) Cars with no review row get no lift while reviewed cars get +0.01 to +0.10 (review values average 0.77 and 0.90): give them a neutral review prior, and boost only the aspects the query cares about (all 13 are active at base weight in every query): **design decisions**. Evidence that reviews do not help: reviews off at coverage 0.50 is 0.740 / 0.862 against 0.720 / 0.853 with reviews, and 0 probe failures against 2 at 0.15.

Bug versus design: only 5(b) looks like a bug. Everything else changes what the engine means by a blank, a review or a pick, and belongs to the owner.

## Appendix: method and limits

- Reproduction: scratch scripts in `/tmp/sg/` (`common.py` captures the score table inside `recommend()`; `q1.py`, `q2.py`/`q2b.py`, `q5.py`, `q6.py`, `patch.py`, `sweep.py`, `sweep2.py`, `cur_abl2.py`, `e1.py`, `perm.py`). Not committed. Patches (coverage constant, class weights, blank prior via a wrapper on `criteria._weighted_mean`, evidence off, owner scale, `REQUIRED_ITEM_WEIGHT`) are applied in the eval process only; the repo is unchanged. The no-reviews patch reproduces run a (0.675 / 0.772) and the coverage 0.15 row reproduces run b (0.655 / 0.762, probe 63 / 2 / 2).
- The 40-query shortlist is a small sample: one pick in 191 is 0.005 recall. Differences under about 0.02 are noise; the effects above (0.04 to 0.10) are not.
- The blank-prior wrapper uses the criterion's unknown fraction, which counts the crash-star prior as unknown, so safety is shrunk slightly more than other criteria. The ablations of the current engine switch one term off at a time in the eval process (`ranking_engine.price_score`, `mileage_score`, `use_case_score`, `model_quality_adjustment`, `NS.MAX_KB_MODELS_PER_MAKE`, `n_soft_flags`).
- "Genuine fit" in section 4 is a judgement from catalogue columns (body, price, seats, fuel, the queried field); it is not a label from the owner.
- Patched variants were run on the main set only; held-out was run for the four coverage constants.
- `eval/shortlist_sheet.csv` was used as it is in the working tree (uncommitted picks), unchanged.
