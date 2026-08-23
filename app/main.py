from pydantic import BaseModel, Field
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException, Response, status,Depends
import psycopg2
from psycopg2.extras import RealDictCursor
from . import  models, auth
import time
from .routers import post, profile, users, users2 
from .database import engine, get_db





models.Base.metadata.create_all(bind=engine)


# Create an instance of FastAPI
app = FastAPI(
    title="Wenyfour",
    description="Car Sharing App",
    version="1.0.0",
)

# origins =["*"]

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )


origins = [
    "https://wenyfour-neww.vercel.app",
    "https://wenyfour.com",
    "https://www.wenyfour.com",
    "https://wenyfour.com.ng",
    "https://www.wenyfour.com.ng",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8000",
    "http://13.247.98.20:8000",
    "https://app.wenyfour.com.ng",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# app.include_router(post.router)
app.include_router(users2.router)
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

