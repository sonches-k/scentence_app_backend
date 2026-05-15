from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.core.entities import User
from app.core.exceptions import (
    InvalidCodeError,
    InvalidRefreshTokenError,
    TooManyAttemptsError,
    UserNotFoundError,
)
from app.core.entities import StoredRefreshToken, VerificationCode
from app.core.interfaces import IEmailService, IJWTService, IUserRepository
from app.core.use_cases.auth import (
    AuthTokens,
    LoginUseCase,
    LogoutUseCase,
    RefreshTokenUseCase,
)


pytestmark = pytest.mark.unit


@pytest.fixture
def mock_user_repo():
    return MagicMock(spec=IUserRepository)


@pytest.fixture
def mock_email_service():
    return MagicMock(spec=IEmailService)


@pytest.fixture
def mock_jwt_service():
    svc = MagicMock(spec=IJWTService)
    svc.create_token.return_value = "access_token"
    svc.issue_refresh_credentials.return_value = (
        "refresh_token",
        datetime.now(timezone.utc) + timedelta(days=30),
    )
    return svc


@pytest.fixture
def sample_user():
    return User(id=1, email="user@example.com")


class TestLoginUseCase:

    def test_login_success_sends_code(self, mock_user_repo, mock_email_service, sample_user):
        mock_user_repo.get_by_email.return_value = sample_user

        use_case = LoginUseCase(user_repo=mock_user_repo, email_service=mock_email_service)
        use_case.execute("user@example.com")

        mock_user_repo.delete_verification_codes.assert_called_once_with("user@example.com")
        mock_user_repo.create_verification_code.assert_called_once()
        mock_email_service.send_verification_code.assert_called_once()

    def test_login_user_not_found_raises(self, mock_user_repo, mock_email_service):
        mock_user_repo.get_by_email.return_value = None

        use_case = LoginUseCase(user_repo=mock_user_repo, email_service=mock_email_service)

        with pytest.raises(UserNotFoundError):
            use_case.execute("unknown@example.com")

        mock_email_service.send_verification_code.assert_not_called()

    def test_login_clears_old_codes_before_creating_new(
        self, mock_user_repo, mock_email_service, sample_user
    ):
        mock_user_repo.get_by_email.return_value = sample_user

        use_case = LoginUseCase(user_repo=mock_user_repo, email_service=mock_email_service)
        use_case.execute("user@example.com")

        calls = mock_user_repo.method_calls
        delete_idx = next(i for i, c in enumerate(calls) if "delete_verification_codes" in str(c))
        create_idx = next(i for i, c in enumerate(calls) if "create_verification_code" in str(c))
        assert delete_idx < create_idx


class TestRefreshTokenUseCase:

    def test_refresh_success_rotates_tokens(
        self, mock_user_repo, mock_jwt_service, sample_user
    ):
        stored = StoredRefreshToken(
            user_id=1,
            expires_at=datetime.now(timezone.utc) + timedelta(days=10),
        )
        mock_user_repo.get_refresh_token.return_value = stored

        use_case = RefreshTokenUseCase(user_repo=mock_user_repo, jwt_service=mock_jwt_service)
        result = use_case.execute("old_refresh_token")

        assert isinstance(result, AuthTokens)
        mock_user_repo.delete_refresh_token.assert_called_once_with("old_refresh_token")
        mock_user_repo.create_refresh_token.assert_called_once()

    def test_refresh_token_not_found_raises(self, mock_user_repo, mock_jwt_service):
        mock_user_repo.get_refresh_token.return_value = None

        use_case = RefreshTokenUseCase(user_repo=mock_user_repo, jwt_service=mock_jwt_service)

        with pytest.raises(InvalidRefreshTokenError):
            use_case.execute("nonexistent_token")

        mock_user_repo.delete_refresh_token.assert_not_called()

    def test_refresh_token_expired_raises_and_deletes(self, mock_user_repo, mock_jwt_service):
        stored = StoredRefreshToken(
            user_id=1,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        mock_user_repo.get_refresh_token.return_value = stored

        use_case = RefreshTokenUseCase(user_repo=mock_user_repo, jwt_service=mock_jwt_service)

        with pytest.raises(InvalidRefreshTokenError):
            use_case.execute("expired_token")

        mock_user_repo.delete_refresh_token.assert_called_once_with("expired_token")
        mock_user_repo.create_refresh_token.assert_not_called()

    def test_refresh_issues_new_access_token(self, mock_user_repo, mock_jwt_service):
        stored = StoredRefreshToken(
            user_id=42,
            expires_at=datetime.now(timezone.utc) + timedelta(days=10),
        )
        mock_user_repo.get_refresh_token.return_value = stored

        use_case = RefreshTokenUseCase(user_repo=mock_user_repo, jwt_service=mock_jwt_service)
        result = use_case.execute("valid_token")

        mock_jwt_service.create_token.assert_called_once_with(42)
        assert result.access_token == "access_token"
        assert result.refresh_token == "refresh_token"


class TestLogoutUseCase:

    def test_logout_deletes_refresh_token(self, mock_user_repo):
        use_case = LogoutUseCase(user_repo=mock_user_repo)
        use_case.execute("some_refresh_token")

        mock_user_repo.delete_refresh_token.assert_called_once_with("some_refresh_token")

    def test_logout_idempotent_no_error_on_missing_token(self, mock_user_repo):
        mock_user_repo.delete_refresh_token.return_value = None

        use_case = LogoutUseCase(user_repo=mock_user_repo)
        use_case.execute("nonexistent_token")

        mock_user_repo.delete_refresh_token.assert_called_once()
