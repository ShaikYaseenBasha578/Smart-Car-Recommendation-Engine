from typing import List, Dict, Any

def detect_vector_marks(page_objects: Dict[str, List[Dict]], cols_x: List[float], rows_y: List[float], page_num: int = -1, x_tol: float = 15.0, y_tol: float = 10.0) -> List[Dict]:
    """
    Generic spatial detector for native PDF graphics (curves, rects).
    """
    marks = []
    
    # Target only small objects that likely represent marks (deduplicate identical ones)
    candidates = []
    seen_centers = set()
    
    for curve in page_objects.get('curves', []):
        if curve['width'] < 15 and curve['height'] < 15:
            cx, cy = round((curve['x0'] + curve['x1'])/2, 1), round((curve['top'] + curve['bottom'])/2, 1)
            if (cx, cy) not in seen_centers:
                seen_centers.add((cx, cy))
                candidates.append({"type": "curve", "x": cx, "y": cy, "raw": curve})
            
    for rect in page_objects.get('rects', []):
        if rect['width'] < 15 and rect['height'] < 15:
            cx, cy = round((rect['x0'] + rect['x1'])/2, 1), round((rect['top'] + rect['bottom'])/2, 1)
            if (cx, cy) not in seen_centers:
                seen_centers.add((cx, cy))
                candidates.append({"type": "rect", "x": cx, "y": cy, "raw": rect})

    for r_idx, ry in enumerate(rows_y):
        for c_idx, cx in enumerate(cols_x):
            matched = [cand for cand in candidates if abs(cand['x'] - cx) < x_tol and abs(cand['y'] - ry) < y_tol]
            for cand in matched:
                marks.append({
                    "col_idx": c_idx,
                    "row_idx": r_idx,
                    "evidence_type": "vector",
                    "raw_evidence": cand['type'],
                    "geometry": {"x": cand['x'], "y": cand['y'], "bbox": (cand['raw']['x0'], cand['raw']['top'], cand['raw']['x1'], cand['raw']['bottom'])},
                    "semantic_state": None, # Semantic state must be established independently
                    "page": page_num
                })
                    
    return marks
