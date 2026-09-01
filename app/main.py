from pydantic import BaseModel, Field
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException, Response, status, Depends
import psycopg2
from psycopg2.extras import RealDictCursor
from . import models, auth
import time
import os
from .routers import post, profile, users, users2, driver, admin
from .database import engine, get_db, Base

from sqlalchemy.orm import Session

from app import auth
from app.routers import  profile, driver
from app.admin import routers as admin_router
from app.cars import routers as cars_router
from app.bookings import routers as bookings_router


# Creates any tables that don't already exist yet. Does NOT apply schema
# changes to existing tables (e.g. new columns) — those need Alembic.
models.Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Wenyfour",
    description="Car Sharing App",
    version="1.0.0",
)


from sqlalchemy import text

@app.on_event("startup")
def verify_db_connection():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            print("==========================================")
            print("🚀 Database connection successful!")
            print("==========================================")
    except Exception as error:
        print("==========================================")
        print("❌ Database connection failed!")
        print(f"Error details: {error}")
        print("==========================================")


# Explicit allow-list of frontends permitted to call this API with
# credentials. Using "*" would silently break allow_credentials=True.
origins = [
    "https://wenyfour-neww.vercel.app",
    "https://wenyfour.com",
    "https://www.wenyfour.com",
    "https://app.wenyfour.com",       
    "https://api.wenyfour.com",       
    "https://wenyfour.com.ng",
    "https://www.wenyfour.com.ng",
    "https://app.wenyfour.com.ng",
    "https://api.wenyfour.com.ng",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8000",
    "http://13.247.98.20:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serves uploaded selfies/licence photos at e.g. /static/uploads/selfies/<file>.
os.makedirs("static/uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# app.include_router(post.router)  # left disabled — not currently in use
app.include_router(users2.router)
app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(driver.router)
#  

# Modular domain routes
app.include_router(admin_router.router)
app.include_router(cars_router.router)
app.include_router(bookings_router.router)

@app.get("/health", tags=["System"])
def health_check(db: Session = Depends(get_db)):
    try:
        # Run a lightweight ping query
        db.execute(text("SELECT 1"))
        return {
            "status": "online",
            "database": "connected",
            "message": "FastAPI engine and PostgreSQL database are healthy"
        }
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "degraded",
                "database": "disconnected",
                "error": str(error)
            }
        )