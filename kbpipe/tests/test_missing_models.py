"""The missing-models rules (PLAN_ADD_MISSING_MODELS.md): battery capacity, strong-hybrid fuel, descriptor words, D1 price,
dual tone, brochure confirmation. Names and prices are the real ones from the 17 Nov listings."""
import json

import pytest

from kbpipe import brochure, extract, match, plan
from kbpipe.sources import common as c
from test_incremental import FakeFetcher


def T(name, fuel="Electric", trans="Automatic", price=None, **kw):
    return dict({"name": name, "fuel": fuel, "transmission": trans, "price": price}, **kw)


def X(name, sub="", fuel="Electric", trans="Automatic", price=None, url=None):
    return {"name": name, "fuel": fuel, "transmission": trans, "price": price, "sub": sub, "url": url or "u/" + name,
            "battery_kwh": c.battery_kwh(name, sub)}


def L(target, cands, model, tier=1, **kw):
    return match.link(target, cands, model, need_price=True, price_tol=0.005, tier=tier, **kw)


# ---------------------------------------------------------------- attribute parsers
def test_battery_parser_spellings():
    assert c.battery_kwh("Executive 42.0 kWh") == 42.0
    assert c.battery_kwh("Hyundai Creta Electric Executive", "42 kWh, 420 km, 133 bhp") == 42.0
    assert c.battery_kwh("BE 6 SPORTEQ One 59kWh") == 59.0
    assert c.battery_kwh("Excellence LR 51.4 kWh Dual Tone") == 51.4
    assert c.battery_kwh("EC Pro 345 kWh") is None            # out of range: only the page-name check reads it as 34.5
    assert c.battery_kwh("Zeta Plus 7Str", "1987 cc, Automatic, Petrol") is None


def test_battery_tolerance_keeps_comet_17_3_and_17_4_apart():
    assert c.battery_agrees(42.0, 42) and c.battery_agrees(17.3, 17.30)
    assert not c.battery_agrees(17.3, 17.4)
    assert not c.battery_agrees(None, 17.3)


def test_page_battery_fix_only_when_the_sub_line_says_the_decimal():
    pn = c.norm_name("Mahindra XUV400 EV EC Pro 345 kWh")
    assert c.page_battery_fix(pn, 34.5) == c.norm_name("Mahindra XUV400 EV EC Pro 34.5 kWh")
    assert c.page_battery_fix(pn, None) == pn and c.page_battery_fix(pn, 39.4) == pn
    assert c.page_battery_fix(c.norm_name("Tigor EV XE 26 kWh"), 26.0) == c.norm_name("Tigor EV XE 26 kWh")


def test_page_name_check_accepts_the_missing_decimal_only_with_a_matching_battery():
    hit = X("Mahindra XUV400 EV EC Pro 34.5 kWh", "34.5 kWh, 375 km, 149.55 bhp")
    assert extract._page_name_ok("Mahindra XUV400 EV EC Pro 345 kWh", hit)
    assert extract._page_name_ok("Mahindra XUV400 EV EC Pro 34.5 kWh", hit)
    assert not extract._page_name_ok("Mahindra XUV400 EV EL Pro 345 kWh", hit)                  # other trim: still refused
    assert not extract._page_name_ok("Mahindra XUV400 EV EC Pro 394 kWh", hit)                  # other battery: still refused


def test_page_name_check_accepts_the_model_name_the_list_left_out():
    hit = X("Essence 7-Seater", "69.2 kWh, 517 km", price=2424800)
    assert extract._page_name_ok("MG Hector Tomahawk EV Essence 7-Seater", hit, "MG Hector Tomahawk EV")
    assert not extract._page_name_ok("MG Hector Tomahawk EV Essence 7-Seater", hit)                         # no model name known: refused as before
    assert not extract._page_name_ok("MG Hector Tomahawk EV Exclusive 7-Seater", hit, "MG Hector Tomahawk EV")
    assert not extract._page_name_ok("MG ZS EV Essence 7-Seater", hit, "MG Hector Tomahawk EV")


