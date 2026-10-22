"""
Test fixtures for the E*TRADE MCP server.

Tests run the real server, repositories, and token storage against FakeETrade,
which answers requests the way E*TRADE's API does, from JSON each test gives it.
"""

from __future__ import annotations

import json
import sys
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import fastmcp
import pytest
import requests
from fastmcp.client import Client, FastMCPTransport

sys.path.insert(0, str(Path(__file__).parent.parent))

import server
import tokens
from repository import ETradeRepository
from tokens import AccessToken


@pytest.fixture(autouse=True)
def temp_config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Keep every test's token file out of the user's real config directory."""
    config_home = tmp_path / "config"
    config_home.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    return config_home


def etrade_response(body: Any, status: int = 200) -> requests.Response:
    """A real requests Response with a JSON body, as E*TRADE sends it.  A 204
    No Content response has an empty body."""
    response = requests.Response()
    response.status_code = status
    response.reason = HTTPStatus(status).phrase
    no_content = status == HTTPStatus.NO_CONTENT
    response._content = b"" if no_content else json.dumps(body).encode()
    return response


type Answer = requests.Response | requests.RequestException


class FakeETrade:
    """E*TRADE's API, in place of the OAuth1Session the repository signs with.

    It answers a GET for an endpoint path with the response a test gave it, and
    with a 404 for any other path.  An answer given with params applies only to
    a request with those params.
    """

    def __init__(self) -> None:
        self.answers: dict[tuple[str, frozenset[tuple[str, str]]], Answer] = {}
        self.requests: list[tuple[str, dict[str, str]]] = []
        self.timeouts: list[float | None] = []
        self.sessions: list[dict[str, Any]] = []

    def answer(
        self,
        endpoint: str,
        body: Any = None,
        status: int = 200,
        params: dict[str, str] | None = None,
        error: requests.RequestException | None = None,
    ) -> None:
        answer = error or etrade_response(body if body is not None else {}, status)
        self.answers[(endpoint, frozenset((params or {}).items()))] = answer

    def __call__(self, consumer_key: str, **kwargs: Any) -> FakeETrade:
        """Open a session, as OAuth1Session(...) does."""
        self.sessions.append(kwargs)
        return self

    def get(
        self,
        url: str,
        params: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> requests.Response:
        path = urlsplit(url).path
        params = params or {}
        self.requests.append((path, params))
        self.timeouts.append(timeout)
        not_found = etrade_response(
            {"Error": {"code": 0, "message": f"FakeETrade has no {path}"}}, 404
        )
        answer = self.answers.get(
            (path, frozenset(params.items())),
            self.answers.get((path, frozenset()), not_found),
        )
        if isinstance(answer, requests.RequestException):
            raise answer
        return answer

    def fetch_request_token(
        self, url: str, timeout: float | None = None
    ) -> dict[str, str]:
        self.timeouts.append(timeout)
        return {"oauth_token": "request-token", "oauth_token_secret": "request-secret"}

    def fetch_access_token(
        self, url: str, timeout: float | None = None
    ) -> dict[str, str]:
        self.timeouts.append(timeout)
        return {"oauth_token": "access-token", "oauth_token_secret": "access-secret"}


def store_token(
    profile_id: str = "0",
    environment: str = "sandbox",
    expires_in: timedelta = timedelta(hours=2),
) -> AccessToken:
    """Store an access token for a profile, as a past authorization would."""
    access_token = AccessToken(
        "stored-token", "stored-secret", datetime.now(UTC) + expires_in
    )
    tokens.save_token(profile_id, environment, access_token)
    return access_token


@pytest.fixture
def etrade(monkeypatch: pytest.MonkeyPatch) -> FakeETrade:
    """E*TRADE, with profile 0 already authorized in the sandbox."""
    fake = FakeETrade()
    monkeypatch.setattr("repository.OAuth1Session", fake)
    store_token()
    return fake


@pytest.fixture
def repository(etrade: FakeETrade) -> ETradeRepository:
    """Profile 0's repository, talking to FakeETrade."""
    return ETradeRepository(
        consumer_key="test_consumer_key",
        consumer_secret="test_consumer_secret",
        environment="sandbox",
        profile_id="0",
    )


@pytest.fixture
async def mcp_client(
    etrade: FakeETrade,
) -> AsyncGenerator[Client[FastMCPTransport], None]:
    """An MCP client connected in memory to the server, which uses FakeETrade."""
    async with fastmcp.Client(server.mcp) as client:
        yield client


def account_json(
    account_id_key: str = "abc123xyz",
    status: str = "ACTIVE",
    institution_type: str = "BROKERAGE",
) -> dict[str, Any]:
    """One account from E*TRADE's account list."""
    return {
        "accountId": "12345678",
        "accountIdKey": account_id_key,
        "accountMode": "MARGIN",
        "accountDesc": "Brokerage",
        "accountName": "Long-term",
        "accountType": "INDIVIDUAL",
        "institutionType": institution_type,
        "accountStatus": status,
    }


def account_list(*accounts: dict[str, Any]) -> dict[str, Any]:
    """E*TRADE's account list response.  One account arrives as a bare object."""
    listed: Any = accounts[0] if len(accounts) == 1 else list(accounts)
    return {"AccountListResponse": {"Accounts": {"Account": listed}}}
