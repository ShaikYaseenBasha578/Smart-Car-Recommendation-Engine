import pdfplumber
import json
import re

pdf_path = "knowledge_base/sources/oem/maruti_suzuki/swift/gen4_2024/brochures/Maruti_Suzuki_Swift_Gen4_2024_Official_Brochure.pdf"

payloads = []

# Base column map for features
# Col 1: LXi 5MT
# Col 2: VXi 5MT/5AMT, VXi CNG 5MT
# Col 3: VXi (O) 5MT/5AMT, VXi (O) CNG 5MT
# Col 4: ZXi 5MT/5AMT, ZXi CNG 5MT
# Col 5: ZXi+ 5MT/5AMT

def expand_variants(header_str):
    if not header_str: return []
    # e.g., "VXi 5MT/5AMT VXi CNG 5MT"
    # split by spaces, but group properly. We know the variants:
    v_list = []
    # Just manual mapping based on the known column headers to ensure zero errors in column expansion:
    if "LXi 5MT" in header_str:
        v_list.append({"raw_variant_name": "LXi", "transmission": "MT", "powertrain_type": "Petrol"})
    elif "VXi 5MT/5AMT" in header_str:
        v_list.append({"raw_variant_name": "VXi", "transmission": "MT", "powertrain_type": "Petrol"})
        v_list.append({"raw_variant_name": "VXi AMT", "transmission": "AMT", "powertrain_type": "Petrol"})
        if "CNG" in header_str:
            v_list.append({"raw_variant_name": "VXi CNG", "transmission": "MT", "powertrain_type": "CNG"})
    elif "VXi (O)" in header_str:
        v_list.append({"raw_variant_name": "VXi (O)", "transmission": "MT", "powertrain_type": "Petrol"})
        v_list.append({"raw_variant_name": "VXi (O) AMT", "transmission": "AMT", "powertrain_type": "Petrol"})
        if "CNG" in header_str:
            v_list.append({"raw_variant_name": "VXi (O) CNG", "transmission": "MT", "powertrain_type": "CNG"})
    elif "ZXi 5MT/5AMT" in header_str:
        v_list.append({"raw_variant_name": "ZXi", "transmission": "MT", "powertrain_type": "Petrol"})
        v_list.append({"raw_variant_name": "ZXi AMT", "transmission": "AMT", "powertrain_type": "Petrol"})
        if "CNG" in header_str:
            v_list.append({"raw_variant_name": "ZXi CNG", "transmission": "MT", "powertrain_type": "CNG"})
    elif "ZXi+" in header_str:
        v_list.append({"raw_variant_name": "ZXi+", "transmission": "MT", "powertrain_type": "Petrol"})
        v_list.append({"raw_variant_name": "ZXi+ AMT", "transmission": "AMT", "powertrain_type": "Petrol"})
    return v_list

with pdfplumber.open(pdf_path) as pdf:
    # Page 6 (0-indexed is page 5)
    page = pdf.pages[5]
    tables = page.extract_tables()
    
    # We will build a template for each generated variant
    variant_templates = []
    
    # The first table is Technical Specifications
    tech_table = tables[0]
    
    # We know petrol and cng columns:
    # row 0: ['TECHNICAL SPECIFICATIONS', 'PETROL', 'CNG']
    # If the layout has merged cells, pdfplumber might give None or empty strings for merged portions.
    
    # Second table is Features List
    feat_table = tables[1]
    headers = feat_table[1] # row 0 is 'FEATURES LIST', row 1 is variants
    
    # Col 1 is Feature Name, Col 2-6 are the variants
    col_variant_maps = {}
    for i in range(1, 6):
        if i < len(headers) and headers[i]:
            col_variant_maps[i] = expand_variants(headers[i].replace('\n', ' '))
            
    # Parse Features
    parsed_features = {i: {} for i in range(1, 6)}
    for row in feat_table[2:]:
        if len(row) < 6: continue
        feature = row[0]
        if not feature or feature.strip() == '': continue
        feature = feature.replace('\n', ' ').strip()
        for i in range(1, 6):
            val = row[i]
            if val:
                val = val.replace('\n', ' ').strip()
                # Parse checkmark and dash
                if val == '-':
                    parsed_features[i][feature] = None # dash means absent but we preserve as None to be safe or False? The prompt says "Explicit OEM False/dash semantics may become canonical False only when the table establishes that meaning." Since dash in this matrix means "not available on this trim", we can map it to False or None. We'll extract raw '-' and let normalizer handle it!
                elif '\uf0fc' in val or '✓' in val:
                    # PDF symbol for checkmark
                    parsed_features[i][feature] = 'Standard'
                else:
                    parsed_features[i][feature] = val
                    
    # Parse Technical
    petrol_specs = {}
    cng_specs = {}
    for row in tech_table:
        if len(row) < 2: continue
        key = row[0]
        if not key: continue
        key = key.replace('\n', ' ').strip()
        
        val_petrol = row[1] if row[1] else ""
        val_cng = row[2] if len(row) > 2 and row[2] else val_petrol
        val_petrol = val_petrol.replace('\n', ' ').strip()
        val_cng = val_cng.replace('\n', ' ').strip()
        
        petrol_specs[key] = val_petrol
        cng_specs[key] = val_cng

    # Assemble payloads
    for col_idx, variant_dicts in col_variant_maps.items():
        for v in variant_dicts:
            p = v.copy()
            pt_type = v['powertrain_type']
            specs = petrol_specs if pt_type == 'Petrol' else cng_specs
            
            # Merge specs
            for k, val in specs.items():
                p[k] = val
            
            # Merge features
            for k, val in parsed_features[col_idx].items():
                # Handle conditional MT/AMT
                if val and '(AMT only)' in val:
                    if p['transmission'] != 'AMT':
                        val = '-'
                    else:
                        val = val.replace('(AMT only)', '').strip()
                elif val and '(MT only)' in val:
                    if p['transmission'] != 'MT':
                        val = '-'
                    else:
                        val = val.replace('(MT only)', '').strip()
                elif val and 'CNG Only' in val:
                    if pt_type != 'CNG':
                        val = '-'
                    else:
                        val = val.replace('CNG Only', '').strip()
                
                # Replace symbol if it's checkmark
                if val and ('✓' in val or '\uf0fc' in val):
                    val = val.replace('✓', '').replace('\uf0fc', '').strip()
                    val = 'Standard ' + val if val else 'Standard'
                
                p[k] = val
                
            payloads.append(p)
            
with open("scratch/swift_dry_run_extracted.json", "w") as f:
    json.dump(payloads, f, indent=2)
print(f"Extracted {len(payloads)} variants.")
