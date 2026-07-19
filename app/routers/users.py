from fastapi import HTTPException, Response, status,Depends,APIRouter
from .. import models, schemas, utils 
# Import classes used for error handling and responses

from sqlalchemy.orm import Session

from sqlalchemy.exc import IntegrityError

from ..database import get_db

router = APIRouter()  


@router.post(
    "/users",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.UserOut
)
def create_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db)
):
    ## Hash the password before storing it in the database
    
    hashed_password = utils.hash(user.password)
    user.password = hashed_password
    

    new_user = models.User(**user.model_dump())

    db.add(new_user)

    try:
        db.commit()
        db.refresh(new_user)

    except IntegrityError as e:
         db.rollback()
         raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email or phone number already exists."
            )
    

    return new_user


@router.get('/users/{id}', response_model=schemas.UserOut)
def get_user(id: int, db: Session = Depends(get_db)):

    user = db.query(models.User).filter(models.User.id == id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {id} not found"
        )

    return user 

