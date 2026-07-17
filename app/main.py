# ==========================================================
# IMPORTS
# ==========================================================

# Optional allows a field to be optional (can be None)
from typing import Optional
from pydantic import BaseModel, Field

# Import the FastAPI class used to create the application
from fastapi import FastAPI

# Import classes used for error handling and responses
from fastapi import HTTPException, Response, status,Depends

# BaseModel is used to create request body models
# Field is used to add validation rules

import psycopg2
from psycopg2.extras import RealDictCursor
import time
from sqlalchemy.orm import Session
from . import models, schemas
from .database import engine, get_db
from .schemas import PostCreate, PostBase, PostResponse
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
# ==========================================================
# CREATE POST
# ==========================================================

# POST /posts
#
# Used for creating a new post.

@app.post("/posts", status_code=status.HTTP_201_CREATED, response_model=schemas.PostResponse)
def create_posts(post: PostCreate, db:Session = Depends(get_db) ):
    # cursor.execute(
    #     """INSERT INTO posts (title, content, published) VALUES (%s, %s, %s) RETURNING *""",
    #     (post.title, post.content, post.published)
    # )
    new_post = models.Post(**post.model_dump())

    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return {
        "data": new_post,
        "message": "Post created successfully",
    }

# ==========================================================
# GET ALL POSTS
# ==========================================================
# ==========================================================
# GET ALL POSTS USING SQLALCHEMY ORM
# ==========================================================


# GET /posts
#
# Retrieves all posts from the database.
#
#
# Example:
#
# GET http://127.0.0.1:8000/posts
#
#
# Workflow:
#
# 1. FastAPI receives the GET request
#
# 2. SQLAlchemy opens a database session
#
# 3. SQLAlchemy queries the Post model
#
# 4. PostgreSQL returns all records
#
# 5. FastAPI sends the data back as JSON
#
#
# SQL equivalent:
#
# SELECT * FROM posts;


@app.get(
    "/posts",
    status_code=status.HTTP_200_OK
)

def get_all_posts(
    db: Session = Depends(get_db)
):


    # Query the posts table using SQLAlchemy ORM.
    #
    # models.Post represents the posts table.
    #
    # .all() returns all rows from the table.
    #
    #
    # SQL equivalent:
    #
    # SELECT *
    # FROM posts;


    posts = db.query(models.Post).all()



    # Return the database results.
    #
    # SQLAlchemy objects are automatically
    # converted by FastAPI when returned.


    return {

        "data": posts,

        "total": len(posts),

        "message": "Posts retrieved successfully"

    }
# ==========================================================
# GET SINGLE POST BY ID
# ==========================================================

# GET /posts/{id}
#
# Example:
#
# GET http://127.0.0.1:8000/posts/5
#
# FastAPI receives:
#
# id = 5
#
# Then SQLAlchemy searches the posts table
# for the record where id = 5.


@app.get("/posts/{id}")
def get_post(
    id: int,
    db: Session = Depends(get_db)
):

    # Query the database table using SQLAlchemy ORM.
    #
    # This is equivalent to SQL:
    #
    # SELECT *
    # FROM posts
    # WHERE id = id;


    post = db.query(models.Post).filter(
        models.Post.id == id
    ).first()



    # If no post is found,
    # return HTTP 404 error.

    if post is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with ID {id} not found"
        )



    return {
        "data": post,
        "message": "Post retrieved successfully"
    }

# ==========================================================
# UPDATE POST
# ==========================================================
# ==========================================================
# UPDATE POST USING SQLALCHEMY ORM
# ==========================================================


# PUT /posts/{id}
#
# Updates an existing post.
#
# Example:
#
# PUT /posts/1
#
# Request body:
#
# {
#     "title": "Updated Title",
#     "content": "Updated Content",
#     "published": true,
#     "rating": 5
# }


@app.put("/posts/{id}", response_model=schemas.PostResponse)
def update_post(
    id: int,
    post: PostCreate,
    db: Session = Depends(get_db)
):


    # Find existing database record

    updated_post = db.query(models.Post).filter(
        models.Post.id == id
    ).first()



    if updated_post is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with ID {id} not found"
        )



    # Update SQLAlchemy model fields

    updated_post.title = post.title

    updated_post.content = post.content

    updated_post.published = post.published

    updated_post.rating = post.rating



    # Save changes

    db.commit()



    # Reload SQLAlchemy object

    db.refresh(updated_post)



    return updated_post

# ==========================================================
# ==========================================================
# DELETE POST USING SQLALCHEMY ORM
# ==========================================================


# DELETE /posts/{id}
#
# Deletes an existing post from the database.
#
#
# Example:
#
# DELETE http://127.0.0.1:8000/posts/5
#
#
# FastAPI receives:
#
# id = 5
#
# SQLAlchemy searches PostgreSQL for the post
# where id = 5.
#
# If the post exists:
#
# 1. Remove it from the database session
#
# 2. Commit the change
#
# 3. Return success response
#
#
# SQL equivalent:
#
# DELETE FROM posts
# WHERE id = 5;


@app.delete(
    "/posts/{id}",
    status_code=status.HTTP_204_NO_CONTENT
)

def delete_post(
    id: int,
    db: Session = Depends(get_db)
):


    # Search for the post we want to delete.
    #
    # db.query(models.Post)
    #
    # tells SQLAlchemy:
    # "Look inside the posts table."
    #
    #
    # filter()
    #
    # works like SQL WHERE.
    #
    # Example:
    #
    # SELECT *
    # FROM posts
    # WHERE id = 5;


    post = db.query(models.Post).filter(
        models.Post.id == id
    ).first()



    # Check if the post exists.
    #
    # If SQLAlchemy returns None,
    # no record was found.


    if post is None:

        raise HTTPException(

            status_code=status.HTTP_404_NOT_FOUND,

            detail=f"Post with ID {id} not found"

        )



    # Mark the object for deletion.
    #
    # This does not immediately remove it.
    #
    # SQLAlchemy prepares the DELETE operation.


    db.delete(post)



    # Permanently apply the deletion
    # to PostgreSQL.
    #
    # Equivalent SQL:
    #
    # DELETE FROM posts
    # WHERE id = id;


    db.commit()



    # HTTP 204 means:
    #
    # The request was successful,
    # but there is no response data.
    #
    # Commonly used for DELETE operations.


    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )@app.get("/sqlalchemy")
def test_posts(db: Session = Depends(get_db)):
    
    return {"status": "success"}  