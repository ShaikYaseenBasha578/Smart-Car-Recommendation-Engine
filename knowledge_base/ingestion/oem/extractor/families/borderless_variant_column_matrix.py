import pdfplumber
from typing import List, Dict, Any, Optional
from knowledge_base.ingestion.oem.extractor.base import OEMBrochureLayoutStrategy, ConfigurationIR, ExtractedField
from knowledge_base.ingestion.oem.extractor.pdf_utils.pdf_char_utils import reconstruct_text_from_chars
from knowledge_base.ingestion.oem.extractor.pdf_utils.pdf_vector_utils import detect_vector_marks

class BorderlessVariantColumnMatrixStrategy(OEMBrochureLayoutStrategy):
    def _extract_page_matrix(self, page, page_num: int) -> Optional[dict]:
        chars = page.chars
        if not chars: return None
        page_width = float(page.width)
        
        reconstruction = reconstruct_text_from_chars(chars, page_num=page_num)
        if reconstruction['status'] == 'insufficient_evidence' or not reconstruction['rows']: return None
        rows_data = reconstruction['rows']
        
        # Discover feature rows by looking for text on the far left
        feature_rows_y = []
        row_objects = []
        for r in rows_data:
            blocks = r.get('blocks', [])
            if not blocks: continue
            if blocks[0]['x_bounds'][0] < page_width * 0.15:
                feature_rows_y.append(r['y'])
                row_objects.append(r)
                
        # Discover vector marks
        # We don't know columns yet, so we just pass all possible X values or a generic grid
        # Wait, detect_vector_marks requires col_centers.
        # We can find col_centers by clustering text boolean symbols first, AND clustering all vector X centers.
        
        bool_x_centers = []
        strict_symbols = {'S', '●', '✓', '—', '-', '', '[393]', 'Y', 'N', '✔', '√', 'Opt', 'Standard'}
        for r in row_objects:
            for b in r.get('blocks', []):
                if b['text'].strip() in strict_symbols:
                    bool_x_centers.append(b['x_center'])
                    
        # Add vector X centers
        for v in page.curves + page.rects:
            if v['width'] < 20 and v['height'] < 20:
                cx = (v['x0'] + v['x1']) / 2.0
                if cx > page_width * 0.15: # Not in the feature label area
                    bool_x_centers.append(cx)
                    
        if not bool_x_centers: return None
        
        # Cluster X centers to find columns
        bool_x_centers.sort()
        cols_x = []
        current_cluster = [bool_x_centers[0]]
        x_tolerance = page_width * 0.04
        
        for x in bool_x_centers[1:]:
            if x - current_cluster[-1] < x_tolerance:
                current_cluster.append(x)
            else:
                if len(current_cluster) >= 3: # Must have at least a few marks to be a column
                    cols_x.append(sum(current_cluster)/len(current_cluster))
                current_cluster = [x]
        if len(current_cluster) >= 3:
            cols_x.append(sum(current_cluster)/len(current_cluster))
            
        if len(cols_x) < 2: return None
        
        # Now we know columns, let's find headers above these columns
        headers = [""] * len(cols_x)
        # Scan top rows (y < first feature row y, or top 30% of page)
        header_y_limit = feature_rows_y[0] if feature_rows_y else page_width * 0.5
        for r in rows_data:
            if r['y'] > header_y_limit + 50: continue # +50 margin
            for b in r.get('blocks', []):
                # find closest column
                closest_c_idx = min(range(len(cols_x)), key=lambda i: abs(cols_x[i] - b['x_center']))
                if abs(cols_x[closest_c_idx] - b['x_center']) < x_tolerance:
                    headers[closest_c_idx] += " " + b['text'].strip()
        headers = [h.strip() for h in headers]
        
        # Detect vectors accurately now that we have column centers
        vector_marks = detect_vector_marks({'curves': page.curves, 'rects': page.rects}, cols_x, feature_rows_y, page_num=page_num)
        
        extracted_features = []
        bool_cells = 0
        feature_rows_count = 0
        
        for idx, (y, r_obj) in enumerate(zip(feature_rows_y, row_objects)):
            blocks = r_obj.get('blocks', [])
            left_blocks = [b for b in blocks if b['x_center'] < cols_x[0] - x_tolerance]
            if not left_blocks: continue
            name = " ".join([b['text'] for b in left_blocks])
            if len(name) < 3: continue
            
            # Reject technical specs
            tech_kw = ['length', 'width', 'height', 'wheelbase', 'capacity', 'mm', 'cc', 'rpm']
            if any(k in name.lower() for k in tech_kw) and len(name.split()) < 4: continue
            
            row_vals = [None] * len(cols_x)
            for b in blocks:
                if b['x_center'] < cols_x[0] - x_tolerance: continue
                closest_c_idx = min(range(len(cols_x)), key=lambda i: abs(cols_x[i] - b['x_center']))
                if abs(cols_x[closest_c_idx] - b['x_center']) < x_tolerance:
                    val = b['text'].strip()
                    if row_vals[closest_c_idx]: row_vals[closest_c_idx] += " " + val
                    else: row_vals[closest_c_idx] = val
            
            for m in vector_marks:
                if m['row_idx'] == idx:
                    c_idx = m['col_idx']
                    row_vals[c_idx] = f"[{m['evidence_type']}:{m['raw_evidence']}]"
                    
            extracted_features.append({"name": name, "vals": row_vals})
            feature_rows_count += 1
            for v in row_vals:
                if v and (v in strict_symbols or 'vector' in v):
                    bool_cells += 1
                    
        is_matrix = False
        total_cells, total_chars = 0, 0
        for feat in extracted_features:
            for v in feat['vals']:
                if v:
                    total_cells += 1
                    total_chars += len(str(v))
        avg_cell_len = (total_chars / total_cells) if total_cells > 0 else 0
        
        if avg_cell_len > 25: is_matrix = False
        elif bool_cells >= len(cols_x) * 2: is_matrix = True
        elif feature_rows_count >= 10 and bool_cells >= len(cols_x): is_matrix = True
        elif feature_rows_count >= 15 and len(cols_x) >= 3 and avg_cell_len < 15: is_matrix = True
            
        if not is_matrix: return None
        
        # Valid headers must exist
        valid_headers = sum(1 for h in headers if len(h) > 2)
        if valid_headers == 0: return None
        
        return {
            "score": (len(cols_x) * 10) + feature_rows_count + (bool_cells * 2),
            "page_num": page_num,
            "cols": [{"center": c} for c in cols_x],
            "headers": headers,
            "features": extracted_features,
            "page_width": page_width
        }

    def _discover_structure(self, pdf) -> List[dict]:
        valid_pages = []
        for i, page in enumerate(pdf.pages):
            matrix = self._extract_page_matrix(page, i)
            if matrix: valid_pages.append(matrix)
        if not valid_pages: return []
        
        clusters = []
        for vp in valid_pages:
            added = False
            for c in clusters:
                parent = c[0]
                if len(parent['cols']) == len(vp['cols']):
                    page_width = parent['page_width']
                    diffs = [abs(parent['cols'][j]['center'] - vp['cols'][j]['center']) for j in range(len(parent['cols']))]
                    if max(diffs) < (page_width * 0.05):
                        c.append(vp)
                        added = True
                        break
            if not added: clusters.append([vp])
        clusters.sort(key=lambda c: sum(p['score'] for p in c), reverse=True)
        return clusters[0]

    def extract(self, pdf_path: str) -> List[ConfigurationIR]:
        with pdfplumber.open(pdf_path) as pdf:
            pages = self._discover_structure(pdf)
            if not pages: raise ValueError("Could not structurally locate borderless feature matrix")
            
            headers = pages[0]['headers']
            configs = []
            for h in headers:
                h_lower = h.lower()
                pt_type = "Diesel" if "diesel" in h_lower else "CNG" if "cng" in h_lower else "Electric" if "ev" in h_lower or "electric" in h_lower else "Petrol" if "petrol" in h_lower else None
                trans = "AMT" if "amt" in h_lower else "AT" if "at" in h_lower or "auto" in h_lower else "MT" if "mt" in h_lower or "manual" in h_lower else None
                configs.append(ConfigurationIR(raw_variant_name=h.strip() if h.strip() else "Unknown", powertrain_type=pt_type, transmission=trans, engine_name=None, fields=[]))
                
            for page_data in pages:
                for feat in page_data['features']:
                    name = feat['name']
                    for c_idx, val in enumerate(feat['vals']):
                        if not val: continue
                        configs[c_idx].fields.append(ExtractedField(field_name=name, raw_value=val, source_page=page_data['page_num'], section="Key features"))
        return configs
