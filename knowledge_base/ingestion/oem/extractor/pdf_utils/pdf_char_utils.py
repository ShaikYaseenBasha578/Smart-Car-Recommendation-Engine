from collections import defaultdict
from typing import List, Dict, Any

def reconstruct_text_from_chars(chars: List[Dict[str, Any]], y_tolerance: float = 2.0, page_num: int = -1) -> Dict[str, Any]:
    """
    Generic utility to reconstruct text logically from page.chars.
    Handles negative coordinates gracefully by retaining relative spacing.
    Exposes blocks (spatially clustered words) to allow column reasoning.
    """
    if not chars:
        return {"raw_char_count": 0, "rows": [], "reconstructed_text": "", "status": "insufficient_evidence", "page": page_num}

    # Group by Y
    rows_dict = defaultdict(list)
    for c in chars:
        if not c.get('text', '').strip():
            continue
        y = round(c['top'] / y_tolerance) * y_tolerance
        rows_dict[y].append(c)

    reconstructed_rows = []
    full_text_lines = []
    ambiguous = False

    for y in sorted(rows_dict.keys()):
        row_chars = sorted(rows_dict[y], key=lambda x: x['x0'])
        if not row_chars: continue
        
        blocks = []
        current_block_chars = []
        
        last_x1 = None
        for c in row_chars:
            if last_x1 is not None:
                gap = c['x0'] - last_x1
                char_height = c['bottom'] - c['top']
                if gap < -char_height * 0.5:
                    ambiguous = True
                
                # If gap > 1.0 * char_height, treat it as a column separator / block boundary
                if gap > char_height * 1.5:
                    if current_block_chars:
                        blocks.append(current_block_chars)
                        current_block_chars = []
            
            current_block_chars.append(c)
            last_x1 = c['x1']
            
        if current_block_chars:
            blocks.append(current_block_chars)
            
        row_text = ""
        row_blocks = []
        for blk in blocks:
            blk_text = ""
            last_cx = None
            for c in blk:
                if last_cx is not None:
                    gap = c['x0'] - last_cx
                    char_h = c['bottom'] - c['top']
                    # normal space
                    if gap > char_h * 0.2:
                        blk_text += " "
                blk_text += c.get('text', '')
                last_cx = c['x1']
            
            row_blocks.append({
                "text": blk_text.strip(),
                "x_center": (blk[0]['x0'] + blk[-1]['x1']) / 2.0,
                "x_bounds": (blk[0]['x0'], blk[-1]['x1'])
            })
            row_text += blk_text.strip() + "    " # separate blocks in raw text with large space
            
        row_text = row_text.strip()
        
        reconstructed_rows.append({
            "y": y,
            "text": row_text,
            "blocks": row_blocks,
            "x_bounds": (row_chars[0]['x0'], row_chars[-1]['x1']),
            "char_count": len(row_chars)
        })
        full_text_lines.append(row_text)

    status = "ambiguous" if ambiguous else "reconstructed"

    return {
        "raw_char_count": len(chars),
        "rows": reconstructed_rows,
        "reconstructed_text": "\n".join(full_text_lines),
        "status": status,
        "page": page_num
    }
