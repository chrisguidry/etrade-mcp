"""
Test configuring profiles from the environment and listing them.
"""

import pytest
from fastmcp.client import Client, FastMCPTransport

from profiles import create_repositories_from_env, create_repository_from_env


def set_environment(monkeypatch: pytest.MonkeyPatch, variables: dict[str, str]) -> None:
    """Replace every E*TRADE variable in the environment with these."""
    for name in ["ETRADE_CONSUMER_KEY", "ETRADE_CONSUMER_SECRET", "ETRADE_ENVIRONMENT"]:
        monkeypatch.delenv(name, raising=False)
    for name, value in variables.items():
        monkeypatch.setenv(name, value)


def test_create_repository_from_legacy_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_environment(
        monkeypatch,
        {
            "ETRADE_CONSUMER_KEY": "legacy_key",
            "ETRADE_CONSUMER_SECRET": "legacy_secret",
            "ETRADE_ENVIRONMENT": "production",
        },
    )

    repository = create_repository_from_env()

    assert repository.consumer_key == "legacy_key"
    assert repository.consumer_secret == "legacy_secret"
    assert repository.environment == "production"


def test_create_repository_defaults_to_the_sandbox(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_environment(
        monkeypatch,
        {"ETRADE_3_CONSUMER_KEY": "key3", "ETRADE_3_CONSUMER_SECRET": "secret3"},
    )

    assert create_repository_from_env("3").environment == "sandbox"


@pytest.mark.parametrize(
    ("variables", "missing"),
    [
        ({}, "ETRADE_0_CONSUMER_KEY"),
        ({"ETRADE_CONSUMER_KEY": "key"}, "ETRADE_0_CONSUMER_SECRET"),
    ],
)
def test_create_repository_requires_a_key_and_secret(
    monkeypatch: pytest.MonkeyPatch, variables: dict[str, str], missing: str
) -> None:
    set_environment(monkeypatch, variables)

    with pytest.raises(ValueError, match=missing):
        create_repository_from_env()


def test_create_repositories_for_every_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_environment(
        monkeypatch,
        {
            "ETRADE_0_CONSUMER_KEY": "key0",
            "ETRADE_0_CONSUMER_SECRET": "secret0",
            "ETRADE_0_ENVIRONMENT": "sandbox",
            "ETRADE_2_CONSUMER_KEY": "key2",
            "ETRADE_2_CONSUMER_SECRET": "secret2",
            "ETRADE_2_ENVIRONMENT": "production",
            "ETRADE_2_LABEL": "Child 2",
        },
    )

    repositories = create_repositories_from_env()

    assert sorted(repositories) == ["0", "2"]
    assert repositories["0"].consumer_key == "key0"
    assert repositories["2"].environment == "production"
    assert repositories["2"].profile_label == "Child 2"


def test_numbered_variables_take_precedence_over_legacy_ones(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_environment(
        monkeypatch,
        {
            "ETRADE_0_CONSUMER_KEY": "key0",
            "ETRADE_0_CONSUMER_SECRET": "secret0",
            "ETRADE_CONSUMER_KEY": "legacy_key",
            "ETRADE_CONSUMER_SECRET": "legacy_secret",
        },
    )

    repositories = create_repositories_from_env()

    assert list(repositories) == ["0"]
    assert repositories["0"].consumer_key == "key0"


def test_create_repositories_requires_a_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_environment(monkeypatch, {})

    with pytest.raises(ValueError, match="No E\\*TRADE profiles found"):
        create_repositories_from_env()


async def test_list_profiles(
    monkeypatch: pytest.MonkeyPatch, mcp_client: Client[FastMCPTransport]
) -> None:
    set_environment(
        monkeypatch,
        {
            "ETRADE_0_CONSUMER_KEY": "key0",
            "ETRADE_0_CONSUMER_SECRET": "secret0",
            "ETRADE_1_CONSUMER_KEY": "key1",
            "ETRADE_1_CONSUMER_SECRET": "secret1",
            "ETRADE_1_ENVIRONMENT": "production",
            "ETRADE_1_LABEL": "Spouse",
        },
    )

    result = await mcp_client.call_tool("list_profiles", {})

    assert result.structured_content == {
        "profiles": [
            {"profile_id": "0", "profile_label": None, "environment": "sandbox"},
            {"profile_id": "1", "profile_label": "Spouse", "environment": "production"},
        ]
    }
