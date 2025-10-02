"""
Test assertion helpers for E*TRADE MCP Server tests.

This module provides helper functions for common test assertions and response
parsing to reduce boilerplate in test files.
"""

import json
import sys
from pathlib import Path
from typing import Any

from mcp.types import TextContent

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))


def extract_response_data(result: Any) -> dict[str, Any]:
    """Extract JSON data from MCP client response."""
    # Handle FastMCP CallToolResult format
    if not hasattr(result, "content"):
        raise TypeError(f"Expected CallToolResult with content, got {type(result)}")

    content = result.content
    assert len(content) == 1
    response_data: dict[str, Any] | None = (
        json.loads(content[0].text) if isinstance(content[0], TextContent) else None
    )
    assert response_data is not None
    return response_data
