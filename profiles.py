"""
Profiles: the E*TRADE logins this server is configured for.

Each profile is one E*TRADE user, such as each member of a household, with its
own API keys and its own access token.  Every account tool takes a profile ID.
"""

import os
from collections.abc import Callable

from fastmcp.dependencies import Shared
from fastmcp.exceptions import ToolError
from fastmcp.tools import tool
from pydantic import BaseModel, Field

from effects import READ, READS
from repository import ETradeRepository


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
    consumer_key = os.environ.get(f"ETRADE_{profile_id}_CONSUMER_KEY")
    consumer_secret = os.environ.get(f"ETRADE_{profile_id}_CONSUMER_SECRET")
    environment = os.environ.get(f"ETRADE_{profile_id}_ENVIRONMENT")
    label = os.environ.get(f"ETRADE_{profile_id}_LABEL")

    if profile_id == "0":
        consumer_key = consumer_key or os.environ.get("ETRADE_CONSUMER_KEY")
        consumer_secret = consumer_secret or os.environ.get("ETRADE_CONSUMER_SECRET")
        environment = environment or os.environ.get("ETRADE_ENVIRONMENT")

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
        environment=environment or "sandbox",
        profile_id=profile_id,
        profile_label=label,
    )


def create_repositories_from_env() -> dict[str, ETradeRepository]:
    """Create an ETradeRepository for every profile the environment configures.

    A profile is configured when ETRADE_N_CONSUMER_KEY is set, or, for profile
    0, the legacy ETRADE_CONSUMER_KEY.

    Returns:
        Dictionary mapping profile_id to ETradeRepository instance
    """
    profile_ids = set()

    if os.environ.get("ETRADE_CONSUMER_KEY") or os.environ.get("ETRADE_0_CONSUMER_KEY"):
        profile_ids.add("0")

    for key in os.environ:
        if key.startswith("ETRADE_") and "_CONSUMER_KEY" in key:
            # ETRADE_1_CONSUMER_KEY is profile "1"
            parts = key.split("_")
            if len(parts) >= 3 and parts[1].isdigit():
                profile_ids.add(parts[1])

    if not profile_ids:
        raise ValueError(
            "No E*TRADE profiles found in environment. "
            "Set ETRADE_0_CONSUMER_KEY and ETRADE_0_CONSUMER_SECRET at minimum."
        )

    return {
        profile_id: create_repository_from_env(profile_id)
        for profile_id in sorted(profile_ids)
    }


class Profiles:
    """The repository for each configured profile, by profile ID."""

    def __init__(self, repositories: dict[str, ETradeRepository]):
        self.repositories = repositories

    def repository(self, profile: str) -> ETradeRepository:
        """The repository for one profile.

        Raises:
            ToolError: no profile has this ID
        """
        repository = self.repositories.get(profile)
        if repository is None:
            raise ToolError(
                f"Profile {profile} not found. "
                f"Available profiles: {', '.join(sorted(self.repositories))}"
            )
        return repository


def configured_profiles() -> Profiles:
    """Build the profiles this server is configured for.

    Tools receive them through FastMCP's Shared dependency, so the server builds
    one repository per profile for its whole lifetime.  A profile authorizes
    with E*TRADE on its first request.
    """
    return Profiles(create_repositories_from_env())


class Profile(BaseModel):
    """One configured E*TRADE login."""

    profile_id: str = Field(
        ..., description="Profile identifier to pass as the profile argument"
    )
    profile_label: str | None = Field(
        None, description="Human-readable label for this profile"
    )
    environment: str = Field(
        ...,
        description="'production' for real accounts, 'sandbox' for E*TRADE's test data",
    )


class ProfilesResponse(BaseModel):
    """Response containing the configured profiles."""

    profiles: list[Profile] = Field(..., description="Configured profiles")


@tool(title="List profiles", tags={"profiles", READ}, annotations=READS)
def list_profiles(
    profiles: Profiles = Shared(configured_profiles),
) -> ProfilesResponse:
    """List the E*TRADE profiles this server is configured for.

    Each profile is a separate E*TRADE login, such as one per household member.
    Call this first when the user has more than one E*TRADE login, then pass a
    profile_id as the profile argument of the other tools.  This does not
    contact E*TRADE.

    Returns:
        ProfilesResponse with every configured profile
    """
    return ProfilesResponse(
        profiles=[
            Profile(
                profile_id=repository.profile_id,
                profile_label=repository.profile_label,
                environment=repository.environment,
            )
            for repository in profiles.repositories.values()
        ]
    )


TOOLS: list[Callable[..., object]] = [list_profiles]
