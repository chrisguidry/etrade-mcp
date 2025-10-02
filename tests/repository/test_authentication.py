"""Tests for E*TRADE repository authentication and OAuth flow."""

from datetime import UTC
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from repository import ETradeRepository


def test_ensure_authorized_not_authorized() -> None:
    """Test _ensure_authorized raises error when not authorized."""
    repo = ETradeRepository(
        consumer_key="test_key",
        consumer_secret="test_secret",
        environment="sandbox",
        auto_authorize=False,
    )

    with pytest.raises(RuntimeError, match="Not authorized"):
        repo._ensure_authorized()


def test_authorize_success(temp_config_home: Path) -> None:
    """Test successful OAuth authorization flow."""
    with (
        patch("repository.OAuth1Session") as mock_oauth,
        patch("repository.webbrowser.open") as mock_browser,
        patch("builtins.input", return_value="verification_code"),
        patch("builtins.print"),
        patch("repository.sys.stdin.isatty", return_value=True),
    ):
        # Mock request token response
        mock_oauth_instance = MagicMock()
        mock_oauth.return_value = mock_oauth_instance
        mock_oauth_instance.fetch_request_token.return_value = {
            "oauth_token": "request_token",
            "oauth_token_secret": "request_secret",
        }
        mock_oauth_instance.fetch_access_token.return_value = {
            "oauth_token": "access_token",
            "oauth_token_secret": "access_secret",
        }

        repo = ETradeRepository(
            consumer_key="test_key",
            consumer_secret="test_secret",
            environment="sandbox",
            auto_authorize=True,
        )

        repo.authorize()

        assert repo._is_authorized
        assert repo.session is not None
        mock_browser.assert_called_once()

        # Verify tokens were saved
        tokens_file = temp_config_home / "etrade-mcp" / "tokens.json"
        assert tokens_file.exists()


def test_authorize_no_auto_browser(temp_config_home: Path) -> None:
    """Test OAuth authorization without auto browser open."""
    with (
        patch("repository.OAuth1Session") as mock_oauth,
        patch("repository.webbrowser.open") as mock_browser,
        patch("builtins.input", return_value="verification_code"),
        patch("builtins.print"),
        patch("repository.sys.stdin.isatty", return_value=True),
    ):
        mock_oauth_instance = MagicMock()
        mock_oauth.return_value = mock_oauth_instance
        mock_oauth_instance.fetch_request_token.return_value = {
            "oauth_token": "request_token",
            "oauth_token_secret": "request_secret",
        }
        mock_oauth_instance.fetch_access_token.return_value = {
            "oauth_token": "access_token",
            "oauth_token_secret": "access_secret",
        }

        repo = ETradeRepository(
            consumer_key="test_key",
            consumer_secret="test_secret",
            environment="sandbox",
            auto_authorize=False,
        )

        repo.authorize()

        assert repo._is_authorized
        mock_browser.assert_not_called()


def test_authorize_request_token_failure(temp_config_home: Path) -> None:
    """Test OAuth authorization handles request token failure."""
    with (
        patch("repository.OAuth1Session") as mock_oauth,
        patch("builtins.print"),
        patch("repository.sys.stdin.isatty", return_value=True),
    ):
        mock_oauth_instance = MagicMock()
        mock_oauth.return_value = mock_oauth_instance
        mock_oauth_instance.fetch_request_token.side_effect = Exception(
            "Request token error"
        )

        repo = ETradeRepository(
            consumer_key="test_key",
            consumer_secret="test_secret",
            environment="sandbox",
        )

        with pytest.raises(Exception, match="Request token error"):
            repo.authorize()


def test_authorize_access_token_failure(temp_config_home: Path) -> None:
    """Test OAuth authorization handles access token failure."""
    with (
        patch("repository.OAuth1Session") as mock_oauth,
        patch("repository.webbrowser.open"),
        patch("builtins.input", return_value="verification_code"),
        patch("builtins.print"),
        patch("repository.sys.stdin.isatty", return_value=True),
    ):
        mock_oauth_instance = MagicMock()
        mock_oauth.return_value = mock_oauth_instance
        mock_oauth_instance.fetch_request_token.return_value = {
            "oauth_token": "request_token",
            "oauth_token_secret": "request_secret",
        }
        mock_oauth_instance.fetch_access_token.side_effect = Exception(
            "Access token error"
        )

        repo = ETradeRepository(
            consumer_key="test_key",
            consumer_secret="test_secret",
            environment="sandbox",
        )

        with pytest.raises(Exception, match="Access token error"):
            repo.authorize()


