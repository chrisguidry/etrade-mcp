"""Tests for E*TRADE repository initialization and configuration."""

from pathlib import Path
from unittest.mock import patch

import pytest

from repository import ETradeRepository, create_repository_from_env


def test_repository_initialization() -> None:
    """Test basic repository initialization."""
    repo = ETradeRepository(
        consumer_key="test_key",
        consumer_secret="test_secret",
        environment="sandbox",
    )

    assert repo.consumer_key == "test_key"
    assert repo.consumer_secret == "test_secret"
    assert repo.environment == "sandbox"
    assert repo.base_url == ETradeRepository.SANDBOX_BASE_URL
    assert not repo._is_authorized


def test_repository_production_url() -> None:
    """Test repository uses production URL for production environment."""
    repo = ETradeRepository(
        consumer_key="test_key",
        consumer_secret="test_secret",
        environment="production",
    )

    assert repo.base_url == ETradeRepository.PRODUCTION_BASE_URL


def test_repository_invalid_environment() -> None:
    """Test repository raises error for invalid environment."""
    with pytest.raises(ValueError, match="Invalid environment"):
        ETradeRepository(
            consumer_key="test_key",
            consumer_secret="test_secret",
            environment="invalid",
        )


@patch.dict(
    "os.environ",
    {
        "ETRADE_CONSUMER_KEY": "test_key",
        "ETRADE_CONSUMER_SECRET": "test_secret",
        "ETRADE_ENVIRONMENT": "production",
    },
)
def test_create_repository_from_env() -> None:
    """Test creating repository from environment variables."""
    repo = create_repository_from_env()

    assert repo.consumer_key == "test_key"
    assert repo.consumer_secret == "test_secret"
    assert repo.environment == "production"


@patch.dict("os.environ", {}, clear=True)
def test_create_repository_from_env_missing_key() -> None:
    """Test creating repository fails when consumer key is missing."""
    with pytest.raises(ValueError, match="ETRADE_0_CONSUMER_KEY"):
        create_repository_from_env()


@patch.dict("os.environ", {"ETRADE_CONSUMER_KEY": "test_key"}, clear=True)
def test_create_repository_from_env_missing_secret() -> None:
    """Test creating repository fails when consumer secret is missing."""
    with pytest.raises(ValueError, match="ETRADE_0_CONSUMER_SECRET"):
        create_repository_from_env()


@patch.dict(
    "os.environ",
    {
        "ETRADE_0_CONSUMER_KEY": "key0",
        "ETRADE_0_CONSUMER_SECRET": "secret0",
        "ETRADE_0_ENVIRONMENT": "sandbox",
        "ETRADE_1_CONSUMER_KEY": "key1",
        "ETRADE_1_CONSUMER_SECRET": "secret1",
        "ETRADE_1_ENVIRONMENT": "production",
        "ETRADE_1_LABEL": "Child 1",
    },
)
def test_create_repositories_from_env() -> None:
    """Test creating multiple repositories from environment variables."""
    from repository import create_repositories_from_env

    repos = create_repositories_from_env()

    assert len(repos) == 2
    assert "0" in repos
    assert "1" in repos
    assert repos["0"].consumer_key == "key0"
    assert repos["0"].environment == "sandbox"
    assert repos["1"].consumer_key == "key1"
    assert repos["1"].environment == "production"
    assert repos["1"].profile_label == "Child 1"


@patch.dict(
    "os.environ",
    {
        "ETRADE_0_CONSUMER_KEY": "key0",
        "ETRADE_0_CONSUMER_SECRET": "secret0",
        "ETRADE_CONSUMER_KEY": "legacy_key",
        "ETRADE_CONSUMER_SECRET": "legacy_secret",
    },
)
def test_create_repositories_from_env_with_legacy() -> None:
    """Test that legacy ETRADE_* vars work for profile 0."""
    from repository import create_repositories_from_env

    repos = create_repositories_from_env()

    assert len(repos) == 1
    assert "0" in repos
    # ETRADE_0_* should take precedence over legacy ETRADE_*
    assert repos["0"].consumer_key == "key0"


@patch.dict("os.environ", {}, clear=True)
def test_create_repositories_from_env_no_profiles() -> None:
    """Test error when no profiles are configured."""
    from repository import create_repositories_from_env

    with pytest.raises(ValueError, match="No E\\*TRADE profiles found"):
        create_repositories_from_env()


@patch.dict(
    "os.environ",
    {
        "ETRADE_0_CONSUMER_KEY": "key0",
        "ETRADE_0_CONSUMER_SECRET": "secret0",
        "ETRADE_2_CONSUMER_KEY": "key2",
        "ETRADE_2_CONSUMER_SECRET": "secret2",
    },
)
def test_create_repositories_from_env_with_gaps() -> None:
    """Test that non-sequential profile IDs are supported."""
    from repository import create_repositories_from_env

    repos = create_repositories_from_env()

    # Should get both profiles even with gap
    assert len(repos) == 2
    assert "0" in repos
    assert "2" in repos


def test_get_config_dir_no_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test _get_config_dir when XDG_CONFIG_HOME is not set."""
    # Unset XDG_CONFIG_HOME
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

    # Patch Path.home() to return our temp path
    with patch("repository.Path.home", return_value=tmp_path):
        config_dir = ETradeRepository._get_config_dir()
        assert config_dir == tmp_path / ".config" / "etrade-mcp"
