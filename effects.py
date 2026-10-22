"""
What each tool does to the user's E*TRADE accounts, declared the same way for
every tool.

MCP clients read tool annotations to decide when to ask the user before a call.
Every tool also carries a "read" or "write" tag.  Every tool on this server only
reads, so every tool is tagged "read".

Every tool works on the user's own E*TRADE accounts and E*TRADE's market data,
and reaches nothing else, so none of them is "open world" in the MCP sense.
"""

from mcp.types import ToolAnnotations

READ = "read"
WRITE = "write"

# Only reads accounts or market data.
READS = ToolAnnotations(read_only_hint=True, open_world_hint=False)
