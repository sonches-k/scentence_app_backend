"""
Integration-тесты для эндпоинтов /auth/.
Используют FastAPI TestClient с подменёнными зависимостями (без БД).
"""

from unittest.mock import MagicMock

import pytest

from app.core.exceptions import InvalidRefreshTokenError
from app.core.use_cases.auth import AuthTokens, RefreshTokenUseCase, LogoutUseCase
from app.main import app
from app.api.dependencies import get_refresh_token_use_case, get_logout_use_case


pytestmark = pytest.mark.integration

BASE = "/api/v1"


@pytest.fixture
def mock_refresh_uc():
    uc = MagicMock(spec=RefreshTokenUseCase)
    uc.execute.return_value = AuthTokens(
        access_token="new_access_token",
        refresh_token="new_refresh_token",
    )
    return uc


@pytest.fixture
def mock_logout_uc():
    return MagicMock(spec=LogoutUseCase)


@pytest.fixture
def auth_client(mock_refresh_uc, mock_logout_uc):
    app.dependency_overrides[get_refresh_token_use_case] = lambda: mock_refresh_uc
    app.dependency_overrides[get_logout_use_case] = lambda: mock_logout_uc
    from fastapi.testclient import TestClient
    client = TestClient(app, raise_server_exceptions=True)
    yield client, mock_refresh_uc, mock_logout_uc
    app.dependency_overrides.pop(get_refresh_token_use_case, None)
    app.dependency_overrides.pop(get_logout_use_case, None)


class TestRefreshEndpoint:

    def test_refresh_success_returns_tokens(self, auth_client):
        client, _, _ = auth_client
        response = client.post(
            f"{BASE}/auth/refresh",
            json={"refresh_token": "valid_refresh_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "new_access_token"
        assert data["refresh_token"] == "new_refresh_token"

    def test_refresh_invalid_token_returns_401(self, auth_client):
        client, mock_uc, _ = auth_client
        mock_uc.execute.side_effect = InvalidRefreshTokenError("Токен не найден")

        response = client.post(
            f"{BASE}/auth/refresh",
            json={"refresh_token": "invalid_token"},
        )

        assert response.status_code == 401

    def test_refresh_missing_token_returns_422(self, auth_client):
        client, _, _ = auth_client
        response = client.post(f"{BASE}/auth/refresh", json={})

        assert response.status_code == 422

    def test_refresh_calls_use_case_with_token(self, auth_client):
        client, mock_uc, _ = auth_client
        client.post(
            f"{BASE}/auth/refresh",
            json={"refresh_token": "my_token"},
        )

        mock_uc.execute.assert_called_once_with("my_token")


class TestLogoutEndpoint:

    def test_logout_success_returns_200(self, auth_client):
        client, _, _ = auth_client
        response = client.post(
            f"{BASE}/auth/logout",
            json={"refresh_token": "valid_refresh_token"},
        )

        assert response.status_code == 200
        assert response.json()["message"] == "Вы вышли из аккаунта"

    def test_logout_calls_use_case_with_token(self, auth_client):
        client, _, mock_uc = auth_client
        client.post(
            f"{BASE}/auth/logout",
            json={"refresh_token": "my_refresh_token"},
        )

        mock_uc.execute.assert_called_once_with("my_refresh_token")

    def test_logout_missing_token_returns_422(self, auth_client):
        client, _, _ = auth_client
        response = client.post(f"{BASE}/auth/logout", json={})

        assert response.status_code == 422

    def test_logout_invalidates_token(self, auth_client):
        """После logout use case вызывает delete, токен больше не действителен."""
        client, mock_refresh_uc, mock_logout_uc = auth_client

        client.post(
            f"{BASE}/auth/logout",
            json={"refresh_token": "used_token"},
        )

        mock_logout_uc.execute.assert_called_once_with("used_token")
        mock_refresh_uc.execute.assert_not_called()
