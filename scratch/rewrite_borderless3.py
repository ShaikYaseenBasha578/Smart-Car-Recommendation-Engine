with open("knowledge_base/ingestion/oem/extractor/families/borderless_variant_column_matrix.py", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "is_matrix = False" in line:
        new_lines.append("""
        is_matrix = False
        
        # Calculate cell length density
        total_cells = 0
        total_chars = 0
        for feat in extracted_features:
            for v in feat['vals']:
                if v:
                    total_cells += 1
                    total_chars += len(str(v))
        avg_cell_len = (total_chars / total_cells) if total_cells > 0 else 0
        
        if avg_cell_len > 25:
            is_matrix = False
        elif bool_cells >= len(cols) * 2:
            is_matrix = True
        elif feature_rows_count >= 10 and bool_cells >= len(cols):
            is_matrix = True
        elif feature_rows_count >= 15 and len(cols) >= 3 and avg_cell_len < 15:
            is_matrix = True
""")
    elif "if bool_cells >= len(cols) * 2:" in line or "elif feature_rows_count >= 10 and bool_cells >= len(cols):" in line or "elif feature_rows_count >= 15 and len(cols) >= 3:" in line or "is_matrix = True" in line:
        pass
    else:
        new_lines.append(line)

with open("knowledge_base/ingestion/oem/extractor/families/borderless_variant_column_matrix.py", "w") as f:
    f.writelines(new_lines)