def test_descriptor_words_are_the_enumerated_ones_only():
    m = "Honda City"
    assert c.relaxed_tokens("Exclusive Plug-in Hybrid (Electric + Petrol) Automatic", "MG Hector Tomahawk PHEV") == {"exclusive"}
    assert c.relaxed_tokens("Sport Hybrid (Electric + Petrol) Automatic e:HEV", "Honda ZR-V") == {"sport"}
    assert c.relaxed_tokens("AX5 39.4 kWh with No Charger", "Mahindra XUV 3XO EV") == {"ax", "5"}
    assert c.relaxed_tokens("AX5 39.4 kWh with Charger", "Mahindra XUV 3XO EV") == {"ax", "5", "with", "charger"}   # not enumerated: stays
    assert c.relaxed_tokens("Zeta Plus Hybrid (Electric + Petrol) Automatic 7 STR", "Maruti Suzuki Invicto") == c.relaxed_tokens("Zeta Plus 7Str", "Maruti Suzuki Invicto")
    assert c.relaxed_tokens("4X2 2WD Diesel Turbo Automatic Dual Tone", "Toyota Fortuner Legender") == {"dual", "tone"}
    assert c.relaxed_tokens("Elegant Hybrid (Electric + Petrol) Automatic", m) != c.relaxed_tokens("Elegance", m)


# ---------------------------------------------------------------- rule 1: battery
def test_creta_electric_executive_links_on_battery_and_unique_identity():
    cands = [X("Hyundai Creta Electric Executive", "42 kWh, 420 km, 133 bhp", price=1802800),
             X("Hyundai Creta Electric Executive Tech", "42 kWh, 420 km, 133 bhp", price=1899900)]
    t = T("Executive 42.0 kWh", price=1457159, battery_kwh=42.0)
    assert L(t, cands, "Hyundai Creta Electric", tier=0)[0] is None                      # the original linker refuses
    hit, why = L(t, cands, "Hyundai Creta Electric", peers=[t])
    assert hit is cands[0] and why == "identity (price differs) [battery]"


def test_tigor_ev_links_with_agreeing_price_as_identity():
    cands = [X("Tata Tigor EV XE", "26 kWh, 315 km, 73.75 bhp", price=1249000), X("Tata Tigor EV XT", "26 kWh", price=1299000)]
    hit, why = L(T("XE 26.0 kWh", price=1249000), cands, "Tata Tigor EV")
    assert hit is cands[0] and why == "identity [battery]"


def test_battery_that_disagrees_never_links():
    cands = [X("Hyundai Creta Electric Excellence HC DT", "42 kWh, 420 km, 169 bhp", price=2218500)]
    t = T("Excellence HC 51.4 kWh Dual Tone", price=2218500)
    assert L(t, cands, "Hyundai Creta Electric", tier=2)[0] is None


def test_comet_17_3_and_17_4_stay_distinct():
    a = X("MG Comet EV Excite", "17.3 kWh, 230 km", price=899800)
    b = X("MG Comet EV Excite", "17.4 kWh, 230 km", price=899800, url="u/2")
    t173, t174 = T("Excite 17.3 kWh", price=899800), T("Excite 17.4 kWh", price=899800)
    assert L(t173, [a, b], "MG Comet EV")[0] is a and L(t174, [a, b], "MG Comet EV")[0] is b
    assert L(t174, [a], "MG Comet EV", tier=2)[0] is None and L(t173, [b], "MG Comet EV", tier=2)[0] is None
    assert L(T("Excite 17.3 kWh", price=757381), [b], "MG Comet EV", tier=2)[0] is None       # D1 does not cross batteries either


def test_comet_price_differs_links_only_when_the_identity_is_unique_among_carwale_versions():
    cands = [X("MG Comet EV Executive", "17.3 kWh", price=789800)]
    t = T("Executive 17.3 kWh", price=647865)
    assert L(t, cands, "MG Comet EV", peers=[t])[1] == "identity (price differs) [battery]"
    assert L(t, cands, "MG Comet EV", peers=[t, dict(t, price=700000)])[0] is None


# ---------------------------------------------------------------- rule 4 (D1): price
def test_price_differs_needs_both_prices_and_one_candidate():
    one = [X("Mahindra BE 6 SPORTEQ One 59kWh", "59 kWh", price=1945000)]
    t = T("One 59.0 kWh No Charger", price=1545392)
    assert L(t, one, "Mahindra BE 6 SPORTEQ", peers=[t])[1] == "identity (price differs) [battery]"
    assert L(dict(t, price=None), one, "Mahindra BE 6 SPORTEQ", peers=[t])[0] is None
    two = one + [X("Mahindra BE 6 SPORTEQ One 59kWh", "59 kWh", price=2100000, url="u/2")]
    assert L(t, two, "Mahindra BE 6 SPORTEQ", peers=[t])[0] is None                    # two candidates: price must break the tie, it cannot
    assert L(dict(t, price=2100000), two, "Mahindra BE 6 SPORTEQ", peers=[t])[0] is two[1]   # exact price still breaks it


