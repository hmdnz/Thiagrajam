# TO RUN THE FILE DO:
# python check_schema.py

import sys
from sqlalchemy import inspect
from app.database import engine  # Adjust import if your engine is named/located differently
from app.rides.models import Base  # Import your SQLAlchemy Base where models are registered

def inspect_db_mismatches():
    inspector = inspect(engine)
    db_tables = inspector.get_table_names()
    
    missing_report = {}
    
    # Iterate over all registered SQLAlchemy models
    for mapper in Base.registry.mappers:
        model_cls = mapper.class_
        table_name = model_cls.__tablename__
        
        if table_name not in db_tables:
            missing_report[table_name] = "TABLE ENTIRELY MISSING IN DB"
            continue
            
        # Get actual DB columns
        db_columns = {col['name'] for col in inspector.get_columns(table_name)}
        
        # Get model defined columns
        model_columns = {col.key for col in mapper.columns}
        
        # Find missing columns
        missing_cols = model_columns - db_columns
        if missing_cols:
            missing_report[table_name] = list(missing_cols)

    print("\n================ SCHEMA MISMATCH REPORT ================")
    if not missing_report:
        print("✅ Success! All model columns match the database tables.")
    else:
        for table, missing in missing_report.items():
            print(f"\nTable: '{table}'")
            if isinstance(missing, list):
                print(f"  Missing Columns: {', '.join(missing)}")
                # Print ready-to-use ALTER TABLE statements
                for col in missing:
                    print(f"  -> SQL: ALTER TABLE {table} ADD COLUMN IF NOT EXISTS \"{col}\" VARCHAR;")
            else:
                print(f"  Status: {missing}")
    print("========================================================\n")

if __name__ == "__main__":
    inspect_db_mismatches()