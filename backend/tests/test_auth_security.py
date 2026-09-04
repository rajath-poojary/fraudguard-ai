from uuid import uuid4

import pytest
from jose import jwt

from app.core.config import settings
from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    require_admin,
    verify_password,
)
from app.models import User


def test_passwords_are_hashed_and_verifiable():
    password = "correct horse battery staple"
    password_hash = hash_password(password)

    assert password_hash != password
    assert verify_password(password, password_hash)
    assert not verify_password("wrong password", password_hash)


def test_access_token_contains_user_id_and_role():
    user_id = uuid4()
    token = create_access_token(user_id, "admin")
    claims = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])

    assert claims["sub"] == str(user_id)
    assert claims["role"] == "admin"
    assert "exp" in claims


def test_non_admin_is_rejected():
    user = User(
        email="user@example.com",
        password_hash=hash_password("password123"),
        role="user",
    )

    with pytest.raises(Exception) as error:
        require_admin(user)

    assert error.value.status_code == 403


def test_admin_is_allowed():
    user = User(
        email="admin@example.com",
        password_hash=hash_password("password123"),
        role="admin",
    )

    assert require_admin(user) is user
