import re

def decode_wagonr_cid(match):
    val = int(match.group(1))
    # It seems to be a mixed mapping. Let's just create a small map based on typical ASCII layout.
    # Actually, we can just use a dict if we know a few, but let's see if there is a pattern.
    # A=35 (65). Z=60 (90). Offset = +30.
    # a=67 (97). z=92 (122). Offset = +30.
    # Space is maybe cid:3?
    if 35 <= val <= 92: return chr(val + 30)
    if val == 3: return ' '
    if val == 8: return '&'
    if val == 15: return '-'
    if val == 13: return '('
    if val == 17: return ')'
    if val == 16: return '.'
    if val == 18: return '0'
    if val == 19: return '1'
    if val == 20: return '2'
    if val == 22: return '4'
    if val == 24: return '6'
    if val == 28: return '8'
    return f"[{val}]"

with open("scratch/wagonr_text.json") as f:
    import json
    data = json.load(f)
    text = data["4"]
    
    decoded = re.sub(r'\(cid:(\d+)\)', decode_wagonr_cid, text)
    print(decoded[:2000])