def test_charger_versions_stay_unlinked():
    one = [X("Mahindra BE 6 SPORTEQ One 59kWh", "59 kWh", price=1945000)]
    assert L(T("One 59.0 kWh 11.2kW Charger", price=2020000), one, "Mahindra BE 6 SPORTEQ")[0] is None


# ---------------------------------------------------------------- rule 2: strong hybrid
INV = "Maruti Suzuki Invicto Maruti Suzuki Invicto"


def test_invicto_links_only_when_every_carwale_version_is_a_strong_hybrid():
    cands = [X("Maruti Suzuki Invicto Zeta Plus 7Str", "1987 cc, Automatic, Petrol, 23.24 kmpl", fuel="Petrol", price=2502400)]
    t = T("Zeta Plus Hybrid (Electric + Petrol) Automatic 7 STR", fuel="Petrol Hybrid", trans="e-CVT", price=2502400)
    assert L(t, cands, INV, strong_hybrid=False)[0] is None
    hit, why = L(t, cands, INV, strong_hybrid=True)
    assert hit is cands[0] and why == "identity [strong-hybrid fuel]"
    assert L(t, cands, INV, tier=0, strong_hybrid=True)[0] is None


def test_strong_hybrid_is_refused_when_cardekho_names_another_fuel():
    for sub in ("1987 cc, Automatic, Diesel", "Electric, 42 kWh", "1498 cc, CNG", "1197 cc, Mild Hybrid"):
        cands = [X("Maruti Suzuki Invicto Zeta Plus 7Str", sub, fuel="Petrol", price=2502400)]
        t = T("Zeta Plus Hybrid (Electric + Petrol) Automatic 7 STR", fuel="Petrol Hybrid", trans="e-CVT", price=2502400)
        assert L(t, cands, INV, strong_hybrid=True)[0] is None, sub


def test_mild_hybrid_is_not_a_strong_hybrid():
    assert c.fuel("Petrol", "Mild Hybrid CVT Petrol Automatic") == "Petrol"          # X-Trail's CarWale fuel: so rule 2 is never switched on
    t = T("Mild Hybrid CVT Petrol Automatic", fuel="Petrol", trans="CVT", price=4819862)
    cands = [X("Nissan X-Trail STD", "1498 cc, Automatic, Petrol, 10 kmpl", fuel="Petrol", price=4819862)]
    assert L(t, cands, "Nissan X-Trail", strong_hybrid=False)[0] is None            # different names: sent to review, not linked
    tp = T("Zeta Plus Hybrid (Electric + Petrol) Automatic 7 STR", fuel="Petrol Hybrid", trans="e-CVT", price=2502400)
    assert L(tp, [X("Maruti Suzuki Invicto Zeta Plus 7Str", "Petrol", fuel="Petrol", price=2502400)], INV, strong_hybrid=False)[0] is None


def test_strong_hybrid_flag_in_extract_needs_every_current_version(cfg):
    def run(fuels):
        cw = {"modelPage": {"modelDetails": {"modelName": "Invicto", "makeName": "Maruti Suzuki", "status": 2},
                            "versions": [{"versionId": i, "versionName": n, "status": 2,
                                          "priceOverview": {"averageExShowRoomPrice": p, "priceLabel": "ex-showroom"},
                                          "specsSummary": [{"itemName": "Fuel Type", "value": f}, {"itemName": "Transmission Type", "value": "e-CVT"}],
                                          "featureSpecs": []} for i, (n, p, f) in enumerate(fuels, 1)]}}
        cdp = {"overView": {"name": "Maruti Suzuki Invicto"}, "variantTable": {"variantList": [
            {"title": "Maruti Suzuki Invicto " + n.split(" Hybrid")[0].replace("Plus", "Plus") + (" 7Str" if "7 STR" in n else ""), "url": "/v/" + n.split(" Hybrid")[0].replace(" ", ""), "fuelName": "Petrol", "exShowRoomPrice": p,
             "subText": "1987 cc, Automatic, Petrol", "variantStatus": "CURRENT"} for n, p, f in fuels]}}
        var = lambda n: "<script>window.__INITIAL_STATE__ = %s;</script>" % json.dumps({"selectedVariant": "Maruti Suzuki Invicto " + n.split(" Hybrid")[0] + (" 7Str" if "7 STR" in n else ""), "specsTechnicalJson": {
            "specification": [{"items": [{"text": "Fuel Type", "value": "Petrol"}, {"text": "Transmission Type", "value": "Automatic"}]}], "featured": []}})
        pages = {"cars/invicto/": '<script id="initial-state" type="application/json">%s</script>' % json.dumps(cw),
                 "m/invicto": "<script>window.__INITIAL_STATE__ = %s;</script>" % json.dumps(cdp)}
        pages.update({"/v/" + n.split(" Hybrid")[0].replace(" ", ""): var(n) for n, p, f in fuels})
        item = {"make": "Maruti Suzuki", "key": "invicto", "model": "Invicto", "cw": {"url": "https://cw/cars/invicto/"}, "cd": {"url": "https://cd/m/invicto"}}
        return extract.model_bundle(item, cfg, FakeFetcher(pages), lambda *a: None, {})
    all_strong = run([("Zeta Plus Hybrid (Electric + Petrol) Automatic 7 STR", 2502400, "Hybrid (Electric + Petrol)"),
                      ("Alpha Plus Hybrid (Electric + Petrol) Automatic 7 STR", 2870500, "Hybrid (Electric + Petrol)")])
    v = all_strong["versions"][0]
    assert v["fields_cd"] and "strong-hybrid fuel" in v["link_reason"]
    assert v["fields_cd"]["fuel_type"] == "Petrol Hybrid" and v["strong_hybrid_rule"]["cardekho_fuel"] == "Petrol"   # fuel is CarWale's, not CarDekho's "Petrol"
    mixed = run([("Zeta Plus Hybrid (Electric + Petrol) Automatic 7 STR", 2502400, "Hybrid (Electric + Petrol)"), ("Zeta Plus Petrol Manual", 2300000, "Petrol")])
    assert mixed["versions"][0]["fields_cd"] is None                                   # a plain-petrol version in the model switches rule 2 off


