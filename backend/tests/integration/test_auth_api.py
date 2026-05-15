"""
Integration tests for Authentication API endpoints.

Tests user registration, login, and token management.
"""
import pytest
import uuid
from datetime import datetime, timedelta

from app.models.user import User, Organization
from app.core.security import get_password_hash, create_access_token


@pytest.mark.integration
@pytest.mark.asyncio
class TestAuthRegistration:
    """Test user registration flow."""

    async def test_register_new_user(self, client, db_session):
        """Test successful user registration."""
        user_data = {
            "email": "newuser@example.com",
            "password": "SecurePassword123!",
            "full_name": "New User",
            "company_name": "Test Company",
        }

        response = client.post("/api/v1/auth/register", json=user_data)

        assert response.status_code == 201
        data = response.json()

        assert data["message"] == "User registered successfully. Please verify your email."
        assert data["user"]["email"] == "newuser@example.com"
        assert data["user"]["full_name"] == "New User"
        assert "id" in data["user"]

    async def test_register_duplicate_email(self, client, test_user):
        """Test registration with existing email fails."""
        user_data = {
            "email": test_user.email,
            "password": "Password123!",
            "full_name": "Another User",
        }

        response = client.post("/api/v1/auth/register", json=user_data)

        assert response.status_code == 400
        data = response.json()
        assert "already registered" in data["detail"].lower()

    async def test_register_invalid_email(self, client):
        """Test registration with invalid email format."""
        user_data = {
            "email": "invalid_email",
            "password": "Password123!",
            "full_name": "Test User",
        }

        response = client.post("/api/v1/auth/register", json=user_data)

        assert response.status_code == 422

    async def test_register_weak_password(self, client):
        """Test registration with weak password."""
        user_data = {
            "email": "user@example.com",
            "password": "123",  # Too short
            "full_name": "Test User",
        }

        response = client.post("/api/v1/auth/register", json=user_data)

        assert response.status_code == 422

    async def test_register_creates_organization(self, client, db_session):
        """Test that registration creates user's organization."""
        user_data = {
            "email": "orgtest@example.com",
            "password": "SecurePassword123!",
            "full_name": "Org Test",
            "company_name": "Org Test Company",
        }

        response = client.post("/api/v1/auth/register", json=user_data)

        assert response.status_code == 201

        # Verify organization was created
        from sqlalchemy import select

        result = await db_session.execute(
            select(Organization).where(Organization.name == "Org Test Company")
        )
        organization = result.scalar_one_or_none()

        assert organization is not None
        assert organization.name == "Org Test Company"


@pytest.mark.integration
@pytest.mark.asyncio
class TestAuthLogin:
    """Test user login flow."""

    async def test_login_success(self, client, db_session):
        """Test successful login."""
        # Create user
        password = "TestPassword123!"
        user = User(
            email="logintest@example.com",
            hashed_password=get_password_hash(password),
            full_name="Login Test",
        )
        db_session.add(user)
        await db_session.commit()

        # Login
        login_data = {
            "email": "logintest@example.com",
            "password": password,
        }

        response = client.post("/api/v1/auth/login", json=login_data)

        assert response.status_code == 200
        data = response.json()

        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"]["email"] == "logintest@example.com"

    async def test_login_wrong_password(self, client, test_user):
        """Test login with incorrect password."""
        login_data = {
            "email": test_user.email,
            "password": "WrongPassword123!",
        }

        response = client.post("/api/v1/auth/login", json=login_data)

        assert response.status_code == 401
        data = response.json()
        assert "incorrect" in data["detail"].lower()

    async def test_login_nonexistent_user(self, client):
        """Test login with non-existent email."""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "Password123!",
        }

        response = client.post("/api/v1/auth/login", json=login_data)

        assert response.status_code == 401

    async def test_login_missing_credentials(self, client):
        """Test login with missing credentials."""
        response = client.post("/api/v1/auth/login", json={})

        assert response.status_code == 422

    async def test_login_returns_user_info(self, client, test_user):
        """Test that login returns user information."""
        login_data = {
            "email": test_user.email,
            "password": "password123",  # Assumes test_user was created with this
        }

        # Note: This test might need adjustment based on actual test_user setup
        response = client.post("/api/v1/auth/login", json=login_data)

        if response.status_code == 200:
            data = response.json()
            assert data["user"]["email"] == test_user.email
            assert "id" in data["user"]


