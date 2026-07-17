# ==========================================================
# IMPORTS
# ==========================================================


# Optional allows us to create fields that can accept None values.
# Example:
# rating can be 5 or it can be empty (None)
from typing import Optional


# FastAPI is the main class used to create our API application.
# It provides the tools needed to create routes/endpoints.
from fastapi import FastAPI


# HTTPException is used when we want to return errors.
# Example:
# Returning "Post not found" with status code 404
#
# Response allows us to return custom responses.
#
# status contains HTTP status code numbers:
# 200 = Success
# 201 = Created
# 404 = Not Found
from fastapi import HTTPException, Response, status


# BaseModel is used by Pydantic to create data models.
#
# FastAPI uses Pydantic models to:
# - validate incoming data
# - define request structure
# - convert JSON data into Python objects
from pydantic import BaseModel, Field


# psycopg2 is a PostgreSQL database adapter.
#
# It allows Python applications to communicate
# with PostgreSQL databases.
import psycopg2


# RealDictCursor makes database results return as dictionaries.
#
# Without it:
#
# (1, "Title", "Content", True)
#
# With it:
#
# {
#   "id":1,
#   "title":"Title",
#   "content":"Content",
#   "published":True
# }
from psycopg2.extras import RealDictCursor


# time allows us to pause execution.
#
# We use it when retrying database connections.
import time



# ==========================================================
# CREATE FASTAPI APPLICATION
# ==========================================================


# Creating an instance/object of FastAPI.
#
# This object represents our API application.
#
# All our routes:
#
# GET
# POST
# PUT
# DELETE
#
# will be attached to this app object.

app = FastAPI(

    # Name displayed in Swagger documentation
    title="Wenyfour FastAPI App",

    # Short explanation of the API
    description="Simple CRUD API built with FastAPI and PostgreSQL",

    # Application version
    version="1.0.0",
)



# ==========================================================
# DATABASE CONNECTION
# ==========================================================


# We create a connection between FastAPI and PostgreSQL.
#
# The application needs this connection so it can:
#
# - insert data
# - read data
# - update data
# - delete data
#
# Database details:
#
# Host:
# localhost means PostgreSQL is running on this computer
#
# Database:
# fastapi is the database we created in PostgreSQL
#
# User:
# postgres is the default PostgreSQL administrator user
#
# Password:
# The password created during PostgreSQL installation


while True:

    try:

        # Create connection to PostgreSQL database
        conn = psycopg2.connect(

            host="localhost",

            database="fastapi",

            user="postgres",

            password="postgres",

            # Return database rows as dictionaries
            cursor_factory=RealDictCursor
        )


        # Cursor is used to execute SQL commands.
        #
        # Example:
        #
        # SELECT * FROM posts
        #
        # INSERT INTO posts ...
        cursor = conn.cursor()


        print("Database connection was successful!")

        # Stop the while loop after successful connection
        break


    except Exception as error:


        # If connection fails, display the error
        print("Database connection failed!")

        print("Error:", error)


        # Wait 5 seconds before trying again
        #
        # This prevents the application from crashing
        # immediately if PostgreSQL is temporarily unavailable.
        time.sleep(5)



# ==========================================================
# PYDANTIC MODEL
# ==========================================================


# A Pydantic model defines the structure of data
# that our API accepts.
#
# When a user sends:
#
# POST /posts
#
# with JSON:
#
# {
#   "title":"Hello",
#   "content":"My content",
#   "published":true
# }
#
# FastAPI checks this model automatically.


class Post(BaseModel):


    # Title field
    #
    # str means the value must be text
    #
    # Field rules:
    #
    # min_length=1
    # prevents empty titles
    #
    # max_length=200
    # limits title size

    title: str = Field(
        ...,
        min_length=1,
        max_length=200
    )



    # Content field
    #
    # TEXT content cannot be empty

    content: str = Field(
        ...,
        min_length=1
    )



    # Published status
    #
    # If user does not provide this value,
    # FastAPI automatically uses True.

    published: bool = True



    # Optional rating field
    #
    # Optional means:
    #
    # rating can be:
    #
    # 5
    #
    # or
    #
    # None
    #
    # Validation:
    #
    # Minimum value = 0
    # Maximum value = 5

    rating: Optional[int] = Field(
        default=None,
        ge=0,
        le=5
    )

# ==========================================================
# HOME ROUTE
# ==========================================================


# GET /
#
# This is the first route of our API.
#
# When a user visits:
#
# http://127.0.0.1:8000/
#
# FastAPI executes this function.
#
# It simply returns a welcome message.


@app.get("/")
def root():


    return {

        "message": "Welcome to Wenyfour FastAPI App",

        "status": "success"
    }




# ==========================================================
# CREATE POST
# ==========================================================


# POST /posts
#
# This endpoint creates a new post.
#
# Workflow:
#
# 1. User sends JSON data
#
# Example:
#
# {
#   "title":"FastAPI Tutorial",
#   "content":"Learning CRUD operations",
#   "published":true,
#   "rating":5
# }
#
#
# 2. FastAPI converts JSON into a Post object
#
# 3. We insert the data into PostgreSQL
#
# 4. Database returns the newly created row
#
#


