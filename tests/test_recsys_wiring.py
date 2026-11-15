import pytest

import services.new_car_service as ncs


def _make_json_safe(v):
    return v


def test_unset_ranker_reaches_v3(monkeypatch):
    """v3 is the default engine: with no RANKER set the request goes to services.recsys."""
    monkeypatch.delenv("RANKER", raising=False)
    import services.recsys.api as api
    seen = {}
    monkeypatch.setattr(api, "recommend", lambda q, **k: seen.update(q=q) or {"engine": "v3", "recommendations": []})
    assert ncs.get_kb_recommendations("family suv under 15 lakh", ".", _make_json_safe)["engine"] == "v3"
    assert seen["q"] == "family suv under 15 lakh"


@pytest.mark.parametrize("name", ["current", "CURRENT", " current ", "old", "v2"])
def test_current_ranker_selects_the_old_engine_and_never_reaches_v3(monkeypatch, name):
    monkeypatch.setenv("RANKER", name)
    import services.recsys.api as api
    monkeypatch.setattr(api, "recommend", lambda *a, **k: (_ for _ in ()).throw(AssertionError("v3 reached")))
    r = ncs.get_kb_recommendations("family suv under 15 lakh", ".", _make_json_safe)
    assert "engine" not in r and r["parser_used"] == "intent_v2" and r["recommendations"]
    assert "ranking_score" in r["recommendations"][0] and "scores" not in r["recommendations"][0]


def test_unknown_ranker_value_falls_back_to_the_default_v3(monkeypatch):
    monkeypatch.setenv("RANKER", "banana")
    assert ncs.ranker_name() == "v3"


def test_v3_path_is_reached_with_env_switch(monkeypatch):
    import services.recsys.api as api
    seen = {}

    def fake(query, drop=None, weight_overrides=None, **kw):
        seen.update(query=query, drop=drop, kw=kw)
        return {"engine": "v3", "recommendations": []}

    monkeypatch.setattr(api, "recommend", fake)
    monkeypatch.setenv("RANKER", "v3")
    r = ncs.get_kb_recommendations("some query", "/root", _make_json_safe, drop=["budget"])
    assert r == {"engine": "v3", "recommendations": []}
    assert seen["query"] == "some query" and seen["drop"] == ["budget"] and seen["kw"]["app_root_path"] == "/root"


def test_get_new_car_recommendations_routes_to_v3(monkeypatch):
    import services.recsys.api as api
    monkeypatch.setattr(api, "recommend", lambda *a, **k: {"engine": "v3"})
    monkeypatch.setenv("RANKER", "v3")
    assert ncs.get_new_car_recommendations("q", None, None, ".", _make_json_safe)["engine"] == "v3"
