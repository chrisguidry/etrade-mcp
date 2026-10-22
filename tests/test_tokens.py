"""
Test storing access tokens between runs, and when they expire.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import tokens
from tokens import AccessToken

NOW = datetime(2026, 10, 22, 14, 0, tzinfo=UTC)


def a_token(expires_at: datetime = NOW) -> AccessToken:
    return AccessToken("token", "secret", expires_at)


def test_a_saved_token_loads_back() -> None:
    tokens.save_token("0", "sandbox", a_token())

    assert tokens.load_token("0", "sandbox") == a_token()


def test_the_tokens_file_is_readable_only_by_the_user(
    temp_config_home: Path,
) -> None:
    tokens.save_token("0", "sandbox", a_token())

    path = temp_config_home / "etrade-mcp" / "tokens.json"
    assert oct(path.stat().st_mode)[-3:] == "600"


def test_saving_a_token_keeps_the_other_profiles_tokens() -> None:
    tokens.save_token("0", "sandbox", a_token())
    tokens.save_token("1", "production", a_token(NOW + timedelta(hours=1)))

    assert tokens.load_token("0", "sandbox") == a_token()
    assert tokens.load_token("1", "production") == a_token(NOW + timedelta(hours=1))


@pytest.mark.parametrize(
    ("profile_id", "environment"),
    [("1", "sandbox"), ("0", "production")],
)
def test_no_token_loads_for_another_profile_or_environment(
    profile_id: str, environment: str
) -> None:
    tokens.save_token("0", "sandbox", a_token())

    assert tokens.load_token(profile_id, environment) is None


def test_no_token_loads_without_a_tokens_file() -> None:
    assert tokens.load_token("0", "sandbox") is None


def test_no_token_loads_from_an_incomplete_entry() -> None:
    tokens.tokens_file().write_text(
        json.dumps({"0": {"environment": "sandbox", "expires_at": NOW.isoformat()}})
    )

    assert tokens.load_token("0", "sandbox") is None


def test_forgetting_a_token_keeps_the_other_profiles_tokens() -> None:
    tokens.save_token("0", "sandbox", a_token())
    tokens.save_token("1", "sandbox", a_token())

    tokens.forget_token("0")

    assert tokens.load_token("0", "sandbox") is None
    assert tokens.load_token("1", "sandbox") == a_token()


def test_forgetting_a_token_without_a_tokens_file() -> None:
    tokens.forget_token("0")

    assert not tokens.tokens_file().exists()


def test_config_directory_without_xdg_config_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME")
    monkeypatch.setenv("HOME", str(tmp_path))

    assert tokens.config_directory() == tmp_path / ".config" / "etrade-mcp"


@pytest.mark.parametrize(
    ("now", "expiry"),
    [
        # Two hours of inactivity comes first.
        (NOW, NOW + timedelta(hours=2)),
        # Midnight Eastern, taken as 04:00 UTC, comes first.
        (
            datetime(2026, 10, 23, 3, 0, tzinfo=UTC),
            datetime(2026, 10, 23, 4, 0, tzinfo=UTC),
        ),
    ],
)
def test_next_expiry(now: datetime, expiry: datetime) -> None:
    assert tokens.next_expiry(now) == expiry


@pytest.mark.parametrize(
    ("expires_at", "renew"),
    [
        (None, True),
        (NOW + timedelta(hours=1), False),
        (NOW + timedelta(minutes=20), True),
        (NOW - timedelta(hours=1), True),
    ],
)
def test_needs_renewal(expires_at: datetime | None, renew: bool) -> None:
    assert tokens.needs_renewal(expires_at, NOW) is renew
