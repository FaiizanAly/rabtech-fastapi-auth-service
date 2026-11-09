"""Comprehensive API test suite validating registration, JWT auth, protected routes, and CRUD."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from auth_service.database import Base, get_db
from auth_service.main import app

# Create in-memory SQLite database shared across threads for testing
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "auth-service"


def test_user_registration_success(client):
    payload = {
        "username": "faizanali",
        "email": "git.faizanali@gmail.com",
        "password": "StrongPassword123!",
    }
    response = client.post("/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "faizanali"
    assert data["email"] == "git.faizanali@gmail.com"
    assert "password" not in data
    assert "hashed_password" not in data
    assert data["is_active"] is True


def test_user_registration_duplicate_username_and_email(client):
    payload = {
        "username": "john_doe",
        "email": "john@example.com",
        "password": "Password123",
    }
    # Initial registration
    res1 = client.post("/register", json=payload)
    assert res1.status_code == 201

    # Duplicate username
    dup_username = {
        "username": "john_doe",
        "email": "another@example.com",
        "password": "Password456",
    }
    res2 = client.post("/register", json=dup_username)
    assert res2.status_code == 400
    assert "Username already registered" in res2.json()["detail"]

    # Duplicate email
    dup_email = {
        "username": "different_user",
        "email": "john@example.com",
        "password": "Password456",
    }
    res3 = client.post("/register", json=dup_email)
    assert res3.status_code == 400
    assert "Email already registered" in res3.json()["detail"]


def test_token_generation_and_login(client):
    # Register user
    client.post("/register", json={
        "username": "alice",
        "email": "alice@example.com",
        "password": "AliceSecretPassword",
    })

    # Successful login via form data (OAuth2 password flow)
    login_res = client.post("/token", data={
        "username": "alice",
        "password": "AliceSecretPassword",
    })
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"

    # Failed login with incorrect password
    bad_pwd_res = client.post("/token", data={
        "username": "alice",
        "password": "WrongPassword",
    })
    assert bad_pwd_res.status_code == 401
    assert "Incorrect username or password" in bad_pwd_res.json()["detail"]

    # Failed login with non-existent username
    bad_user_res = client.post("/token", data={
        "username": "nonexistent",
        "password": "AnyPassword",
    })
    assert bad_user_res.status_code == 401


def test_protected_users_me_route(client):
    # Register and obtain token
    client.post("/register", json={
        "username": "bob",
        "email": "bob@example.com",
        "password": "BobPassword123",
    })
    token_res = client.post("/token", data={
        "username": "bob",
        "password": "BobPassword123",
    })
    token = token_res.json()["access_token"]

    # Access /users/me with valid bearer token
    auth_headers = {"Authorization": f"Bearer {token}"}
    me_res = client.get("/users/me", headers=auth_headers)
    assert me_res.status_code == 200
    user_info = me_res.json()
    assert user_info["username"] == "bob"
    assert user_info["email"] == "bob@example.com"

    # Access without authorization header
    unauth_res = client.get("/users/me")
    assert unauth_res.status_code == 401

    # Access with malformed/invalid token
    invalid_res = client.get("/users/me", headers={"Authorization": "Bearer invalid.jwt.token"})
    assert invalid_res.status_code == 401


def test_item_creation_and_listing(client):
    # Register and login
    client.post("/register", json={
        "username": "charlie",
        "email": "charlie@example.com",
        "password": "CharliePassword123",
    })
    token_res = client.post("/token", data={
        "username": "charlie",
        "password": "CharliePassword123",
    })
    token = token_res.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Create item authenticated
    item_payload = {
        "title": "Cloud Ledger Service",
        "description": "High throughput microservice with distributed locking",
    }
    create_res = client.post("/items/", json=item_payload, headers=auth_headers)
    assert create_res.status_code == 201
    item_data = create_res.json()
    assert item_data["title"] == "Cloud Ledger Service"
    assert item_data["description"] == "High throughput microservice with distributed locking"
    assert "id" in item_data

    # Attempt to create item without authentication
    unauth_item_res = client.post("/items/", json={"title": "Unauthorized Item"})
    assert unauth_item_res.status_code == 401

    # Public list of items
    list_res = client.get("/items/")
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) == 1
    assert items[0]["title"] == "Cloud Ledger Service"

    # Pagination test
    empty_page = client.get("/items/?skip=10&limit=5")
    assert empty_page.status_code == 200
    assert empty_page.json() == []
