import pytest
from fastapi.testclient import TestClient
from fastapi_main import app

client = TestClient(app)

# Test for root endpoint
def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to the AI-Powered TED Talk Assistant API!"}

# Test for login endpoint
def test_login_success(mocker):
    mocker.patch("fastapi_main.get_db_connection")
    mocker.patch("fastapi_main.verify_password", return_value=True)
    mocker.patch("fastapi_main.create_access_token", return_value="dummy_token")

    response = client.post(
        "/login",
        data={"username": "test_user", "password": "test_password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_login_failure(mocker):
    mocker.patch("fastapi_main.get_db_connection")
    mocker.patch("fastapi_main.verify_password", return_value=False)

    response = client.post(
        "/login",
        data={"username": "invalid_user", "password": "wrong_password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid credentials"

# Test for signup endpoint
def test_signup_success(mocker):
    mocker.patch("fastapi_main.get_db_connection")
    mocker.patch("fastapi_main.hash_password", return_value="hashed_password")

    response = client.post(
        "/signup",
        json={"username": "new_user", "password": "secure_password", "email": "user@example.com"}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "User signed up successfully!"

def test_signup_user_exists(mocker):
    mocker.patch("fastapi_main.get_db_connection")
    mocker.patch("fastapi_main.hash_password", return_value="hashed_password")

    def mock_cursor_execute(query, params):
        if "SELECT" in query:
            return True  # Simulate user already exists

    mocker.patch("fastapi_main.get_db_connection().cursor.execute", side_effect=mock_cursor_execute)

    response = client.post(
        "/signup",
        json={"username": "existing_user", "password": "password123", "email": "existing@example.com"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "User already exists"

# Test for trending talks endpoint
def test_get_trending_talks(mocker):
    mocker.patch("fastapi_main.get_trending_talks_agent", return_value=[{"title": "Talk 1"}])

    response = client.get("/trending")
    assert response.status_code == 200
    assert "talks" in response.json()

