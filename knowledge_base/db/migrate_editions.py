import sqlite3

def migrate():
    conn = sqlite3.connect('knowledge_base/carrec_kb.db')
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