# ---------------------------------------------------------------- genuinely different names
def test_camry_elegant_does_not_link_to_elegance():
    cands = [X("Toyota Camry Elegance", "2487 cc, Automatic, Petrol", fuel="Petrol", price=4869000),
             X("Toyota Camry Sprint Edition", "2487 cc, Automatic, Petrol", fuel="Petrol", price=4869000)]
    t = T("Elegant Hybrid (Electric + Petrol) Automatic", fuel="Petrol Hybrid", trans="e-CVT", price=4869000)
    for tier in (1, 2):
        assert L(t, cands, "Toyota Camry", tier=tier, strong_hybrid=True, peers=[t])[0] is None
    assert L(dict(t, name="Elegant Hybrid (Electric + Petrol) Automatic Platinum White Pearl", price=4889000), cands, "Toyota Camry", tier=2, strong_hybrid=True)[0] is None


def test_zr_v_and_x_trail_stay_for_review():
    zrv = [X("Honda ZR-V Hybrid", "1993 cc, Automatic, Petrol, 22.8 kmpl", fuel="Petrol Hybrid", trans="e-CVT", price=4999900)]
    assert L(T("Sport Hybrid (Electric + Petrol) Automatic e:HEV", fuel="Petrol Hybrid", trans="e-CVT", price=4799000), zrv, "Honda ZR-V", strong_hybrid=True)[0] is None


# ---------------------------------------------------------------- tier 2: dual tone on one site
def test_fortuner_legender_links_dual_tone_only_with_exact_price_and_only_at_tier_2():
    cands = [X("Toyota Fortuner Legender 4x2 AT", "2755 cc, Automatic, Diesel", fuel="Diesel", price=4335000),
             X("Toyota Fortuner Legender 4x4", "2755 cc, Manual, Diesel", fuel="Diesel", trans="Manual", price=4553000)]
    t = T("4X2 2WD Diesel Turbo Automatic Dual Tone", fuel="Diesel", trans="Torque Converter", price=4335000)
    m = "Toyota Fortuner Legender"
    assert L(t, cands, m, tier=1)[0] is None
    hit, why = L(t, cands, m, tier=2)
    assert hit is cands[0] and why == "identity + price [dual tone on one site]"
    assert L(dict(t, price=4400000), cands, m, tier=2)[0] is None                       # price must agree
    assert L(T("4X4 4WD Diesel Turbo Manual Dual Tone", fuel="Diesel", trans="Manual", price=4553000), cands, m, tier=2)[0] is cands[1]
    mild = T("4X4 4WD Mild Hybrid (Electric + Diesel) Turbo Automatic Dual Tone", fuel="Diesel Mild Hybrid", trans="Torque Converter", price=4877000)
    assert L(mild, cands, m, tier=2)[0] is None                                          # "Neo Drive" is a different name


