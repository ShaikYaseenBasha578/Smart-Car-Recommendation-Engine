import re
import json

def decode_rsc_chunk(chunk):
    try:
        return chunk.encode().decode('unicode_escape')
    except UnicodeDecodeError:
        return chunk.replace('\\"', '"').replace('\\n', '\n')

def extract_rsc_payloads(html_text):
    if not html_text: return []
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html_text, re.DOTALL)
    return [decode_rsc_chunk(c) for c in chunks]

def extract_json_block(text, start_idx, open_char='{', close_char='}'):
    depth = 0
    in_string = False
    escape = False
    for i in range(start_idx, len(text)):
        c = text[i]
        if escape:
            escape = False
            continue
        if c == '\\':
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if not in_string:
            if c == open_char:
                depth += 1
            elif c == close_char:
                depth -= 1
                if depth == 0:
                    return text[start_idx:i+1]
    return None

def extract_all(html_text):
    payloads = extract_rsc_payloads(html_text)
    if not payloads:
        return {'status': 'NO_PAYLOAD', 'variants': [], 'v_specs_blocks': []}
        
    vlist = []
    blocks = []
    container_found = False
    malformed = False
    
    # 1. variantList
    for p in payloads:
        m = re.search(r'"variantList"\s*:\s*\[', p)
        if m:
            container_found = True
            block = extract_json_block(p, m.end() - 1, '[', ']')
            if block:
                try:
                    parsed = json.loads(block)
                    if parsed: vlist.extend(parsed)
                except json.JSONDecodeError:
                    malformed = True
                    
    # 2. variants
    for p in payloads:
        for m in re.finditer(r'"variants"\s*:\s*\[', p):
            container_found = True
            block = extract_json_block(p, m.end() - 1, '[', ']')
            if block:
                try:
                    parsed = json.loads(block)
                    if parsed and isinstance(parsed, list) and len(parsed)>0 and isinstance(parsed[0], dict) and 'v_variant_id' in parsed[0]:
                        vlist.extend(parsed)
                except json.JSONDecodeError:
                    malformed = True
                    
    # 3. variantSpecsData
    for p in payloads:
        for m in re.finditer(r'"variantSpecsData"\s*:\s*\[', p):
            container_found = True
            block = extract_json_block(p, m.end() - 1, '[', ']')
            if block:
                try:
                    parsed = json.loads(block)
                    if parsed and isinstance(parsed, list):
                        for item in parsed:
                            if isinstance(item, dict) and 'data' in item:
                                vlist.append(item['data'])
                except json.JSONDecodeError:
                    malformed = True

    # Extract v_specs
    for p in payloads:
        for m in re.finditer(r'"v_specs"\s*:\s*\{', p):
            block = extract_json_block(p, m.end() - 1, '{', '}')
            if block:
                try:
                    parsed = json.loads(block)
                    total_fields = sum(len(v) for v in parsed.values() if isinstance(v, dict))
                    if total_fields >= 20:
                        ctx_start = max(0, m.start() - 2000)
                        ctx = p[ctx_start:m.start()]
                        vid_m = re.search(r'"v_variant_id"\s*:\s*(\d+)', ctx)
                        vid = int(vid_m.group(1)) if vid_m else None
                        blocks.append({'v_variant_id': vid, 'v_specs': parsed})
                except json.JSONDecodeError:
                    pass

    unique_vlist = {}
    for v in vlist:
        vid = v.get('v_variant_id')
        if not vid: continue
        if vid not in unique_vlist or ('specs' in v and 'specs' not in unique_vlist[vid]):
            unique_vlist[vid] = v
            
    final_vlist = list(unique_vlist.values())
    
    status = 'SUCCESS_COMPLETE'
    if not container_found:
        status = 'NO_CONTAINER'
    elif malformed and not final_vlist:
        status = 'MALFORMED_CONTAINER'
    elif len(final_vlist) == 0:
        status = 'ZERO_VARIANTS'
    elif len(final_vlist) <= 5 and not any('variantList' in p for p in payloads):
        status = 'SUCCESS_PARTIAL'
        
    return {
        'status': status,
        'variants': final_vlist,
        'v_specs_blocks': blocks
    }
