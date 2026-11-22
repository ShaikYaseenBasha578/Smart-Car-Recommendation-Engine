"""GET /compare?ids=: id parsing, the table, the Best marks, Not verified cells, empty state, title, escaping, remove links."""

import contextlib
import html as H
import io
import re

import pytest

from services.catalogue import get_catalogue
from services.compare import MAX_COMPARE, get_compare, mark_best, parse_ids

CAT = get_catalogue()


@pytest.fixture(scope="module")
def client():
    from app import app
    app.config["TESTING"] = True
    return app.test_client()


def get(client, path):
    with contextlib.redirect_stdout(io.StringIO()):
        return client.get(path)


def first_id(model, fuel):
    rows = CAT[(CAT["model"] == model) & (CAT["fuel_type"] == fuel)].sort_values(["price_ex_showroom", "variant_id"])
    return int(rows["variant_id"].iloc[0])


def text(response):
    return H.unescape(response.get_data(as_text=True))


def row_cells(data, label):
    return next(r for r in data["rows"] if r["label"] == label)["cells"]


def test_parse_ids_keeps_positive_ints_in_order_without_duplicates_and_caps_at_four():
    assert parse_ids("3,x,3,-1,0,7, 9 ,1.5,") == [3, 7, 9]
    assert parse_ids("") == [] and parse_ids(None) == [] and parse_ids(",,") == []
    assert parse_ids("1,2,3,4,5,6") == [1, 2, 3, 4] and MAX_COMPARE == 4


def test_two_variants_render_both_names_and_best_goes_to_the_cheaper_price(client):
    cheap, dear = first_id("Swift", "petrol"), first_id("Nexon", "petrol")
    prices = CAT.loc[[cheap, dear], "price_ex_showroom"]
    assert prices[cheap] < prices[dear]
    r = get(client, f"/compare?ids={dear},{cheap}")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Swift" in body and "Nexon" in body
    data = get_compare([dear, cheap])
    cells = row_cells(data, "Price (ex-showroom)")
    assert [c["best"] for c in cells] == [False, True]          # columns follow the ids order
    price_row = re.search(r"<tr>\s*<th scope=\"row\">Price \(ex-showroom\)</th>(.*?)</tr>", body, re.S).group(1)
    assert price_row.count('class="best-pill"') == 1 and "(best of these cars)" in price_row


def test_a_cell_the_car_page_calls_unverified_reads_not_verified():
    rows = CAT[CAT["unverified_fields"].map(lambda s: "boot_space_litres" in s)]
    assert not rows.empty, "catalogue has no variant with an unverified boot space"
    vid = int(rows["variant_id"].iloc[0])
    other = int(CAT[(CAT["variant_id"] != vid) & CAT["boot_space_litres"].notna()]["variant_id"].iloc[0])
    cell = row_cells(get_compare([vid, other]), "Boot space")[0]
    assert (cell["display"], cell["status"], cell["best"]) == ("Not verified", "unverified", False)


def test_not_verified_uses_the_site_style(client):
    rows = CAT[CAT["unverified_fields"].map(lambda s: "boot_space_litres" in s)]
    vid = int(rows["variant_id"].iloc[0])
    other = int(CAT[(CAT["variant_id"] != vid) & CAT["boot_space_litres"].notna()]["variant_id"].iloc[0])
    assert '<span class="not-verified">Not verified</span>' in get(client, f"/compare?ids={vid},{other}").get_data(as_text=True)


def test_electric_and_petrol_mileage_are_never_ranked_against_each_other():
    petrol, ev = first_id("Nexon", "petrol"), first_id("Nexon EV", "electric")
    cells = row_cells(get_compare([petrol, ev]), "Mileage / range")
    assert "kmpl" in cells[0]["display"] and cells[1]["display"].endswith(" km")
    assert [c["best"] for c in cells] == [False, False]


def test_mileage_best_only_within_a_unit_and_cng_is_km_per_kg():
    a, b, cng = first_id("Swift", "petrol"), first_id("Nexon", "petrol"), first_id("Swift", "cng")
    cells = row_cells(get_compare([a, b, cng]), "Mileage / range")
    assert cells[0]["best"] and not cells[1]["best"] and not cells[2]["best"]
    assert "km/kg" in cells[2]["display"] and "kmpl" not in cells[2]["display"]


def test_mark_best_rules():
    assert mark_best([5, 3], False, 0) == [False, True]
    assert mark_best([5, 5.0], False, 0) == [False, False]            # everything ties: nobody
    assert mark_best([5, None], False, 0) == [False, False]           # fewer than two known values
    assert mark_best([100, 105, 140], False, 10) == [True, True, False]
    assert mark_best([1, 9, 2, 8], True, 0, groups=["a", "a", "b", "b"]) == [False, True, False, True]


