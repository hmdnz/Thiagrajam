


from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from . import models, schemas, utils, oauth2
from .database import get_db

router = APIRouter(
    tags=["Login"]
)  


@router.post("/login")
def login(user: schemas.UserLogin, db: Session = Depends(get_db)):

    db_user = db.query(models.User).filter(
        or_(
            models.User.email == user.email,
            models.User.phone_number == user.phone_number
        )
    ).first()

    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not utils.verify(user.password, db_user.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token = oauth2.create_access_token(data={"user_id": db_user.id})

    return {"access_token": access_token, "token_type": "bearer"}

# @router.post("/login")
# def login(user: schemas.UserLogin, db: Session = Depends(get_db)):

#     db_user = db.query(models.User).filter(
#         or_(
#             models.User.email == user.email,
#             models.User.phone_number == user.phone_number
#         )
#     ).first()

#     print("Login email:", user.email)
#     print("User found:", db_user)

#     if not db_user:
#         raise HTTPException(status_code=401, detail="Invalid email or password")

#     print("Stored hash:", db_user.password)

#     result = utils.verify(user.password, db_user.password)

#     print("Password match:", result)

#     if not result:
#         raise HTTPException(status_code=401, detail="Invalid email or password")

#     access_token = oauth2.create_access_token(
#         data={"user_id": db_user.id}
#     )

#     return {
#         "access_token": access_token,
#         "token_type": "bearer"
#     }