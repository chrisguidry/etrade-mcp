"""
E*TRADE access tokens: where they are stored between runs, and when they expire.

The server stores each profile's access token in one JSON file, readable only
by the user, so that a restart does not ask the user to authorize again.

E*TRADE expires every access token at midnight US Eastern time, and deactivates
it after two hours with no requests.  A deactivated token can be renewed; an
expired one cannot.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import NamedTuple

logger = logging.getLogger(__name__)

# Renew a token this long before it expires or is deactivated.
RENEWAL_MARGIN = timedelta(minutes=30)


class AccessToken(NamedTuple):
    """An OAuth access token and the time it stops working."""

    token: str
    secret: str
    expires_at: datetime


def config_directory() -> Path:
    """The directory for this server's files, created if it is missing."""
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        directory = Path(xdg_config) / "etrade-mcp"
    else:
        directory = Path.home() / ".config" / "etrade-mcp"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def tokens_file() -> Path:
    """The file that holds every profile's access token."""
    return config_directory() / "tokens.json"


def save_token(profile_id: str, environment: str, access_token: AccessToken) -> None:
    """Store one profile's access token, keeping the other profiles' tokens."""
    path = tokens_file()
    all_tokens = json.loads(path.read_text()) if path.exists() else {}

    all_tokens[profile_id] = {
        "oauth_token": access_token.token,
        "oauth_token_secret": access_token.secret,
        "expires_at": access_token.expires_at.isoformat(),
        "environment": environment,
    }

    path.touch(mode=0o600, exist_ok=True)
    path.write_text(json.dumps(all_tokens, indent=2))
    logger.info(f"Saved tokens for profile {profile_id}")


def load_token(profile_id: str, environment: str) -> AccessToken | None:
    """Read one profile's access token, if one is stored for this environment."""
    path = tokens_file()
    if not path.exists():
        return None

    stored = json.loads(path.read_text()).get(profile_id)
    if not stored:
        return None

    if stored.get("environment") != environment:
        logger.warning(
            f"Token environment mismatch for profile {profile_id}: "
            f"expected {environment}, got {stored.get('environment')}"
        )
        return None

    token = stored.get("oauth_token")
    secret = stored.get("oauth_token_secret")
    expires_at = stored.get("expires_at")
    if not token or not secret or not expires_at:
        return None

    logger.info(f"Loaded tokens for profile {profile_id}")
    return AccessToken(token, secret, datetime.fromisoformat(expires_at))


def forget_token(profile_id: str) -> None:
    """Remove one profile's access token, so the next run authorizes again."""
    path = tokens_file()
    if not path.exists():
        return
    all_tokens = json.loads(path.read_text())
    all_tokens.pop(profile_id, None)
    path.write_text(json.dumps(all_tokens, indent=2))


def next_expiry(now: datetime) -> datetime:
    """When a token used at this moment expires or is deactivated.

    This takes Eastern time as UTC-4 all year.  During standard time, that puts
    midnight an hour early, so the server renews early, which is safe.
    """
    eastern_offset = timedelta(hours=-4)
    now_eastern = now + eastern_offset
    next_midnight_eastern = (now_eastern + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    midnight = next_midnight_eastern - eastern_offset
    return min(midnight, now + timedelta(hours=2))


def needs_renewal(expires_at: datetime | None, now: datetime) -> bool:
    """Whether a token is expired, or close enough to expiry to renew it now."""
    return expires_at is None or now >= expires_at - RENEWAL_MARGIN
