from dotenv import load_dotenv
load_dotenv()
from sqlalchemy import text
from app.database import engine

with engine.connect() as c:
    print(c.execute(text(
        "select current_database(), current_schema(), inet_server_port()"
    )).fetchone())
    rows = c.execute(text(
        "select table_name from information_schema.tables "
        "where table_schema = 'public' order by 1"
    )).fetchall()
    print(len(rows), "tables:", [r[0] for r in rows])