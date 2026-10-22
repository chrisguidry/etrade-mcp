"""
Test how a profile authorizes with E*TRADE and keeps its access token working.
"""

import sys
import threading
import time
from datetime import UTC, datetime, timedelta

import pytest
import requests
from conftest import FakeETrade, store_token

import tokens
from etrade_errors import ETradeError
from repository import REQUEST_TIMEOUT_SECONDS, ETradeRepository

RENEW = "/oauth/renew_access_token"


@pytest.mark.parametrize(
    ("environment", "base_url"),
    [
        ("sandbox", ETradeRepository.SANDBOX_BASE_URL),
        ("production", ETradeRepository.PRODUCTION_BASE_URL),
    ],
)
def test_each_environment_has_its_own_api(environment: str, base_url: str) -> None:
    repository = ETradeRepository("key", "secret", environment=environment)

    assert repository.base_url == base_url
    assert not repository.is_authorized


def test_an_unknown_environment_is_refused() -> None:
    with pytest.raises(ValueError, match="Invalid environment"):
        ETradeRepository("key", "secret", environment="invalid")


@pytest.fixture
def unauthorized(etrade: FakeETrade) -> FakeETrade:
    """E*TRADE, with no access token stored for profile 0."""
    tokens.forget_token("0")
    return etrade


@pytest.fixture
def terminal(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """A terminal where the user types the verification code.  Returns the URLs
    the server opens in the browser."""
    opened: list[str] = []
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda: " typed-code ")
    monkeypatch.setattr("repository.webbrowser.open", opened.append)
    return opened


def test_authorizing_from_a_stored_token(
    etrade: FakeETrade, repository: ETradeRepository
) -> None:
    repository.authorize()

    assert repository.is_authorized
    assert etrade.sessions == [
        {
            "client_secret": "test_consumer_secret",
            "resource_owner_key": "stored-token",
            "resource_owner_secret": "stored-secret",
        }
    ]


def test_authorizing_in_a_terminal(
    unauthorized: FakeETrade,
    repository: ETradeRepository,
    terminal: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository.authorize()

    assert repository.is_authorized
    assert terminal == [
        f"{ETradeRepository.AUTHORIZE_URL}?key=test_consumer_key&token=request-token"
    ]
    assert unauthorized.sessions[1]["verifier"] == "typed-code"
    stored = tokens.load_token("0", "sandbox")
    assert stored is not None
    assert (stored.token, stored.secret) == ("access-token", "access-secret")
    assert unauthorized.timeouts == [REQUEST_TIMEOUT_SECONDS] * 2

    output = capsys.readouterr()
    assert output.out == ""
    assert "E*TRADE AUTHORIZATION REQUIRED" in output.err


def test_authorizing_in_a_terminal_without_opening_a_browser(
    unauthorized: FakeETrade, terminal: list[str]
) -> None:
    repository = ETradeRepository("key", "secret", auto_authorize=False)

    repository.authorize()

    assert repository.is_authorized
    assert terminal == []


def test_authorizing_without_a_terminal_uses_the_web_page(
    unauthorized: FakeETrade,
    repository: ETradeRepository,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(
        "repository.run_web_oauth_flow", lambda url, timeout: "web-code"
    )

    repository.authorize()

    assert repository.is_authorized
    assert unauthorized.sessions[1]["verifier"] == "web-code"
    assert capsys.readouterr().out == ""


def test_an_expiring_stored_token_starts_authorization(
    etrade: FakeETrade, repository: ETradeRepository, terminal: list[str]
) -> None:
    store_token(expires_in=timedelta(minutes=10))

    repository.authorize()

    assert len(terminal) == 1
    assert repository.access_token is not None
    assert repository.access_token.token == "access-token"


def test_the_first_request_authorizes(
    etrade: FakeETrade, repository: ETradeRepository
) -> None:
    etrade.answer("/v1/accounts/list.json", {"ok": True})

    assert repository.get("/v1/accounts/list.json") == {"ok": True}
    assert repository.is_authorized
    assert etrade.timeouts == [REQUEST_TIMEOUT_SECONDS]


def expiring(repository: ETradeRepository) -> None:
    """Authorize the repository with a token that expires in ten minutes."""
    repository.authorize()
    assert repository.access_token is not None
    repository.access_token = repository.access_token._replace(
        expires_at=datetime.now(UTC) + timedelta(minutes=10)
    )


def test_a_request_renews_an_expiring_token(
    etrade: FakeETrade, repository: ETradeRepository
) -> None:
    expiring(repository)
    etrade.answer(RENEW)

    repository.ensure_authorized()

    assert etrade.requests == [(RENEW, {})]
    assert repository.access_token is not None
    assert tokens.load_token("0", "sandbox") == repository.access_token
    assert not tokens.needs_renewal(
        repository.access_token.expires_at, datetime.now(UTC)
    )


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, None),
        (200, requests.ConnectionError("E*TRADE is down")),
    ],
)
def test_a_token_that_does_not_renew_is_authorized_again(
    etrade: FakeETrade,
    repository: ETradeRepository,
    terminal: list[str],
    status: int,
    error: requests.RequestException | None,
) -> None:
    expiring(repository)
    etrade.answer(RENEW, status=status, error=error)

    repository.ensure_authorized()

    assert len(terminal) == 1
    assert repository.access_token is not None
    assert repository.access_token.token == "access-token"


def test_a_rejected_token_is_forgotten(
    etrade: FakeETrade, repository: ETradeRepository
) -> None:
    etrade.answer("/v1/accounts/list.json", status=401)

    with pytest.raises(ETradeError, match="did not accept"):
        repository.get("/v1/accounts/list.json")

    assert not repository.is_authorized
    assert tokens.load_token("0", "sandbox") is None


def test_concurrent_requests_authorize_once(
    unauthorized: FakeETrade,
    repository: ETradeRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flows: list[str] = []

    def slow_web_flow(url: str, timeout: int) -> str:
        flows.append(url)
        time.sleep(0.1)
        return "web-code"

    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr("repository.run_web_oauth_flow", slow_web_flow)

    threads = [threading.Thread(target=repository.ensure_authorized) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert len(flows) == 1
    assert repository.is_authorized
