import sqlite3,csv,collections
c=sqlite3.connect('carrec_kb.db')
obs=c.execute("select id,raw_name,resolved_variant_id,resolution_status from source_observation where source_id=1 and source_url='offline_brochure' order by id").fetchall()
fps=c.execute("""select fp.id,fp.variant_id,fp.field_name,fp.decision,fp.decision_reason,fp.accepted_value,fp.source_observation_id from field_provenance fp
 where fp.source_observation_id in (select id from source_observation where source_id=1 and source_url='offline_brochure') order by fp.id""").fetchall()
w=csv.writer(open('B2_affected.csv','w'));w.writerow(['table','id','variant_id','field','decision','decision_reason','value','source_observation_id','raw_name','tier_effect_if_oem_tier1','canonical_now','other_live_support'])
for o in obs: w.writerow(['source_observation',o[0],o[2],'','',o[3],'',o[0],o[1],'','',''])
eff=collections.Counter()
for fid,vid,f,d,reason,val,oid in fps:
    canon=c.execute(f"select {f} from variant where id=?",(vid,)).fetchone()[0] if f in [r[1] for r in c.execute('pragma table_info(variant)')] else None
    others=c.execute("""select s.name||':'||fp.decision||':'||coalesce(fp.accepted_value,'') from field_provenance fp join source_observation so on so.id=fp.source_observation_id join source s on s.id=so.source_id
       where fp.variant_id=? and fp.field_name=? and fp.id<>? and so.source_url<>'offline_brochure'""",(vid,f,fid)).fetchall()
    if d=='rejected': e='WOULD_FLIP_TO_ACCEPTED (tier1 < best existing)'
    elif d=='accepted': e='unchanged (already accepted; sole support)' if not others else 'unchanged (accepted)'
    else: e='unchanged (agrees)'
    eff[(d,e)]+=1
    w.writerow(['field_provenance',fid,vid,f,d,reason,val,oid,'',e,canon,';'.join(x[0] for x in others)])
print(len(obs),len(fps),eff)
for r in c.execute("""select fp.id,fp.variant_id,fp.field_name,fp.accepted_value oem_value,v.name from field_provenance fp join variant v on v.id=fp.variant_id where fp.decision='rejected' and fp.source_observation_id in (select id from source_observation where source_url='offline_brochure')""").fetchall():
    canon=c.execute(f"select {r[2]} from variant where id=?",(r[1],)).fetchone()[0]; print(r,'canon=',canon)
