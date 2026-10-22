"""
E*TRADE API client with OAuth 1.0 authentication.

Each profile has its own repository, which authorizes with E*TRADE, keeps the
profile's access token renewed, and makes the profile's API requests.
"""

import logging
import sys
import threading
import webbrowser
from datetime import UTC, datetime
from typing import Any

import requests
from requests_oauthlib import OAuth1Session

import tokens
from etrade_errors import ETradeError
from oauth_web_server import run_web_oauth_flow
from tokens import AccessToken

logger = logging.getLogger(__name__)

# Every request to E*TRADE waits at most this long, so that a stuck request
# fails the tool call instead of hanging the client.
REQUEST_TIMEOUT_SECONDS = 30

# Tools run in worker threads, so two calls can need authorization at once.
# The browser flow keeps its state in one class, and E*TRADE issues one
# request token per flow, so only one authorization runs at a time.
_authorization_lock = threading.Lock()


class ETradeRepository:
    """Client for E*TRADE API with OAuth 1.0 authentication."""

    # OAuth endpoints
    REQUEST_TOKEN_URL = "https://api.etrade.com/oauth/request_token"
    AUTHORIZE_URL = "https://us.etrade.com/e/t/etws/authorize"
    ACCESS_TOKEN_URL = "https://api.etrade.com/oauth/access_token"
    RENEW_TOKEN_URL = "https://api.etrade.com/oauth/renew_access_token"

    # API base URLs
    SANDBOX_BASE_URL = "https://apisb.etrade.com"
    PRODUCTION_BASE_URL = "https://api.etrade.com"

    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        environment: str = "sandbox",
        auto_authorize: bool = True,
        profile_id: str = "0",
        profile_label: str | None = None,
    ):
        """Initialize E*TRADE client.

        Args:
            consumer_key: E*TRADE consumer key from developer portal
            consumer_secret: E*TRADE consumer secret from developer portal
            environment: 'sandbox' or 'production' (default: 'sandbox')
            auto_authorize: Whether to open the browser for terminal authorization
            profile_id: Unique identifier for this profile (default: '0')
            profile_label: Human-readable label for this profile
        """
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.environment = environment
        self.auto_authorize = auto_authorize
        self.profile_id = profile_id
        self.profile_label = profile_label

        if environment == "sandbox":
            self.base_url = self.SANDBOX_BASE_URL
        elif environment == "production":
            self.base_url = self.PRODUCTION_BASE_URL
        else:
            raise ValueError(f"Invalid environment: {environment}")

        self.session: OAuth1Session | None = None
        self.access_token: AccessToken | None = None

    @property
    def is_authorized(self) -> bool:
        """Whether this profile has an access token to sign requests with."""
        return self.session is not None and self.access_token is not None

    def _use_token(self, access_token: AccessToken) -> None:
        """Sign every request from now on with this access token."""
        self.access_token = access_token
        self.session = OAuth1Session(
            self.consumer_key,
            client_secret=self.consumer_secret,
            resource_owner_key=access_token.token,
            resource_owner_secret=access_token.secret,
        )

    def _forget_token(self) -> None:
        """Drop the access token, here and on disk, so the next call authorizes."""
        self.session = None
        self.access_token = None
        tokens.forget_token(self.profile_id)

    def _renew_token(self) -> None:
        """Renew the access token without the user, before E*TRADE deactivates it.

        Renewal extends the token E*TRADE already issued, so only its expiry
        changes.
        """
        assert self.session is not None and self.access_token is not None

        logger.info(f"Renewing tokens for profile {self.profile_id}")
        response = self.session.get(
            self.RENEW_TOKEN_URL, timeout=REQUEST_TIMEOUT_SECONDS
        )
        response.raise_for_status()

        renewed = self.access_token._replace(
            expires_at=tokens.next_expiry(datetime.now(UTC))
        )
        self.access_token = renewed
        tokens.save_token(self.profile_id, self.environment, renewed)
        logger.info(f"Successfully renewed tokens for profile {self.profile_id}")

    def authorize(self) -> None:
        """Authorize with E*TRADE, from the stored token if it is still good.

        Otherwise this runs E*TRADE's OAuth flow: it gets a request token, sends
        the user to E*TRADE to approve it, reads the verification code, and
        exchanges it for an access token, which it stores for the next run.  In
        a terminal, the user types the code; anywhere else, such as under an MCP
        client, a local web page in the browser asks for it.

        Prompts go to stderr, because an MCP server's stdout carries the
        protocol.
        """
        logger.info(f"Authorizing E*TRADE session for profile {self.profile_id}")

        stored = tokens.load_token(self.profile_id, self.environment)
        if stored:
            if not tokens.needs_renewal(stored.expires_at, datetime.now(UTC)):
                logger.info("Using persisted tokens (still valid)")
                self._use_token(stored)
                return
            logger.info("Persisted tokens expired, starting interactive authorization")

        logger.info("Starting E*TRADE OAuth authorization flow")

        oauth = OAuth1Session(
            self.consumer_key,
            client_secret=self.consumer_secret,
            callback_uri="oob",
        )
        request_token = oauth.fetch_request_token(
            self.REQUEST_TOKEN_URL, timeout=REQUEST_TIMEOUT_SECONDS
        )
        resource_owner_key = request_token.get("oauth_token")
        resource_owner_secret = request_token.get("oauth_token_secret")
        logger.info("Received request token")

        authorization_url = (
            f"{self.AUTHORIZE_URL}?key={self.consumer_key}&token={resource_owner_key}"
        )

        if sys.stdin.isatty():
            print("\n" + "=" * 70, file=sys.stderr)
            print("E*TRADE AUTHORIZATION REQUIRED", file=sys.stderr)
            print("=" * 70, file=sys.stderr)
            print("\nPlease authorize this application:  ", file=sys.stderr)
            print(f"\n  {authorization_url}\n", file=sys.stderr)

            if self.auto_authorize:
                print("Opening browser...", file=sys.stderr)
                webbrowser.open(authorization_url)
            else:
                print("Please visit the URL above in your browser.", file=sys.stderr)

            print(
                "\nAfter authorizing, you will receive a verification code.",
                file=sys.stderr,
            )
            print("Enter verification code: ", end="", file=sys.stderr, flush=True)
            verification_code = input().strip()
        else:
            logger.info(
                "Non-interactive environment detected, using web-based OAuth flow"
            )
            verification_code = run_web_oauth_flow(authorization_url, timeout=300)

        oauth = OAuth1Session(
            self.consumer_key,
            client_secret=self.consumer_secret,
            resource_owner_key=resource_owner_key,
            resource_owner_secret=resource_owner_secret,
            verifier=verification_code,
        )
        access_token = oauth.fetch_access_token(
            self.ACCESS_TOKEN_URL, timeout=REQUEST_TIMEOUT_SECONDS
        )

        authorized = AccessToken(
            access_token.get("oauth_token", ""),
            access_token.get("oauth_token_secret", ""),
            tokens.next_expiry(datetime.now(UTC)),
        )
        self._use_token(authorized)
        tokens.save_token(self.profile_id, self.environment, authorized)

        logger.info(
            f"Successfully authorized E*TRADE session for profile {self.profile_id}"
        )

    def ensure_authorized(self) -> None:
        """Authorize this profile, or renew its token, if a request needs it.

        A token that E*TRADE will not renew has expired at midnight Eastern
        time, so the profile goes through authorization again.
        """
        with _authorization_lock:
            if not self.is_authorized:
                self.authorize()
                return

            assert self.access_token is not None
            if not tokens.needs_renewal(
                self.access_token.expires_at, datetime.now(UTC)
            ):
                return

            try:
                self._renew_token()
            except requests.RequestException as error:
                logger.warning(f"Token renewal failed, authorizing again: {error}")
                self._forget_token()
                self.authorize()

    def get(self, endpoint: str, params: dict[str, str] | None = None) -> Any:
        """Make a GET request to E*TRADE API.

        Args:
            endpoint: API endpoint path (e.g., '/v1/accounts/list.json')
            params: Optional query parameters

        Returns:
            The response's JSON, or an empty dict when the response has no body

        Raises:
            ETradeError: E*TRADE refused the request or did not answer
        """
        self.ensure_authorized()
        assert self.session is not None

        url = f"{self.base_url}{endpoint}"
        logger.debug(f"GET {endpoint}")

        try:
            response = self.session.get(
                url, params=params, timeout=REQUEST_TIMEOUT_SECONDS
            )
        except requests.Timeout as error:
            raise ETradeError(
                f"E*TRADE did not answer within {REQUEST_TIMEOUT_SECONDS} seconds. "
                "Try again."
            ) from error
        except requests.ConnectionError as error:
            raise ETradeError("Could not connect to E*TRADE. Try again.") from error

        if response.status_code == 401:
            self._forget_token()
        if not response.ok:
            raise ETradeError.from_response(response)

        # E*TRADE answers a search with no results, such as a date range with
        # no transactions, with 204 No Content and an empty body.
        if not response.content:
            return {}
        return response.json()