def test_authorize_with_cached_tokens(temp_config_home: Path) -> None:
    """Test authorization using cached tokens."""
    from datetime import datetime, timedelta

    repo = ETradeRepository(
        consumer_key="test_key",
        consumer_secret="test_secret",
        environment="sandbox",
        profile_id="test_profile",
    )

    # Save valid tokens
    expires_at = datetime.now(UTC) + timedelta(hours=1)
    repo._save_tokens("cached_token", "cached_secret", expires_at)

    # Authorize should use cached tokens
    with (
        patch("repository.OAuth1Session") as mock_oauth,
        patch("repository.webbrowser.open") as mock_browser,
        patch("builtins.input") as mock_input,
        patch("builtins.print"),
    ):
        repo.authorize()

        # OAuth1Session should be called once to create session with cached tokens
        mock_oauth.assert_called_once_with(
            "test_key",
            client_secret="test_secret",
            resource_owner_key="cached_token",
            resource_owner_secret="cached_secret",
        )
        # But fetch_request_token and fetch_access_token should NOT be called
        mock_oauth.return_value.fetch_request_token.assert_not_called()
        mock_oauth.return_value.fetch_access_token.assert_not_called()
        # And browser/input should not be used
        mock_browser.assert_not_called()
        mock_input.assert_not_called()
        assert repo._is_authorized


def test_authorize_with_expired_cached_tokens(temp_config_home: Path) -> None:
    """Test authorize when cached tokens exist but are expired."""
    from datetime import datetime, timedelta

    repo = ETradeRepository(
        consumer_key="test_key",
        consumer_secret="test_secret",
        environment="sandbox",
        profile_id="test",
    )

    # Save expired tokens
    expires_at = datetime.now(UTC) - timedelta(hours=1)
    repo._save_tokens("old_token", "old_secret", expires_at)

    # Now authorize - should trigger new OAuth flow
    with (
        patch("repository.OAuth1Session") as mock_oauth,
        patch("repository.webbrowser.open"),
        patch("builtins.input", return_value="new_code"),
        patch("builtins.print"),
        patch("repository.sys.stdin.isatty", return_value=True),
    ):
        mock_oauth_instance = MagicMock()
        mock_oauth.return_value = mock_oauth_instance
        mock_oauth_instance.fetch_request_token.return_value = {
            "oauth_token": "request_token",
            "oauth_token_secret": "request_secret",
        }
        mock_oauth_instance.fetch_access_token.return_value = {
            "oauth_token": "new_token",
            "oauth_token_secret": "new_secret",
        }

        repo.authorize()

        # Should have called fetch_request_token (new auth flow)
        mock_oauth_instance.fetch_request_token.assert_called_once()
        assert repo._is_authorized


def test_web_oauth_flow_success(temp_config_home: Path) -> None:
    """Test web-based OAuth flow with successful verification."""
    with (
        patch("repository.OAuth1Session") as mock_oauth,
        patch("repository.sys.stdin.isatty", return_value=False),
        patch("repository.run_web_oauth_flow", return_value="verification_code"),
        patch("builtins.print"),
    ):
        mock_oauth_instance = MagicMock()
        mock_oauth.return_value = mock_oauth_instance
        mock_oauth_instance.fetch_request_token.return_value = {
            "oauth_token": "request_token",
            "oauth_token_secret": "request_secret",
        }
        mock_oauth_instance.fetch_access_token.return_value = {
            "oauth_token": "access_token",
            "oauth_token_secret": "access_secret",
        }

        repo = ETradeRepository(
            consumer_key="test_key",
            consumer_secret="test_secret",
            environment="sandbox",
        )

        repo.authorize()

        assert repo._is_authorized
        mock_oauth_instance.fetch_access_token.assert_called_once()


def test_web_oauth_flow_timeout(temp_config_home: Path) -> None:
    """Test web OAuth flow timeout."""
    with (
        patch("repository.OAuth1Session") as mock_oauth,
        patch("repository.sys.stdin.isatty", return_value=False),
        patch("builtins.print"),
    ):
        mock_oauth_instance = MagicMock()
        mock_oauth.return_value = mock_oauth_instance
        mock_oauth_instance.fetch_request_token.return_value = {
            "oauth_token": "request_token",
            "oauth_token_secret": "request_secret",
        }

        repo = ETradeRepository(
            consumer_key="test_key",
            consumer_secret="test_secret",
            environment="sandbox",
        )

        # Patch _web_oauth_flow to raise a timeout error
        with patch.object(
            repo,
            "_web_oauth_flow",
            side_effect=TimeoutError("OAuth authorization timed out"),
        ):
            with pytest.raises(TimeoutError, match="OAuth authorization timed out"):
                repo.authorize()
