# ==========================================================
# IMPORTS
# ==========================================================

# Optional allows a field to be optional (can be None)
# from typing import Optional
from pydantic import BaseModel, Field

# Import the FastAPI class used to create the application
from fastapi import FastAPI

# Import classes used for error handling and responses
from fastapi import HTTPException, Response, status,Depends

# BaseModel is used to create request body models
# Field is used to add validation rules

import psycopg2
from psycopg2.extras import RealDictCursor
from . import models
import time
# from sqlalchemy.orm import Session
# from sqlalchemy.exc import IntegrityError
# from . import models, schemas, utils 
# from .schemas import PostCreate, PostBase, PostResponse
# from . import schemas

from .routers import post, users

from .database import engine, get_db
models.Base.metadata.create_all(bind=engine)



# ==========================================================
# CREATE FASTAPI APPLICATION
# ==========================================================

# Create an instance of FastAPI
app = FastAPI(
    title="Wenyfour FastAPI App",
    description="Simple ORM CRUD API built with FastAPI",
    version="1.0.0",
)

app.include_router(post.router)
app.include_router(users.router)

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

# ==========================================================
# PYDANTIC MODELS
# ==========================================================

# Base model containing the common fields for a post.
# This model is reused for both creating and updating posts.
#imported from schemas.py
#imported Post from schemas.py

# ==========================================================
# HOME ROUTE
# ==========================================================

# GET /
#
# This is the root endpoint.
#
# Visiting:
#
# http://127.0.0.1:8000/
#
# returns the message below.

@app.get("/")
def root():

    return {
        "message": "Welcome to Wenyfour FastAPI App",
        "status": "success",
    }
