import re

with open("knowledge_base/ingestion/oem/extractor/families/borderless_variant_column_matrix.py", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "is_matrix = False" in line:
        new_lines.append("""
        # Structural Rejection: 
        # A valid feature matrix MUST have a solid density of boolean/mark indicators, or be a massive list of features with many columns.
        is_matrix = False
        if bool_cells >= len(cols) * 2: # Strong boolean presence
            is_matrix = True
        elif feature_rows_count >= 10 and bool_cells >= len(cols): # Many rows, some booleans
            is_matrix = True
        elif feature_rows_count >= 15 and len(cols) >= 3: # Massive matrix, even if no booleans recognized (e.g. text values)
            is_matrix = True
            
        # Reject dimension tables strongly
        dimension_vals = sum(1 for feat in extracted_features for v in feat['vals'] if v and any(x in str(v).lower() for x in ['mm', 'cc', 'rpm', 'kg', 'litres']))
        if dimension_vals > feature_rows_count:
            is_matrix = False
""")
    elif "if bool_cells >= (len(cols) / 2):" in line or "elif feature_rows_count >= 5 and bool_cells > 0:" in line or "is_matrix = True" in line:
        pass # Skip old lines
    else:
        new_lines.append(line)

with open("knowledge_base/ingestion/oem/extractor/families/borderless_variant_column_matrix.py", "w") as f:
    f.writelines(new_lines)
