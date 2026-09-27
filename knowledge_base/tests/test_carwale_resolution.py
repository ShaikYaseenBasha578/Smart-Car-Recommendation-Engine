"""Phase 10C-2: CarWale resolution must fail closed on fuel/transmission and never use 91wheels aliases.
Runs entirely on an in-memory DB built from fixtures/carwale_resolution_fixture.json (extracted from a /tmp copy
of production; the production DB is never opened).
Run ONLY as: pytest knowledge_base/tests/test_carwale_resolution.py"""
import json, os, sqlite3
import pytest
from knowledge_base.ingestion.carwale.field_map_carwale import parse_version_name
from knowledge_base.ingestion.carwale.ingest_carwale import resolve_carwale_version
from knowledge_base.ingestion.common.resolver import validate_structured, AUTO_TRANSMISSIONS, FUEL_FAMILIES

FX = json.load(open(os.path.join(os.path.dirname(__file__), 'fixtures', 'carwale_resolution_fixture.json')))
# obs 3185 is the exact-name source of edition variant 820 (probable W1 false positive, PHASE10B_W1_REPORT.md)
EXPECTED_CORRECT = {3185}


def build_db():
    c = sqlite3.connect(':memory:')
    c.row_factory = sqlite3.Row
    c.executescript("""
      CREATE TABLE source (id INTEGER PRIMARY KEY, name TEXT);
      CREATE TABLE manufacturer (id INTEGER PRIMARY KEY, name TEXT);
      CREATE TABLE model (id INTEGER PRIMARY KEY, manufacturer_id INTEGER, name TEXT);
      CREATE TABLE powertrain (id INTEGER PRIMARY KEY, model_id INTEGER, fuel_type TEXT, engine_cc REAL, power_bhp REAL);
      CREATE TABLE variant (id INTEGER PRIMARY KEY, model_id INTEGER, generation_id INTEGER, powertrain_id INTEGER, name TEXT,
                            transmission TEXT, price_ex_showroom REAL, base_variant_id INTEGER, is_discontinued INTEGER);
      CREATE TABLE variant_alias (variant_id INTEGER, source_id INTEGER, alias_name TEXT, needs_review INTEGER, is_verified INTEGER);""")
    for t in ('source', 'manufacturer', 'model', 'powertrain', 'variant', 'variant_alias'):
        for r in FX[t]:
            c.execute(f'insert into {t} values ({",".join("?" * len(r))})', r)
    return c


@pytest.fixture(scope='module')
def db():
    return build_db()


def slugs(case):
    return case['make'].lower().replace(' ', '-'), case['model'].lower().replace(' ', '-')


def fuel_trans(db, vid):
    r = db.execute('select p.fuel_type, v.transmission from variant v join powertrain p on p.id=v.powertrain_id where v.id=?', (vid,)).fetchone()
    return r['fuel_type'], r['transmission']


def consistent(db, vid, fuel, trans):
    return validate_structured(dict(zip(('fuel_type', 'transmission', 'engine_cc', 'price_ex_showroom'),
                                        (*fuel_trans(db, vid), None, None))), fuel, trans, None, None) == []


# --- parser -------------------------------------------------------------------------------------
@pytest.mark.parametrize('name,expected', [
    ('HX 5 Diesel 1.5L Turbo Automatic (TC)', ('Diesel', 'TC')),
    ('SX Premium Petrol 1.5L Manual Dual Tone', ('Petrol', 'MT')),
    ('V Petrol Automatic', ('Petrol', 'AT')),
    ('Pure Petrol 1.2L Automatic (AMT)', ('Petrol', 'AMT')),
    ('GTX (A) Petrol 1.5L Automatic (CVT) Dual Tone', ('Petrol', 'CVT')),
    ('Delta CNG Manual', ('CNG', 'MT')),
    ('VXi Petrol Manual Smart Hybrid', ('Petrol', 'MT')),
    ('Zeta Plus 2WD Hybrid (Electric + Petrol) 1.5L Automatic (e-CVT)', ('Hybrid', 'CVT')),
    ('Empowered Plus A 45.0 kWh Dark Edition', ('Electric', 'AT')),
    ('AX7 T 2WD Diesel 2.2L Turbo Manual 7 STR', ('Diesel', 'MT')),
    ('Topline Petrol 1.5L Turbo Automatic (DCT)', ('Petrol', 'DCT')),
    ('Zeta 1.2 iMT', (None, 'MT')),
    ('Alpha', (None, None)),
])
def test_parse_version_name(name, expected):
    assert parse_version_name(name) == expected