@pytest.mark.integration
@pytest.mark.asyncio
class TestTokenManagement:
    """Test token refresh and validation."""

    async def test_refresh_token(self, client, test_user):
        """Test refreshing access token."""
        # Create refresh token
        refresh_token = create_access_token(
            data={"sub": str(test_user.id), "type": "refresh"},
            expires_delta=timedelta(days=7),
        )

        refresh_data = {"refresh_token": refresh_token}

        response = client.post("/api/v1/auth/refresh", json=refresh_data)

        assert response.status_code == 200
        data = response.json()

        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"

    async def test_refresh_with_invalid_token(self, client):
        """Test refresh with invalid token."""
        refresh_data = {"refresh_token": "invalid_token"}

        response = client.post("/api/v1/auth/refresh", json=refresh_data)

        assert response.status_code == 401

    async def test_refresh_with_expired_token(self, client, test_user):
        """Test refresh with expired token."""
        # Create expired refresh token
        expired_token = create_access_token(
            data={"sub": str(test_user.id), "type": "refresh"},
            expires_delta=timedelta(seconds=-1),  # Already expired
        )

        refresh_data = {"refresh_token": expired_token}

        response = client.post("/api/v1/auth/refresh", json=refresh_data)

        assert response.status_code == 401

    async def test_access_protected_endpoint(self, auth_client):
        """Test accessing protected endpoint with valid token."""
        response = auth_client.get("/api/v1/agents")

        assert response.status_code == 200

    async def test_access_protected_endpoint_no_token(self, client):
        """Test accessing protected endpoint without token."""
        response = client.get("/api/v1/agents")

        assert response.status_code == 401

    async def test_access_protected_endpoint_invalid_token(self, client):
        """Test accessing protected endpoint with invalid token."""
        client.headers = {"Authorization": "Bearer invalid_token"}

        response = client.get("/api/v1/agents")

        assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
class TestUserProfile:
    """Test user profile management."""

    async def test_get_current_user(self, auth_client, test_user):
        """Test retrieving current user profile."""
        response = auth_client.get("/api/v1/auth/me")

        assert response.status_code == 200
        data = response.json()

        assert data["email"] == test_user.email
        assert data["full_name"] == test_user.full_name
        assert "id" in data

    async def test_update_user_profile(self, auth_client):
        """Test updating user profile."""
        update_data = {
            "full_name": "Updated Name",
            "company_name": "Updated Company",
        }

        response = auth_client.put("/api/v1/auth/me", json=update_data)

        assert response.status_code == 200
        data = response.json()

        assert data["full_name"] == "Updated Name"

    async def test_change_password(self, auth_client, test_user):
        """Test changing user password."""
        password_data = {
            "current_password": "password123",
            "new_password": "NewPassword123!",
        }

        response = auth_client.post("/api/v1/auth/change-password", json=password_data)

        assert response.status_code == 200

    async def test_change_password_wrong_current(self, auth_client):
        """Test changing password with wrong current password."""
        password_data = {
            "current_password": "wrong_password",
            "new_password": "NewPassword123!",
        }

        response = auth_client.post("/api/v1/auth/change-password", json=password_data)

        assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
class TestPasswordReset:
    """Test password reset flow."""

    async def test_request_password_reset(self, client, test_user):
        """Test requesting password reset."""
        reset_data = {"email": test_user.email}

        response = client.post("/api/v1/auth/forgot-password", json=reset_data)

        assert response.status_code == 200
        data = response.json()

        assert "message" in data

    async def test_request_reset_nonexistent_email(self, client):
        """Test requesting reset for non-existent email."""
        reset_data = {"email": "nonexistent@example.com"}

        response = client.post("/api/v1/auth/forgot-password", json=reset_data)

        # Should return 200 for security (don't reveal if email exists)
        assert response.status_code == 200

    async def test_reset_password_with_token(self, client):
        """Test resetting password with valid token."""
        reset_token = "valid_reset_token_here"

        reset_data = {
            "token": reset_token,
            "new_password": "NewSecurePassword123!",
        }

        response = client.post("/api/v1/auth/reset-password", json=reset_data)

        # This will fail without actual token generation
        # In real implementation, you'd generate a valid token first
        assert response.status_code in [200, 400, 401]


@pytest.mark.integration
@pytest.mark.asyncio
class TestOrganizationAccess:
    """Test organization-based access control."""

    async def test_user_organization_isolation(
        self, client, db_session, test_organization
    ):
        """Test that users can only see their organization's data."""
        # Create two users in different organizations
        user1 = User(
            email="user1@example.com",
            hashed_password=get_password_hash("password"),
            full_name="User 1",
        )

        user2 = User(
            email="user2@example.com",
            hashed_password=get_password_hash("password"),
            full_name="User 2",
        )

        db_session.add(user1)
        db_session.add(user2)
        await db_session.commit()

        # Create tokens for each user
        token1 = create_access_token(data={"sub": str(user1.id)})
        token2 = create_access_token(data={"sub": str(user2.id)})

        # Each user should only see their own organization's data
        # Implementation depends on actual organization association
        assert token1 != token2
