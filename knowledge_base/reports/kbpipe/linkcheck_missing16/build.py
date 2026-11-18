import sys, os, json, csv, random, collections, re
sys.path.insert(0, os.getcwd())
from kbpipe import config, fetch, extract
from kbpipe.sources import cardekho as cd, common as c
cfg = config.load() if hasattr(config, 'load') else dict(config.DEFAULTS)
cfg = dict(cfg, refresh_days={k: 10**6 for k in cfg['refresh_days']})
f = fetch.Fetcher(cfg, log=lambda *a: None)
disc = json.load(open('knowledge_base/runs/update_full_2026-11-17_specs/discovery.json'))
ex = {"%s/%s" % (r['model'].split('/')[0], r['model'].split('/')[1]) for r in csv.DictReader(open('knowledge_base/reports/kbpipe/missing16_regression_new_pairs_existing_models.tsv'), delimiter='\t')}
items = [x for x in disc if x.get('kind') == 'NEW_MODEL' or "%s/%s" % (x['make'], x['model']) in ex]
print(len(items), 'models', file=sys.stderr)
rows = []
for it in items:
    b = extract.model_bundle(it, cfg, f, lambda *a: None, {})
    p2, _ = f.get(it['cd']['url'], max_age_days=10**6)
    subs = {v['url']: v for v in (cd.parse_model(p2) or {}).get('variants', [])} if p2 else {}
    for v in b.get('versions', []):
        why = v.get('link_reason') or ''
        if not v.get('cd_name'):
            continue
        new = ('[' in why) or ('price differs' in why) or it['model'] == 'XUV400'
        if not new:
            continue
        cls = ('dual tone' if 'dual tone' in why else 'strong hybrid' if 'strong-hybrid' in why else
               'price differs + battery' if ('price differs' in why and 'battery' in why) else 'price differs' if 'price differs' in why else
               'battery' if 'battery' in why else 'descriptor' if 'descriptor' in why else 'page spelling (XUV400)' if it['model'] == 'XUV400' else 'other')
        fw = v['fields_cw']; cdu = v['obs_cd']['url'] if v.get('obs_cd') else ''
        s = subs.get(cdu, {})
        rows.append({'make': it['make'], 'model': it['model'], 'group': 'new model' if it.get('kind') == 'NEW_MODEL' else 'existing model', 'cls': cls, 'reason': why,
                     'cw_name': v['name'], 'cw_url': v['obs_cw']['url'], 'cw_fuel': fw.get('fuel_type'), 'cw_gearbox': fw.get('transmission'),
                     'cw_price': fw.get('price_ex_showroom'), 'cw_engine_cc': fw.get('engine_cc'), 'cw_battery_kwh': c.battery_kwh(v['name']) or fw.get('battery_capacity_kwh'),
                     'cw_seats': fw.get('seating_capacity'), 'cd_name': v['cd_name'], 'cd_url': cdu, 'cd_fuel': s.get('fuel'), 'cd_specline': s.get('sub'), 'cd_price': s.get('price')})
json.dump(rows, open('/tmp/carrec_audit/blind16/all_new_links.json', 'w'), indent=1, default=str)
print(collections.Counter((r['group'], r['cls']) for r in rows))