# --- validator ----------------------------------------------------------------------------------
def test_validator_at_is_automatic():
    assert 'at' in AUTO_TRANSMISSIONS
    assert validate_structured({'fuel_type': 'Petrol', 'transmission': 'Manual', 'engine_cc': None, 'price_ex_showroom': None},
                               'Petrol', 'AT', None, None) == ['transmission_mismatch']


def test_validator_fuel_families():
    c = lambda f: {'fuel_type': f, 'transmission': 'Automatic', 'engine_cc': None, 'price_ex_showroom': None}
    assert validate_structured(c('Petrol Hybrid'), 'Hybrid', 'AT', None, None) == []
    assert validate_structured(c('Diesel Mild Hybrid'), 'Diesel', 'AT', None, None) == []
    assert validate_structured(c('Petrol Hybrid'), 'Petrol', 'AT', None, None) == ['fuel_mismatch']
    assert validate_structured(c('Petrol'), 'CNG', 'AT', None, None) == ['fuel_mismatch']
    assert FUEL_FAMILIES['cng'] == {'cng'}


# --- fail closed --------------------------------------------------------------------------------
def test_unparseable_is_unresolved_without_guessing(db):
    case = FX['cases'][0]
    assert resolve_carwale_version(db, *slugs(case), 'Alpha', 'alpha') == (None, 'unresolved', None)
    assert resolve_carwale_version(db, *slugs(case), 'Zeta 1.2 iMT', 'zeta-12-imt') == (None, 'unresolved', None)


def test_does_not_use_91wheels_alias(db):
    # Plant a 91wheels alias for a CarWale slug pointing at a fuel-consistent variant: CarWale must not follow it.
    case = next(c for c in FX['cases'] if c['observation_id'] == 2820)
    make, model = slugs(case)
    target = db.execute("select v.id from variant v join model m on m.id=v.model_id join powertrain p on p.id=v.powertrain_id "
                        "where m.name=? and p.fuel_type='Petrol' and v.transmission<>'Manual' order by v.id limit 1", (case['model'],)).fetchone()['id']
    db.execute("insert into variant_alias values (?, 2, 'zz-planted-slug', 0, 1)", (target,))
    vid, status, _ = resolve_carwale_version(db, make, model, 'Nonexistent Trim Petrol Automatic', 'zz-planted-slug')
    db.execute("delete from variant_alias where alias_name='zz-planted-slug'")
    assert vid != target


@pytest.mark.parametrize('oid,bad_vid', [(2928, 152), (2858, 23), (2820, 647)])
def test_10a_examples(db, oid, bad_vid):
    case = next(c for c in FX['cases'] if c['observation_id'] == oid)
    assert case['must_not_resolve_to'] == bad_vid
    fuel, trans = parse_version_name(case['raw_name'])
    vid, status, base = resolve_carwale_version(db, *slugs(case), case['raw_name'], case['slug'])
    assert vid != bad_vid
    if vid: assert consistent(db, vid, fuel, trans)
    if base: assert consistent(db, base, fuel, trans)


@pytest.mark.parametrize('case', [c for c in FX['cases'] if c['observation_id'] not in EXPECTED_CORRECT],
                         ids=lambda c: str(c['observation_id']))
def test_b3_cases_never_reproduce_bad_resolution(db, case):
    fuel, trans = parse_version_name(case['raw_name'])
    vid, status, base = resolve_carwale_version(db, *slugs(case), case['raw_name'], case['slug'])
    assert vid != case['must_not_resolve_to']
    if vid: assert consistent(db, vid, fuel, trans)
    if base: assert consistent(db, base, fuel, trans)


def test_3185_exact_source_still_resolves(db):
    case = next(c for c in FX['cases'] if c['observation_id'] == 3185)
    vid, status, _ = resolve_carwale_version(db, *slugs(case), case['raw_name'], case['slug'])
    assert vid == 820 and status == 'resolved'
