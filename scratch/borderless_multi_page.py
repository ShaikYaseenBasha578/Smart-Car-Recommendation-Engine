def _is_continuation_page(page_rows, parent_cols):
    cols = _find_configuration_columns(page_rows)
    if len(cols) != len(parent_cols):
        return False
        
    for cx, pcx in zip(cols, parent_cols):
        if abs(cx - pcx) > 25:
            return False
            
    # Check absence of new header
    # Check boolean density
    return True
