import sqlite3,csv,collections,json
c=sqlite3.connect('carrec_kb.db')
rows=c.execute("""select fp.id,fp.variant_id,fp.field_name,s.name,fp.source_observation_id from field_provenance fp join source_observation so on so.id=fp.source_observation_id join source s on s.id=so.source_id
 where fp.decision='accepted' and fp.accepted_value='0' and so.source_id in (2,3) order by s.name,fp.id""").fetchall()
out=[];cnt=collections.Counter();cur_changed=0
for fid,vid,f,src,oid in rows:
    others=c.execute("""select s.name,fp.decision,fp.accepted_value from field_provenance fp join source_observation so on so.id=fp.source_observation_id join source s on s.id=so.source_id
      where fp.variant_id=? and fp.field_name=? and fp.id<>? and so.source_id<>so2 """.replace("so2","(select source_id from source_observation where id=?)"),(vid,f,fid,oid)).fetchall()
    vals=[o[2] for o in others if o[2] is not None]
    nz=[v for v in vals if str(v) not in ('0','0.0','False','false')]
    z=[v for v in vals if str(v) in ('0','0.0','False','false')]
    cls='CONTRADICTED' if nz else ('CORROBORATED' if z else 'SOLE-SOURCE')
    canon=c.execute(f"select {f} from variant where id=?",(vid,)).fetchone()[0]
    if str(canon) not in ('0','0.0'): cur_changed+=1
    cnt[(src,cls)]+=1
    out.append([fid,vid,f,src,oid,canon,cls,';'.join(f"{o[0]}:{o[1]}:{o[2]}" for o in others)])
w=csv.writer(open('B1_affected.csv','w'));w.writerow(['field_provenance_id','variant_id','field','zero_source','source_observation_id','canonical_now','classification','other_source_evidence'])
w.writerows(out)
print(len(out),dict(cnt),'canonical_not_0_now',cur_changed)
print(collections.Counter((r[3],r[2],r[6]) for r in out).most_common(30))
