# ==========================================================
# IMPORTS
# ==========================================================

# Optional allows a field to be optional (can be None)
from typing import Optional

# Import the FastAPI class used to create the application
from fastapi import FastAPI

# Import classes used for error handling and responses
from fastapi import HTTPException, Response, status,Depends

# BaseModel is used to create request body models
# Field is used to add validation rules
from pydantic import BaseModel, Field
import psycopg2
from psycopg2.extras import RealDictCursor
import time
from sqlalchemy.orm import Session
from . import models
from .database import engine, get_db

models.Base.metadata.create_all(bind=engine)

# ==========================================================
# CREATE FASTAPI APPLICATION
# ==========================================================

# Create an instance of FastAPI
app = FastAPI(
    title="Wenyfour FastAPI App",
    description="Simple CRUD API built with FastAPI",
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
class Post(BaseModel):

    # Title cannot be empty
    title: str = Field(..., min_length=1, max_length=200)

    # Content cannot be empty
    content: str = Field(..., min_length=1)

    # Default value is True if the client doesn't provide one
    published: bool = True

    # Rating is optional and must be between 0 and 5
    rating: Optional[int] = Field(default=None, ge=0, le=5)

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

@app.post("/posts", status_code=status.HTTP_201_CREATED)
def create_posts(post: Post, db:Session = Depends(get_db) ):
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

# GET /posts
#
# Returns every post in our database.

@app.get("/posts", status_code=status.HTTP_200_OK)
def get_all_posts():
    cursor.execute("""SELECT * FROM posts""")
    posts = cursor.fetchall()
    print(posts)
    return {
        "data": posts}

# ==========================================================
# GET SINGLE POST
# ==========================================================

# GET /posts/{post_id}
#
# Example:
#
# /posts/3
#
# FastAPI automatically converts
# post_id into an integer.


@app.get("/posts/{id}")
def get_post(id: int):

    cursor.execute(
        """SELECT * FROM posts WHERE id = %s""",
        (id,)
    )

    post = cursor.fetchone()

    print(post)

    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with ID {id} not found",
        )

    return {
        "data": post,
        "message": "Post retrieved successfully",
    }

# ==========================================================
# UPDATE POST
# ==========================================================

# PUT /posts/{post_id}
#
# Updates the entire post.

@app.put("/posts/{id}")
def update_post(id: int, post: Post):

    cursor.execute(
        """
        UPDATE posts
        SET title = %s,
            content = %s,
            published = %s
        WHERE id = %s
        RETURNING *
        """,
        (
            post.title,
            post.content,
            post.published,
            id
        )
    )

    updated_post = cursor.fetchone()

    if updated_post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with ID {id} not found",
        )
    conn.commit()

    return {
        "data": updated_post,
        "message": "Post updated successfully",
    }

# ==========================================================
# DELETE POST
# ==========================================================

# DELETE /posts/{post_id}
#
# Deletes a post from our database.

@app.delete("/posts/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(id: int):

    cursor.execute(
        """
        DELETE FROM posts
        WHERE id = %s
        RETURNING *
        """,
        (id,)
    )

    deleted_post = cursor.fetchone()

    if deleted_post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with ID {id} not found",
        )

    conn.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)

@app.get("/sqlalchemy")
def test_posts(db: Session = Depends(get_db)):
    
    return {"status": "success"}  