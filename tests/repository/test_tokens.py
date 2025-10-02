"""Tests for E*TRADE repository token management."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repository import ETradeRepository


def test_token_persistence(temp_config_home: Path) -> None:
    """Test that tokens are saved and loaded correctly."""
    repo = ETradeRepository(
        consumer_key="test_key",
        consumer_secret="test_secret",
        environment="sandbox",
        profile_id="test_profile",
    )

    # Save tokens
    expires_at = datetime.now(UTC) + timedelta(hours=1)
    repo._save_tokens("test_token", "test_secret", expires_at)

    # Verify file exists with correct permissions
    tokens_file = temp_config_home / "etrade-mcp" / "tokens.json"
    assert tokens_file.exists()
    assert oct(tokens_file.stat().st_mode)[-3:] == "600"

    # Load tokens back
    result = repo._load_tokens()
    assert result is not None
    token, secret, loaded_expires = result
    assert token == "test_token"
    assert secret == "test_secret"
    assert loaded_expires == expires_at


def test_token_persistence_missing_file(temp_config_home: Path) -> None:
    """Test loading tokens when file doesn't exist."""
    repo = ETradeRepository(
        consumer_key="test_key",
        consumer_secret="test_secret",
        environment="sandbox",
    )

    result = repo._load_tokens()
    assert result is None


def test_token_persistence_wrong_environment(temp_config_home: Path) -> None:
    """Test loading tokens for wrong environment."""
    repo_sandbox = ETradeRepository(
        consumer_key="test_key",
        consumer_secret="test_secret",
        environment="sandbox",
        profile_id="test_profile",
    )

    expires_at = datetime.now(UTC) + timedelta(hours=1)
    repo_sandbox._save_tokens("test_token", "test_secret", expires_at)

    # Try to load with production environment
    repo_prod = ETradeRepository(
        consumer_key="test_key",
        consumer_secret="test_secret",
        environment="production",
        profile_id="test_profile",
    )

    result = repo_prod._load_tokens()
    assert result is None


def test_token_renewal(temp_config_home: Path) -> None:
    """Test token renewal."""
    repo = ETradeRepository(
        consumer_key="test_key",
        consumer_secret="test_secret",
        environment="sandbox",
    )

    # Set up an authorized session
    mock_session = MagicMock()
    mock_session._client.client.resource_owner_key = "test_token"
    mock_session._client.client.resource_owner_secret = "test_secret"
    mock_session.get.return_value.status_code = 200
    mock_session.get.return_value.raise_for_status.return_value = None

    repo.session = mock_session
    repo._is_authorized = True
    repo._token_expires_at = datetime.now(UTC) + timedelta(hours=1)

    # Renew tokens
    repo._renew_tokens()

    # Verify renewal was called
    mock_session.get.assert_called_once_with(repo.RENEW_TOKEN_URL)


def test_token_expiration_check() -> None:
    """Test token expiration checking."""
    repo = ETradeRepository(
        consumer_key="test_key",
        consumer_secret="test_secret",
        environment="sandbox",
    )

    # No expiration set
    assert repo._is_token_expired()

    # Token expires in 1 hour (not expired)
    repo._token_expires_at = datetime.now(UTC) + timedelta(hours=1)
    assert not repo._is_token_expired()

    # Token expires in 20 minutes (should renew)
    repo._token_expires_at = datetime.now(UTC) + timedelta(minutes=20)
    assert repo._is_token_expired()

    # Token expired
    repo._token_expires_at = datetime.now(UTC) - timedelta(hours=1)
    assert repo._is_token_expired()


def test_load_tokens_missing_profile(temp_config_home: Path) -> None:
    """Test loading tokens when profile doesn't exist in file."""
    # Create repo with profile 0
    repo0 = ETradeRepository(
        consumer_key="test_key",
        consumer_secret="test_secret",
        environment="sandbox",
        profile_id="0",
    )

    # Save tokens for profile 0
    expires_at = datetime.now(UTC) + timedelta(hours=1)
    repo0._save_tokens("token0", "secret0", expires_at)

    # Try to load tokens for profile 1 (doesn't exist)
    repo1 = ETradeRepository(
        consumer_key="test_key",
        consumer_secret="test_secret",
        environment="sandbox",
        profile_id="1",
    )

    result = repo1._load_tokens()
    assert result is None


def test_load_tokens_malformed_data(temp_config_home: Path) -> None:
    """Test loading tokens with malformed token data."""
    repo = ETradeRepository(
        consumer_key="test_key",
        consumer_secret="test_secret",
        environment="sandbox",
        profile_id="test",
    )

    # Create malformed tokens file (missing required fields)
    tokens_file = repo._get_tokens_file()
    with open(tokens_file, "w") as f:
        json.dump(
            {
                "test": {
                    "environment": "sandbox",
                    # Missing oauth_token and oauth_token_secret
                    "expires_at": datetime.now(UTC).isoformat(),
                }
            },
            f,
        )

    result = repo._load_tokens()
    assert result is None


def test_token_renewal_failure(temp_config_home: Path) -> None:
    """Test token renewal failure."""
    repo = ETradeRepository(
        consumer_key="test_key",
        consumer_secret="test_secret",
        environment="sandbox",
    )

    # Set up an authorized session that will fail on renewal
    mock_session = MagicMock()
    mock_session.get.side_effect = Exception("Network error")
    repo.session = mock_session
    repo._is_authorized = True
    repo._token_expires_at = datetime.now(UTC) + timedelta(hours=1)

    with pytest.raises(Exception, match="Network error"):
        repo._renew_tokens()


def test_ensure_authorized_with_expired_token_renewal_failure(
    temp_config_home: Path,
) -> None:
    """Test _ensure_authorized when token is expired and renewal fails."""
    repo = ETradeRepository(
        consumer_key="test_key",
        consumer_secret="test_secret",
        environment="sandbox",
    )

    # Set up expired session
    mock_session = MagicMock()
    mock_session.get.side_effect = Exception("Renewal failed")
    mock_session._client.client.resource_owner_key = "test_token"
    mock_session._client.client.resource_owner_secret = "test_secret"

    repo.session = mock_session
    repo._is_authorized = True
    repo._token_expires_at = datetime.now(UTC) - timedelta(hours=1)

    with pytest.raises(RuntimeError, match="Token renewal failed"):
        repo._ensure_authorized()


def test_renew_tokens_without_session() -> None:
    """Test that _renew_tokens raises error without a session."""
    repo = ETradeRepository(
        consumer_key="test_key",
        consumer_secret="test_secret",
        environment="sandbox",
    )

    with pytest.raises(RuntimeError, match="Cannot renew tokens"):
        repo._renew_tokens()


def test_renew_tokens_without_credentials(temp_config_home: Path) -> None:
    """Test token renewal when session doesn't have credentials."""
    repo = ETradeRepository(
        consumer_key="test_key",
        consumer_secret="test_secret",
        environment="sandbox",
    )

    # Set up session without credentials
    mock_session = MagicMock()
    mock_session.get.return_value.status_code = 200
    mock_session.get.return_value.raise_for_status.return_value = None
    # No resource_owner_key/secret
    mock_session._client.client.resource_owner_key = None
    mock_session._client.client.resource_owner_secret = None

    repo.session = mock_session
    repo._is_authorized = True
    repo._token_expires_at = datetime.now(UTC) + timedelta(hours=1)

    # Should not raise, just skip saving
    repo._renew_tokens()
