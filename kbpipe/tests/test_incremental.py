"""Discovery classification and change detection, on synthetic pages shaped like the two sites' payloads."""
import json
import sqlite3

from kbpipe import discover, extract, kb


def cw_brand(models, gone=()):
    st = {"makePage": {"models": [{"modelName": n, "modelMaskingName": n.lower(), "status": s, "bodyStyleId": 6,
                                   "priceOverview": {"price": p}, "launchedOn": "01/13/2026 00:00:00"} for n, s, p in models],
                       "discontinuedModels": [{"modelName": n, "modelMaskingName": n.lower()} for n in gone]}}
    return '<script id="initial-state" type="application/json">%s</script>' % json.dumps(st)


def cd_brand(models, gone=()):
    st = {"items": [{"name": n, "slug": n.lower(), "minComparePrice": p, "vehicleType": "Sport Utilities", "modelUrl": "/tata/" + n.lower()}
                    for n, p in models], "upcomingCars": {"items": []}, "ExpiredCars": {"list": [{"text": "Tata " + n, "link": "/x"} for n in gone]}}
    return "<script>window.__INITIAL_STATE__ = %s; window.x = 1;</script>" % json.dumps(st)


def cw_model(versions):
    st = {"modelPage": {"modelDetails": {"modelName": "Punch", "makeName": "Tata", "status": 2, "launchedOn": "01/13/2026 00:00:00"},
                        "versions": [{"versionId": i, "versionName": n, "status": 2,
                                      "priceOverview": {"averageExShowRoomPrice": p, "priceLabel": "Avg. Ex-Showroom price"},
                                      "specsSummary": [{"itemName": "Fuel Type", "value": "Petrol"}, {"itemName": "Transmission Type", "value": "Manual"}],
                                      "featureSpecs": [{"itemName": "Airbags", "value": "6"}]} for i, n, p in versions]}}
    return '<script id="initial-state" type="application/json">%s</script>' % json.dumps(st)


def cd_model(variants):
    st = {"overView": {"name": "Tata Punch"}, "variantTable": {"variantList": [
        {"title": "Tata Punch " + n, "url": "/v/" + n, "fuelName": "Petrol", "exShowRoomPrice": p, "subText": "1199 cc, Manual, Petrol",
         "variantStatus": "CURRENT"} for n, p in variants]}}
    return "<script>window.__INITIAL_STATE__ = %s;</script>" % json.dumps(st)


def cd_variant(name):
    st = {"selectedVariant": "Tata Punch " + name, "specsTechnicalJson": {"specification": [{"items": [
        {"text": "Fuel Type", "value": "Petrol"}, {"text": "Transmission Type", "value": "Manual"}]}], "featured": [{"items": [{"text": "No. of Airbags", "value": "6"}]}]}}
    return "<script>window.__INITIAL_STATE__ = %s;</script>" % json.dumps(st)


class FakeFetcher:
    def __init__(self, pages):
        self.pages, self.asked = pages, []

    def get(self, url, max_age_days=None, binary=False):
        self.asked.append(url)
        for k, v in self.pages.items():
            if url.endswith(k):
                return v, {"fetched_at": "2026-11-13T00:00:00Z", "sha256": "0" * 64}
        return None, None


def test_discovery_classifies_existing_new_one_site_out_of_scope_and_vanished(cfg, kbfile):
    cfg["scope_makes"] = ["Tata"]
    f = FakeFetcher({"tata-cars/": cw_brand([("Nexon", 2, 800000), ("Punch", 2, 574990), ("Avinya", 1, 0), ("Dear", 2, 9000000), ("Onlycw", 2, 700000)], gone=["Bolt"]),
                     "cars/Tata": cd_brand([("Nexon", 800000), ("Punch", 574990), ("Dear", 9000000), ("Xpres", 574000)], gone=["Bolt"])})
    c = sqlite3.connect(kbfile); c.execute("insert into model(id,manufacturer_id,name,body_type) values (2,1,'Tigor','Sedan')"); c.commit(); c.close()
    lst, failed = discover.listings(cfg, f, lambda *a: None)
    kinds = {i["model"]: i["kind"] for i in discover.classify(cfg, kb.ro(kbfile), lst, failed)}
    assert failed == []
    assert kinds["Nexon"] == "EXISTING" and kinds["Punch"] == "NEW_MODEL"
    assert kinds["Dear"] == "OUT_OF_SCOPE" and kinds["Avinya"] == "UPCOMING" and kinds["Bolt"] == "NOT_ON_SALE"
    assert kinds["Xpres"] == "ONE_SITE_ONLY" and kinds["Onlycw"] == "ONE_SITE_ONLY"
    assert kinds["Tigor"] == "DISCONTINUED_CANDIDATE"          # in the KB, on neither site: flagged, never deleted


def test_an_unreadable_listing_never_looks_like_a_discontinuation(cfg, kbfile):
    cfg["scope_makes"] = ["Tata"]
    f = FakeFetcher({"tata-cars/": cw_brand([("Punch", 2, 574990)])})        # CarDekho page missing
    lst, failed = discover.listings(cfg, f, lambda *a: None)
    kinds = {i["model"]: i["kind"] for i in discover.classify(cfg, kb.ro(kbfile), lst, failed)}
    assert failed and kinds["Nexon"] == "UNKNOWN" and kinds["Punch"] == "UNKNOWN"


def _bundle(cfg, versions, variants, state):
    item = {"make": "Tata", "key": "punch", "model": "Punch", "cw": {"url": "https://cw/tata-cars/punch/"}, "cd": {"url": "https://cd/tata/punch"}}
    pages = {"tata-cars/punch/": cw_model(versions), "tata/punch": cd_model(variants)}
    pages.update({"/v/" + n: cd_variant(n) for n, _ in variants})
    return extract.model_bundle(item, cfg, FakeFetcher(pages), lambda *a: None, state)


def test_incremental_detection_unchanged_price_change_and_new_variant(cfg):
    v1 = [(1, "Pure Petrol Manual", 664990)]
    d1 = [("Pure", 664990)]
    b = _bundle(cfg, v1, d1, {})
    assert b["changed"] is True and b["versions"][0]["fields_cd"]["airbags"] == 6       # first sight, linked on both sites
    state = {"Tata/punch": {"fingerprint": b["fingerprint"], "applied": True}}
    assert _bundle(cfg, v1, d1, state)["changed"] is False                              # nothing changed -> skipped by the run
    assert _bundle(cfg, [(1, "Pure Petrol Manual", 674990)], [("Pure", 674990)], state)["changed"] is True      # price moved
    assert _bundle(cfg, v1 + [(2, "Smart Petrol Manual", 574990)], d1 + [("Smart", 574990)], state)["changed"] is True


def test_cardekho_page_for_another_variant_is_not_used(cfg):
    item = {"make": "Tata", "key": "punch", "model": "Punch", "cw": {"url": "https://cw/tata-cars/punch/"}, "cd": {"url": "https://cd/tata/punch"}}
    pages = {"tata-cars/punch/": cw_model([(1, "Pure Petrol Manual", 664990)]), "tata/punch": cd_model([("Pure", 664990)]),
             "/v/Pure": cd_variant("Adventure")}                                         # the site serves the wrong variant
    b = extract.model_bundle(item, cfg, FakeFetcher(pages), lambda *a: None, {})
    assert b["versions"][0]["fields_cd"] is None and "not used" in b["problems"][0]
