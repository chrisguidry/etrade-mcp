"""
Pytest configuration and shared fixtures for E*TRADE repository tests.
"""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from repository import ETradeRepository


@pytest.fixture
def mock_oauth_session() -> MagicMock:
    """Mock OAuth session for testing."""
    session = MagicMock()
    session.get.return_value.status_code = 200
    session.get.return_value.raise_for_status.return_value = None
    return session


@pytest.fixture
def temp_config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set XDG_CONFIG_HOME to a temporary directory for testing."""
    config_home = tmp_path / "config"
    config_home.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    return config_home


@pytest.fixture
def repository(
    mock_oauth_session: MagicMock, temp_config_home: Path
) -> ETradeRepository:
    """Create a repository with mocked OAuth session."""
    repo = ETradeRepository(
        consumer_key="test_key",
        consumer_secret="test_secret",
        environment="sandbox",
        auto_authorize=False,
    )
    repo.session = mock_oauth_session
    repo._is_authorized = True
    # Set token expiration far in the future to avoid renewal during tests
    repo._token_expires_at = datetime.now(UTC) + timedelta(hours=24)
    repo._last_activity = datetime.now(UTC)
    return repo
