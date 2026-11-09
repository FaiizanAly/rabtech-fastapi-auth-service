"""FastAPI Application Entrypoint exposing Auth and Item endpoints."""

from typing import List
import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from auth_service import crud, models, schemas
from auth_service.database import Base, engine, get_db
from auth_service.security import create_access_token, decode_access_token, oauth2_scheme

# Create database tables automatically
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Auth & Item Management Microservice",
    description="FastAPI service with JWT Authentication, OAuth2 password flow, and SQLAlchemy ORM.",
    version="0.1.0",
)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    """Dependency that decodes Bearer JWT token and retrieves the authenticated User."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception

    user = crud.get_user_by_username(db, username=username)
    if user is None:
        raise credentials_exception
    return user


@app.get("/", tags=["Health"])
def root():
    """Root health and service information."""
    return {
        "service": "auth-service",
        "status": "healthy",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.post(
    "/register",
    response_model=schemas.UserResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Authentication"],
)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Register a new user account with hashed password."""
    if crud.get_user_by_username(db, username=user.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )
    if crud.get_user_by_email(db, email=user.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    return crud.create_user(db=db, user=user)


@app.post("/token", response_model=schemas.Token, tags=["Authentication"])
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Authenticate credentials via OAuth2 Password Request Form and issue a JWT token."""
    user = crud.authenticate_user(db, username=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/users/me", response_model=schemas.UserResponse, tags=["Users"])
def read_users_me(current_user: models.User = Depends(get_current_user)):
    """Protected route returning the currently authenticated user's profile."""
    return current_user


@app.post(
    "/items/",
    response_model=schemas.ItemResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Items"],
)
def create_item(
    item: schemas.ItemCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Protected route creating a new item owned by the authenticated user."""
    return crud.create_user_item(db=db, item=item, user_id=current_user.id)


@app.get("/items/", response_model=List[schemas.ItemResponse], tags=["Items"])
def read_items(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Public paginated route listing all created items."""
    return crud.get_items(db, skip=skip, limit=limit)
