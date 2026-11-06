import fitz, os, re, sys, hashlib, json
O="/Users/shaikyaseenbasha/Car_recommender_app/Flask Based App with Used Cars Function/knowledge_base/sources/oem/"
FEAT=r"cruise|paddle|sunroof|skyroof|head.?up|\bhud\b|wireless (phone |smartphone |mobile )?charg|ventilat|tyre pressure|tpms|android|carplay|climate|fatc|temperature control|rear (view )?camera|reverse (parking )?camera|hill|\besc\b|stability|rear ac|ac vents|360|adas|drive mode|connected|parking sensor"
QUAL=r"\b(at|amt|ags|cvt|ivt|dct|dsg|dca|mt|tc|e-?cvt|petrol|diesel|cng|turbo|tsi|pl)\s*(only|-?\s*only|variants?)\b|\bonly\b|\(\s*(at|amt|cvt|dct|ivt|mt|dsg|ags|6at|mt & [a-z ]+|petrol|diesel|cng|turbo)\s*\)|(?<![a-z])6at(?![a-z])|\bags\b|strong hybrid|\ballgrip\b|\bexcept\b"
out=[]
for root,_,fs in os.walk(O):
    if "_quarantine" in root: continue
    for f in fs:
        if not f.endswith(".pdf"): continue
        p=os.path.join(root,f); rel=p[len(O):]
        d=fitz.open(p)
        for i,pg in enumerate(d,1):
            ws=pg.get_text("words")
            if not ws: continue
            rows={}
            for w in ws:
                y=round(w[1]/ (pg.rect.height/220))
                rows.setdefault(y,[]).append(w)
            for y,r in rows.items():
                r.sort(key=lambda w:w[0]); t=" ".join(w[4] for w in r)
                if re.search(FEAT,t,re.I) and re.search(QUAL,t,re.I):
                    out.append((rel,i,t[:170]))
seen=set()
with open("qualifier_rows.txt","w") as fh:
    for rel,i,t in sorted(out):
        k=(rel.split("/brochures")[0],i,t)
        if k in seen: continue
        seen.add(k); fh.write(f"{rel.split('/latest')[0]}|p{i}|{t}\n")
print(len(seen))
