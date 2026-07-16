# ==========================================================
# IMPORTS
# ==========================================================

# Optional allows a field to be optional (can be None)
from typing import Optional

# Import the FastAPI class used to create the application
from fastapi import FastAPI

# Import classes used for error handling and responses
from fastapi import HTTPException, Response, status

# BaseModel is used to create request body models
# Field is used to add validation rules
from pydantic import BaseModel, Field
import psycopg2
from psycopg2.extras import RealDictCursor
import time



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


# # Model used when creating a post
# class PostCreate(PostBase):
#     pass


# # Model used when updating a post
# class PostUpdate(PostBase):
#     pass


# # Model that represents a complete post including its ID
# class PostResponse(PostBase):
#     id: int



# ==========================================================
# TEMPORARY DATABASE
# ==========================================================

# This list acts like our database.
# Later you'll replace this with PostgreSQL.

my_posts = [
    {
        "id": 1,
        "title": "Post 1",
        "content": "Content of post 1",
        "published": True,
        "rating": 5,
    },
    {
        "id": 2,
        "title": "Post 2",
        "content": "Content of post 2",
        "published": True,
        "rating": 4,
    },
]


# ==========================================================
# HELPER FUNCTIONS
# ==========================================================

# Instead of writing the same code repeatedly,
# we create helper functions. 


def find_post(post_id: int):
    """
    Search for a post by its ID.

    Returns:
        The post if found.
        None if not found.
    """

    return next(
        (post for post in my_posts if post["id"] == post_id),
        None,
    )


def find_post_index(post_id: int):
    """
    Find the index(position) of a post.

    Example:

    my_posts

    [
        {"id":1},
        {"id":2},
        {"id":3}
    ]

    find_post_index(2)

    returns 1
    """

    return next(
        (
            index
            for index, post in enumerate(my_posts)
            if post["id"] == post_id
        ),
        None,
    )


def generate_post_id():
    """
    Generate the next available ID.

    Example:

    Existing IDs

    1
    2
    3

    Next ID becomes

    4
    """

    if not my_posts:
        return 1

    return max(post["id"] for post in my_posts) + 1


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
def create_posts(post: Post):
    cursor.execute(
        """INSERT INTO posts (title, content, published) VALUES (%s, %s, %s) RETURNING *""",
        (post.title, post.content, post.published)
    )
    new_post =cursor.fetchone
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


@app.put("/posts/{post_id}")
def update_post(post_id: int, updated_post: Post):

    # Find where the post is located
    post_index = find_post_index(post_id)

    # If not found, return 404
    if post_index is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with ID {post_id} not found",
        )

    # Convert request body into a dictionary
    updated_post_dict = updated_post.model_dump()

    # Preserve the original ID
    updated_post_dict["id"] = post_id

    # Replace the old post with the updated one
    my_posts[post_index] = updated_post_dict

    return {
        "data": updated_post_dict,
        "message": "Post updated successfully",
    }


# ==========================================================
# DELETE POST
# ==========================================================

# DELETE /posts/{post_id}
#
# Deletes a post from our database.


@app.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(post_id: int):

    # Find the post index
    post_index = find_post_index(post_id)

    # Return 404 if the post doesn't exist
    if post_index is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with ID {post_id} not found",
        )

    # Remove the post
    my_posts.pop(post_index)

    # 204 means "Success but nothing to return"
    return Response(status_code=status.HTTP_204_NO_CONTENT)