# ---------------------------------------------------------------- the original linker is untouched
@pytest.mark.parametrize("tier", [0, 1, 2])
def test_a_link_that_exists_today_never_changes(tier):
    kb = [{"name": "Adventure Plus", "fuel": "Petrol", "transmission": "Manual", "price": 800000},
          {"name": "Adventure Plus", "fuel": "Petrol", "transmission": "Manual", "price": 811990, "url": "2"}]
    t = {"name": "Adventure Plus Petrol Manual", "fuel": "Petrol", "transmission": "Manual", "price": 811990}
    assert match.link(t, kb, "Tata Punch", need_price=True, tier=tier) == match._strict_link(t, kb, "Tata Punch", need_price=True)
    assert match.link(t, kb, "Tata Punch", need_price=True, tier=tier)[0] is kb[1]


def test_without_tier_the_signature_behaves_as_before():
    kb = [{"name": "Pure", "fuel": "Petrol", "transmission": "Manual", "price": 767990}]
    t = {"name": "Pure Petrol Manual", "fuel": "Petrol", "transmission": "Manual", "price": 767990}
    assert match.link(t, kb, "Tata Punch")[0] is kb[0]
    ev = [X("Tata Tigor EV XE", "26 kWh", price=1249000)]
    assert match.link(T("XE 26.0 kWh", price=1249000), ev, "Tata Tigor EV", need_price=True, price_tol=0.005)[0] is None   # plan.py's KB match is unchanged


# ---------------------------------------------------------------- plan: D1 writes no price, and a review item
def test_price_disagreement_writes_no_price_and_raises_a_review_item():
    price_obs = {"source": "carwale", "raw_name": "Executive 17.3 kWh", "url": "https://cw/comet#vid=1", "observed_at": "t", "method": "m", "payload": {}}
    v = {"name": "Executive 17.3 kWh", "special": False, "link_reason": "identity (price differs) [battery]",
         "fields_cw": {"fuel_type": "Electric", "transmission": "Automatic", "price_ex_showroom": 647865},
         "fields_cd": {"fuel_type": "Electric", "transmission": "Automatic", "price_ex_showroom": 789800}, "cd_name": "MG Comet EV Executive",
         "obs_cw": price_obs, "obs_cd": dict(price_obs, source="cardekho", url="https://cd/comet-executive"),
         "price_disagrees": {"carwale_price": 647865, "cardekho_price": 789800, "cardekho_url": "https://cd/comet-executive"}, "strong_hybrid_rule": False, "brochure": []}
    assert plan._cands(v, "price_ex_showroom", {}) == []
    assert [x["value"] for x in plan._cands(v, "fuel_type", {})] == ["Electric", "Electric"]
    v2 = dict(v, price_disagrees=None)
    assert len(plan._cands(v2, "price_ex_showroom", {})) == 2


# ---------------------------------------------------------------- rule 5: brochure confirmation records, never blocks
def _bro(printed, qualifier=None):
    return {"field": "claimed_ev_range_km", "value": 510.0, "obs": {"payload": {"printed": {"claimed_ev_range_km": printed}, "qualifier": {"claimed_ev_range_km": qualifier} if qualifier else {}}}}


def test_brochure_confirms_battery_and_hybrid_in_the_link_reason_only():
    b = {"versions": [
        {"name": "Executive (O) LR 51.4 kWh", "fields_cd": {"airbags": 6}, "link_reason": "identity [battery]", "brochure": [_bro("51.4 kWh Driving range up to 510 km")]},
        {"name": "Premium 42.0 kWh", "fields_cd": {"airbags": 6}, "link_reason": "identity [battery]", "brochure": [_bro("51.4 kWh Driving range up to 510 km")]},
        {"name": "XE 26.0 kWh", "fields_cd": {"airbags": 6}, "link_reason": "identity [battery]", "brochure": []},
        {"name": "Zeta Plus Hybrid 7 STR", "fields_cd": {"airbags": 6}, "link_reason": "identity [strong-hybrid fuel]", "brochure": [_bro("strong hybrid 23.24 km/l")]},
        {"name": "Alpha", "fields_cd": None, "link_reason": "no candidate with the same identity", "brochure": []},
        {"name": "Plain", "fields_cd": {"airbags": 6}, "link_reason": "identity", "brochure": [_bro("51.4 kWh")]}]}
    brochure.confirm_links(b)
    r = [v["link_reason"] for v in b["versions"]]
    assert r[0] == "identity [battery]; brochure confirms trim and 51.4 kWh"
    assert r[1] == "identity [battery]"                   # the brochure names another battery: nothing recorded, link stays
    assert r[2] == "identity [battery]"                   # no brochure data (Comet, ZS EV, X-Trail, Camry): link stands on the two sites
    assert r[3] == "identity [strong-hybrid fuel]; brochure confirms trim and hybrid system"
    assert r[4] == "no candidate with the same identity" and r[5] == "identity"
