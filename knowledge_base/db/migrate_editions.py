import os as _kb_os, sys as _kb_sys
_kb_sys.path.insert(0, _kb_os.path.abspath(_kb_os.path.join(_kb_os.path.dirname(_kb_os.path.abspath(__file__)), "..", "..")))  # repo root
from knowledge_base.kb_db import KB_PATH, open_kb
import sqlite3

def migrate():
    conn = open_kb(KB_PATH)
    c = conn.cursor()
    
    try:
        c.execute("ALTER TABLE variant ADD COLUMN base_variant_id INTEGER REFERENCES variant(id)")
        c.execute("ALTER TABLE variant ADD COLUMN edition_classification TEXT")
        print("Added edition columns to variant table.")
    except sqlite3.OperationalError as e:
        print("Migration may have already run or failed:", e)
        
    # Create view for effective variants
    # We will get all column names from variant table to construct the COALESCE query dynamically
    c.execute("PRAGMA table_info(variant)")
    columns = [row[1] for row in c.fetchall()]
    
    view_cols = []
    for col in columns:
        if col in ('id', 'model_id', 'generation_id', 'powertrain_id', 'name', 'full_name', 'transmission', 'drivetrain', 'is_discontinued', 'base_variant_id', 'edition_classification', 'created_at', 'updated_at', 'v6_row_index'):
            view_cols.append(f"v.{col}")
        else:
            view_cols.append(f"COALESCE(v.{col}, bv.{col}) AS {col}")
            
    view_sql = f"""
    CREATE VIEW IF NOT EXISTS v_effective_variant AS
    SELECT
        {', '.join(view_cols)}
    FROM variant v
    LEFT JOIN variant bv ON v.base_variant_id = bv.id
    """
    c.execute("DROP VIEW IF EXISTS v_effective_variant")
    c.execute(view_sql)
    print("Created v_effective_variant view.")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrate()