def test_low_confidence_owner_ratings_never_win():
    from services.recsys.explain import owner_standing
    from services.recsys.evidence import get_evidence
    ev = get_evidence()
    for model in CAT["model"].unique():
        st = owner_standing(model, ev)
        if st and st["band"] == "low_confidence":
            other = next(m for m in CAT["model"].unique() if (owner_standing(m, ev) or {}).get("band") not in (None, "low_confidence"))
            ids = [int(CAT[CAT["model"] == m]["variant_id"].iloc[0]) for m in (model, other)]
            cells = row_cells(get_compare(ids), "Owners")
            assert "only" in cells[0]["display"] and not cells[0]["best"]
            return
    pytest.skip("no low-confidence owner rating in the evidence")


def test_missing_ids_are_counted_and_noted(client):
    a, b = first_id("Swift", "petrol"), first_id("Nexon", "petrol")
    assert get_compare([a, b, 9999999])["missing"] == 1
    assert "1 car in this link is no longer in our catalogue." in text(get(client, f"/compare?ids={a},{b},9999999"))
    assert "2 cars in this link are no longer in our catalogue." in text(get(client, f"/compare?ids={a},{b},9999998,9999999"))


def test_fewer_than_two_cars_is_the_empty_state_with_200(client):
    a = first_id("Swift", "petrol")
    for path in ("/compare", "/compare?ids=", f"/compare?ids={a}", "/compare?ids=abc,-4", f"/compare?ids={a},9999999"):
        r = get(client, path)
        body = text(r)
        assert r.status_code == 200, path
        assert "Pick two to four cars to compare" in body and "<title>Compare cars | CarRec</title>" in body, path
        assert "<table" not in body


def test_title_lists_model_names_and_shortens_for_long_ones(client):
    a, b, c = first_id("Nexon", "petrol"), first_id("Punch", "petrol"), first_id("Brezza", "petrol")
    assert "<title>Nexon vs Punch vs Brezza | CarRec</title>" in text(get(client, f"/compare?ids={a},{b},{c}"))
    long_ids = [int(CAT[CAT["model"] == m]["variant_id"].iloc[0]) for m in
                ("Urban Cruiser Hyryder", "Innova Hycross", "Carens Clavis EV", "Grand Vitara")]
    body = text(get(client, "/compare?ids=" + ",".join(map(str, long_ids))))
    assert "<title>Compare 4 cars | CarRec</title>" in body


def test_q_is_escaped_in_the_back_link_and_the_link_round_trips_the_search(client):
    a, b = first_id("Swift", "petrol"), first_id("Nexon", "petrol")
    evil = '"><script>alert(1)</script> & SUV'
    from urllib.parse import quote
    raw = get(client, f"/compare?ids={a},{b}&q={quote(evil)}&drop=budget&sort=price").get_data(as_text=True)
    assert "<script>alert(1)" not in raw
    back = re.search(r'<a class="back-link-a" href="([^"]*)"', raw).group(1)
    assert back.startswith("/recommend?q=") and "drop=budget" in back and "sort=price" in back
    assert "Back to your results" in raw
    assert "Back to your results" not in get(client, f"/compare?ids={a},{b}").get_data(as_text=True)


def test_remove_links_drop_exactly_one_id_and_keep_the_search(client):
    ids = [first_id("Swift", "petrol"), first_id("Nexon", "petrol"), first_id("Punch", "petrol")]
    raw = get(client, "/compare?ids=" + ",".join(map(str, ids)) + "&q=suv&sort=mileage").get_data(as_text=True)
    hrefs = [H.unescape(h) for h in re.findall(r'<a class="compare-remove" href="([^"]*)"', raw)]
    assert len(hrefs) == 3
    for gone, href in zip(ids, hrefs):
        left = re.search(r"ids=([\d,]*)", href).group(1).split(",")
        assert sorted(left) == sorted(str(i) for i in ids if i != gone)
        assert "q=suv" in href and "sort=mileage" in href
    assert 'aria-label="Remove Maruti Suzuki Swift ' in raw
    # removing down to one car still works and shows the empty state
    two = get(client, f"/compare?ids={ids[0]},{ids[1]}").get_data(as_text=True)
    one_href = H.unescape(re.findall(r'<a class="compare-remove" href="([^"]*)"', two)[0])
    assert get(client, one_href).status_code == 200


def test_table_markup_has_headers_a_scroll_region_and_a_footnote(client):
    a, b = first_id("Swift", "petrol"), first_id("Nexon", "petrol")
    raw = get(client, f"/compare?ids={a},{b}").get_data(as_text=True)
    assert '<table class="compare-table"' in raw and '<caption class="sr-only">' in raw
    assert raw.count('<th scope="col"') == 2 and raw.count('<th scope="row">') == 12
    assert 'role="region" aria-label="Comparison table" tabindex="0"' in raw
    assert "Mileage is compared only between cars with the same unit." in raw and "Prices and specs updated" in raw
    assert "/car/maruti-suzuki/swift?variant_id=" in raw
