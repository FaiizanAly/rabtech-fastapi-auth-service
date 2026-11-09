"""CRUD operations for User accounts and Items."""

from typing import List, Optional
from sqlalchemy.orm import Session

from auth_service import models, schemas
from auth_service.security import get_password_hash, verify_password


def get_user(db: Session, user_id: int) -> Optional[models.User]:
    """Retrieve a single user by database ID."""
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> Optional[models.User]:
    """Retrieve a single user by username."""
    return db.query(models.User).filter(models.User.username == username).first()


def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    """Retrieve a single user by email address."""
    return db.query(models.User).filter(models.User.email == email).first()


def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    """Create a new user with a hashed password in the database."""
    hashed_pwd = get_password_hash(user.password)
    db_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_pwd,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def authenticate_user(db: Session, username: str, password: str) -> Optional[models.User]:
    """Authenticate a user by username and password against stored hash."""
    user = get_user_by_username(db, username=username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_user_item(db: Session, item: schemas.ItemCreate, user_id: int) -> models.Item:
    """Create a new item associated with the given user_id."""
    db_item = models.Item(
        title=item.title,
        description=item.description,
        owner_id=user_id,
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def get_items(db: Session, skip: int = 0, limit: int = 100) -> List[models.Item]:
    """Retrieve a paginated list of items across all users."""
    return db.query(models.Item).offset(skip).limit(limit).all()
