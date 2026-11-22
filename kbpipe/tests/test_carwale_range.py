"""CarWale EV range from the version's specsSummary ("Expected Range", itemId 459) with the battery identity guard.
Inline dicts follow the structure of real cached model-page payloads (no cache reads)."""
from kbpipe.sources import carwale


def _it(item_id, name, value, unit):
    return {"itemId": item_id, "value": value, "itemName": name, "unitType": unit, "customTypeId": -1,
            "DataTypeId": 3, "isHighlighted": False}


def _ver(name, fuel="Electric", rng=None, battery=None, label="Expected Range", item_id=459, unit="km"):
    sp = [_it(1, "Fuel Type", fuel, "")]
    if battery is not None:
        sp.append(_it(466, "Battery Capacity", battery, "kWh"))
    if rng is not None:
        sp.append(_it(item_id, label, rng, unit))
    return {"versionId": 1, "versionName": name, "specsSummary": sp, "featureSpecs": []}


def test_expected_range_item_459():
    f = carwale._map_version(_ver("EC PRO 34.5 kWh", rng="375", battery="34.5"))
    assert f["claimed_ev_range_km"] == 375


def test_driving_range_label_still_works():
    f = carwale._map_version(_ver("Pro", rng="420", label="Driving Range", item_id=1001))
    assert f["claimed_ev_range_km"] == 420
    f = carwale._map_version(_ver("Pro", rng="421", label="Range", item_id=1002))
    assert f["claimed_ev_range_km"] == 421


def test_bad_unit_or_out_of_range_not_emitted():
    for rng, unit in [("375", "miles"), ("375", "kWh"), ("99", "km"), ("1001", "km"), ("", "km"), ("375 to 456", "km")]:
        assert "claimed_ev_range_km" not in carwale._map_version(_ver("Pro", rng=rng, unit=unit))
    assert carwale._map_version(_ver("Pro", rng="375", unit=""))["claimed_ev_range_km"] == 375


def test_non_electric_not_emitted():
    f = carwale._map_version(_ver("VXi Petrol", fuel="Petrol", rng="375"))
    assert "claimed_ev_range_km" not in f


def test_only_specs_summary_is_read():
    v = _ver("Pro")
    v["featureSpecs"] = [_it(459, "Expected Range", "375", "km")]
    assert "claimed_ev_range_km" not in carwale._map_version(v)


def test_battery_guard():
    # XEV 9e case: name says 59.0 kWh but the payload carries the 79 kWh pack
    v = _ver("Pack Three Select 59.0 kWh 11.2kW Charger", rng="656", battery="79")
    assert "claimed_ev_range_km" not in carwale._map_version(v)
    v = _ver("Pack Three Select 59.0 kWh 7.2kW", rng="542", battery="59")
    assert carwale._map_version(v)["claimed_ev_range_km"] == 542
    v = _ver("Pack Three Select 59 kWh 7.2kW", rng="542", battery="59.5")
    assert carwale._map_version(v)["claimed_ev_range_km"] == 542
    v = _ver("Pack Three Select 59.0 kWh 7.2kW", rng="542")           # no capacity item: guard does not block
    assert carwale._map_version(v)["claimed_ev_range_km"] == 542
    v = _ver("Pack Three Select 7.2kW", rng="542", battery="79")      # no pack size in name: guard does not block
    assert carwale._map_version(v)["claimed_ev_range_km"] == 542
