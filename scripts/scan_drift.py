"""
scripts/scan_drift.py
Run: python scripts\scan_drift.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect
from app.database import engine
from app import models
from app.cars import models as cm
from app.rides import models as rm
from app.bookings import models as bm
from app.payments import models as pm

inspector = inspect(engine)
existing_tables = set(inspector.get_table_names())

issues_found = False

for base in (models, cm, rm, bm, pm):
    for name, cls in vars(base).items():
        if not hasattr(cls, "__tablename__"):
            continue
        table = cls.__tablename__
        if table not in existing_tables:
            print(f"[MISSING TABLE] {table}")
            issues_found = True
            continue

        db_cols = {c["name"] for c in inspector.get_columns(table)}
        model_cols = {c.name for c in cls.__table__.columns}

        missing_in_db = model_cols - db_cols
        extra_in_db = db_cols - model_cols

        if missing_in_db:
            print(f"[{table}] missing in DB: {sorted(missing_in_db)}")
            issues_found = True
        if extra_in_db:
            print(f"[{table}] extra in DB  : {sorted(extra_in_db)}")

if not issues_found:
    print("No schema drift detected.")