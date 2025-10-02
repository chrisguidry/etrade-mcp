"""
E*TRADE API client with OAuth 1.0 authentication.

Handles OAuth flow and provides methods for accessing E*TRADE API endpoints.
"""

import json
import logging
import os
import sys
import webbrowser
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from requests_oauthlib import OAuth1Session

from models import Account, Balance, Portfolio, Position, Quote
from oauth_web_server import run_web_oauth_flow

logger = logging.getLogger(__name__)


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
            auto_authorize: Whether to automatically open browser for authorization
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
        self._is_authorized = False
        self._token_expires_at: datetime | None = None
        self._last_activity: datetime | None = None

    @staticmethod
    def _get_config_dir() -> Path:
        """Get the config directory for storing tokens."""
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            config_dir = Path(xdg_config) / "etrade-mcp"
        else:
            config_dir = Path.home() / ".config" / "etrade-mcp"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir

    @staticmethod
    def _get_tokens_file() -> Path:
        """Get the path to the tokens file."""
        return ETradeRepository._get_config_dir() / "tokens.json"

    def _save_tokens(
        self, oauth_token: str, oauth_token_secret: str, expires_at: datetime
    ) -> None:
        """Save OAuth tokens to disk.

        Args:
            oauth_token: OAuth access token
            oauth_token_secret: OAuth access token secret
            expires_at: Token expiration timestamp
        """
        tokens_file = self._get_tokens_file()

        # Load existing tokens
        if tokens_file.exists():
            with open(tokens_file) as f:
                all_tokens = json.load(f)
        else:
            all_tokens = {}

        # Update tokens for this profile
        all_tokens[self.profile_id] = {
            "oauth_token": oauth_token,
            "oauth_token_secret": oauth_token_secret,
            "expires_at": expires_at.isoformat(),
            "environment": self.environment,
        }

        # Write tokens with secure permissions
        tokens_file.touch(mode=0o600, exist_ok=True)
        with open(tokens_file, "w") as f:
            json.dump(all_tokens, f, indent=2)

        logger.info(f"Saved tokens for profile {self.profile_id}")

    def _load_tokens(self) -> tuple[str, str, datetime] | None:
        """Load OAuth tokens from disk.

        Returns:
            Tuple of (oauth_token, oauth_token_secret, expires_at) or None if not found
        """
        tokens_file = self._get_tokens_file()

        if not tokens_file.exists():
            return None

        with open(tokens_file) as f:
            all_tokens = json.load(f)

        profile_tokens = all_tokens.get(self.profile_id)
        if not profile_tokens:
            return None

        # Verify environment matches
        if profile_tokens.get("environment") != self.environment:
            logger.warning(
                f"Token environment mismatch for profile {self.profile_id}: "
                f"expected {self.environment}, got {profile_tokens.get('environment')}"
            )
            return None

        oauth_token = profile_tokens.get("oauth_token")
        oauth_token_secret = profile_tokens.get("oauth_token_secret")
        expires_at_str = profile_tokens.get("expires_at")

        if not oauth_token or not oauth_token_secret or not expires_at_str:
            return None

        expires_at = datetime.fromisoformat(expires_at_str)
        logger.info(f"Loaded tokens for profile {self.profile_id}")
        return oauth_token, oauth_token_secret, expires_at

    @staticmethod
    def _calculate_token_expiry() -> datetime:
        """Calculate when the current token will expire.

        E*TRADE tokens expire at midnight US Eastern time.
        Also track 2-hour inactivity timeout.

        Returns:
            Expiration timestamp (whichever comes first: midnight ET or 2hr inactivity)
        """
        now = datetime.now(UTC)

        # Calculate midnight Eastern Time
        # ET is UTC-5 (EST) or UTC-4 (EDT)
        # For simplicity, we'll use a conservative approach: next midnight UTC-4
        # This means we might renew slightly early during EST, but that's safe
        eastern_offset = timedelta(hours=-4)
        now_eastern = now + eastern_offset

        # Next midnight Eastern
        next_midnight_eastern = (now_eastern + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        midnight_utc = next_midnight_eastern - eastern_offset

        # 2 hour inactivity timeout
        two_hour_timeout = now + timedelta(hours=2)

        # Return whichever comes first
        return min(midnight_utc, two_hour_timeout)

    def _is_token_expired(self) -> bool:
        """Check if the token is expired or will expire soon.

        Returns:
            True if token needs renewal
        """
        if self._token_expires_at is None:
            return True

        # Renew if within 30 minutes of expiration
        now = datetime.now(UTC)
        return now >= (self._token_expires_at - timedelta(minutes=30))

    def _renew_tokens(self) -> None:
        """Renew OAuth access tokens without user interaction."""
        if not self.session:
            raise RuntimeError("Cannot renew tokens: no active session")

        logger.info(f"Renewing tokens for profile {self.profile_id}")

        try:
            response = self.session.get(self.RENEW_TOKEN_URL)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to renew tokens: {e}")
            raise

        # Parse response to get new token info
        # The renew endpoint doesn't change the tokens, just extends their validity
        # We just need to update the expiration time
        self._token_expires_at = self._calculate_token_expiry()
        self._last_activity = datetime.now(UTC)

        # Save updated expiration
        if (
            self.session._client.client.resource_owner_key
            and self.session._client.client.resource_owner_secret
        ):
            self._save_tokens(
                self.session._client.client.resource_owner_key,
                self.session._client.client.resource_owner_secret,
                self._token_expires_at,
            )

        logger.info(f"Successfully renewed tokens for profile {self.profile_id}")

    def authorize(self) -> None:
        """Perform OAuth 1.0 authorization flow.

        This will:
        1. Try to load persisted tokens
        2. If valid tokens exist, use them
        3. Otherwise, perform interactive OAuth flow:
           a. Get a request token
           b. Open browser for user to authorize (if auto_authorize=True)
           c. Prompt for verification code
           d. Exchange for access token
        4. Save tokens to disk
        """
        logger.info(f"Authorizing E*TRADE session for profile {self.profile_id}")

        # Try to load existing tokens
        token_data = self._load_tokens()
        if token_data:
            oauth_token, oauth_token_secret, expires_at = token_data

            # Check if token is still valid
            self._token_expires_at = expires_at
            if not self._is_token_expired():
                logger.info("Using persisted tokens (still valid)")
                self.session = OAuth1Session(
                    self.consumer_key,
                    client_secret=self.consumer_secret,
                    resource_owner_key=oauth_token,
                    resource_owner_secret=oauth_token_secret,
                )
                self._is_authorized = True
                self._last_activity = datetime.now(UTC)
                return

            logger.info("Persisted tokens expired, starting interactive authorization")

        # No valid tokens, start interactive OAuth flow
        logger.info("Starting E*TRADE OAuth authorization flow")

        # Step 1: Get request token
        oauth = OAuth1Session(
            self.consumer_key,
            client_secret=self.consumer_secret,
            callback_uri="oob",
        )

        try:
            request_token_response = oauth.fetch_request_token(self.REQUEST_TOKEN_URL)
        except Exception as e:
            logger.error(f"Failed to get request token: {e}")
            raise

        resource_owner_key = request_token_response.get("oauth_token")
        resource_owner_secret = request_token_response.get("oauth_token_secret")

        logger.info("Received request token")

        # Step 2: Direct user to authorization URL
        authorization_url = (
            f"{self.AUTHORIZE_URL}?key={self.consumer_key}&token={resource_owner_key}"
        )

        # Check if we're in an interactive terminal
        is_interactive = sys.stdin.isatty()

        if is_interactive:
            # Traditional terminal-based flow
            print("\n" + "=" * 70)
            print("E*TRADE AUTHORIZATION REQUIRED")
            print("=" * 70)
            print("\nPlease authorize this application:  ")
            print(f"\n  {authorization_url}\n")

            if self.auto_authorize:
                print("Opening browser...")
                webbrowser.open(authorization_url)
            else:
                print("Please visit the URL above in your browser.")

            print("\nAfter authorizing, you will receive a verification code.")
            verification_code = input("Enter verification code: ").strip()
        else:
            # Web-based flow for non-interactive environments (MCP servers, etc.)
            logger.info(
                "Non-interactive environment detected, using web-based OAuth flow"
            )
            verification_code = self._web_oauth_flow(authorization_url)

        # Step 3: Exchange verification code for access token
        oauth = OAuth1Session(
            self.consumer_key,
            client_secret=self.consumer_secret,
            resource_owner_key=resource_owner_key,
            resource_owner_secret=resource_owner_secret,
            verifier=verification_code,
        )

        try:
            access_token_response = oauth.fetch_access_token(self.ACCESS_TOKEN_URL)
        except Exception as e:
            logger.error(f"Failed to get access token: {e}")
            raise

        # Store the authorized session
        oauth_token = access_token_response.get("oauth_token", "")
        oauth_token_secret = access_token_response.get("oauth_token_secret", "")

        self.session = OAuth1Session(
            self.consumer_key,
            client_secret=self.consumer_secret,
            resource_owner_key=oauth_token,
            resource_owner_secret=oauth_token_secret,
        )

        self._is_authorized = True
        self._token_expires_at = self._calculate_token_expiry()
        self._last_activity = datetime.now(UTC)

        # Save tokens for future use
        self._save_tokens(oauth_token, oauth_token_secret, self._token_expires_at)

        logger.info(
            f"Successfully authorized E*TRADE session for profile {self.profile_id}"
        )
        print("\n✓ Authorization successful!\n")
        print("=" * 70 + "\n")

    def _web_oauth_flow(self, authorization_url: str) -> str:
        """Conduct OAuth flow via temporary web server.

        Args:
            authorization_url: The E*TRADE authorization URL

        Returns:
            Verification code entered by user
        """
        return run_web_oauth_flow(authorization_url, timeout=300)

    def _ensure_authorized(self) -> None:
        """Ensure the session is authorized before making API calls.

        This will also renew tokens if they are expired or about to expire.
        """
        if not self._is_authorized or self.session is None:
            raise RuntimeError(
                "Not authorized. Call authorize() first to complete OAuth flow."
            )

        # Check if token needs renewal
        if self._is_token_expired():
            try:
                self._renew_tokens()
            except Exception as e:
                logger.error(f"Token renewal failed: {e}")
                raise RuntimeError(
                    "Token renewal failed. Please call authorize() again to "
                    "re-authenticate."
                ) from e

        # Update last activity time
        self._last_activity = datetime.now(UTC)

    def _get(
        self, endpoint: str, params: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Make a GET request to E*TRADE API.

        Args:
            endpoint: API endpoint path (e.g., '/v1/accounts/list')
            params: Optional query parameters

        Returns:
            Response JSON as dict
        """
        self._ensure_authorized()
        assert self.session is not None

        url = f"{self.base_url}{endpoint}"
        logger.debug(f"GET {url} with params {params}")

        response = self.session.get(url, params=params)
        response.raise_for_status()

        result: dict[str, Any] = response.json()
        return result

    def get_accounts(self) -> list[Account]:
        """Get list of all E*TRADE accounts.

        Returns:
            List of Account objects
        """
        logger.info("Fetching account list")
        data = self._get("/v1/accounts/list.json")

        accounts_data = (
            data.get("AccountListResponse", {}).get("Accounts", {}).get("Account", [])
        )

        # API sometimes returns a single dict instead of a list
        if isinstance(accounts_data, dict):
            accounts_data = [accounts_data]

        accounts = []
        for acct_data in accounts_data:
            # Skip closed accounts
            if acct_data.get("accountStatus") == "CLOSED":
                continue

            accounts.append(
                Account(
                    account_id=acct_data.get("accountId", ""),
                    account_id_key=acct_data.get("accountIdKey", ""),
                    account_mode=acct_data.get("accountMode", ""),
                    account_desc=acct_data.get("accountDesc", ""),
                    account_name=acct_data.get("accountName"),
                    account_type=acct_data.get("accountType", ""),
                    institution_type=acct_data.get("institutionType", ""),
                    account_status=acct_data.get("accountStatus", ""),
                    closed_date=acct_data.get("closedDate"),
                    profile_id=self.profile_id,
                    profile_label=self.profile_label,
                )
            )

        logger.info(f"Found {len(accounts)} active accounts")
        return accounts

    def get_account_balance(self, account_id_key: str) -> Balance:
        """Get detailed balance for a specific account.

        Args:
            account_id_key: Account identifier key (use account.account_id_key)

        Returns:
            Balance object with detailed account balance information
        """
        logger.info(f"Fetching balance for account {account_id_key}")

        # Note: The balance endpoint requires additional parameters based on
        # account type. For now, we'll get the account type from the account list
        accounts = self.get_accounts()
        account = next(
            (a for a in accounts if a.account_id_key == account_id_key), None
        )

        if account is None:
            raise ValueError(f"Account not found: {account_id_key}")

        params = {
            "instType": account.institution_type,
            "realTimeNAV": "true",
        }

        data = self._get(f"/v1/accounts/{account_id_key}/balance.json", params=params)

        balance_data = data.get("BalanceResponse", {})

        # Extract computed values
        computed = balance_data.get("Computed", {})
        realtime_values = computed.get("RealTimeValues", {})

        return Balance(
            account_id=balance_data.get("accountId", ""),
            account_type=balance_data.get("accountType", ""),
            account_description=balance_data.get("accountDescription"),
            account_mode=balance_data.get("accountMode"),
            cash_balance=self._extract_decimal(computed, "cashBalance"),
            cash_buying_power=self._extract_decimal(computed, "cashBuyingPower"),
            margin_buying_power=self._extract_decimal(computed, "marginBuyingPower"),
            total_account_value=self._extract_decimal(
                realtime_values, "totalAccountValue"
            ),
            net_account_value=self._extract_decimal(realtime_values, "netAccountValue"),
            uncleared_deposits=self._extract_decimal(computed, "unclearedDeposits"),
            funds_withheld_from_purchase_power=self._extract_decimal(
                computed, "fundsWithheldFromPurchasePower"
            ),
            funds_withheld_from_withdrawal=self._extract_decimal(
                computed, "fundsWithheldFromWithdrawal"
            ),
            profile_id=self.profile_id,
            profile_label=self.profile_label,
        )

    def get_account_portfolio(self, account_id_key: str) -> Portfolio:
        """Get portfolio (holdings) for a specific account.

        Args:
            account_id_key: Account identifier key (use account.account_id_key)

        Returns:
            Portfolio object with all positions
        """
        logger.info(f"Fetching portfolio for account {account_id_key}")
        data = self._get(f"/v1/accounts/{account_id_key}/portfolio.json")

        portfolio_response = data.get("PortfolioResponse", {})
        account_portfolios = portfolio_response.get("AccountPortfolio", [])

        # API sometimes returns a single dict instead of a list
        if isinstance(account_portfolios, dict):
            account_portfolios = [account_portfolios]

        positions = []
        total_market_value = Decimal("0")

        for acct_portfolio in account_portfolios:
            position_data_list = acct_portfolio.get("Position", [])

            # API sometimes returns a single dict instead of a list
            if isinstance(position_data_list, dict):
                position_data_list = [position_data_list]

            for pos_data in position_data_list:
                quick = pos_data.get("Quick", {})

                position = Position(
                    symbol=pos_data.get("symbolDescription", ""),
                    symbol_description=pos_data.get("symbolDescription", ""),
                    type_code=pos_data.get("Product", {}).get("securityType", ""),
                    quantity=Decimal(str(pos_data.get("quantity", 0))),
                    price_paid=self._extract_decimal(pos_data, "pricePaid"),
                    total_cost=self._extract_decimal(pos_data, "totalCost"),
                    cost_per_share=self._extract_decimal(pos_data, "costPerShare"),
                    last_trade=self._extract_decimal(quick, "lastTrade"),
                    market_value=self._extract_decimal(pos_data, "marketValue"),
                    total_gain=self._extract_decimal(pos_data, "totalGain"),
                    total_gain_pct=self._extract_decimal(pos_data, "totalGainPct"),
                    days_gain=self._extract_decimal(pos_data, "daysGain"),
                    days_gain_pct=self._extract_decimal(pos_data, "daysGainPct"),
                    position_type=pos_data.get("positionType"),
                    quote_detail=pos_data.get("quoteDetail"),
                )
                positions.append(position)

                if position.market_value:
                    total_market_value += position.market_value

        return Portfolio(
            account_id=account_id_key,
            positions=positions,
            total_market_value=total_market_value if total_market_value > 0 else None,
            profile_id=self.profile_id,
            profile_label=self.profile_label,
        )

    def get_quotes(self, symbols: list[str]) -> list[Quote]:
        """Get real-time or delayed quotes for securities.

        Args:
            symbols: List of symbols to get quotes for (max 25)

        Returns:
            List of Quote objects
        """
        if len(symbols) > 25:
            raise ValueError("Maximum 25 symbols allowed per request")

        if not symbols:
            return []

        logger.info(f"Fetching quotes for {len(symbols)} symbols")

        # Join symbols with comma for API
        symbol_string = ",".join(symbols)
        endpoint = f"/v1/market/quote/{symbol_string}.json"

        data = self._get(endpoint)

        quote_response = data.get("QuoteResponse", {})
        quote_data_list = quote_response.get("QuoteData", [])

        # API sometimes returns a single dict instead of a list
        if isinstance(quote_data_list, dict):
            quote_data_list = [quote_data_list]

        quotes = []
        for quote_data in quote_data_list:
            product = quote_data.get("Product", {})
            all_data = quote_data.get("All", {})

            quotes.append(
                Quote(
                    symbol=product.get("symbol", ""),
                    company_name=product.get("companyName"),
                    security_type=product.get("securityType"),
                    last_trade=self._extract_decimal(all_data, "lastTrade"),
                    bid=self._extract_decimal(all_data, "bid"),
                    ask=self._extract_decimal(all_data, "ask"),
                    change=self._extract_decimal(all_data, "change"),
                    change_pct=self._extract_decimal(all_data, "changePct"),
                    volume=all_data.get("totalVolume"),
                    bid_size=all_data.get("bidSize"),
                    ask_size=all_data.get("askSize"),
                    high=self._extract_decimal(all_data, "high"),
                    low=self._extract_decimal(all_data, "low"),
                    open=self._extract_decimal(all_data, "open"),
                    close=self._extract_decimal(all_data, "previousClose"),
                    high_52=self._extract_decimal(all_data, "high52"),
                    low_52=self._extract_decimal(all_data, "low52"),
                    pe_ratio=self._extract_decimal(all_data, "peRatio"),
                    dividend=self._extract_decimal(all_data, "annualDividend"),
                    dividend_yield=self._extract_decimal(all_data, "dividendYield"),
                    market_cap=self._extract_decimal(all_data, "marketCap"),
                    quote_status=all_data.get("quoteStatus"),
                    timestamp=all_data.get("dateTime"),
                )
            )

        return quotes

    def _extract_decimal(self, data: dict[str, Any], key: str) -> Decimal | None:
        """Extract a decimal value from a dict, handling missing or invalid values.

        Args:
            data: Dictionary to extract from
            key: Key to extract

        Returns:
            Decimal value or None if not present or invalid
        """
        value = data.get(key)
        if value is None:
            return None

        try:
            return Decimal(str(value))
        except (ValueError, TypeError, Exception):
            return None


def create_repository_from_env(profile_id: str = "0") -> ETradeRepository:
    """Create an ETradeRepository from environment variables for a specific profile.

    Environment variables (where N is the profile_id):
        - ETRADE_N_CONSUMER_KEY: Consumer key from E*TRADE developer portal
        - ETRADE_N_CONSUMER_SECRET: Consumer secret from E*TRADE developer portal
        - ETRADE_N_ENVIRONMENT: 'sandbox' or 'production' (optional, default: 'sandbox')
        - ETRADE_N_LABEL: Human-readable label for this profile (optional)

    Legacy environment variables (used when profile_id is "0"):
        - ETRADE_CONSUMER_KEY: Consumer key (fallback for profile 0)
        - ETRADE_CONSUMER_SECRET: Consumer secret (fallback for profile 0)
        - ETRADE_ENVIRONMENT: Environment (fallback for profile 0)

    Args:
        profile_id: Profile identifier (default: "0")

    Returns:
        Configured ETradeRepository instance
    """
    # Try profile-specific env vars first
    consumer_key = os.environ.get(f"ETRADE_{profile_id}_CONSUMER_KEY")
    consumer_secret = os.environ.get(f"ETRADE_{profile_id}_CONSUMER_SECRET")
    environment = os.environ.get(f"ETRADE_{profile_id}_ENVIRONMENT")
    label = os.environ.get(f"ETRADE_{profile_id}_LABEL")

    # Fallback to legacy env vars for profile 0
    if profile_id == "0":
        consumer_key = consumer_key or os.environ.get("ETRADE_CONSUMER_KEY")
        consumer_secret = consumer_secret or os.environ.get("ETRADE_CONSUMER_SECRET")
        environment = environment or os.environ.get("ETRADE_ENVIRONMENT")

    # Default environment to sandbox if not set
    if not environment:
        environment = "sandbox"

    if not consumer_key:
        raise ValueError(
            f"ETRADE_{profile_id}_CONSUMER_KEY environment variable is required"
        )
    if not consumer_secret:
        raise ValueError(
            f"ETRADE_{profile_id}_CONSUMER_SECRET environment variable is required"
        )

    return ETradeRepository(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        environment=environment,
        profile_id=profile_id,
        profile_label=label,
    )


def create_repositories_from_env() -> dict[str, ETradeRepository]:
    """Create ETradeRepository instances for all configured profiles.

    Scans environment variables for ETRADE_N_CONSUMER_KEY patterns
    and creates a repository for each profile found.

    Returns:
        Dictionary mapping profile_id to ETradeRepository instance
    """
    repositories = {}

    # Scan environment for all profiles
    profile_ids = set()

    # Check for legacy (profile 0) env vars
    if os.environ.get("ETRADE_CONSUMER_KEY") or os.environ.get("ETRADE_0_CONSUMER_KEY"):
        profile_ids.add("0")

    # Scan for numbered profiles
    for key in os.environ:
        if key.startswith("ETRADE_") and "_CONSUMER_KEY" in key:
            # Extract profile number: ETRADE_1_CONSUMER_KEY -> "1"
            parts = key.split("_")
            if len(parts) >= 3 and parts[1].isdigit():
                profile_ids.add(parts[1])

    if not profile_ids:
        raise ValueError(
            "No E*TRADE profiles found in environment. "
            "Set ETRADE_0_CONSUMER_KEY and ETRADE_0_CONSUMER_SECRET at minimum."
        )

    # Create repository for each profile
    for profile_id in sorted(profile_ids):
        repositories[profile_id] = create_repository_from_env(profile_id)

    return repositories
