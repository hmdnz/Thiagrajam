from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


# ==========================================================
# PYDANTIC MODELS
# ==========================================================

# Base model containing the common fields for a post.
# This model is reused for both creating and updating posts.
class PostBase(BaseModel):

    # Title cannot be empty
    title: str = Field(..., min_length=1, max_length=200)

    # Content cannot be empty
    content: str = Field(..., min_length=1)

    # Default value is True if the client doesn't provide one
    published: bool = True

    # Rating is optional and must be between 0 and 5
    rating: Optional[int] = Field(default=None, ge=0, le=5)

class PostCreate(PostBase):
    pass    

class PostResponse(BaseModel):

    id: int

    title: str

    content: str

    published: bool

    rating: Optional[int]

    created_at: datetime


    class Config:
        orm_mode = True