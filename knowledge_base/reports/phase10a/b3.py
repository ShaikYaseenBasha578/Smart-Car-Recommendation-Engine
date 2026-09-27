import sqlite3,csv,collections,re
c=sqlite3.connect('carrec_kb.db')
norm=lambda s:re.sub(r'[^a-z0-9]','',s.lower())
def fuel(s):
    s=s.lower()
    for k,v in [('cng','CNG'),('diesel','Diesel'),('kwh','Electric'),('electric','Electric'),('hybrid','Hybrid'),('petrol','Petrol')]:
        if k in s: return v
def tx(s):
    s=' '+s.lower()+' '
    if any(k in s for k in ['automatic','amt','dct','cvt','ivt',' at ','(tc)','e-cvt']): return 'A'
    if 'manual' in s or ' mt' in s: return 'M'
rows=c.execute("""select so.id,so.raw_name,v.id,v.name,v.transmission,p.fuel_type from source_observation so join variant v on v.id=so.resolved_variant_id join powertrain p on p.id=v.powertrain_id where so.source_id=4""").fetchall()
cnt=collections.Counter(); obs_rows=[]; loose=[]
for oid,raw,vid,vn,t,f in rows:
    rf=fuel(raw); vf='Hybrid' if 'Hybrid' in f else ('CNG' if 'CNG' in f else f.split()[0]); rt=tx(raw); vt='M' if t in('Manual','iMT') else 'A'
    bad=[]
    if rf and rf!=vf and not (rf=='Petrol' and vf in('Hybrid','CNG')) and not(rf=='Hybrid' and vf=='Petrol'): bad.append('FUEL')
    if rt and rt!=vt and t!='iMT': bad.append('TX')
    tags=[]
    if bad: tags.append('STRUCTURAL_'+'+'.join(bad))
    if oid in (2842,2843): tags.append('CRETA_E_EX_SWAP')
    if vid==820: tags.append('ON_VARIANT_820')
    if tags: obs_rows.append((oid,raw,vid,vn,';'.join(tags)))
    elif norm(raw)!=norm(vn) and c.execute("select count(*) from source_observation where source_id=4 and resolved_variant_id=?",(vid,)).fetchone()[0]>1: loose.append((oid,raw,vid,vn))
w=csv.writer(open('B3_affected.csv','w'));w.writerow(['table','id','variant_id','raw_name_or_field','resolved_variant_name','decision','value','tags','contamination'])
for oid,raw,vid,vn,tags in obs_rows:
    w.writerow(['source_observation',oid,vid,raw,vn,'','',tags,'']); cnt['obs']+=1
    for fid,fvid,fld,d,val in c.execute("select id,variant_id,field_name,decision,accepted_value from field_provenance where source_observation_id=?",(oid,)).fetchall():
        sup=c.execute("select count(*) from field_provenance fp join source_observation so on so.id=fp.source_observation_id where fp.variant_id=? and fp.field_name=? and fp.id<>? and fp.decision in('accepted','confirmed') and not (so.source_id=4 and so.id in (%s))"%','.join(str(o[0]) for o in obs_rows),(fvid,fld,fid)).fetchone()[0]
        cont='SOLE_SOURCE_CANONICAL' if d=='accepted' and sup==0 else ('ACCEPTED_BUT_SUPPORTED' if d=='accepted' else ('CONFIRMATION_ONLY' if d=='confirmed' else 'REJECTED_INERT'))
        w.writerow(['field_provenance',fid,fvid,fld,vn,d,val,tags,cont]); cnt['fp']+=1; cnt[cont]+=1
csv.writer(open('B3_loose_name_mismatch_UNDETERMINABLE.csv','w')).writerows([('source_observation_id','raw_name','variant_id','variant_name')]+loose)
tagc=collections.Counter(t for r in obs_rows for t in r[4].split(';'))
print(dict(cnt),dict(tagc),'loose',len(loose),'variants',len({r[2] for r in obs_rows}))
