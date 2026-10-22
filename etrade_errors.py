"""
Turning E*TRADE API errors into messages a model can act on.

The server masks the details of unexpected errors, so that a stack trace never
leaks internal state to the client.  An E*TRADE API error is different: E*TRADE
writes its error message for the caller ("Invalid account key specified in
request"), and the model needs that message to correct its next call.  This
middleware passes the message through as a ToolError, which the server never
masks.

FastMCP masks a tool's exception before middleware sees it, but it chains the
original exception as the masked error's cause, so that is where this looks.
"""

import logging
from typing import Self

import mcp.types as mt
import requests
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools import ToolResult

logger = logging.getLogger(__name__)


class ETradeError(Exception):
    """An E*TRADE API call failed, described in words a model can act on."""

    @classmethod
    def from_response(cls, response: requests.Response) -> Self:
        """Describe a failed E*TRADE response, without the OAuth credentials."""
        status = response.status_code
        if status == 401:
            return cls(
                "E*TRADE did not accept this profile's access token. The next "
                "call asks the user to authorize the profile again in a browser."
            )
        if status == 429:
            return cls(
                "E*TRADE's rate limit is exhausted. Wait a minute and try again."
            )

        message = None
        try:
            message = response.json()["Error"]["message"]
        except (ValueError, KeyError, TypeError):
            pass
        detail = message or response.reason or "no detail"
        return cls(f"E*TRADE returned {status}: {detail}")


class ETradeErrorMiddleware(Middleware):
    """Report E*TRADE API errors from any tool as ToolErrors."""

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        try:
            return await call_next(context)
        except ToolError as error:
            cause = error.__cause__
            if not isinstance(cause, ETradeError):
                raise
            logger.warning("E*TRADE API error in %s", context.method)
            raise ToolError(str(cause)) from cause