@app.post(
    "/posts",
    status_code=status.HTTP_201_CREATED
)
def create_post(post: Post):


    # cursor.execute()
    #
    # Sends SQL commands to PostgreSQL.
    #
    # %s are placeholders.
    #
    # They protect against SQL injection attacks.
    #
    # The values are supplied separately below.


    cursor.execute(

        """
        INSERT INTO posts 
        (
            title,
            content,
            published,
            rating
        )

        VALUES
        (
            %s,
            %s,
            %s,
            %s
        )

        RETURNING *
        """,


        (

            post.title,

            post.content,

            post.published,

            post.rating
        )

    )



    # fetchone() gets the single row returned
    # by RETURNING *
    #
    # Example:
    #
    # {
    #   id:1,
    #   title:"FastAPI Tutorial"
    # }


    new_post = cursor.fetchone()



    # commit permanently saves the change
    # in PostgreSQL.
    #
    # Without commit:
    #
    # Data may disappear after restart.

    conn.commit()



    return {

        "data": new_post,

        "message": "Post created successfully"
    }




# ==========================================================
# GET ALL POSTS
# ==========================================================


# GET /posts
#
# Retrieves every post stored
# inside PostgreSQL.
#
# SQL equivalent:
#
# SELECT * FROM posts;


@app.get(
    "/posts",
    status_code=status.HTTP_200_OK
)
def get_all_posts():


    # Execute SQL query

    cursor.execute(
        """
        SELECT * FROM posts
        """
    )



    # fetchall()
    #
    # Returns all rows from database.
    #
    # Example:
    #
    # [
    #   {
    #      id:1,
    #      title:"Post 1"
    #   },
    #
    #   {
    #      id:2,
    #      title:"Post 2"
    #   }
    # ]

    posts = cursor.fetchall()



    return {

        "data": posts,

        "total": len(posts),

        "message": "Posts retrieved successfully"

    }




# ==========================================================
# GET SINGLE POST
# ==========================================================


# GET /posts/{id}
#
# Retrieves one specific post.
#
# Example:
#
# /posts/5
#
# means:
#
# Find the post where id = 5


@app.get("/posts/{id}")
def get_post(id: int):


    # SQL query:
    #
    # SELECT all columns
    # FROM posts table
    # WHERE id matches the supplied id


    cursor.execute(

        """
        SELECT *
        FROM posts
        WHERE id = %s
        """,

        (id,)

    )



    # Get one result

    post = cursor.fetchone()



    # If no record exists:
    #
    # post will be None


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


# PUT /posts/{id}
#
# PUT is used to update an existing record.
#
# Example request:
#
# PUT /posts/1
#
# Means:
#
# Find the post where id = 1
# and replace its information.
#
#
# The user sends:
#
# {
#   "title":"Updated title",
#   "content":"Updated content",
#   "published":true,
#   "rating":5
# }
#
#
# Flow:
#
# 1. Receive post ID from URL
#
# 2. Receive updated information from request body
#
# 3. Run SQL UPDATE command
#
# 4. Return updated record
#


@app.put("/posts/{id}")
def update_post(id: int, post: Post):


    # UPDATE changes existing data in a table.
    #
    # SQL explanation:
    #
    # UPDATE posts
    #
    # means modify data inside posts table.
    #
    #
    # SET specifies which columns should change.
    #
    # WHERE identifies the specific row.
    #
    # RETURNING * gives back the updated row.


    cursor.execute(

        """
        UPDATE posts

        SET
            title = %s,
            content = %s,
            published = %s,
            rating = %s

        WHERE id = %s

        RETURNING *
        """,


        (

            post.title,

            post.content,

            post.published,

            post.rating,

            id
        )

    )



    # fetchone()
    #
    # Retrieves the updated row returned
    # by RETURNING *


    updated_post = cursor.fetchone()



    # If no row was updated,
    # it means the ID does not exist.


    if updated_post is None:


        raise HTTPException(

            status_code=status.HTTP_404_NOT_FOUND,

            detail=f"Post with ID {id} not found"

        )



    # Save changes permanently
    # into PostgreSQL.


    conn.commit()



    return {


        "data": updated_post,


        "message": "Post updated successfully"

    }





# ==========================================================
# DELETE POST
# ==========================================================


# DELETE /posts/{id}
#
# Deletes a post permanently.
#
#
# Example:
#
# DELETE /posts/3
#
# Means:
#
# Remove the post where id = 3
#
#
# Unlike GET and PUT,
# DELETE normally does not require
# a request body.
#
# The ID in the URL is enough.


@app.delete(
    "/posts/{id}",
    status_code=status.HTTP_204_NO_CONTENT
)

def delete_post(id: int):


    # DELETE removes data from a table.
    #
    # SQL explanation:
    #
    # DELETE FROM posts
    #
    # removes records from posts table.
    #
    # WHERE id = %s
    #
    # prevents deleting every post.
    #
    # RETURNING *
    #
    # returns the deleted record.


    cursor.execute(

        """
        DELETE FROM posts

        WHERE id = %s

        RETURNING *
        """,

        (id,)

    )



    # Get the deleted post

    deleted_post = cursor.fetchone()



    # If nothing was returned,
    # the post does not exist.


    if deleted_post is None:


        raise HTTPException(

            status_code=status.HTTP_404_NOT_FOUND,

            detail=f"Post with ID {id} not found"

        )



    # Permanently save deletion

    conn.commit()



    # HTTP 204 means:
    #
    # "Request succeeded but no response body"
    #
    # This is the standard response
    # for successful DELETE operations.


    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )