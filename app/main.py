from pydantic import BaseModel, Field
from fastapi import FastAPI
from fastapi import HTTPException, Response, status,Depends
import psycopg2
from psycopg2.extras import RealDictCursor
from . import  models, auth
import time
from .routers import post, users, profile
from .database import engine, get_db





models.Base.metadata.create_all(bind=engine)


# Create an instance of FastAPI
app = FastAPI(
    title="Wenyfour FastAPI App",
    description="Simple ORM CRUD API built with FastAPI",
    version="1.0.0",
)

# app.include_router(post.router)
app.include_router(users.router)
app.include_router(auth.router) 
app.include_router(profile.router)

while True:

    try:
        conn = psycopg2.connect(host='localhost', database='fastapi', user='postgres', password='postgres', cursor_factory=RealDictCursor)
        cursor = conn.cursor()
        print ("Database connection was successful!")
        break
    except Exception as error:
        print ("Database connection failed!")
        print ("Error: ", error) 
        time.sleep(5)  # Wait for 5 seconds before retrying

