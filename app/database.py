from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from app.config import settings

# SQLALCHEMY_DATABASE_URL = "postgresql://postgres:postgres@localhost/fastapi"
# SQLALCHEMY_DATABASE_URL =(
#     f"postgresql://{settings.DATABASE_USERNAME}:"
#     f"{settings.DATABASE_PASSWORD}@"
#     f"{settings.DATABASE_HOSTNAME}:"
#     f"{settings.DATABASE_PORT}/"
#     f"{settings.DATABASE_NAME}"
# )

SQLALCHEMY_DATABASE_URL = f"postgresql://{settings.DATABASE_USERNAME}:{settings.DATABASE_PASSWORD}@{settings.DATABASE_HOSTNAME}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}"

engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
