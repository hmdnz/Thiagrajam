from sqlalchemy import create_engine, text
from app.database import SQLALCHEMY_DATABASE_URL

engine = create_engine(SQLALCHEMY_DATABASE_URL)
tables = ['bookings', 'rides', 'ride_occurrences', 'car_photos', 'admins', 'admin_logs', 'ride_stopovers']

with engine.connect() as conn:
    for table in tables:
        query = text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'public' AND table_name = :t 
            ORDER BY ordinal_position
        """)
        columns = conn.execute(query, {'t': table}).mappings().fetchall()
        col_names = [c['column_name'] for c in columns]
        print(f"{table}: {col_names if col_names else '[TABLE DOES NOT EXIST]'}")